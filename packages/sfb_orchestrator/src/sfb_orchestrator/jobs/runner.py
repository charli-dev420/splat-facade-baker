from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from ..comfy.client import ComfyClient
from ..db.store import OrchestratorStore
from ..models import JobRecord
from ..paths import SFBWorkspace
from ..utils import write_json
from ..workflows.template import WorkflowTemplateMetadata, inject_template_inputs, load_workflow_template


class JobCancelledError(RuntimeError):
    pass


class JobRunner:
    def __init__(self, store: OrchestratorStore, workspace: SFBWorkspace, *, worker_id: str | None = None):
        self.store = store
        self.workspace = workspace
        self.worker_id = worker_id or make_worker_id("runner")
        self.heartbeat_interval_s = 0.2
        self.cancel_grace_s = 2.0
        self.workspace.ensure()

    def run_next(self, project_id: str | None = None) -> JobRecord | None:
        job = self.store.claim_next_job(project_id, worker_id=self.worker_id)
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
        except JobCancelledError as exc:
            self._write_job_log(job, "cancel.log", f"CancelledError: {exc}\n")
            return self.store.update_job_status(
                job.job_id,
                "cancelled",
                error_type="CancelledError",
                error_message=str(exc),
            )
        except Exception as exc:
            self._write_job_log(job, "error.log", f"{type(exc).__name__}: {exc}\n")
            if job.attempt < job.max_attempts:
                return self.store.requeue_failed_attempt(
                    job.job_id,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            return self.store.update_job_status(
                job.job_id,
                "failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

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
        command = _normalize_shell_command(job.params.get("command"))
        cwd = job.params.get("cwd")
        proc = subprocess.Popen(
            command,
            shell=False,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.store.set_job_process(job.job_id, proc.pid)
        stdout = ""
        stderr = ""
        cancelled = False
        try:
            while True:
                if self.store.is_cancel_requested(job.job_id):
                    self._terminate_process(proc)
                    stdout_tail, stderr_tail = proc.communicate()
                    stdout += stdout_tail or ""
                    stderr += stderr_tail or ""
                    cancelled = True
                    break
                try:
                    stdout_tail, stderr_tail = proc.communicate(timeout=self.heartbeat_interval_s)
                    stdout += stdout_tail or ""
                    stderr += stderr_tail or ""
                    break
                except subprocess.TimeoutExpired:
                    self.store.heartbeat_job(job.job_id)
            self.store.heartbeat_job(job.job_id)
        finally:
            self.store.set_job_process(job.job_id, None)
        stdout_path = self._write_job_log(job, "stdout.log", stdout)
        stderr_path = self._write_job_log(job, "stderr.log", stderr)
        self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type="stdout_log", path=stdout_path)
        self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type="stderr_log", path=stderr_path)
        if cancelled:
            raise JobCancelledError(f"job cancellation requested: {job.job_id}")
        if proc.returncode != 0:
            raise RuntimeError(f"shell command failed with exit code {proc.returncode}")
        self._register_output_paths(job)
        return self.store.update_job_status(job.job_id, "completed")

    def _terminate_process(self, proc: subprocess.Popen[str]) -> None:
        if proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=self.cancel_grace_s)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=self.cancel_grace_s)

    def _run_sfb_bake_maps(self, job: JobRecord) -> JobRecord:
        # Keep this engine subprocess-based so the orchestrator can remain loosely coupled to sfb_core.
        params = dict(job.params)
        required = ["albedo", "alpha", "depth", "out"]
        missing = [key for key in required if key not in params]
        if missing:
            raise ValueError(f"sfb_bake_maps missing required params: {', '.join(missing)}")
        out_dir = _resolve_workspace_path(self.workspace, params["out"])
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
            str(out_dir),
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
        shell_job = job.model_copy(update={"engine": "shell", "params": {"command": command, "output_paths": [str(out_dir / "asset.sfb.json")]}})
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
        out_dir = _resolve_workspace_path(self.workspace, params["out"])
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
            str(out_dir),
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
        shell_params: dict[str, Any] = {"command": command}
        if "output_paths" in params:
            shell_params["output_paths"] = params["output_paths"]
        shell_job = job.model_copy(update={"engine": "shell", "params": shell_params})
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
            history_item = self._wait_for_comfy_history(
                job,
                client,
                prompt_id,
                poll_interval=float(params.get("poll_interval", 1.0)),
                timeout_s=float(params.get("timeout_s", 3600)),
            )
            history_path = self._job_dir(job) / "comfy_history.json"
            write_json(history_path, history_item)
            self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type="comfy_history", path=history_path)
            refs = client.output_refs_from_history(history_item)
            refs_path = self._job_dir(job) / "comfy_output_refs.json"
            write_json(refs_path, refs)
            self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type="comfy_output_refs", path=refs_path, metadata={"count": len(refs)})
        self._register_output_paths(job)
        return self.store.update_job_status(job.job_id, "completed")

    def _wait_for_comfy_history(
        self,
        job: JobRecord,
        client: ComfyClient,
        prompt_id: str,
        *,
        poll_interval: float,
        timeout_s: float,
    ) -> dict[str, Any]:
        start = time.monotonic()
        while True:
            if self.store.is_cancel_requested(job.job_id):
                try:
                    client.interrupt()
                except Exception as exc:  # noqa: BLE001 - interrupt is best-effort.
                    self._write_job_log(job, "comfy_interrupt_error.log", f"{type(exc).__name__}: {exc}\n")
                raise JobCancelledError(f"ComfyUI wait cancelled for prompt: {prompt_id}")
            data = client.history(prompt_id)
            if prompt_id in data:
                self.store.heartbeat_job(job.job_id)
                return data[prompt_id]
            if time.monotonic() - start > timeout_s:
                raise TimeoutError(f"ComfyUI prompt timed out: {prompt_id}")
            self.store.heartbeat_job(job.job_id)
            time.sleep(min(max(poll_interval, 0.05), 5.0))

    def _register_output_paths(self, job: JobRecord) -> None:
        if "output_paths" not in job.params or job.params.get("output_paths") is None:
            return
        output_paths = job.params["output_paths"]
        if isinstance(output_paths, str) or not isinstance(output_paths, list):
            raise ValueError("job params.output_paths must be a list of file paths")
        if not output_paths:
            raise ValueError("job params.output_paths must not be empty when provided")
        for index, raw in enumerate(output_paths):
            if raw is None or isinstance(raw, (dict, list)):
                raise ValueError(f"job params.output_paths[{index}] must be a string-like file path")
            path = _resolve_workspace_path(self.workspace, raw)
            if not path.exists() or not path.is_file():
                raise ValueError(f"declared output path does not exist or is not a file: {path}")
            kind = job.params.get("output_artifact_type") or path.suffix.lower().lstrip(".") or "file"
            self.store.register_artifact(job.project_id, job_id=job.job_id, asset_id=job.asset_id, artifact_type=kind, path=path)


def _normalize_shell_command(command: Any) -> list[str]:
    if isinstance(command, str):
        raise ValueError("shell job params.command must be a non-empty argv list, not a string")
    if not isinstance(command, list) or not command:
        raise ValueError("shell job requires params.command as a non-empty argv list")
    normalized: list[str] = []
    for index, item in enumerate(command):
        if item is None or isinstance(item, (dict, list)):
            raise ValueError(f"shell job params.command[{index}] must be a string-like value")
        normalized.append(str(item))
    return normalized


def make_worker_id(prefix: str = "worker") -> str:
    host = socket.gethostname().replace(" ", "_")
    return f"{prefix}_{host}_{os.getpid()}_{uuid.uuid4().hex[:8]}"


def _resolve_workspace_path(workspace: SFBWorkspace, raw: Any) -> Path:
    if raw is None or isinstance(raw, (dict, list)):
        raise ValueError("path must be a string-like value")
    path = Path(str(raw))
    resolved = path.resolve() if path.is_absolute() else (workspace.root / path).resolve()
    root = workspace.root.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path is outside the workspace: {raw}") from exc
    return resolved
