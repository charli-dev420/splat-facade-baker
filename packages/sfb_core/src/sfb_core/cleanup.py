from __future__ import annotations

from dataclasses import asdict, dataclass
from collections import deque

import numpy as np


@dataclass(frozen=True)
class CleanupStats:
    alpha_threshold: float
    alpha_coverage_before: float
    alpha_coverage_after: float
    components_before: int
    components_after: int
    removed_components: int
    filled_holes: int
    depth_low_value: float | None
    depth_high_value: float | None
    depth_range_before: float
    depth_range_after: float

    def to_dict(self) -> dict:
        return asdict(self)


def _neighbors4(y: int, x: int, h: int, w: int):
    if y > 0:
        yield y - 1, x
    if y + 1 < h:
        yield y + 1, x
    if x > 0:
        yield y, x - 1
    if x + 1 < w:
        yield y, x + 1


def connected_components(mask: np.ndarray) -> tuple[np.ndarray, list[int], list[bool]]:
    """Return labels, component sizes and whether each component touches the image border.

    Label 0 means background. Component ids in sizes/touches_border start at 1.
    This pure-Numpy/Python implementation is deliberately dependency-light. It is
    intended for masks, not high-throughput image segmentation.
    """
    if mask.ndim != 2:
        raise ValueError("connected_components expects a 2D mask")
    mask_bool = mask.astype(bool)
    h, w = mask_bool.shape
    labels = np.zeros((h, w), dtype=np.int32)
    sizes: list[int] = [0]
    touches_border: list[bool] = [False]
    current = 0
    for y in range(h):
        for x in range(w):
            if not mask_bool[y, x] or labels[y, x] != 0:
                continue
            current += 1
            q: deque[tuple[int, int]] = deque([(y, x)])
            labels[y, x] = current
            size = 0
            border = False
            while q:
                cy, cx = q.popleft()
                size += 1
                if cy == 0 or cx == 0 or cy == h - 1 or cx == w - 1:
                    border = True
                for ny, nx in _neighbors4(cy, cx, h, w):
                    if mask_bool[ny, nx] and labels[ny, nx] == 0:
                        labels[ny, nx] = current
                        q.append((ny, nx))
            sizes.append(size)
            touches_border.append(border)
    return labels, sizes, touches_border


def remove_small_components(mask: np.ndarray, min_pixels: int, keep_largest: bool = False) -> tuple[np.ndarray, int, int, int]:
    labels, sizes, _ = connected_components(mask)
    components_before = max(len(sizes) - 1, 0)
    if components_before == 0:
        return mask.astype(bool), 0, 0, 0
    keep_ids: set[int] = set()
    if keep_largest:
        largest_id = max(range(1, len(sizes)), key=lambda idx: sizes[idx])
        keep_ids.add(largest_id)
    for idx, size in enumerate(sizes[1:], start=1):
        if size >= min_pixels:
            keep_ids.add(idx)
    cleaned = np.isin(labels, list(keep_ids))
    removed = components_before - len(keep_ids)
    components_after = len(keep_ids)
    return cleaned, components_before, components_after, max(removed, 0)


def fill_small_holes(mask: np.ndarray, max_hole_pixels: int) -> tuple[np.ndarray, int]:
    """Fill background components not touching the border, up to max_hole_pixels."""
    if max_hole_pixels <= 0:
        return mask.astype(bool), 0
    inv = ~mask.astype(bool)
    labels, sizes, touches_border = connected_components(inv)
    filled = mask.astype(bool).copy()
    filled_count = 0
    for idx in range(1, len(sizes)):
        if touches_border[idx]:
            continue
        if sizes[idx] <= max_hole_pixels:
            filled[labels == idx] = True
            filled_count += 1
    return filled, filled_count


