#if UNITY_EDITOR
using System.Collections.Generic;
using System.IO;
using SFB.Runtime;
using UnityEditor;
using UnityEditor.AssetImporters;
using UnityEngine;

namespace SFB.Editor
{
    internal static class SFBPrefabBuilder
    {
        public static GameObject BuildImportedObject(SFBPackage package, Material material, bool createColliders, float[] lodTransitions, AssetImportContext ctx)
        {
            var root = new GameObject($"Prefab_SFB_{package.AssetId}");
            var metadata = root.AddComponent<SFBAssetMetadata>();
            FillMetadata(metadata, package);

            var visualRoot = new GameObject("Visual");
            visualRoot.transform.SetParent(root.transform, false);

            var lods = new List<LOD>();
            int lodCount = Mathf.Max(1, package.LodSfbMeshPaths.Count);
            for (int lodIndex = 0; lodIndex < lodCount; lodIndex++)
            {
                if (!package.LodSfbMeshPaths.TryGetValue(lodIndex, out string meshPath) || string.IsNullOrWhiteSpace(meshPath)) continue;
                if (!File.Exists(SFBPackageReader.ToFullPath(meshPath))) continue;

                Mesh mesh = SFBMeshBuilder.LoadMeshFromSfbMeshJson(meshPath, $"M_{package.AssetId}_LOD{lodIndex}");
                ctx.AddObjectToAsset(mesh.name, mesh);

                var child = new GameObject($"LOD{lodIndex}");
                child.transform.SetParent(visualRoot.transform, false);
                var filter = child.AddComponent<MeshFilter>();
                filter.sharedMesh = mesh;
                var renderer = child.AddComponent<MeshRenderer>();
                renderer.sharedMaterial = material;

                float transition = lodIndex < lodTransitions.Length ? lodTransitions[lodIndex] : Mathf.Max(0.01f, 0.6f / (lodIndex + 1));
                lods.Add(new LOD(transition, new Renderer[] { renderer }));
            }

            if (lods.Count > 0)
            {
                var lodGroup = root.AddComponent<LODGroup>();
                lodGroup.SetLODs(lods.ToArray());
                lodGroup.RecalculateBounds();
            }

            if (createColliders)
            {
                BuildColliders(root, package);
            }

            return root;
        }

        private static void BuildColliders(GameObject root, SFBPackage package)
        {
            var collisionRoot = new GameObject("Collision");
            collisionRoot.transform.SetParent(root.transform, false);

            if (package.ColliderProxy != null && package.ColliderProxy.Boxes.Count > 0)
            {
                for (int i = 0; i < package.ColliderProxy.Boxes.Count; i++)
                {
                    var boxData = package.ColliderProxy.Boxes[i];
                    var child = new GameObject($"BoxCollider_{i:00}");
                    child.transform.SetParent(collisionRoot.transform, false);
                    var box = child.AddComponent<BoxCollider>();
                    box.center = boxData.Center;
                    box.size = boxData.Size;
                }
                return;
            }

            var fallback = collisionRoot.AddComponent<BoxCollider>();
            fallback.center = new Vector3(0f, package.HeightMeters * 0.5f, -Mathf.Max(package.MaxDepthMeters, 0.01f) * 0.5f);
            fallback.size = new Vector3(Mathf.Max(package.WidthMeters, 0.01f), Mathf.Max(package.HeightMeters, 0.01f), Mathf.Max(package.MaxDepthMeters, 0.01f));
        }

        private static void FillMetadata(SFBAssetMetadata metadata, SFBPackage package)
        {
            metadata.assetId = package.AssetId;
            metadata.sourceAssetId = package.SourceAssetId;
            metadata.source = package.Source;
            metadata.viewId = package.ViewId;
            metadata.viewContract = package.ViewContract;
            metadata.bakeMode = package.Mode;
            metadata.pivot = package.Pivot;
            metadata.widthMeters = package.WidthMeters;
            metadata.heightMeters = package.HeightMeters;
            metadata.maxDepthMeters = package.MaxDepthMeters;
            metadata.cameraType = package.CameraType;
            metadata.azimuthDeg = package.AzimuthDeg;
            metadata.elevationDeg = package.ElevationDeg;
            metadata.mobileTier = package.MobileTier;
            metadata.alphaMode = package.AlphaMode;
            metadata.recommendedMaterial = package.RecommendedMaterial;
            metadata.lodCount = package.LodCount;
            metadata.packagePath = package.AssetPath;
            metadata.reportPath = package.ReportPath;

            if (package.Report != null)
            {
                metadata.qualityStatus = package.Report.Status;
                metadata.verticesLod0 = package.Report.VerticesLod0;
                metadata.trianglesLod0 = package.Report.TrianglesLod0;
                metadata.alphaCoverage = package.Report.AlphaCoverage;
                metadata.depthRangeMeters = package.Report.DepthRangeMeters;
                metadata.estimatedTextureMemoryMb = package.Report.EstimatedTextureMemoryMb;
            }
            else
            {
                package.LodTriangles.TryGetValue(0, out int triangles);
                package.LodVertices.TryGetValue(0, out int vertices);
                metadata.trianglesLod0 = triangles;
                metadata.verticesLod0 = vertices;
            }
        }
    }
}
#endif
