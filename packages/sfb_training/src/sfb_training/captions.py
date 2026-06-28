from __future__ import annotations

from .manifest_io import TrainingAsset

FORMAT_TAGS = [
    "sfb_clean_render",
    "orthographic object render",
    "centered single asset",
    "solid neutral background",
    "neutral soft lighting",
    "no cast shadow",
    "no bloom",
    "no cinematic lighting",
    "no particles",
    "no text",
    "clean silhouette",
    "trellis friendly image",
    "splat friendly image",
]

NEGATIVE_PROMPT = (
    "busy background, scenery, environment, dramatic shadows, cast shadow, bloom, glow, "
    "particles, fog, smoke, depth of field, watermark, text, label, frame, cropped object, "
    "cinematic lighting, strong rim light, clutter, multiple objects"
)


def clean_tokens(tokens: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        token = " ".join(str(token).strip().split())
        if not token:
            continue
        key = token.lower()
        if key not in seen:
            seen.add(key)
            out.append(token)
    return out


def build_lora_caption(asset: TrainingAsset, view_id: str, *, extra_tags: list[str] | None = None) -> str:
    tokens = list(FORMAT_TAGS)
    tokens.append(f"{view_id} view")
    if asset.category and asset.category != "uncategorized":
        tokens.append(asset.category.replace("_", " "))
    # style_family is intentionally late in the caption so the clean-render behavior dominates.
    if asset.style_family and asset.style_family != "unknown":
        tokens.append(f"style family {asset.style_family}")
    tokens.extend(asset.tags)
    if extra_tags:
        tokens.extend(extra_tags)
    if asset.base_caption:
        tokens.append(asset.base_caption)
    return ", ".join(clean_tokens(tokens))


def build_view_pair_caption(
    asset: TrainingAsset,
    *,
    source_view_id: str,
    target_view_id: str,
    target_azimuth_deg: float | None = None,
    target_elevation_deg: float | None = None,
    extra_tags: list[str] | None = None,
) -> str:
    tokens = [
        "sfb_clean_render",
        "image to target view translation",
        "preserve object identity",
        "solid neutral background",
        "neutral soft lighting",
        "clean silhouette",
        f"source view {source_view_id}",
        f"target view {target_view_id}",
    ]
    if target_azimuth_deg is not None:
        tokens.append(f"target azimuth {target_azimuth_deg:g} degrees")
    if target_elevation_deg is not None:
        tokens.append(f"target elevation {target_elevation_deg:g} degrees")
    if asset.category and asset.category != "uncategorized":
        tokens.append(asset.category.replace("_", " "))
    tokens.extend(asset.tags)
    if extra_tags:
        tokens.extend(extra_tags)
    if asset.base_caption:
        tokens.append(asset.base_caption)
    return ", ".join(clean_tokens(tokens))
