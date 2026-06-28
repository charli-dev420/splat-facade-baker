from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from sfb_core.cleanup import clean_alpha_depth
from sfb_core.config import BakeSettings
from sfb_core.depthcard import bake_maps
from sfb_core.view_contract import load_view_contract


def _save(path: Path, arr: np.ndarray, mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, mode=mode).save(path)


def _synthetic_maps(tmp_path: Path, *, island: bool = False) -> tuple[Path, Path, Path]:
    h, w = 64, 128
    albedo = np.zeros((h, w, 3), dtype=np.uint8)
    albedo[..., 0] = 180
    albedo[..., 1] = 120
    albedo[..., 2] = 80
    yy, xx = np.mgrid[:h, :w]
    alpha = (((xx - w / 2) / 55) ** 2 + ((yy - h / 2) / 25) ** 2 < 1).astype(np.uint8) * 255
    if island:
        alpha[2:5, 2:5] = 255
    depth = np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))
    _save(tmp_path / "albedo.png", albedo, "RGB")
    _save(tmp_path / "alpha.png", alpha, "L")
    _save(tmp_path / "depth.png", depth, "L")
    return tmp_path / "albedo.png", tmp_path / "alpha.png", tmp_path / "depth.png"


def test_bake_maps_creates_package_with_lods(tmp_path: Path) -> None:
    albedo, alpha, depth = _synthetic_maps(tmp_path)

    package = bake_maps(
        albedo,
        alpha,
        depth,
        tmp_path / "out",
        BakeSettings(name="TestAsset", width_m=4, height_m=2, max_depth_m=0.4, grid=32, lod_count=3),
    )

    assert package["schema"] == "sfb.asset.v1"
    assert package["mesh"]["triangles_lod0"] > 0
    assert package["mesh"]["triangles_lod1"] > 0
    assert package["mesh"]["triangles_lod2"] == 2  # default far LOD flat card
    assert (tmp_path / "out" / "asset.sfb.json").exists()
    assert (tmp_path / "out" / package["mesh"]["lod0_sfbmesh"]).exists()
    assert (tmp_path / "out" / package["mesh"]["lod1_sfbmesh"]).exists()
    assert (tmp_path / "out" / package["textures"]["mask"]).exists()
    report = json.loads((tmp_path / "out" / package["report"]).read_text())
    assert report["status"] == "ok"
    assert "cleanup" in report
    assert report["metrics"]["lods"]["lod2"]["triangles"] == 2


def test_cleanup_removes_small_islands_and_reports(tmp_path: Path) -> None:
    albedo, alpha, depth = _synthetic_maps(tmp_path, island=True)
    package = bake_maps(
        albedo,
        alpha,
        depth,
        tmp_path / "out",
        BakeSettings(
            name="CleanupAsset",
            width_m=4,
            height_m=2,
            max_depth_m=0.4,
            grid=32,
            remove_components_smaller_than_px=20,
            fill_holes_smaller_than_px=0,
            depth_smooth_radius=0,
        ),
    )
    report = json.loads((tmp_path / "out" / package["report"]).read_text())
    assert report["cleanup"]["removed_components"] >= 1
    assert any("cleanup_removed_components" in warning for warning in report["warnings"])


def test_clean_alpha_depth_can_fill_small_hole() -> None:
    alpha = np.ones((16, 16), dtype=np.float32)
    alpha[7:9, 7:9] = 0.0
    depth = np.tile(np.linspace(0, 1, 16, dtype=np.float32), (16, 1))
    cleaned_alpha, _, stats = clean_alpha_depth(
        alpha,
        depth,
        alpha_threshold=0.5,
        remove_components_smaller_than_px=0,
        fill_holes_smaller_than_px=8,
        depth_smooth_radius=0,
    )
    assert cleaned_alpha[8, 8] > 0.5
    assert stats.filled_holes == 1


def test_view_contract_loads_example() -> None:
    path = Path(__file__).resolve().parents[3] / ".." / ".." / "examples" / "view_contracts" / "MV8_OBJECT.json"
    path = path.resolve()
    if not path.exists():
        # package-local tests may run without repo examples; skip hard failure in installed wheel contexts
        return
    contract = load_view_contract(path)
    assert contract.get("front_right").azimuth_deg == 45
