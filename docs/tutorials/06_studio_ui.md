# Tutorial — Launch SFB Studio UI

## 1. Install the orchestrator

```bash
pip install -e packages/sfb_orchestrator[dev]
```

## 2. Initialize a workspace

```bash
sfb-orch --workspace workspace init --project-id demo --name Demo
```

## 3. Start the API

```bash
SFB_WORKSPACE=workspace sfb-api
```

Check:

```text
http://127.0.0.1:8765/health
```

## 4. Start the UI

```bash
cd apps/sfb_studio
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## 5. Smoke test with a noop job

In another terminal:

```bash
sfb-orch --workspace workspace jobs create \
  --project-id demo \
  --engine noop \
  --param message='"hello studio"'
```

Then use the UI:

1. Open **Jobs**.
2. Click **Run next**.
3. Open the job drawer.
4. Check the generated logs and artifacts.

## 6. Review actions

The **Review Queue** page aggregates assets, jobs and bakes needing human decision. Use it for quick approve/reject/retry actions during batch production.
