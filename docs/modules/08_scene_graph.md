# Bloc 8 — Scene Graph 2.5D

Bloc 8 turns approved SFB asset packages into a lightweight 2.5D scene graph made of cards, chunks and placement metadata.

It is not a complete level editor. It is the stable data layer that lets Studio UI and Unity agree on how depth-cards are placed.

```text
SFB packages
→ SceneCards
→ chunks
→ scene.sfbscene.json
→ scene validation report
→ Unity scene import scaffold
```

## Core concepts

### SceneCard

A `SceneCard` references one `asset.sfb.json` package and stores placement information:

- `scene_card_id`
- `asset_package`
- `view_id`
- `view_contract`
- `position`
- `rotation_y`
- `scale`
- `width_m`, `height_m`, `depth_m`
- `chunk_id`
- `occlusion_layer`
- `status`

### ChunkGroup

A chunk groups cards for mobile reasoning and later Unity hierarchy construction.

### ViewContract placement

`sfb-scene add-card` can resolve `rotation_y` from a fixed `ViewContract`:

```text
base_rotation_y + view azimuth → card rotation_y
```

This keeps the system deterministic. Angles are not guessed by an AI model.

## CLI

Create an empty scene:

```bash
sfb-scene create \
  --scene-id demo_lane \
  --out workspace/scenes/demo_lane.sfbscene.json
```

Add a chunk:

```bash
sfb-scene add-chunk workspace/scenes/demo_lane.sfbscene.json \
  --chunk-id chunk_001 \
  --name lane_start \
  --replace
```

Add a card from an SFB asset package:

```bash
sfb-scene add-card workspace/scenes/demo_lane.sfbscene.json \
  --scene-card-id card_wall_001 \
  --asset-package exports/DemoWall/asset.sfb.json \
  --view-contract examples/view_contracts/MV8_OBJECT.json \
  --view-id front_right \
  --position 0,0,0 \
  --chunk-id chunk_001 \
  --replace
```

Align a card to another card:

```bash
sfb-scene align-edge workspace/scenes/demo_lane.sfbscene.json \
  --card-id card_wall_002 \
  --target-card-id card_wall_001 \
  --edge right \
  --overlap-m 0.25
```

Validate a scene:

```bash
sfb-scene validate workspace/scenes/demo_lane.sfbscene.json \
  --out workspace/scenes/demo_lane_report.json
```

## Unity

The Unity package now includes a scaffold `SFBSceneImporter` for `.sfbscene.json`. It creates a hierarchy:

```text
Scene_SFB_<scene_id>
├─ Chunk_<chunk_id>
│  ├─ Card_<scene_card_id>
│  └─ ...
└─ SFBSceneMetadata
```

The v2.8 importer is intentionally conservative. It creates scene/card metadata and placeholders, with an optional `tryInstantiateImportedPackages` flag for later package instantiation tests inside Unity.

## Done in v2.8

- Functional `sfb_scene` package.
- `sfb-scene` CLI.
- Scene schema update.
- Scene report schema.
- Scene validation.
- Chunk bounds computation.
- Edge alignment helper.
- Demo scene.
- Studio API scene listing endpoint.
- Studio UI scene table.
- Unity `.sfbscene.json` importer scaffold.
