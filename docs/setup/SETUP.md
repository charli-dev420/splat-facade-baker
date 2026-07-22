# Setup

## Core only

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e packages/sfb_core[dev]
pytest packages/sfb_core/tests
```

## Dataset Factory

```bash
pip install -e packages/sfb_dataset
pytest packages/sfb_dataset/tests
```

## Orchestrator + local API

```bash
pip install -e packages/sfb_orchestrator[dev]
pytest packages/sfb_orchestrator/tests

sfb-orch --workspace workspace init \
  --project-id demo \
  --name Demo

SFB_WORKSPACE=workspace sfb-api
```

Smoke test:

```bash
sfb-orch --workspace workspace jobs create \
  --project-id demo \
  --engine noop \
  --param hello='"world"'

sfb-orch --workspace workspace jobs run-next \
  --project-id demo
```

## Studio UI

```bash
cd apps/sfb_studio
npm install
npm run dev
```

The UI expects the API at:

```text
http://127.0.0.1:8765
```

## Optional tools

- ComfyUI for external generation workflows. Splat workflows remain experimental
  until a real operator-owned template is validated.
- Blender for GLB turntable captures.
- Unity for prefab import.

## Full Python test pass

```bash
pytest
```

## Complete validation gate

Run the deterministic repo gate and write a normalized proof report:

```bash
python tools/run_validation_pipeline.py --skip-slow
```

Reports are written under `workspace/validation_reports/`, including
`latest.json`, a timestamped JSON report and per-step stdout/stderr logs. The
gate uses `git -c safe.directory=<repo>` internally so it does not mutate global
Git config. To fix Windows dubious-ownership warnings permanently on this
checkout, run:

```bash
git config --global --add safe.directory D:/Dev/splat/splat-facade-baker-v2.8-scene-graph
```

Optional native checks:

```bash
python tools/run_validation_pipeline.py --include-blender
python tools/run_validation_pipeline.py --include-blender --fail-on-blocked
python tools/run_validation_pipeline.py --include-unity
python tools/run_validation_pipeline.py --include-comfy-live --fail-on-blocked
```

To inspect existing workspace content instead of only the deterministic
synthetic bake path, add:

```bash
python tools/run_validation_pipeline.py --skip-slow --real-workspace-smoke
```

Studio exposes the same report family on the Validation page through the local
API. The Studio run button uses `--skip-slow` by default and keeps Blender,
Unity, ComfyUI live and real workspace smoke as explicit options.

Blender certification renders `rgb.png`, `alpha.png`, `normal.png`,
`depth.exr` and `camera.json` for the requested views, then validates PNG
dimensions and camera metadata. Unity certification imports DemoWall and
`demo_lane_v0`, then verifies metadata, LOD/render/collider objects and
scene card/chunk counts. Missing Blender, Unity or license state is reported as
`blocked_*` unless `--fail-on-blocked` is used.
