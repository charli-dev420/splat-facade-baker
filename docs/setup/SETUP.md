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

- ComfyUI for generation and splat workflows.
- Blender for GLB turntable captures.
- Unity for prefab import.

## Full Python test pass

```bash
pytest
```
