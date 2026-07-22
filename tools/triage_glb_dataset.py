from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from sfb_dataset.manifest import AssetRecord, DatasetManifest

try:
    from PIL import Image
except Exception:  # pragma: no cover - covered by runtime report status
    Image = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VIEW_CONTRACT = ROOT / "examples" / "view_contracts" / "MV8_OBJECT.json"
MANAGED_STATUS = Literal["keep", "repair", "quarantine", "reject", "pending"]


@dataclass(frozen=True)
class TriageThresholds:
    min_alpha_coverage: float = 0.002
    repair_alpha_coverage: float = 0.01
    max_alpha_coverage: float = 0.92
    edge_touch_ratio: float = 0.01
    min_bbox_extent: float = 0.001
    max_bbox_extent: float = 10000.0
    heavy_file_mb: float = 250.0
    slow_render_s: float = 60.0

    def as_dict(self) -> dict[str, float]:
        return {
            "min_alpha_coverage": self.min_alpha_coverage,
            "repair_alpha_coverage": self.repair_alpha_coverage,
            "max_alpha_coverage": self.max_alpha_coverage,
            "edge_touch_ratio": self.edge_touch_ratio,
            "min_bbox_extent": self.min_bbox_extent,
            "max_bbox_extent": self.max_bbox_extent,
            "heavy_file_mb": self.heavy_file_mb,
            "slow_render_s": self.slow_render_s,
        }


@dataclass
class TriageItem:
    asset_id: str
    source_path: str
    status: MANAGED_STATUS
    score: float
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    gate_report: str | None = None
    duration_s: float | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "source_path": self.source_path,
            "status": self.status,
            "score": round(self.score, 3),
            "reasons": self.reasons,
            "metrics": self.metrics,
            "outputs": self.outputs,
            "gate_report": self.gate_report,
            "duration_s": self.duration_s,
            "error": self.error,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_executable(executable: str) -> str | None:
    candidate = Path(executable)
    if candidate.exists():
        return str(candidate.resolve())
    found = shutil.which(executable)
    return str(Path(found).resolve()) if found else None


def normalize_prefix(manifest_path: Path, manifest: DatasetManifest) -> str:
    prefix = manifest_path.name
    for suffix in (".raw.json", ".json"):
        if prefix.endswith(suffix):
            prefix = prefix[: -len(suffix)]
            break
    return prefix or manifest.dataset_id


def resolve_asset_source(asset: AssetRecord, source_root: Path | None) -> Path | None:
    if not asset.source_path:
        return None
    source = Path(asset.source_path)
    if source.is_absolute():
        return source
    if source_root is None:
        return None
    return source_root / source


def source_preflight(
    asset: AssetRecord,
    source_path: Path | None,
    seen_hashes: set[str],
    thresholds: TriageThresholds,
) -> tuple[MANAGED_STATUS | None, float, list[str], dict[str, Any]]:
    reasons: list[str] = []
    metrics: dict[str, Any] = {}
    score = 100.0

    if source_path is None:
        return "reject", 0.0, ["missing_source_path"], metrics
    metrics["resolved_source_path"] = str(source_path)
    if not source_path.is_file():
        return "reject", 0.0, [f"missing_source_file:{source_path}"], metrics
    size_bytes = source_path.stat().st_size
    metrics["source_size_bytes"] = size_bytes
    metrics["source_size_mb"] = round(size_bytes / (1024 * 1024), 3)
    if size_bytes <= 0:
        return "reject", 0.0, ["empty_source_file"], metrics
    if source_path.suffix.lower() not in {".glb", ".gltf"}:
        return "reject", 0.0, [f"unsupported_ext:{source_path.suffix.lower()}"], metrics

    digest = asset.source_hash
    if digest and digest in seen_hashes:
        return "reject", 0.0, [f"duplicate_source_hash:{digest[:12]}"], metrics
    if digest:
        seen_hashes.add(digest)

    if metrics["source_size_mb"] > thresholds.heavy_file_mb:
        reasons.append("heavy_source_file")
        score -= 15

    return None, score, reasons, metrics


