from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from sfb_orchestrator.comfy.client import ComfyClient
from sfb_orchestrator.db.store import OrchestratorStore
from sfb_orchestrator.jobs.runner import JobRunner
from sfb_orchestrator.paths import SFBWorkspace


class HealthResponse(BaseModel):
    ok: bool
    service: str
    workspace: str
    version: str = "0.2.8-pre"


class CreateProjectRequest(BaseModel):
    project_id: str
    name: str | None = None
    root_path: str = "."
    default_view_contract: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegisterManifestRequest(BaseModel):
    project_id: str
    manifest_path: str


class RegisterWorkflowRequest(BaseModel):
    metadata_path: str
    project_id: str | None = None


class CreateJobRequest(BaseModel):
    project_id: str
    engine: str
    workflow_id: str | None = None
    asset_id: str | None = None
    priority: int = 50
    params: dict[str, Any] = Field(default_factory=dict)
    status: str = "queued"


class AssetReviewRequest(BaseModel):
    quality_status: str | None = None
    data_tier: str | None = None
    category: str | None = None
    style_family: str | None = None
    metadata_patch: dict[str, Any] = Field(default_factory=dict)


class UpdateJobStatusRequest(BaseModel):
    status: str
    error_type: str | None = None
    error_message: str | None = None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.exists() and path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _resolve_path(workspace: SFBWorkspace, raw: str | Path) -> Path:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p
    return (workspace.root / p).resolve()


def _job_log_dir(workspace: SFBWorkspace, project_id: str, job_id: str) -> Path:
    return workspace.logs_dir / project_id / job_id


def _scan_bakes(store: OrchestratorStore, workspace: SFBWorkspace, project_id: str | None, limit: int) -> list[dict[str, Any]]:
    records = store.list_artifacts(project_id, limit=1000)
    candidates: list[Path] = []
    for artifact in records:
        p = _resolve_path(workspace, artifact.path)
        if p.name == "asset.sfb.json":
            candidates.append(p)
        if p.suffix.lower() == ".json" and p.exists():
            data = _read_json(p)
            if data and str(data.get("schema", "")).startswith("sfb.asset"):
                candidates.append(p)
    exports_root = workspace.root / "exports"
    if exports_root.exists():
        candidates.extend(exports_root.glob("**/asset.sfb.json"))

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        asset = _read_json(path) or {}
        report_path = path.parent / "reports" / f"{asset.get('asset_id') or asset.get('name') or path.parent.name}_report.json"
        if not report_path.exists():
            reports = sorted((path.parent / "reports").glob("*_report.json")) if (path.parent / "reports").exists() else []
            report_path = reports[0] if reports else report_path
        report = _read_json(report_path) or {}
        metrics = report.get("metrics", {}) if isinstance(report.get("metrics"), dict) else {}
        out.append(
            {
                "asset_id": asset.get("asset_id") or path.parent.name,
                "source_asset_id": asset.get("source_asset_id"),
                "view_id": asset.get("view_id"),
                "mode": asset.get("mode") or asset.get("bake_mode"),
                "path": str(path),
                "package_dir": str(path.parent),
                "report_path": str(report_path) if report_path.exists() else None,
                "status": report.get("status") or asset.get("status") or "unreviewed",
                "metrics": metrics,
                "warnings": report.get("warnings", []),
                "mobile": asset.get("runtime", {}),
            }
        )
    return out[:limit]




def _scan_scenes(workspace: SFBWorkspace, limit: int = 200) -> list[dict[str, Any]]:
    roots = [workspace.root / "scenes", workspace.root / "examples" / "scenes"]
    candidates: list[Path] = []
    for root in roots:
        if root.exists():
            candidates.extend(root.glob("**/*.sfbscene.json"))
            candidates.extend(root.glob("**/*.scene.json"))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(candidates):
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        data = _read_json(path) or {}
        if data.get("schema") != "sfb.scene.v1":
            continue
        cards = data.get("cards", []) if isinstance(data.get("cards"), list) else []
        chunks = data.get("chunks", []) if isinstance(data.get("chunks"), list) else []
        out.append({
            "scene_id": data.get("scene_id") or path.stem,
            "path": str(path),
            "units": data.get("units", "meters"),
            "target": data.get("target", {}),
            "cards_total": len(cards),
            "chunks_total": len(chunks),
            "status": data.get("status") or "unreviewed",
            "view_contracts": data.get("view_contracts", []),
        })
    return out[:limit]


