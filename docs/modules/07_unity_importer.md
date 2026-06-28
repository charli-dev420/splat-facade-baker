# Bloc 7 — Unity Importer / Mobile Package

The Unity importer is an Editor-only bridge from SFB packages to mobile-ready prefabs.

## Goals

```text
asset.sfb.json
+ .sfbmesh.json LODs
+ textures
+ collider proxy
+ report
→ Unity prefab-like imported asset
```

## Non-goals

```text
- no runtime Gaussian Splat rendering;
- no Python or ComfyUI calls from Unity runtime;
- no 360° reconstruction;
- no heavy mesh collider generation;
- no procedural baking inside Unity.
```

## Import result

```text
Prefab_SFB_<asset_id>
├─ Visual
│  ├─ LOD0
│  ├─ LOD1
│  └─ LOD2
├─ Collision
│  └─ BoxCollider_00
└─ SFBAssetMetadata
```

## Main components

- `SFBImporter`: `ScriptedImporter` for `.sfb.json` files.
- `SFBPackageReader`: reads package JSON, report and collider proxy.
- `SFBMeshBuilder`: converts `.sfbmesh.json` to Unity `Mesh`.
- `SFBMaterialBuilder`: creates a simple cutout mobile material.
- `SFBPrefabBuilder`: creates LOD children, collider proxies and metadata.
- `SFBValidator`: emits mobile budget warnings.
- `SFBTextureUtility`: applies mobile texture import settings.

## Install

Use Unity Package Manager and add package from disk:

```text
integrations/unity/SFBUnityImporter/package.json
```

## Runtime contract

Runtime assets must stay simple:

```text
MeshFilter + MeshRenderer + LODGroup + primitive colliders + metadata
```

The importer keeps the expensive SFB pipeline offline.
