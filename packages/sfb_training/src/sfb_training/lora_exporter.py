from __future__ import annotations

from pathlib import Path
from typing import Any

from .captions import build_lora_caption, NEGATIVE_PROMPT
from .filters import iter_eligible_assets, view_has_required_files
from .manifest_io import TrainingManifest
from .reporting import leakage_report, summarize_records
from .utils import copy_or_link, ensure_clean_dir, path_posix, resolve_maybe_relative, stable_hash, write_json, write_jsonl
from .view_contract import ViewContract


def _view_ids(manifest: TrainingManifest, view_contract: ViewContract | None, views: list[str] | None) -> list[str]:
    if views:
        return views
    if view_contract is not None:
        return view_contract.view_ids()
    ordered: list[str] = []
    for asset in manifest.assets:
        for view_id in asset.views:
            if view_id not in ordered:
                ordered.append(view_id)
    return ordered


def export_lora_dataset(
    manifest_path: str | Path,
    out_dir: str | Path,
    *,
    export_id: str = "lora_clean_render_v0",
    view_contract_path: str | Path | None = None,
    views: list[str] | None = None,
    tiers: set[str] | None = None,
    quality_statuses: set[str] | None = None,
    splits: set[str] | None = None,
    require_exists: bool = True,
    copy_mode: str = "copy",
    overwrite: bool = False,
    default_split: str = "train",
    extra_tags: list[str] | None = None,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    manifest = TrainingManifest.load(manifest_path)
    contract = ViewContract.load(view_contract_path) if view_contract_path else None
    selected_views = _view_ids(manifest, contract, views)
    out = ensure_clean_dir(out_dir, overwrite=overwrite)

    assets, rejected_assets = iter_eligible_assets(
        manifest,
        tiers=tiers,
        quality_statuses=quality_statuses,
        splits=splits,
    )
    records: list[dict[str, Any]] = []
    skipped_views: dict[str, int] = {}

    for asset in assets:
        split = asset.split or default_split
        if splits is not None and split not in splits:
            continue
        for view_id in selected_views:
            ok, reason = view_has_required_files(asset, view_id, manifest_path=manifest_path, require_exists=require_exists)
            if not ok:
                skipped_views[reason or "unknown"] = skipped_views.get(reason or "unknown", 0) + 1
                continue
            view = asset.views[view_id]
            src = resolve_maybe_relative(view.rgb or "", manifest_path.parent)
            file_stem = f"{asset.asset_id}_{view_id}"
            rel_image = Path("images") / split / f"{file_stem}{src.suffix.lower() or '.png'}"
            rel_caption = Path("captions") / split / f"{file_stem}.txt"
            if copy_mode != "reference":
                copy_or_link(src, out / rel_image, mode=copy_mode)
                (out / rel_caption).parent.mkdir(parents=True, exist_ok=True)
                caption_path_for_record = rel_caption
            else:
                rel_image = src
                caption_path_for_record = out / rel_caption
            caption = build_lora_caption(asset, view_id, extra_tags=extra_tags)
            (out / rel_caption).parent.mkdir(parents=True, exist_ok=True)
            (out / rel_caption).write_text(caption + "\n", encoding="utf-8")
            record = {
                "schema": "sfb.lora_record.v1",
                "export_id": export_id,
                "asset_id": asset.asset_id,
                "view_id": view_id,
                "split": split,
                "data_tier": asset.data_tier,
                "quality_status": asset.quality_status,
                "category": asset.category,
                "style_family": asset.style_family,
                "image": path_posix(rel_image),
                "caption": path_posix(caption_path_for_record),
                "caption_text": caption,
                "negative_prompt": NEGATIVE_PROMPT,
                "source_rgb": path_posix(src),
                "view_contract": manifest.view_contract or (contract.view_contract_id if contract else None),
                "azimuth_deg": view.azimuth_deg,
                "elevation_deg": view.elevation_deg,
                "camera_type": view.camera_type,
            }
            records.append(record)

    records_by_split: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": [], "holdout": []}
    for record in records:
        records_by_split.setdefault(record["split"], []).append(record)

    write_jsonl(out / "metadata.jsonl", records)
    for split_name, rows in records_by_split.items():
        if rows:
            write_jsonl(out / f"{split_name}.jsonl", rows)

    settings = {
        "export_id": export_id,
        "manifest": str(manifest_path),
        "view_contract": str(view_contract_path) if view_contract_path else None,
        "views": selected_views,
        "tiers": sorted(tiers) if tiers else None,
        "quality_statuses": sorted(quality_statuses) if quality_statuses else None,
        "splits": sorted(splits) if splits else None,
        "copy_mode": copy_mode,
        "default_split": default_split,
    }
    dataset_hash = stable_hash({"manifest": manifest.model_dump(mode="json"), "settings": settings, "records": records})
    config = {
        "schema": "sfb.training_export_config.v1",
        "task": "lora_clean_render",
        "export_id": export_id,
        "dataset_hash": dataset_hash,
        "records": len(records),
        "recommended_trigger": "sfb_clean_render",
        "caption_format": "caption_text",
        "settings": settings,
    }
    write_json(out / "config.json", config)
    # Keep a YAML-compatible minimal file without requiring PyYAML.
    (out / "config.yaml").write_text(
        "schema: sfb.training_export_config.v1\n"
        f"task: lora_clean_render\nexport_id: {export_id}\ndataset_hash: {dataset_hash}\nrecords: {len(records)}\n",
        encoding="utf-8",
    )
    report = {
        "schema": "sfb.training_export_report.v1",
        "task": "lora_clean_render",
        "export_id": export_id,
        "dataset_hash": dataset_hash,
        "summary": summarize_records(records),
        "leakage": leakage_report(records),
        "rejected_assets": rejected_assets,
        "skipped_views": skipped_views,
        "settings": settings,
    }
    write_json(out / "reports" / "dataset_report.json", report)
    return report
