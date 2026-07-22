from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "sfb_orchestrator" / "src"))

from sfb_orchestrator.comfy.client import ComfyClient  # noqa: E402
from sfb_orchestrator.db.store import OrchestratorStore  # noqa: E402
from sfb_orchestrator.jobs.runner import JobRunner  # noqa: E402
from sfb_orchestrator.paths import SFBWorkspace  # noqa: E402


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the MVP ComfyUI demo gate.")
    parser.add_argument("--workspace", default="workspace/comfyui_demo_gate")
    parser.add_argument("--project-id", default="comfyui_demo")
    parser.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    parser.add_argument("--live-metadata", default=None, help="Operator-provided real ComfyUI metadata JSON.")
    parser.add_argument("--report", default=None)
    args = parser.parse_args(argv)

    workspace = SFBWorkspace(Path(args.workspace))
    workspace.ensure()
    report_path = Path(args.report) if args.report else workspace.root / "comfyui_demo_gate_report.json"
    store = OrchestratorStore(workspace.db_path)
    try:
        store.create_project(args.project_id, name="ComfyUI Demo Gate", root_path=workspace.root)
    except ValueError:
        pass

    fixture = ROOT / "packages" / "sfb_orchestrator" / "tests" / "fixtures" / "comfyui_dry_run" / "comfy_dry_run.metadata.json"
    workflow = store.register_workflow_metadata(fixture, project_id=args.project_id)
    job = store.create_job(
        args.project_id,
        engine="comfyui",
        workflow_id=workflow.workflow_id,
        params={
            "dry_run": True,
            "input_image": "operator_input.png",
            "filename_prefix": "SFB/demo_gate",
        },
    )
    dry_result = JobRunner(store, workspace).run_next(args.project_id)

    report: dict[str, Any] = {
        "ok": dry_result is not None and dry_result.status == "completed",
        "dry_run": {
            "job_id": job.job_id,
            "status": None if dry_result is None else dry_result.status,
            "workflow_id": workflow.workflow_id,
        },
        "live": {"status": "not_requested"},
    }

    try:
        status = ComfyClient(base_url=args.comfy_url, timeout=2).status()
    except Exception as exc:  # noqa: BLE001
        status = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    if not status.get("ok"):
        report["live"] = {
            "status": "blocked_comfyui_unavailable",
            "comfy_url": args.comfy_url,
            "detail": status,
        }
    elif args.live_metadata is None:
        report["live"] = {
            "status": "blocked_live_metadata_required",
            "comfy_url": args.comfy_url,
            "detail": "Provide --live-metadata for a real operator-owned workflow.",
        }
    else:
        report["live"] = {
            "status": "ready_for_operator_workflow",
            "comfy_url": args.comfy_url,
            "metadata": str(Path(args.live_metadata).resolve()),
        }

    _write_report(report_path, report)
    print(json.dumps({"ok": report["ok"], "report": str(report_path), "live": report["live"]["status"]}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
