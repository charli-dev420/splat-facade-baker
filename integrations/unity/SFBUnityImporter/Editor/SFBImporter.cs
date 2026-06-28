#if UNITY_EDITOR
using System;
using System.IO;
using UnityEditor;
using UnityEditor.AssetImporters;
using UnityEngine;

namespace SFB.Editor
{
    [ScriptedImporter(1, "sfb.json")]
    public class SFBImporter : ScriptedImporter
    {
        public enum MobileProfileOverride
        {
            UsePackage,
            MobileLow,
            MobileMid,
            MobileHigh
        }

        [Header("Import")]
        public bool createColliders = true;
        public bool logValidationWarnings = true;
        public MobileProfileOverride mobileProfileOverride = MobileProfileOverride.UsePackage;

        [Header("Material")]
        [Range(0f, 1f)] public float alphaCutoff = 0.5f;

        [Header("LOD transitions")]
        [Range(0.01f, 1f)] public float lod0Transition = 0.60f;
        [Range(0.01f, 1f)] public float lod1Transition = 0.25f;
        [Range(0.01f, 1f)] public float lod2Transition = 0.08f;

        public override void OnImportAsset(AssetImportContext ctx)
        {
            try
            {
                SFBPackage package = SFBPackageReader.Read(ctx.assetPath);
                ApplyProfileOverride(package);
                RegisterDependencies(ctx, package);

                SFBValidationResult validation = SFBValidator.Validate(package);
                if (logValidationWarnings)
                {
                    SFBValidator.LogToConsole(package, validation);
                }

                Material material = SFBMaterialBuilder.BuildMaterial(package, alphaCutoff);
                ctx.AddObjectToAsset(material.name, material);

                float[] transitions = { lod0Transition, lod1Transition, lod2Transition };
                GameObject root = SFBPrefabBuilder.BuildImportedObject(package, material, createColliders, transitions, ctx);
                ctx.AddObjectToAsset("main", root);
                ctx.SetMainObject(root);
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                var root = new GameObject("SFB_Import_Failed");
                var metadata = root.AddComponent<SFB.Runtime.SFBAssetMetadata>();
                metadata.assetId = Path.GetFileNameWithoutExtension(ctx.assetPath).Replace(".sfb", string.Empty);
                metadata.qualityStatus = "import_failed";
                metadata.packagePath = ctx.assetPath;
                ctx.AddObjectToAsset("main", root);
                ctx.SetMainObject(root);
            }
        }

        private void ApplyProfileOverride(SFBPackage package)
        {
            if (mobileProfileOverride == MobileProfileOverride.UsePackage) return;
            if (mobileProfileOverride == MobileProfileOverride.MobileLow) package.MobileTier = "mobile_low";
            if (mobileProfileOverride == MobileProfileOverride.MobileMid) package.MobileTier = "mobile_mid";
            if (mobileProfileOverride == MobileProfileOverride.MobileHigh) package.MobileTier = "mobile_high";
        }

        private static void RegisterDependencies(AssetImportContext ctx, SFBPackage package)
        {
            foreach (string meshPath in package.LodSfbMeshPaths.Values)
            {
                DependIfExists(ctx, meshPath);
            }
            foreach (string texturePath in package.TexturePaths.Values)
            {
                DependIfExists(ctx, texturePath);
            }
            DependIfExists(ctx, package.CollisionPath);
            DependIfExists(ctx, package.ReportPath);
            DependIfExists(ctx, package.PreviewPath);
        }

        private static void DependIfExists(AssetImportContext ctx, string assetPath)
        {
            if (string.IsNullOrWhiteSpace(assetPath)) return;
            if (File.Exists(SFBPackageReader.ToFullPath(assetPath)))
            {
                ctx.DependsOnSourceAsset(assetPath);
            }
        }
    }
}
#endif
