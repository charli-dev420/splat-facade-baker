# MVP Demos And Local Gates

The MVP demo contract is intentionally narrow: every demo must either run
locally with repository assets or report a clear blocked state for an external
dependency. Do not present TripoSplat, View Adapter or splat rendering as a
working demo until their real workflows are validated.

## Demo 1: Maps To SFB Package

This is the stable MVP path.

```bash
python tools/make_synthetic_maps.py --out examples/synthetic
sfb bake-maps \
  --albedo examples/synthetic/albedo.png \
  --alpha examples/synthetic/alpha.png \
  --depth examples/synthetic/depth.png \
  --name DemoWall \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --view-id front \
  --out exports/DemoWall
```

Acceptance: `exports/DemoWall/asset.sfb.json`, textures, meshes, collider proxy,
previews and report are created.

## Demo 2: Unity Import Smoke

This gate validates the Editor package against the checked-in DemoWall package
and scene graph.

```powershell
.\tools\unity_import_smoke.ps1
```

Default Unity executable:

```text
C:\Program Files\Unity\Hub\Editor\6000.3.18f1\Editor\Unity.exe
```

Acceptance: the script creates `workspace/unity_smoke/`, imports
`asset.sfb.json` and `demo_lane.sfbscene.json` in batchmode, and writes
`SFBUnitySmokeReport.json`. A missing Unity install or import error is a failed
or blocked gate, not a passed demo.

## Demo 3: ComfyUI Orchestrator Gate

This gate proves SFB orchestration separately from live generation.

```bash
python tools/comfyui_demo_gate.py --workspace workspace/comfyui_demo_gate
```

Acceptance: the dry-run fixture creates an injected workflow artifact. Live
generation is only attempted when a ComfyUI server is reachable and the operator
provides a real metadata file:

```bash
python tools/comfyui_demo_gate.py \
  --comfy-url http://127.0.0.1:8188 \
  --live-metadata path/to/real_workflow.metadata.json
```

If the server is unavailable, the report must say
`blocked_comfyui_unavailable`. That is an honest blocked result, not a failure
of the MVP dry-run gate.
