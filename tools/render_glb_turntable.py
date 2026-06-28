"""Render GLB/GLTF assets through an SFB ViewContract using Blender.

This script is intended to be executed by Blender, not by normal Python:

blender --background --python tools/render_glb_turntable.py -- \
  --input sources/wall.glb \
  --asset-id wall_001 \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --out workspace/renders/wall_001 \
  --resolution 1024

Outputs per view:
- rgb.png      RGBA render with transparent background
- alpha.png    alpha mask extracted by the compositor
- depth.exr    Z pass
- normal.png   normal pass
- camera.json  SFB camera metadata

The script keeps lighting deliberately neutral and predictable. It is a
production starting point, not a renderer-specific art look.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore
except Exception:  # pragma: no cover - executed only outside Blender
    bpy = None
    Vector = None


def _argv_after_double_dash() -> list[str]:
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1 :]
    return []


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="render_glb_turntable.py")
    p.add_argument("--input", required=True, help="Source .glb/.gltf asset")
    p.add_argument("--asset-id", required=True)
    p.add_argument("--view-contract", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--resolution", type=int, default=1024)
    p.add_argument("--ortho-scale", type=float, default=None, help="Override camera orthographic scale")
    p.add_argument("--views", default=None, help="Optional comma-separated view_id subset")
    p.add_argument("--engine", default="BLENDER_EEVEE_NEXT", help="Blender render engine")
    return p.parse_args(_argv_after_double_dash())


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_asset(path: Path) -> list[object]:
    bpy.ops.import_scene.gltf(filepath=str(path))
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not mesh_objects:
        raise RuntimeError(f"No mesh objects found after importing {path}")
    return mesh_objects


def compute_bbox(objects: list[object]) -> tuple[Vector, Vector, Vector]:
    mins = Vector((float("inf"), float("inf"), float("inf")))
    maxs = Vector((float("-inf"), float("-inf"), float("-inf")))
    for obj in objects:
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            mins.x = min(mins.x, world.x)
            mins.y = min(mins.y, world.y)
            mins.z = min(mins.z, world.z)
            maxs.x = max(maxs.x, world.x)
            maxs.y = max(maxs.y, world.y)
            maxs.z = max(maxs.z, world.z)
    center = (mins + maxs) * 0.5
    size = maxs - mins
    return mins, maxs, center


def center_asset(objects: list[object]) -> dict[str, list[float] | float]:
    mins, maxs, center = compute_bbox(objects)
    for obj in objects:
        obj.location -= center
    mins2, maxs2, _ = compute_bbox(objects)
    size = maxs2 - mins2
    max_dim = max(size.x, size.y, size.z, 0.001)
    return {
        "bbox_min": [mins2.x, mins2.y, mins2.z],
        "bbox_max": [maxs2.x, maxs2.y, maxs2.z],
        "bbox_size": [size.x, size.y, size.z],
        "max_dim": max_dim,
    }


def setup_scene(resolution: int, engine: str) -> None:
    scene = bpy.context.scene
    try:
        scene.render.engine = engine
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    view_layer = scene.view_layers[0]
    view_layer.use_pass_z = True
    view_layer.use_pass_normal = True

    # Neutral, broad light without dramatic shadows.
    bpy.ops.object.light_add(type="AREA", location=(0, -4, 6))
    light = bpy.context.object
    light.name = "SFB_Neutral_Area_Light"
    light.data.energy = 350
    light.data.size = 6
    if hasattr(light.data, "use_shadow"):
        light.data.use_shadow = False
    world = scene.world or bpy.data.worlds.new("SFB_World")
    scene.world = world
    try:
        world.color = (1.0, 1.0, 1.0)
    except Exception:
        pass


def create_camera() -> object:
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.name = "SFB_Camera"
    cam.data.type = "ORTHO"
    bpy.context.scene.camera = cam
    return cam


def look_at(obj: object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def configure_camera(cam: object, *, azimuth_deg: float, elevation_deg: float, distance: float, ortho_scale: float) -> None:
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    horizontal = math.cos(el) * distance
    cam.location = Vector((math.sin(az) * horizontal, -math.cos(az) * horizontal, math.sin(el) * distance))
    look_at(cam, Vector((0, 0, 0)))
    cam.data.ortho_scale = ortho_scale


def setup_compositor(out_dir: Path) -> None:
    scene = bpy.context.scene
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    render_layers = tree.nodes.new(type="CompositorNodeRLayers")

    def output_node(name: str, file_format: str, color_mode: str, socket_name: str, slot_path: str) -> None:
        node = tree.nodes.new(type="CompositorNodeOutputFile")
        node.name = name
        node.base_path = str(out_dir)
        node.file_slots[0].path = slot_path
        node.format.file_format = file_format
        if hasattr(node.format, "color_mode"):
            node.format.color_mode = color_mode
        if file_format == "OPEN_EXR":
            node.format.color_depth = "32"
        tree.links.new(render_layers.outputs[socket_name], node.inputs[0])

    output_node("SFB_RGB", "PNG", "RGBA", "Image", "rgb_")
    output_node("SFB_ALPHA", "PNG", "BW", "Alpha", "alpha_")
    output_node("SFB_DEPTH", "OPEN_EXR", "BW", "Depth", "depth_")
    output_node("SFB_NORMAL", "PNG", "RGB", "Normal", "normal_")


def rename_compositor_outputs(out_dir: Path) -> None:
    mapping = {
        "rgb_": "rgb.png",
        "alpha_": "alpha.png",
        "depth_": "depth.exr",
        "normal_": "normal.png",
    }
    for prefix, final_name in mapping.items():
        candidates = sorted(out_dir.glob(f"{prefix}*"))
        if not candidates:
            continue
        target = out_dir / final_name
        if target.exists():
            target.unlink()
        candidates[0].rename(target)
        for extra in candidates[1:]:
            extra.unlink(missing_ok=True)


def render_view(asset_id: str, view: dict, out_root: Path, cam: object, bbox_info: dict, ortho_scale: float) -> None:
    view_id = view["view_id"]
    out_dir = out_root / view_id
    out_dir.mkdir(parents=True, exist_ok=True)
    setup_compositor(out_dir)
    distance = float(bbox_info["max_dim"]) * 3.0 + 1.0
    configure_camera(
        cam,
        azimuth_deg=float(view["azimuth_deg"]),
        elevation_deg=float(view["elevation_deg"]),
        distance=distance,
        ortho_scale=ortho_scale,
    )
    bpy.ops.render.render(write_still=False)
    rename_compositor_outputs(out_dir)
    camera_meta = {
        "schema": "sfb.camera.v1",
        "asset_id": asset_id,
        "view_id": view_id,
        "camera_type": "orthographic",
        "azimuth_deg": float(view["azimuth_deg"]),
        "elevation_deg": float(view["elevation_deg"]),
        "ortho_scale": ortho_scale,
        "camera_location": [cam.location.x, cam.location.y, cam.location.z],
        "camera_rotation_euler": list(cam.rotation_euler),
        "bbox": bbox_info,
    }
    (out_dir / "camera.json").write_text(json.dumps(camera_meta, indent=2), encoding="utf-8")


def main() -> int:
    if bpy is None:
        print("This script must be executed with Blender: blender --background --python tools/render_glb_turntable.py -- ...", file=sys.stderr)
        return 2
    args = parse_args()
    contract = json.loads(Path(args.view_contract).read_text(encoding="utf-8"))
    views = contract["views"]
    if args.views:
        wanted = {v.strip() for v in args.views.split(",") if v.strip()}
        views = [v for v in views if v["view_id"] in wanted]
    if not views:
        raise RuntimeError("No views selected for rendering")

    clear_scene()
    objects = import_asset(Path(args.input))
    bbox_info = center_asset(objects)
    setup_scene(args.resolution, args.engine)
    cam = create_camera()
    ortho_scale = args.ortho_scale or float(bbox_info["max_dim"]) / 0.8
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    for view in views:
        render_view(args.asset_id, view, out_root, cam, bbox_info, ortho_scale)
    print(json.dumps({"ok": True, "asset_id": args.asset_id, "views": len(views), "out": str(out_root)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
