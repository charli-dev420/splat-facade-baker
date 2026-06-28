from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json

import numpy as np
import trimesh
from PIL import Image

from .cleanup import clean_alpha_depth
from .config import BakeSettings
from .io_maps import load_luma, load_rgb, save_luma, save_rgb
from .mesh_json import export_sfbmesh_json
from .presets import get_mobile_preset


def resize_array(arr: np.ndarray, size: tuple[int, int], mode: str = "linear") -> np.ndarray:
    if arr.ndim == 2:
        img = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), mode="L")
        img = img.resize(size, Image.Resampling.BILINEAR if mode == "linear" else Image.Resampling.NEAREST)
        return np.asarray(img, dtype=np.float32) / 255.0
    img = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), mode="RGB")
    img = img.resize(size, Image.Resampling.BILINEAR)
    return np.asarray(img, dtype=np.float32) / 255.0


def resize_longest(arr: np.ndarray, max_size: int, mode: str = "linear") -> np.ndarray:
    if max_size <= 0:
        return arr
    h, w = arr.shape[:2]
    longest = max(h, w)
    if longest == max_size:
        return arr
    scale = max_size / max(longest, 1)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return resize_array(arr, (new_w, new_h), mode=mode)


def compute_normals_from_depth(depth: np.ndarray, width_m: float, height_m: float, max_depth_m: float) -> np.ndarray:
    h, w = depth.shape
    dzdx = np.gradient(depth * max_depth_m, width_m / max(w - 1, 1), axis=1)
    dzdy = np.gradient(depth * max_depth_m, height_m / max(h - 1, 1), axis=0)
    n = np.stack([-dzdx, -dzdy, np.ones_like(depth)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-8
    return n * 0.5 + 0.5


def build_flat_card_mesh(settings: BakeSettings) -> trimesh.Trimesh:
    settings.validate()
    x0 = -settings.width_m / 2.0
    x1 = settings.width_m / 2.0
    if settings.pivot == "bottom_center":
        y0, y1 = 0.0, settings.height_m
    else:
        y0, y1 = -settings.height_m / 2.0, settings.height_m / 2.0
    vertices = np.asarray([[x0, y0, 0.0], [x1, y0, 0.0], [x0, y1, 0.0], [x1, y1, 0.0]], dtype=np.float32)
    faces = np.asarray([[0, 2, 1], [1, 2, 3]], dtype=np.int64)
    uvs = np.asarray([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype=np.float32)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.visual = trimesh.visual.TextureVisuals(uv=uvs)
    return mesh


def build_depthcard_mesh(alpha: np.ndarray, depth: np.ndarray, settings: BakeSettings, *, grid: int | None = None) -> trimesh.Trimesh:
    settings.validate()
    grid_w = int(grid or settings.grid)
    grid_w = max(2, grid_w)
    grid_h = max(2, int(round(grid_w * settings.height_m / settings.width_m)))
    depth_g = resize_array(depth, (grid_w, grid_h), "linear")
    alpha_g = resize_array(alpha, (grid_w, grid_h), "linear")
    if settings.depth_invert:
        depth_g = 1.0 - depth_g

    xs = np.linspace(-settings.width_m / 2.0, settings.width_m / 2.0, grid_w)
    if settings.pivot == "bottom_center":
        ys = np.linspace(0.0, settings.height_m, grid_h)
    else:
        ys = np.linspace(-settings.height_m / 2.0, settings.height_m / 2.0, grid_h)

    vertices: list[list[float]] = []
    uvs: list[list[float]] = []
    index = -np.ones((grid_h, grid_w), dtype=np.int32)

    for j in range(grid_h):
        for i in range(grid_w):
            if alpha_g[j, i] < settings.alpha_threshold:
                continue
            z = -float(depth_g[j, i]) * settings.max_depth_m
            index[j, i] = len(vertices)
            vertices.append([float(xs[i]), float(ys[grid_h - 1 - j]), z])
            uvs.append([i / max(grid_w - 1, 1), 1.0 - j / max(grid_h - 1, 1)])

    faces: list[list[int]] = []
    for j in range(grid_h - 1):
        for i in range(grid_w - 1):
            a = int(index[j, i])
            b = int(index[j, i + 1])
            c = int(index[j + 1, i])
            d = int(index[j + 1, i + 1])
            if min(a, b, c, d) < 0:
                continue
            faces.append([a, c, b])
            faces.append([b, c, d])

    mesh = trimesh.Trimesh(vertices=np.asarray(vertices, dtype=np.float32), faces=np.asarray(faces, dtype=np.int64), process=False)
    mesh.visual = trimesh.visual.TextureVisuals(uv=np.asarray(uvs, dtype=np.float32))
    return mesh


def _lod_grid(settings: BakeSettings, lod_index: int) -> int:
    if lod_index == 0:
        return settings.grid
    if lod_index == 1:
        return max(2, int(round(settings.grid * settings.lod1_grid_scale)))
    return max(2, int(round(settings.grid * settings.lod2_grid_scale)))


def _mesh_for_lod(alpha: np.ndarray, depth: np.ndarray, settings: BakeSettings, lod_index: int) -> trimesh.Trimesh:
    if settings.mode == "flat_card":
        return build_flat_card_mesh(settings)
    if lod_index == 2 and settings.lod2_mode == "flat_card":
        return build_flat_card_mesh(settings)
    return build_depthcard_mesh(alpha, depth, settings, grid=_lod_grid(settings, lod_index))


def _export_mesh_lod(mesh: trimesh.Trimesh, mesh_dir: Path, settings: BakeSettings, lod_index: int) -> dict:
    stem = f"{settings.name}_LOD{lod_index}"
    glb_path = mesh_dir / f"{stem}.glb"
    obj_path = mesh_dir / f"{stem}.obj"
    sfbmesh_path = mesh_dir / f"{stem}.sfbmesh.json"
    mesh.export(glb_path)
    mesh.export(obj_path)
    export_sfbmesh_json(mesh, sfbmesh_path)
    return {
        "lod": lod_index,
        "path": str(glb_path),
        "obj_debug_path": str(obj_path),
        "sfbmesh_path": str(sfbmesh_path),
        "vertices": int(len(mesh.vertices)),
        "triangles": int(len(mesh.faces)),
    }


def _texture_memory_estimate_mb(width: int, height: int, *, normal_map: bool = True) -> float:
    # Conservative uncompressed estimate for review. Real runtime uses GPU compression.
    channels = 3 + 1 + 1 + 1  # albedo RGB + alpha + depth + mask
    if normal_map:
        channels += 3
    return float(width * height * channels / (1024 * 1024))


def _package_relative(output_dir: Path, path: str | Path) -> str:
    return str(Path(path).relative_to(output_dir)).replace("\\", "/")


def bake_maps(albedo_path: str | Path, alpha_path: str | Path, depth_path: str | Path, output_dir: str | Path, settings: BakeSettings) -> dict:
    settings.validate()
    output_dir = Path(output_dir)
    mesh_dir = output_dir / "mesh"
    tex_dir = output_dir / "textures"
    report_dir = output_dir / "reports"
    collision_dir = output_dir / "collision"
    preview_dir = output_dir / "preview"
    debug_dir = output_dir / "debug"
    for d in (mesh_dir, tex_dir, report_dir, collision_dir, preview_dir):
        d.mkdir(parents=True, exist_ok=True)
    if settings.save_clean_debug:
        debug_dir.mkdir(parents=True, exist_ok=True)

    albedo = load_rgb(albedo_path)
    alpha = load_luma(alpha_path)
    depth = load_luma(depth_path)

    if alpha.shape != depth.shape:
        depth = resize_array(depth, (alpha.shape[1], alpha.shape[0]), "linear")
    if albedo.shape[:2] != alpha.shape:
        albedo = resize_array(albedo, (alpha.shape[1], alpha.shape[0]), "linear")

    if settings.cleanup:
        alpha_clean, depth_clean, cleanup_stats = clean_alpha_depth(
            alpha,
            depth,
            alpha_threshold=settings.alpha_threshold,
            remove_components_smaller_than_px=settings.remove_components_smaller_than_px,
            keep_largest_component=settings.keep_largest_component,
            fill_holes_smaller_than_px=settings.fill_holes_smaller_than_px,
            edge_feather_px=settings.edge_feather_px,
            depth_clip_low_percentile=settings.depth_clip_low_percentile,
            depth_clip_high_percentile=settings.depth_clip_high_percentile,
            depth_smooth_radius=settings.depth_smooth_radius,
        )
    else:
        from .cleanup import CleanupStats

        alpha_clean = alpha
        depth_clean = depth
        mask = alpha >= settings.alpha_threshold
        visible = depth[mask]
        cleanup_stats = CleanupStats(
            alpha_threshold=settings.alpha_threshold,
            alpha_coverage_before=float(np.mean(mask)),
            alpha_coverage_after=float(np.mean(mask)),
            components_before=0,
            components_after=0,
            removed_components=0,
            filled_holes=0,
            depth_low_value=None,
            depth_high_value=None,
            depth_range_before=float(visible.max() - visible.min()) if visible.size else 0.0,
            depth_range_after=float(visible.max() - visible.min()) if visible.size else 0.0,
        )

    if settings.save_clean_debug:
        save_luma(debug_dir / f"{settings.name}_Alpha_raw.png", alpha)
        save_luma(debug_dir / f"{settings.name}_Depth_raw.png", depth)

    normal = compute_normals_from_depth(depth_clean, settings.width_m, settings.height_m, settings.max_depth_m)
    normal = normal * (alpha_clean[..., None] >= settings.alpha_threshold) + np.asarray([0.5, 0.5, 1.0], dtype=np.float32) * (alpha_clean[..., None] < settings.alpha_threshold)
    mask = (alpha_clean >= settings.alpha_threshold).astype(np.float32)

    texture_size = int(settings.texture_size)
    albedo_out = resize_longest(albedo, texture_size, "linear")
    alpha_out = resize_longest(alpha_clean, texture_size, "linear")
    depth_out = resize_longest(depth_clean, texture_size, "linear")
    normal_out = resize_longest(normal, texture_size, "linear")
    mask_out = resize_longest(mask, texture_size, "nearest")

    mesh_exports: list[dict] = []
    lod_count = min(max(settings.lod_count, 1), 3)
    for lod_index in range(lod_count):
        mesh = _mesh_for_lod(alpha_clean, depth_clean, settings, lod_index)
        mesh_exports.append(_export_mesh_lod(mesh, mesh_dir, settings, lod_index))

    save_rgb(tex_dir / f"{settings.name}_Albedo.png", albedo_out)
    save_luma(tex_dir / f"{settings.name}_Alpha.png", alpha_out)
    save_luma(tex_dir / f"{settings.name}_Depth.png", depth_out)
    save_rgb(tex_dir / f"{settings.name}_Normal.png", normal_out)
    save_luma(tex_dir / f"{settings.name}_Mask.png", mask_out)
    save_rgb(preview_dir / f"{settings.name}_preview.png", albedo_out * alpha_out[..., None] + (1.0 - alpha_out[..., None]))
    save_rgb(preview_dir / f"{settings.name}_depth_preview.png", np.repeat(depth_out[..., None], 3, axis=2))

    lod0 = mesh_exports[0]
    triangles = int(lod0["triangles"])
    vertices = int(lod0["vertices"])
    alpha_coverage = float(np.mean(alpha_clean >= settings.alpha_threshold))
    valid_depth = depth_clean[alpha_clean >= settings.alpha_threshold]
    depth_range_m = float((valid_depth.max() - valid_depth.min()) * settings.max_depth_m) if valid_depth.size else 0.0

    preset = get_mobile_preset(settings.mobile_tier)
    tex_h, tex_w = alpha_out.shape
    texture_memory_estimate_mb = _texture_memory_estimate_mb(tex_w, tex_h, normal_map=preset.normal_map)

    warnings: list[str] = []
    if triangles == 0:
        warnings.append("empty_mesh: alpha threshold removed all pixels")
    if alpha_coverage > 0.8:
        warnings.append("high_alpha_coverage: consider opaque silhouette mesh to reduce overdraw")
    if depth_range_m > settings.max_depth_m * 0.95:
        warnings.append("depth_range_near_limit: clipping/compression may be visible off-axis")
    if triangles > preset.triangles_lod0:
        warnings.append(f"triangle_budget_exceeded: lod0 has {triangles} tris, preset budget is {preset.triangles_lod0}")
    if max(tex_w, tex_h) > preset.texture_size:
        warnings.append(f"texture_budget_exceeded: texture longest side is {max(tex_w, tex_h)}, preset budget is {preset.texture_size}")
    if cleanup_stats.removed_components > 0:
        warnings.append(f"cleanup_removed_components: {cleanup_stats.removed_components} small/floating components removed")
    if cleanup_stats.filled_holes > 0:
        warnings.append(f"cleanup_filled_holes: {cleanup_stats.filled_holes} small holes filled")

    collider = {
        "schema": "sfb.collider.v1",
        "colliders": [
            {
                "type": "box",
                "center": [0.0, settings.height_m / 2.0, -settings.max_depth_m / 2.0],
                "size": [settings.width_m, settings.height_m, max(settings.max_depth_m, 0.01)],
            }
        ],
    }
    (collision_dir / "collider_proxy.json").write_text(json.dumps(collider, indent=2), encoding="utf-8")

    lod_report = {
        f"lod{item['lod']}": {
            "vertices": item["vertices"],
            "triangles": item["triangles"],
        }
        for item in mesh_exports
    }
    report = {
        "schema": "sfb.report.v1",
        "asset_id": settings.name,
        "status": "ok" if triangles > 0 else "failed",
        "warnings": warnings,
        "settings": settings.to_dict(),
        "cleanup": cleanup_stats.to_dict(),
        "metrics": {
            "vertices_lod0": vertices,
            "triangles_lod0": triangles,
            "lods": lod_report,
            "alpha_coverage": alpha_coverage,
            "depth_range_m": depth_range_m,
            "texture_width": tex_w,
            "texture_height": tex_h,
            "estimated_texture_memory_mb_uncompressed": round(texture_memory_estimate_mb, 3),
            "mobile_preset_triangle_budget_lod0": preset.triangles_lod0,
            "mobile_preset_texture_size": preset.texture_size,
        },
        "recommendations": [
            "use a simple mobile cutout/opaque material",
            "keep collision as primitive proxy",
            "use LOD2 flat card for far distance when possible",
        ],
    }

    mesh_package: dict[str, object] = {
        "triangles_lod0": triangles,
        "vertices_lod0": vertices,
    }
    for item in mesh_exports:
        lod_key = f"lod{item['lod']}"
        mesh_package[lod_key] = _package_relative(output_dir, item["path"])
        mesh_package[f"{lod_key}_sfbmesh"] = _package_relative(output_dir, item["sfbmesh_path"])
        mesh_package[f"{lod_key}_obj_debug"] = _package_relative(output_dir, item["obj_debug_path"])
        mesh_package[f"triangles_{lod_key}"] = item["triangles"]
        mesh_package[f"vertices_{lod_key}"] = item["vertices"]

    package = {
        "schema": "sfb.asset.v1",
        "asset_id": settings.name,
        "source_asset_id": settings.name,
        "source": "maps",
        "view_contract": settings.view_contract_id,
        "view_id": settings.view_id,
        "mode": settings.mode,
        "units": "meters",
        "width_m": settings.width_m,
        "height_m": settings.height_m,
        "max_depth_m": settings.max_depth_m,
        "pivot": settings.pivot,
        "camera": {
            "type": "orthographic",
            "azimuth_deg": settings.azimuth_deg,
            "elevation_deg": settings.elevation_deg,
        },
        "mesh": mesh_package,
        "textures": {
            "albedo": f"textures/{settings.name}_Albedo.png",
            "alpha": f"textures/{settings.name}_Alpha.png",
            "depth": f"textures/{settings.name}_Depth.png",
            "normal": f"textures/{settings.name}_Normal.png",
            "mask": f"textures/{settings.name}_Mask.png",
        },
        "collision": "collision/collider_proxy.json",
        "runtime": {
            "target": "mobile",
            "mobile_tier": settings.mobile_tier,
            "alpha_mode": preset.alpha_mode,
            "recommended_material": "SFB_Mobile_DepthCard",
            "lod_count": lod_count,
        },
        "preview": f"preview/{settings.name}_preview.png",
        "report": f"reports/{settings.name}_report.json",
    }

    (output_dir / "asset.sfb.json").write_text(json.dumps(package, indent=2), encoding="utf-8")
    (report_dir / f"{settings.name}_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return package
