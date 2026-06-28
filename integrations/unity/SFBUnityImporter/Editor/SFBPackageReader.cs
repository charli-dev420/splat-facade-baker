#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace SFB.Editor
{
    internal sealed class SFBPackage
    {
        public string AssetPath;
        public string PackageDirectoryAssetPath;
        public string Schema;
        public string AssetId;
        public string SourceAssetId;
        public string Source;
        public string ViewContract;
        public string ViewId;
        public string Mode;
        public string Units;
        public float WidthMeters;
        public float HeightMeters;
        public float MaxDepthMeters;
        public string Pivot;
        public string CameraType;
        public float AzimuthDeg;
        public float ElevationDeg;
        public Dictionary<int, string> LodSfbMeshPaths = new Dictionary<int, string>();
        public Dictionary<int, string> LodGlbPaths = new Dictionary<int, string>();
        public Dictionary<int, int> LodTriangles = new Dictionary<int, int>();
        public Dictionary<int, int> LodVertices = new Dictionary<int, int>();
        public Dictionary<string, string> TexturePaths = new Dictionary<string, string>();
        public string CollisionPath;
        public string PreviewPath;
        public string ReportPath;
        public string Target;
        public string MobileTier;
        public string AlphaMode;
        public string RecommendedMaterial;
        public int LodCount;
        public SFBReport Report;
        public SFBColliderProxy ColliderProxy;
    }

    internal sealed class SFBReport
    {
        public string Status;
        public readonly List<string> Warnings = new List<string>();
        public int VerticesLod0;
        public int TrianglesLod0;
        public float AlphaCoverage;
        public float DepthRangeMeters;
        public float EstimatedTextureMemoryMb;
    }

    internal sealed class SFBColliderProxy
    {
        public readonly List<SFBBoxColliderData> Boxes = new List<SFBBoxColliderData>();
    }

    internal struct SFBBoxColliderData
    {
        public Vector3 Center;
        public Vector3 Size;
    }

    internal static class SFBPackageReader
    {
        public static SFBPackage Read(string assetPath)
        {
            string fullPath = ToFullPath(assetPath);
            if (!File.Exists(fullPath))
            {
                throw new FileNotFoundException("SFB package not found.", assetPath);
            }

            var root = SFBMiniJson.ParseObject(File.ReadAllText(fullPath));
            string dir = NormalizeAssetPath(Path.GetDirectoryName(assetPath) ?? string.Empty);

            var package = new SFBPackage
            {
                AssetPath = NormalizeAssetPath(assetPath),
                PackageDirectoryAssetPath = dir,
                Schema = GetString(root, "schema"),
                AssetId = GetString(root, "asset_id"),
                SourceAssetId = GetString(root, "source_asset_id"),
                Source = GetString(root, "source"),
                ViewContract = GetString(root, "view_contract"),
                ViewId = GetString(root, "view_id"),
                Mode = GetString(root, "mode"),
                Units = GetString(root, "units"),
                WidthMeters = GetFloat(root, "width_m"),
                HeightMeters = GetFloat(root, "height_m"),
                MaxDepthMeters = GetFloat(root, "max_depth_m"),
                Pivot = GetString(root, "pivot"),
                PreviewPath = ResolveOptional(dir, GetString(root, "preview")),
                ReportPath = ResolveOptional(dir, GetString(root, "report")),
                CollisionPath = ResolveCollision(dir, root),
            };

            if (TryGetObject(root, "camera", out var camera))
            {
                package.CameraType = GetString(camera, "type", "orthographic");
                package.AzimuthDeg = GetFloat(camera, "azimuth_deg");
                package.ElevationDeg = GetFloat(camera, "elevation_deg");
            }

            if (TryGetObject(root, "mesh", out var mesh))
            {
                ReadMeshMap(dir, mesh, package);
            }

            if (TryGetObject(root, "textures", out var textures))
            {
                foreach (var kv in textures)
                {
                    if (kv.Value is string rel && !string.IsNullOrWhiteSpace(rel))
                    {
                        package.TexturePaths[kv.Key] = ResolveOptional(dir, rel);
                    }
                }
            }

            if (TryGetObject(root, "runtime", out var runtime))
            {
                package.Target = GetString(runtime, "target");
                package.MobileTier = GetString(runtime, "mobile_tier");
                package.AlphaMode = GetString(runtime, "alpha_mode");
                package.RecommendedMaterial = GetString(runtime, "recommended_material");
                package.LodCount = GetInt(runtime, "lod_count");
            }

            if (!string.IsNullOrWhiteSpace(package.ReportPath) && File.Exists(ToFullPath(package.ReportPath)))
            {
                package.Report = ReadReport(package.ReportPath);
            }

            if (!string.IsNullOrWhiteSpace(package.CollisionPath) && File.Exists(ToFullPath(package.CollisionPath)))
            {
                package.ColliderProxy = ReadCollider(package.CollisionPath);
            }

            if (string.IsNullOrWhiteSpace(package.AssetId))
            {
                package.AssetId = Path.GetFileNameWithoutExtension(assetPath).Replace(".sfb", string.Empty);
            }
            if (package.LodCount <= 0)
            {
                package.LodCount = package.LodSfbMeshPaths.Count;
            }
            return package;
        }

        public static string ToFullPath(string assetPath)
        {
            var parent = Directory.GetParent(Application.dataPath);
            string projectRoot = parent != null ? parent.FullName : Application.dataPath;
            return Path.GetFullPath(Path.Combine(projectRoot, assetPath));
        }

        public static string NormalizeAssetPath(string path)
        {
            return path.Replace("\\", "/");
        }

        public static string ResolveOptional(string baseAssetDir, string relativePath)
        {
            if (string.IsNullOrWhiteSpace(relativePath)) return string.Empty;
            if (relativePath.StartsWith("Assets/", StringComparison.OrdinalIgnoreCase)) return NormalizeAssetPath(relativePath);
            return NormalizeAssetPath(Path.Combine(baseAssetDir, relativePath));
        }

        private static string ResolveCollision(string dir, Dictionary<string, object> root)
        {
            if (!root.TryGetValue("collision", out var collision) || collision == null) return string.Empty;
            if (collision is string rel) return ResolveOptional(dir, rel);
            return string.Empty;
        }

        private static void ReadMeshMap(string dir, Dictionary<string, object> mesh, SFBPackage package)
        {
            for (int i = 0; i < 8; i++)
            {
                string lod = $"lod{i}";
                string lodSfb = $"lod{i}_sfbmesh";
                string triKey = $"triangles_lod{i}";
                string vertKey = $"vertices_lod{i}";
                string glb = GetString(mesh, lod);
                string sfbmesh = GetString(mesh, lodSfb);
                if (!string.IsNullOrWhiteSpace(glb)) package.LodGlbPaths[i] = ResolveOptional(dir, glb);
                if (!string.IsNullOrWhiteSpace(sfbmesh)) package.LodSfbMeshPaths[i] = ResolveOptional(dir, sfbmesh);
                if (mesh.ContainsKey(triKey)) package.LodTriangles[i] = GetInt(mesh, triKey);
                if (mesh.ContainsKey(vertKey)) package.LodVertices[i] = GetInt(mesh, vertKey);
            }
        }

        private static SFBReport ReadReport(string assetPath)
        {
            var root = SFBMiniJson.ParseObject(File.ReadAllText(ToFullPath(assetPath)));
            var report = new SFBReport { Status = GetString(root, "status") };
            if (root.TryGetValue("warnings", out var warningsObj) && warningsObj is List<object> warnings)
            {
                foreach (object item in warnings)
                {
                    if (item != null) report.Warnings.Add(item.ToString());
                }
            }
            if (TryGetObject(root, "metrics", out var metrics))
            {
                report.VerticesLod0 = GetInt(metrics, "vertices_lod0");
                report.TrianglesLod0 = GetInt(metrics, "triangles_lod0");
                report.AlphaCoverage = GetFloat(metrics, "alpha_coverage");
                report.DepthRangeMeters = GetFloat(metrics, "depth_range_m");
                report.EstimatedTextureMemoryMb = GetFloat(metrics, "estimated_texture_memory_mb_uncompressed");
            }
            return report;
        }

        private static SFBColliderProxy ReadCollider(string assetPath)
        {
            var root = SFBMiniJson.ParseObject(File.ReadAllText(ToFullPath(assetPath)));
            var proxy = new SFBColliderProxy();
            if (!root.TryGetValue("colliders", out var collidersObj) || !(collidersObj is List<object> colliders))
            {
                return proxy;
            }

            foreach (object item in colliders)
            {
                if (!(item is Dictionary<string, object> c)) continue;
                string type = GetString(c, "type");
                if (!string.Equals(type, "box", StringComparison.OrdinalIgnoreCase)) continue;
                proxy.Boxes.Add(new SFBBoxColliderData
                {
                    Center = GetVector3(c, "center"),
                    Size = GetVector3(c, "size")
                });
            }
            return proxy;
        }

        internal static bool TryGetObject(Dictionary<string, object> dict, string key, out Dictionary<string, object> value)
        {
            if (dict.TryGetValue(key, out var obj) && obj is Dictionary<string, object> parsed)
            {
                value = parsed;
                return true;
            }
            value = new Dictionary<string, object>();
            return false;
        }

        internal static string GetString(Dictionary<string, object> dict, string key, string defaultValue = "")
        {
            if (!dict.TryGetValue(key, out var value) || value == null) return defaultValue;
            return value.ToString();
        }

        internal static int GetInt(Dictionary<string, object> dict, string key, int defaultValue = 0)
        {
            if (!dict.TryGetValue(key, out var value) || value == null) return defaultValue;
            if (value is double d) return Convert.ToInt32(d);
            if (int.TryParse(value.ToString(), NumberStyles.Integer, CultureInfo.InvariantCulture, out int i)) return i;
            if (float.TryParse(value.ToString(), NumberStyles.Float, CultureInfo.InvariantCulture, out float f)) return Mathf.RoundToInt(f);
            return defaultValue;
        }

        internal static float GetFloat(Dictionary<string, object> dict, string key, float defaultValue = 0f)
        {
            if (!dict.TryGetValue(key, out var value) || value == null) return defaultValue;
            if (value is double d) return (float)d;
            if (float.TryParse(value.ToString(), NumberStyles.Float, CultureInfo.InvariantCulture, out float f)) return f;
            return defaultValue;
        }

        internal static Vector3 GetVector3(Dictionary<string, object> dict, string key)
        {
            if (!dict.TryGetValue(key, out var value) || !(value is List<object> arr) || arr.Count < 3) return Vector3.zero;
            return new Vector3(ToFloat(arr[0]), ToFloat(arr[1]), ToFloat(arr[2]));
        }

        internal static float ToFloat(object value)
        {
            if (value is double d) return (float)d;
            if (value is float f) return f;
            float.TryParse(value?.ToString() ?? "0", NumberStyles.Float, CultureInfo.InvariantCulture, out float result);
            return result;
        }
    }
}
#endif
