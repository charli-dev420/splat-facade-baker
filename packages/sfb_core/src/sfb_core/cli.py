from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import BakeSettings
from .depthcard import bake_maps
from .splat_maps import SplatRenderRequest, render_splat_to_maps
from .view_contract import load_view_contract


def _add_bake_maps(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("bake-maps", help="Bake albedo/alpha/depth maps into an SFB depth-card package.")
    p.add_argument("--albedo", required=True)
    p.add_argument("--alpha", required=True)
    p.add_argument("--depth", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--name", default="SFB_Asset")
    p.add_argument("--width-m", type=float, default=8.0)
    p.add_argument("--height-m", type=float, default=4.0)
    p.add_argument("--max-depth-m", type=float, default=0.5)
    p.add_argument("--grid", type=int, default=96)
    p.add_argument("--alpha-threshold", type=float, default=0.05)
    p.add_argument("--depth-invert", action="store_true")
    p.add_argument("--pivot", default="bottom_center")
    p.add_argument("--mode", default="depth_card", choices=["flat_card", "depth_card", "layered_card", "multi_angle_impostor"])
    p.add_argument("--mobile-tier", default="mobile_mid")
    p.add_argument("--view-contract", help="Path to a ViewContract JSON file")
    p.add_argument("--view-id", default="front")

    cleanup = p.add_argument_group("cleanup")
    cleanup.add_argument("--no-cleanup", action="store_true", help="Disable deterministic alpha/depth cleanup.")
    cleanup.add_argument("--keep-largest-component", action="store_true", help="Keep the largest alpha component and remove smaller islands.")
    cleanup.add_argument("--remove-components-smaller-than-px", type=int, default=32)
    cleanup.add_argument("--fill-holes-smaller-than-px", type=int, default=64)
    cleanup.add_argument("--edge-feather-px", type=int, default=0)
    cleanup.add_argument("--depth-clip-low-percentile", type=float, default=1.0)
    cleanup.add_argument("--depth-clip-high-percentile", type=float, default=99.0)
    cleanup.add_argument("--depth-smooth-radius", type=int, default=1)
    cleanup.add_argument("--save-clean-debug", action="store_true")

    lod = p.add_argument_group("lod/texture")
    lod.add_argument("--lod-count", type=int, default=3)
    lod.add_argument("--lod1-grid-scale", type=float, default=0.5)
    lod.add_argument("--lod2-grid-scale", type=float, default=0.25)
    lod.add_argument("--lod2-mode", choices=["flat_card", "depth_card"], default="flat_card")
    lod.add_argument("--texture-size", type=int, default=0, help="Resize output textures so their longest side matches this value. 0 keeps source resolution.")


def _add_bake_splat(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "bake-splat",
        help="Experimental, non-MVP splat -> maps command. Returns not_implemented until a renderer is integrated.",
        description="Experimental, non-MVP splat -> maps command. Returns not_implemented until a renderer is integrated.",
    )
    p.add_argument("--input", required=True, help="Input .ply/.splat/.spz")
    p.add_argument("--out", required=True)
    p.add_argument("--view-contract", required=True)
    p.add_argument("--view-id", default="front")
    p.add_argument("--width-m", type=float, default=8.0)
    p.add_argument("--height-m", type=float, default=4.0)
    p.add_argument("--max-depth-m", type=float, default=0.5)
    p.add_argument("--resolution", type=int, default=1024)


def _add_view_contract(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("view-contract", help="Inspect a ViewContract JSON file.")
    p.add_argument("path")


def _settings_from_bake_maps_args(args: argparse.Namespace) -> BakeSettings:
    view_contract_id = "manual"
    azimuth = 0.0
    elevation = 0.0
    mode = args.mode
    if args.view_contract:
        contract = load_view_contract(args.view_contract)
        view = contract.get(args.view_id)
        view_contract_id = contract.view_contract_id
        azimuth = view.azimuth_deg
        elevation = view.elevation_deg
        mode = args.mode or view.bake_mode

    return BakeSettings(
        name=args.name,
        width_m=args.width_m,
        height_m=args.height_m,
        max_depth_m=args.max_depth_m,
        grid=args.grid,
        alpha_threshold=args.alpha_threshold,
        depth_invert=args.depth_invert,
        pivot=args.pivot,
        mode=mode,
        view_contract_id=view_contract_id,
        view_id=args.view_id,
        canonical_view=args.view_id,
        azimuth_deg=azimuth,
        elevation_deg=elevation,
        mobile_tier=args.mobile_tier,
        cleanup=not args.no_cleanup,
        keep_largest_component=args.keep_largest_component,
        remove_components_smaller_than_px=args.remove_components_smaller_than_px,
        fill_holes_smaller_than_px=args.fill_holes_smaller_than_px,
        edge_feather_px=args.edge_feather_px,
        depth_clip_low_percentile=args.depth_clip_low_percentile,
        depth_clip_high_percentile=args.depth_clip_high_percentile,
        depth_smooth_radius=args.depth_smooth_radius,
        lod_count=args.lod_count,
        lod1_grid_scale=args.lod1_grid_scale,
        lod2_grid_scale=args.lod2_grid_scale,
        lod2_mode=args.lod2_mode,
        texture_size=args.texture_size,
        save_clean_debug=args.save_clean_debug,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sfb", description="Splat Facade Baker CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_bake_maps(subparsers)
    _add_bake_splat(subparsers)
    _add_view_contract(subparsers)
    args = parser.parse_args(argv)

    if args.command == "view-contract":
        contract = load_view_contract(args.path)
        print(json.dumps({
            "view_contract_id": contract.view_contract_id,
            "camera_type": contract.camera_type,
            "views": [v.__dict__ for v in contract.views],
        }, indent=2))
        return 0

    if args.command == "bake-maps":
        settings = _settings_from_bake_maps_args(args)
        package = bake_maps(args.albedo, args.alpha, args.depth, args.out, settings)
        print(json.dumps({
            "ok": True,
            "package": str(Path(args.out) / "asset.sfb.json"),
            "triangles": package["mesh"]["triangles_lod0"],
            "view_contract": package["view_contract"],
            "view_id": package["view_id"],
            "lod_count": package["runtime"]["lod_count"],
        }, indent=2))
        return 0

    if args.command == "bake-splat":
        contract = load_view_contract(args.view_contract)
        contract.get(args.view_id)
        request = SplatRenderRequest(
            input_splat=Path(args.input),
            output_dir=Path(args.out),
            view_contract_id=contract.view_contract_id,
            view_id=args.view_id,
            width_m=args.width_m,
            height_m=args.height_m,
            max_depth_m=args.max_depth_m,
            resolution=args.resolution,
        )
        try:
            render_splat_to_maps(request)
        except NotImplementedError as exc:
            print(json.dumps({
                "ok": False,
                "status": "not_implemented",
                "experimental": True,
                "mvp_contract": "excluded_pre_mvp",
                "message": str(exc),
            }, indent=2))
            return 3
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
