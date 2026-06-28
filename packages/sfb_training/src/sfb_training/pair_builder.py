from __future__ import annotations

from pathlib import Path
from typing import Any

from .captions import build_view_pair_caption, NEGATIVE_PROMPT
from .filters import iter_eligible_assets, view_has_required_files
from .manifest_io import TrainingAsset, TrainingManifest
from .reporting import leakage_report, summarize_records
from .utils import copy_or_link, ensure_clean_dir, path_posix, resolve_maybe_relative, safe_name, stable_hash, write_json, write_jsonl
from .view_contract import ViewContract


def _ordered_views(manifest: TrainingManifest, contract: ViewContract | None) -> list[str]:
    if contract is not None:
        return contract.view_ids()
    ordered: list[str] = []
    for asset in manifest.assets:
        for view_id in asset.views:
            if view_id not in ordered:
                ordered.append(view_id)
    return ordered


def _pairs_for_policy(
    asset: TrainingAsset,
    ordered_views: list[str],
    policy: str,
    *,
    source_views: list[str] | None = None,
    target_views: list[str] | None = None,
) -> list[tuple[str, str]]:
    available = [v for v in ordered_views if v in asset.views]
    if source_views:
        srcs = [v for v in source_views if v in available]
    else:
        srcs = list(available)
    if target_views:
        tgts = [v for v in target_views if v in available]
    else:
        tgts = list(available)

    pairs: list[tuple[str, str]] = []
    if policy == "custom":
        for src in srcs:
            for tgt in tgts:
                if src != tgt:
                    pairs.append((src, tgt))
        return pairs
    if policy == "front_to_all":
        front = "front" if "front" in available else (available[0] if available else None)
        if not front:
            return []
        return [(front, tgt) for tgt in available if tgt != front]
    if policy == "all_to_all":
        return [(src, tgt) for src in available for tgt in available if src != tgt]
    if policy == "adjacent":
        n = len(ordered_views)
        if n <= 1:
            return []
        for i, src in enumerate(ordered_views):
            if src not in available:
                continue
            prev_view = ordered_views[(i - 1) % n]
            next_view = ordered_views[(i + 1) % n]
            if prev_view in available:
                pairs.append((src, prev_view))
            if next_view in available:
                pairs.append((src, next_view))
        return pairs
    if policy == "front_to_cardinal":
        front = "front" if "front" in available else (available[0] if available else None)
        if not front:
            return []
        cardinal = [v for v in ["front_right", "right", "front_left", "left", "back"] if v in available]
        return [(front, tgt) for tgt in cardinal if tgt != front]
    raise ValueError(f"unsupported pair policy: {policy}")


