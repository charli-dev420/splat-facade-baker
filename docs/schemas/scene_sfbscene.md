# `scene.sfbscene.json`

`scene.sfbscene.json` stores a 2.5D scene graph made of SFB cards and chunks.

Main fields:

- `schema`: must be `sfb.scene.v1`
- `scene_id`: stable scene identifier
- `target`: runtime target metadata, usually Unity/mobile
- `view_contracts`: contracts used by the cards
- `cards`: list of `SceneCard` records
- `chunks`: list of chunk groups
- `placement_rules`: optional placement history/rules

Each card references an `asset.sfb.json` package and stores `position`, `rotation_y`, `scale`, dimensions and chunk/occlusion metadata.
