from __future__ import annotations

import argparse
import sqlite3
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
PYTHONPATH_ENTRIES = [
    ROOT / "packages" / "sfb_core" / "src",
    ROOT / "packages" / "sfb_dataset" / "src",
    ROOT / "packages" / "sfb_orchestrator" / "src",
    ROOT / "packages" / "sfb_training" / "src",
    ROOT / "packages" / "sfb_scene" / "src",
]


@dataclass
class GateRecord:
    name: str
    ok: bool
    status: str
    required: bool
    blocked: bool = False
    started_at: str = ""
    finished_at: str = ""
    duration_s: float = 0.0
    command: list[str] = field(default_factory=list)
    cwd: str = ""
    exit_code: int | None = None
    stdout_log: str | None = None
    stderr_log: str | None = None
    report_path: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_pythonpath(env: dict[str, str] | None = None) -> dict[str, str]:
    merged = dict(os.environ if env is None else env)
    existing = merged.get("PYTHONPATH")
    entries = [str(path) for path in PYTHONPATH_ENTRIES]
    merged["PYTHONPATH"] = os.pathsep.join(entries + ([existing] if existing else []))
    return merged


def git_safe_status_command(repo: Path = ROOT) -> list[str]:
    safe = str(repo).replace("\\", "/")
    return ["git", "-c", f"safe.directory={safe}", "status", "--short", "--branch"]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_command(
    name: str,
    command: Sequence[str],
    *,
    cwd: Path,
    logs_dir: Path,
    required: bool = True,
    env: dict[str, str] | None = None,
    timeout_s: float | None = None,
) -> GateRecord:
    started = utc_now()
    start = time.monotonic()
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
    stdout_log = logs_dir / f"{safe_name}.stdout.log"
    stderr_log = logs_dir / f"{safe_name}.stderr.log"
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    resolved_command = resolve_command(command)
    try:
        proc = subprocess.run(
            resolved_command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_s,
        )
        stdout_log.write_text(proc.stdout, encoding="utf-8", errors="replace")
        stderr_log.write_text(proc.stderr, encoding="utf-8", errors="replace")
        ok = proc.returncode == 0
        status = "passed" if ok else "failed"
        errors = [] if ok else [f"command_failed:{proc.returncode}"]
        exit_code: int | None = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout_log.write_text(exc.stdout or "", encoding="utf-8", errors="replace")
        stderr_log.write_text(exc.stderr or "", encoding="utf-8", errors="replace")
        ok = False
        status = "failed_timeout"
        errors = [f"command_timeout:{timeout_s}"]
        exit_code = None
    except FileNotFoundError as exc:
        stdout_log.write_text("", encoding="utf-8")
        stderr_log.write_text(str(exc), encoding="utf-8")
        ok = False
        status = "failed_missing_command"
        errors = [f"missing_command:{command[0]}"]
        exit_code = None
    finished = utc_now()
    return GateRecord(
        name=name,
        ok=ok,
        status=status,
        required=required,
        blocked=False,
        started_at=started,
        finished_at=finished,
        duration_s=round(time.monotonic() - start, 3),
        command=[str(part) for part in resolved_command],
        cwd=str(cwd),
        exit_code=exit_code,
        stdout_log=str(stdout_log),
        stderr_log=str(stderr_log),
        errors=errors,
    )


def resolve_command(command: Sequence[str]) -> list[str]:
    resolved = [str(part) for part in command]
    if not resolved:
        return resolved
    executable = resolved[0]
    candidates = [executable]
    if platform.system().lower().startswith("win"):
        if executable.lower() == "npm":
            candidates.insert(0, "npm.cmd")
        elif executable.lower() in {"powershell", "pwsh"}:
            candidates = ["pwsh.exe", "powershell.exe", executable]
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            resolved[0] = found
            break
    return resolved


def skipped_record(name: str, *, status: str, required: bool, warning: str | None = None) -> GateRecord:
    now = utc_now()
    return GateRecord(
        name=name,
        ok=True,
        status=status,
        required=required,
        blocked=False,
        started_at=now,
        finished_at=now,
        duration_s=0.0,
        warnings=[warning] if warning else [],
    )


