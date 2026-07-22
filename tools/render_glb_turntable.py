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
    p.add_argument(
        "--ortho-scale",
        type=float,
        default=None,
        help="Override camera orthographic scale",
    )
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


def configure_camera(
    cam: object,
    *,
    azimuth_deg: float,
    elevation_deg: float,
    distance: float,
    ortho_scale: float,
) -> None:
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    horizontal = math.cos(el) * distance
    cam.location = Vector(
        (math.sin(az) * horizontal, -math.cos(az) * horizontal, math.sin(el) * distance)
    )
    look_at(cam, Vector((0, 0, 0)))
    cam.data.ortho_scale = ortho_scale


def setup_compositor(out_dir: Path, enabled_outputs: set[str] | None = None) -> None:
    scene = bpy.context.scene
    if hasattr(scene, "node_tree"):
        scene.use_nodes = True
        tree = scene.node_tree
    else:
        tree = scene.compositing_node_group
        if tree is None:
            tree = bpy.data.node_groups.new("SFB_Compositor", "CompositorNodeTree")
            scene.compositing_node_group = tree
    tree.nodes.clear()
    render_layers = tree.nodes.new(type="CompositorNodeRLayers")

    def output_node(
        name: str,
        file_format: str,
        color_mode: str,
        socket_name: str,
        slot_path: str,
    ) -> None:
        node = tree.nodes.new(type="CompositorNodeOutputFile")
        node.name = name
        if hasattr(node, "base_path"):
            node.base_path = str(out_dir)
            node.file_slots[0].path = slot_path
            input_socket = node.inputs[0]
        else:
            node.directory = str(out_dir)
            node.file_name = slot_path
            node.file_output_items.clear()
            socket_type = {
                "Image": "RGBA",
                "Alpha": "FLOAT",
                "Depth": "FLOAT",
                "Normal": "VECTOR",
            }[socket_name]
            item = node.file_output_items.new(socket_type, slot_path)
            item.override_node_format = True
            input_socket = node.inputs[item.name]
            fmt = item.format
            fmt.file_format = file_format
            if hasattr(fmt, "color_mode"):
                fmt.color_mode = color_mode
            if file_format == "OPEN_EXR":
                fmt.color_depth = "32"
            tree.links.new(render_layers.outputs[socket_name], input_socket)
            return
        node.format.file_format = file_format
        if hasattr(node.format, "color_mode"):
            node.format.color_mode = color_mode
        if file_format == "OPEN_EXR":
            node.format.color_depth = "32"
        tree.links.new(render_layers.outputs[socket_name], input_socket)

    outputs = enabled_outputs or {"rgb_", "alpha_", "depth_", "normal_"}
    if "rgb_" in outputs:
        output_node("SFB_RGB", "PNG", "RGBA", "Image", "rgb_")
    if "alpha_" in outputs:
        output_node("SFB_ALPHA", "PNG", "BW", "Alpha", "alpha_")
    if "depth_" in outputs:
        output_node("SFB_DEPTH", "OPEN_EXR", "BW", "Depth", "depth_")
    if "normal_" in outputs:
        output_node("SFB_NORMAL", "PNG", "RGB", "Normal", "normal_")


def convert_image_to_png(source: Path, target: Path) -> None:
    image = bpy.data.images.load(str(source), check_existing=False)
    try:
        image.filepath_raw = str(target)
        image.file_format = "PNG"
        image.save()
    finally:
        bpy.data.images.remove(image)


def rename_compositor_outputs(out_dir: Path, enabled_outputs: set[str] | None = None) -> None:
    mapping = {
        "rgb_": "rgb.png",
        "alpha_": "alpha.png",
        "depth_": "depth.exr",
        "normal_": "normal.png",
    }
    for prefix, final_name in mapping.items():
        if enabled_outputs is not None and prefix not in enabled_outputs:
            continue
        candidates = sorted(out_dir.glob(f"{prefix}*"))
        if not candidates:
            continue
        target = out_dir / final_name
        if target.exists():
            target.unlink()
        source = candidates[0]
        if target.suffix.lower() == ".png" and source.suffix.lower() != ".png":
            convert_image_to_png(source, target)
            source.unlink(missing_ok=True)
        else:
            source.rename(target)
        for extra in candidates[1:]:
            extra.unlink(missing_ok=True)


def clear_managed_outputs(out_dir: Path) -> None:
    patterns = [
        "rgb.png",
        "alpha.png",
        "normal.png",
        "depth.exr",
        "camera.json",
        "rgb_*",
        "alpha_*",
        "normal_*",
        "depth_*",
        "file_name.exr",
    ]
    for pattern in patterns:
        for path in out_dir.glob(pattern):
            if path.is_file():
                path.unlink()