def _validate_scene_json(workspace: SFBWorkspace, scene_path: str) -> dict[str, Any]:
    path = _resolve_path(workspace, scene_path)
    data = _read_json(path)
    if not data or data.get("schema") != "sfb.scene.v1":
        raise ValueError("not an SFB scene file")
    cards = data.get("cards", []) if isinstance(data.get("cards"), list) else []
    chunks = data.get("chunks", []) if isinstance(data.get("chunks"), list) else []
    warnings: list[str] = []
    errors: list[str] = []
    chunk_ids = {c.get("chunk_id") for c in chunks if isinstance(c, dict)}
    missing_packages = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        package = card.get("asset_package")
        if package:
            p = Path(str(package))
            if not p.is_absolute():
                p = (path.parent / p).resolve()
            if not p.exists():
                missing_packages += 1
                errors.append(f"missing_package:{card.get('scene_card_id')}:{package}")
        if card.get("chunk_id") and card.get("chunk_id") not in chunk_ids:
            warnings.append(f"card_references_missing_chunk:{card.get('scene_card_id')}:{card.get('chunk_id')}")
    status = "failed" if errors else ("needs_review" if warnings else "ok")
    return {
        "schema": "sfb.scene_report.v1",
        "scene_id": data.get("scene_id"),
        "status": status,
        "metrics": {
            "cards_total": len(cards),
            "chunks_total": len(chunks),
            "missing_packages": missing_packages,
        },
        "warnings": warnings,
        "errors": errors,
    }


def _training_runs(workspace: SFBWorkspace, runs_root: str | None = None) -> list[dict[str, Any]]:
    root = _resolve_path(workspace, runs_root or "runs")
    if not root.exists():
        return []
    runs: list[dict[str, Any]] = []
    for run_json in sorted(root.glob("*/run.json")):
        data = _read_json(run_json)
        if data:
            data.setdefault("run_dir", str(run_json.parent))
            runs.append(data)
    return runs


def _model_registry(workspace: SFBWorkspace, runs_root: str | None = None) -> dict[str, Any]:
    root = _resolve_path(workspace, runs_root or "runs")
    data = _read_json(root / "model_registry.json")
    return data or {"schema": "sfb.model_registry.v1", "aliases": {}, "models": []}


