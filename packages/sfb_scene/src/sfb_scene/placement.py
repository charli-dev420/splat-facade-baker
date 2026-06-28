from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .models import Bounds, SceneCard, SFBScene


def normalize_angle_deg(value: float) -> float:
    value = value % 360.0
    return 0.0 if abs(value) < 1e-8 else value


def load_view_specs(view_contract_path: str | Path) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(view_contract_path).read_text(encoding="utf-8"))
    return {item["view_id"]: item for item in data.get("views", [])}


def resolve_view_rotation(view_contract_path: str | Path, view_id: str, *, base_rotation_y: float = 0.0) -> tuple[float, dict[str, Any]]:
    specs = load_view_specs(view_contract_path)
    if view_id not in specs:
        raise KeyError(f"view_id '{view_id}' not found in {view_contract_path}")
    spec = specs[view_id]
    return normalize_angle_deg(float(base_rotation_y) + float(spec.get("azimuth_deg", 0.0))), spec


def with_resolved_view(card: SceneCard, view_contract_path: str | Path | None, *, base_rotation_y: float | None = None) -> SceneCard:
    if view_contract_path is None:
        return card
    base = card.base_rotation_y if base_rotation_y is None else base_rotation_y
    rotation, spec = resolve_view_rotation(view_contract_path, card.view_id, base_rotation_y=base)
    data = card.model_dump()
    data["rotation_y"] = rotation
    data["base_rotation_y"] = base
    data["view_contract"] = data.get("view_contract") or str(view_contract_path)
    if spec.get("preferred_camera_band") and data.get("preferred_camera_band") is None:
        data["preferred_camera_band"] = tuple(float(v) for v in spec["preferred_camera_band"])
    if spec.get("role"):
        data.setdefault("metadata", {})["view_role"] = spec.get("role")
    if spec.get("elevation_deg") is not None:
        data.setdefault("metadata", {})["elevation_deg"] = float(spec.get("elevation_deg"))
    return SceneCard(**data)


def card_axis_aligned_bounds(card: SceneCard) -> Bounds:
    width = card.width_m * card.scale[0]
    height = card.height_m * card.scale[1]
    depth = max(card.depth_m * card.scale[2], 0.001)
    theta = math.radians(card.rotation_y)
    cos_t = abs(math.cos(theta))
    sin_t = abs(math.sin(theta))
    size_x = width * cos_t + depth * sin_t
    size_z = width * sin_t + depth * cos_t
    # bottom_center pivot: position is bottom center of the card.
    center = (card.position[0], card.position[1] + height * 0.5, card.position[2])
    return Bounds(center=center, size=(size_x, height, size_z))


def union_bounds(bounds: list[Bounds]) -> Bounds:
    if not bounds:
        return Bounds(center=(0.0, 0.0, 0.0), size=(0.0, 0.0, 0.0))
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    for b in bounds:
        for i in range(3):
            half = b.size[i] * 0.5
            mins[i] = min(mins[i], b.center[i] - half)
            maxs[i] = max(maxs[i], b.center[i] + half)
    size = tuple(maxs[i] - mins[i] for i in range(3))
    center = tuple(mins[i] + size[i] * 0.5 for i in range(3))
    return Bounds(center=center, size=size)  # type: ignore[arg-type]


def update_chunk_bounds(scene: SFBScene, chunk_id: str) -> SFBScene:
    chunk = scene.get_chunk(chunk_id)
    bounds = [card_axis_aligned_bounds(card) for card in scene.cards if card.chunk_id == chunk_id]
    chunk.bounds = union_bounds(bounds)
    return scene


def align_card_to_edge(scene: SFBScene, *, card_id: str, target_card_id: str, edge: str = "right", overlap_m: float = 0.0) -> SFBScene:
    card = scene.get_card(card_id)
    target = scene.get_card(target_card_id)
    # v2.8 MVP: edge alignment assumes similar card rotations and aligns along world X.
    data = card.model_dump()
    tx, ty, tz = target.position
    if edge == "right":
        data["position"] = (tx + target.width_m * target.scale[0] * 0.5 + card.width_m * card.scale[0] * 0.5 - overlap_m, card.position[1], tz)
    elif edge == "left":
        data["position"] = (tx - target.width_m * target.scale[0] * 0.5 - card.width_m * card.scale[0] * 0.5 + overlap_m, card.position[1], tz)
    else:
        raise ValueError("v2.8 align_card_to_edge supports 'left' and 'right' edges")
    scene.add_card(SceneCard(**data), replace=True)
    return scene
