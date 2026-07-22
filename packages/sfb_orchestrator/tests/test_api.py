from __future__ import annotations

import json

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


def test_api_bakes_marks_corrupt_package_json_invalid(tmp_path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace)
    client = TestClient(app)
    package_path = workspace / "exports" / "Broken" / "asset.sfb.json"
    package_path.parent.mkdir(parents=True)
    package_path.write_text("{ broken json", encoding="utf-8")

    bakes = client.get("/api/bakes").json()["bakes"]

    assert len(bakes) == 1
    bake = bakes[0]
    assert bake["asset_id"] == "Broken"
    assert bake["status"] == "invalid_package_json"
    assert bake["metrics"] is None
    assert bake["report_path"] is None
    assert bake["errors"][0].startswith("invalid_package_json:")

    queue = client.get("/api/review-queue").json()
    assert len(queue["bakes"]) == 1
    summary = client.get("/api/summary").json()
    assert summary["review"]["bakes_needs_review"] == 1


def test_api_bakes_marks_corrupt_report_json_invalid(tmp_path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace)
    client = TestClient(app)
    package_dir = workspace / "exports" / "CorruptReport"
    report_path = package_dir / "reports" / "CorruptReport_report.json"
    report_path.parent.mkdir(parents=True)
    (package_dir / "asset.sfb.json").write_text(
        json.dumps({
            "schema": "sfb.asset.v1",
            "asset_id": "CorruptReport",
            "source_asset_id": "src",
            "view_id": "front",
            "mode": "depth_card",
            "report": "reports/CorruptReport_report.json",
            "runtime": {"lod_count": 3},
        }),
        encoding="utf-8",
    )
    report_path.write_text("{ broken report", encoding="utf-8")

    bakes = client.get("/api/bakes").json()["bakes"]

    assert len(bakes) == 1
    bake = bakes[0]
    assert bake["asset_id"] == "CorruptReport"
    assert bake["source_asset_id"] == "src"
    assert bake["status"] == "invalid_package_json"
    assert bake["metrics"] is None
    assert bake["report_path"] == str(report_path)
    assert bake["errors"][0].startswith("invalid_report_json:")


def test_api_file_serves_workspace_file(tmp_path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace)
    client = TestClient(app)
    safe_file = workspace / "safe.txt"
    safe_file.write_text("safe content", encoding="utf-8")

    resp = client.get("/api/file", params={"path": "safe.txt"})

    assert resp.status_code == 200
    assert resp.text == "safe content"


def test_api_file_rejects_traversal_outside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace)
    client = TestClient(app)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    resp = client.get("/api/file", params={"path": "../outside.txt"})

    assert resp.status_code == 403


def test_api_file_rejects_absolute_path_outside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace)
    client = TestClient(app)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    resp = client.get("/api/file", params={"path": str(outside)})

    assert resp.status_code == 403


def test_api_file_returns_404_for_safe_missing_file(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)

    resp = client.get("/api/file", params={"path": "missing.txt"})

    assert resp.status_code == 404


