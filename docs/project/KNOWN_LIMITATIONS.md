# Known Limitations

## External tool validation

The repository includes scaffolds for Unity, Blender and ComfyUI, but these integrations need validation on the target machine:

- Unity: compile the UPM package and test `.sfb.json` and `.sfbscene.json` imports.
- Blender: run `tools/render_glb_turntable.py` on real GLB assets and inspect RGB/alpha/depth/normal outputs.
- ComfyUI: connect to a live ComfyUI server, inject workflow templates, and collect outputs.

## Splat backend

The `bake-splat` command is intentionally scaffolded but not implemented. The current stable path is:

```text
albedo + alpha + depth → cleanup → depth-card → SFB package
```

The planned path is:

```text
splat + ViewContract camera → RGB/alpha/depth → same bake-maps pipeline
```

## Training

The Training Runner generates reproducible commands and dry-runs. Real GPU training depends on local Diffusers/Kohya setup, model licenses, dataset availability, and GPU memory.

## Data policy

Do not commit private GLB assets, generated datasets, model weights, or production outputs into the public/private source repository. Use external storage or Git LFS only after an explicit decision.
