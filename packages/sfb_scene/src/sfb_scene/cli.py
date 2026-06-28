from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .models import ChunkGroup, SFBScene, SceneCard
from .package_reader import card_defaults_from_package
from .placement import align_card_to_edge, update_chunk_bounds, with_resolved_view
from .validation import validate_scene


def _vec3(text: str) -> tuple[float, float, float]:
    parts = [float(x.strip()) for x in text.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("expected three comma-separated floats, e.g. 0,0,0")
    return (parts[0], parts[1], parts[2])


def _write_scene(scene: SFBScene, output: str | None, input_path: str | None = None) -> Path:
    out = Path(output or input_path or f"{scene.scene_id}.sfbscene.json")
    scene.save(out)
    return out


def _load_or_create(path: str | None, scene_id: str | None) -> SFBScene:
    if path and Path(path).exists():
        return SFBScene.load(path)
    if not scene_id:
        raise SystemExit("--scene-id is required when creating a new scene")
    return SFBScene(scene_id=scene_id)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", help="Output scene path. Defaults to input scene path for mutating commands.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sfb-scene")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create an empty .sfbscene.json file")
    create.add_argument("--scene-id", required=True)
    create.add_argument("--out", required=True)
    create.add_argument("--camera-mode", default="isometric_2_5d")
    create.add_argument("--mobile-profile", default="mobile_mid")

    inspect = sub.add_parser("inspect", help="Print a scene summary")
    inspect.add_argument("scene")

    add_chunk = sub.add_parser("add-chunk", help="Add or replace a chunk")
    add_chunk.add_argument("scene")
    add_chunk.add_argument("--chunk-id", required=True)
    add_chunk.add_argument("--name", default="")
    add_chunk.add_argument("--mobile-profile", default="mobile_mid")
    add_chunk.add_argument("--occlusion-layer", type=int, default=0)
    add_chunk.add_argument("--replace", action="store_true")
    _add_common_args(add_chunk)

    add_card = sub.add_parser("add-card", help="Add a SceneCard from an SFB asset package")
    add_card.add_argument("scene")
    add_card.add_argument("--scene-card-id", required=True)
    add_card.add_argument("--asset-package", required=True)
    add_card.add_argument("--view-id")
    add_card.add_argument("--view-contract")
    add_card.add_argument("--position", type=_vec3, default=(0.0, 0.0, 0.0))
    add_card.add_argument("--scale", type=_vec3, default=(1.0, 1.0, 1.0))
    add_card.add_argument("--base-rotation-y", type=float, default=0.0)
    add_card.add_argument("--rotation-y", type=float)
    add_card.add_argument("--width-m", type=float)
    add_card.add_argument("--height-m", type=float)
    add_card.add_argument("--depth-m", type=float)
    add_card.add_argument("--pivot", default=None)
    add_card.add_argument("--chunk-id")
    add_card.add_argument("--occlusion-layer", type=int, default=0)
    add_card.add_argument("--status", default="unreviewed")
    add_card.add_argument("--replace", action="store_true")
    _add_common_args(add_card)

    align = sub.add_parser("align-edge", help="Align one card to the left/right edge of another")
    align.add_argument("scene")
    align.add_argument("--card-id", required=True)
    align.add_argument("--target-card-id", required=True)
    align.add_argument("--edge", choices=["left", "right"], default="right")
    align.add_argument("--overlap-m", type=float, default=0.0)
    _add_common_args(align)

    update_bounds = sub.add_parser("update-chunk-bounds", help="Recompute bounds for one chunk")
    update_bounds.add_argument("scene")
    update_bounds.add_argument("--chunk-id", required=True)
    _add_common_args(update_bounds)

    validate = sub.add_parser("validate", help="Validate a scene and optionally write a report")
    validate.add_argument("scene")
    validate.add_argument("--out")

    args = parser.parse_args(argv)

    if args.command == "create":
        scene = SFBScene(scene_id=args.scene_id)
        scene.target.camera_mode = args.camera_mode
        scene.target.mobile_profile = args.mobile_profile
        scene.save(args.out)
        print(json.dumps({"scene_id": scene.scene_id, "path": args.out}, indent=2))
        return 0

    if args.command == "inspect":
        scene = SFBScene.load(args.scene)
        print(json.dumps({
            "scene_id": scene.scene_id,
            "cards": len(scene.cards),
            "chunks": len(scene.chunks),
            "target": scene.target.model_dump(),
        }, indent=2))
        return 0

    if args.command == "add-chunk":
        scene = SFBScene.load(args.scene)
        scene.add_chunk(
            ChunkGroup(
                chunk_id=args.chunk_id,
                name=args.name,
                mobile_profile=args.mobile_profile,
                occlusion_layer=args.occlusion_layer,
            ),
            replace=args.replace,
        )
        out = _write_scene(scene, args.out, args.scene)
        print(json.dumps({"ok": True, "scene": str(out), "chunks": len(scene.chunks)}, indent=2))
        return 0

    if args.command == "add-card":
        scene = SFBScene.load(args.scene)
        defaults: dict[str, Any] = card_defaults_from_package(args.asset_package)
        view_id = args.view_id or defaults.get("view_id") or "front"
        data = {
            **defaults,
            "scene_card_id": args.scene_card_id,
            "asset_package": args.asset_package,
            "view_id": view_id,
            "position": args.position,
            "scale": args.scale,
            "base_rotation_y": args.base_rotation_y,
            "rotation_y": args.rotation_y if args.rotation_y is not None else 0.0,
            "chunk_id": args.chunk_id,
            "occlusion_layer": args.occlusion_layer,
            "status": args.status,
        }
        if args.width_m is not None:
            data["width_m"] = args.width_m
        if args.height_m is not None:
            data["height_m"] = args.height_m
        if args.depth_m is not None:
            data["depth_m"] = args.depth_m
        if args.pivot is not None:
            data["pivot"] = args.pivot
        if args.view_contract:
            data["view_contract"] = args.view_contract
        card = SceneCard(**data)
        if args.view_contract and args.rotation_y is None:
            card = with_resolved_view(card, args.view_contract, base_rotation_y=args.base_rotation_y)
            if args.view_contract not in scene.view_contracts:
                scene.view_contracts.append(args.view_contract)
        scene.add_card(card, replace=args.replace)
        out = _write_scene(scene, args.out, args.scene)
        print(json.dumps({"ok": True, "scene": str(out), "cards": len(scene.cards), "rotation_y": card.rotation_y}, indent=2))
        return 0

    if args.command == "align-edge":
        scene = SFBScene.load(args.scene)
        scene = align_card_to_edge(scene, card_id=args.card_id, target_card_id=args.target_card_id, edge=args.edge, overlap_m=args.overlap_m)
        out = _write_scene(scene, args.out, args.scene)
        print(json.dumps({"ok": True, "scene": str(out)}, indent=2))
        return 0

    if args.command == "update-chunk-bounds":
        scene = SFBScene.load(args.scene)
        update_chunk_bounds(scene, args.chunk_id)
        out = _write_scene(scene, args.out, args.scene)
        print(json.dumps({"ok": True, "scene": str(out), "chunk_id": args.chunk_id}, indent=2))
        return 0

    if args.command == "validate":
        scene = SFBScene.load(args.scene)
        report = validate_scene(scene, scene_path=args.scene)
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if report["status"] != "failed" else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
