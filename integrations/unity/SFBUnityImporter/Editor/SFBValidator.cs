#if UNITY_EDITOR
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace SFB.Editor
{
    internal sealed class SFBValidationResult
    {
        public string Status = "ok";
        public readonly List<string> Warnings = new List<string>();
        public readonly List<string> Errors = new List<string>();

        public bool IsOk => Errors.Count == 0;
    }

    internal static class SFBValidator
    {
        public static SFBValidationResult Validate(SFBPackage package)
        {
            var result = new SFBValidationResult();

            if (!string.Equals(package.Schema, "sfb.asset.v1"))
            {
                result.Errors.Add($"Unsupported schema: {package.Schema}");
            }
            if (string.IsNullOrWhiteSpace(package.AssetId)) result.Errors.Add("Missing asset_id.");
            if (package.LodSfbMeshPaths.Count == 0) result.Errors.Add("No lod*_sfbmesh entries found.");
            if (package.WidthMeters <= 0 || package.HeightMeters <= 0) result.Errors.Add("Invalid package dimensions.");

            foreach (var kv in package.LodSfbMeshPaths)
            {
                if (!File.Exists(SFBPackageReader.ToFullPath(kv.Value)))
                {
                    result.Errors.Add($"Missing LOD{kv.Key} mesh: {kv.Value}");
                }
            }

            foreach (var required in new[] { "albedo", "alpha" })
            {
                if (!package.TexturePaths.TryGetValue(required, out string texturePath) || !File.Exists(SFBPackageReader.ToFullPath(texturePath)))
                {
                    result.Errors.Add($"Missing required texture '{required}'.");
                }
            }

            int budget = TriangleBudget(package.MobileTier);
            if (package.LodTriangles.TryGetValue(0, out int tris) && budget > 0 && tris > budget)
            {
                result.Warnings.Add($"LOD0 triangle budget exceeded: {tris} > {budget} for {package.MobileTier}.");
            }
            if (package.Report != null)
            {
                foreach (string warning in package.Report.Warnings)
                {
                    result.Warnings.Add(warning);
                }
                if (package.Report.AlphaCoverage > 0.8f)
                {
                    result.Warnings.Add("High alpha coverage may create overdraw. Consider opaque/flat-card variant.");
                }
            }
            if (package.LodSfbMeshPaths.Count < 2)
            {
                result.Warnings.Add("Only one LOD found. Mobile scenes should normally use at least LOD0 + LOD1.");
            }
            if (string.IsNullOrWhiteSpace(package.CollisionPath) || !File.Exists(SFBPackageReader.ToFullPath(package.CollisionPath)))
            {
                result.Warnings.Add("Collider proxy missing. Importer will create a fallback BoxCollider.");
            }

            result.Status = result.Errors.Count > 0 ? "failed" : (result.Warnings.Count > 0 ? "warnings" : "ok");
            return result;
        }

        public static int TriangleBudget(string mobileTier)
        {
            string tier = (mobileTier ?? string.Empty).ToLowerInvariant();
            if (tier.Contains("low")) return 300;
            if (tier.Contains("high")) return 1500;
            return 800;
        }

        public static int TextureBudget(string mobileTier)
        {
            string tier = (mobileTier ?? string.Empty).ToLowerInvariant();
            if (tier.Contains("low")) return 512;
            if (tier.Contains("high")) return 2048;
            return 1024;
        }

        public static void LogToConsole(SFBPackage package, SFBValidationResult result)
        {
            foreach (string error in result.Errors)
            {
                Debug.LogError($"[SFB] {package.AssetId}: {error}");
            }
            foreach (string warning in result.Warnings)
            {
                Debug.LogWarning($"[SFB] {package.AssetId}: {warning}");
            }
            if (result.Errors.Count == 0 && result.Warnings.Count == 0)
            {
                Debug.Log($"[SFB] {package.AssetId}: validation OK.");
            }
        }
    }
}
#endif
