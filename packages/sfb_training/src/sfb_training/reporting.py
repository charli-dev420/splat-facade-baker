from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_split = Counter(r.get("split", "train") for r in records)
    by_view = Counter(r.get("view_id") or r.get("target_view_id") for r in records)
    by_tier = Counter(r.get("data_tier", "unknown") for r in records)
    by_category = Counter(r.get("category", "uncategorized") for r in records)
    assets_by_split: dict[str, set[str]] = defaultdict(set)
    for r in records:
        assets_by_split[str(r.get("split", "train"))].add(str(r.get("asset_id", "")))
    return {
        "records_total": len(records),
        "by_split": dict(sorted(by_split.items())),
        "by_view": dict(sorted((str(k), v) for k, v in by_view.items() if k is not None)),
        "by_tier": dict(sorted(by_tier.items())),
        "by_category": dict(sorted(by_category.items())),
        "assets_by_split": {k: len(v) for k, v in sorted(assets_by_split.items())},
    }


def leakage_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    asset_splits: dict[str, set[str]] = defaultdict(set)
    for r in records:
        asset_splits[str(r.get("asset_id"))].add(str(r.get("split", "train")))
    leaking = {asset: sorted(splits) for asset, splits in asset_splits.items() if len(splits) > 1}
    return {
        "ok": not leaking,
        "leaking_assets": leaking,
        "leaking_assets_count": len(leaking),
    }
