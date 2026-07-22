from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable

from ..models import ArtifactRecord, AssetRecord, JobRecord, ProjectRecord, WorkflowRecord
from ..utils import recipe_hash, sha256_file, utc_now_iso


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  root_path TEXT NOT NULL,
  default_view_contract TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
  project_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  source_path TEXT,
  source_hash TEXT,
  data_tier TEXT NOT NULL DEFAULT 'candidate',
  quality_status TEXT NOT NULL DEFAULT 'unreviewed',
  category TEXT NOT NULL DEFAULT 'uncategorized',
  style_family TEXT NOT NULL DEFAULT 'unknown',
  manifest_id TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (project_id, asset_id),
  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);
CREATE TABLE IF NOT EXISTS workflows (
  workflow_id TEXT NOT NULL,
  project_id TEXT,
  engine TEXT NOT NULL,
  version TEXT NOT NULL DEFAULT '0.1.0',
  template_path TEXT,
  description TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (project_id, workflow_id)
);
CREATE TABLE IF NOT EXISTS jobs (
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
  error_message TEXT,
  heartbeat_at TEXT,
  cancel_requested_at TEXT,
  cancel_reason TEXT,
  worker_id TEXT,
  process_id INTEGER,
  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON jobs(status, priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_jobs_project_status ON jobs(project_id, status);
CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  job_id TEXT,
  asset_id TEXT,
  artifact_type TEXT NOT NULL,
  path TEXT NOT NULL,
  hash TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_artifacts_job ON artifacts(job_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_asset ON artifacts(project_id, asset_id);
"""


def _json(data: dict[str, Any] | None) -> str:
    return json.dumps(data or {}, ensure_ascii=False, sort_keys=True)


def _loads(data: str | None) -> dict[str, Any]:
    if not data:
        return {}
    return json.loads(data)


class OrchestratorStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate_jobs_lifecycle(conn)

    def _migrate_jobs_lifecycle(self, conn: sqlite3.Connection) -> None:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        columns = {
            "heartbeat_at": "TEXT",
            "cancel_requested_at": "TEXT",
            "cancel_reason": "TEXT",
            "worker_id": "TEXT",
            "process_id": "INTEGER",
        }
        for name, sql_type in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {sql_type}")

    def create_project(
        self,
        project_id: str,
        *,
        name: str | None = None,
        root_path: str | Path | None = None,
        default_view_contract: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectRecord:
        now = utc_now_iso()
        record = ProjectRecord(
            project_id=project_id,
            name=name or project_id,
            root_path=str(root_path or "."),
            default_view_contract=default_view_contract,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO projects(project_id, name, root_path, default_view_contract, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                  name=excluded.name,
                  root_path=excluded.root_path,
                  default_view_contract=excluded.default_view_contract,
                  metadata_json=excluded.metadata_json,
                  updated_at=excluded.updated_at
                """,
                (record.project_id, record.name, record.root_path, record.default_view_contract, _json(record.metadata), now, now),
            )
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> ProjectRecord:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if row is None:
            raise KeyError(f"project not found: {project_id}")
        return ProjectRecord(
            project_id=row["project_id"],
            name=row["name"],
            root_path=row["root_path"],
            default_view_contract=row["default_view_contract"],
            metadata=_loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_projects(self) -> list[ProjectRecord]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY created_at ASC").fetchall()
        return [self._project_from_row(r) for r in rows]

    def _project_from_row(self, row: sqlite3.Row) -> ProjectRecord:
        return ProjectRecord(
            project_id=row["project_id"], name=row["name"], root_path=row["root_path"],
            default_view_contract=row["default_view_contract"], metadata=_loads(row["metadata_json"]),
            created_at=row["created_at"], updated_at=row["updated_at"]
        )

    def upsert_asset(self, asset: AssetRecord) -> AssetRecord:
        now = utc_now_iso()
        created_at = asset.created_at or now
        metadata = dict(asset.metadata)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO assets(project_id, asset_id, source_path, source_hash, data_tier, quality_status, category, style_family, manifest_id, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, asset_id) DO UPDATE SET
                  source_path=excluded.source_path,
                  source_hash=excluded.source_hash,
                  data_tier=excluded.data_tier,
                  quality_status=excluded.quality_status,
                  category=excluded.category,
                  style_family=excluded.style_family,
                  manifest_id=excluded.manifest_id,
                  metadata_json=excluded.metadata_json,
                  updated_at=excluded.updated_at
                """,
                (
                    asset.project_id,
                    asset.asset_id,
                    asset.source_path,
                    asset.source_hash,
                    asset.data_tier,
                    asset.quality_status,
                    asset.category,
                    asset.style_family,
                    asset.manifest_id,
                    _json(metadata),
                    created_at,
                    now,
                ),
            )
        return self.get_asset(asset.project_id, asset.asset_id)

    def get_asset(self, project_id: str, asset_id: str) -> AssetRecord:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM assets WHERE project_id=? AND asset_id=?", (project_id, asset_id)).fetchone()
        if row is None:
            raise KeyError(f"asset not found: {project_id}/{asset_id}")
        return self._asset_from_row(row)

    def list_assets(self, project_id: str | None = None, *, limit: int = 500, offset: int = 0) -> list[AssetRecord]:
        with self.connect() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM assets WHERE project_id=? ORDER BY asset_id LIMIT ? OFFSET ?",
                    (project_id, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM assets ORDER BY project_id, asset_id LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [self._asset_from_row(r) for r in rows]

    def update_asset_review(
        self,
        project_id: str,
        asset_id: str,
        *,
        quality_status: str | None = None,
        data_tier: str | None = None,
        category: str | None = None,
        style_family: str | None = None,
        metadata_patch: dict[str, Any] | None = None,
    ) -> AssetRecord:
        asset = self.get_asset(project_id, asset_id)
        metadata = dict(asset.metadata)
        if metadata_patch:
            metadata.update(metadata_patch)
        updated = asset.model_copy(
            update={
                "quality_status": quality_status or asset.quality_status,
                "data_tier": data_tier or asset.data_tier,
                "category": category or asset.category,
                "style_family": style_family or asset.style_family,
                "metadata": metadata,
            }
        )
        return self.upsert_asset(updated)

    def asset_counts(self, project_id: str | None = None) -> dict[str, Any]:
        clause = " WHERE project_id=?" if project_id else ""
        values: list[Any] = [project_id] if project_id else []
        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) AS c FROM assets{clause}", values).fetchone()["c"]
            by_quality = {
                row["quality_status"]: row["c"]
                for row in conn.execute(
                    f"SELECT quality_status, COUNT(*) AS c FROM assets{clause} GROUP BY quality_status",
                    values,
                ).fetchall()
            }
            by_tier = {
                row["data_tier"]: row["c"]
                for row in conn.execute(
                    f"SELECT data_tier, COUNT(*) AS c FROM assets{clause} GROUP BY data_tier",
                    values,
                ).fetchall()
            }
        return {"total": total, "by_quality_status": by_quality, "by_data_tier": by_tier}

    def _asset_from_row(self, row: sqlite3.Row) -> AssetRecord:
        return AssetRecord(
            project_id=row["project_id"],
            asset_id=row["asset_id"],
            source_path=row["source_path"],
            source_hash=row["source_hash"],
            data_tier=row["data_tier"],
            quality_status=row["quality_status"],
            category=row["category"],
            style_family=row["style_family"],
            manifest_id=row["manifest_id"],
            metadata=_loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def register_manifest(self, project_id: str, manifest_path: str | Path) -> int:
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        dataset_id = data.get("dataset_id") or Path(manifest_path).stem
        count = 0
        for item in data.get("assets", []):
            metadata = {
                "dataset_id": dataset_id,
                "manifest_path": str(manifest_path),
                "views": item.get("views", {}),
                "tags": item.get("tags", []),
                "base_caption": item.get("base_caption", ""),
                "split": item.get("split"),
            }
            self.upsert_asset(
                AssetRecord(
                    project_id=project_id,
                    asset_id=item["asset_id"],
                    source_path=item.get("source_path"),
                    source_hash=item.get("source_hash"),
                    data_tier=item.get("data_tier", "candidate"),
                    quality_status=item.get("quality_status", "unreviewed"),
                    category=item.get("category", "uncategorized"),
                    style_family=item.get("style_family", "unknown"),
                    manifest_id=dataset_id,
                    metadata=metadata,
                )
            )
            count += 1
        return count

    def upsert_workflow(self, workflow: WorkflowRecord) -> WorkflowRecord:
        now = utc_now_iso()
        project_id = workflow.project_id or "__global__"
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO workflows(workflow_id, project_id, engine, version, template_path, description, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, workflow_id) DO UPDATE SET
                  engine=excluded.engine,
                  version=excluded.version,
                  template_path=excluded.template_path,
                  description=excluded.description,
                  metadata_json=excluded.metadata_json,
                  updated_at=excluded.updated_at
                """,
                (
                    workflow.workflow_id,
                    project_id,
                    workflow.engine,
                    workflow.version,
                    workflow.template_path,
                    workflow.description,
                    _json(workflow.metadata),
                    workflow.created_at or now,
                    now,
                ),
            )
        return self.get_workflow(workflow.workflow_id, workflow.project_id)

    def register_workflow_metadata(self, metadata_path: str | Path, *, project_id: str | None = None) -> WorkflowRecord:
        data = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
        workflow = WorkflowRecord(
            workflow_id=data["workflow_id"],
            project_id=project_id or data.get("project_id"),
            engine=data.get("engine", "comfyui"),
            version=data.get("version", "0.1.0"),
            template_path=data.get("template_file") or data.get("template_path"),
            description=data.get("description", ""),
            metadata={**data, "metadata_path": str(metadata_path)},
        )
        return self.upsert_workflow(workflow)

    def get_workflow(self, workflow_id: str, project_id: str | None = None) -> WorkflowRecord:
        key = project_id or "__global__"
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM workflows WHERE project_id=? AND workflow_id=?", (key, workflow_id)).fetchone()
            if row is None and project_id is not None:
                row = conn.execute("SELECT * FROM workflows WHERE project_id='__global__' AND workflow_id=?", (workflow_id,)).fetchone()
        if row is None:
            raise KeyError(f"workflow not found: {workflow_id}")
        return self._workflow_from_row(row)

    def list_workflows(self, project_id: str | None = None) -> list[WorkflowRecord]:
        with self.connect() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM workflows WHERE project_id IN (?, '__global__') ORDER BY workflow_id", (project_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM workflows ORDER BY project_id, workflow_id").fetchall()
        return [self._workflow_from_row(r) for r in rows]

    def _workflow_from_row(self, row: sqlite3.Row) -> WorkflowRecord:
        pid = row["project_id"]
        return WorkflowRecord(
            workflow_id=row["workflow_id"],
            project_id=None if pid == "__global__" else pid,
            engine=row["engine"],
            version=row["version"],
            template_path=row["template_path"],
            description=row["description"],
            metadata=_loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create_job(
        self,
        project_id: str,
        *,
        engine: str,
        workflow_id: str | None = None,
        asset_id: str | None = None,
        params: dict[str, Any] | None = None,
        priority: int = 50,
        status: str = "queued",
        max_attempts: int = 3,
        job_id: str | None = None,
    ) -> JobRecord:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        now = utc_now_iso()
        params = params or {}
        r_hash = recipe_hash(project_id, engine, workflow_id, asset_id, params)
        job_id = job_id or f"job_{uuid.uuid4().hex[:16]}"
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs(job_id, project_id, engine, workflow_id, asset_id, status, priority, params_json, recipe_hash, attempt, max_attempts, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (job_id, project_id, engine, workflow_id, asset_id, status, priority, _json(params), r_hash, max_attempts, now),
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> JobRecord:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"job not found: {job_id}")
        return self._job_from_row(row)

    def list_jobs(self, project_id: str | None = None, status: str | None = None, *, limit: int = 500, offset: int = 0) -> list[JobRecord]:
        sql = "SELECT * FROM jobs"
        clauses: list[str] = []
        values: list[Any] = []
        if project_id:
            clauses.append("project_id=?")
            values.append(project_id)
        if status:
            clauses.append("status=?")
            values.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        values.extend([limit, offset])
        with self.connect() as conn:
            rows = conn.execute(sql, values).fetchall()
        return [self._job_from_row(r) for r in rows]

    def job_counts(self, project_id: str | None = None) -> dict[str, Any]:
        clause = " WHERE project_id=?" if project_id else ""
        values: list[Any] = [project_id] if project_id else []
        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) AS c FROM jobs{clause}", values).fetchone()["c"]
            by_status = {
                row["status"]: row["c"]
                for row in conn.execute(
                    f"SELECT status, COUNT(*) AS c FROM jobs{clause} GROUP BY status",
                    values,
                ).fetchall()
            }
        return {"total": total, "by_status": by_status}

    def claim_next_job(self, project_id: str | None = None, *, worker_id: str | None = None) -> JobRecord | None:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if project_id:
                row = conn.execute(
                    """
                    SELECT * FROM jobs
                    WHERE status='queued' AND attempt < max_attempts AND project_id=?
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    """,
                    (project_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM jobs
                    WHERE status='queued' AND attempt < max_attempts
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    """
                ).fetchone()
            if row is None:
                return None
            job_id = row["job_id"]
            cur = conn.execute(
                """
                UPDATE jobs
                SET status='running',
                    started_at=?,
                    heartbeat_at=?,
                    finished_at=NULL,
                    attempt=attempt+1,
                    error_type=NULL,
                    error_message=NULL,
                    cancel_requested_at=NULL,
                    cancel_reason=NULL,
                    worker_id=?,
                    process_id=NULL
                WHERE job_id=? AND status='queued' AND attempt < max_attempts
                """,
                (now, now, worker_id, job_id),
            )
            if cur.rowcount != 1:
                return None
            updated = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return self._job_from_row(updated)

    def heartbeat_job(self, job_id: str) -> JobRecord:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute("UPDATE jobs SET heartbeat_at=? WHERE job_id=?", (now, job_id))
        return self.get_job(job_id)

    def set_job_process(self, job_id: str, process_id: int | None) -> JobRecord:
        with self.connect() as conn:
            conn.execute("UPDATE jobs SET process_id=? WHERE job_id=?", (process_id, job_id))
        return self.get_job(job_id)

    def is_cancel_requested(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        return job.status == "cancelling" or job.cancel_requested_at is not None

    def request_cancel_job(self, job_id: str, *, reason: str | None = None) -> JobRecord:
        job = self.get_job(job_id)
        now = utc_now_iso()
        if job.status in {"created", "queued"}:
            with self.connect() as conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status='cancelled',
                        finished_at=?,
                        cancel_requested_at=?,
                        cancel_reason=?,
                        process_id=NULL,
                        error_type='CancelledError',
                        error_message=?
                    WHERE job_id=?
                    """,
                    (now, now, reason, reason or "cancelled before start", job_id),
                )
            return self.get_job(job_id)
        if job.status in {"running", "collecting_outputs"}:
            with self.connect() as conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status='cancelling',
                        cancel_requested_at=?,
                        cancel_reason=?,
                        error_type='CancelledError',
                        error_message=?
                    WHERE job_id=?
                    """,
                    (now, reason, reason or "cancel requested", job_id),
                )
            return self.get_job(job_id)
        raise ValueError(f"job cannot be cancelled from status: {job.status}")

    def update_job_status(
        self,
        job_id: str,
        status: str,
        *,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> JobRecord:
        finished = utc_now_iso() if status in {"completed", "failed", "cancelled", "skipped", "needs_review"} else None
        with self.connect() as conn:
            if finished:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status=?,
                        finished_at=?,
                        heartbeat_at=?,
                        process_id=NULL,
                        error_type=?,
                        error_message=?
                    WHERE job_id=?
                    """,
                    (status, finished, finished, error_type, error_message, job_id),
                )
            else:
                conn.execute(
                    "UPDATE jobs SET status=?, error_type=?, error_message=? WHERE job_id=?",
                    (status, error_type, error_message, job_id),
                )
        return self.get_job(job_id)

    def requeue_failed_attempt(
        self,
        job_id: str,
        *,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> JobRecord:
        now = utc_now_iso()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status='queued',
                    started_at=NULL,
                    finished_at=?,
                    heartbeat_at=NULL,
                    process_id=NULL,
                    error_type=?,
                    error_message=?
                WHERE job_id=?
                """,
                (now, error_type, error_message, job_id),
            )
        return self.get_job(job_id)

    def retry_job(self, job_id: str) -> JobRecord:
        job = self.get_job(job_id)
        if job.status not in {"failed", "cancelled", "skipped", "needs_review", "rejected"}:
            raise ValueError(f"job cannot be retried from status: {job.status}")
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status='queued',
                    attempt=0,
                    started_at=NULL,
                    finished_at=NULL,
                    heartbeat_at=NULL,
                    cancel_requested_at=NULL,
                    cancel_reason=NULL,
                    worker_id=NULL,
                    process_id=NULL,
                    error_type=NULL,
                    error_message=NULL
                WHERE job_id=?
                """,
                (job_id,),
            )
        return self.get_job(job_id)

    def _job_from_row(self, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            project_id=row["project_id"],
            engine=row["engine"],
            workflow_id=row["workflow_id"],
            asset_id=row["asset_id"],
            status=row["status"],
            priority=row["priority"],
            params=_loads(row["params_json"]),
            recipe_hash=row["recipe_hash"],
            attempt=row["attempt"],
            max_attempts=row["max_attempts"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            error_type=row["error_type"],
            error_message=row["error_message"],
            heartbeat_at=row["heartbeat_at"],
            cancel_requested_at=row["cancel_requested_at"],
            cancel_reason=row["cancel_reason"],
            worker_id=row["worker_id"],
            process_id=row["process_id"],
        )

    def register_artifact(
        self,
        project_id: str,
        *,
        artifact_type: str,
        path: str | Path,
        job_id: str | None = None,
        asset_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        compute_hash: bool = True,
    ) -> ArtifactRecord:
        now = utc_now_iso()
        p = Path(path)
        digest = sha256_file(p) if compute_hash and p.exists() and p.is_file() else None
        artifact_id: str
        with self.connect() as conn:
            existing = conn.execute(
                """
                SELECT artifact_id FROM artifacts
                WHERE project_id=? AND job_id IS ? AND artifact_type=? AND path=?
                """,
                (project_id, job_id, artifact_type, str(path)),
            ).fetchone()
            if existing is not None:
                conn.execute(
                    """
                    UPDATE artifacts
                    SET asset_id=?, hash=?, metadata_json=?, created_at=?
                    WHERE artifact_id=?
                    """,
                    (asset_id, digest, _json(metadata), now, existing["artifact_id"]),
                )
                artifact_id = existing["artifact_id"]
            else:
                artifact_id = f"artifact_{uuid.uuid4().hex[:16]}"
                conn.execute(
                    """
                    INSERT INTO artifacts(artifact_id, project_id, job_id, asset_id, artifact_type, path, hash, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (artifact_id, project_id, job_id, asset_id, artifact_type, str(path), digest, _json(metadata), now),
                )
        return self.get_artifact(artifact_id)

    def get_artifact(self, artifact_id: str) -> ArtifactRecord:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
        if row is None:
            raise KeyError(f"artifact not found: {artifact_id}")
        return self._artifact_from_row(row)

    def list_artifacts(
        self,
        project_id: str | None = None,
        *,
        job_id: str | None = None,
        asset_id: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[ArtifactRecord]:
        sql = "SELECT * FROM artifacts"
        clauses: list[str] = []
        values: list[Any] = []
        if project_id:
            clauses.append("project_id=?")
            values.append(project_id)
        if job_id:
            clauses.append("job_id=?")
            values.append(job_id)
        if asset_id:
            clauses.append("asset_id=?")
            values.append(asset_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        values.extend([limit, offset])
        with self.connect() as conn:
            rows = conn.execute(sql, values).fetchall()
        return [self._artifact_from_row(r) for r in rows]

    def artifact_counts(self, project_id: str | None = None) -> dict[str, Any]:
        clause = " WHERE project_id=?" if project_id else ""
        values: list[Any] = [project_id] if project_id else []
        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) AS c FROM artifacts{clause}", values).fetchone()["c"]
            by_type = {
                row["artifact_type"]: row["c"]
                for row in conn.execute(
                    f"SELECT artifact_type, COUNT(*) AS c FROM artifacts{clause} GROUP BY artifact_type",
                    values,
                ).fetchall()
            }
        return {"total": total, "by_type": by_type}

    def _artifact_from_row(self, row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=row["artifact_id"],
            project_id=row["project_id"],
            job_id=row["job_id"],
            asset_id=row["asset_id"],
            artifact_type=row["artifact_type"],
            path=row["path"],
            hash=row["hash"],
            metadata=_loads(row["metadata_json"]),
            created_at=row["created_at"],
        )
