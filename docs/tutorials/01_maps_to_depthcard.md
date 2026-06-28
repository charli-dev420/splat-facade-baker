# Tutorial: maps to depth-card

This is the shortest end-to-end path through the runnable core.

```bash
pip install -e packages/sfb_core[dev]
python tools/make_synthetic_maps.py --out examples/synthetic

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

python tools/validate_sfb_package.py exports/DemoWall/asset.sfb.json
```

The package includes cleaned textures, LOD meshes, a collider proxy and a richer bake report.
