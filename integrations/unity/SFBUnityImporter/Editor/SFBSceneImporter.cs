#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using SFB.Runtime;
using UnityEditor;
using UnityEditor.AssetImporters;
using UnityEngine;

namespace SFB.Editor
{
    [ScriptedImporter(1, "sfbscene.json")]
    public class SFBSceneImporter : ScriptedImporter
    {
        public bool createCardPlaceholders = true;
        public bool tryInstantiateImportedPackages = false;

        public override void OnImportAsset(AssetImportContext ctx)
        {
            try
            {
                Dictionary<string, object> rootJson = SFBMiniJson.ParseObject(File.ReadAllText(SFBPackageReader.ToFullPath(ctx.assetPath)));
                string sceneId = SFBPackageReader.GetString(rootJson, "scene_id", Path.GetFileNameWithoutExtension(ctx.assetPath));
                var root = new GameObject($"Scene_SFB_{sceneId}");
                var metadata = root.AddComponent<SFBSceneMetadata>();
                metadata.sceneId = sceneId;
                metadata.units = SFBPackageReader.GetString(rootJson, "units", "meters");
                metadata.scenePath = ctx.assetPath;

                if (SFBPackageReader.TryGetObject(rootJson, "target", out var target))
                {
                    metadata.cameraMode = SFBPackageReader.GetString(target, "camera_mode", "isometric_2_5d");
                    metadata.mobileProfile = SFBPackageReader.GetString(target, "mobile_profile", "mobile_mid");
                }

                var chunkParents = new Dictionary<string, Transform>();
                if (rootJson.TryGetValue("chunks", out object chunksObj) && chunksObj is List<object> chunks)
                {
                    metadata.chunkCount = chunks.Count;
                    foreach (object item in chunks)
                    {
                        if (!(item is Dictionary<string, object> chunk)) continue;
                        string chunkId = SFBPackageReader.GetString(chunk, "chunk_id", "chunk");
                        string name = SFBPackageReader.GetString(chunk, "name", chunkId);
                        var chunkGo = new GameObject($"Chunk_{chunkId}_{name}");
                        chunkGo.transform.SetParent(root.transform, false);
                        chunkParents[chunkId] = chunkGo.transform;
                    }
                }

                if (rootJson.TryGetValue("cards", out object cardsObj) && cardsObj is List<object> cards)
                {
                    metadata.cardCount = cards.Count;
                    foreach (object item in cards)
                    {
                        if (!(item is Dictionary<string, object> card)) continue;
                        CreateCardObject(ctx, root, chunkParents, card);
                    }
                }

                ctx.AddObjectToAsset("main", root);
                ctx.SetMainObject(root);
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                var root = new GameObject("SFB_Scene_Import_Failed");
                var metadata = root.AddComponent<SFBSceneMetadata>();
                metadata.sceneId = Path.GetFileNameWithoutExtension(ctx.assetPath);
                metadata.scenePath = ctx.assetPath;
                ctx.AddObjectToAsset("main", root);
                ctx.SetMainObject(root);
            }
        }

        private void CreateCardObject(AssetImportContext ctx, GameObject root, Dictionary<string, Transform> chunkParents, Dictionary<string, object> card)
        {
            string cardId = SFBPackageReader.GetString(card, "scene_card_id", "card");
            string chunkId = SFBPackageReader.GetString(card, "chunk_id", "");
            Transform parent = root.transform;
            if (!string.IsNullOrWhiteSpace(chunkId) && chunkParents.TryGetValue(chunkId, out Transform chunkParent))
            {
                parent = chunkParent;
            }

            GameObject child = null;
            string assetPackage = SFBPackageReader.GetString(card, "asset_package", "");
            if (tryInstantiateImportedPackages && !string.IsNullOrWhiteSpace(assetPackage))
            {
                string packageAssetPath = ResolveSceneRelativePath(ctx.assetPath, assetPackage);
                GameObject importedPackage = AssetDatabase.LoadAssetAtPath<GameObject>(packageAssetPath);
                if (importedPackage != null)
                {
                    child = UnityEngine.Object.Instantiate(importedPackage);
                    child.name = $"Card_{cardId}";
                }
            }

            if (child == null)
            {
                child = new GameObject($"Card_{cardId}");
            }
            child.transform.SetParent(parent, false);
            child.transform.localPosition = SFBPackageReader.GetVector3(card, "position");
            child.transform.localRotation = Quaternion.Euler(0f, SFBPackageReader.GetFloat(card, "rotation_y"), 0f);
            child.transform.localScale = SFBPackageReader.GetVector3(card, "scale");
            if (child.transform.localScale == Vector3.zero) child.transform.localScale = Vector3.one;

            var metadata = child.AddComponent<SFBSceneCardMetadata>();
            metadata.sceneCardId = cardId;
            metadata.assetPackage = assetPackage;
            metadata.viewId = SFBPackageReader.GetString(card, "view_id", "");
            metadata.viewContract = SFBPackageReader.GetString(card, "view_contract", "");
            metadata.chunkId = chunkId;
            metadata.occlusionLayer = SFBPackageReader.GetInt(card, "occlusion_layer");
            metadata.widthMeters = SFBPackageReader.GetFloat(card, "width_m");
            metadata.heightMeters = SFBPackageReader.GetFloat(card, "height_m");
            metadata.depthMeters = SFBPackageReader.GetFloat(card, "depth_m");
            metadata.status = SFBPackageReader.GetString(card, "status", "unreviewed");
        }

        private static string ResolveSceneRelativePath(string sceneAssetPath, string maybeRelative)
        {
            if (string.IsNullOrWhiteSpace(maybeRelative)) return string.Empty;
            if (maybeRelative.StartsWith("Assets/", StringComparison.OrdinalIgnoreCase)) return maybeRelative.Replace("\\", "/");
            string sceneFull = SFBPackageReader.ToFullPath(sceneAssetPath);
            string sceneDirFull = Path.GetDirectoryName(sceneFull) ?? Application.dataPath;
            string full = Path.GetFullPath(Path.Combine(sceneDirFull, maybeRelative));
            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            if (full.StartsWith(projectRoot, StringComparison.OrdinalIgnoreCase))
            {
                return full.Substring(projectRoot.Length).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar).Replace("\\", "/");
            }
            return full.Replace("\\", "/");
        }
    }
}
#endif
