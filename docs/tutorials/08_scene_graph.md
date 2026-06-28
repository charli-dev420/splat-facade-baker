# Tutorial — Build a small 2.5D SFB scene

Install the scene package:

```bash
pip install -e packages/sfb_scene[dev]
```

Create a scene:

```bash
sfb-scene create --scene-id demo_lane --out workspace/scenes/demo_lane.sfbscene.json
```

Add a chunk:

```bash
sfb-scene add-chunk workspace/scenes/demo_lane.sfbscene.json \
  --chunk-id chunk_001 \
  --name lane_start \
  --replace
```

Add a card using the included demo SFB package:

```bash
sfb-scene add-card workspace/scenes/demo_lane.sfbscene.json \
  --scene-card-id demo_wall_001 \
  --asset-package examples/sfb_packages/DemoWall/asset.sfb.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --view-id front \
  --chunk-id chunk_001 \
  --replace
```

Add a second card with a fixed ViewContract angle:

```bash
sfb-scene add-card workspace/scenes/demo_lane.sfbscene.json \
  --scene-card-id demo_wall_002 \
  --asset-package examples/sfb_packages/DemoWall/asset.sfb.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --view-id front_right \
  --position 7.5,0,0.25 \
  --chunk-id chunk_001 \
  --replace
```

Update chunk bounds and validate:

```bash
sfb-scene update-chunk-bounds workspace/scenes/demo_lane.sfbscene.json --chunk-id chunk_001
sfb-scene validate workspace/scenes/demo_lane.sfbscene.json --out workspace/scenes/demo_lane_report.json
```

The scene can later be copied into Unity alongside its referenced packages. Unity v2.8 includes an Editor-only `.sfbscene.json` importer scaffold.
