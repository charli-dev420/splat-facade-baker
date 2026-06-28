# Roadmap

## Phase 0 — Public scaffold

- [x] Monorepo structure.
- [x] Core CLI pre-MVP.
- [x] Public schemas.
- [x] ViewContract examples.
- [x] Module documentation.

## Phase 1 — Core MVP

- [x] `bake-maps` command.
- [x] Synthetic example.
- [x] Asset package JSON.
- [x] Basic report.
- [x] Alpha/depth cleanup pass.
- [ ] Adaptive mesh simplification.
- [x] LOD generation.
- [ ] Schema validation in CLI.

## Phase 2 — Dataset Factory

- [x] GLB/GLTF scanner.
- [x] ViewContract validation.
- [x] MV8/FACADE8 contracts.
- [x] Dataset manifest writer.
- [x] Capture plan JSONL generator.
- [x] Expected views attachment.
- [x] Asset-level split writer.
- [x] Capture output validation.
- [x] Dataset stats/report.
- [x] Blender turntable renderer script.
- [ ] Visual quality gates and automatic scoring.
- [x] MV16 training contract.
- [x] Caption normalization/export for Training Prep.
- [ ] Batch renderer orchestration through Bloc 2.

## Phase 3 — Orchestrator

- [x] FastAPI backend.
- [x] SQLite registry.
- [x] Job queue.
- [x] ComfyUI API client.
- [x] Artifact registry.
- [x] Workflow templates.
- [x] ComfyUI dry-run injection jobs.
- [x] Capture-plan to Blender job creation.
- [x] Local worker loop.
- [ ] Parallel workers.
- [ ] Robust ComfyUI output file collection.
- [ ] Job cancellation for external subprocesses.
- [ ] WebSocket live UI events.

## Phase 4 — Studio UI

- [x] Dashboard connected to local API.
- [x] Assets page.
- [x] Jobs page with actions and logs.
- [x] Artifacts page.
- [x] Bakes page.
- [x] Review queue.
- [x] Training runs / model registry pages.
- [x] Workflows and settings pages.
- [ ] Live websocket events.
- [ ] 3D viewer for GLB/depth-card previews.

## Phase 5 — Unity importer

- [x] `asset.sfb.json` importer.
- [x] `.sfbmesh.json` mesh import.
- [x] Material builder using simple mobile cutout shader.
- [x] Prefab-like imported asset builder.
- [x] LODGroup.
- [x] Collider proxy.
- [x] Metadata component.
- [x] Mobile validator.
- [x] Texture import settings utility.
- [ ] Test package inside a real Unity project.
- [ ] Add optional scene importer after Bloc 8.

## Phase 6 — Splat backend

- [ ] Canonical splat render path.
- [ ] RGB/alpha/depth output.
- [ ] `bake-splat` command.
- [ ] Splat preview reports.

## Phase 7 — Training

- [x] LoRA clean-render dataset exporter.
- [x] View-pair dataset exporter.
- [x] Training prep reports and leakage checks.
- [x] Fixed eval set exporter.
- [x] Training run registry scaffold.
- [x] LoRA training runner command generation / dry-run.
- [x] Checkpoint registry.
- [x] Clean-render eval reports from generated images.
- [x] Model registry promotion and ComfyUI export.
- [ ] Real GPU training execution validation on user machine.
- [ ] Pipeline eval: ComfyUI → TripoSplat → SFB Baker.

## Phase 8 — Scene Graph 2.5D

- [x] SceneCard schema implementation.
- [x] Placement helpers.
- [x] Chunk validation.
- [x] Unity scene import scaffold.
- [ ] Native Unity scene import validation.
- [ ] Studio Scene Graph UX pass.

## v2.8 completed

- Scene Graph 2.5D package and CLI.
- Scene validation reports.
- Studio scene listing.
- Unity scene importer scaffold.

## v2.9 private repo ready

- GitHub issue templates and PR template.
- Project status document.
- Known limitations document.
- Roadmap of pursuit document.
- Private GitHub setup guide.
- Dev bootstrap and smoke-test scripts.
