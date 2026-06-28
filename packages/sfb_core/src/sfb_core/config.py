from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class BakeSettings:
    name: str
    width_m: float = 8.0
    height_m: float = 4.0
    max_depth_m: float = 0.5
    grid: int = 96
    alpha_threshold: float = 0.05
    depth_invert: bool = False
    pivot: str = "bottom_center"
    mode: str = "depth_card"
    view_contract_id: str = "manual"
    view_id: str = "front"
    canonical_view: str = "front"
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    mobile_tier: str = "mobile_mid"

    # Block 3 cleanup controls.
    cleanup: bool = True
    keep_largest_component: bool = False
    remove_components_smaller_than_px: int = 32
    fill_holes_smaller_than_px: int = 64
    edge_feather_px: int = 0
    depth_clip_low_percentile: float = 1.0
    depth_clip_high_percentile: float = 99.0
    depth_smooth_radius: int = 1

    # Block 3 LOD / texture controls.
    lod_count: int = 3
    lod1_grid_scale: float = 0.5
    lod2_grid_scale: float = 0.25
    lod2_mode: str = "flat_card"
    texture_size: int = 0
    save_clean_debug: bool = False

    def validate(self) -> None:
        if self.width_m <= 0 or self.height_m <= 0:
            raise ValueError("width_m and height_m must be positive")
        if self.max_depth_m < 0:
            raise ValueError("max_depth_m must be non-negative")
        if self.grid < 2:
            raise ValueError("grid must be >= 2")
        if not (0 <= self.alpha_threshold <= 1):
            raise ValueError("alpha_threshold must be in [0, 1]")
        if self.mode not in {"flat_card", "depth_card", "layered_card", "multi_angle_impostor"}:
            raise ValueError(f"unsupported mode: {self.mode}")
        if self.lod_count < 1 or self.lod_count > 3:
            raise ValueError("lod_count must be between 1 and 3 in v2.3")
        if self.lod1_grid_scale <= 0 or self.lod2_grid_scale <= 0:
            raise ValueError("LOD grid scales must be positive")
        if self.lod2_mode not in {"flat_card", "depth_card"}:
            raise ValueError("lod2_mode must be 'flat_card' or 'depth_card'")
        if not (0 <= self.depth_clip_low_percentile <= 100 and 0 <= self.depth_clip_high_percentile <= 100):
            raise ValueError("depth clip percentiles must be in [0, 100]")
        if self.depth_clip_low_percentile >= self.depth_clip_high_percentile:
            raise ValueError("depth_clip_low_percentile must be lower than depth_clip_high_percentile")
        if self.texture_size < 0:
            raise ValueError("texture_size must be >= 0")

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
