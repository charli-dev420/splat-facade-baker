# ComfyUI Integration

Current v2.2 integration is orchestrator-first:

```text
SFB Orchestrator
→ workflow metadata
→ workflow template injection
→ ComfyUI /prompt
→ history/output refs
→ artifact registry
```

ComfyUI is treated as a background worker. The local registry remains the source of truth for jobs and artifacts.

## Dry-run test

```bash
sfb-orch --workspace workspace workflows register \
  workflows/comfyui/examples/noop_comfy.metadata.json \
  --project-id demo

sfb-orch --workspace workspace jobs create \
  --project-id demo \
  --engine comfyui \
  --workflow-id noop_comfy_image_v1 \
  --param input_image='"asset_front.png"' \
  --param filename_prefix='"SFB/test"' \
  --param dry_run=true

sfb-orch --workspace workspace jobs run-next --project-id demo
```

This writes the injected workflow as an artifact without contacting ComfyUI.

## Live status

```bash
sfb-orch comfy status --url http://127.0.0.1:8188
```

Custom nodes remain placeholders. The preferred pre-MVP path is API orchestration, not putting the whole SFB pipeline inside ComfyUI nodes.
