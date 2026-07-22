from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from PIL import Image

from sfb_dataset.manifest import AssetRecord, DatasetManifest


ROOT = Path(__file__).resolve().parents[3]


def _load_triage_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "triage_glb_dataset",
        ROOT / "tools" / "triage_glb_dataset.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


triage = _load_triage_module()


def test_source_preflight_rejects_duplicate_hash(tmp_path: Path) -> None:
    source = tmp_path / "asset.glb"
    source.write_bytes(b"glb")
    asset = AssetRecord(asset_id="asset", source_path=str(source), source_hash="abc")

    status, score, reasons, _metrics = triage.source_preflight(
        asset,
        source,
        {"abc"},
        triage.TriageThresholds(),
    )

    assert status == "reject"
    assert score == 0.0
    assert reasons == ["duplicate_source_hash:abc"]


def test_alpha_analysis_marks_invisible_image_for_rejection(tmp_path: Path) -> None:
    alpha = tmp_path / "alpha.png"
    Image.new("L", (16, 16), 0).save(alpha)

    score_delta, reasons, metrics = triage.analyze_alpha(alpha, triage.TriageThresholds())

    assert score_delta == -100
    assert "invisible_or_tiny_alpha" in reasons
    assert metrics["alpha_coverage"] == 0
    assert triage.classify(0.0, reasons) == "reject"


def test_alpha_analysis_keeps_centered_visible_image(tmp_path: Path) -> None:
    alpha = tmp_path / "alpha.png"
    image = Image.new("L", (32, 32), 0)
    for y in range(8, 24):
        for x in range(8, 24):
            image.putpixel((x, y), 255)
    image.save(alpha)

    score_delta, reasons, metrics = triage.analyze_alpha(alpha, triage.TriageThresholds())

    assert score_delta == 0
    assert reasons == []
    assert metrics["alpha_coverage"] == 0.25
    assert triage.classify(100.0, reasons) == "keep"


def test_write_status_manifests_preserves_pending_and_statuses(tmp_path: Path) -> None:
    manifest = DatasetManifest(
        dataset_id="triage_test",
        assets=[
            AssetRecord(asset_id="keep_asset", source_path="keep.glb"),
            AssetRecord(asset_id="reject_asset", source_path="reject.glb"),
            AssetRecord(asset_id="pending_asset", source_path="pending.glb"),
        ],
    )
    items = [
        triage.TriageItem("keep_asset", "keep.glb", "keep", 100.0),
        triage.TriageItem("reject_asset", "reject.glb", "reject", 0.0, ["broken"]),
    ]

    outputs = triage.write_status_manifests(
        manifest,
        items,
        [manifest.assets[2]],
        tmp_path,
        "triage_test",
    )

    keep = DatasetManifest.load(outputs["keep_manifest"])
    reject = DatasetManifest.load(outputs["reject_manifest"])
    pending = DatasetManifest.load(outputs["pending_manifest"])
    assert [asset.asset_id for asset in keep.assets] == ["keep_asset"]
    assert keep.assets[0].quality_status == "approved"
    assert [asset.asset_id for asset in reject.assets] == ["reject_asset"]
    assert reject.assets[0].data_tier == "rejected"
    assert [asset.asset_id for asset in pending.assets] == ["pending_asset"]