def blocked_record(name: str, *, status: str, required: bool, error: str | None = None) -> GateRecord:
    now = utc_now()
    return GateRecord(
        name=name,
        ok=False,
        status=status,
        required=required,
        blocked=True,
        started_at=now,
        finished_at=now,
        duration_s=0.0,
        errors=[error] if error else [],
    )


def aggregate_status(records: list[GateRecord], *, fail_on_blocked: bool = False) -> str:
    if fail_on_blocked and any(record.blocked for record in records):
        return "blocked"
    for record in records:
        if record.required and not record.ok:
            return "failed"
        if not record.required and not record.ok and not record.blocked:
            return "failed"
    return "passed"


def verify_paths(name: str, paths: Sequence[Path], *, required: bool = True) -> GateRecord:
    started = utc_now()
    start = time.monotonic()
    missing = [str(path) for path in paths if not path.exists()]
    finished = utc_now()
    return GateRecord(
        name=name,
        ok=not missing,
        status="passed" if not missing else "failed_missing_artifacts",
        required=required,
        started_at=started,
        finished_at=finished,
        duration_s=round(time.monotonic() - start, 3),
        errors=[f"missing_artifact:{path}" for path in missing],
        artifacts=[str(path) for path in paths if path.exists()],
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _read_json_checked(path: Path, *, code: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{code}:{path}:{exc.msg} at line {exc.lineno} column {exc.colno}")
        return None
    except Exception as exc:
        errors.append(f"{code}:{path}:{type(exc).__name__}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{code}:{path}:JSON root must be an object")
        return None
    return data


def run_real_workspace_smoke(workspace: Path) -> GateRecord:
    started = utc_now()
    start = time.monotonic()
    errors: list[str] = []
    warnings: list[str] = []
    artifacts: list[str] = []
    valid_packages = 0
    valid_scenes = 0

    package_paths = sorted((workspace / "exports").glob("**/asset.sfb.json")) if (workspace / "exports").exists() else []
    for package_path in package_paths:
        package = _read_json_checked(package_path, code="invalid_package_json", errors=errors)
        if package is None:
            continue
        artifacts.append(str(package_path))
        valid_packages += 1
        report_path = package_path.parent / "reports" / f"{package.get('asset_id') or package.get('name') or package_path.parent.name}_report.json"
        if not report_path.exists():
            reports = sorted((package_path.parent / "reports").glob("*_report.json")) if (package_path.parent / "reports").exists() else []
            report_path = reports[0] if reports else report_path
        if report_path.exists():
            if _read_json_checked(report_path, code="invalid_report_json", errors=errors) is not None:
                artifacts.append(str(report_path))

    scene_paths = sorted((workspace / "scenes").glob("**/*.sfbscene.json")) if (workspace / "scenes").exists() else []
    for scene_path in scene_paths:
        scene = _read_json_checked(scene_path, code="invalid_scene_json", errors=errors)
        if scene is None:
            continue
        if scene.get("schema") != "sfb.scene.v1":
            warnings.append(f"ignored_non_sfb_scene:{scene_path}")
            continue
        valid_scenes += 1
        artifacts.append(str(scene_path))
        for card in scene.get("cards", []) if isinstance(scene.get("cards"), list) else []:
            if not isinstance(card, dict) or not card.get("asset_package"):
                continue
            raw = Path(str(card["asset_package"]))
            package_ref = raw if raw.is_absolute() else (scene_path.parent / raw).resolve()
            if not package_ref.exists():
                errors.append(f"missing_scene_package:{scene_path}:{card.get('scene_card_id')}:{card['asset_package']}")
            elif _read_json_checked(package_ref, code="invalid_scene_package_json", errors=errors) is not None:
                artifacts.append(str(package_ref))

    db_path = workspace / "orchestrator" / "sfb_orchestrator.sqlite3"
    if db_path.exists():
        try:
            with sqlite3.connect(db_path) as conn:
                for row in conn.execute("SELECT path FROM artifacts").fetchall():
                    artifact_path = Path(str(row[0]))
                    resolved = artifact_path if artifact_path.is_absolute() else (workspace / artifact_path).resolve()
                    if not resolved.exists():
                        errors.append(f"missing_registered_artifact:{row[0]}")
        except Exception as exc:
            errors.append(f"invalid_orchestrator_registry:{db_path}:{type(exc).__name__}: {exc}")

    if errors:
        ok = False
        status = "failed_real_workspace_invalid"
        blocked = False
    elif valid_packages == 0 and valid_scenes == 0:
        ok = False
        status = "blocked_real_workspace_empty"
        blocked = True
        warnings.append(f"empty_workspace:{workspace}")
    else:
        ok = True
        status = "passed"
        blocked = False
    return GateRecord(
        name="real_workspace_smoke",
        ok=ok,
        status=status,
        required=False,
        blocked=blocked,
        started_at=started,
        finished_at=utc_now(),
        duration_s=round(time.monotonic() - start, 3),
        errors=errors,
        warnings=warnings,
        artifacts=artifacts,
    )


def _update_from_json_summary(record: GateRecord, report_path: Path) -> GateRecord:
    data = _read_json(report_path)
    record.report_path = str(report_path)
    record.artifacts.append(str(report_path))
    if data is None:
        return record
    status = data.get("status") or data.get("live")
    if isinstance(status, str):
        record.status = status
        record.blocked = status.startswith("blocked")
    if isinstance(data.get("ok"), bool):
        record.ok = bool(data["ok"])
    if isinstance(data.get("blocked"), bool):
        record.blocked = bool(data["blocked"])
    errors = data.get("errors")
    if isinstance(errors, list):
        record.errors.extend(str(error) for error in errors)
    warnings = data.get("warnings")
    if isinstance(warnings, list):
        record.warnings.extend(str(warning) for warning in warnings)
    artifacts = data.get("artifacts")
    if isinstance(artifacts, list):
        record.artifacts.extend(str(artifact) for artifact in artifacts if isinstance(artifact, str))
    return record


def run_comfy_gate(args: argparse.Namespace, *, logs_dir: Path, env: dict[str, str]) -> GateRecord:
    report_path = Path(args.workspace) / "comfyui_demo_gate_report.json"
    command = [
        sys.executable,
        str(ROOT / "tools" / "comfyui_demo_gate.py"),
        "--workspace",
        str(Path(args.workspace) / "comfyui_demo_gate"),
        "--comfy-url",
        args.comfy_url,
        "--report",
        str(report_path),
    ]
    record = run_command("comfyui_demo_gate", command, cwd=ROOT, logs_dir=logs_dir, required=False, env=env)
    report = _read_json(report_path)
    record.report_path = str(report_path)
    if report_path.exists():
        record.artifacts.append(str(report_path))
    if report:
        live = report.get("live", {})
        live_status = live.get("status") if isinstance(live, dict) else None
        dry_run = report.get("dry_run", {})
        dry_status = dry_run.get("status") if isinstance(dry_run, dict) else None
        if dry_status != "completed":
            record.ok = False
            record.status = "failed_comfyui_dry_run"
            record.errors.append(f"comfyui_dry_run_status:{dry_status}")
        elif args.include_comfy_live and isinstance(live_status, str) and live_status.startswith("blocked"):
            record.ok = False
            record.blocked = True
            record.status = live_status
        elif isinstance(live_status, str) and live_status.startswith("blocked"):
            record.warnings.append(live_status)
    return record


def run_blender_gate(args: argparse.Namespace, *, logs_dir: Path, env: dict[str, str]) -> GateRecord:
    if not args.include_blender:
        return skipped_record(
            "blender_capture_gate",
            status="skipped_blender_not_requested",
            required=False,
            warning="Run with --include-blender to execute the Blender capture gate.",
        )

    report_path = Path(args.workspace) / "blender_capture_gate_report.json"
    out_dir = Path(args.workspace) / "blender_gate"
    command = [
        sys.executable,
        str(ROOT / "tools" / "blender_capture_gate.py"),
        "--blender-exe",
        args.blender_exe,
        "--input",
        args.blender_input,
        "--views",
        args.blender_views,
        "--resolution",
        str(args.blender_resolution),
        "--out",
        str(out_dir),
        "--report",
        str(report_path),
    ]
    record = run_command("blender_capture_gate", command, cwd=ROOT, logs_dir=logs_dir, required=False, env=env)
    report = _read_json(report_path)
    record.report_path = str(report_path)
    if report_path.exists():
        record.artifacts.append(str(report_path))
    if not report:
        record.ok = False
        record.status = "failed_blender_gate_report_missing"
        record.errors.append(f"missing_or_invalid_report:{report_path}")
        return record

    status = report.get("status")
    if isinstance(status, str):
        record.status = status
        record.blocked = status.startswith("blocked")
        record.ok = status == "passed"
    errors = report.get("errors")
    if isinstance(errors, list):
        record.errors.extend(str(error) for error in errors)
    warnings = report.get("warnings")
    if isinstance(warnings, list):
        record.warnings.extend(str(warning) for warning in warnings)
    outputs = report.get("outputs")
    if isinstance(outputs, list):
        for output in outputs:
            if isinstance(output, dict):
                for value in output.values():
                    if isinstance(value, str):
                        record.artifacts.append(value)
    log = report.get("log")
    if isinstance(log, dict):
        for value in log.values():
            if isinstance(value, str):
                record.artifacts.append(value)
    return record


def run_unity_gate(args: argparse.Namespace, *, logs_dir: Path) -> GateRecord:
    if not args.include_unity:
        return skipped_record(
            "unity_import_smoke",
            status="skipped_unity_not_requested",
            required=False,
            warning="Run with --include-unity to execute the Unity smoke gate.",
        )
    report_path = Path(args.workspace) / "unity_smoke_report.json"
    command = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ROOT / "tools" / "unity_import_smoke.ps1"),
        "-UnityExe",
        str(args.unity_exe),
        "-ProjectPath",
        str(Path(args.workspace) / "unity_smoke"),
        "-ReportPath",
        str(report_path),
        "-Clean",
    ]
    record = run_command("unity_import_smoke", command, cwd=ROOT, logs_dir=logs_dir, required=False)
    if report_path.exists():
        record = _update_from_json_summary(record, report_path)
    if "unity_license_unavailable" in record.status or "unity_project_creation_failed" in record.status:
        record.blocked = True
    return record


