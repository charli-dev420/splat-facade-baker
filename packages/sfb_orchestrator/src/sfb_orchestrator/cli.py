from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from .comfy.client import ComfyClient
from .db.store import OrchestratorStore
from .jobs.runner import JobRunner, _normalize_shell_command, make_worker_id
from .models import WorkflowRecord
from .paths import SFBWorkspace
from .utils import read_json, write_json


def _print(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _parse_params(values: list[str] | None, params_json: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if params_json:
        p = Path(params_json)
        params.update(read_json(p) if p.exists() else json.loads(params_json))
    for item in values or []:
        if "=" not in item:
            raise ValueError(f"expected KEY=VALUE, got: {item}")
        key, value = item.split("=", 1)
        try:
            params[key] = json.loads(value)
        except json.JSONDecodeError:
            params[key] = value
    return params


def _workspace(args: argparse.Namespace) -> SFBWorkspace:
    ws = SFBWorkspace.from_env(getattr(args, "workspace", None))
    ws.ensure()
    return ws


def _store(args: argparse.Namespace) -> OrchestratorStore:
    return OrchestratorStore(_workspace(args).db_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sfb-orch", description="SFB local orchestrator CLI")
    parser.add_argument("--workspace", default=None, help="Workspace root. Defaults to SFB_WORKSPACE or ./workspace.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize a local SFB workspace and SQLite registry.")
    init.add_argument("--project-id", default="default")
    init.add_argument("--name", default=None)

    status = sub.add_parser("status", help="Show registry status.")

    project = sub.add_parser("project", help="Project commands")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_create = project_sub.add_parser("create")
    project_create.add_argument("--project-id", required=True)
    project_create.add_argument("--name", default=None)
    project_create.add_argument("--root-path", default=".")
    project_create.add_argument("--default-view-contract", default=None)
    project_sub.add_parser("list")

    assets = sub.add_parser("assets", help="Asset registry commands")
    assets_sub = assets.add_subparsers(dest="assets_command", required=True)
    reg_manifest = assets_sub.add_parser("register-manifest")
    reg_manifest.add_argument("manifest")
    reg_manifest.add_argument("--project-id", required=True)
    list_assets = assets_sub.add_parser("list")
    list_assets.add_argument("--project-id", default=None)
    list_assets.add_argument("--limit", type=int, default=200)

    workflows = sub.add_parser("workflows", help="Workflow registry commands")
    workflows_sub = workflows.add_subparsers(dest="workflows_command", required=True)
    wf_register = workflows_sub.add_parser("register")
    wf_register.add_argument("metadata")
    wf_register.add_argument("--project-id", default=None)
    wf_list = workflows_sub.add_parser("list")
    wf_list.add_argument("--project-id", default=None)

    jobs = sub.add_parser("jobs", help="Job queue commands")
    jobs_sub = jobs.add_subparsers(dest="jobs_command", required=True)
    job_create = jobs_sub.add_parser("create")
    job_create.add_argument("--project-id", required=True)
    job_create.add_argument("--engine", required=True, choices=["noop", "shell", "comfyui", "sfb_bake_maps", "blender_capture"])
    job_create.add_argument("--workflow-id", default=None)
    job_create.add_argument("--asset-id", default=None)
    job_create.add_argument("--priority", type=int, default=50)
    job_create.add_argument("--max-attempts", type=int, default=3)
    job_create.add_argument("--params-json", default=None)
    job_create.add_argument("--param", action="append", default=[])
    job_create.add_argument("--status", default="queued")
    job_list = jobs_sub.add_parser("list")
    job_list.add_argument("--project-id", default=None)
    job_list.add_argument("--status", default=None)
    job_list.add_argument("--limit", type=int, default=200)
    job_show = jobs_sub.add_parser("show")
    job_show.add_argument("job_id")
    job_retry = jobs_sub.add_parser("retry")
    job_retry.add_argument("job_id")
    run_next = jobs_sub.add_parser("run-next")
    run_next.add_argument("--project-id", default=None)
    run_all = jobs_sub.add_parser("run-all")
    run_all.add_argument("--project-id", default=None)
    run_all.add_argument("--limit", type=int, default=100)
    from_capture = jobs_sub.add_parser("from-capture-plan", help="Create jobs from a capture plan JSONL.")
    from_capture.add_argument("capture_plan")
    from_capture.add_argument("--project-id", required=True)
    from_capture.add_argument("--workflow-id", default=None)
    from_capture.add_argument("--engine", default="blender_capture", choices=["noop", "shell", "blender_capture"])
    from_capture.add_argument("--view-contract", default=None, help="Path to ViewContract JSON for Blender. If omitted, jobs are only useful for noop/dry workflows.")
    from_capture.add_argument("--blender", default="blender")
    from_capture.add_argument("--script", default="tools/render_glb_turntable.py")
    from_capture.add_argument("--resolution", type=int, default=1024)
    from_capture.add_argument("--priority", type=int, default=50)

    artifacts = sub.add_parser("artifacts")
    artifacts_sub = artifacts.add_subparsers(dest="artifacts_command", required=True)
    art_list = artifacts_sub.add_parser("list")
    art_list.add_argument("--project-id", default=None)
    art_list.add_argument("--job-id", default=None)
    art_list.add_argument("--asset-id", default=None)
    art_list.add_argument("--limit", type=int, default=200)

    comfy = sub.add_parser("comfy")
    comfy_sub = comfy.add_subparsers(dest="comfy_command", required=True)
    comfy_status = comfy_sub.add_parser("status")
    comfy_status.add_argument("--url", default="http://127.0.0.1:8188")

    worker = sub.add_parser("worker", help="Run queued jobs.")
    worker.add_argument("--project-id", default=None)
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--poll-interval", type=float, default=2.0)
    worker.add_argument("--max-jobs", type=int, default=None)

    args = parser.parse_args(argv)

    if args.command == "init":
        ws = _workspace(args)
        store = OrchestratorStore(ws.db_path)
        project = store.create_project(args.project_id, name=args.name, root_path=ws.root)
        _print({"ok": True, "workspace": str(ws.root), "db": str(ws.db_path), "project": project.model_dump()})
        return 0

    if args.command == "status":
        ws = _workspace(args)
        store = OrchestratorStore(ws.db_path)
        _print({"ok": True, "workspace": str(ws.root), "db": str(ws.db_path), "projects": [p.model_dump() for p in store.list_projects()]})
        return 0

    store = _store(args)

    if args.command == "project":
        if args.project_command == "create":
            project = store.create_project(args.project_id, name=args.name, root_path=args.root_path, default_view_contract=args.default_view_contract)
            _print(project.model_dump())
            return 0
        if args.project_command == "list":
            _print({"projects": [p.model_dump() for p in store.list_projects()]})
            return 0

    if args.command == "assets":
        if args.assets_command == "register-manifest":
            count = store.register_manifest(args.project_id, args.manifest)
            _print({"ok": True, "registered_assets": count, "project_id": args.project_id})
            return 0
        if args.assets_command == "list":
            _print({"assets": [a.model_dump() for a in store.list_assets(args.project_id, limit=args.limit)]})
            return 0

    if args.command == "workflows":
        if args.workflows_command == "register":
            workflow = store.register_workflow_metadata(args.metadata, project_id=args.project_id)
            _print(workflow.model_dump())
            return 0
        if args.workflows_command == "list":
            _print({"workflows": [w.model_dump() for w in store.list_workflows(args.project_id)]})
            return 0

    if args.command == "jobs":
        if args.jobs_command == "create":
            params = _parse_params(args.param, args.params_json)
            if args.engine == "shell":
                params["command"] = _normalize_shell_command(params.get("command"))
            job = store.create_job(
                args.project_id,
                engine=args.engine,
                workflow_id=args.workflow_id,
                asset_id=args.asset_id,
                priority=args.priority,
                max_attempts=args.max_attempts,
                params=params,
                status=args.status,
            )
            _print(job.model_dump())
            return 0
        if args.jobs_command == "list":
            _print({"jobs": [j.model_dump() for j in store.list_jobs(args.project_id, args.status, limit=args.limit)]})
            return 0
        if args.jobs_command == "show":
            _print(store.get_job(args.job_id).model_dump())
            return 0
        if args.jobs_command == "retry":
            _print(store.retry_job(args.job_id).model_dump())
            return 0
        if args.jobs_command == "run-next":
            job = JobRunner(store, _workspace(args), worker_id=make_worker_id("cli_run_next")).run_next(args.project_id)
            _print({"job": None if job is None else job.model_dump()})
            return 0
        if args.jobs_command == "run-all":
            runner = JobRunner(store, _workspace(args), worker_id=make_worker_id("cli_run_all"))
            results = []
            for _ in range(args.limit):
                job = runner.run_next(args.project_id)
                if job is None:
                    break
                results.append(job.model_dump())
            _print({"ran": len(results), "jobs": results})
            return 0
        if args.jobs_command == "from-capture-plan":
            rows_by_asset: dict[str, list[dict[str, Any]]] = {}
            with Path(args.capture_plan).open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    rows_by_asset.setdefault(row["asset_id"], []).append(row)
            created = []
            for asset_id, rows in sorted(rows_by_asset.items()):
                first = rows[0]
                output_root = Path(first["output_dir"]).parent
                views = [row["view_id"] for row in rows]
                output_paths: list[str] = []
                for row in rows:
                    output_paths.extend(list(row.get("outputs", {}).values()))
                params = {
                    "input": first["source_path"],
                    "asset_id": asset_id,
                    "views": views,
                    "view_contract_id": first.get("view_contract"),
                    "view_contract": args.view_contract or first.get("view_contract"),
                    "out": str(output_root),
                    "blender": args.blender,
                    "script": args.script,
                    "resolution": args.resolution,
                    "capture_plan_entries": rows,
                    "output_paths": output_paths,
                }
                if args.engine == "shell":
                    params["command"] = _normalize_shell_command(params.get("command"))
                job = store.create_job(
                    args.project_id,
                    engine=args.engine,
                    workflow_id=args.workflow_id,
                    asset_id=asset_id,
                    priority=args.priority,
                    params=params,
                )
                created.append(job.model_dump())
            _print({"created": len(created), "jobs": created})
            return 0

    if args.command == "artifacts" and args.artifacts_command == "list":
        _print({"artifacts": [a.model_dump() for a in store.list_artifacts(args.project_id, job_id=args.job_id, asset_id=args.asset_id, limit=args.limit)]})
        return 0

    if args.command == "comfy" and args.comfy_command == "status":
        _print(ComfyClient(base_url=args.url).status())
        return 0

    if args.command == "worker":
        runner = JobRunner(store, _workspace(args), worker_id=make_worker_id("worker"))
        processed = 0
        while True:
            job = runner.run_next(args.project_id)
            if job is not None:
                processed += 1
                _print({"processed": processed, "job": job.model_dump()})
                if args.max_jobs is not None and processed >= args.max_jobs:
                    return 0
                continue
            if args.once:
                _print({"processed": processed, "idle": True})
                return 0
            time.sleep(args.poll_interval)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
