#!/usr/bin/env bash
set -euo pipefail
pytest packages/sfb_core/tests packages/sfb_dataset/tests packages/sfb_orchestrator/tests packages/sfb_training/tests packages/sfb_scene/tests
python tools/make_synthetic_maps.py --out examples/synthetic
sfb bake-maps \
  --albedo examples/synthetic/albedo.png \
  --alpha examples/synthetic/alpha.png \
  --depth examples/synthetic/depth.png \
  --name CIWall \
  --width-m 8 \
  --height-m 4 \
  --max-depth-m 0.45 \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --view-id front \
  --out exports/CIWall
python tools/validate_sfb_package.py exports/CIWall/asset.sfb.json
sfb-dataset validate-contract examples/view_contracts/MV8_OBJECT.json
sfb-scene validate examples/scenes/demo_lane.sfbscene.json