def test_api_rejects_public_shell_job_creation(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    client.post("/api/projects", json={"project_id": "p", "name": "Project"})

    resp = client.post(
        "/api/jobs",
        json={"project_id": "p", "engine": "shell", "params": {"command": ["python", "--version"]}},
    )

    assert resp.status_code == 400
    assert "unsupported public job engine" in resp.json()["detail"]
    jobs = client.get("/api/jobs?project_id=p").json()["jobs"]
    assert jobs == []


def test_api_rejects_public_shell_job_creation_with_string_command(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    client.post("/api/projects", json={"project_id": "p", "name": "Project"})

    resp = client.post(
        "/api/jobs",
        json={"project_id": "p", "engine": "shell", "params": {"command": "python --version"}},
    )

    assert resp.status_code == 400
    jobs = client.get("/api/jobs?project_id=p").json()["jobs"]
    assert jobs == []


def test_api_rejects_unknown_job_engine(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    client.post("/api/projects", json={"project_id": "p", "name": "Project"})

    resp = client.post("/api/jobs", json={"project_id": "p", "engine": "danger", "params": {}})

    assert resp.status_code == 400
    assert "unsupported public job engine" in resp.json()["detail"]


def test_api_job_creation_persists_max_attempts(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    client.post("/api/projects", json={"project_id": "p", "name": "Project"})

    resp = client.post(
        "/api/jobs",
        json={"project_id": "p", "engine": "noop", "max_attempts": 5},
    )

    assert resp.status_code == 200
    assert resp.json()["max_attempts"] == 5


def test_api_job_creation_rejects_invalid_max_attempts(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    client.post("/api/projects", json={"project_id": "p", "name": "Project"})

    resp = client.post(
        "/api/jobs",
        json={"project_id": "p", "engine": "noop", "max_attempts": 0},
    )

    assert resp.status_code == 400
    assert "max_attempts" in resp.json()["detail"]


def test_api_retry_rejects_queued_job_with_400(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    client.post("/api/projects", json={"project_id": "p", "name": "Project"})
    job_id = client.post("/api/jobs", json={"project_id": "p", "engine": "noop"}).json()["job_id"]

    resp = client.post(f"/api/jobs/{job_id}/retry")

    assert resp.status_code == 400


def test_api_cancel_queued_job_marks_cancelled(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    client.post("/api/projects", json={"project_id": "p", "name": "Project"})
    job_id = client.post("/api/jobs", json={"project_id": "p", "engine": "noop"}).json()["job_id"]

    resp = client.post(f"/api/jobs/{job_id}/cancel", json={"reason": "operator"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancel_requested_at"] is not None
    assert body["cancel_reason"] == "operator"


def test_api_cancel_running_job_marks_cancelling(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    client.post("/api/projects", json={"project_id": "p", "name": "Project"})
    job_id = client.post("/api/jobs", json={"project_id": "p", "engine": "noop"}).json()["job_id"]
    store = app.state.store
    claimed = store.claim_next_job("p", worker_id="api_test_worker")
    assert claimed.job_id == job_id

    resp = client.post(f"/api/jobs/{job_id}/cancel")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelling"
    assert body["cancel_requested_at"] is not None
    assert body["worker_id"] == "api_test_worker"


def test_api_cancel_terminal_job_returns_400(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    client.post("/api/projects", json={"project_id": "p", "name": "Project"})
    job_id = client.post("/api/jobs", json={"project_id": "p", "engine": "noop"}).json()["job_id"]
    client.post("/api/jobs/run-next?project_id=p")

    resp = client.post(f"/api/jobs/{job_id}/cancel")

    assert resp.status_code == 400


def test_api_job_log_rejects_traversal(tmp_path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace)
    client = TestClient(app)
    client.post("/api/projects", json={"project_id": "p", "name": "Project"})
    job_id = client.post("/api/jobs", json={"project_id": "p", "engine": "noop"}).json()["job_id"]
    run_resp = client.post("/api/jobs/run-next?project_id=p")
    assert run_resp.status_code == 200
    outside = workspace / "orchestrator" / "logs" / "p" / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    resp = client.get(f"/api/jobs/{job_id}/logs/..\\outside.txt")

    assert resp.status_code == 403


def test_api_validation_latest_reports_and_logs(tmp_path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace)
    client = TestClient(app)
    report_dir = workspace / "validation_reports"
    log_dir = report_dir / "logs" / "20260101-010101"
    log_dir.mkdir(parents=True)
    report = {
        "schema": "sfb.validation_report.v1",
        "run_id": "20260101-010101",
        "ok": True,
        "status": "passed",
        "gates": [{"name": "unit", "status": "passed", "ok": True}],
    }
    (report_dir / "20260101-010101.json").write_text(json.dumps(report), encoding="utf-8")
    (report_dir / "latest.json").write_text(json.dumps(report), encoding="utf-8")
    (log_dir / "unit.stdout.log").write_text("hello", encoding="utf-8")

    latest = client.get("/api/validation/latest")
    reports = client.get("/api/validation/reports")
    by_id = client.get("/api/validation/reports/20260101-010101")
    log = client.get("/api/validation/logs/20260101-010101/unit.stdout.log")

    assert latest.status_code == 200
    assert latest.json()["run_id"] == "20260101-010101"
    assert reports.status_code == 200
    assert [item["run_id"] for item in reports.json()["reports"]] == ["20260101-010101"]
    assert by_id.status_code == 200
    assert by_id.json()["status"] == "passed"
    assert log.status_code == 200
    assert log.text == "hello"


def test_api_validation_latest_404_when_missing(tmp_path):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)

    resp = client.get("/api/validation/latest")

    assert resp.status_code == 404


def test_api_validation_log_rejects_traversal(tmp_path):
    workspace = tmp_path / "workspace"
    app = create_app(workspace)
    client = TestClient(app)
    log_dir = workspace / "validation_reports" / "logs" / "run"
    log_dir.mkdir(parents=True)
    (workspace / "validation_reports" / "logs" / "outside.log").write_text("secret", encoding="utf-8")

    resp = client.get("/api/validation/logs/run/..\\outside.log")

    assert resp.status_code == 403


def test_api_validation_run_builds_command_and_rejects_second_active_run(tmp_path, monkeypatch):
    app = create_app(tmp_path / "workspace")
    client = TestClient(app)
    seen: dict[str, object] = {}

    class FakeProcess:
        pid = 4242

        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr("sfb_orchestrator.api.main.subprocess.Popen", fake_popen)

    resp = client.post(
        "/api/validation/run",
        json={"real_workspace_smoke": True, "include_blender": True, "skip_slow": True},
    )
    active = client.get("/api/validation/active")
    second = client.post("/api/validation/run", json={})

    assert resp.status_code == 200
    assert resp.json()["process_id"] == 4242
    command = seen["command"]
    assert "run_validation_pipeline.py" in command[1]
    assert "--skip-slow" in command
    assert "--real-workspace-smoke" in command
    assert "--include-blender" in command
    assert seen["kwargs"]["shell"] is False
    assert active.status_code == 200
    assert active.json()["active"]["status"] == "running"
    assert second.status_code == 409
