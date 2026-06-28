from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SFBWorkspace:
    root: Path

    @classmethod
    def from_env(cls, root: str | Path | None = None) -> "SFBWorkspace":
        value = root if root is not None else os.environ.get("SFB_WORKSPACE", "workspace")
        return cls(Path(value).expanduser().resolve())

    @property
    def db_path(self) -> Path:
        return self.root / "orchestrator" / "sfb_orchestrator.sqlite3"

    @property
    def logs_dir(self) -> Path:
        return self.root / "orchestrator" / "logs"

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    @property
    def workflows_dir(self) -> Path:
        return self.root / "workflows"

    def ensure(self) -> None:
        for path in [self.root, self.db_path.parent, self.logs_dir, self.artifacts_dir, self.workflows_dir]:
            path.mkdir(parents=True, exist_ok=True)
