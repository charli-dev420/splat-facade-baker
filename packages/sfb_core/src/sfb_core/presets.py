from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MobilePreset:
    texture_size: int
    triangles_lod0: int
    max_depth_m: float
    normal_map: bool
    alpha_mode: str


MOBILE_PRESETS: dict[str, MobilePreset] = {
    "mobile_low": MobilePreset(texture_size=512, triangles_lod0=300, max_depth_m=0.25, normal_map=False, alpha_mode="cutout_or_opaque"),
    "mobile_mid": MobilePreset(texture_size=1024, triangles_lod0=800, max_depth_m=0.45, normal_map=True, alpha_mode="cutout"),
    "mobile_high": MobilePreset(texture_size=2048, triangles_lod0=1500, max_depth_m=0.7, normal_map=True, alpha_mode="cutout_or_blend_limited"),
}


def get_mobile_preset(name: str) -> MobilePreset:
    return MOBILE_PRESETS.get(name, MOBILE_PRESETS["mobile_mid"])
