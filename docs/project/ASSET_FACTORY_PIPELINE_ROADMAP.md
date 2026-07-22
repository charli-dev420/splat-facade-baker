# Roadmap - Integration Asset Factory dans Splat

## Objectif

Transformer Splat Facade Baker en projet maitre pour toute la chaine :

```text
images source -> generation 3D TRELLIS2 -> GLB valides -> rendu MV8 Blender
-> generation d'images par vue -> QA -> split final -> exports training
```

Le projet `codextounity` devient une base de code a integrer et adapter dans Splat,
pas une dependance runtime separee. Unity reste hors du chemin critique initial.

## Etat de depart confirme

- Les assets publies sont conserves avec image source, GLB et JSON de provenance.
- Le dataset courant `D:\dataset\dataset splat training v0.1` contient 49 assets
  integres, sans `000006`, avec captures MV8 validees.
- Les fichiers de split doivent rester absents tant que le dataset global n'est pas
  declare complet.
- Splat possede deja :
  - `sfb_dataset` pour manifests, ViewContracts, plans de capture et validation ;
  - `sfb_orchestrator` pour jobs, workflows ComfyUI, artifacts et logs ;
  - `sfb_training` pour exports LoRA/view-adapter/eval ;
  - `tools/render_glb_turntable.py` et `tools/blender_capture_gate.py`.
- `codextounity` apporte :
  - batch TRELLIS2/ComfyUI ;
  - validation et staging d'images de reference ;
  - postprocess de generation GLB ;
  - profils d'assets ;
  - workflows ComfyUI ;
  - logique de jobs persistants et publication.

## Principes non negociables

- Pas de split train/val/test avant completion explicite du dataset.
- Pas de generation simulee : chaque sortie declaree doit exister et etre validee.
- Les assets sources restent regroupes par asset : `model.glb`, `original_image.*`,
  JSON de prompt/history/publish/provenance.
- Les rendus Blender MV8 restent la reference geometrique par vue.
- Les images generees par vue ne remplacent pas les rendus Blender ; elles ajoutent
  une couche training/augmentation distincte.
- Les workflows ComfyUI doivent etre configurables par metadata. Si un workflow ne
  fournit pas les entrees requises, la commande echoue clairement.

## Architecture cible

Ajouter un package Python :

```text
packages/sfb_asset_factory/
  src/sfb_asset_factory/
    cli.py
    import_published.py
    source_assets.py
    codextounity_clone/
    comfy_workflows.py
    trellis2_batch.py
    glb_postprocess.py
    mv8_batch.py
    view_image_generation.py
    view_generation_manifest.py
    qa.py
```

Commandes publiques visees :

```powershell
sfb-asset-factory import-published ...
sfb-asset-factory render-mv8 ...
sfb-asset-factory generate-view-images ...
sfb-asset-factory validate-view-images ...
sfb-asset-factory finalize-master-manifest ...
sfb-asset-factory finalize-split ...
```

Le package utilise les contrats existants de Splat au lieu de les dupliquer :

- `DatasetManifest` et `AssetRecord` depuis `sfb_dataset`.
- `ViewContract` et `capture_plan`.
- `OrchestratorStore`, `JobRunner`, workflows ComfyUI et artifacts.
- `TrainingManifest` et exporters de `sfb_training`.

## Phase 0 - Verrouiller le baseline dataset

Livrables :

- Rapport baseline reproductible pour `D:\dataset\dataset splat training v0.1`.
- Script read-only de verification globale :
  - manifests raw presents ;
  - manifests MV8 presents ;
  - aucun split ;
  - hashes uniques ;
  - `000006` absent ;
  - images source lisibles ;
  - captures MV8 presentes.

Critere d'acceptation :

```powershell
sfb-dataset validate-captures "<manifest mv8_expected>"
```

doit retourner `missing_files=0` pour chaque manifest courant.

Notes implementation :

- Ne pas deplacer ni renommer le dataset existant.
- Produire les rapports sous `workspace/reports/datasets/baseline/`.
- Le script doit etre non destructif par defaut.

## Phase 1 - Cloner proprement le coeur CodexToUnity

Objectif : integrer les fonctions utiles sans importer le projet entier.

A reprendre/adaptater :

- batch ComfyUI/TRELLIS2 ;
- upload image ComfyUI ;
- selection et collecte des sorties ;
- validation reference image ;
- postprocess generation GLB ;
- profils `prop`, `weapon`, `wall`, `character`, etc. ;
- workflows ComfyUI utiles.

A exclure au depart :

- installateur Windows ;
- UI bootstrap ;
- MCP/widget ;
- templates Unity ;
- docs publiques de distribution.

Livrables :

- `packages/sfb_asset_factory/pyproject.toml`.
- CLI `sfb-asset-factory`.
- Dossier `workflows/comfyui/asset_factory/` avec workflows copies ou references.
- `configs/asset_profiles/` cote Splat, ou mapping documente vers les profils importes.
- Tests syntaxe et dry-run.

Critere d'acceptation :

```powershell
python -m py_compile packages/sfb_asset_factory/src/sfb_asset_factory/*.py
sfb-asset-factory trellis2-dry-run --input-dir <images> --limit 1
```

