param(
  [string]$UnityExe = "C:\Program Files\Unity\Hub\Editor\6000.3.18f1\Editor\Unity.exe",
  [string]$ProjectPath = "workspace\unity_smoke",
  [string]$ReportPath = "",
  [switch]$Clean
)

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Resolve-LocalPath {
  param([string]$PathValue)
  if ([System.IO.Path]::IsPathRooted($PathValue)) {
    return [System.IO.Path]::GetFullPath($PathValue)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $repo $PathValue))
}

$project = Resolve-LocalPath $ProjectPath
$packageSourcePath = Join-Path $repo "integrations\unity\SFBUnityImporter"
$demoPackage = Join-Path $repo "examples\sfb_packages\DemoWall"
$demoScene = Join-Path $repo "examples\scenes\demo_lane.sfbscene.json"
$logPath = Join-Path $project "unity_smoke.log"
$projectParent = Split-Path -Parent $project
$packagePath = Join-Path $projectParent "SFBUnityImporterPackage"
$createLogPath = Join-Path $projectParent "unity_smoke_create.log"
if ([string]::IsNullOrWhiteSpace($ReportPath)) {
  $reportPath = Join-Path $projectParent "unity_smoke_report.json"
} else {
  $reportPath = Resolve-LocalPath $ReportPath
}

function Invoke-UnityBatch {
  param([string[]]$Arguments)
  & $UnityExe @Arguments | Out-Null
  if ($null -eq $LASTEXITCODE) {
    return 0
  }
  return [int]$LASTEXITCODE
}

function Write-GateReport {
  param(
    [string]$Status,
    [bool]$Ok,
    [bool]$Blocked,
    [int]$ExitCode,
    [string]$LogFile,
    [string[]]$Errors = @(),
    [string[]]$Warnings = @(),
    [hashtable]$Counts = @{},
    [string[]]$Artifacts = @()
  )
  $report = [ordered]@{
    schema = "sfb.unity_import_gate.v1"
    ok = $Ok
    status = $Status
    blocked = $Blocked
    project = $project
    package = $demoPackage
    scene = $demoScene
    counts = $Counts
    errors = $Errors
    warnings = $Warnings
    artifacts = $Artifacts
    log = $LogFile
    exit_code = $ExitCode
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $reportPath) | Out-Null
  ($report | ConvertTo-Json -Depth 8) | Set-Content -Path $reportPath -Encoding UTF8
}

New-Item -ItemType Directory -Force -Path $projectParent | Out-Null
Remove-Item -LiteralPath $reportPath -Force -ErrorAction SilentlyContinue

if (!(Test-Path $UnityExe)) {
  Write-GateReport `
    -Status "blocked_unity_executable_missing" `
    -Ok $false `
    -Blocked $true `
    -ExitCode -1 `
    -LogFile "" `
    -Errors @("unity_executable_missing:$UnityExe")
  throw "Unity executable not found: $UnityExe"
}

if ($Clean -and (Test-Path $project)) {
  Remove-Item -LiteralPath $project -Recurse -Force
}

Remove-Item -LiteralPath $packagePath -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -Path $packageSourcePath -Destination $packagePath -Recurse -Force

if (!(Test-Path $project)) {
  $exitCode = Invoke-UnityBatch @("-batchmode", "-quit", "-createProject", $project, "-logFile", $createLogPath)
  if ($exitCode -ne 0 -or !(Test-Path $project)) {
    $status = "blocked_unity_project_creation_failed"
    if ((Test-Path $createLogPath) -and ((Get-Content -Path $createLogPath -Raw) -match "No valid Unity Editor license found")) {
      $status = "blocked_unity_license_unavailable"
    }
    Write-GateReport `
      -Status $status `
      -Ok $false `
      -Blocked $true `
      -ExitCode $exitCode `
      -LogFile $createLogPath `
      -Errors @("unity_project_creation_failed:$exitCode")
    throw "Unity project creation failed with exit code $exitCode. See $createLogPath"
  }
}

$assetsDir = Join-Path $project "Assets"
$importsDir = Join-Path $assetsDir "SFBImports"
$editorDir = Join-Path $assetsDir "Editor"
$packagesDir = Join-Path $project "Packages"
New-Item -ItemType Directory -Force -Path $importsDir, $editorDir, $packagesDir | Out-Null

