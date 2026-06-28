# Tutorial — Render GLB turntable captures

This tutorial shows the intended Dataset Factory flow for controlled multiview rendering.

## 1. Scan source assets

```bash
sfb-dataset scan-glb ./sources/glb \
  --dataset-id medieval_gold_v0 \
  --tier gold_candidate \
  --source-license internal \
  --out workspace/manifests/medieval_gold_v0.json
```

## 2. Validate the view contract

```bash
sfb-dataset validate-contract examples/view_contracts/MV8_OBJECT.json
```

## 3. Create the capture plan

```bash
sfb-dataset make-capture-plan workspace/manifests/medieval_gold_v0.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --renders-root workspace/renders/medieval_gold_v0 \
  --out workspace/plans/medieval_gold_mv8.jsonl
```

## 4. Render one asset manually with Blender

```bash
blender --background --python tools/render_glb_turntable.py -- \
  --input sources/glb/wall_a.glb \
  --asset-id wall_a \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --out workspace/renders/medieval_gold_v0/wall_a \
  --resolution 1024
```

The orchestrator will later consume the capture plan and launch these jobs automatically.
