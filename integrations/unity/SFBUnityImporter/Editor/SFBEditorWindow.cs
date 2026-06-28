#if UNITY_EDITOR
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace SFB.Editor
{
    public sealed class SFBEditorWindow : EditorWindow
    {
        private Vector2 _scroll;
        private string _lastReport = "Select one or more asset.sfb.json files, then use the buttons below.";

        [MenuItem("Tools/SFB/Importer Window")]
        public static void Open()
        {
            GetWindow<SFBEditorWindow>("SFB Importer");
        }

        [MenuItem("Tools/SFB/Reimport Selected Packages")]
        public static void ReimportSelectedPackages()
        {
            foreach (Object obj in Selection.objects)
            {
                string path = AssetDatabase.GetAssetPath(obj);
                if (!string.IsNullOrWhiteSpace(path) && path.EndsWith(".sfb.json"))
                {
                    AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceUpdate);
                }
            }
        }

        [MenuItem("Tools/SFB/Validate Selected Packages")]
        public static void ValidateSelectedPackagesMenu()
        {
            foreach (Object obj in Selection.objects)
            {
                string path = AssetDatabase.GetAssetPath(obj);
                if (!string.IsNullOrWhiteSpace(path) && path.EndsWith(".sfb.json"))
                {
                    var package = SFBPackageReader.Read(path);
                    var result = SFBValidator.Validate(package);
                    SFBValidator.LogToConsole(package, result);
                }
            }
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Splat Facade Baker", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox("Editor-only importer for SFB packages. Unity imports asset.sfb.json files into prefab-like assets with LODs, materials and collider proxies.", MessageType.Info);

            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Validate Selected"))
                {
                    _lastReport = ValidateSelected();
                }
                if (GUILayout.Button("Reimport Selected"))
                {
                    ReimportSelectedPackages();
                    _lastReport = "Reimport requested for selected SFB packages.";
                }
                if (GUILayout.Button("Apply Texture Settings"))
                {
                    SFBTextureUtility.ApplyTextureSettingsToSelectedPackages();
                    _lastReport = "Texture settings applied to selected SFB packages.";
                }
            }

            EditorGUILayout.Space();
            EditorGUILayout.LabelField("Report", EditorStyles.boldLabel);
            _scroll = EditorGUILayout.BeginScrollView(_scroll);
            EditorGUILayout.TextArea(_lastReport, GUILayout.ExpandHeight(true));
            EditorGUILayout.EndScrollView();
        }

        private static string ValidateSelected()
        {
            var lines = new List<string>();
            foreach (Object obj in Selection.objects)
            {
                string path = AssetDatabase.GetAssetPath(obj);
                if (string.IsNullOrWhiteSpace(path) || !path.EndsWith(".sfb.json")) continue;
                var package = SFBPackageReader.Read(path);
                var result = SFBValidator.Validate(package);
                lines.Add($"{package.AssetId}: {result.Status}");
                foreach (string error in result.Errors) lines.Add($"  ERROR: {error}");
                foreach (string warning in result.Warnings) lines.Add($"  WARN: {warning}");
            }
            return lines.Count == 0 ? "No selected .sfb.json package." : string.Join("\n", lines);
        }
    }
}
#endif
