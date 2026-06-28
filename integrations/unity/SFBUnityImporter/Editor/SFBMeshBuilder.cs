#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

namespace SFB.Editor
{
    internal static class SFBMeshBuilder
    {
        public static Mesh LoadMeshFromSfbMeshJson(string assetPath, string meshName)
        {
            string fullPath = SFBPackageReader.ToFullPath(assetPath);
            if (!File.Exists(fullPath))
            {
                throw new FileNotFoundException("SFB mesh JSON not found.", assetPath);
            }

            var root = SFBMiniJson.ParseObject(File.ReadAllText(fullPath));
            Vector3[] vertices = ReadVector3Array(root, "vertices");
            Vector3[] normals = ReadVector3Array(root, "normals");
            Vector2[] uvs = ReadVector2Array(root, "uv");
            int[] triangles = ReadTriangleArray(root, "triangles");

            var mesh = new Mesh { name = meshName };
            if (vertices.Length > 65535)
            {
                mesh.indexFormat = IndexFormat.UInt32;
            }
            mesh.vertices = vertices;
            mesh.triangles = triangles;
            if (uvs.Length == vertices.Length)
            {
                mesh.uv = uvs;
            }
            if (normals.Length == vertices.Length)
            {
                mesh.normals = normals;
            }
            else
            {
                mesh.RecalculateNormals();
            }
            mesh.RecalculateBounds();
            return mesh;
        }

        private static Vector3[] ReadVector3Array(Dictionary<string, object> root, string key)
        {
            if (!root.TryGetValue(key, out var value) || !(value is List<object> rows))
            {
                return Array.Empty<Vector3>();
            }
            var output = new Vector3[rows.Count];
            for (int i = 0; i < rows.Count; i++)
            {
                if (rows[i] is List<object> row && row.Count >= 3)
                {
                    output[i] = new Vector3(
                        SFBPackageReader.ToFloat(row[0]),
                        SFBPackageReader.ToFloat(row[1]),
                        SFBPackageReader.ToFloat(row[2])
                    );
                }
            }
            return output;
        }

        private static Vector2[] ReadVector2Array(Dictionary<string, object> root, string key)
        {
            if (!root.TryGetValue(key, out var value) || !(value is List<object> rows))
            {
                return Array.Empty<Vector2>();
            }
            var output = new Vector2[rows.Count];
            for (int i = 0; i < rows.Count; i++)
            {
                if (rows[i] is List<object> row && row.Count >= 2)
                {
                    output[i] = new Vector2(
                        SFBPackageReader.ToFloat(row[0]),
                        SFBPackageReader.ToFloat(row[1])
                    );
                }
            }
            return output;
        }

        private static int[] ReadTriangleArray(Dictionary<string, object> root, string key)
        {
            if (!root.TryGetValue(key, out var value) || !(value is List<object> faces))
            {
                return Array.Empty<int>();
            }
            var output = new List<int>(faces.Count * 3);
            foreach (object faceObj in faces)
            {
                if (!(faceObj is List<object> face) || face.Count < 3) continue;
                output.Add(Mathf.RoundToInt(SFBPackageReader.ToFloat(face[0])));
                output.Add(Mathf.RoundToInt(SFBPackageReader.ToFloat(face[1])));
                output.Add(Mathf.RoundToInt(SFBPackageReader.ToFloat(face[2])));
            }
            return output.ToArray();
        }
    }
}
#endif
