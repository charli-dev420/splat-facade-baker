from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

try:
    from PIL import Image
except Exception:  # pragma: no cover - dependency is present in normal dev envs
    Image = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "examples" / "sfb_packages" / "DemoWall" / "mesh" / "DemoWall_LOD0.glb"
DEFAULT_VIEW_CONTRACT = ROOT / "examples" / "view_contracts" / "MV8_OBJECT.json"
DEFAULT_OUT = ROOT / "workspace" / "blender_gate"
REQUIRED_CAMERA_KEYS = {
    "schema",
    "asset_id",
    "view_id",
    "camera_type",
    "ortho_scale",
    "camera_location",
    "camera_rotation_euler",
    "bbox",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_views(raw: str | Sequence[str]) -> list[str]:
    if isinstance(raw, str):
        parts = raw.split(",")
    else:
        parts = raw
    return [part.strip() for part in parts if part and part.strip()]


def resolve_executable(executable: str) -> str | None:
    path = Path(executable)
    if path.exists():
        return str(path)
    found = shutil.which(executable)
    return found


def resolve_user_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def build_blender_command(
    *,
    blender_exe: str,
    input_path: Path,
    asset_id: str,
    view_contract: Path,
    out_dir: Path,
    resolution: int,
    views: Sequence[str],
) -> list[str]:
    return [
        blender_exe,
        "--background",
        "--python",
        str(ROOT / "tools" / "render_glb_turntable.py"),
        "--",
        "--input",
        str(input_path),
        "--asset-id",
        asset_id,
        "--view-contract",
        str(view_contract),
        "--out",
        str(out_dir),
        "--resolution",
        str(resolution),
        "--views",
        ",".join(views),
    ]


def _non_empty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _validate_png(path: Path, resolution: int, errors: list[str]) -> None:
    if not _non_empty_file(path):
        errors.append(f"missing_output:{path}")
        return
    if Image is None:
        errors.append("png_validation_unavailable:pillow_missing")
        return
    try:
        with Image.open(path) as image:
            if image.size != (resolution, resolution):
                errors.append(
                    f"invalid_png_dimensions:{path}:{image.size[0]}x{image.size[1]}:expected_{resolution}x{resolution}"
                )
    except Exception as exc:
        errors.append(f"invalid_png:{path}:{exc}")


def _validate_camera(path: Path, asset_id: str, view_id: str, errors: list[str]) -> None:
    if not _non_empty_file(path):
        errors.append(f"missing_output:{path}")
        return
    try:
        camera = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid_camera_json:{path}:{exc}")
        return
    if not isinstance(camera, dict):
        errors.append(f"invalid_camera_json:{path}:root_not_object")
        return
    missing = sorted(REQUIRED_CAMERA_KEYS - set(camera))
    if missing:
        errors.append(f"invalid_camera_json:{path}:missing_keys:{','.join(missing)}")
    if camera.get("schema") != "sfb.camera.v1":
        errors.append(f"invalid_camera_json:{path}:schema")
    if camera.get("asset_id") != asset_id:
        errors.append(f"invalid_camera_json:{path}:asset_id")
    if camera.get("view_id") != view_id:
        errors.append(f"invalid_camera_json:{path}:view_id")
    if camera.get("camera_type") != "orthographic":
        errors.append(f"invalid_camera_json:{path}:camera_type")
    if not isinstance(camera.get("ortho_scale"), (int, float)):
        errors.append(f"invalid_camera_json:{path}:ortho_scale")
    for key in ("camera_location", "camera_rotation_euler"):
        value = camera.get(key)
        if not isinstance(value, list) or len(value) != 3 or not all(isinstance(item, (int, float)) for item in value):
            errors.append(f"invalid_camera_json:{path}:{key}")
    if not isinstance(camera.get("bbox"), dict):
        errors.append(f"invalid_camera_json:{path}:bbox")


def validate_blender_outputs(
    *,
    out_dir: Path,
    asset_id: str,
    views: Sequence[str],
    resolution: int,
) -> dict[str, Any]:
    errors: list[str] = []
    outputs: list[dict[str, str]] = []
    for view_id in views:
        view_dir = out_dir / view_id
        rgb = view_dir / "rgb.png"
        alpha = view_dir / "alpha.png"
        normal = view_dir / "normal.png"
        depth = view_dir / "depth.exr"
        camera = view_dir / "camera.json"
        _validate_png(rgb, resolution, errors)
        _validate_png(alpha, resolution, errors)
        _validate_png(normal, resolution, errors)
        if not _non_empty_file(depth):
            errors.append(f"missing_output:{depth}")
        _validate_camera(camera, asset_id, view_id, errors)
        outputs.append(
            {
                "view": view_id,
                "rgb": str(rgb),
                "alpha": str(alpha),
                "normal": str(normal),
                "depth": str(depth),
                "camera": str(camera),
            }
        )

    camera_errors = [error for error in errors if error.startswith("invalid_camera_json:")]
    status = "passed"
    if camera_errors:
        status = "failed_invalid_camera_json"
    elif errors:
        status = "failed_missing_blender_outputs"
    return {
        "ok": not errors,
        "status": status,
        "outputs": outputs,
        "errors": errors,
    }


def _base_report(args: argparse.Namespace, views: Sequence[str], started_at: str) -> dict[str, Any]:
    return {
        "schema": "sfb.blender_capture_gate.v1",
        "ok": False,
        "status": "failed_blender_render",
        "blocked": False,
        "started_at": started_at,
        "finished_at": "",
        "duration_s": 0.0,
        "input": str(Path(args.input)),
        "asset_id": args.asset_id,
        "view_contract": str(Path(args.view_contract)),
        "views": list(views),
        "resolution": args.resolution,
        "outputs": [],
        "errors": [],
        "warnings": [],
        "log": {},
        "command": [],
    }


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    started_at = utc_now()
    start = time.monotonic()
    views = parse_views(args.views)
    out_dir = resolve_user_path(args.out)
    report_path = (
        resolve_user_path(args.report)
        if args.report
        else out_dir / "blender_capture_gate_report.json"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = out_dir / "blender_stdout.log"
    stderr_log = out_dir / "blender_stderr.log"
    report = _base_report(args, views, started_at)
    report["input"] = str(resolve_user_path(args.input))
    report["view_contract"] = str(resolve_user_path(args.view_contract))
    report["log"] = {"stdout": str(stdout_log), "stderr": str(stderr_log)}

    def finish(status: str, *, ok: bool = False, blocked: bool = False) -> dict[str, Any]:
        report["ok"] = ok
        report["status"] = status
        report["blocked"] = blocked
        report["finished_at"] = utc_now()
        report["duration_s"] = round(time.monotonic() - start, 3)
        write_json(report_path, report)
        return report

    if not views:
        report["errors"].append("no_views_selected")
        return finish("failed_blender_render")

    blender = resolve_executable(args.blender_exe)
    if blender is None:
        report["errors"].append(f"blender_executable_missing:{args.blender_exe}")
        return finish("blocked_blender_executable_missing", blocked=True)

    input_path = resolve_user_path(args.input)
    view_contract = resolve_user_path(args.view_contract)
    if not input_path.is_file():
        report["errors"].append(f"missing_input:{input_path}")
        return finish("failed_blender_render")
    if not view_contract.is_file():
        report["errors"].append(f"missing_view_contract:{view_contract}")
        return finish("failed_blender_render")

    command = build_blender_command(
        blender_exe=blender,
        input_path=input_path,
        asset_id=args.asset_id,
        view_contract=view_contract,
        out_dir=out_dir,
        resolution=args.resolution,
        views=views,
    )
    report["command"] = command
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    stdout_log.write_text(proc.stdout, encoding="utf-8", errors="replace")
    stderr_log.write_text(proc.stderr, encoding="utf-8", errors="replace")
    report["exit_code"] = proc.returncode
    if proc.returncode != 0:
        report["errors"].append(f"blender_render_failed:{proc.returncode}")
        return finish("failed_blender_render")
    if "Traceback (most recent call last):" in proc.stderr:
        report["errors"].append("blender_python_traceback")
        return finish("failed_blender_render")

    validation = validate_blender_outputs(out_dir=out_dir, asset_id=args.asset_id, views=views, resolution=args.resolution)
    report["outputs"] = validation["outputs"]
    report["errors"].extend(validation["errors"])
    return finish(validation["status"], ok=bool(validation["ok"]))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and certify Blender capture outputs.")
    parser.add_argument("--blender-exe", default="blender")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--asset-id", default="DemoWall_LOD0")
    parser.add_argument("--view-contract", default=str(DEFAULT_VIEW_CONTRACT))
    parser.add_argument("--views", default="front")
    parser.add_argument("--resolution", type=int, default=256)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--report", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    report = run_gate(parse_args(argv))
    print(json.dumps({"ok": report["ok"], "status": report["status"]}, indent=2))
    return 0 if report["ok"] or report["blocked"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