def analyze_alpha(
    alpha_path: Path,
    thresholds: TriageThresholds,
) -> tuple[float, list[str], dict[str, Any]]:
    if Image is None:
        return 0.0, ["image_analysis_unavailable:pillow_missing"], {}
    reasons: list[str] = []
    metrics: dict[str, Any] = {}
    with Image.open(alpha_path) as image:
        alpha = image.convert("L")
        width, height = alpha.size
        pixels = alpha.load()
        nonzero = 0
        min_x = width
        min_y = height
        max_x = -1
        max_y = -1
        edge_nonzero = 0
        for y in range(height):
            for x in range(width):
                if pixels[x, y] > 8:
                    nonzero += 1
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
                    if x == 0 or y == 0 or x == width - 1 or y == height - 1:
                        edge_nonzero += 1
    total = max(width * height, 1)
    coverage = nonzero / total
    edge_ratio = edge_nonzero / max(nonzero, 1)
    metrics.update(
        {
            "alpha_coverage": round(coverage, 6),
            "alpha_nonzero_pixels": nonzero,
            "alpha_edge_touch_ratio": round(edge_ratio, 6),
        }
    )
    score_delta = 0.0
    if nonzero == 0 or coverage < thresholds.min_alpha_coverage:
        reasons.append("invisible_or_tiny_alpha")
        score_delta -= 100
    elif coverage < thresholds.repair_alpha_coverage:
        reasons.append("very_small_render_coverage")
        score_delta -= 35
    if coverage > thresholds.max_alpha_coverage:
        reasons.append("oversized_or_full_frame_alpha")
        score_delta -= 35
    if edge_ratio > thresholds.edge_touch_ratio:
        reasons.append("object_touches_render_border")
        score_delta -= 20
    if nonzero:
        bbox_w = max_x - min_x + 1
        bbox_h = max_y - min_y + 1
        metrics.update(
            {
                "alpha_bbox": [min_x, min_y, max_x, max_y],
                "alpha_bbox_width": bbox_w,
                "alpha_bbox_height": bbox_h,
                "alpha_bbox_area_ratio": round((bbox_w * bbox_h) / total, 6),
            }
        )
    return score_delta, reasons, metrics


def analyze_camera(
    camera_path: Path,
    thresholds: TriageThresholds,
) -> tuple[float, list[str], dict[str, Any]]:
    camera = json.loads(camera_path.read_text(encoding="utf-8"))
    bbox = camera.get("bbox") if isinstance(camera, dict) else None
    if not isinstance(bbox, dict):
        return -100.0, ["missing_camera_bbox"], {}
    size = bbox.get("bbox_size")
    max_dim = bbox.get("max_dim")
    metrics: dict[str, Any] = {"camera_bbox": bbox}
    reasons: list[str] = []
    score_delta = 0.0
    if (
        isinstance(size, list)
        and len(size) == 3
        and all(isinstance(value, (int, float)) for value in size)
    ):
        dims = [abs(float(value)) for value in size]
        metrics["bbox_size"] = dims
        nonzero = [value for value in dims if value > thresholds.min_bbox_extent]
        if not nonzero:
            reasons.append("zero_or_near_zero_bbox")
            score_delta -= 100
        elif len(nonzero) < 2:
            reasons.append("flat_or_degenerate_bbox")
            score_delta -= 25
        if nonzero:
            ratio = max(nonzero) / max(min(nonzero), thresholds.min_bbox_extent)
            metrics["bbox_aspect_ratio"] = round(ratio, 3)
            if ratio > 500:
                reasons.append("extreme_bbox_aspect_ratio")
                score_delta -= 20
    if isinstance(max_dim, (int, float)):
        metrics["bbox_max_dim"] = float(max_dim)
        if max_dim < thresholds.min_bbox_extent:
            reasons.append("bbox_too_small")
            score_delta -= 100
        elif max_dim > thresholds.max_bbox_extent:
            reasons.append("bbox_too_large")
            score_delta -= 35
    else:
        reasons.append("missing_bbox_max_dim")
        score_delta -= 20
    return score_delta, reasons, metrics


