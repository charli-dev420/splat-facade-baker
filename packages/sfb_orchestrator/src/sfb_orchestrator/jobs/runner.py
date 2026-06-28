from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from ..comfy.client import ComfyClient
from ..db.store import OrchestratorStore
from ..models import JobRecord
from ..paths import SFBWorkspace
from ..utils import write_json
from ..workflows.template import WorkflowTemplateMetadata, inject_template_inputs, load_workflow_template


class JobRunner:
    def __init__(self, store: OrchestratorStore, workspace: SFBWorkspace):
        self.store = store
        self.workspace = workspace
        self.workspace.ensure()

    def run_next(self, project_id: str | None = None) -> JobRecord | None:
        job = self.store.claim_next_job(project_id)
        if job is None:
            return None
        return self.run_claimed(job)

    def run_claimed(self, job: JobRecord) -> JobRecord:
        try:
            if job.engine == "noop":
                return self._run_noop(job)
            if job.engine == "shell":
                return self._run_shell(job)
            if job.engine == "sfb_bake_maps":
                return self._run_sfb_bake_maps(job)
            if job.engine == "comfyui":
                return self._run_comfyui(job)
            if job.engine == "blender_capture":
                return self._run_blender_capture(job)
            raise ValueError(f"unsupported job engine: {job.engine}")
        except Exception as exc:
            self._write_job_log(job, "error.log", f"{type(exc).__name__}: {exc}\n")
            return self.store.update_job_status(job.job_id, "failed", error_type=type(exc).__name__, error_message=str(exc))

    def _job_dir(self, job: JobRecord) -> Path:
        path = self.workspace.logs_dir / job.project_id / job.job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_job_log(self, job: JobRecord, name: str, content: str) -> Path:
        path = self._job_dir(job) / name
        path.write_text(content, encoding="utf-8")
        return path

    def _run_noop(self, job: JobRecord) -> JobRecord:
        report = {
            "schema": "sfb.job_report.v1",
            "job_id": job.job_id,
            "engine": "noop",
            "params": job.params,
            "message": "Noop job completed successfully.",
        }
        report_path = self._job_dir(job) / "noop_report.json"
        write_json(report_path, report)
        self.store.register_artifact(
            job.project_id,
            job_id=job.job_id,
            asset_id=job.asset_id,
            artifact_type="job_report",
            path=report_path,
            metadata={"engine": job.engine},
        )
        return self.store.update_job_status(job.job_id, "completed")

    def _run_shell(self, job: JobRecord) -> JobRecord:
        command = job.params.get("command")
        if not command:
            raise ValueError("shell job requires params.command")
        shell = isinstance(command, str)
        cwd = job.params.get("cwd")
        proc = subprocess.run(
            command,
            shell=shell,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout_path = self._write_job_log(job, "stdout.log", proc.stdout)
        stderr_path = self._write_job_log(job, "stderr.log", proc.stderr)
        self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type="stdout_log", path=stdout_path)
        self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type="stderr_log", path=stderr_path)
        self._register_output_paths(job)
        if proc.returncode != 0:
            raise RuntimeError(f"shell command failed with exit code {proc.returncode}")
        return self.store.update_job_status(job.job_id, "completed")

    def _run_sfb_bake_maps(self, job: JobRecord) -> JobRecord:
        # Keep this engine subprocess-based so the orchestrator can remain loosely coupled to sfb_core.
        params = dict(job.params)
        required = ["albedo", "alpha", "depth", "out"]
        missing = [key for key in required if key not in params]
        if missing:
            raise ValueError(f"sfb_bake_maps missing required params: {', '.join(missing)}")
        command = [
            sys.executable,
            "-m",
            "sfb_core.cli",
            "bake-maps",
            "--albedo",
            str(params["albedo"]),
            "--alpha",
            str(params["alpha"]),
            "--depth",
            str(params["depth"]),
            "--out",
            str(params["out"]),
            "--name",
            str(params.get("name", job.asset_id or "SFB_Asset")),
            "--width-m",
            str(params.get("width_m", 8.0)),
            "--height-m",
            str(params.get("height_m", 4.0)),
            "--max-depth-m",
            str(params.get("max_depth_m", 0.5)),
            "--grid",
            str(params.get("grid", 96)),
            "--view-id",
            str(params.get("view_id", "front")),
        ]
        if params.get("view_contract"):
            command.extend(["--view-contract", str(params["view_contract"])])
        if params.get("mobile_tier"):
            command.extend(["--mobile-tier", str(params["mobile_tier"])])
        shell_job = job.model_copy(update={"engine": "shell", "params": {"command": command, "output_paths": [str(Path(params["out"]) / "asset.sfb.json")]}})
        result = self._run_shell(shell_job)
        return self.store.update_job_status(job.job_id, result.status)

    def _run_blender_capture(self, job: JobRecord) -> JobRecord:
        params = dict(job.params)
        blender = params.get("blender", "blender")
        script = params.get("script", "tools/render_glb_turntable.py")
        required = ["input", "asset_id", "view_contract", "out"]
        missing = [key for key in required if key not in params]
        if missing:
            raise ValueError(f"blender_capture missing required params: {', '.join(missing)}")
        command = [
            blender,
            "--background",
            "--python",
            script,
            "--",
            "--input",
            str(params["input"]),
            "--asset-id",
            str(params["asset_id"]),
            "--view-contract",
            str(params["view_contract"]),
            "--out",
            str(params["out"]),
            "--resolution",
            str(params.get("resolution", 1024)),
        ]
        if params.get("views"):
            views = params["views"]
            if isinstance(views, list):
                views = ",".join(str(v) for v in views)
            command.extend(["--views", str(views)])
        if params.get("samples") is not None:
            command.extend(["--samples", str(params["samples"])])
        shell_job = job.model_copy(update={"engine": "shell", "params": {"command": command, "output_paths": params.get("output_paths", [])}})
        result = self._run_shell(shell_job)
        return self.store.update_job_status(job.job_id, result.status)

    def _run_comfyui(self, job: JobRecord) -> JobRecord:
        params = dict(job.params)
        workflow = None
        workflow_meta = None
        if job.workflow_id:
            workflow_record = self.store.get_workflow(job.workflow_id, job.project_id)
            meta_path = workflow_record.metadata.get("metadata_path")
            if meta_path:
                workflow_meta = WorkflowTemplateMetadata.load(meta_path)
            template_path = params.get("template_path")
            if not template_path and workflow_meta and workflow_meta.template_path:
                template_path = str(workflow_meta.template_path)
            if not template_path:
                template_path = workflow_record.template_path
            if template_path:
                workflow = load_workflow_template(template_path)
        if workflow is None:
            workflow = params.get("workflow")
        if workflow is None:
            raise ValueError("comfyui job requires a workflow template, registered workflow, or params.workflow")
        if workflow_meta is not None:
            workflow = inject_template_inputs(workflow, workflow_meta, params)
        workflow_path = self._job_dir(job) / "injected_workflow.json"
        write_json(workflow_path, workflow)
        self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type="comfy_injected_workflow", path=workflow_path)
        if params.get("dry_run", False):
            return self.store.update_job_status(job.job_id, "completed")
        client = ComfyClient(base_url=params.get("comfy_url", "http://127.0.0.1:8188"), timeout=float(params.get("timeout", 30)))
        client_id = params.get("client_id", f"sfb-{uuid.uuid4().hex[:8]}")
        submitted = client.submit_prompt(workflow, client_id=client_id)
        prompt_id = submitted.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI did not return prompt_id: {submitted}")
        submit_path = self._job_dir(job) / "comfy_submit_response.json"
        write_json(submit_path, submitted)
        self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type="comfy_submit_response", path=submit_path)
        if params.get("wait", True):
            history_item = client.wait_for_history(prompt_id, poll_interval=float(params.get("poll_interval", 1.0)), timeout_s=float(params.get("timeout_s", 3600)))
            history_path = self._job_dir(job) / "comfy_history.json"
            write_json(history_path, history_item)
            self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type="comfy_history", path=history_path)
            refs = client.output_refs_from_history(history_item)
            refs_path = self._job_dir(job) / "comfy_output_refs.json"
            write_json(refs_path, refs)
            self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type="comfy_output_refs", path=refs_path, metadata={"count": len(refs)})
        self._register_output_paths(job)
        return self.store.update_job_status(job.job_id, "completed")

    def _register_output_paths(self, job: JobRecord) -> None:
        for raw in job.params.get("output_paths", []) or []:
            path = Path(raw)
            if not path.exists():
                continue
            kind = job.params.get("output_artifact_type") or path.suffix.lower().lstrip(".") or "file"
            self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type=kind, path=path)
