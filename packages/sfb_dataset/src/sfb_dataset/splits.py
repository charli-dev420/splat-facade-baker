from __future__ import annotations

from dataclasses import dataclass
import random

from .manifest import AssetRecord, DatasetManifest


@dataclass(frozen=True)
class AssetSplit:
    train: list[str]
    val: list[str]
    test: list[str]
    holdout: list[str]

    def as_dict(self) -> dict[str, list[str]]:
        return {"train": self.train, "val": self.val, "test": self.test, "holdout": self.holdout}


def split_by_asset(
    assets: list[AssetRecord],
    seed: int = 1337,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float | None = None,
    holdout_ratio: float = 0.0,
    include_rejected: bool = False,
) -> AssetSplit:
    ratios_sum = train_ratio + val_ratio + (test_ratio if test_ratio is not None else 0.0) + holdout_ratio
    if test_ratio is None:
        test_ratio = max(0.0, 1.0 - train_ratio - val_ratio - holdout_ratio)
        ratios_sum = train_ratio + val_ratio + test_ratio + holdout_ratio
    if abs(ratios_sum - 1.0) > 1e-6:
        raise ValueError("train + val + test + holdout ratios must sum to 1.0")
    ids = [a.asset_id for a in assets if include_rejected or (a.data_tier != "rejected" and a.quality_status != "rejected")]
    rng = random.Random(seed)
    rng.shuffle(ids)
    n = len(ids)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    n_test = int(n * test_ratio)
    train = ids[:n_train]
    val = ids[n_train:n_train + n_val]
    test = ids[n_train + n_val:n_train + n_val + n_test]
    holdout = ids[n_train + n_val + n_test:]
    return AssetSplit(train=train, val=val, test=test, holdout=holdout)


def apply_split(manifest: DatasetManifest, split: AssetSplit) -> DatasetManifest:
    lookup = {}
    for split_name, ids in split.as_dict().items():
        for asset_id in ids:
            lookup[asset_id] = split_name
    assets = [asset.model_copy(update={"split": lookup.get(asset.asset_id)}) for asset in manifest.assets]
    return manifest.model_copy(update={"assets": assets})
