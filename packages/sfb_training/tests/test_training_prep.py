from __future__ import annotations

import json
from pathlib import Path

from sfb_training.dataset_report import manifest_training_report
from sfb_training.lora_exporter import export_lora_dataset
from sfb_training.pair_builder import export_view_pairs
from sfb_training.eval_sets import make_eval_set
from sfb_training.utils import read_jsonl


def _write_fake_png(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PNG-FAKE-" + label.encode("utf-8"))


def _manifest(tmp_path: Path) -> Path:
    renders = tmp_path / "renders"
    assets = []
    for idx, split in enumerate(["train", "val", "test"]):
        asset_id = f"asset_{idx:03d}"
        views = {}
        for view_id, az in [("front", 0), ("front_right", 45), ("right", 90)]:
            rgb = renders / asset_id / view_id / "rgb.png"
            _write_fake_png(rgb, f"{asset_id}-{view_id}")
            views[view_id] = {
                "view_id": view_id,
                "rgb": str(rgb),
                "azimuth_deg": az,
                "elevation_deg": 10,
                "camera_type": "orthographic",
                "status": "approved",
            }
        assets.append({
            "asset_id": asset_id,
            "data_tier": "gold",
            "quality_status": "approved",
            "category": "ruined_wall",
            "style_family": "mixed",
            "base_caption": "worn stone blocks",
            "tags": ["stone", "modular"],
            "split": split,
            "views": views,
        })
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "schema": "sfb.dataset_manifest.v1",
        "dataset_id": "test_dataset",
        "view_contract": "MV8_OBJECT",
        "assets": assets,
    }), encoding="utf-8")
    return path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_export_lora_dataset(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    out = tmp_path / "lora"
    report = export_lora_dataset(
        manifest,
        out,
        view_contract_path=_repo_root() / "examples" / "view_contracts" / "MV8_OBJECT.json",
        views=["front", "right"],
        overwrite=True,
    )
    assert report["summary"]["records_total"] == 6
    assert report["leakage"]["ok"] is True
    assert (out / "metadata.jsonl").exists()
    assert (out / "train.jsonl").exists()
    assert (out / "val.jsonl").exists()
    assert (out / "test.jsonl").exists()
    rows = read_jsonl(out / "metadata.jsonl")
    assert "sfb_clean_render" in rows[0]["caption_text"]
    assert (out / rows[0]["image"]).exists()
    assert (out / rows[0]["caption"]).exists()


def test_export_view_pairs_front_to_all(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    out = tmp_path / "pairs"
    report = export_view_pairs(
        manifest,
        out,
        view_contract_path=_repo_root() / "examples" / "view_contracts" / "MV8_OBJECT.json",
        pair_policy="front_to_all",
        target_views=["front_right", "right"],
        overwrite=True,
    )
    assert report["summary"]["records_total"] == 6
    rows = read_jsonl(out / "metadata.jsonl")
    assert rows[0]["source_view_id"] == "front"
    assert rows[0]["target_view_id"] in {"front_right", "right"}
    assert "target view" in rows[0]["caption_text"]
    assert (out / rows[0]["source_image"]).exists()
    assert (out / rows[0]["target_image"]).exists()


def test_make_eval_set_and_report(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    report = manifest_training_report(manifest)
    assert report["assets_total"] == 3
    assert report["view_counts"]["front"] == 3

    out = tmp_path / "eval"
    eval_report = make_eval_set(
        manifest,
        out,
        view_contract_path=_repo_root() / "examples" / "view_contracts" / "MV8_OBJECT.json",
        task="view_adapter",
        split="test",
        views=["right"],
        overwrite=True,
    )
    assert eval_report["items"] == 1
    assert (out / "eval_items.jsonl").exists()
    rows = read_jsonl(out / "eval_items.jsonl")
    assert rows[0]["task"] == "view_adapter"
    assert rows[0]["target_view_id"] == "right"
