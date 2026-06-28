from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .utils import path_posix, sha256_file, slugify

DataTier = Literal["gold", "silver", "bronze", "rejected", "candidate", "gold_candidate"]
QualityStatus = Literal["unreviewed", "needs_review", "approved", "rejected", "flagged"]
SplitName = Literal["train", "val", "test", "holdout"]


class ViewRecord(BaseModel):
    view_id: str
    rgb: str | None = None
    alpha: str | None = None
    depth: str | None = None
    normal: str | None = None
    camera: str | None = None
    preview: str | None = None
    azimuth_deg: float | None = None
    elevation_deg: float | None = None
    camera_type: str | None = None
    status: QualityStatus = "unreviewed"
    quality_score: float | None = None
    notes: str = ""


class AssetRecord(BaseModel):
    asset_id: str
    source_path: str | None = None
    source_hash: str | None = None
    source_ext: str | None = None
    source_license: str = "internal"
    data_tier: DataTier = "candidate"
    quality_status: QualityStatus = "unreviewed"
    category: str = "uncategorized"
    style_family: str = "unknown"
    base_caption: str = ""
    tags: list[str] = Field(default_factory=list)
    quality_score: float | None = None
    split: SplitName | None = None
    width_m: float | None = None
    height_m: float | None = None
    depth_m: float | None = None
    views: dict[str, ViewRecord] = Field(default_factory=dict)
    notes: str = ""

    @field_validator("asset_id")
    @classmethod
    def non_empty_asset_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("asset_id cannot be empty")
        return value


class DatasetManifest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_: Literal["sfb.dataset_manifest.v1"] = Field("sfb.dataset_manifest.v1", alias="schema")
    dataset_id: str
    view_contract: str | None = None
    description: str = ""
    assets: list[AssetRecord] = Field(default_factory=list)
    frozen: bool = False
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "DatasetManifest":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2, by_alias=True), encoding="utf-8")

    def by_asset_id(self) -> dict[str, AssetRecord]:
        return {asset.asset_id: asset for asset in self.assets}


def _asset_id_for(path: Path, idx: int, policy: str, digest: str) -> str:
    if policy == "sequential":
        return f"asset_{idx:06d}"
    if policy == "stem":
        return slugify(path.stem, fallback=f"asset_{idx:06d}")
    if policy == "stem_hash":
        return f"{slugify(path.stem, fallback='asset')}_{digest[:8]}"
    raise ValueError(f"unknown asset id policy: {policy}")


def scan_glb_folder(
    folder: str | Path,
    dataset_id: str,
    *,
    data_tier: DataTier = "candidate",
    category: str = "uncategorized",
    style_family: str = "unknown",
    source_license: str = "internal",
    id_policy: str = "stem_hash",
    recursive: bool = True,
    relative_paths: bool = False,
) -> DatasetManifest:
    folder = Path(folder).resolve()
    if not folder.exists():
        raise FileNotFoundError(folder)
    pattern_paths: list[Path] = []
    patterns = ["*.glb", "*.gltf"]
    for pattern in patterns:
        pattern_paths.extend(folder.rglob(pattern) if recursive else folder.glob(pattern))
    assets: list[AssetRecord] = []
    used_ids: set[str] = set()
    for idx, src in enumerate(sorted(set(pattern_paths))):
        digest = sha256_file(src)
        asset_id = _asset_id_for(src, idx, id_policy, digest)
        if asset_id in used_ids:
            asset_id = f"{asset_id}_{digest[:12]}"
        used_ids.add(asset_id)
        source_path = src.relative_to(folder) if relative_paths else src
        assets.append(
            AssetRecord(
                asset_id=asset_id,
                source_path=path_posix(source_path),
                source_hash=digest,
                source_ext=src.suffix.lower(),
                source_license=source_license,
                data_tier=data_tier,
                category=category,
                style_family=style_family,
            )
        )
    return DatasetManifest(dataset_id=dataset_id, assets=assets)