def export_view_pairs(
    manifest_path: str | Path,
    out_dir: str | Path,
    *,
    export_id: str = "view_adapter_v0",
    view_contract_path: str | Path | None = None,
    pair_policy: str = "front_to_all",
    source_views: list[str] | None = None,
    target_views: list[str] | None = None,
    tiers: set[str] | None = None,
    quality_statuses: set[str] | None = None,
    splits: set[str] | None = None,
    require_exists: bool = True,
    copy_mode: str = "copy",
    overwrite: bool = False,
    default_split: str = "train",
    max_pairs_per_asset: int | None = None,
    extra_tags: list[str] | None = None,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    manifest = TrainingManifest.load(manifest_path)
    contract = ViewContract.load(view_contract_path) if view_contract_path else None
    ordered_views = _ordered_views(manifest, contract)
    contract_by_view = contract.by_id() if contract else {}
    out = ensure_clean_dir(out_dir, overwrite=overwrite)

    assets, rejected_assets = iter_eligible_assets(
        manifest,
        tiers=tiers,
        quality_statuses=quality_statuses,
        splits=splits,
    )
    records: list[dict[str, Any]] = []
    skipped_pairs: dict[str, int] = {}

    for asset in assets:
        split = asset.split or default_split
        if splits is not None and split not in splits:
            continue
        raw_pairs = _pairs_for_policy(asset, ordered_views, pair_policy, source_views=source_views, target_views=target_views)
        if max_pairs_per_asset is not None:
            raw_pairs = raw_pairs[:max_pairs_per_asset]
        for source_view_id, target_view_id in raw_pairs:
            ok_src, reason_src = view_has_required_files(asset, source_view_id, manifest_path=manifest_path, require_exists=require_exists)
            ok_tgt, reason_tgt = view_has_required_files(asset, target_view_id, manifest_path=manifest_path, require_exists=require_exists)
            if not ok_src or not ok_tgt:
                reason = f"source:{reason_src}" if not ok_src else f"target:{reason_tgt}"
                skipped_pairs[reason] = skipped_pairs.get(reason, 0) + 1
                continue
            src_view = asset.views[source_view_id]
            tgt_view = asset.views[target_view_id]
            src_path = resolve_maybe_relative(src_view.rgb or "", manifest_path.parent)
            tgt_path = resolve_maybe_relative(tgt_view.rgb or "", manifest_path.parent)
            pair_id = safe_name(f"{asset.asset_id}_{source_view_id}_to_{target_view_id}")
            rel_src = Path("pairs") / split / pair_id / f"source{src_path.suffix.lower() or '.png'}"
            rel_tgt = Path("pairs") / split / pair_id / f"target{tgt_path.suffix.lower() or '.png'}"
            if copy_mode != "reference":
                copy_or_link(src_path, out / rel_src, mode=copy_mode)
                copy_or_link(tgt_path, out / rel_tgt, mode=copy_mode)
            else:
                rel_src = src_path
                rel_tgt = tgt_path
            target_contract_view = contract_by_view.get(target_view_id)
            target_azimuth = tgt_view.azimuth_deg if tgt_view.azimuth_deg is not None else (target_contract_view.azimuth_deg if target_contract_view else None)
            target_elevation = tgt_view.elevation_deg if tgt_view.elevation_deg is not None else (target_contract_view.elevation_deg if target_contract_view else None)
            caption = build_view_pair_caption(
                asset,
                source_view_id=source_view_id,
                target_view_id=target_view_id,
                target_azimuth_deg=target_azimuth,
                target_elevation_deg=target_elevation,
                extra_tags=extra_tags,
            )
            record = {
                "schema": "sfb.view_pair_record.v1",
                "export_id": export_id,
                "pair_id": pair_id,
                "asset_id": asset.asset_id,
                "split": split,
                "data_tier": asset.data_tier,
                "quality_status": asset.quality_status,
                "category": asset.category,
                "style_family": asset.style_family,
                "source_image": path_posix(rel_src),
                "target_image": path_posix(rel_tgt),
                "source_rgb": path_posix(src_path),
                "target_rgb": path_posix(tgt_path),
                "source_view_id": source_view_id,
                "target_view_id": target_view_id,
                "view_id": target_view_id,
                "target_azimuth_deg": target_azimuth,
                "target_elevation_deg": target_elevation,
                "view_contract": manifest.view_contract or (contract.view_contract_id if contract else None),
                "caption_text": caption,
                "negative_prompt": NEGATIVE_PROMPT,
            }
            records.append(record)

    records_by_split: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": [], "holdout": []}
    for record in records:
        records_by_split.setdefault(record["split"], []).append(record)
    write_jsonl(out / "metadata.jsonl", records)
    for split_name, rows in records_by_split.items():
        if rows:
            write_jsonl(out / f"{split_name}_pairs.jsonl", rows)

    settings = {
        "export_id": export_id,
        "manifest": str(manifest_path),
        "view_contract": str(view_contract_path) if view_contract_path else None,
        "pair_policy": pair_policy,
        "source_views": source_views,
        "target_views": target_views,
        "tiers": sorted(tiers) if tiers else None,
        "quality_statuses": sorted(quality_statuses) if quality_statuses else None,
        "splits": sorted(splits) if splits else None,
        "copy_mode": copy_mode,
        "default_split": default_split,
        "max_pairs_per_asset": max_pairs_per_asset,
    }
    dataset_hash = stable_hash({"manifest": manifest.model_dump(mode="json"), "settings": settings, "records": records})
    config = {
        "schema": "sfb.training_export_config.v1",
        "task": "view_adapter",
        "export_id": export_id,
        "dataset_hash": dataset_hash,
        "records": len(records),
        "conditioning": {
            "source_image": True,
            "target_view_token": True,
            "target_camera_metadata": True,
        },
        "settings": settings,
    }
    write_json(out / "config.json", config)
    (out / "config.yaml").write_text(
        "schema: sfb.training_export_config.v1\n"
        f"task: view_adapter\nexport_id: {export_id}\ndataset_hash: {dataset_hash}\nrecords: {len(records)}\n",
        encoding="utf-8",
    )
    report = {
        "schema": "sfb.training_export_report.v1",
        "task": "view_adapter",
        "export_id": export_id,
        "dataset_hash": dataset_hash,
        "summary": summarize_records(records),
        "leakage": leakage_report(records),
        "rejected_assets": rejected_assets,
        "skipped_pairs": skipped_pairs,
        "settings": settings,
    }
    write_json(out / "reports" / "dataset_report.json", report)
    return report
