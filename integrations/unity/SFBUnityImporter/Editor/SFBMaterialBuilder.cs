#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

namespace SFB.Editor
{
    internal static class SFBMaterialBuilder
    {
        public static Material BuildMaterial(SFBPackage package, float alphaCutoff)
        {
            Shader shader = Shader.Find("SFB/MobileDepthCard") ?? Shader.Find("Unlit/Transparent Cutout") ?? Shader.Find("Unlit/Texture") ?? Shader.Find("Standard");
            var material = new Material(shader)
            {
                name = $"MAT_{package.AssetId}_SFB"
            };

            Texture2D albedo = LoadTexture(package, "albedo");
            Texture2D alpha = LoadTexture(package, "alpha");
            Texture2D normal = LoadTexture(package, "normal");

            if (albedo != null)
            {
                SetTextureIfExists(material, "_BaseMap", albedo);
                SetTextureIfExists(material, "_MainTex", albedo);
            }
            if (alpha != null)
            {
                SetTextureIfExists(material, "_AlphaMap", alpha);
            }
            if (normal != null)
            {
                SetTextureIfExists(material, "_BumpMap", normal);
                SetTextureIfExists(material, "_NormalMap", normal);
            }

            if (material.HasProperty("_Cutoff")) material.SetFloat("_Cutoff", alphaCutoff);
            ConfigureCutout(material, package.AlphaMode);
            return material;
        }

        private static Texture2D LoadTexture(SFBPackage package, string key)
        {
            if (!package.TexturePaths.TryGetValue(key, out string path) || string.IsNullOrWhiteSpace(path)) return null;
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        private static void SetTextureIfExists(Material material, string property, Texture texture)
        {
            if (material != null && texture != null && material.HasProperty(property))
            {
                material.SetTexture(property, texture);
            }
        }

        private static void ConfigureCutout(Material material, string alphaMode)
        {
            bool cutout = string.IsNullOrWhiteSpace(alphaMode) || alphaMode.ToLowerInvariant().Contains("cutout");
            if (!cutout) return;

            material.renderQueue = (int)UnityEngine.Rendering.RenderQueue.AlphaTest;
            material.SetOverrideTag("RenderType", "TransparentCutout");
            if (material.HasProperty("_Mode")) material.SetFloat("_Mode", 1f); // Built-in Standard Cutout.
            if (material.HasProperty("_Surface")) material.SetFloat("_Surface", 0f); // URP opaque surface.
            if (material.HasProperty("_AlphaClip")) material.SetFloat("_AlphaClip", 1f);
            material.EnableKeyword("_ALPHATEST_ON");
            material.DisableKeyword("_ALPHABLEND_ON");
            material.DisableKeyword("_ALPHAPREMULTIPLY_ON");
        }
    }
}
#endif
