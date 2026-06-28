# Tutorial — Local Orchestrator Smoke Test

This tutorial validates Bloc 2 without Blender, ComfyUI or GPU.

```bash
pip install -e packages/sfb_orchestrator[dev]

sfb-orch --workspace workspace init \
  --project-id demo \
  --name Demo

sfb-orch --workspace workspace jobs create \
  --project-id demo \
  --engine noop \
  --param hello='"world"'

sfb-orch --workspace workspace jobs run-next \
  --project-id demo

sfb-orch --workspace workspace artifacts list \
  --project-id demo
```

Expected result: one completed job and one `job_report` artifact.

Start the API:

```bash
SFB_WORKSPACE=workspace sfb-api
```

Open:

```text
http://127.0.0.1:8765/health
```

Optional Studio UI:

```bash
cd apps/sfb_studio
npm install
npm run dev
```
