from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _open(path: str | Path) -> Image.Image:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    return Image.open(p)


def load_rgb(path: str | Path) -> np.ndarray:
    img = _open(path).convert("RGB")
    return np.asarray(img, dtype=np.float32) / 255.0


def load_luma(path: str | Path) -> np.ndarray:
    img = _open(path).convert("L")
    return np.asarray(img, dtype=np.float32) / 255.0


def save_rgb(path: str | Path, arr: np.ndarray) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), mode="RGB").save(path)


def save_luma(path: str | Path, arr: np.ndarray) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), mode="L").save(path)
