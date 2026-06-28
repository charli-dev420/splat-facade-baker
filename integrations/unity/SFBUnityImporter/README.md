# Splat Facade Baker Unity Importer

This package is the Unity Editor bridge for SFB packages.

## Scope

It is intentionally simple:

- reads `asset.sfb.json`;
- reads `.sfbmesh.json` LOD meshes;
- loads albedo/alpha/normal textures;
- builds a material using `SFB/MobileDepthCard`;
- creates a root GameObject with `LODGroup`;
- creates primitive collider proxies;
- attaches `SFBAssetMetadata`;
- exposes validation and texture import tools in `Tools/SFB`.

It does not bake splats, generate assets, train models, call ComfyUI or run Python inside Unity.

## Minimal package layout

```text
DemoWall/
├─ asset.sfb.json
├─ mesh/
│  ├─ DemoWall_LOD0.sfbmesh.json
│  ├─ DemoWall_LOD1.sfbmesh.json
│  └─ DemoWall_LOD2.sfbmesh.json
├─ textures/
│  ├─ DemoWall_Albedo.png
│  ├─ DemoWall_Alpha.png
│  └─ DemoWall_Normal.png
├─ collision/
│  └─ collider_proxy.json
└─ reports/
   └─ DemoWall_report.json
```

## Scene graph import

v2.8 also includes a conservative Editor-only importer for `.sfbscene.json` files.

It creates a hierarchy of chunks and card placeholders with metadata:

```text
Scene_SFB_<scene_id>
├─ Chunk_<chunk_id>
│  ├─ Card_<scene_card_id>
│  └─ ...
└─ SFBSceneMetadata
```

By default it does not instantiate every referenced SFB package. The importer exposes `tryInstantiateImportedPackages` for local Unity testing once the package assets are imported and paths are valid under `Assets/`.
