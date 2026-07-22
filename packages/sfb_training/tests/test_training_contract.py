from __future__ import annotations

from pathlib import Path

import pytest

from sfb_training.config_io import read_config
from sfb_training.runners.base import build_training_command


def test_placeholder_training_backend_is_not_public() -> None:
    with pytest.raises(ValueError, match="Unsupported training backend: placeholder"):
        build_training_command({"backend": "placeholder"}, Path("runs/placeholder"))


def test_public_training_config_uses_supported_backend() -> None:
    config_path = Path(__file__).resolve().parents[3] / "examples" / "training_configs" / "lora_clean_render_diffusers.yaml"
    config = read_config(config_path)

    command = build_training_command(config, Path("runs/clean_render_lora_v0"))

    assert config["backend"] in {"diffusers", "kohya", "shell"}
    assert command
    assert command[0] == "accelerate"
