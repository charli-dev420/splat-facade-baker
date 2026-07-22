from __future__ import annotations

from pathlib import Path


class SplatBackendNotAvailable(RuntimeError):
    pass


def render_splat_to_maps(*, splat_path: str | Path, output_dir: str | Path, view_id: str) -> None:
    """Experimental non-MVP gsplat-backed canonical renderer.

    Planned behavior:
    splat + ViewContract camera → RGB + alpha + depth maps → bake_maps.

    This stub is intentionally not implemented in pre-MVP so the core remains
    usable without CUDA or splat-specific dependencies.
    """
    raise SplatBackendNotAvailable(
        "`sfb bake-splat` is experimental and excluded from the current MVP. "
        "Use `sfb bake-maps` until a validated renderer is integrated."
    )
