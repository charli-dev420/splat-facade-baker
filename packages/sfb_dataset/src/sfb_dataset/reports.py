from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .manifest import DatasetManifest


def dataset_stats(manifest: DatasetManifest) -> dict[str, Any]:
    tiers = Counter(asset.data_tier for asset in manifest.assets)
    quality = Counter(asset.quality_status for asset in manifest.assets)
    categories = Counter(asset.category for asset in manifest.assets)
    styles = Counter(asset.style_family for asset in manifest.assets)
    splits = Counter(asset.split or "unsplit" for asset in manifest.assets)
    view_counts = Counter()
    missing_sources = 0
    for asset in manifest.assets:
        if not asset.source_path:
            missing_sources += 1
        for view_id, view in asset.views.items():
            view_counts[view_id] += 1
    return {
        "schema": "sfb.dataset_report.v1",
        "dataset_id": manifest.dataset_id,
        "view_contract": manifest.view_contract,
        "assets_total": len(manifest.assets),
        "frozen": manifest.frozen,
        "tiers": dict(sorted(tiers.items())),
        "quality_status": dict(sorted(quality.items())),
        "categories": dict(categories.most_common()),
        "style_families": dict(styles.most_common()),
        "splits": dict(sorted(splits.items())),
        "views": dict(sorted(view_counts.items())),
        "missing_sources": missing_sources,
    }


def print_stats(stats: dict[str, Any]) -> str:
    lines = [f"Dataset: {stats['dataset_id']}", f"Assets: {stats['assets_total']}"]
    if stats.get("view_contract"):
        lines.append(f"ViewContract: {stats['view_contract']}")
    for key in ["tiers", "quality_status", "splits", "views"]:
        lines.append(f"{key}:")
        values = stats.get(key, {})
        if values:
            for k, v in values.items():
                lines.append(f"  - {k}: {v}")
        else:
            lines.append("  - none: 0")
    return "\n".join(lines)


def validate_capture_outputs(manifest: DatasetManifest) -> dict[str, Any]:
    missing: list[dict[str, str]] = []
    existing = 0
    for asset in manifest.assets:
        for view_id, view in asset.views.items():
            for kind in ["rgb", "alpha", "depth", "normal", "camera"]:
                path = getattr(view, kind)
                if not path:
                    missing.append({"asset_id": asset.asset_id, "view_id": view_id, "kind": kind, "path": ""})
                    continue
                if Path(path).exists():
                    existing += 1
                else:
                    missing.append({"asset_id": asset.asset_id, "view_id": view_id, "kind": kind, "path": path})
    return {"schema": "sfb.capture_validation.v1", "existing_files": existing, "missing_files": len(missing), "missing": missing[:1000]}
