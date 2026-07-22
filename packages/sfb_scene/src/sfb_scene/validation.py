from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import SFBScene
from .placement import card_axis_aligned_bounds, union_bounds


def _read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"{exc.msg} at line {exc.lineno} column {exc.colno}"
    except Exception as exc:  # noqa: BLE001 - validation reports file/read failures.
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(data, dict):
        return None, "JSON root must be an object"
    return data, None


def validate_scene(scene: SFBScene, *, scene_path: str | Path | None = None) -> dict[str, Any]:
    base_dir = Path(scene_path).parent if scene_path else Path.cwd()
    warnings: list[str] = []
    errors: list[str] = []
    total_triangles = 0
    total_texture_memory = 0.0
    alpha_cards = 0
    packages_found = 0
    invalid_packages = 0
    invalid_reports = 0
    missing_packages: list[str] = []
    package_paths_seen: set[str] = set()

    for card in scene.cards:
        package_path = Path(card.asset_package)
        if not package_path.is_absolute():
            package_path = (base_dir / package_path).resolve()
        if not package_path.exists():
            missing_packages.append(card.asset_package)
            errors.append(f"missing_package:{card.scene_card_id}:{card.asset_package}")
            continue
        packages_found += 1
        package_paths_seen.add(str(package_path))
        package, package_error = _read_json_object(package_path)
        if package is None:
            invalid_packages += 1
            errors.append(f"invalid_package_json:{card.scene_card_id}:{package_path}:{package_error}")
            continue
        mesh = package.get("mesh", {}) if isinstance(package.get("mesh"), dict) else {}
        runtime = package.get("runtime", {}) if isinstance(package.get("runtime"), dict) else {}
        total_triangles += int(mesh.get("triangles_lod0") or 0)
        if str(runtime.get("alpha_mode", "")).lower() in {"cutout", "transparent", "blend"}:
            alpha_cards += 1
        report_rel = package.get("report")
        if report_rel:
            report_path = package_path.parent / str(report_rel)
            report, report_error = _read_json_object(report_path) if report_path.exists() else ({}, None)
            if report is None:
                invalid_reports += 1
                errors.append(f"invalid_report_json:{card.scene_card_id}:{report_path}:{report_error}")
                continue
            metrics = report.get("metrics", {}) if isinstance(report.get("metrics"), dict) else {}
            total_texture_memory += float(metrics.get("estimated_texture_memory_mb_uncompressed") or 0.0)
            if report.get("status") in {"failed", "rejected"}:
                warnings.append(f"package_status_{report.get('status')}:{card.scene_card_id}")

    chunk_ids = {chunk.chunk_id for chunk in scene.chunks}
    for card in scene.cards:
        if card.chunk_id and card.chunk_id not in chunk_ids:
            warnings.append(f"card_references_missing_chunk:{card.scene_card_id}:{card.chunk_id}")
        if card.depth_m > 1.0:
            warnings.append(f"large_card_depth:{card.scene_card_id}:{card.depth_m:.2f}m")

    if len(package_paths_seen) < packages_found:
        warnings.append("duplicate_asset_packages_in_scene")
    if alpha_cards > max(8, len(scene.cards) * 0.75):
        warnings.append("high_alpha_card_density")
    if total_texture_memory > 128.0:
        warnings.append("texture_memory_over_128mb_uncompressed")
    if total_triangles > 50000:
        warnings.append("triangles_lod0_over_50000")

    chunk_reports: list[dict[str, Any]] = []
    for chunk in scene.chunks:
        cards = [card for card in scene.cards if card.chunk_id == chunk.chunk_id]
        bounds = union_bounds([card_axis_aligned_bounds(card) for card in cards])
        chunk_reports.append({
            "chunk_id": chunk.chunk_id,
            "cards": len(cards),
            "bounds": bounds.model_dump(),
            "mobile_profile": chunk.mobile_profile,
        })

    status = "failed" if errors else ("needs_review" if warnings else "ok")
    return {
        "schema": "sfb.scene_report.v1",
        "scene_id": scene.scene_id,
        "status": status,
        "metrics": {
            "cards_total": len(scene.cards),
            "chunks_total": len(scene.chunks),
            "packages_found": packages_found,
            "missing_packages": len(missing_packages),
            "invalid_packages": invalid_packages,
            "invalid_reports": invalid_reports,
            "unique_packages": len(package_paths_seen),
            "triangles_total_lod0": total_triangles,
            "estimated_texture_memory_mb_uncompressed": round(total_texture_memory, 3),
            "alpha_cards": alpha_cards,
        },
        "chunks": chunk_reports,
        "warnings": warnings,
        "errors": errors,
        "missing_packages": missing_packages,
    }
