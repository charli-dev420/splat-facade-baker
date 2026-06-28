from __future__ import annotations

from pathlib import Path
from typing import Any

from .captions import build_lora_caption, build_view_pair_caption
from .filters import iter_eligible_assets, view_has_required_files
from .manifest_io import TrainingManifest
from .utils import ensure_clean_dir, path_posix, resolve_maybe_relative, stable_hash, write_json, write_jsonl
from .view_contract import ViewContract


def make_eval_set(
    manifest_path: str | Path,
    out_dir: str | Path,
    *,
    eval_id: str = "clean_render_eval_v0",
    view_contract_path: str | Path | None = None,
    task: str = "clean_render",
    split: str = "test",
    views: list[str] | None = None,
    tiers: set[str] | None = None,
    max_assets: int | None = 32,
    require_exists: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    manifest = TrainingManifest.load(manifest_path)
    contract = ViewContract.load(view_contract_path) if view_contract_path else None
    view_ids = views or (contract.view_ids() if contract else None)
    out = ensure_clean_dir(out_dir, overwrite=overwrite)
    assets, rejected = iter_eligible_assets(manifest, tiers=tiers, splits={split})
    if max_assets is not None:
        assets = assets[:max_assets]
    rows: list[dict[str, Any]] = []
    prompts: list[str] = []
    skipped: dict[str, int] = {}
    for asset in assets:
        selected_views = view_ids or list(asset.views.keys())
        for view_id in selected_views:
            ok, reason = view_has_required_files(asset, view_id, manifest_path=manifest_path, require_exists=require_exists)
            if not ok:
                skipped[reason or "unknown"] = skipped.get(reason or "unknown", 0) + 1
                continue
            view = asset.views[view_id]
            rgb = resolve_maybe_relative(view.rgb or "", manifest_path.parent)
            if task == "view_adapter":
                # Eval records use the front view as source when possible.
                source_view_id = "front" if "front" in asset.views and view_id != "front" else next((v for v in asset.views if v != view_id), view_id)
                if source_view_id == view_id:
                    continue
                src_ok, src_reason = view_has_required_files(asset, source_view_id, manifest_path=manifest_path, require_exists=require_exists)
                if not src_ok:
                    skipped[f"source:{src_reason}"] = skipped.get(f"source:{src_reason}", 0) + 1
                    continue
                prompt = build_view_pair_caption(
                    asset,
                    source_view_id=source_view_id,
                    target_view_id=view_id,
                    target_azimuth_deg=view.azimuth_deg,
                    target_elevation_deg=view.elevation_deg,
                )
                source_rgb = resolve_maybe_relative(asset.views[source_view_id].rgb or "", manifest_path.parent)
                row = {
                    "schema": "sfb.eval_item.v1",
                    "eval_id": eval_id,
                    "task": task,
                    "asset_id": asset.asset_id,
                    "split": split,
                    "source_view_id": source_view_id,
                    "target_view_id": view_id,
                    "source_image": path_posix(source_rgb),
                    "target_image": path_posix(rgb),
                    "prompt": prompt,
                }
            else:
                prompt = build_lora_caption(asset, view_id)
                row = {
                    "schema": "sfb.eval_item.v1",
                    "eval_id": eval_id,
                    "task": task,
                    "asset_id": asset.asset_id,
                    "split": split,
                    "view_id": view_id,
                    "target_image": path_posix(rgb),
                    "prompt": prompt,
                }
            rows.append(row)
            prompts.append(prompt)
    write_jsonl(out / "eval_items.jsonl", rows)
    (out / "eval_prompts.txt").write_text("\n".join(prompts) + ("\n" if prompts else ""), encoding="utf-8")
    settings = {
        "eval_id": eval_id,
        "manifest": str(manifest_path),
        "view_contract": str(view_contract_path) if view_contract_path else None,
        "task": task,
        "split": split,
        "views": view_ids,
        "tiers": sorted(tiers) if tiers else None,
        "max_assets": max_assets,
    }
    report = {
        "schema": "sfb.eval_set_report.v1",
        "eval_id": eval_id,
        "task": task,
        "items": len(rows),
        "assets": len({r["asset_id"] for r in rows}),
        "dataset_hash": stable_hash({"settings": settings, "rows": rows}),
        "skipped": skipped,
        "rejected_assets": rejected,
        "settings": settings,
    }
    write_json(out / "eval_set_report.json", report)
    return report
