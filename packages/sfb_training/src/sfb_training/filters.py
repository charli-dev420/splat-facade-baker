from __future__ import annotations

from pathlib import Path

from .manifest_io import TrainingAsset, TrainingManifest
from .utils import resolve_maybe_relative


DEFAULT_TIERS = {"gold", "gold_candidate"}
DEFAULT_QUALITY_STATUSES = {"approved", "needs_review", "unreviewed"}
DEFAULT_VIEW_STATUSES = {"approved", "needs_review", "unreviewed"}


class FilterResult:
    def __init__(self) -> None:
        self.reasons: dict[str, int] = {}

    def add(self, reason: str) -> None:
        self.reasons[reason] = self.reasons.get(reason, 0) + 1


def asset_allowed(
    asset: TrainingAsset,
    *,
    tiers: set[str] | None = None,
    quality_statuses: set[str] | None = None,
    splits: set[str] | None = None,
) -> tuple[bool, str | None]:
    tiers = tiers or DEFAULT_TIERS
    quality_statuses = quality_statuses or DEFAULT_QUALITY_STATUSES
    if asset.data_tier not in tiers:
        return False, f"tier:{asset.data_tier}"
    if asset.quality_status not in quality_statuses:
        return False, f"quality:{asset.quality_status}"
    if splits is not None:
        split = asset.split or "train"
        if split not in splits:
            return False, f"split:{split}"
    return True, None


def iter_eligible_assets(
    manifest: TrainingManifest,
    *,
    tiers: set[str] | None = None,
    quality_statuses: set[str] | None = None,
    splits: set[str] | None = None,
) -> tuple[list[TrainingAsset], dict[str, int]]:
    result = FilterResult()
    assets: list[TrainingAsset] = []
    for asset in manifest.assets:
        ok, reason = asset_allowed(asset, tiers=tiers, quality_statuses=quality_statuses, splits=splits)
        if ok:
            assets.append(asset)
        else:
            result.add(reason or "unknown")
    return assets, result.reasons


def view_has_required_files(
    asset: TrainingAsset,
    view_id: str,
    *,
    manifest_path: str | Path,
    require_exists: bool = True,
    allowed_view_statuses: set[str] | None = None,
) -> tuple[bool, str | None]:
    allowed_view_statuses = allowed_view_statuses or DEFAULT_VIEW_STATUSES
    view = asset.views.get(view_id)
    if view is None:
        return False, "missing_view"
    if view.status not in allowed_view_statuses:
        return False, f"view_status:{view.status}"
    if not view.rgb:
        return False, "missing_rgb_path"
    if require_exists:
        rgb = resolve_maybe_relative(view.rgb, Path(manifest_path).parent)
        if not rgb.exists():
            return False, "missing_rgb_file"
    return True, None
