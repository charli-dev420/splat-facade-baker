from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class ViewSpec:
    view_id: str
    azimuth_deg: float
    elevation_deg: float
    role: str = ""
    bake_mode: str = "depth_card"
    preferred_camera_band: tuple[float, float] | None = None


@dataclass(frozen=True)
class ViewContract:
    view_contract_id: str
    camera_type: str
    views: tuple[ViewSpec, ...]
    unit: str = "meters"
    object_centering: str = "bbox_center"
    scale_policy: str = "fit_80_percent_height"

    def get(self, view_id: str) -> ViewSpec:
        for view in self.views:
            if view.view_id == view_id:
                return view
        available = ", ".join(v.view_id for v in self.views)
        raise KeyError(f"view_id '{view_id}' not found. Available: {available}")


def load_view_contract(path: str | Path) -> ViewContract:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    views: list[ViewSpec] = []
    for item in data.get("views", []):
        band = item.get("preferred_camera_band")
        views.append(
            ViewSpec(
                view_id=item["view_id"],
                azimuth_deg=float(item["azimuth_deg"]),
                elevation_deg=float(item["elevation_deg"]),
                role=item.get("role", ""),
                bake_mode=item.get("bake_mode", "depth_card"),
                preferred_camera_band=tuple(band) if band is not None else None,
            )
        )
    return ViewContract(
        view_contract_id=data["view_contract_id"],
        camera_type=data.get("camera_type", "orthographic"),
        unit=data.get("unit", "meters"),
        object_centering=data.get("object_centering", "bbox_center"),
        scale_policy=data.get("scale_policy", "fit_80_percent_height"),
        views=tuple(views),
    )