$copiedDemoPackage = Join-Path $importsDir "DemoWall"
Remove-Item -LiteralPath $copiedDemoPackage -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -Path $demoPackage -Destination $copiedDemoPackage -Recurse -Force
Copy-Item -Path $demoScene -Destination (Join-Path $importsDir "demo_lane.sfbscene.json") -Force

$manifestPath = Join-Path $packagesDir "manifest.json"
$packageUri = ("file:" + $packagePath.Replace("\", "/"))
$manifestJson = @"
{
  "dependencies": {
    "dev.splatfacadebaker.unity-importer": "$packageUri",
    "com.unity.test-framework": "1.4.6"
  }
}
"@
$manifestJson | Set-Content -Path $manifestPath -Encoding UTF8

$smokeCs = @'
using System;
using System.Collections.Generic;
using System.IO;
using SFB.Runtime;
using UnityEditor;
using UnityEngine;

public static class SFBUnitySmoke
{
    private static void Assert(bool condition, string message)
    {
        if (!condition)
        {
            throw new Exception("SFB Unity certification failed: " + message);
        }
    }

    private static string JsonEscape(string value)
    {
        return value.Replace("\\", "\\\\").Replace("\"", "\\\"");
    }

    private static void AddCardMetadata(HashSet<string> ids, SFBSceneCardMetadata[] components)
    {
        foreach (var component in components)
        {
            if (component == null)
            {
                continue;
            }
            ids.Add(string.IsNullOrEmpty(component.sceneCardId) ? component.GetInstanceID().ToString() : component.sceneCardId);
        }
    }

    public static void Run()
    {
        string assetPath = "Assets/SFBImports/DemoWall/asset.sfb.json";
        string scenePath = "Assets/SFBImports/demo_lane.sfbscene.json";
        AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceUpdate);
        AssetDatabase.ImportAsset(scenePath, ImportAssetOptions.ForceUpdate);

        var asset = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
        var scene = AssetDatabase.LoadAssetAtPath<GameObject>(scenePath);
        Assert(asset != null, "asset GameObject did not load");
        Assert(scene != null, "scene GameObject did not load");
        Assert(asset.name != "SFB_Import_Failed", "asset importer returned failure placeholder");
        Assert(scene.name != "SFB_Scene_Import_Failed", "scene importer returned failure placeholder");

        var assetInstance = UnityEngine.Object.Instantiate(asset);
        var sceneInstance = UnityEngine.Object.Instantiate(scene);
        assetInstance.name = "SFBUnitySmokeAssetInstance";
        sceneInstance.name = "SFBUnitySmokeSceneInstance";

        var assetMetadata = assetInstance.GetComponent<SFBAssetMetadata>();
        Assert(assetMetadata != null, "missing SFBAssetMetadata");
        Assert(assetMetadata.assetId == "DemoWall", "unexpected assetId " + assetMetadata.assetId);
        Assert(assetMetadata.qualityStatus != "import_failed", "asset metadata reports import_failed");
        Assert(assetInstance.GetComponent<LODGroup>() != null, "missing LODGroup");
        Assert(assetInstance.transform.Find("Visual") != null, "missing Visual child");
        var renderers = assetInstance.GetComponentsInChildren<MeshRenderer>(true);
        Assert(renderers.Length >= 1, "missing MeshRenderer");
        int materialCount = 0;
        foreach (var renderer in renderers)
        {
            if (renderer.sharedMaterial != null)
            {
                materialCount++;
            }
        }
        Assert(materialCount >= 1, "missing material");
        Assert(assetInstance.transform.Find("Collision") != null, "missing Collision child");
        var colliders = assetInstance.GetComponentsInChildren<BoxCollider>(true);
        Assert(colliders.Length >= 1, "missing BoxCollider");

        var sceneMetadata = sceneInstance.GetComponent<SFBSceneMetadata>();
        Assert(sceneMetadata != null, "missing SFBSceneMetadata");
        Assert(sceneMetadata.sceneId == "demo_lane_v0", "unexpected sceneId " + sceneMetadata.sceneId);
        Assert(sceneMetadata.cardCount == 2, "unexpected cardCount " + sceneMetadata.cardCount);
        Assert(sceneMetadata.chunkCount == 1, "unexpected chunkCount " + sceneMetadata.chunkCount);
        var cardMetadata = sceneInstance.GetComponentsInChildren<SFBSceneCardMetadata>(true);
        var cardMetadataIds = new HashSet<string>();
        AddCardMetadata(cardMetadataIds, cardMetadata);
        int subAssetGameObjectCount = 0;
        int subAssetCardMetadataCount = 0;
        foreach (var subAsset in AssetDatabase.LoadAllAssetsAtPath(scenePath))
        {
            var subAssetGameObject = subAsset as GameObject;
            if (subAssetGameObject == null)
            {
                continue;
            }
            subAssetGameObjectCount++;
            int directCards = subAssetGameObject.GetComponents<SFBSceneCardMetadata>().Length;
            subAssetCardMetadataCount += directCards;
            AddCardMetadata(cardMetadataIds, subAssetGameObject.GetComponents<SFBSceneCardMetadata>());
            if (subAssetGameObject != scene)
            {
                int childCards = subAssetGameObject.GetComponentsInChildren<SFBSceneCardMetadata>(true).Length;
                subAssetCardMetadataCount += childCards;
                AddCardMetadata(cardMetadataIds, subAssetGameObject.GetComponentsInChildren<SFBSceneCardMetadata>(true));
            }
        }
        int cardMetadataCount = cardMetadataIds.Count;
        Assert(cardMetadataCount >= 2, "missing card metadata components; hierarchy=" + cardMetadata.Length + ", subasset_gameobjects=" + subAssetGameObjectCount + ", subasset_cards=" + subAssetCardMetadataCount);

        string report = "{\n" +
            "  \"schema\": \"sfb.unity_import_gate.v1\",\n" +
            "  \"ok\": true,\n" +
            "  \"status\": \"passed\",\n" +
            "  \"blocked\": false,\n" +
            "  \"asset\": \"" + JsonEscape(assetPath) + "\",\n" +
            "  \"scene\": \"" + JsonEscape(scenePath) + "\",\n" +
            "  \"counts\": {\n" +
            "    \"lods\": " + asset.GetComponent<LODGroup>().GetLODs().Length + ",\n" +
            "    \"renderers\": " + renderers.Length + ",\n" +
            "    \"materials\": " + materialCount + ",\n" +
            "    \"colliders\": " + colliders.Length + ",\n" +
            "    \"cards\": " + sceneMetadata.cardCount + ",\n" +
            "    \"chunks\": " + sceneMetadata.chunkCount + ",\n" +
            "    \"card_metadata_components\": " + cardMetadataCount + "\n" +
            "  },\n" +
            "  \"errors\": [],\n" +
            "  \"warnings\": [],\n" +
            "  \"artifacts\": [\"" + JsonEscape(assetPath) + "\", \"" + JsonEscape(scenePath) + "\"],\n" +
            "  \"log\": \"SFBUnitySmokeReport.json\"\n" +
            "}\n";
        File.WriteAllText(Path.Combine(Directory.GetCurrentDirectory(), "SFBUnitySmokeReport.json"), report);
        UnityEngine.Object.DestroyImmediate(assetInstance);
        UnityEngine.Object.DestroyImmediate(sceneInstance);
        Debug.Log("SFB Unity certification passed");
    }
}
'@
$smokePath = Join-Path $editorDir "SFBUnitySmoke.cs"
$smokeCs | Set-Content -Path $smokePath -Encoding UTF8

$exitCode = Invoke-UnityBatch @("-batchmode", "-quit", "-projectPath", $project, "-executeMethod", "SFBUnitySmoke.Run", "-logFile", $logPath)
if ($exitCode -ne 0) {
  $status = "failed_unity_import_smoke"
  $blocked = $false
  if ((Test-Path $logPath) -and ((Get-Content -Path $logPath -Raw) -match "No valid Unity Editor license found")) {
    $status = "blocked_unity_license_unavailable"
    $blocked = $true
  }
  Write-GateReport `
    -Status $status `
    -Ok $false `
    -Blocked $blocked `
    -ExitCode $exitCode `
    -LogFile $logPath `
    -Errors @("unity_import_failed:$exitCode")
  throw "Unity import smoke failed with exit code $exitCode. See $logPath"
}

$unityReportPath = Join-Path $project "SFBUnitySmokeReport.json"
if (!(Test-Path $unityReportPath)) {
  Write-GateReport `
    -Status "failed_unity_report_missing" `
    -Ok $false `
    -Blocked $false `
    -ExitCode $exitCode `
    -LogFile $logPath `
    -Errors @("unity_report_missing:$unityReportPath")
  throw "Unity smoke report was not written: $unityReportPath"
}

Copy-Item -Path $unityReportPath -Destination $reportPath -Force
Get-Content -Path $reportPath
