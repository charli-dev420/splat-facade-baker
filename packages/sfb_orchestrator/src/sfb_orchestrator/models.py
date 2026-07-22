from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

JobStatus = Literal[
    "created",
    "queued",
    "running",
    "cancelling",
    "collecting_outputs",
    "completed",
    "failed",
    "cancelled",
    "skipped",
    "needs_review",
    "approved",
    "rejected",
]

EngineName = Literal["noop", "shell", "comfyui", "sfb_bake_maps", "blender_capture"]


class ProjectRecord(BaseModel):
    project_id: str
    name: str
    root_path: str
    default_view_contract: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class AssetRecord(BaseModel):
    project_id: str
    asset_id: str
    source_path: str | None = None
    source_hash: str | None = None
    data_tier: str = "candidate"
    quality_status: str = "unreviewed"
    category: str = "uncategorized"
    style_family: str = "unknown"
    manifest_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class WorkflowRecord(BaseModel):
    workflow_id: str
    project_id: str | None = None
    engine: str
    version: str = "0.1.0"
    template_path: str | None = None
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class JobRecord(BaseModel):
    job_id: str
    project_id: str
    engine: str
    workflow_id: str | None = None
    asset_id: str | None = None
    status: str = "created"
    priority: int = 50
    params: dict[str, Any] = Field(default_factory=dict)
    recipe_hash: str | None = None
    attempt: int = 0
    max_attempts: int = 3
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    heartbeat_at: str | None = None
    cancel_requested_at: str | None = None
    cancel_reason: str | None = None
    worker_id: str | None = None
    process_id: int | None = None


class ArtifactRecord(BaseModel):
    artifact_id: str
    project_id: str
    job_id: str | None = None
    asset_id: str | None = None
    artifact_type: str
    path: str
    hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
