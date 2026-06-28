from __future__ import annotations

import argparse
import json
from pathlib import Path

from .capture_plan import attach_expected_views, build_capture_plan, save_capture_plan
from .manifest import DatasetManifest, scan_glb_folder
from .reports import dataset_stats, print_stats, validate_capture_outputs
from .splits import apply_split, split_by_asset
from .utils import write_json
from .view_contract import ViewContract


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sfb-dataset")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_contract = sub.add_parser("validate-contract", help="Validate and summarize a ViewContract JSON file.")
    validate_contract.add_argument("contract")

    scan = sub.add_parser("scan-glb", help="Create a candidate manifest from a folder of GLB/GLTF files.")
    scan.add_argument("folder")
    scan.add_argument("--dataset-id", required=True)
    scan.add_argument("--out", required=True)
    scan.add_argument("--tier", default="candidate", choices=["gold", "silver", "bronze", "rejected", "candidate", "gold_candidate"])
    scan.add_argument("--category", default="uncategorized")
    scan.add_argument("--style-family", default="unknown")
    scan.add_argument("--source-license", default="internal")
    scan.add_argument("--id-policy", default="stem_hash", choices=["stem_hash", "stem", "sequential"])
    scan.add_argument("--non-recursive", action="store_true")
    scan.add_argument("--relative-paths", action="store_true")

    stats_cmd = sub.add_parser("stats", help="Print manifest stats.")
    stats_cmd.add_argument("manifest")
    stats_cmd.add_argument("--json", action="store_true", help="Print JSON instead of a human summary.")

    split = sub.add_parser("split", help="Create deterministic train/val/test/holdout asset split.")
    split.add_argument("manifest")
    split.add_argument("--seed", type=int, default=1337)
    split.add_argument("--train", type=float, default=0.7)
    split.add_argument("--val", type=float, default=0.15)
    split.add_argument("--test", type=float, default=None)
    split.add_argument("--holdout", type=float, default=0.0)
    split.add_argument("--out", required=True)
    split.add_argument("--write-manifest", default=None, help="Optional manifest path with split labels applied.")

    plan = sub.add_parser("make-capture-plan", help="Build a JSONL capture plan from manifest + ViewContract.")
    plan.add_argument("manifest")
    plan.add_argument("--view-contract", required=True)
    plan.add_argument("--renders-root", required=True)
    plan.add_argument("--source-root", default=None, help="Resolve relative source paths against this folder.")
    plan.add_argument("--out", required=True)

    attach = sub.add_parser("attach-expected-views", help="Attach expected output paths to a manifest before/after rendering.")
    attach.add_argument("manifest")
    attach.add_argument("--view-contract", required=True)
    attach.add_argument("--renders-root", required=True)
    attach.add_argument("--out", required=True)

    validate = sub.add_parser("validate-captures", help="Check which expected render files exist on disk.")
    validate.add_argument("manifest")
    validate.add_argument("--out", default=None)

    args = parser.parse_args(argv)

    if args.command == "validate-contract":
        contract = ViewContract.load(args.contract)
        _print_json({
            "ok": True,
            "view_contract_id": contract.view_contract_id,
            "camera_type": contract.camera_type,
            "views": len(contract.views),
            "view_ids": contract.view_ids(),
        })
        return 0

    if args.command == "scan-glb":
        manifest = scan_glb_folder(
            args.folder,
            args.dataset_id,
            data_tier=args.tier,
            category=args.category,
            style_family=args.style_family,
            source_license=args.source_license,
            id_policy=args.id_policy,
            recursive=not args.non_recursive,
            relative_paths=args.relative_paths,
        )
        manifest.save(args.out)
        _print_json({"ok": True, "assets": len(manifest.assets), "out": args.out})
        return 0

    if args.command == "stats":
        manifest = DatasetManifest.load(args.manifest)
        stats = dataset_stats(manifest)
        if args.json:
            _print_json(stats)
        else:
            print(print_stats(stats))
        return 0

    if args.command == "split":
        manifest = DatasetManifest.load(args.manifest)
        split_data = split_by_asset(
            manifest.assets,
            seed=args.seed,
            train_ratio=args.train,
            val_ratio=args.val,
            test_ratio=args.test,
            holdout_ratio=args.holdout,
        )
        out = {"schema": "sfb.asset_split.v1", "seed": args.seed, **split_data.as_dict()}
        write_json(args.out, out)
        if args.write_manifest:
            apply_split(manifest, split_data).save(args.write_manifest)
        _print_json({
            "ok": True,
            "out": args.out,
            "train": len(split_data.train),
            "val": len(split_data.val),
            "test": len(split_data.test),
            "holdout": len(split_data.holdout),
            "manifest": args.write_manifest,
        })
        return 0

    if args.command == "make-capture-plan":
        manifest = DatasetManifest.load(args.manifest)
        contract = ViewContract.load(args.view_contract)
        rows = build_capture_plan(manifest, contract, renders_root=args.renders_root, source_root=args.source_root)
        save_capture_plan(args.out, rows)
        _print_json({"ok": True, "entries": len(rows), "assets": len(manifest.assets), "views": len(contract.views), "out": args.out})
        return 0

    if args.command == "attach-expected-views":
        manifest = DatasetManifest.load(args.manifest)
        contract = ViewContract.load(args.view_contract)
        updated = attach_expected_views(manifest, contract, renders_root=args.renders_root)
        updated.save(args.out)
        _print_json({"ok": True, "assets": len(updated.assets), "view_contract": contract.view_contract_id, "out": args.out})
        return 0

    if args.command == "validate-captures":
        manifest = DatasetManifest.load(args.manifest)
        result = validate_capture_outputs(manifest)
        if args.out:
            write_json(args.out, result)
        _print_json(result)
        return 0

    return 2
