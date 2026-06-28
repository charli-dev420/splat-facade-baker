from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .manifest_io import TrainingManifest
from .utils import write_json


def manifest_training_report(manifest_path: str | Path, out: str | Path | None = None) -> dict[str, Any]:
    manifest = TrainingManifest.load(manifest_path)
    by_tier = Counter(a.data_tier for a in manifest.assets)
    by_quality = Counter(a.quality_status for a in manifest.assets)
    by_category = Counter(a.category for a in manifest.assets)
    by_style = Counter(a.style_family for a in manifest.assets)
    by_split = Counter(a.split or "unsplit" for a in manifest.assets)
    view_counts = Counter()
    missing_rgb = 0
    for asset in manifest.assets:
        for view_id, view in asset.views.items():
            view_counts[view_id] += 1
            if not view.rgb:
                missing_rgb += 1
    report = {
        "schema": "sfb.training_dataset_report.v1",
        "dataset_id": manifest.dataset_id,
        "view_contract": manifest.view_contract,
        "assets_total": len(manifest.assets),
        "views_total": sum(view_counts.values()),
        "missing_rgb": missing_rgb,
        "by_tier": dict(sorted(by_tier.items())),
        "by_quality": dict(sorted(by_quality.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_style_family": dict(sorted(by_style.items())),
        "by_split": dict(sorted(by_split.items())),
        "view_counts": dict(sorted(view_counts.items())),
        "frozen": manifest.frozen,
    }
    if out:
        write_json(out, report)
    return report
