from __future__ import annotations

import pytest

from sfb_orchestrator.cli import main
from sfb_orchestrator.db.store import OrchestratorStore


def test_cli_jobs_create_persists_max_attempts(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    assert main(["--workspace", str(workspace), "init", "--project-id", "p"]) == 0

    result = main(
        [
            "--workspace",
            str(workspace),
            "jobs",
            "create",
            "--project-id",
            "p",
            "--engine",
            "noop",
            "--max-attempts",
            "2",
        ]
    )

    assert result == 0
    jobs = OrchestratorStore(workspace / "orchestrator" / "sfb_orchestrator.sqlite3").list_jobs("p")
    assert len(jobs) == 1
    assert jobs[0].max_attempts == 2


def test_cli_jobs_create_rejects_invalid_max_attempts(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    assert main(["--workspace", str(workspace), "init", "--project-id", "p"]) == 0

    with pytest.raises(ValueError):
        main(
            [
                "--workspace",
                str(workspace),
                "jobs",
                "create",
                "--project-id",
                "p",
                "--engine",
                "noop",
                "--max-attempts",
                "0",
            ]
        )
