from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_asset_package(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema") != "sfb.asset.v1":
        raise ValueError(f"not an SFB asset package: {path}")
    return data


def card_defaults_from_package(path: str | Path) -> dict[str, Any]:
    data = read_asset_package(path)
    report_path = data.get("report")
    report: dict[str, Any] = {}
    if report_path:
        rp = (Path(path).parent / str(report_path)).resolve()
        if rp.exists():
            report = json.loads(rp.read_text(encoding="utf-8"))
    camera = data.get("camera", {}) if isinstance(data.get("camera"), dict) else {}
    package = {
        "asset_package": str(path),
        "view_id": data.get("view_id", "front"),
        "view_contract": data.get("view_contract"),
        "source_asset_id": data.get("source_asset_id"),
        "width_m": float(data.get("width_m", 1.0) or 1.0),
        "height_m": float(data.get("height_m", 1.0) or 1.0),
        "depth_m": float(data.get("max_depth_m", 0.05) or 0.05),
        "pivot": data.get("pivot", "bottom_center"),
        "status": report.get("status", "unreviewed"),
        "metadata": {
            "asset_id": data.get("asset_id"),
            "mode": data.get("mode"),
            "azimuth_deg": camera.get("azimuth_deg"),
            "elevation_deg": camera.get("elevation_deg"),
            "runtime": data.get("runtime", {}),
            "mesh": data.get("mesh", {}),
            "metrics": report.get("metrics", {}),
            "warnings": report.get("warnings", []),
        },
    }
    return package
