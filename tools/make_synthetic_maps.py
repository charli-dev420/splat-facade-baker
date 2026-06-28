from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic albedo/alpha/depth maps for SFB quickstart.")
    parser.add_argument("--out", required=True)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=256)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    w, h = args.width, args.height
    yy, xx = np.mgrid[:h, :w]
    x = (xx - w / 2) / (w / 2)
    y = (yy - h / 2) / (h / 2)
    mask = ((x / 0.88) ** 2 + (y / 0.72) ** 2) < 1
    alpha = (mask.astype(np.uint8) * 255)

    albedo = np.zeros((h, w, 3), dtype=np.uint8)
    albedo[..., 0] = np.clip(120 + 60 * np.sin(xx / 18), 0, 255)
    albedo[..., 1] = np.clip(100 + 40 * np.cos(yy / 16), 0, 255)
    albedo[..., 2] = 85
    albedo[~mask] = [245, 245, 245]

    depth = np.clip((0.35 + 0.55 * (1 - np.sqrt(np.minimum(1, x*x + y*y)))) * 255, 0, 255).astype(np.uint8)
    depth[~mask] = 0

    Image.fromarray(albedo, "RGB").save(out / "albedo.png")
    Image.fromarray(alpha, "L").save(out / "alpha.png")
    Image.fromarray(depth, "L").save(out / "depth.png")
    print(f"wrote synthetic maps to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
