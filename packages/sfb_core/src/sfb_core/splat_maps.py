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
    """Experimental non-MVP backend: splat → RGB/alpha/depth maps.

    This is intentionally a typed stub in pre-MVP. The stable MVP path is
    `bake-maps`; once a real renderer is wired, this function should render
    canonical RGB/alpha/depth maps and then call the same bake code.
    """
    raise NotImplementedError(
        "`sfb bake-splat` is experimental and excluded from the current MVP. "
        "Use `sfb bake-maps`; add a validated splat renderer before enabling this path."
    )
