# Roadmap of Pursuit

This document lists the next practical tasks after the v2.9 private repo setup.

## Priority 0 — Validate native integrations

### Unity importer hardening

- [ ] Create a blank Unity project.
- [ ] Add `integrations/unity/SFBUnityImporter/package.json` through Package Manager.
- [ ] Import `examples/sfb_packages/DemoWall/asset.sfb.json`.
- [ ] Fix any compile errors.
- [ ] Confirm LODGroup, material, textures and collider proxy are created.
- [ ] Import `examples/scenes/demo_lane.sfbscene.json`.
- [ ] Add Unity screenshots to docs.

### Studio UI/UX review

- [ ] Start `sfb-api` with a real workspace.
- [ ] Run `apps/sfb_studio` in browser.
- [ ] Review dashboard, assets, jobs, bakes, training, scenes and settings.
- [ ] Fix empty states, errors, loading states and actions.
- [ ] Add screenshots to docs.

### Blender turntable validation

- [ ] Select 10 representative GLB assets.
- [ ] Run MV8 render at 1024.
- [ ] Inspect RGB, alpha, depth, normal and camera JSON.
- [ ] Fix scale, origin, lighting, alpha and camera framing issues.
- [ ] Freeze `MV8_OBJECT` and `FACADE8_GAME` conventions.

## Priority 1 — Real production loop

- [ ] Create first real workspace.
- [ ] Scan 50 GLB assets.
- [ ] Generate capture plans.
- [ ] Render MV8 in Blender.
- [ ] Validate captures.
- [ ] Export first LoRA clean-render dataset.
- [ ] Generate first depth-card packages from real maps.
- [ ] Import first packages into Unity.

## Priority 2 — ComfyUI live orchestration

- [ ] Configure ComfyUI URL and models directory.
- [ ] Create a minimal workflow template for image cleanup / LoRA inference.
- [ ] Create a minimal TripoSplat workflow template.
- [ ] Implement robust output collection from ComfyUI history.
- [ ] Add job retry rules for ComfyUI failures.
- [ ] Add batch review of generated outputs.

## Priority 3 — Splat backend

- [ ] Choose initial splat format: PLY first.
- [ ] Implement canonical camera resolver for splat render.
- [ ] Integrate gsplat or a compatible renderer.
- [ ] Render RGB/alpha/depth from known `view_id`.
- [ ] Route results into `bake-maps`.
- [ ] Add previews and reports.

## Priority 4 — Training loop

- [ ] Validate LoRA Clean Render dataset on real captures.
- [ ] Run first short training.
- [ ] Evaluate clean-render outputs.
- [ ] Export candidate LoRA to ComfyUI.
- [ ] Run pipeline eval manually: generation → TripoSplat → SFB Baker.
- [ ] Start View Adapter experiments only after clean-render loop is stable.

## Priority 5 — Scene production

- [ ] Compose first small 2.5D test scene from 5–10 SFB packages.
- [ ] Validate scene cost.
- [ ] Import scene into Unity.
- [ ] Add chunk grouping rules.
- [ ] Add card alignment helpers in Studio UI.
