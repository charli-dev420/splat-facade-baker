from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "tools" / "run_validation_pipeline.py"
SPEC = importlib.util.spec_from_file_location("run_validation_pipeline", MODULE_PATH)
assert SPEC and SPEC.loader
validation_pipeline = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validation_pipeline
SPEC.loader.exec_module(validation_pipeline)


def test_gate_record_normalizes_timestamps_and_duration() -> None:
    record = validation_pipeline.skipped_record("unit", status="skipped", required=False)

    payload = record.to_json()

    assert payload["name"] == "unit"
    assert payload["ok"] is True
    assert payload["status"] == "skipped"
    assert payload["started_at"]
    assert payload["finished_at"]
    assert payload["duration_s"] == 0.0
    assert payload["command"] == []


def test_run_command_captures_success_and_failure_logs(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    success = validation_pipeline.run_command(
        "success",
        [sys.executable, "-c", "print('hello')"],
        cwd=tmp_path,
        logs_dir=logs,
    )
    failure = validation_pipeline.run_command(
        "failure",
        [sys.executable, "-c", "import sys; print('bad'); sys.exit(3)"],
        cwd=tmp_path,
        logs_dir=logs,
    )

    assert success.ok is True
    assert success.status == "passed"
    assert Path(success.stdout_log).read_text(encoding="utf-8").strip() == "hello"
    assert failure.ok is False
    assert failure.status == "failed"
    assert failure.exit_code == 3
    assert "command_failed:3" in failure.errors
    assert Path(failure.stdout_log).read_text(encoding="utf-8").strip() == "bad"


def test_aggregate_status_rules() -> None:
    passed = validation_pipeline.skipped_record("ok", status="passed", required=True)
    optional_blocked = validation_pipeline.blocked_record("blocked", status="blocked_tool_missing", required=False)
    required_failed = validation_pipeline.blocked_record("required", status="blocked_required", required=True)
    optional_failed = validation_pipeline.GateRecord(
        name="optional_failed",
        ok=False,
        status="failed",
        required=False,
        started_at="start",
        finished_at="end",
    )

    assert validation_pipeline.aggregate_status([passed, optional_blocked]) == "passed"
    assert validation_pipeline.aggregate_status([passed, optional_blocked], fail_on_blocked=True) == "blocked"
    assert validation_pipeline.aggregate_status([required_failed]) == "failed"
    assert validation_pipeline.aggregate_status([passed, optional_failed]) == "failed"


def test_git_safe_status_command_uses_local_config() -> None:
    command = validation_pipeline.git_safe_status_command(Path("D:/Repo/Example"))

    assert command[:3] == ["git", "-c", "safe.directory=D:/Repo/Example"]
    assert command[-3:] == ["status", "--short", "--branch"]


def test_skip_slow_records_exclude_external_live_gates() -> None:
    blender = validation_pipeline.skipped_record("blender_capture_gate", status="skipped_slow", required=False)
    comfy = validation_pipeline.skipped_record("comfyui_demo_gate", status="skipped_slow", required=False)
    unity = validation_pipeline.skipped_record("unity_import_smoke", status="skipped_slow", required=False)

    assert blender.ok is True
    assert blender.required is False
    assert blender.blocked is False
    assert comfy.ok is True
    assert comfy.required is False
    assert comfy.blocked is False
    assert unity.ok is True
    assert unity.required is False
    assert unity.blocked is False


def test_build_report_writes_common_shape(tmp_path: Path) -> None:
    record = validation_pipeline.skipped_record("unit", status="passed", required=True)

    report = validation_pipeline.build_report(
        run_id="20260101-010101",
        workspace=tmp_path / "workspace",
        report_dir=tmp_path / "reports",
        records=[record],
        fail_on_blocked=False,
    )

    assert report["schema"] == "sfb.validation_report.v1"
    assert report["ok"] is True
    assert report["status"] == "passed"
    assert report["gates"][0]["name"] == "unit"
    assert "git config --global --add safe.directory" in report["git_safe_directory_command"]


def test_cli_fake_command_smoke(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    record = validation_pipeline.run_command(
        "fake_cli",
        [sys.executable, "-c", "import json; print(json.dumps({'ok': True}))"],
        cwd=tmp_path,
        logs_dir=logs,
        required=True,
    )

    payload = json.loads(Path(record.stdout_log).read_text(encoding="utf-8"))
    assert record.ok is True
    assert payload == {"ok": True}


def test_real_workspace_smoke_passes_with_valid_package_and_scene(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    package_dir = workspace / "exports" / "Demo"
    report_dir = package_dir / "reports"
    scene_dir = workspace / "scenes"
    report_dir.mkdir(parents=True)
    scene_dir.mkdir(parents=True)
    package_path = package_dir / "asset.sfb.json"
    package_path.write_text(json.dumps({"schema": "sfb.asset.v1", "asset_id": "Demo"}), encoding="utf-8")
    (report_dir / "Demo_report.json").write_text(json.dumps({"status": "ok", "metrics": {}}), encoding="utf-8")
    (scene_dir / "demo.sfbscene.json").write_text(
        json.dumps({
            "schema": "sfb.scene.v1",
            "scene_id": "demo",
            "cards": [{"scene_card_id": "card", "asset_package": "../exports/Demo/asset.sfb.json"}],
        }),
        encoding="utf-8",
    )

    record = validation_pipeline.run_real_workspace_smoke(workspace)

    assert record.ok is True
    assert record.status == "passed"
    assert str(package_path) in record.artifacts


def test_real_workspace_smoke_blocks_empty_workspace(tmp_path: Path) -> None:
    record = validation_pipeline.run_real_workspace_smoke(tmp_path / "workspace")

    assert record.ok is False
    assert record.blocked is True
    assert record.status == "blocked_real_workspace_empty"


def test_real_workspace_smoke_fails_invalid_package_report_and_missing_scene_ref(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    package_dir = workspace / "exports" / "Broken"
    report_dir = package_dir / "reports"
    scene_dir = workspace / "scenes"
    report_dir.mkdir(parents=True)
    scene_dir.mkdir(parents=True)
    (package_dir / "asset.sfb.json").write_text(json.dumps({"schema": "sfb.asset.v1", "asset_id": "Broken"}), encoding="utf-8")
    (report_dir / "Broken_report.json").write_text("{ broken report", encoding="utf-8")
    (scene_dir / "bad.sfbscene.json").write_text(
        json.dumps({
            "schema": "sfb.scene.v1",
            "scene_id": "bad",
            "cards": [{"scene_card_id": "missing", "asset_package": "../exports/Missing/asset.sfb.json"}],
        }),
        encoding="utf-8",
    )

    record = validation_pipeline.run_real_workspace_smoke(workspace)

    assert record.ok is False
    assert record.status == "failed_real_workspace_invalid"
    assert any(error.startswith("invalid_report_json:") for error in record.errors)
    assert any(error.startswith("missing_scene_package:") for error in record.errors)


def test_real_workspace_blocked_aggregate_respects_fail_on_blocked(tmp_path: Path) -> None:
    record = validation_pipeline.run_real_workspace_smoke(tmp_path / "workspace")

    assert validation_pipeline.aggregate_status([record]) == "passed"
    assert validation_pipeline.aggregate_status([record], fail_on_blocked=True) == "blocked"