def _blur_float(arr: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0:
        return arr.astype(np.float32)
    r = max(1, int(round(radius)))
    sigma = max(float(radius) * 0.5, 0.5)
    xs = np.arange(-r, r + 1, dtype=np.float32)
    kernel = np.exp(-(xs * xs) / (2.0 * sigma * sigma))
    kernel /= np.sum(kernel)
    src = arr.astype(np.float32)
    pad_x = np.pad(src, ((0, 0), (r, r)), mode="edge")
    tmp = np.empty_like(src, dtype=np.float32)
    for y in range(src.shape[0]):
        tmp[y, :] = np.convolve(pad_x[y, :], kernel, mode="valid")
    pad_y = np.pad(tmp, ((r, r), (0, 0)), mode="edge")
    out = np.empty_like(src, dtype=np.float32)
    for x in range(src.shape[1]):
        out[:, x] = np.convolve(pad_y[:, x], kernel, mode="valid")
    return out


def feather_alpha(alpha: np.ndarray, radius_px: int) -> np.ndarray:
    if radius_px <= 0:
        return np.clip(alpha.astype(np.float32), 0.0, 1.0)
    return np.clip(_blur_float(np.clip(alpha, 0.0, 1.0), float(radius_px)), 0.0, 1.0)


def smooth_depth_masked(depth: np.ndarray, mask: np.ndarray, radius_px: int) -> np.ndarray:
    if radius_px <= 0:
        return np.clip(depth.astype(np.float32), 0.0, 1.0)
    mask_f = mask.astype(np.float32)
    weighted = _blur_float(depth.astype(np.float32) * mask_f, radius_px)
    weights = _blur_float(mask_f, radius_px)
    smoothed = weighted / np.maximum(weights, 1e-6)
    return np.where(mask, smoothed, depth).astype(np.float32)


def clip_depth_percentiles(
    depth: np.ndarray,
    mask: np.ndarray,
    low_percentile: float,
    high_percentile: float,
) -> tuple[np.ndarray, float | None, float | None]:
    values = depth[mask.astype(bool)]
    if values.size == 0:
        return depth.astype(np.float32), None, None
    low = float(np.percentile(values, low_percentile))
    high = float(np.percentile(values, high_percentile))
    if high <= low + 1e-8:
        clipped = np.clip(depth, 0.0, 1.0)
        return clipped.astype(np.float32), low, high
    clipped = np.clip(depth, low, high)
    # Re-normalize only the visible depth range. This makes max_depth_m consistent after spike removal.
    normalized = (clipped - low) / (high - low)
    return np.clip(normalized, 0.0, 1.0).astype(np.float32), low, high


def clean_alpha_depth(
    alpha: np.ndarray,
    depth: np.ndarray,
    *,
    alpha_threshold: float,
    remove_components_smaller_than_px: int = 32,
    keep_largest_component: bool = False,
    fill_holes_smaller_than_px: int = 64,
    edge_feather_px: int = 0,
    depth_clip_low_percentile: float = 1.0,
    depth_clip_high_percentile: float = 99.0,
    depth_smooth_radius: int = 1,
) -> tuple[np.ndarray, np.ndarray, CleanupStats]:
    """Clean alpha/depth maps deterministically before mesh generation.

    The output alpha remains continuous, but its support is driven by the cleaned
    binary mask. This keeps the saved alpha useful for cutout/preview while the
    mesh builder can still apply its own alpha threshold.
    """
    if alpha.shape != depth.shape:
        raise ValueError("alpha and depth must have the same shape")
    alpha_f = np.clip(alpha.astype(np.float32), 0.0, 1.0)
    depth_f = np.clip(depth.astype(np.float32), 0.0, 1.0)
    mask_before = alpha_f >= alpha_threshold
    coverage_before = float(np.mean(mask_before))
    visible_before = depth_f[mask_before]
    depth_range_before = float(visible_before.max() - visible_before.min()) if visible_before.size else 0.0

    min_pixels = max(int(remove_components_smaller_than_px), 0)
    if min_pixels > 0 or keep_largest_component:
        cleaned_mask, components_before, components_after, removed = remove_small_components(mask_before, min_pixels, keep_largest_component)
    else:
        labels, sizes, _ = connected_components(mask_before)
        components_before = max(len(sizes) - 1, 0)
        cleaned_mask = mask_before
        components_after = components_before
        removed = 0

    cleaned_mask, filled_holes = fill_small_holes(cleaned_mask, int(fill_holes_smaller_than_px))

    clipped_depth, depth_low, depth_high = clip_depth_percentiles(
        depth_f,
        cleaned_mask,
        float(depth_clip_low_percentile),
        float(depth_clip_high_percentile),
    )
    smoothed_depth = smooth_depth_masked(clipped_depth, cleaned_mask, int(depth_smooth_radius))
    smoothed_depth = np.where(cleaned_mask, smoothed_depth, 0.0)

    cleaned_alpha = np.where(
        cleaned_mask,
        np.where(alpha_f >= alpha_threshold, alpha_f, 1.0),
        0.0,
    ).astype(np.float32)
    if edge_feather_px > 0:
        cleaned_alpha = feather_alpha(cleaned_alpha, int(edge_feather_px))
        cleaned_alpha = np.where(cleaned_mask | (cleaned_alpha > 0.001), cleaned_alpha, 0.0)

    coverage_after = float(np.mean(cleaned_alpha >= alpha_threshold))
    visible_after = smoothed_depth[cleaned_alpha >= alpha_threshold]
    depth_range_after = float(visible_after.max() - visible_after.min()) if visible_after.size else 0.0
    stats = CleanupStats(
        alpha_threshold=float(alpha_threshold),
        alpha_coverage_before=coverage_before,
        alpha_coverage_after=coverage_after,
        components_before=int(components_before),
        components_after=int(components_after),
        removed_components=int(removed),
        filled_holes=int(filled_holes),
        depth_low_value=depth_low,
        depth_high_value=depth_high,
        depth_range_before=depth_range_before,
        depth_range_after=depth_range_after,
    )
    return cleaned_alpha.astype(np.float32), smoothed_depth.astype(np.float32), stats
