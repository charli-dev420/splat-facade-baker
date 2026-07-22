from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sfb_core.cli import main


def test_bake_splat_help_marks_command_experimental(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["bake-splat", "--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out.lower()
    assert "experimental" in help_text
    assert "non-mvp" in help_text


def test_bake_splat_returns_explicit_non_mvp_contract(tmp_path: Path, capsys) -> None:
    view_contract = Path(__file__).resolve().parents[3] / "examples" / "view_contracts" / "MV8_OBJECT.json"

    result = main([
        "bake-splat",
        "--input",
        str(tmp_path / "asset.ply"),
        "--view-contract",
        str(view_contract),
        "--view-id",
        "front",
        "--out",
        str(tmp_path / "out"),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert result == 3
    assert payload["status"] == "not_implemented"
    assert payload["experimental"] is True
    assert payload["mvp_contract"] == "excluded_pre_mvp"


def test_validate_sfb_package_reports_invalid_json(tmp_path: Path) -> None:
    package = tmp_path / "asset.sfb.json"
    package.write_text("{ broken json", encoding="utf-8")
    tool = Path(__file__).resolve().parents[3] / "tools" / "validate_sfb_package.py"

    result = subprocess.run(
        [sys.executable, str(tool), str(package)],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["status"] == "invalid_package_json"
    assert payload["errors"][0].startswith("invalid_package_json:")