def classify(score: float, reasons: list[str]) -> MANAGED_STATUS:
    hard_reject = {
        "empty_source_file",
        "invisible_or_tiny_alpha",
        "zero_or_near_zero_bbox",
        "bbox_too_small",
    }
    if any(reason in hard_reject for reason in reasons):
        return "reject"
    if score >= 85 and not reasons:
        return "keep"
    if score >= 70:
        return "repair"
    return "quarantine"


def run_blender_gate(
    *,
    blender_exe: str,
    source_path: Path,
    asset_id: str,
    view_contract: Path,
    out_dir: Path,
    report_path: Path,
    resolution: int,
    timeout_s: int,
) -> tuple[dict[str, Any] | None, float, str | None]:
    command = [
        sys.executable,
        str(ROOT / "tools" / "blender_capture_gate.py"),
        "--blender-exe",
        blender_exe,
        "--input",
        str(source_path),
        "--asset-id",
        asset_id,
        "--view-contract",
        str(view_contract),
        "--views",
        "front",
        "--resolution",
        str(resolution),
        "--out",
        str(out_dir),
        "--report",
        str(report_path),
    ]
    start = time.monotonic()
    try:
        subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return None, round(time.monotonic() - start, 3), "blender_gate_timeout"
    duration = round(time.monotonic() - start, 3)
    if not report_path.is_file():
        return None, duration, "missing_gate_report"
    try:
        return json.loads(report_path.read_text(encoding="utf-8")), duration, None
    except Exception as exc:
        return None, duration, f"invalid_gate_report:{exc}"


def classify_asset(
    *,
    asset: AssetRecord,
    source_path: Path | None,
    seen_hashes: set[str],
    blender_exe: str,
    view_contract: Path,
    renders_root: Path,
    reports_root: Path,
    resolution: int,
    timeout_s: int,
    thresholds: TriageThresholds,
) -> TriageItem:
    terminal, score, reasons, metrics = source_preflight(
        asset,
        source_path,
        seen_hashes,
        thresholds,
    )
    source_label = str(source_path) if source_path is not None else asset.source_path or ""
    if terminal is not None:
        return TriageItem(
            asset_id=asset.asset_id,
            source_path=source_label,
            status=terminal,
            score=score,
            reasons=reasons,
            metrics=metrics,
        )

    out_dir = renders_root / asset.asset_id
    report_path = reports_root / "gate_reports" / f"{asset.asset_id}.json"
    gate, duration, gate_error = run_blender_gate(
        blender_exe=blender_exe,
        source_path=source_path,
        asset_id=asset.asset_id,
        view_contract=view_contract,
        out_dir=out_dir,
        report_path=report_path,
        resolution=resolution,
        timeout_s=timeout_s,
    )
    metrics["render_duration_s"] = duration
    if duration > thresholds.slow_render_s:
        reasons.append("slow_front_render")
        score -= 15
    if gate_error:
        return TriageItem(
            asset_id=asset.asset_id,
            source_path=source_label,
            status="quarantine",
            score=0.0,
            reasons=[*reasons, gate_error],
            metrics=metrics,
            gate_report=str(report_path),
            duration_s=duration,
            error=gate_error,
        )
    assert gate is not None
    if not gate.get("ok"):
        gate_reasons = [str(error) for error in gate.get("errors", [])]
        status: MANAGED_STATUS = (
            "reject" if gate.get("status") == "failed_blender_render" else "quarantine"
        )
        return TriageItem(
            asset_id=asset.asset_id,
            source_path=source_label,
            status=status,
            score=0.0,
            reasons=[*reasons, f"gate_status:{gate.get('status')}", *gate_reasons],
            metrics=metrics,
            gate_report=str(report_path),
            duration_s=duration,
        )

    view_dir = out_dir / "front"
    outputs = {
        "rgb": str(view_dir / "rgb.png"),
        "alpha": str(view_dir / "alpha.png"),
        "normal": str(view_dir / "normal.png"),
        "depth": str(view_dir / "depth.exr"),
        "camera": str(view_dir / "camera.json"),
    }
    alpha_delta, alpha_reasons, alpha_metrics = analyze_alpha(
        view_dir / "alpha.png",
        thresholds,
    )
    camera_delta, camera_reasons, camera_metrics = analyze_camera(
        view_dir / "camera.json",
        thresholds,
    )
    score += alpha_delta + camera_delta
    reasons.extend(alpha_reasons)
    reasons.extend(camera_reasons)
    metrics.update(alpha_metrics)
    metrics.update(camera_metrics)
    status = classify(max(score, 0.0), reasons)
    return TriageItem(
        asset_id=asset.asset_id,
        source_path=source_label,
        status=status,
        score=max(score, 0.0),
        reasons=reasons,
        metrics=metrics,
        outputs=outputs,
        gate_report=str(report_path),
        duration_s=duration,
    )


