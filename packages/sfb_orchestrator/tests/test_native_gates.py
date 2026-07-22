from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


blender_gate = _load_module("blender_capture_gate", ROOT / "tools" / "blender_capture_gate.py")
validation_pipeline = _load_module("run_validation_pipeline_p6", ROOT / "tools" / "run_validation_pipeline.py")


def _write_png(path: Path, size: tuple[int, int] = (64, 64)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (255, 0, 0, 255)).save(path)


def _write_camera(path: Path, *, asset_id: str = "DemoWall_LOD0", view_id: str = "front") -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "sfb.camera.v1",
                "asset_id": asset_id,
                "view_id": view_id,
                "camera_type": "orthographic",
                "ortho_scale": 4.0,
                "camera_location": [0.0, -4.0, 1.0],
                "camera_rotation_euler": [1.0, 0.0, 0.0],
                "bbox": {"bbox_min": [0, 0, 0], "bbox_max": [1, 1, 1]},
            }
        ),
        encoding="utf-8",
    )


def _write_complete_blender_view(out_dir: Path, view_id: str = "front") -> None:
    view = out_dir / view_id
    _write_png(view / "rgb.png")
    _write_png(view / "alpha.png")
    _write_png(view / "normal.png")
    (view / "depth.exr").write_bytes(b"exr")
    _write_camera(view / "camera.json", view_id=view_id)


def test_blender_gate_missing_executable_returns_blocked(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    args = blender_gate.parse_args(
        [
            "--blender-exe",
            str(tmp_path / "missing-blender.exe"),
            "--out",
            str(tmp_path / "out"),
            "--report",
            str(report_path),
        ]
    )

    report = blender_gate.run_gate(args)

    assert report["ok"] is False
    assert report["blocked"] is True
    assert report["status"] == "blocked_blender_executable_missing"
    assert json.loads(report_path.read_text(encoding="utf-8"))["status"] == "blocked_blender_executable_missing"


def test_blender_gate_passes_absolute_paths_to_blender(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.chdir(tmp_path)
    blender = tmp_path / "bin" / "blender.exe"
    blender.parent.mkdir(parents=True)
    blender.write_text("", encoding="utf-8")
    source = tmp_path / "assets" / "asset.glb"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"glb")
    contract = tmp_path / "contracts" / "MV8_OBJECT.json"
    contract.parent.mkdir(parents=True)
    contract.write_text(json.dumps({"views": [{"view_id": "front"}]}), encoding="utf-8")
    captured: dict[str, Any] = {}

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command: list[str], **kwargs: Any) -> Completed:
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        out = Path(command[command.index("--out") + 1])
        _write_complete_blender_view(out)
        return Completed()

    monkeypatch.setattr(blender_gate.subprocess, "run", fake_run)

    report = blender_gate.run_gate(
        blender_gate.parse_args(
            [
                "--blender-exe",
                str(blender),
                "--input",
                str(Path("assets") / "asset.glb"),
                "--asset-id",
                "DemoWall_LOD0",
                "--view-contract",
                str(Path("contracts") / "MV8_OBJECT.json"),
                "--out",
                str(Path("workspace") / "renders" / "asset"),
                "--report",
                str(Path("workspace") / "report.json"),
                "--resolution",
                "64",
            ]
        )
    )

    command = captured["command"]
    assert Path(command[command.index("--input") + 1]).is_absolute()
    assert Path(command[command.index("--view-contract") + 1]).is_absolute()
    assert Path(command[command.index("--out") + 1]).is_absolute()
    assert report["ok"] is True


def test_blender_output_validation_accepts_complete_view(tmp_path: Path) -> None:
    _write_complete_blender_view(tmp_path)

    report = blender_gate.validate_blender_outputs(
        out_dir=tmp_path,
        asset_id="DemoWall_LOD0",
        views=["front"],
        resolution=64,
    )

    assert report["ok"] is True
    assert report["status"] == "passed"
    assert report["errors"] == []


def test_blender_output_validation_rejects_missing_outputs(tmp_path: Path) -> None:
    view = tmp_path / "front"
    _write_png(view / "rgb.png")
    _write_png(view / "normal.png")
    (view / "depth.exr").write_bytes(b"exr")
    _write_camera(view / "camera.json")

    report = blender_gate.validate_blender_outputs(
        out_dir=tmp_path,
        asset_id="DemoWall_LOD0",
        views=["front"],
        resolution=64,
    )

    assert report["ok"] is False
    assert report["status"] == "failed_missing_blender_outputs"
    assert any("alpha.png" in error for error in report["errors"])


