# Project Status

Status: **private pre-MVP / repo-ready v2.9**.

This repository contains the full scaffold and the first executable paths for Splat Facade Baker.

## Implemented and smoke-tested in this environment

- `sfb_core`: synthetic maps → depth-card SFB package.
- `sfb_dataset`: ViewContract validation, GLB/GLTF scan, capture plans, expected views, splits, capture validation.
- `sfb_orchestrator`: local SQLite registry, jobs, artifacts, workflows, FastAPI API, ComfyUI API orchestration and dry-run fixtures.
- `sfb_training`: training prep exports, TrainingRun registry, command generation, dry-run runner, clean-render image evaluation, model registry.
- `sfb_scene`: SceneCard and chunk scene graph CLI with validation.
- `apps/sfb_studio`: React/Vite app builds successfully.

## Implemented but not validated in native tools here

- Blender turntable rendering must be tested with real `.glb` assets in Blender.
- ComfyUI workflow execution must be tested against your real ComfyUI install and nodes.
- Unity importer and scene importer must be compiled/tested inside a real Unity project.
- Studio UI/UX must be tested in a browser with real project data.

## Not implemented yet

- `sfb bake-splat`: experimental non-MVP command stub that returns `not_implemented`.
- gsplat backend integration.
- robust ComfyUI output collection for real graph outputs.
- parallel orchestrator workers.
- adaptive depth-card meshing.
- full View Adapter training implementation.
- pipeline evaluation: generation → TripoSplat → SFB Baker.

## Repo hygiene

Generated workspaces, exports, training runs, private datasets, model weights, and source GLB assets are intentionally ignored by Git.
