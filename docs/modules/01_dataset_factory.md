# Bloc 1 — Dataset Factory + ViewContract

The Dataset Factory turns source GLB/GLTF assets into a controlled, reproducible multiview dataset.

It is the source of truth for:

- asset IDs;
- source hashes;
- Gold/Silver/Bronze/rejected tiers;
- fixed camera angles;
- capture output paths;
- train/val/test splits;
- training-ready manifests.

## Current v2.1 status

Implemented:

- `ViewContract` loader and validation;
- GLB/GLTF folder scanner;
- enriched `dataset_manifest` model;
- deterministic train/val/test/holdout split by asset;
- capture plan JSONL generation;
- expected view attachment to a manifest;
- capture output validation;
- dataset stats/report CLI;
- Blender turntable renderer script.

Not implemented yet:

- automatic visual quality scoring;
- caption normalization UI;
- public dataset importers;
- LoRA/ViewAdapter dataset exporters.

## ViewContract

Example:

```bash
sfb-dataset validate-contract examples/view_contracts/MV8_OBJECT.json
```

A contract defines known cameras. The model and baker never guess the angle.

```text
view_id → azimuth/elevation → render camera → splat extraction camera → scene rotation
```

## Scan GLB/GLTF files

```bash
sfb-dataset scan-glb ./sources/glb \
  --dataset-id medieval_gold_v0 \
  --tier gold_candidate \
  --category uncategorized \
  --style-family mixed \
  --source-license internal \
  --out workspace/manifests/medieval_gold_v0.json
```

The scanner records stable source hashes and asset IDs.

Default asset ID policy:

```text
<file_stem_slug>_<sha256_prefix>
```

For test datasets, use sequential IDs:

```bash
sfb-dataset scan-glb ./sources/glb \
  --dataset-id test \
  --id-policy sequential \
  --out workspace/manifests/test.json
```

## Build a capture plan

```bash
sfb-dataset make-capture-plan workspace/manifests/medieval_gold_v0.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --renders-root workspace/renders/medieval_gold_v0 \
  --out workspace/plans/medieval_gold_mv8.jsonl
```

The capture plan is JSONL. Each row is one render job:

```json
{
  "schema": "sfb.capture_plan_entry.v1",
  "dataset_id": "medieval_gold_v0",
  "asset_id": "wall_a_3f2e...",
  "source_path": "sources/glb/wall_a.glb",
  "view_contract": "MV8_OBJECT",
  "view_id": "front_right",
  "azimuth_deg": 45,
  "elevation_deg": 10,
  "outputs": {
    "rgb": "workspace/renders/.../rgb.png",
    "alpha": "workspace/renders/.../alpha.png",
    "depth": "workspace/renders/.../depth.exr",
    "normal": "workspace/renders/.../normal.png",
    "camera": "workspace/renders/.../camera.json"
  }
}
```

## Attach expected views to manifest

Before or after rendering, attach the expected output paths:

```bash
sfb-dataset attach-expected-views workspace/manifests/medieval_gold_v0.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --renders-root workspace/renders/medieval_gold_v0 \
  --out workspace/manifests/medieval_gold_v0_mv8_expected.json
```

## Render a single GLB with Blender

```bash
blender --background --python tools/render_glb_turntable.py -- \
  --input sources/glb/wall_a.glb \
  --asset-id wall_a \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --out workspace/renders/wall_a \
  --resolution 1024
```

Outputs per view:

```text
front/
├─ rgb.png
├─ alpha.png
├─ depth.exr
├─ normal.png
└─ camera.json
```

## Validate expected capture outputs

```bash
sfb-dataset validate-captures workspace/manifests/medieval_gold_v0_mv8_expected.json \
  --out workspace/reports/capture_validation.json
```

## Split by asset

```bash
sfb-dataset split workspace/manifests/medieval_gold_v0_mv8_expected.json \
  --seed 1337 \
  --train 0.7 \
  --val 0.15 \
  --test 0.15 \
  --out workspace/splits/medieval_gold_v0_split.json \
  --write-manifest workspace/manifests/medieval_gold_v0_mv8_split.json
```

Splits are by asset, never by image, to avoid view leakage.

## Stats

```bash
sfb-dataset stats workspace/manifests/medieval_gold_v0_mv8_split.json
```

## Definition of done for this block

The block is usable when you can:

1. scan a GLB folder;
2. validate a ViewContract;
3. create a capture plan;
4. render or schedule fixed views;
5. attach expected views;
6. split by asset;
7. validate which captures exist;
8. generate a dataset report.
