from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dataset_report import manifest_training_report
from .eval_sets import make_eval_set
from .lora_exporter import export_lora_dataset
from .pair_builder import export_view_pairs
from .utils import parse_csv, write_json


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _set_csv(value: str | None) -> set[str] | None:
    parts = parse_csv(value)
    return set(parts) if parts else None


def _list_csv(value: str | None) -> list[str] | None:
    return parse_csv(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sfb-trainprep")
    sub = parser.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report", help="Summarize a dataset manifest for training readiness.")
    report.add_argument("manifest")
    report.add_argument("--out", default=None)

    lora = sub.add_parser("export-lora", help="Export a LoRA clean-render dataset.")
    lora.add_argument("manifest")
    lora.add_argument("--out", required=True)
    lora.add_argument("--export-id", default="lora_clean_render_v0")
    lora.add_argument("--view-contract", default=None)
    lora.add_argument("--views", default=None, help="Comma-separated view ids; defaults to ViewContract order or manifest views.")
    lora.add_argument("--tiers", default="gold,gold_candidate")
    lora.add_argument("--quality-statuses", default="approved,needs_review,unreviewed")
    lora.add_argument("--splits", default=None, help="Comma-separated split filter, e.g. train,val.")
    lora.add_argument("--copy-mode", default="copy", choices=["copy", "hardlink", "symlink", "reference"])
    lora.add_argument("--allow-missing", action="store_true")
    lora.add_argument("--overwrite", action="store_true")
    lora.add_argument("--default-split", default="train")
    lora.add_argument("--extra-tags", default=None)

    pairs = sub.add_parser("export-view-pairs", help="Export source→target view pairs for a view adapter.")
    pairs.add_argument("manifest")
    pairs.add_argument("--out", required=True)
    pairs.add_argument("--export-id", default="view_adapter_v0")
    pairs.add_argument("--view-contract", default=None)
    pairs.add_argument("--pair-policy", default="front_to_all", choices=["front_to_all", "all_to_all", "adjacent", "front_to_cardinal", "custom"])
    pairs.add_argument("--source-views", default=None)
    pairs.add_argument("--target-views", default=None)
    pairs.add_argument("--tiers", default="gold,gold_candidate")
    pairs.add_argument("--quality-statuses", default="approved,needs_review,unreviewed")
    pairs.add_argument("--splits", default=None)
    pairs.add_argument("--copy-mode", default="copy", choices=["copy", "hardlink", "symlink", "reference"])
    pairs.add_argument("--allow-missing", action="store_true")
    pairs.add_argument("--overwrite", action="store_true")
    pairs.add_argument("--default-split", default="train")
    pairs.add_argument("--max-pairs-per-asset", type=int, default=None)
    pairs.add_argument("--extra-tags", default=None)

    evals = sub.add_parser("make-eval-set", help="Create fixed eval items and prompts from a manifest.")
    evals.add_argument("manifest")
    evals.add_argument("--out", required=True)
    evals.add_argument("--eval-id", default="clean_render_eval_v0")
    evals.add_argument("--view-contract", default=None)
    evals.add_argument("--task", default="clean_render", choices=["clean_render", "view_adapter"])
    evals.add_argument("--split", default="test")
    evals.add_argument("--views", default=None)
    evals.add_argument("--tiers", default="gold,gold_candidate")
    evals.add_argument("--max-assets", type=int, default=32)
    evals.add_argument("--allow-missing", action="store_true")
    evals.add_argument("--overwrite", action="store_true")

    freeze = sub.add_parser("freeze-manifest", help="Write a copy of a manifest with frozen=true for reproducible training exports.")
    freeze.add_argument("manifest")
    freeze.add_argument("--out", required=True)

    args = parser.parse_args(argv)

    if args.command == "report":
        result = manifest_training_report(args.manifest, out=args.out)
        _print(result)
        return 0

    if args.command == "export-lora":
        result = export_lora_dataset(
            args.manifest,
            args.out,
            export_id=args.export_id,
            view_contract_path=args.view_contract,
            views=_list_csv(args.views),
            tiers=_set_csv(args.tiers),
            quality_statuses=_set_csv(args.quality_statuses),
            splits=_set_csv(args.splits),
            require_exists=not args.allow_missing,
            copy_mode=args.copy_mode,
            overwrite=args.overwrite,
            default_split=args.default_split,
            extra_tags=_list_csv(args.extra_tags),
        )
        _print({"ok": True, "out": args.out, "records": result["summary"]["records_total"], "report": str(Path(args.out) / "reports" / "dataset_report.json")})
        return 0

    if args.command == "export-view-pairs":
        result = export_view_pairs(
            args.manifest,
            args.out,
            export_id=args.export_id,
            view_contract_path=args.view_contract,
            pair_policy=args.pair_policy,
            source_views=_list_csv(args.source_views),
            target_views=_list_csv(args.target_views),
            tiers=_set_csv(args.tiers),
            quality_statuses=_set_csv(args.quality_statuses),
            splits=_set_csv(args.splits),
            require_exists=not args.allow_missing,
            copy_mode=args.copy_mode,
            overwrite=args.overwrite,
            default_split=args.default_split,
            max_pairs_per_asset=args.max_pairs_per_asset,
            extra_tags=_list_csv(args.extra_tags),
        )
        _print({"ok": True, "out": args.out, "records": result["summary"]["records_total"], "report": str(Path(args.out) / "reports" / "dataset_report.json")})
        return 0

    if args.command == "make-eval-set":
        result = make_eval_set(
            args.manifest,
            args.out,
            eval_id=args.eval_id,
            view_contract_path=args.view_contract,
            task=args.task,
            split=args.split,
            views=_list_csv(args.views),
            tiers=_set_csv(args.tiers),
            max_assets=args.max_assets,
            require_exists=not args.allow_missing,
            overwrite=args.overwrite,
        )
        _print({"ok": True, "out": args.out, "items": result["items"], "report": str(Path(args.out) / "eval_set_report.json")})
        return 0

    if args.command == "freeze-manifest":
        data = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        data["frozen"] = True
        write_json(args.out, data)
        _print({"ok": True, "out": args.out, "frozen": True})
        return 0

    return 2
