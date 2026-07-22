# Changelog


## v2.9 — Private repo ready

- Hardened the local orchestrator API file serving, job creation and shell execution boundaries.
- Added atomic job claiming, bounded auto-retry, strict workspace-scoped output registration and artifact de-duplication.
- Clarified the MVP contract: `bake-splat` is experimental/non-MVP, public Training and ComfyUI examples no longer ship placeholders, and local demo gates are documented.
- Fixed bake validation so corrupt package/report JSON returns `invalid_package_json` instead of empty metrics.
- Added GitHub issue templates and PR template.
- Added project status, known limitations, release notes and roadmap of pursuit.
- Added private GitHub setup guide.
- Added dev bootstrap and smoke-test helper scripts.
- Removed generated workspace artifacts from the prepared repository.

## v2.8 — Scene Graph 2.5D

- Added functional `sfb-scene` CLI.
- Added SceneCard, ChunkGroup, placement helpers and scene validation.
- Added ViewContract-based rotation resolution for scene cards.
- Added chunk bounds computation and simple edge alignment.
- Updated `scene.sfbscene.json` schema and added `scene_report.schema.json`.
- Added example `examples/scenes/demo_lane.sfbscene.json`.
- Added Studio API `/api/scenes` and `/api/scenes/validate` endpoints.
- Added Studio UI Scenes page.
- Added Unity `.sfbscene.json` importer scaffold and scene/card metadata components.

## v2.7 — Unity Importer / Mobile Package

- Added Unity Editor package `dev.splatfacadebaker.unity-importer`.
- Added `.sfb.json` ScriptedImporter.
- Added `.sfbmesh.json` mesh parser and Unity Mesh creation.
- Added prefab-like imported GameObject with Visual LOD children and LODGroup.
- Added `SFB/MobileDepthCard` cutout shader and material builder.
- Added primitive collider proxy import from `collider_proxy.json`.
- Expanded `SFBAssetMetadata`.
- Added mobile validator, importer window, selected package validation/reimport tools and texture settings utility.
- Added `sfbmesh` and collider proxy schemas plus Unity docs/tutorial.

## v2.6 — Studio UI

- Added React/Vite/TypeScript Studio UI pages for dashboard, review queue, assets, jobs, artifacts, bakes, training, workflows and settings.
- Added FastAPI endpoints for summary, review actions, job logs, bakes, training run listing and model registry.
- Added UI docs and smoke-test tutorial.
- Added API smoke coverage for summary, logs, asset review and review queue.

## v2.5 — Training Runner

- Added `sfb-train` CLI.
- Added TrainingRun registry and checkpoint scanner.
- Added Diffusers/Kohya command generation and dry-run support.
- Added clean-render image evaluation reports.
- Added model registry promotion and ComfyUI LoRA export.
- Added model card generation and Training Runner docs/tests.

## v2.4 — Training Prep exports

- Added `sfb-trainprep` CLI.
- Added LoRA clean-render dataset export with images, captions, JSONL splits, config and report.
- Added view-adapter source→target pair export with fixed ViewContract metadata.
- Added fixed eval set exporter for clean-render and view-adapter tasks.
- Added training dataset readiness reports.
- Added leakage reports to verify asset-level split separation.
- Added public schemas for training export records.
- Added Bloc 4 docs, tutorial and tests.

## v2.3 — Baker Core cleanup + LODs

- Added deterministic alpha/depth cleanup in `sfb_core`.
- Added small component removal, hole filling, depth percentile clipping and masked depth smoothing.
- Added mask texture export.
- Added LOD0/LOD1/LOD2 export.
- Added far LOD flat-card option.
- Added `.sfbmesh.json` normals and mesh counts.
- Added mobile preset warnings and richer `bake_report.json`.
- Added experimental `bake-splat` scaffold for future canonical splat rendering.
- Added Bloc 3 docs and tests.


## v2.2 — Orchestrator local + ComfyUI background

- Added `sfb-orch` CLI.
- Added `sfb-api` FastAPI local service.
- Added SQLite registry for projects, assets, workflows, jobs and artifacts.
- Added local job runner with `noop`, `shell`, `sfb_bake_maps`, `blender_capture` and `comfyui` engines.
- Added ComfyUI client and workflow template injection.
- Added ComfyUI dry-run jobs.
- Added capture-plan to Blender job batching.
- Added orchestrator tests and API smoke test.
- Updated Studio UI dashboard to read projects, assets, jobs, artifacts and ComfyUI status.
- Added docs for Bloc 2.

## v2.1 — Dataset Factory

- Added ViewContract validation.
- Added GLB/GLTF scanner.
- Added dataset manifest enrichment.
- Added capture plan JSONL.
- Added MV16 training contract.
- Added Blender turntable renderer script.


## 0.2.1-pre

- Makes Bloc 1 — Dataset Factory usable from CLI.
- Adds `sfb-dataset validate-contract`.
- Adds GLB/GLTF scanner with source hashing and stable asset IDs.
- Adds enriched dataset manifest models.
- Adds JSONL capture plan generation.
- Adds expected view path attachment.
- Adds capture output validation.
- Adds deterministic train/val/test/holdout split by asset.
- Adds MV16 training ViewContract.
- Replaces Blender turntable placeholder with a functional Blender script skeleton for RGB/alpha/depth/normal/camera outputs.
- Adds dataset factory tests.

## 0.2.0-pre

- Introduces public repo v2 scaffold.
- Adds ViewContract, Dataset, Asset, Scene and TrainingRun schema drafts.
- Keeps `maps → depth-card` as the runnable pre-MVP core path.
