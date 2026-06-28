# Bloc 3 — Splat / Map Baker Core

The Baker Core is the runtime-independent part of SFB that turns a known view into a lightweight mobile asset.

It does **not** try to reconstruct a clean 360° model. It extracts the useful visible surface for a known `view_id` and packages it as a 2.5D asset.

```text
albedo + alpha + depth
→ deterministic alpha/depth cleanup
→ depth-card / flat-card mesh
→ LODs
→ textures
→ collider proxy
→ asset.sfb.json
→ bake_report.json
```

## Current v2.3 status

Implemented:

- `sfb bake-maps` remains the stable MVP path.
- deterministic alpha/depth cleanup;
- small component removal;
- optional largest-component mode;
- small hole filling;
- depth percentile clipping;
- masked depth smoothing;
- normal map generation from cleaned depth;
- mask texture export;
- LOD0/LOD1/LOD2 mesh export;
- default far LOD flat-card;
- `.glb`, `.obj` and `.sfbmesh.json` export per LOD;
- mobile preset warnings;
- richer `bake_report.json` with cleanup and mobile metrics;
- `bake-splat` command scaffold for the future gsplat backend.

Not implemented yet:

- gsplat-backed canonical splat rendering;
- adaptive contour-preserving triangulation;
- true layered cards;
- multi-angle impostor runtime logic;
- advanced AI cleanup.

## Why maps first?

`maps → depth-card` isolates the deterministic asset-building problem before adding splat rendering complexity.

Once `splat → RGB/alpha/depth` exists, it will feed the same code path:

```text
splat + known camera
→ RGB / alpha / depth
→ sfb bake-maps core
```

## Main command

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

## Cleanup controls

```bash
--remove-components-smaller-than-px 32
--keep-largest-component
--fill-holes-smaller-than-px 64
--depth-clip-low-percentile 1
--depth-clip-high-percentile 99
--depth-smooth-radius 1
--edge-feather-px 0
--no-cleanup
--save-clean-debug
```

Default cleanup is intentionally conservative. Use `--keep-largest-component` only when a single connected object is expected; it can remove valid disconnected pieces.

## LOD controls

```bash
--lod-count 3
--lod1-grid-scale 0.5
--lod2-grid-scale 0.25
--lod2-mode flat_card
```

Default output:

```text
LOD0 = depth-card
LOD1 = lower-grid depth-card
LOD2 = flat-card
```

This is designed for mobile where far distance often benefits more from a cheap card than a noisy depth surface.

## Package output

```text
exports/DemoWall/
├─ asset.sfb.json
├─ mesh/
│  ├─ DemoWall_LOD0.glb
│  ├─ DemoWall_LOD0.obj
│  ├─ DemoWall_LOD0.sfbmesh.json
│  ├─ DemoWall_LOD1.glb
│  ├─ DemoWall_LOD1.obj
│  ├─ DemoWall_LOD1.sfbmesh.json
│  ├─ DemoWall_LOD2.glb
│  ├─ DemoWall_LOD2.obj
│  └─ DemoWall_LOD2.sfbmesh.json
├─ textures/
│  ├─ DemoWall_Albedo.png
│  ├─ DemoWall_Alpha.png
│  ├─ DemoWall_Depth.png
│  ├─ DemoWall_Normal.png
│  └─ DemoWall_Mask.png
├─ collision/
│  └─ collider_proxy.json
├─ preview/
│  ├─ DemoWall_preview.png
│  └─ DemoWall_depth_preview.png
└─ reports/
   └─ DemoWall_report.json
```

## Splat backend scaffold

The command exists but intentionally returns `not_implemented` in v2.3:

```bash
sfb bake-splat \
  --input splats/wall_front.ply \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --view-id front \
  --width-m 8 \
  --height-m 4 \
  --max-depth-m 0.45 \
  --out exports/wall_front
```

The planned implementation is:

```text
PLY/SPZ/SPLAT
→ canonical camera from ViewContract
→ RGB + alpha + expected depth
→ same bake-maps pipeline
```
