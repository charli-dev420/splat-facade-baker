from __future__ import annotations

from fastapi.testclient import TestClient

from sfb_orchestrator.api.main import create_app


def test_api_project_job_noop(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True

    resp = client.post("/api/projects", json={"project_id": "p", "name": "Project"})
    assert resp.status_code == 200
    assert resp.json()["project_id"] == "p"

    job_resp = client.post("/api/jobs", json={"project_id": "p", "engine": "noop", "params": {"x": 1}})
    assert job_resp.status_code == 200
    job_id = job_resp.json()["job_id"]

    run_resp = client.post("/api/jobs/run-next?project_id=p")
    assert run_resp.status_code == 200
    assert run_resp.json()["job"]["status"] == "completed"

    artifacts = client.get(f"/api/artifacts?project_id=p&job_id={job_id}").json()["artifacts"]
    assert len(artifacts) == 1

    summary = client.get("/api/summary?project_id=p")
    assert summary.status_code == 200
    assert summary.json()["jobs"]["by_status"]["completed"] == 1

    logs = client.get(f"/api/jobs/{job_id}/logs")
    assert logs.status_code == 200
    assert any(item["name"] == "noop_report.json" for item in logs.json()["files"])


def test_api_asset_review_and_review_queue(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    client.post("/api/projects", json={"project_id": "p", "name": "Project"})
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        '{"schema":"sfb.dataset_manifest.v1","dataset_id":"d","assets":[{"asset_id":"a","quality_status":"needs_review","data_tier":"gold_candidate"}]}',
        encoding="utf-8",
    )
    resp = client.post("/api/assets/register-manifest", json={"project_id": "p", "manifest_path": str(manifest_path)})
    assert resp.status_code == 200
    assert resp.json()["registered_assets"] == 1
    queue = client.get("/api/review-queue?project_id=p").json()
    assert len(queue["assets"]) == 1
    review = client.patch("/api/assets/p/a/review", json={"quality_status": "approved"})
    assert review.status_code == 200
    assert review.json()["quality_status"] == "approved"


def test_api_scenes_listing_and_validation(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    scenes_dir = tmp_path / "workspace" / "scenes"
    scenes_dir.mkdir(parents=True)
    scene_path = scenes_dir / "demo.sfbscene.json"
    scene_path.write_text(
        '{"schema":"sfb.scene.v1","scene_id":"demo","cards":[],"chunks":[]}',
        encoding="utf-8",
    )
    scenes = client.get("/api/scenes").json()["scenes"]
    assert len(scenes) == 1
    assert scenes[0]["scene_id"] == "demo"
    report = client.get("/api/scenes/validate", params={"path": str(scene_path)}).json()
    assert report["status"] == "ok"
    assert report["metrics"]["cards_total"] == 0
