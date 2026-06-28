using System;
using UnityEngine;

namespace SFB.Runtime
{
    [Serializable]
    public class SFBAssetMetadata : MonoBehaviour
    {
        [Header("Identity")]
        public string assetId;
        public string sourceAssetId;
        public string source;

        [Header("View")]
        public string viewId;
        public string viewContract;
        public string bakeMode;
        public string pivot;

        [Header("Dimensions")]
        public float widthMeters;
        public float heightMeters;
        public float maxDepthMeters;

        [Header("Camera")]
        public string cameraType = "orthographic";
        public float azimuthDeg;
        public float elevationDeg;

        [Header("Runtime")]
        public string mobileTier;
        public string alphaMode;
        public string recommendedMaterial;
        public int lodCount;

        [Header("Metrics")]
        public string qualityStatus;
        public int verticesLod0;
        public int trianglesLod0;
        public float alphaCoverage;
        public float depthRangeMeters;
        public float estimatedTextureMemoryMb;

        [Header("SFB")]
        public string packagePath;
        public string reportPath;
        public string importedByVersion = "0.7.0-pre";
    }
}
