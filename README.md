# Splat Facade Baker

**Splat Facade Baker (SFB)** is an offline toolchain for turning controlled renders and RGB/alpha/depth maps into lightweight **2.5D depth-card assets** for mobile game environments. The splat path is experimental and excluded from the current MVP.

It is designed for workflows where a clean image or controlled render has one excellent canonical view, but the full 360° geometry is too noisy, too heavy, or unnecessary for mobile.

```text
clean view / maps
→ known ViewContract camera
→ RGB + alpha + depth
→ cleanup
→ depth-card / layered-card / impostor
→ SFB package
→ Unity mobile prefab
```

## What this project does

- Converts albedo + alpha + depth maps into a depth-card mesh.
- Exports a standard `asset.sfb.json` package with textures, mesh, collider proxy and report.
- Defines reusable schemas for view contracts, datasets, assets, scenes and training runs.
- Provides the skeleton for a full local production pipeline: Dataset Factory, ComfyUI background orchestration, Training Prep, Studio UI, Unity importer and Scene Graph.

## What this project does **not** do

- It does not reconstruct a clean 360° mesh.
- It does not run Gaussian Splatting on mobile.
- It does not ship an MVP splat renderer; `sfb bake-splat` is experimental and returns `not_implemented`.
- It does not replace Blender, Unity or ComfyUI.
- It does not ship trained model weights or datasets.

## Current status

**Pre-MVP / scaffold v2.8.**

Working now:

- `sfb bake-maps` CLI.
- synthetic maps example.
- deterministic alpha/depth cleanup.
- depth-card and flat-card GLB/OBJ/`.sfbmesh.json` export.
- LOD0/LOD1/LOD2 package export.
- SFB asset package JSON.
- richer mobile bake report and tests.
- public schemas and ViewContract examples.
- `sfb-dataset` CLI for ViewContracts, GLB/GLTF scanning, capture plans, expected views, capture validation and asset-level splits.
- `sfb-orch` CLI with SQLite registry, jobs, artifacts, workflow registry and ComfyUI dry-run support.
- `sfb-api` FastAPI local API for projects, assets, jobs, workflows, artifacts and ComfyUI status.
- Studio UI connected to the local API with dashboard, review queue, assets, jobs, artifacts, bakes, training, workflows and settings pages.
- Unity Editor importer package for `.sfb.json` packages, `.sfbmesh.json` LODs, cutout material, collider proxies, metadata and validation tools.
- `sfb-scene` CLI for 2.5D SceneCards, chunks, ViewContract-based rotations, validation reports and `.sfbscene.json` export.
- Studio API/UI scene listing and Unity `.sfbscene.json` importer scaffold.
- `sfb-trainprep` CLI for LoRA clean-render exports, view-pair exports, eval sets and training dataset reports.
- `sfb-train` CLI for TrainingRun registry, Diffusers/Kohya command generation, dry-runs, checkpoints, clean-render eval, promotion and ComfyUI export.

Structured but intentionally incomplete:

- actual GPU training execution depends on external Diffusers/Kohya environments; v2.5 provides run/checkpoint/eval tooling and dry-runs.
- `sfb bake-splat` is experimental and excluded from the MVP until a validated renderer exists.
- ComfyUI custom nodes beyond API orchestration are experimental scaffolds, not product demos.
- Unity importer has not been compiled inside Unity in this environment; it is implemented as an Editor package and must be tested in a real Unity project.


## Project management docs

- [Project status](docs/project/PROJECT_STATUS.md)
- [Known limitations](docs/project/KNOWN_LIMITATIONS.md)
- [Roadmap of pursuit](docs/project/ROADMAP_NEXT.md)
- [MVP demos and local gates](docs/demos/MVP_DEMOS.md)
- [Private GitHub setup](docs/setup/GITHUB_PRIVATE_SETUP.md)
- [v2.9 release notes](docs/release/RELEASE_NOTES_v2.9_private_ready.md)

## Quickstart: maps → depth-card