def clone_manifest_with_assets(
    manifest: DatasetManifest,
    assets: list[AssetRecord],
    *,
    triage_status: str,
) -> DatasetManifest:
    cloned_assets: list[AssetRecord] = []
    for asset in assets:
        cloned = asset.model_copy(deep=True)
        if triage_status == "keep":
            cloned.quality_status = "approved"
            cloned.data_tier = "gold_candidate"
        elif triage_status == "repair":
            cloned.quality_status = "needs_review"
            cloned.data_tier = "candidate"
        elif triage_status == "quarantine":
            cloned.quality_status = "flagged"
            cloned.data_tier = "candidate"
        elif triage_status == "reject":
            cloned.quality_status = "rejected"
            cloned.data_tier = "rejected"
        cloned_assets.append(cloned)
    result = manifest.model_copy(deep=True)
    result.assets = cloned_assets
    result.metadata = {
        **result.metadata,
        "triage_status": triage_status,
        "triage_generated_at": utc_now(),
    }
    return result


def apply_item_to_asset(asset: AssetRecord, item: TriageItem) -> AssetRecord:
    cloned = asset.model_copy(deep=True)
    cloned.quality_score = round(item.score, 3)
    cloned.notes = "; ".join(item.reasons)
    if item.metrics.get("bbox_size"):
        size = item.metrics["bbox_size"]
        cloned.width_m = float(size[0])
        cloned.height_m = float(size[1])
        cloned.depth_m = float(size[2])
    return cloned


