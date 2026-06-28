from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .manifest import AssetRecord, DatasetManifest, ViewRecord
from .utils import path_posix, write_jsonl
from .view_contract import ViewContract


class CapturePlanEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_: Literal["sfb.capture_plan_entry.v1"] = Field("sfb.capture_plan_entry.v1", alias="schema")
    dataset_id: str
    asset_id: str
    source_path: str
    view_contract: str
    view_id: str
    azimuth_deg: float
    elevation_deg: float
    camera_type: str
    output_dir: str
    outputs: dict[str, str] = Field(default_factory=dict)


def build_capture_plan(
    manifest: DatasetManifest,
    contract: ViewContract,
    *,
    renders_root: str | Path,
    source_root: str | Path | None = None,
) -> list[CapturePlanEntry]:
    root = Path(renders_root)
    source_root_path = Path(source_root).resolve() if source_root else None
    rows: list[CapturePlanEntry] = []
    for asset in manifest.assets:
        if not asset.source_path:
            continue
        source = Path(asset.source_path)
        if not source.is_absolute() and source_root_path:
            source = source_root_path / source
        for view in contract.views:
            out_dir = root / asset.asset_id / view.view_id
            rows.append(
                CapturePlanEntry(
                    dataset_id=manifest.dataset_id,
                    asset_id=asset.asset_id,
                    source_path=path_posix(source),
                    view_contract=contract.view_contract_id,
                    view_id=view.view_id,
                    azimuth_deg=view.azimuth_deg,
                    elevation_deg=view.elevation_deg,
                    camera_type=contract.camera_type,
                    output_dir=path_posix(out_dir),
                    outputs={
                        "rgb": path_posix(out_dir / "rgb.png"),
                        "alpha": path_posix(out_dir / "alpha.png"),
                        "depth": path_posix(out_dir / "depth.exr"),
                        "normal": path_posix(out_dir / "normal.png"),
                        "camera": path_posix(out_dir / "camera.json"),
                    },
                )
            )
    return rows


def save_capture_plan(path: str | Path, rows: list[CapturePlanEntry]) -> None:
    write_jsonl(path, [row.model_dump(by_alias=True) for row in rows])


def attach_expected_views(
    manifest: DatasetManifest,
    contract: ViewContract,
    *,
    renders_root: str | Path,
) -> DatasetManifest:
    root = Path(renders_root)
    updated_assets: list[AssetRecord] = []
    for asset in manifest.assets:
        views = dict(asset.views)
        for view in contract.views:
            out_dir = root / asset.asset_id / view.view_id
            views[view.view_id] = ViewRecord(
                view_id=view.view_id,
                rgb=path_posix(out_dir / "rgb.png"),
                alpha=path_posix(out_dir / "alpha.png"),
                depth=path_posix(out_dir / "depth.exr"),
                normal=path_posix(out_dir / "normal.png"),
                camera=path_posix(out_dir / "camera.json"),
                azimuth_deg=view.azimuth_deg,
                elevation_deg=view.elevation_deg,
                camera_type=contract.camera_type,
            )
        updated_assets.append(asset.model_copy(update={"views": views}))
    return manifest.model_copy(update={"view_contract": contract.view_contract_id, "assets": updated_assets})
