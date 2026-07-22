from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from sfb_orchestrator.db.store import OrchestratorStore
from sfb_orchestrator.jobs.runner import JobRunner
from sfb_orchestrator.paths import SFBWorkspace
from sfb_orchestrator.workflows.template import WorkflowTemplateMetadata, inject_template_inputs, load_workflow_template


def test_store_project_asset_job_noop(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    project = store.create_project("test_project", name="Test Project", root_path=workspace.root)
    assert project.project_id == "test_project"

    job = store.create_job("test_project", engine="noop", params={"hello": "world"})
    assert job.status == "queued"

    finished = JobRunner(store, workspace).run_next("test_project")
    assert finished is not None
    assert finished.status == "completed"
    artifacts = store.list_artifacts("test_project", job_id=finished.job_id)
    assert len(artifacts) == 1
    assert artifacts[0].artifact_type == "job_report"
    assert Path(artifacts[0].path).exists()


def test_register_manifest_imports_assets(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    manifest = {
        "schema": "sfb.dataset_manifest.v1",
        "dataset_id": "dataset_a",
        "assets": [
            {
                "asset_id": "asset_a",
                "source_path": "sources/a.glb",
                "source_hash": "abc",
                "data_tier": "gold_candidate",
                "quality_status": "needs_review",
                "category": "wall",
                "style_family": "mixed",
                "views": {"front": {"rgb": "renders/a/front/rgb.png"}},
                "split": "train",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    count = store.register_manifest("p", manifest_path)
    assert count == 1
    asset = store.get_asset("p", "asset_a")
    assert asset.manifest_id == "dataset_a"
    assert asset.metadata["views"]["front"]["rgb"] == "renders/a/front/rgb.png"


def test_comfy_template_injection(tmp_path: Path) -> None:
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "old.png"}},
        "2": {"class_type": "SaveImage", "inputs": {"filename_prefix": "old"}},
    }
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps({
        "workflow_id": "wf",
        "engine": "comfyui",
        "template_file": "workflow.json",
        "inputs": {
            "input_image": {"node_id": "1", "field": "image"},
            "filename_prefix": {"path": "2.inputs.filename_prefix"},
        },
        "outputs": {},
    }), encoding="utf-8")
    meta = WorkflowTemplateMetadata.load(meta_path)
    injected = inject_template_inputs(load_workflow_template(meta.template_path), meta, {"input_image": "new.png", "filename_prefix": "SFB/test"})
    assert injected["1"]["inputs"]["image"] == "new.png"
    assert injected["2"]["inputs"]["filename_prefix"] == "SFB/test"


def test_comfyui_dry_run_job_registers_injected_workflow(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    workflow = {"1": {"class_type": "LoadImage", "inputs": {"image": "old.png"}}}
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps({
        "workflow_id": "wf",
        "engine": "comfyui",
        "template_file": "workflow.json",
        "inputs": {"input_image": {"node_id": "1", "field": "image"}},
        "outputs": {},
    }), encoding="utf-8")
    store.register_workflow_metadata(meta_path, project_id="p")
    job = store.create_job("p", engine="comfyui", workflow_id="wf", params={"input_image": "asset.png", "dry_run": True})
    result = JobRunner(store, workspace).run_next("p")
    assert result is not None
    assert result.status == "completed"
    artifacts = store.list_artifacts("p", job_id=job.job_id)
    assert any(a.artifact_type == "comfy_injected_workflow" for a in artifacts)


def test_shell_job_with_argv_list_runs_for_local_runner(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    job = store.create_job(
        "p",
        engine="shell",
        params={"command": [sys.executable, "-c", "print('shell ok')"]},
    )

    result = JobRunner(store, workspace).run_next("p")

    assert result is not None
    assert result.status == "completed"
    stdout = workspace.logs_dir / "p" / job.job_id / "stdout.log"
    assert "shell ok" in stdout.read_text(encoding="utf-8")


def test_shell_job_with_string_command_fails_without_executing(tmp_path: Path, monkeypatch) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    job = store.create_job(
        "p",
        engine="shell",
        max_attempts=1,
        params={"command": f"{sys.executable} -c \"print('should not run')\""},
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called for string shell commands")

    monkeypatch.setattr("sfb_orchestrator.jobs.runner.subprocess.run", fail_if_called)
    result = JobRunner(store, workspace).run_next("p")

    assert result is not None
    assert result.status == "failed"
    assert result.error_type == "ValueError"
    assert "argv list" in (result.error_message or "")
    error_log = workspace.logs_dir / "p" / job.job_id / "error.log"
    assert "argv list" in error_log.read_text(encoding="utf-8")


def test_sfb_bake_maps_uses_internal_shell_argv_list(tmp_path: Path, monkeypatch) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    job = store.create_job(
        "p",
        engine="sfb_bake_maps",
        params={
            "albedo": "albedo.png",
            "alpha": "alpha.png",
            "depth": "depth.png",
            "out": "exports/Test",
        },
    )
    seen: dict[str, object] = {}

    def fake_run_shell(self, shell_job):
        seen["command"] = shell_job.params["command"]
        return store.update_job_status(shell_job.job_id, "completed")

    monkeypatch.setattr(JobRunner, "_run_shell", fake_run_shell)
    result = JobRunner(store, workspace).run_next("p")

    assert result is not None
    assert result.status == "completed"
    assert isinstance(seen["command"], list)
    assert seen["command"][:3] == [sys.executable, "-m", "sfb_core.cli"]


def test_blender_capture_uses_internal_shell_argv_list(tmp_path: Path, monkeypatch) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    store.create_job(
        "p",
        engine="blender_capture",
        params={
            "input": "source.glb",
            "asset_id": "asset",
            "view_contract": "examples/view_contracts/MV8_OBJECT.json",
            "out": "workspace/renders/asset",
        },
    )
    seen: dict[str, object] = {}

    def fake_run_shell(self, shell_job):
        seen["command"] = shell_job.params["command"]
        return store.update_job_status(shell_job.job_id, "completed")

    monkeypatch.setattr(JobRunner, "_run_shell", fake_run_shell)
    result = JobRunner(store, workspace).run_next("p")

    assert result is not None
    assert result.status == "completed"
    assert isinstance(seen["command"], list)
    assert seen["command"][:3] == ["blender", "--background", "--python"]


def test_atomic_claim_allows_only_one_worker_per_job(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    job = store.create_job("p", engine="noop")
    barrier = threading.Barrier(2)
    results: list[str | None] = []

    def claim() -> None:
        local_store = OrchestratorStore(workspace.db_path)
        barrier.wait()
        claimed = local_store.claim_next_job("p")
        results.append(None if claimed is None else claimed.job_id)

    threads = [threading.Thread(target=claim) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results, key=lambda value: value or "") == [None, job.job_id]
    claimed_job = store.get_job(job.job_id)
    assert claimed_job.status == "running"
    assert claimed_job.attempt == 1
    assert claimed_job.heartbeat_at is not None


def test_store_migrates_existing_jobs_table_with_lifecycle_columns(tmp_path: Path) -> None:
    import sqlite3

    db = tmp_path / "old.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE jobs (
              job_id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              engine TEXT NOT NULL,
              workflow_id TEXT,
              asset_id TEXT,
              status TEXT NOT NULL,
              priority INTEGER NOT NULL DEFAULT 50,
              params_json TEXT NOT NULL DEFAULT '{}',
              recipe_hash TEXT,
              attempt INTEGER NOT NULL DEFAULT 0,
              max_attempts INTEGER NOT NULL DEFAULT 3,
              created_at TEXT NOT NULL,
              started_at TEXT,
              finished_at TEXT,
              error_type TEXT,
              error_message TEXT
            );
            INSERT INTO jobs(job_id, project_id, engine, status, params_json, created_at)
            VALUES ('job_old', 'p', 'noop', 'queued', '{}', '2026-01-01T00:00:00+00:00');
            """
        )

    store = OrchestratorStore(db)
    job = store.get_job("job_old")

    assert job.job_id == "job_old"
    assert job.heartbeat_at is None
    assert job.cancel_requested_at is None


def test_atomic_claim_preserves_priority_then_created_order(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    first_low = store.create_job("p", engine="noop", priority=10)
    high = store.create_job("p", engine="noop", priority=100)
    second_low = store.create_job("p", engine="noop", priority=10)

    assert store.claim_next_job("p").job_id == high.job_id
    assert store.claim_next_job("p").job_id == first_low.job_id
    assert store.claim_next_job("p").job_id == second_low.job_id


def test_auto_retry_until_max_attempts_then_failed(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    job = store.create_job(
        "p",
        engine="shell",
        max_attempts=2,
        params={"command": [sys.executable, "-c", "raise SystemExit(7)"]},
    )
    runner = JobRunner(store, workspace)

    first = runner.run_next("p")
    assert first is not None
    assert first.status == "queued"
    assert first.attempt == 1
    assert first.error_type == "RuntimeError"

    second = runner.run_next("p")
    assert second is not None
    assert second.status == "failed"
    assert second.attempt == 2
    assert second.error_type == "RuntimeError"

    assert store.claim_next_job("p") is None
    assert store.get_job(job.job_id).status == "failed"


def test_manual_retry_resets_failed_job_attempts(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    job = store.create_job("p", engine="noop")
    claimed = store.claim_next_job("p")
    assert claimed is not None
    store.update_job_status(job.job_id, "failed", error_type="TestError", error_message="failed")

    retried = store.retry_job(job.job_id)

    assert retried.status == "queued"
    assert retried.attempt == 0
    assert retried.started_at is None
    assert retried.finished_at is None
    assert retried.error_type is None
    assert retried.error_message is None


def test_cancel_transitions_for_queued_running_and_terminal_jobs(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    running = store.create_job("p", engine="noop")
    queued = store.create_job("p", engine="noop")
    completed = store.create_job("p", engine="noop")
    claimed = store.claim_next_job("p", worker_id="worker_test")
    assert claimed is not None
    assert claimed.job_id == running.job_id
    store.update_job_status(completed.job_id, "completed")

    cancelled = store.request_cancel_job(queued.job_id, reason="not needed")
    cancelling = store.request_cancel_job(claimed.job_id, reason="stop")

    assert cancelled.status == "cancelled"
    assert cancelled.finished_at is not None
    assert cancelling.status == "cancelling"
    assert cancelling.cancel_requested_at is not None
    assert cancelling.worker_id == "worker_test"
    with pytest.raises(ValueError):
        store.request_cancel_job(completed.job_id)


def test_manual_retry_resets_cancelled_job_lifecycle_fields(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    job = store.create_job("p", engine="noop")
    store.request_cancel_job(job.job_id, reason="operator")

    retried = store.retry_job(job.job_id)

    assert retried.status == "queued"
    assert retried.attempt == 0
    assert retried.cancel_requested_at is None
    assert retried.cancel_reason is None
    assert retried.worker_id is None
    assert retried.process_id is None


def test_manual_retry_rejects_active_and_completed_jobs(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    queued = store.create_job("p", engine="noop")
    running = store.create_job("p", engine="noop")
    completed = store.create_job("p", engine="noop")
    store.claim_next_job("p")
    store.update_job_status(completed.job_id, "completed")

    for job_id in [queued.job_id, running.job_id, completed.job_id]:
        with pytest.raises(ValueError):
            store.retry_job(job_id)


def test_failed_shell_command_does_not_register_declared_output(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    out = workspace.root / "outputs" / "failed.txt"
    out.parent.mkdir(parents=True)
    out.write_text("exists but command fails", encoding="utf-8")
    job = store.create_job(
        "p",
        engine="shell",
        max_attempts=1,
        params={"command": [sys.executable, "-c", "raise SystemExit(3)"], "output_paths": ["outputs/failed.txt"]},
    )

    result = JobRunner(store, workspace).run_next("p")

    assert result is not None
    assert result.status == "failed"
    artifacts = store.list_artifacts("p", job_id=job.job_id)
    assert all(a.path != str(out.resolve()) for a in artifacts)


def test_long_running_shell_job_can_be_cancelled_and_does_not_register_outputs(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    output = workspace.root / "outputs" / "cancelled.txt"
    code = (
        "from pathlib import Path; import time; "
        f"p=Path({str(output)!r}); p.parent.mkdir(parents=True, exist_ok=True); "
        "p.write_text('created before cancel', encoding='utf-8'); time.sleep(30)"
    )
    job = store.create_job(
        "p",
        engine="shell",
        max_attempts=1,
        params={"command": [sys.executable, "-c", code], "output_paths": ["outputs/cancelled.txt"]},
    )
    runner = JobRunner(store, workspace, worker_id="worker_cancel_test")
    result_holder: list[object] = []
    thread = threading.Thread(target=lambda: result_holder.append(runner.run_next("p")))
    thread.start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        active = store.get_job(job.job_id)
        if active.process_id is not None:
            break
        time.sleep(0.05)
    assert store.get_job(job.job_id).process_id is not None

    store.request_cancel_job(job.job_id, reason="test cancel")
    thread.join(timeout=10)

    assert not thread.is_alive()
    result = result_holder[0]
    assert result.status == "cancelled"
    assert result.error_type == "CancelledError"
    assert (workspace.logs_dir / "p" / job.job_id / "cancel.log").exists()
    artifacts = store.list_artifacts("p", job_id=job.job_id)
    assert all(a.path != str(output.resolve()) for a in artifacts)


def test_comfyui_wait_cancel_marks_job_cancelled_and_interrupts(tmp_path: Path, monkeypatch) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    job = store.create_job(
        "p",
        engine="comfyui",
        max_attempts=1,
        params={"workflow": {"1": {"class_type": "SaveImage", "inputs": {}}}, "poll_interval": 0.05, "timeout_s": 5},
    )
    interrupted: list[bool] = []

    def fake_submit(self, workflow, client_id):
        return {"prompt_id": "prompt_1"}

    def fake_history(self, prompt_id):
        store.request_cancel_job(job.job_id, reason="cancel comfy")
        return {}

    def fake_interrupt(self):
        interrupted.append(True)
        return {"ok": True}

    monkeypatch.setattr("sfb_orchestrator.jobs.runner.ComfyClient.submit_prompt", fake_submit)
    monkeypatch.setattr("sfb_orchestrator.jobs.runner.ComfyClient.history", fake_history)
    monkeypatch.setattr("sfb_orchestrator.jobs.runner.ComfyClient.interrupt", fake_interrupt)

    result = JobRunner(store, workspace, worker_id="worker_comfy_cancel").run_next("p")

    assert result is not None
    assert result.status == "cancelled"
    assert result.error_type == "CancelledError"
    assert interrupted == [True]


def test_output_paths_are_strict_and_workspace_scoped(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    cases = [
        [],
        "outputs/scalar.txt",
        ["outputs/missing.txt"],
        ["../outside.txt"],
        [str(outside)],
        [{"bad": "shape"}],
    ]

    for output_paths in cases:
        job = store.create_job(
            "p",
            engine="shell",
            max_attempts=1,
            params={
                "command": [sys.executable, "-c", "print('ok')"],
                "output_paths": output_paths,
            },
        )
        result = JobRunner(store, workspace).run_next("p")
        assert result is not None
        assert result.status == "failed"
        assert result.error_type == "ValueError"
        assert store.list_artifacts("p", job_id=job.job_id)


def test_valid_output_path_registers_single_artifact_on_repeated_registration(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)
    output = workspace.root / "outputs" / "ok.txt"
    output.parent.mkdir(parents=True)
    output.write_text("ok", encoding="utf-8")
    job = store.create_job(
        "p",
        engine="shell",
        params={"command": [sys.executable, "-c", "print('ok')"], "output_paths": ["outputs/ok.txt"]},
    )
    runner = JobRunner(store, workspace)

    result = runner.run_next("p")
    assert result is not None
    assert result.status == "completed"
    runner._register_output_paths(store.get_job(job.job_id))

    artifacts = [
        artifact
        for artifact in store.list_artifacts("p", job_id=job.job_id)
        if artifact.path == str(output.resolve())
    ]
    assert len(artifacts) == 1


def test_create_job_rejects_invalid_max_attempts(tmp_path: Path) -> None:
    workspace = SFBWorkspace(tmp_path / "workspace")
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    store.create_project("p", root_path=workspace.root)

    with pytest.raises(ValueError):
        store.create_job("p", engine="noop", max_attempts=0)
