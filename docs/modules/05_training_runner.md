# Bloc 5 — Training Runner

This module turns Training Prep exports into versioned training runs, checkpoints, evaluation reports and approved model aliases.

## Current v2.5 scope

Working:

- `sfb-train init-run` creates `runs/<run_id>/run.json`.
- `sfb-train command` generates a reproducible Diffusers/Kohya/shell command.
- `sfb-train run --dry-run` writes `command.sh` without requiring GPU training.
- checkpoint scanning detects `checkpoints/checkpoint-*` folders and `.safetensors` files.
- `sfb-train eval-clean-render` scores generated images for neutral-background / centered-object compatibility.
- `sfb-train promote` writes `model_registry.json`.
- `sfb-train export-comfy` copies an approved `.safetensors` into ComfyUI `models/loras`.

Not yet implemented:

- full View Adapter training.
- pipeline eval through ComfyUI → TripoSplat → SFB Baker.
- live Studio UI training panel.
