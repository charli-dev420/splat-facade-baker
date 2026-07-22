# sfb_training

Training preparation and run-registry tools for Splat Facade Baker.

Implemented:

- `sfb-trainprep report`
- `sfb-trainprep export-lora`
- `sfb-trainprep export-view-pairs`
- `sfb-trainprep make-eval-set`
- `sfb-trainprep freeze-manifest`
- `sfb-train init-run`
- `sfb-train command`
- `sfb-train run --dry-run`
- `sfb-train checkpoints`
- `sfb-train eval-clean-render`
- `sfb-train promote`
- `sfb-train export-comfy`

The public MVP supports reproducible command generation, dry-runs, checkpoint
registry, clean-render evaluation and model registry operations. Real GPU
training still depends on a local Diffusers or Kohya environment; placeholder
training backends are not supported.