def test_blender_output_validation_rejects_corrupt_camera_json(tmp_path: Path) -> None:
    view = tmp_path / "front"
    _write_png(view / "rgb.png")
    _write_png(view / "alpha.png")
    _write_png(view / "normal.png")
    (view / "depth.exr").write_bytes(b"exr")
    (view / "camera.json").write_text("{broken", encoding="utf-8")

    report = blender_gate.validate_blender_outputs(
        out_dir=tmp_path,
        asset_id="DemoWall_LOD0",
        views=["front"],
        resolution=64,
    )

    assert report["ok"] is False
    assert report["status"] == "failed_invalid_camera_json"
    assert any(error.startswith("invalid_camera_json:") for error in report["errors"])


def test_run_blender_gate_maps_report_status_and_command(tmp_path: Path, monkeypatch: Any) -> None:
    args = validation_pipeline.parse_args(
        [
            "--workspace",
            str(tmp_path / "workspace"),
            "--include-blender",
            "--blender-exe",
            "missing-blender",
        ]
    )
    captured: dict[str, Any] = {}

    def fake_run_command(name: str, command: list[str], **kwargs: Any) -> Any:
        captured["name"] = name
        captured["command"] = command
        report_path = Path(args.workspace) / "blender_capture_gate_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "ok": False,
                    "status": "blocked_blender_executable_missing",
                    "blocked": True,
                    "errors": ["blender_executable_missing:missing-blender"],
                    "warnings": [],
                    "outputs": [],
                    "log": {},
                }
            ),
            encoding="utf-8",
        )
        return validation_pipeline.GateRecord(
            name=name,
            ok=True,
            status="passed",
            required=False,
            started_at="start",
            finished_at="end",
            command=command,
        )

    monkeypatch.setattr(validation_pipeline, "run_command", fake_run_command)

    record = validation_pipeline.run_blender_gate(args, logs_dir=tmp_path / "logs", env={})

    assert captured["name"] == "blender_capture_gate"
    assert str(ROOT / "tools" / "blender_capture_gate.py") in captured["command"]
    assert "--blender-exe" in captured["command"]
    assert record.status == "blocked_blender_executable_missing"
    assert record.blocked is True
    assert validation_pipeline.aggregate_status([record]) == "passed"
    assert validation_pipeline.aggregate_status([record], fail_on_blocked=True) == "blocked"


def test_run_unity_gate_maps_blocked_and_failed_reports(tmp_path: Path, monkeypatch: Any) -> None:
    args = validation_pipeline.parse_args(
        [
            "--workspace",
            str(tmp_path / "workspace"),
            "--include-unity",
            "--unity-exe",
            str(tmp_path / "missing-unity.exe"),
        ]
    )
    statuses = iter(["blocked_unity_license_unavailable", "failed_unity_import_smoke"])

    def fake_run_command(name: str, command: list[str], **kwargs: Any) -> Any:
        status = next(statuses)
        report_path = Path(command[command.index("-ReportPath") + 1])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "ok": False,
                    "status": status,
                    "blocked": status.startswith("blocked"),
                    "errors": [status],
                    "warnings": [],
                    "artifacts": [],
                }
            ),
            encoding="utf-8",
        )
        return validation_pipeline.GateRecord(
            name=name,
            ok=False,
            status="failed",
            required=False,
            started_at="start",
            finished_at="end",
            command=command,
        )

    monkeypatch.setattr(validation_pipeline, "run_command", fake_run_command)

    blocked = validation_pipeline.run_unity_gate(args, logs_dir=tmp_path / "logs")
    failed = validation_pipeline.run_unity_gate(args, logs_dir=tmp_path / "logs")

    assert blocked.status == "blocked_unity_license_unavailable"
    assert blocked.blocked is True
    assert validation_pipeline.aggregate_status([blocked]) == "passed"
    assert failed.status == "failed_unity_import_smoke"
    assert failed.blocked is False
    assert validation_pipeline.aggregate_status([failed]) == "failed"


def test_unity_script_contains_certifying_assertions() -> None:
    script = (ROOT / "tools" / "unity_import_smoke.ps1").read_text(encoding="utf-8")

    assert "blocked_unity_executable_missing" in script
    assert "SFBAssetMetadata" in script
    assert "LODGroup" in script
    assert "SFBSceneMetadata" in script
    assert "cardCount == 2" in script
    assert "chunkCount == 1" in script
    assert "BoxCollider" in script