Le dry-run doit produire un plan de jobs sans lancer de generation GPU.

## Phase 2 - Ingestion native des assets publies

Objectif : remplacer les scripts ponctuels par une commande stable.

Commande cible :

```powershell
sfb-asset-factory import-published `
  --source-root "D:\dataset\assets\modelegenerer\all_assets_conversation" `
  --dataset-root "D:\dataset\dataset splat training v0.1" `
  --dataset-id modelegenerer_master_working `
  --exclude-index 000006 `
  --no-split
```

Comportement :

- Scanner recursivement les GLB.
- Calculer hash source.
- Ignorer les hashes deja integres.
- Exclure explicitement `000006`.
- Copier chaque asset dans `source_assets/<asset_id>/`.
- Pour les dossiers multi-assets, copier seulement les fichiers partageant le meme
  prefixe `0000xx__`.
- Ecrire `provenance.json` par asset.
- Ecrire ou mettre a jour un manifest de travail non splitte.

Critere d'acceptation :

- Aucun doublon hash.
- Aucune source manquante.
- Toutes les images `original_image.*` lisibles.
- Aucun fichier `splits/*.json` cree.

## Phase 3 - Rendu MV8 batch par orchestrateur

Objectif : rendre Blender MV8 depuis la commande Splat et enregistrer les artifacts.

Commande cible :

```powershell
sfb-asset-factory render-mv8 `
  --manifest "<raw manifest>" `
  --view-contract examples\view_contracts\MV8_OBJECT.json `
  --renders-root "<dataset_root>\renders\<dataset_id>" `
  --resolution 256 `
  --views front,front_right,right,back_right,back,back_left,left,front_left
```

Comportement :

- Utiliser `tools/blender_capture_gate.py`.
- Traiter par batch configurable.
- Reprendre les assets deja rendus si validation locale OK.
- Produire un rapport par asset et un rapport global.
- Ne jamais marquer un asset OK si Blender a emis traceback ou sortie manquante.

Critere d'acceptation :

- `existing_files = assets * views * 5`.
- Tous les rapports Blender ont `status=passed`.
- Le manifest `mv8_expected` pointe vers le dossier dataset final.

## Phase 4 - Manifest de generation d'images par vue

Objectif : ajouter un contrat explicite pour les images generees par vue.

Nouveau schema :

```text
sfb.view_generation_manifest.v1
```

Champs par record :

- `asset_id`
- `view_id`
- `source_reference_image`
- `blender_rgb`
- `blender_alpha`
- `blender_normal`
- `camera_json`
- `generated_image`
- `workflow_id`
- `prompt`
- `negative_prompt`
- `seed`
- `status`
- `quality_score`
- `errors`
- `metadata`

Statuts :

```text
planned -> queued -> generated -> needs_review -> approved/rejected
```

Critere d'acceptation :

- Schema JSON ajoute dans `schemas/`.
- Loader Pydantic ajoute dans `sfb_asset_factory`.
- Test de round-trip JSON.
- Aucun changement obligatoire dans `dataset_manifest.v1` a cette phase.

## Phase 5 - Generation dual-image par vue

Objectif : generer une image cible par vue en utilisant deux references :

```text
image source originale du modele + rendu Blender de la vue -> image generee de cette vue
```

Workflow logique cible :

```text
source_reference_image -> reference identite / style
blender_view_rgb       -> reference pose / silhouette / vue
camera metadata        -> prompt angle explicite
prompt asset           -> description objet
```

Commande cible :

```powershell
sfb-asset-factory generate-view-images `
  --manifest "<mv8_expected manifest>" `
  --view-contract examples\view_contracts\MV8_OBJECT.json `
  --workflow-id view_refiner_dual_image_v1 `
  --out-root "<dataset_root>\generated_views\view_refiner_dual_image_v1" `
  --comfy-url http://127.0.0.1:8188 `
  --batch-size 5 `
  --seed-mode stable `
  --dry-run
```

Inputs workflow obligatoires :

- `source_reference_image`
- `blender_view_rgb`
- `view_id`
- `target_azimuth_deg`
- `target_elevation_deg`
- `prompt`
- `negative_prompt`
- `seed`
- `filename_prefix`

Comportement :

- `--dry-run` verifie mappings, chemins et jobs sans appeler ComfyUI.
- En mode live, creer un job orchestrateur par asset/vue.
- Sorties par vue :

```text
generated_views/<workflow_id>/<asset_id>/<view_id>/
  image.png
  generation.json
  comfy_history.json
  injected_workflow.json
```

Critere d'acceptation :

- Dry-run sur 1 asset genere 8 jobs planifies.
- Live-run sur 1 asset produit 8 images et 8 sidecars.
- Si le workflow ne contient pas les deux images d'entree, erreur bloquante.

## Phase 6 - QA automatique et revue humaine

Objectif : separer generation brute et donnees utilisables en training.

Commandes cibles :

```powershell
sfb-asset-factory validate-view-images --view-generation-manifest <manifest>
sfb-asset-factory mark-view-image --asset-id <id> --view-id <view> --status approved
```

Gates automatiques :

- image presente et lisible ;
- resolution conforme ;
- pas d'image vide ;
- silhouette non coupee ;
- fond suffisamment neutre ;
- similarite raisonnable avec rendu Blender ;
- difference suffisante pour justifier la generation ;
- pas de texte/watermark detecte par heuristiques simples.

Sorties :

- `view_generation_validation.json`
- `review_queue.jsonl`
- manifest mis a jour avec `status`.

Critere d'acceptation :

- Les images invalides passent `needs_review` ou `rejected`, jamais `approved`.
- Les seuils sont configures dans un fichier versionne.

## Phase 7 - Master manifest et split final

Objectif : finaliser le dataset seulement quand la production est complete.

Commande cible :

```powershell
sfb-asset-factory finalize-master-manifest `
  --dataset-root "D:\dataset\dataset splat training v0.1" `
  --out-manifest "<dataset_root>\manifests\modelegenerer_master_v1.raw.json"
```

Puis, uniquement apres confirmation explicite :

```powershell
sfb-asset-factory finalize-split `
  --manifest "<dataset_root>\manifests\modelegenerer_master_v1.raw.json" `
  --seed 20260702 `
  --train 0.70 `
  --val 0.15 `
  --test 0.15
```

Regles :

- Split par asset, jamais par vue.
- Les assets avec vues generees non approuvees peuvent rester hors training.
- Les splits sont ecrits une seule fois pour une version figee.

Critere d'acceptation :

- Aucun leakage entre vues d'un meme asset.
- Dataset hash stable.
- Manifest final `frozen=true`.

## Phase 8 - Exports training

Objectif : produire les exports exploitables apres split final.

Exports :

- LoRA clean-render depuis MV8 Blender.
- View-adapter depuis paires de vues.
- Dual-image view refinement depuis `view_generation_manifest`.
- Eval sets fixes.

Commandes :

```powershell
sfb-trainprep export-lora ...
sfb-trainprep export-view-pairs ...
sfb-trainprep make-eval-set ...
```

Extension a ajouter :

```powershell
sfb-asset-factory export-view-generation-training ...
```

Critere d'acceptation :

- `metadata.jsonl` contient reference source, rendu Blender et image generee.
- Les eval sets sont fixes et reproductibles.
- Les records `rejected` sont exclus.

## Phase 9 - Studio UI et monitoring

Objectif : rendre le pipeline operable sans scripts manuels.

Surfaces Studio :

- Asset Factory dashboard.
- Nouveaux assets detectes.
- Statut MV8.
- Statut generation image par vue.
- Review queue.
- Boutons `approve/reject`.
- Logs job et artifacts.

Backend :

- Endpoints API pour import, render MV8, generate-view-images, validation et review.
- Jobs annulables/retryables via `sfb_orchestrator`.

Critere d'acceptation :

- Un operator peut traiter un asset complet depuis Studio.
- Les erreurs bloquantes sont visibles, pas cachees dans logs seulement.

## Phase 10 - Durcissement release interne

Validation obligatoire :

```powershell
python -m pytest packages/sfb_dataset/tests packages/sfb_orchestrator/tests packages/sfb_training/tests
sfb-dataset validate-captures "<manifest>"
sfb-asset-factory import-published --dry-run ...
sfb-asset-factory generate-view-images --dry-run --limit-assets 1
```

Checks manuels :

- Visual QA sur un echantillon par famille d'asset.
- Controle que `D:\dataset\dataset splat training v0.1` ne contient pas de split
  avant completion.
- Controle que les workflows ComfyUI references existent.
- Controle que les chemins personnels ne sont pas ajoutes aux exemples publics.

Definition of done :

- Pipeline executable end-to-end sur au moins 1 asset live.
- Pipeline executable en batch sur le dataset courant en dry-run.
- Rendus MV8 valides.
- Images par vue generees et QA.
- Master manifest non splitte propre.
- Split final uniquement apres validation utilisateur.

## Ordre de travail recommande

1. Phase 0 : baseline dataset.
2. Phase 1 : package `sfb_asset_factory`.
3. Phase 2 : ingestion native sans split.
4. Phase 3 : MV8 batch stable.
5. Phase 4 : schema view generation.
6. Phase 5 : dual-image generation dry-run, puis 1 asset live.
7. Phase 6 : QA et review.
8. Phase 7 : master manifest et split final.
9. Phase 8 : exports training.
10. Phase 9-10 : Studio et durcissement.

## Risques principaux

- Workflow ComfyUI dual-image absent ou incompatible localement.
- Generation image par vue trop libre, perdant l'identite de l'asset.
- Explosion du volume de fichiers si chaque vue genere plusieurs candidats.
- Confusion entre rendu Blender reference et image generee training.
- Reintroduction prematuree de splits intermediaires.

Mitigations :

- Workflow metadata strict.
- Dry-run obligatoire avant live.
- Une image approuvee maximum par asset/vue pour la version 1.
- Manifests separes pour captures Blender et images generees.
- Gate qui refuse tout split tant que `dataset_complete=true` n'est pas explicite.
