#if UNITY_EDITOR
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace SFB.Editor
{
    internal static class SFBTextureUtility
    {
        [MenuItem("Tools/SFB/Apply Texture Settings To Selected Packages")]
        public static void ApplyTextureSettingsToSelectedPackages()
        {
            int updated = 0;
            foreach (Object obj in Selection.objects)
            {
                string assetPath = AssetDatabase.GetAssetPath(obj);
                if (string.IsNullOrWhiteSpace(assetPath) || !assetPath.EndsWith(".sfb.json")) continue;
                SFBPackage package = SFBPackageReader.Read(assetPath);
                updated += ApplyTextureSettings(package);
            }
            Debug.Log($"[SFB] Applied texture settings to {updated} texture imports.");
            AssetDatabase.Refresh();
        }

        public static int ApplyTextureSettings(SFBPackage package)
        {
            int count = 0;
            int maxSize = SFBValidator.TextureBudget(package.MobileTier);
            foreach (KeyValuePair<string, string> kv in package.TexturePaths)
            {
                string path = kv.Value;
                var importer = AssetImporter.GetAtPath(path) as TextureImporter;
                if (importer == null) continue;

                importer.maxTextureSize = maxSize;
                importer.mipmapEnabled = true;
                importer.alphaIsTransparency = kv.Key == "alpha" || kv.Key == "mask";
                importer.sRGBTexture = kv.Key != "normal" && kv.Key != "depth" && kv.Key != "mask";
                if (kv.Key == "normal")
                {
                    importer.textureType = TextureImporterType.NormalMap;
                }
                else
                {
                    importer.textureType = TextureImporterType.Default;
                }

                importer.SetPlatformTextureSettings(new TextureImporterPlatformSettings
                {
                    name = "Android",
                    overridden = true,
                    maxTextureSize = maxSize,
                    format = TextureImporterFormat.ASTC_6x6
                });
                importer.SetPlatformTextureSettings(new TextureImporterPlatformSettings
                {
                    name = "iPhone",
                    overridden = true,
                    maxTextureSize = maxSize,
                    format = TextureImporterFormat.ASTC_6x6
                });
                importer.SaveAndReimport();
                count++;
            }
            return count;
        }
    }
}
#endif
