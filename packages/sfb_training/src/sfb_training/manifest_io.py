from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .utils import read_json, resolve_maybe_relative


class TrainingView(BaseModel):
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
    status: str = "unreviewed"
    quality_score: float | None = None
    notes: str = ""


class TrainingAsset(BaseModel):
    asset_id: str
    source_path: str | None = None
    source_hash: str | None = None
    source_ext: str | None = None
    source_license: str = "internal"
    data_tier: str = "candidate"
    quality_status: str = "unreviewed"
    category: str = "uncategorized"
    style_family: str = "unknown"
    base_caption: str = ""
    tags: list[str] = Field(default_factory=list)
    quality_score: float | None = None
    split: str | None = None
    width_m: float | None = None
    height_m: float | None = None
    depth_m: float | None = None
    views: dict[str, TrainingView] = Field(default_factory=dict)
    notes: str = ""


class TrainingManifest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_: Literal["sfb.dataset_manifest.v1"] = Field("sfb.dataset_manifest.v1", alias="schema")
    dataset_id: str
    view_contract: str | None = None
    description: str = ""
    frozen: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    assets: list[TrainingAsset] = Field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "TrainingManifest":
        return cls.model_validate(read_json(path))

    def asset_by_id(self) -> dict[str, TrainingAsset]:
        return {a.asset_id: a for a in self.assets}


def resolve_view_rgb(view: TrainingView, manifest_path: str | Path) -> Path | None:
    if not view.rgb:
        return None
    return resolve_maybe_relative(view.rgb, Path(manifest_path).parent)
