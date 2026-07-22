using System;
using UnityEngine;

namespace SFB.Runtime
{
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
