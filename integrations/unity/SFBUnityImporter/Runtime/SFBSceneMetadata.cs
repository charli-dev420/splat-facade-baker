using System;
using UnityEngine;

namespace SFB.Runtime
{
    [Serializable]
    public class SFBSceneMetadata : MonoBehaviour
    {
        [Header("Identity")]
        public string sceneId;
        public string units = "meters";
        public string cameraMode = "isometric_2_5d";
        public string mobileProfile = "mobile_mid";

        [Header("Counts")]
        public int cardCount;
        public int chunkCount;

        [Header("SFB")]
        public string scenePath;
        public string importedByVersion = "0.8.0-pre";
    }

    [Serializable]
    public class SFBSceneCardMetadata : MonoBehaviour
    {
        public string sceneCardId;
        public string assetPackage;
        public string viewId;
        public string viewContract;
        public string chunkId;
        public int occlusionLayer;
        public float widthMeters;
        public float heightMeters;
        public float depthMeters;
        public string status;
    }
}
