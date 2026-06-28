# Tutorial — Training Prep exports

This tutorial assumes you already have a dataset manifest with attached view paths and asset-level splits.

## 1. Inspect the manifest

```bash
sfb-trainprep report workspace/manifests/medieval_gold_v0_mv8_split.json \
  --out workspace/reports/training_readiness.json
```

Check:

- tier distribution;
- split distribution;
- view counts;
- missing RGB count.

## 2. Export LoRA clean-render data

```bash
sfb-trainprep export-lora workspace/manifests/medieval_gold_v0_mv8_split.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --out training_exports/lora_clean_render_v0 \
  --export-id lora_clean_render_v0 \
  --tiers gold,gold_candidate \
  --quality-statuses approved,needs_review,unreviewed \
  --overwrite
```

Output:

```text
training_exports/lora_clean_render_v0/
├─ metadata.jsonl
├─ train.jsonl
├─ val.jsonl
├─ test.jsonl
├─ config.json
└─ reports/dataset_report.json
```

## 3. Export view-adapter pairs

```bash
sfb-trainprep export-view-pairs workspace/manifests/medieval_gold_v0_mv8_split.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --pair-policy front_to_all \
  --out training_exports/view_adapter_v0 \
  --export-id view_adapter_v0 \
  --overwrite
```

For a smaller first experiment:

```bash
sfb-trainprep export-view-pairs workspace/manifests/medieval_gold_v0_mv8_split.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --pair-policy custom \
  --source-views front \
  --target-views front_right,right,front_left,left \
  --out training_exports/view_adapter_small_v0 \
  --overwrite
```

## 4. Create eval items

```bash
sfb-trainprep make-eval-set workspace/manifests/medieval_gold_v0_mv8_split.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --task clean_render \
  --split test \
  --max-assets 32 \
  --out training_exports/eval_clean_render_v0 \
  --overwrite
```

The eval set is deliberately fixed so future checkpoints can be compared fairly.
