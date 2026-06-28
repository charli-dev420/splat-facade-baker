from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


BakeMode = Literal["flat_card", "depth_card", "layered_card", "multi_angle_impostor"]
CameraType = Literal["orthographic", "perspective"]


class ViewDefinition(BaseModel):
    view_id: str
    azimuth_deg: float
    elevation_deg: float
    role: str = "production_view"
    preferred_camera_band: tuple[float, float] | None = None
    bake_mode: BakeMode = "depth_card"

    @field_validator("view_id")
    @classmethod
    def non_empty_view_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("view_id cannot be empty")
        return value


class ViewContract(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_: Literal["sfb.view_contract.v1"] = Field("sfb.view_contract.v1", alias="schema")
    view_contract_id: str
    camera_type: CameraType = "orthographic"
    unit: str = "meters"
    object_centering: str = "bbox_center"
    scale_policy: str = "fit_80_percent_height"
    views: list[ViewDefinition] = Field(default_factory=list)

    @field_validator("view_contract_id")
    @classmethod
    def non_empty_contract_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("view_contract_id cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_unique_views(self) -> "ViewContract":
        ids = [v.view_id for v in self.views]
        duplicates = sorted({view_id for view_id in ids if ids.count(view_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate view_id values: {', '.join(duplicates)}")
        if not self.views:
            raise ValueError("ViewContract must define at least one view")
        return self

    @classmethod
    def load(cls, path: str | Path) -> "ViewContract":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2, by_alias=True), encoding="utf-8")

    def get(self, view_id: str) -> ViewDefinition:
        for view in self.views:
            if view.view_id == view_id:
                return view
        raise KeyError(f"view_id not found in {self.view_contract_id}: {view_id}")

    def view_ids(self) -> list[str]:
        return [v.view_id for v in self.views]
