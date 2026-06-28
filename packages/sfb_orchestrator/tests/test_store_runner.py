from __future__ import annotations

import json
from pathlib import Path

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