def write_status_manifests(
    manifest: DatasetManifest,
    items: list[TriageItem],
    pending_assets: list[AssetRecord],
    manifests_dir: Path,
    prefix: str,
) -> dict[str, str]:
    by_id = {asset.asset_id: asset for asset in manifest.assets}
    buckets: dict[str, list[AssetRecord]] = {
        status: [] for status in ["keep", "repair", "quarantine", "reject"]
    }
    for item in items:
        source = by_id[item.asset_id]
        buckets[item.status].append(apply_item_to_asset(source, item))

    outputs: dict[str, str] = {}
    for status, assets in buckets.items():
        path = manifests_dir / f"{prefix}.{status}.json"
        clone_manifest_with_assets(manifest, assets, triage_status=status).save(path)
        outputs[f"{status}_manifest"] = str(path)
    pending_path = manifests_dir / f"{prefix}.pending.json"
    clone_manifest_with_assets(manifest, pending_assets, triage_status="pending").save(pending_path)
    outputs["pending_manifest"] = str(pending_path)
    return outputs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Triage GLB assets before expensive MV8 rendering."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-root", default=None)
    parser.add_argument("--blender-exe", default="blender")
    parser.add_argument("--view-contract", default=str(DEFAULT_VIEW_CONTRACT))
    parser.add_argument("--resolution", type=int, default=128)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--renders-root", default=None)
    parser.add_argument("--reports-root", default=None)
    parser.add_argument("--manifests-dir", default=str(ROOT / "workspace" / "manifests"))
    parser.add_argument("--out", default=None)
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest).resolve()
    manifest = DatasetManifest.load(manifest_path)
    prefix = args.prefix or normalize_prefix(manifest_path, manifest)
    reports_root = Path(
        args.reports_root
        or ROOT / "workspace" / "reports" / "datasets" / manifest.dataset_id / "triage"
    )
    renders_root = Path(
        args.renders_root
        or ROOT / "workspace" / "triage" / manifest.dataset_id / "renders"
    )
    manifests_dir = Path(args.manifests_dir)
    report_path = Path(args.out or reports_root / f"{prefix}.triage_report.json")
    source_root = Path(args.source_root).resolve() if args.source_root else None
    view_contract = Path(args.view_contract).resolve()
    thresholds = TriageThresholds()
    blender = resolve_executable(args.blender_exe)
    if blender is None:
        raise SystemExit(f"Blender executable not found: {args.blender_exe}")
    if Image is None:
        raise SystemExit("Pillow is required for GLB triage image analysis")

    selected = manifest.assets[args.start :]
    if args.limit is not None:
        selected = selected[: args.limit]
    selected_ids = {asset.asset_id for asset in selected}
    pending_assets = [asset for asset in manifest.assets if asset.asset_id not in selected_ids]

    seen_hashes: set[str] = set()
    for asset in manifest.assets[: args.start]:
        if asset.source_hash:
            seen_hashes.add(asset.source_hash)

    items: list[TriageItem] = []
    started_at = utc_now()
    for index, asset in enumerate(selected, start=args.start):
        source_path = resolve_asset_source(asset, source_root)
        item = classify_asset(
            asset=asset,
            source_path=source_path,
            seen_hashes=seen_hashes,
            blender_exe=blender,
            view_contract=view_contract,
            renders_root=renders_root,
            reports_root=reports_root,
            resolution=args.resolution,
            timeout_s=args.timeout,
            thresholds=thresholds,
        )
        item.metrics["asset_index"] = index
        items.append(item)
        print(
            json.dumps(
                {"asset_id": item.asset_id, "status": item.status, "score": item.score}
            )
        )

    manifest_outputs = write_status_manifests(
        manifest,
        items,
        pending_assets,
        manifests_dir,
        prefix,
    )
    totals = {status: 0 for status in ["keep", "repair", "quarantine", "reject", "pending"]}
    for item in items:
        totals[item.status] += 1
    totals["pending"] = len(pending_assets)
    report = {
        "schema": "sfb.glb_triage_report.v1",
        "dataset_id": manifest.dataset_id,
        "manifest": str(manifest_path),
        "source_root": str(source_root) if source_root else None,
        "view_contract": str(view_contract),
        "blender_exe": blender,
        "resolution": args.resolution,
        "timeout_s": args.timeout,
        "started_at": started_at,
        "finished_at": utc_now(),
        "processed_assets": len(items),
        "total_assets": len(manifest.assets),
        "start": args.start,
        "limit": args.limit,
        "thresholds": thresholds.as_dict(),
        "totals": totals,
        "outputs": {
            **manifest_outputs,
            "renders_root": str(renders_root),
            "reports_root": str(reports_root),
        },
        "items": [item.as_dict() for item in items],
    }
    write_json(report_path, report)
    print(json.dumps({"ok": True, "report": str(report_path), "totals": totals}, indent=2))
    return report


def main(argv: list[str] | None = None) -> int:
    run(build_arg_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
