# Architecture

```text
Dataset Factory
→ Orchestrator
→ ComfyUI / Blender / SFB Core workers
→ SFB Packages
→ Studio UI review
→ Unity importer
→ Scene Graph 2.5D
```

The core rule is that all heavyweight or experimental systems call into deterministic packages. ComfyUI, Unity and the web UI should not duplicate the core bake logic.

## Current deterministic path

```text
albedo + alpha + depth
→ sfb_core cleanup
→ LOD depth-card / flat-card meshes
→ textures + collider proxy + reports
→ asset.sfb.json
```

## Future splat path

```text
PLY/SPZ/SPLAT
→ canonical camera from ViewContract
→ RGB + alpha + depth maps
→ same deterministic maps-to-depth-card path
```

Splat rendering is intentionally not implemented in v2.3; the typed stub lives in `sfb_core.splat_maps`.
