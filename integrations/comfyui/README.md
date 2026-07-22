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

## MVP Contract

ComfyUI is an external local worker. SFB owns orchestration, artifact inventory,
post-processing decisions and Unity handoff. Public MVP examples do not include
fake workflows or no-op demos.

## Dry-run gate

```bash
python tools/comfyui_demo_gate.py --workspace workspace/comfyui_demo_gate
```

This writes an injected workflow artifact from a test fixture without contacting
ComfyUI. It proves the orchestrator path, not generation quality.

Live validation requires a reachable ComfyUI server and a real operator-owned
metadata file:

```bash
python tools/comfyui_demo_gate.py \
  --comfy-url http://127.0.0.1:8188 \
  --live-metadata path/to/real_workflow.metadata.json
```

## Live status

```bash
sfb-orch comfy status --url http://127.0.0.1:8188
```

Custom nodes remain experimental scaffolds. The preferred MVP path is API
orchestration, not putting the whole SFB pipeline inside ComfyUI nodes.
