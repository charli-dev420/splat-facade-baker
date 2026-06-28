from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field


class TrainingRun(BaseModel):
    schema: str = "sfb.training_run.v1"
    run_id: str
    task: str
    backend: str
    base_model: str | None = None
    dataset_export_id: str
    dataset_hash: str | None = None
    config_hash: str | None = None
    status: str = "created"
    checkpoints: list[dict] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")