def build_report(
    *,
    run_id: str,
    workspace: Path,
    report_dir: Path,
    records: list[GateRecord],
    fail_on_blocked: bool,
) -> dict[str, Any]:
    status = aggregate_status(records, fail_on_blocked=fail_on_blocked)
    return {
        "schema": "sfb.validation_report.v1",
        "run_id": run_id,
        "ok": status == "passed",
        "status": status,
        "repo": str(ROOT),
        "workspace": str(workspace),
        "report_dir": str(report_dir),
        "python": sys.version,
        "platform": platform.platform(),
        "git_safe_directory_command": f"git config --global --add safe.directory {str(ROOT).replace(chr(92), '/')}",
        "gates": [record.to_json() for record in records],
    }


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace)
    report_dir = workspace.parent / "validation_reports"
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    logs_dir = report_dir / "logs" / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    env = repo_pythonpath()

    records: list[GateRecord] = []
    records.append(run_command("git_status", git_safe_status_command(ROOT), cwd=ROOT, logs_dir=logs_dir, env=env))
    records.append(run_command("python_pytest", [sys.executable, "-m", "pytest"], cwd=ROOT, logs_dir=logs_dir, env=env))
    records.append(run_command("studio_smoke", ["npm", "run", "test:smoke"], cwd=ROOT / "apps" / "sfb_studio", logs_dir=logs_dir, env=env))
    records.append(run_command("studio_build", ["npm", "run", "build"], cwd=ROOT / "apps" / "sfb_studio", logs_dir=logs_dir, env=env))

    synthetic_dir = workspace / "synthetic"
    export_dir = workspace / "exports" / "DemoWall"
    scene_report = workspace / "scene_reports" / "demo_lane_report.json"
    records.append(run_command(
        "synthetic_maps",
        [sys.executable, str(ROOT / "tools" / "make_synthetic_maps.py"), "--out", str(synthetic_dir)],
        cwd=ROOT,
        logs_dir=logs_dir,
        env=env,
    ))
    records.append(run_command(
        "bake_maps",
        [
            sys.executable,
            "-m",
            "sfb_core.cli",
            "bake-maps",
            "--albedo",
            str(synthetic_dir / "albedo.png"),
            "--alpha",
            str(synthetic_dir / "alpha.png"),
            "--depth",
            str(synthetic_dir / "depth.png"),
            "--name",
            "DemoWall",
            "--view-contract",
            str(ROOT / "examples" / "view_contracts" / "MV8_OBJECT.json"),
            "--view-id",
            "front",
            "--out",
            str(export_dir),
        ],
        cwd=ROOT,
        logs_dir=logs_dir,
        env=env,
    ))
    package_path = export_dir / "asset.sfb.json"
    records.append(run_command(
        "validate_sfb_package",
        [sys.executable, str(ROOT / "tools" / "validate_sfb_package.py"), str(package_path)],
        cwd=ROOT,
        logs_dir=logs_dir,
        env=env,
    ))
    records.append(verify_paths(
        "verify_mvp_package_artifacts",
        [
            package_path,
            export_dir / "reports" / "DemoWall_report.json",
            export_dir / "mesh" / "DemoWall_LOD0.sfbmesh.json",
            export_dir / "mesh" / "DemoWall_LOD1.sfbmesh.json",
            export_dir / "mesh" / "DemoWall_LOD2.sfbmesh.json",
            export_dir / "textures" / "DemoWall_Albedo.png",
            export_dir / "textures" / "DemoWall_Alpha.png",
            export_dir / "textures" / "DemoWall_Depth.png",
            export_dir / "collision" / "collider_proxy.json",
            export_dir / "preview" / "DemoWall_preview.png",
        ],
    ))
    records.append(run_command(
        "scene_validate",
        [
            sys.executable,
            "-m",
            "sfb_scene.cli",
            "validate",
            str(ROOT / "examples" / "scenes" / "demo_lane.sfbscene.json"),
            "--out",
            str(scene_report),
        ],
        cwd=ROOT,
        logs_dir=logs_dir,
        env=env,
    ))
    if scene_report.exists():
        records[-1].report_path = str(scene_report)
        records[-1].artifacts.append(str(scene_report))

    records.append(run_comfy_gate(args, logs_dir=logs_dir, env=env))
    if args.real_workspace_smoke:
        records.append(run_real_workspace_smoke(workspace.parent))
    if args.skip_slow:
        records.append(skipped_record("blender_capture_gate", status="skipped_slow", required=False))
        records.append(skipped_record("unity_import_smoke", status="skipped_slow", required=False))
    else:
        records.append(run_blender_gate(args, logs_dir=logs_dir, env=env))
        records.append(run_unity_gate(args, logs_dir=logs_dir))

    report = build_report(
        run_id=run_id,
        workspace=workspace,
        report_dir=report_dir,
        records=records,
        fail_on_blocked=args.fail_on_blocked,
    )
    timestamped = report_dir / f"{run_id}.json"
    latest = report_dir / "latest.json"
    write_json(timestamped, report)
    write_json(latest, report)
    report["report_path"] = str(timestamped)
    report["latest_report_path"] = str(latest)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SFB complete validation pipeline.")
    parser.add_argument("--workspace", default="workspace/validation")
    parser.add_argument("--skip-slow", action="store_true")
    parser.add_argument("--include-blender", action="store_true")
    parser.add_argument("--include-unity", action="store_true")
    parser.add_argument("--include-comfy-live", action="store_true")
    parser.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    parser.add_argument("--blender-exe", default="blender")
    parser.add_argument(
        "--blender-input",
        default=str(ROOT / "examples" / "sfb_packages" / "DemoWall" / "mesh" / "DemoWall_LOD0.glb"),
    )
    parser.add_argument("--blender-views", default="front")
    parser.add_argument("--blender-resolution", type=int, default=256)
    parser.add_argument("--unity-exe", default=r"C:\Program Files\Unity\Hub\Editor\6000.3.18f1\Editor\Unity.exe")
    parser.add_argument("--fail-on-blocked", action="store_true")
    parser.add_argument("--real-workspace-smoke", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_pipeline(args)
    print(json.dumps({
        "ok": report["ok"],
        "status": report["status"],
        "report": report["report_path"],
        "latest": report["latest_report_path"],
    }, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