def create_app(workspace_root: str | Path | None = None) -> FastAPI:
    workspace = SFBWorkspace.from_env(workspace_root)
    workspace.ensure()
    store = OrchestratorStore(workspace.db_path)
    runner = JobRunner(store, workspace)

    app = FastAPI(title="SFB Local Orchestrator", version="0.2.8-pre")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.workspace = workspace
    app.state.store = store
    app.state.runner = runner

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(ok=True, service="sfb-orchestrator", workspace=str(workspace.root))

    @app.get("/api/summary")
    def summary(project_id: str | None = None) -> dict:
        projects = store.list_projects()
        jobs = store.job_counts(project_id)
        assets = store.asset_counts(project_id)
        artifacts = store.artifact_counts(project_id)
        bakes = _scan_bakes(store, workspace, project_id, limit=250)
        scenes = _scan_scenes(workspace, limit=250)
        runs = _training_runs(workspace)
        review = {
            "assets_needs_review": assets["by_quality_status"].get("needs_review", 0) + assets["by_quality_status"].get("unreviewed", 0),
            "jobs_failed": jobs["by_status"].get("failed", 0),
            "jobs_needs_review": jobs["by_status"].get("needs_review", 0),
            "bakes_needs_review": len([b for b in bakes if b.get("status") in {"needs_review", "unreviewed"}]),
        }
        return {
            "projects": [p.model_dump() for p in projects],
            "active_project_id": project_id or (projects[0].project_id if projects else None),
            "assets": assets,
            "jobs": jobs,
            "artifacts": artifacts,
            "bakes": {"total": len(bakes)},
            "scenes": {"total": len(scenes)},
            "training": {"runs_total": len(runs), "running": len([r for r in runs if r.get("status") == "running"])},
            "review": review,
            "workspace": str(workspace.root),
        }

    @app.post("/api/projects")
    def create_project(req: CreateProjectRequest) -> dict:
        project = store.create_project(
            req.project_id,
            name=req.name,
            root_path=req.root_path,
            default_view_contract=req.default_view_contract,
            metadata=req.metadata,
        )
        return project.model_dump()

    @app.get("/api/projects")
    def list_projects() -> dict:
        return {"projects": [p.model_dump() for p in store.list_projects()]}

    @app.post("/api/assets/register-manifest")
    def register_manifest(req: RegisterManifestRequest) -> dict:
        try:
            count = store.register_manifest(req.project_id, req.manifest_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "registered_assets": count, "project_id": req.project_id}

    @app.get("/api/assets")
    def list_assets(project_id: str | None = None, limit: int = Query(200, le=1000), offset: int = 0) -> dict:
        return {"assets": [a.model_dump() for a in store.list_assets(project_id, limit=limit, offset=offset)]}

    @app.patch("/api/assets/{project_id}/{asset_id}/review")
    def update_asset_review(project_id: str, asset_id: str, req: AssetReviewRequest) -> dict:
        try:
            return store.update_asset_review(
                project_id,
                asset_id,
                quality_status=req.quality_status,
                data_tier=req.data_tier,
                category=req.category,
                style_family=req.style_family,
                metadata_patch=req.metadata_patch,
            ).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/workflows/register")
    def register_workflow(req: RegisterWorkflowRequest) -> dict:
        try:
            workflow = store.register_workflow_metadata(req.metadata_path, project_id=req.project_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return workflow.model_dump()

    @app.get("/api/workflows")
    def list_workflows(project_id: str | None = None) -> dict:
        return {"workflows": [w.model_dump() for w in store.list_workflows(project_id)]}

    @app.post("/api/jobs")
    def create_job(req: CreateJobRequest) -> dict:
        try:
            job = store.create_job(
                req.project_id,
                engine=req.engine,
                workflow_id=req.workflow_id,
                asset_id=req.asset_id,
                priority=req.priority,
                params=req.params,
                status=req.status,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return job.model_dump()

    @app.get("/api/jobs")
    def list_jobs(project_id: str | None = None, status: str | None = None, limit: int = Query(200, le=1000), offset: int = 0) -> dict:
        return {"jobs": [j.model_dump() for j in store.list_jobs(project_id, status, limit=limit, offset=offset)]}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        try:
            return store.get_job(job_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/api/jobs/{job_id}/status")
    def update_job_status(job_id: str, req: UpdateJobStatusRequest) -> dict:
        try:
            return store.update_job_status(job_id, req.status, error_type=req.error_type, error_message=req.error_message).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/retry")
    def retry_job(job_id: str) -> dict:
        try:
            return store.retry_job(job_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict:
        try:
            return store.update_job_status(job_id, "cancelled").model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/approve")
    def approve_job(job_id: str) -> dict:
        try:
            return store.update_job_status(job_id, "approved").model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/reject")
    def reject_job(job_id: str) -> dict:
        try:
            return store.update_job_status(job_id, "rejected").model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}/logs")
    def list_job_logs(job_id: str) -> dict:
        try:
            job = store.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_dir = _job_log_dir(workspace, job.project_id, job.job_id)
        files = []
        if log_dir.exists():
            files = [{"name": p.name, "path": str(p), "size": p.stat().st_size} for p in sorted(log_dir.glob("*")) if p.is_file()]
        return {"job_id": job_id, "log_dir": str(log_dir), "files": files}

    @app.get("/api/jobs/{job_id}/logs/{filename}")
    def get_job_log(job_id: str, filename: str) -> PlainTextResponse:
        try:
            job = store.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        path = _job_log_dir(workspace, job.project_id, job.job_id) / filename
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="log file not found")
        return PlainTextResponse(path.read_text(encoding="utf-8", errors="replace"))

    @app.post("/api/jobs/run-next")
    def run_next(project_id: str | None = None) -> dict:
        job = runner.run_next(project_id)
        return {"job": None if job is None else job.model_dump()}

    @app.post("/api/jobs/run-all")
    def run_all(project_id: str | None = None, limit: int = Query(25, le=500)) -> dict:
        results = []
        for _ in range(limit):
            job = runner.run_next(project_id)
            if job is None:
                break
            results.append(job.model_dump())
        return {"ran": len(results), "jobs": results}

    @app.get("/api/artifacts")
    def list_artifacts(project_id: str | None = None, job_id: str | None = None, asset_id: str | None = None, limit: int = Query(200, le=1000), offset: int = 0) -> dict:
        return {"artifacts": [a.model_dump() for a in store.list_artifacts(project_id, job_id=job_id, asset_id=asset_id, limit=limit, offset=offset)]}

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str) -> dict:
        try:
            return store.get_artifact(artifact_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/bakes")
    def list_bakes(project_id: str | None = None, limit: int = Query(200, le=1000)) -> dict:
        return {"bakes": _scan_bakes(store, workspace, project_id, limit=limit)}

    @app.get("/api/scenes")
    def list_scenes(limit: int = Query(200, le=1000)) -> dict:
        return {"scenes": _scan_scenes(workspace, limit=limit)}

    @app.get("/api/scenes/validate")
    def validate_scene(path: str) -> dict:
        try:
            return _validate_scene_json(workspace, path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/training/runs")
    def list_training_runs(runs_root: str | None = None) -> dict:
        return {"runs": _training_runs(workspace, runs_root)}

    @app.get("/api/training/model-registry")
    def get_model_registry(runs_root: str | None = None) -> dict:
        return _model_registry(workspace, runs_root)

    @app.get("/api/review-queue")
    def review_queue(project_id: str | None = None, limit: int = Query(100, le=500)) -> dict:
        assets = [
            a.model_dump()
            for a in store.list_assets(project_id, limit=limit)
            if a.quality_status in {"unreviewed", "needs_review"}
        ]
        jobs = [
            j.model_dump()
            for status in ["failed", "needs_review"]
            for j in store.list_jobs(project_id, status=status, limit=limit)
        ][:limit]
        bakes = [b for b in _scan_bakes(store, workspace, project_id, limit=limit) if b.get("status") in {"needs_review", "unreviewed"}]
        return {"assets": assets, "jobs": jobs, "bakes": bakes}

    @app.get("/api/file")
    def get_file(path: str) -> FileResponse:
        p = _resolve_path(workspace, path)
        if not p.exists() or not p.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(p)

    @app.get("/api/comfy/status")
    def comfy_status(url: str = "http://127.0.0.1:8188") -> dict:
        return ComfyClient(base_url=url).status()

    @app.get("/api/settings")
    def settings() -> dict:
        return {
            "workspace": str(workspace.root),
            "db_path": str(workspace.db_path),
            "logs_dir": str(workspace.logs_dir),
            "artifacts_dir": str(workspace.artifacts_dir),
            "workflows_dir": str(workspace.workflows_dir),
            "api_version": "0.2.8-pre",
        }

    return app


app = create_app()


def main() -> None:
    uvicorn.run("sfb_orchestrator.api.main:app", host="127.0.0.1", port=8765, reload=True)


if __name__ == "__main__":
    main()
