from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]


class SceneTarget(BaseModel):
    engine: str = "unity"
    platform: str = "mobile"
    camera_mode: str = "isometric_2_5d"
    mobile_profile: str = "mobile_mid"


class Bounds(BaseModel):
    center: Vec3 = (0.0, 0.0, 0.0)
    size: Vec3 = (0.0, 0.0, 0.0)


class ChunkGroup(BaseModel):
    chunk_id: str
    name: str = ""
    bounds: Bounds | None = None
    mobile_profile: str = "mobile_mid"
    occlusion_layer: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SceneCard(BaseModel):
    scene_card_id: str
    asset_package: str
    view_id: str
    view_contract: str | None = None
    source_asset_id: str | None = None
    position: Vec3 = (0.0, 0.0, 0.0)
    rotation_y: float = 0.0
    base_rotation_y: float = 0.0
    scale: Vec3 = (1.0, 1.0, 1.0)
    width_m: float = 1.0
    height_m: float = 1.0
    depth_m: float = 0.05
    pivot: str = "bottom_center"
    occlusion_layer: int = 0
    chunk_id: str | None = None
    status: str = "unreviewed"
    preferred_camera_band: Vec2 | None = None
    card_type: Literal["single_card", "layered_card", "multi_angle_card", "facade_strip"] = "single_card"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("width_m", "height_m", "depth_m")
    @classmethod
    def _non_negative_dimensions(cls, value: float) -> float:
        if value < 0:
            raise ValueError("dimensions must be non-negative")
        return value

    @field_validator("scale")
    @classmethod
    def _positive_scale(cls, value: Vec3) -> Vec3:
        if any(v <= 0 for v in value):
            raise ValueError("scale values must be positive")
        return value


class PlacementRule(BaseModel):
    rule_id: str
    rule_type: Literal["align_edge", "manual", "strip_step", "next_generation_context"]
    card_id: str | None = None
    target_card_id: str | None = None
    edge: Literal["left", "right", "top", "bottom", "front", "back"] | None = None
    overlap_m: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SFBScene(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_: str = Field("sfb.scene.v1", alias="schema")
    scene_id: str
    units: str = "meters"
    target: SceneTarget = Field(default_factory=SceneTarget)
    view_contracts: list[str] = Field(default_factory=list)
    cards: list[SceneCard] = Field(default_factory=list)
    chunks: list[ChunkGroup] = Field(default_factory=list)
    placement_rules: list[PlacementRule] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "SFBScene":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def save(self, path: str | Path) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.model_dump_json(indent=2, by_alias=True), encoding="utf-8")

    def get_card(self, scene_card_id: str) -> SceneCard:
        for card in self.cards:
            if card.scene_card_id == scene_card_id:
                return card
        raise KeyError(f"SceneCard not found: {scene_card_id}")

    def get_chunk(self, chunk_id: str) -> ChunkGroup:
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        raise KeyError(f"Chunk not found: {chunk_id}")

    def add_card(self, card: SceneCard, *, replace: bool = False) -> None:
        for idx, existing in enumerate(self.cards):
            if existing.scene_card_id == card.scene_card_id:
                if not replace:
                    raise ValueError(f"SceneCard already exists: {card.scene_card_id}")
                self.cards[idx] = card
                return
        self.cards.append(card)

    def add_chunk(self, chunk: ChunkGroup, *, replace: bool = False) -> None:
        for idx, existing in enumerate(self.chunks):
            if existing.chunk_id == chunk.chunk_id:
                if not replace:
                    raise ValueError(f"Chunk already exists: {chunk.chunk_id}")
                self.chunks[idx] = chunk
                return
        self.chunks.append(chunk)

    def remove_card(self, scene_card_id: str) -> None:
        before = len(self.cards)
        self.cards = [card for card in self.cards if card.scene_card_id != scene_card_id]
        if len(self.cards) == before:
            raise KeyError(f"SceneCard not found: {scene_card_id}")
