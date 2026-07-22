# Repository Guidelines

## Project Structure & Module Organization

Splat Facade Baker is a modular Python toolchain with a Vite/React Studio UI. Core packages live under `packages/`: `sfb_core` for map baking, `sfb_dataset` for ViewContracts and manifests, `sfb_orchestrator` for the local API/job registry, `sfb_training` for prep and run tooling, and `sfb_scene` for scene graph exports. The Studio app is in `apps/sfb_studio`. Public JSON schemas are in `schemas/`, docs in `docs/`, examples and fixtures in `examples/`, integration adapters in `integrations/`, and helper scripts in `scripts/` and `tools/`.

## Build, Test, and Development Commands

- `python -m venv .venv` then activate it (`.venv\Scripts\activate` on Windows).
- `bash scripts/bootstrap_dev.sh`: install all Python packages in editable mode.
- `pytest`: run the cross-package test suite configured in root `pyproject.toml`.
- `bash scripts/smoke_test.sh`: run tests plus synthetic bake/package validation and schema checks.
- `python tools/make_synthetic_maps.py --out examples/synthetic`: regenerate sample input maps.
- `sfb bake-maps ... --out exports/DemoWall`: produce an SFB package from albedo/alpha/depth maps.
- `SFB_WORKSPACE=workspace sfb-api`: start the local FastAPI service. In PowerShell use `$env:SFB_WORKSPACE='workspace'; sfb-api`.
- From `apps/sfb_studio`: `npm install`, `npm run dev`, and `npm run build`.

## Coding Style & Naming Conventions

Use Python 3.10+, 4-space indentation, type hints for public interfaces, and keep lines at or below the Ruff limit of 100 columns. CLI modules expose console scripts via each package `pyproject.toml`. Prefer snake_case for Python files, functions, CLI IDs, and JSON fields. TypeScript uses React function components, single-quoted imports, and colocated types in `src/types.ts`.

## Testing Guidelines

Place Python tests in `packages/<package>/tests/` and name them `test_*.py`. Add or update tests for CLI behavior, schema validation, manifests, scene graph changes, and package exports. Before handoff, run the narrow package test first, then `pytest` or `bash scripts/smoke_test.sh` for cross-package changes.

## Commit & Pull Request Guidelines

History uses short imperative subjects with optional prefixes such as `docs:`, `ci:`, `test:`, `chore:`, and `fix:`. Keep commits scoped to one module when possible. PRs should describe the change, list validation commands, link related issues, and include screenshots for Studio UI changes.

## Schema, Security, and Agent Notes

Public JSON format changes must update `schemas/`, `docs/schemas/`, at least one example, tests, and `CHANGELOG.md`. Do not commit generated workspaces, exports, model weights, secrets, or local credentials. Agents should parallelize inspection and use sub-agents when they add value; a task is complete only when the full requested behavior is implemented and verified, not when a simplified surface pass works.
