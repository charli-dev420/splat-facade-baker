# SFB Unity Importer

Editor-only Unity integration for Splat Facade Baker packages.

It imports:

```text
asset.sfb.json
mesh/*_LOD*.sfbmesh.json
textures/*.png
collision/collider_proxy.json
reports/*_report.json
```

and creates a prefab-like Unity asset with:

```text
Prefab_SFB_<asset_id>
├─ Visual
│  ├─ LOD0
│  ├─ LOD1
│  └─ LOD2
├─ Collision
│  └─ BoxCollider_00...
└─ SFBAssetMetadata
```

Unity does **not** run ComfyUI, Python baking, TripoSplat or Gaussian rendering. All heavy work stays offline in SFB Core.

## Install as a local package

In Unity:

```text
Window → Package Manager → + → Add package from disk...
```

Select:

```text
integrations/unity/SFBUnityImporter/package.json
```

## Import an SFB package

Copy a generated SFB package under `Assets`, for example:

```text
Assets/SFBImports/DemoWall/
├─ asset.sfb.json
├─ mesh/
├─ textures/
├─ collision/
└─ reports/
```

Unity will import `asset.sfb.json` with the `SFBImporter` ScriptedImporter.

## Editor tools

```text
Tools/SFB/Importer Window
Tools/SFB/Validate Selected Packages
Tools/SFB/Reimport Selected Packages
Tools/SFB/Apply Texture Settings To Selected Packages
```

## Runtime footprint

The runtime side only contains:

```text
SFBAssetMetadata.cs
SFB/MobileDepthCard shader
```

No Python, no ComfyUI, no AI runtime.