def create_normal_material() -> object:
    mat = bpy.data.materials.new("SFB_Normal_Override")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    output = nodes.new(type="ShaderNodeOutputMaterial")
    geometry = nodes.new(type="ShaderNodeNewGeometry")
    add = nodes.new(type="ShaderNodeVectorMath")
    add.operation = "ADD"
    add.inputs[1].default_value = (1.0, 1.0, 1.0)
    scale = nodes.new(type="ShaderNodeVectorMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = (0.5, 0.5, 0.5)
    emission = nodes.new(type="ShaderNodeEmission")
    emission.inputs["Strength"].default_value = 1.0
    links = mat.node_tree.links
    links.new(geometry.outputs["Normal"], add.inputs[0])
    links.new(add.outputs["Vector"], scale.inputs[0])
    links.new(scale.outputs["Vector"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def render_png(path: Path, color_mode: str) -> None:
    scene = bpy.context.scene
    scene.render.filepath = str(path)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = color_mode
    bpy.ops.render.render(write_still=True)


def save_alpha_from_rgba(source: Path, target: Path) -> None:
    image = bpy.data.images.load(str(source), check_existing=False)
    mask = None
    try:
        width, height = image.size
        pixels = list(image.pixels)
        mask = bpy.data.images.new("SFB_Alpha_Mask", width=width, height=height, alpha=True)
        mask_pixels: list[float] = []
        for idx in range(0, len(pixels), 4):
            alpha = pixels[idx + 3]
            mask_pixels.extend([alpha, alpha, alpha, 1.0])
        mask.pixels.foreach_set(mask_pixels)
        mask.filepath_raw = str(target)
        mask.file_format = "PNG"
        mask.save()
    finally:
        if mask is not None:
            bpy.data.images.remove(mask)
        bpy.data.images.remove(image)


def render_blender_5_outputs(out_dir: Path) -> None:
    scene = bpy.context.scene
    view_layer = scene.view_layers[0]
    world = scene.world or bpy.data.worlds.new("SFB_World")
    scene.world = world
    old_override = getattr(view_layer, "material_override", None)
    old_film_transparent = scene.render.film_transparent
    old_filepath = scene.render.filepath
    old_file_format = scene.render.image_settings.file_format
    old_color_mode = scene.render.image_settings.color_mode
    old_world_color = tuple(world.color)
    normal_mat = create_normal_material()
    setup_compositor(out_dir, {"depth_"})
    try:
        view_layer.material_override = None
        scene.render.film_transparent = True
        rgb_path = out_dir / "rgb.png"
        render_png(rgb_path, "RGBA")
        save_alpha_from_rgba(rgb_path, out_dir / "alpha.png")

        world.color = (0.0, 0.0, 0.0)
        scene.render.film_transparent = False
        view_layer.material_override = normal_mat
        render_png(out_dir / "normal.png", "RGB")
        rename_compositor_outputs(out_dir, {"depth_"})
    finally:
        view_layer.material_override = old_override
        scene.render.film_transparent = old_film_transparent
        scene.render.filepath = old_filepath
        scene.render.image_settings.file_format = old_file_format
        scene.render.image_settings.color_mode = old_color_mode
        world.color = old_world_color


def render_view(
    asset_id: str,
    view: dict,
    out_root: Path,
    cam: object,
    bbox_info: dict,
    ortho_scale: float,
) -> None:
    view_id = view["view_id"]
    out_dir = out_root / view_id
    out_dir.mkdir(parents=True, exist_ok=True)
    clear_managed_outputs(out_dir)
    distance = float(bbox_info["max_dim"]) * 3.0 + 1.0
    configure_camera(
        cam,
        azimuth_deg=float(view["azimuth_deg"]),
        elevation_deg=float(view["elevation_deg"]),
        distance=distance,
        ortho_scale=ortho_scale,
    )
    if hasattr(bpy.context.scene, "node_tree"):
        setup_compositor(out_dir)
        bpy.ops.render.render(write_still=False)
        rename_compositor_outputs(out_dir)
    else:
        render_blender_5_outputs(out_dir)
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
        print(
            "This script must be executed with Blender: "
            "blender --background --python tools/render_glb_turntable.py -- ...",
            file=sys.stderr,
        )
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
    print(
        json.dumps(
            {"ok": True, "asset_id": args.asset_id, "views": len(views), "out": str(out_root)},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
