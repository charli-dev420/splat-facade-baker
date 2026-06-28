from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfb_dataset.capture_plan import attach_expected_views, build_capture_plan
from sfb_dataset.manifest import DatasetManifest, scan_glb_folder
from sfb_dataset.splits import apply_split, split_by_asset
from sfb_dataset.view_contract import ViewContract


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_view_contract_loads_mv8() -> None:
    contract = ViewContract.load(_repo_root() / "examples" / "view_contracts" / "MV8_OBJECT.json")
    assert contract.view_contract_id == "MV8_OBJECT"
    assert len(contract.views) == 8
    assert contract.get("front_right").azimuth_deg == 45


def test_view_contract_rejects_duplicate_views(tmp_path: Path) -> None:
    p = tmp_path / "bad_contract.json"
    p.write_text(json.dumps({
        "schema": "sfb.view_contract.v1",
        "view_contract_id": "BAD",
        "camera_type": "orthographic",
        "views": [
            {"view_id": "front", "azimuth_deg": 0, "elevation_deg": 10},
            {"view_id": "front", "azimuth_deg": 45, "elevation_deg": 10},
        ],
    }), encoding="utf-8")
    with pytest.raises(ValueError):
        ViewContract.load(p)


def test_scan_glb_folder_builds_stable_manifest(tmp_path: Path) -> None:
    src = tmp_path / "sources"
    src.mkdir()
    (src / "Wall A.glb").write_bytes(b"glb-one")
    (src / "Props" ).mkdir()
    (src / "Props" / "Crate.gltf").write_text("{}", encoding="utf-8")

    manifest = scan_glb_folder(src, "dataset_test", data_tier="gold_candidate", category="ruins", style_family="mixed")

    assert manifest.dataset_id == "dataset_test"
    assert len(manifest.assets) == 2
    assert all(asset.source_hash for asset in manifest.assets)
    assert {asset.source_ext for asset in manifest.assets} == {".glb", ".gltf"}
    assert {asset.data_tier for asset in manifest.assets} == {"gold_candidate"}

    out = tmp_path / "manifest.json"
    manifest.save(out)
    loaded = DatasetManifest.load(out)
    assert loaded.assets[0].asset_id == manifest.assets[0].asset_id


def test_capture_plan_and_expected_views(tmp_path: Path) -> None:
    src = tmp_path / "sources"
    src.mkdir()
    (src / "wall.glb").write_bytes(b"fake-glb")
    manifest = scan_glb_folder(src, "dataset_capture", id_policy="sequential")
    contract = ViewContract.load(_repo_root() / "examples" / "view_contracts" / "MV8_OBJECT.json")

    rows = build_capture_plan(manifest, contract, renders_root=tmp_path / "renders")
    assert len(rows) == 8
    assert rows[0].outputs["rgb"].endswith("rgb.png")
    assert rows[0].view_contract == "MV8_OBJECT"

    updated = attach_expected_views(manifest, contract, renders_root=tmp_path / "renders")
    asset = updated.assets[0]
    assert updated.view_contract == "MV8_OBJECT"
    assert set(asset.views) == set(contract.view_ids())
    assert asset.views["front"].rgb is not None


def test_split_is_by_asset_and_deterministic(tmp_path: Path) -> None:
    src = tmp_path / "sources"
    src.mkdir()
    for i in range(10):
        (src / f"asset_{i}.glb").write_bytes(f"glb-{i}".encode())
    manifest = scan_glb_folder(src, "dataset_split", id_policy="sequential")

    split_a = split_by_asset(manifest.assets, seed=7, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)
    split_b = split_by_asset(manifest.assets, seed=7, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)
    assert split_a == split_b
    assert len(split_a.train) == 6
    assert len(split_a.val) == 2
    assert len(split_a.test) == 2
    assert set(split_a.train).isdisjoint(split_a.val)
    assert set(split_a.train).isdisjoint(split_a.test)

    labeled = apply_split(manifest, split_a)
    assert all(asset.split in {"train", "val", "test"} for asset in labeled.assets)