```bash
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate

pip install -e packages/sfb_core[dev]

python tools/make_synthetic_maps.py --out examples/synthetic

sfb bake-maps \
  --albedo examples/synthetic/albedo.png \
  --alpha examples/synthetic/alpha.png \
  --depth examples/synthetic/depth.png \
  --name DemoWall \
  --width-m 8 \
  --height-m 4 \
  --max-depth-m 0.45 \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --view-id front \
  --grid 96 \
  --lod-count 3 \
  --texture-size 1024 \
  --out exports/DemoWall
```

Expected output:

```text
exports/DemoWall/
├─ asset.sfb.json
├─ mesh/        # LOD0/LOD1/LOD2 GLB, OBJ and .sfbmesh.json
├─ textures/    # albedo, alpha, depth, normal, mask
├─ collision/
├─ preview/
└─ reports/
```


## Quickstart: Dataset Factory

Install the dataset package:

```bash
pip install -e packages/sfb_dataset
```

Validate a ViewContract:

```bash
sfb-dataset validate-contract examples/view_contracts/MV8_OBJECT.json
```

Scan a folder of GLB/GLTF files:

```bash
sfb-dataset scan-glb ./sources/glb \
  --dataset-id medieval_gold_v0 \
  --tier gold_candidate \
  --source-license internal \
  --out workspace/manifests/medieval_gold_v0.json
```

Create a fixed-angle capture plan:

```bash
sfb-dataset make-capture-plan workspace/manifests/medieval_gold_v0.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --renders-root workspace/renders/medieval_gold_v0 \
  --out workspace/plans/medieval_gold_mv8.jsonl
```

Attach expected render paths and split by asset:

```bash
sfb-dataset attach-expected-views workspace/manifests/medieval_gold_v0.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --renders-root workspace/renders/medieval_gold_v0 \
  --out workspace/manifests/medieval_gold_v0_mv8_expected.json

sfb-dataset split workspace/manifests/medieval_gold_v0_mv8_expected.json \
  --seed 1337 \
  --train 0.7 \
  --val 0.15 \
  --test 0.15 \
  --out workspace/splits/medieval_gold_v0_split.json \
  --write-manifest workspace/manifests/medieval_gold_v0_mv8_split.json
```

Render a GLB manually with Blender:

```bash
blender --background --python tools/render_glb_turntable.py -- \
  --input sources/glb/wall_a.glb \
  --asset-id wall_a \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --out workspace/renders/wall_a \
  --resolution 1024
```


## Quickstart: Local Orchestrator

Install the orchestrator package:

```bash
pip install -e packages/sfb_orchestrator[dev]
```

Initialize a local workspace:

```bash
sfb-orch --workspace workspace init \
  --project-id demo \
  --name Demo
```

Create and run a local test job:

```bash
sfb-orch --workspace workspace jobs create \
  --project-id demo \
  --engine noop \
  --param hello='"world"'

sfb-orch --workspace workspace jobs run-next \
  --project-id demo

sfb-orch --workspace workspace artifacts list \
  --project-id demo
```

Start the local API:

```bash
SFB_WORKSPACE=workspace sfb-api
```

Then open `http://127.0.0.1:8765/health`.

To run the Studio UI:

```bash
cd apps/sfb_studio
npm install
npm run dev
```

## Quickstart: Training Prep

Install the training package:

```bash
pip install -e packages/sfb_training[dev]
```

Inspect a split manifest:

```bash
sfb-trainprep report workspace/manifests/medieval_gold_v0_mv8_split.json
```

Export a LoRA clean-render dataset:

```bash
sfb-trainprep export-lora workspace/manifests/medieval_gold_v0_mv8_split.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --out training_exports/lora_clean_render_v0 \
  --export-id lora_clean_render_v0 \
  --tiers gold,gold_candidate \
  --overwrite
```

Export view-adapter source→target pairs:

```bash
sfb-trainprep export-view-pairs workspace/manifests/medieval_gold_v0_mv8_split.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --pair-policy front_to_all \
  --out training_exports/view_adapter_v0 \
  --export-id view_adapter_v0 \
  --overwrite
```

Create a fixed eval set:

```bash
sfb-trainprep make-eval-set workspace/manifests/medieval_gold_v0_mv8_split.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --task clean_render \
  --split test \
  --out training_exports/eval_clean_render_v0 \
  --overwrite
```


## Quickstart: Unity Importer

Install the Unity package from disk:

```text
Unity → Window → Package Manager → + → Add package from disk...
```

Select:

```text
integrations/unity/SFBUnityImporter/package.json
```

Then copy a generated SFB package under your Unity project, for example:

```text
Assets/SFBImports/DemoWall/
├─ asset.sfb.json
├─ mesh/
├─ textures/
├─ collision/
└─ reports/
```

Unity imports `asset.sfb.json` as a prefab-like asset with LOD children, a mobile cutout material, primitive collider proxies and `SFBAssetMetadata`.

Editor tools are available under:

```text
Tools/SFB/Importer Window
Tools/SFB/Validate Selected Packages
Tools/SFB/Reimport Selected Packages
Tools/SFB/Apply Texture Settings To Selected Packages
```

## Pipeline blocks

1. **Dataset Factory + ViewContract** — render GLB assets through fixed camera contracts.
2. **Local Orchestrator + ComfyUI background** — job queue, artifact registry, workflow execution.
3. **Map Baker Core** — maps to mobile 2.5D assets; splat input remains experimental and non-MVP.
4. **Training Prep** — LoRA clean-render datasets and view-pair datasets.
5. **Training Runner** — versioned runs, checkpoints, evaluation and model registry.
6. **Studio UI** — production dashboard, review queue, jobs, bakes and training pages.
7. **Unity Importer** — import SFB packages as mobile-ready prefabs.
8. **Scene Graph 2.5D** — compose SceneCards, chunks and Unity scenes.
9. **Open Source Repo / Docs** — schemas, docs, tests, roadmap and contribution process.

See [`docs/modules`](docs/modules) for the detailed plan.

## Repository layout

```text
packages/        Python modules
apps/            Studio UI
integrations/    ComfyUI, Unity, Blender bridges
schemas/         Public JSON Schemas
examples/        Minimal inputs, view contracts and presets
docs/            Product, architecture, setup and module docs
tools/           Small utility scripts
tests/           Cross-package fixtures and integration tests
```

## License

Code is released under the MIT License. Datasets, model weights and third-party workflows must define their own licenses separately.


## Quickstart: Training Runner dry-run

Install the training package:

```bash
pip install -e packages/sfb_training[dev]
```

Create a TrainingRun from a config and generate the backend command without launching GPU training:

```bash
sfb-train init-run \
  --config examples/training_configs/lora_clean_render_diffusers.yaml \
  --out runs/clean_render_lora_v0 \
  --overwrite

sfb-train command --run-dir runs/clean_render_lora_v0 --write
sfb-train run --run-dir runs/clean_render_lora_v0 --dry-run
```

Evaluate a folder of generated images for clean-render compatibility:

```bash
sfb-train eval-clean-render \
  --images path/to/generated/images \
  --run-dir runs/clean_render_lora_v0 \
  --eval-id clean_render_eval_v0
```


## Quickstart: Scene Graph 2.5D

Install the scene package:

```bash
pip install -e packages/sfb_scene[dev]
```

Create and validate a small scene from an SFB package:

```bash
sfb-scene create --scene-id demo_lane --out workspace/scenes/demo_lane.sfbscene.json

sfb-scene add-chunk workspace/scenes/demo_lane.sfbscene.json \
  --chunk-id chunk_001 \
  --name lane_start \
  --replace

sfb-scene add-card workspace/scenes/demo_lane.sfbscene.json \
  --scene-card-id demo_wall_001 \
  --asset-package examples/sfb_packages/DemoWall/asset.sfb.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --view-id front_right \
  --chunk-id chunk_001 \
  --replace

sfb-scene update-chunk-bounds workspace/scenes/demo_lane.sfbscene.json --chunk-id chunk_001
sfb-scene validate workspace/scenes/demo_lane.sfbscene.json --out workspace/scenes/demo_lane_report.json
```
