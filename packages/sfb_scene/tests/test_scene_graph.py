from __future__ import annotations

import json
from pathlib import Path

from sfb_scene.cli import main
from sfb_scene.models import ChunkGroup, SFBScene, SceneCard
from sfb_scene.placement import align_card_to_edge, resolve_view_rotation, update_chunk_bounds
from sfb_scene.validation import validate_scene


REPO = Path(__file__).resolve().parents[3]
VIEW_CONTRACT = REPO / "examples" / "view_contracts" / "MV8_OBJECT.json"
DEMO_PACKAGE = REPO / "examples" / "sfb_packages" / "DemoWall" / "asset.sfb.json"


def test_resolve_view_rotation_from_view_contract() -> None:
    rotation, spec = resolve_view_rotation(VIEW_CONTRACT, "front_right", base_rotation_y=30)
    assert rotation == 75
    assert spec["view_id"] == "front_right"


def test_scene_load_save_and_validate_demo_package(tmp_path: Path) -> None:
    scene_path = tmp_path / "scene.sfbscene.json"
    scene = SFBScene(scene_id="test_scene")
    scene.add_chunk(ChunkGroup(chunk_id="chunk_001", name="start"))
    scene.add_card(
        SceneCard(
            scene_card_id="card_001",
            asset_package=str(DEMO_PACKAGE),
            view_id="front",
            width_m=8,
            height_m=4,
            depth_m=0.45,
            chunk_id="chunk_001",
        )
    )
    update_chunk_bounds(scene, "chunk_001")
    scene.save(scene_path)

    loaded = SFBScene.load(scene_path)
    assert loaded.scene_id == "test_scene"
    assert loaded.chunks[0].bounds is not None

    report = validate_scene(loaded, scene_path=scene_path)
    assert report["status"] in {"ok", "needs_review"}
    assert report["metrics"]["cards_total"] == 1
    assert report["metrics"]["packages_found"] == 1


def test_align_card_to_right_edge() -> None:
    scene = SFBScene(scene_id="align")
    scene.add_card(SceneCard(scene_card_id="a", asset_package="a/asset.sfb.json", view_id="front", width_m=4))
    scene.add_card(SceneCard(scene_card_id="b", asset_package="b/asset.sfb.json", view_id="front", width_m=2))
    align_card_to_edge(scene, card_id="b", target_card_id="a", edge="right", overlap_m=0.25)
    assert scene.get_card("b").position[0] == 2.75


def test_cli_create_add_validate(tmp_path: Path) -> None:
    scene_path = tmp_path / "demo.sfbscene.json"
    assert main(["create", "--scene-id", "demo", "--out", str(scene_path)]) == 0
    assert main(["add-chunk", str(scene_path), "--chunk-id", "chunk_001", "--replace"]) == 0
    assert main([
        "add-card",
        str(scene_path),
        "--scene-card-id", "card_demo",
        "--asset-package", str(DEMO_PACKAGE),
        "--view-contract", str(VIEW_CONTRACT),
        "--view-id", "front_right",
        "--chunk-id", "chunk_001",
        "--replace",
    ]) == 0
    data = json.loads(scene_path.read_text())
    assert data["cards"][0]["rotation_y"] == 45
    report_path = tmp_path / "report.json"
    assert main(["validate", str(scene_path), "--out", str(report_path)]) == 0
    report = json.loads(report_path.read_text())
    assert report["metrics"]["cards_total"] == 1
