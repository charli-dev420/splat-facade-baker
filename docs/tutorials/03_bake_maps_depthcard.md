# Tutorial — Bake maps into a mobile depth-card

This tutorial exercises Bloc 3 without ComfyUI, Blender, Unity, GPU or splats.

## 1. Install

```bash
pip install -e packages/sfb_core[dev]
```

## 2. Create synthetic maps

```bash
python tools/make_synthetic_maps.py --out examples/synthetic
```

## 3. Bake a package

```bash
sfb bake-maps \
  --albedo examples/synthetic/albedo.png \
  --alpha examples/synthetic/alpha.png \
  --depth examples/synthetic/depth.png \
  --name DemoWall \
  --width-m 8 \
  --height-m 4 \
  --max-depth-m 0.45 \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --view-id front \
  --grid 96 \
  --lod-count 3 \
  --texture-size 1024 \
  --out exports/DemoWall
```

## 4. Validate files exist

```bash
python tools/validate_sfb_package.py exports/DemoWall/asset.sfb.json
```

Expected:

```json
{
  "ok": true,
  "missing": []
}
```

## 5. Inspect the report

Open:

```text
exports/DemoWall/reports/DemoWall_report.json
```

Useful fields:

```text
cleanup.removed_components
cleanup.filled_holes
metrics.triangles_lod0
metrics.lods
metrics.alpha_coverage
metrics.depth_range_m
metrics.estimated_texture_memory_mb_uncompressed
warnings
```
