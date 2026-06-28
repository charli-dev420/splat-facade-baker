# Tutorial — Training Runner Dry Run

```bash
pip install -e packages/sfb_training[dev]

sfb-train init-run \
  --config examples/training_configs/lora_clean_render_diffusers.yaml \
  --out runs/clean_render_lora_v0 \
  --overwrite

sfb-train command --run-dir runs/clean_render_lora_v0 --write
sfb-train run --run-dir runs/clean_render_lora_v0 --dry-run
```

To evaluate generated images:

```bash
sfb-train eval-clean-render --images path/to/images --run-dir runs/clean_render_lora_v0
```
