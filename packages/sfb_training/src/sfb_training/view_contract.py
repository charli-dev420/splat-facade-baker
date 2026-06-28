from __future__ import annotations

from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from .utils import read_json


class ContractView(BaseModel):
    view_id: str
    azimuth_deg: float
    elevation_deg: float = 0.0
    role: str = "production_view"
    preferred_camera_band: list[float] | None = None


class ViewContract(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_: Literal["sfb.view_contract.v1"] = Field("sfb.view_contract.v1", alias="schema")
    view_contract_id: str
    camera_type: str = "orthographic"
    unit: str = "meters"
    views: list[ContractView] = Field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "ViewContract":
        vc = cls.model_validate(read_json(path))
        seen = set()
        for view in vc.views:
            if view.view_id in seen:
                raise ValueError(f"duplicate view_id in ViewContract: {view.view_id}")
            seen.add(view.view_id)
        return vc

    def view_ids(self) -> list[str]:
        return [v.view_id for v in self.views]

    def by_id(self) -> dict[str, ContractView]:
        return {v.view_id: v for v in self.views}
