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

## Experimental Non-MVP Splat Path

```text
PLY/SPZ/SPLAT
→ canonical camera from ViewContract
→ RGB + alpha + depth maps
→ same deterministic maps-to-depth-card path
```

Splat rendering is intentionally excluded from the current MVP. `sfb bake-splat`
is kept as an experimental typed stub so future renderer work can plug into the
same maps-to-depth-card path without changing the stable MVP contract.
