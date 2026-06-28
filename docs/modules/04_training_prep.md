# Bloc 4 — Training Prep

Bloc 4 turns curated dataset manifests into reproducible training exports.

It does **not** train models yet. It prepares clean, versioned datasets for:

- LoRA clean-render training;
- view-adapter / image-to-target-view training;
- fixed evaluation sets.

The guiding rule is that the training data must preserve the SFB contracts:

```text
asset-level split
+ known ViewContract
+ Gold / Silver / Bronze tier labels
+ clean captions
+ reproducible export hash
```

## Commands

Install the package:

```bash
pip install -e packages/sfb_training[dev]
```

Summarize a manifest:

```bash
sfb-trainprep report workspace/manifests/medieval_gold_v0_mv8_split.json
```

Export a LoRA clean-render dataset:

```bash
sfb-trainprep export-lora workspace/manifests/medieval_gold_v0_mv8_split.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --out training_exports/lora_clean_render_v0 \
  --export-id lora_clean_render_v0 \
  --tiers gold,gold_candidate \
  --overwrite
```

Export source→target view pairs:

```bash
sfb-trainprep export-view-pairs workspace/manifests/medieval_gold_v0_mv8_split.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --pair-policy front_to_all \
  --out training_exports/view_adapter_v0 \
  --export-id view_adapter_v0 \
  --overwrite
```

Create a fixed eval set:

```bash
sfb-trainprep make-eval-set workspace/manifests/medieval_gold_v0_mv8_split.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --task clean_render \
  --split test \
  --out training_exports/eval_clean_render_v0 \
  --overwrite
```

## LoRA clean-render export

The LoRA export creates:

```text
lora_clean_render_v0/
├─ images/<split>/...
├─ captions/<split>/...
├─ metadata.jsonl
├─ train.jsonl
├─ val.jsonl
├─ test.jsonl
├─ config.json
├─ config.yaml
└─ reports/dataset_report.json
```

Captions intentionally put the clean-render behavior first:

```text
sfb_clean_render, orthographic object render, centered single asset,
solid neutral background, neutral soft lighting, no cast shadow,
no bloom, no cinematic lighting, no particles, no text,
clean silhouette, trellis friendly image, splat friendly image,
front view, ruined wall, worn stone blocks
```

The LoRA should learn the image format, not a unique game style.

## View-pair export

The view-adapter export creates examples like:

```json
{
  "source_view_id": "front",
  "target_view_id": "right",
  "target_azimuth_deg": 90,
  "caption_text": "sfb_clean_render, image to target view translation, ..."
}
```

Supported initial pair policies:

- `front_to_all`;
- `front_to_cardinal`;
- `adjacent`;
- `all_to_all`;
- `custom` with `--source-views` and `--target-views`.

## Quality rules

Training Prep filters by:

- data tier;
- asset quality status;
- split;
- view availability;
- view status;
- RGB file existence unless `--allow-missing` is used.

The split must be created at asset level by Bloc 1. Bloc 4 reports leakage if one asset appears across multiple splits in an export.

## Gold / Silver / Bronze

The `data_tier` field is preserved in every exported row.

Recommended use:

```text
Gold   → main train/val/test source
Silver → optional diversity, lower sampling weight later
Bronze → generated/Wan data, never test truth by default
```

## Definition of done

Bloc 4 is usable when it can:

1. summarize a manifest;
2. export a LoRA clean-render dataset;
3. export view-pair records;
4. create eval sets;
5. produce composition reports and leakage reports;
6. reproduce the same export from the same manifest and settings.
