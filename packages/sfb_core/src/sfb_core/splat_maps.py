from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SplatRenderRequest:
    input_splat: Path
    output_dir: Path
    view_contract_id: str
    view_id: str
    width_m: float
    height_m: float
    max_depth_m: float
    resolution: int = 1024
    camera_model: str = "orthographic"


def render_splat_to_maps(request: SplatRenderRequest) -> dict:
    """Future Block 3 backend: splat → RGB/alpha/depth maps.

    This is intentionally a typed stub in v2.3. The stable pipeline already uses
    `bake-maps`; once the gsplat backend is wired, this function should render
    canonical RGB/alpha/depth maps and then call the same bake code.
    """
    raise NotImplementedError(
        "Splat rendering is scaffolded but not implemented in v2.3. "
        "Use `sfb bake-maps` first, or add a gsplat-backed renderer here."
    )
