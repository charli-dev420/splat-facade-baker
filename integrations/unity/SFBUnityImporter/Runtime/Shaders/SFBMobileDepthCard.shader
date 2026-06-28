Shader "SFB/MobileDepthCard"
{
    Properties
    {
        _BaseMap ("Albedo", 2D) = "white" {}
        _AlphaMap ("Alpha", 2D) = "white" {}
        _Tint ("Tint", Color) = (1,1,1,1)
        _Cutoff ("Alpha Cutoff", Range(0,1)) = 0.5
    }

    SubShader
    {
        Tags { "Queue"="AlphaTest" "RenderType"="TransparentCutout" "IgnoreProjector"="True" }
        Cull Back
        ZWrite On
        Blend Off

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                float2 uv : TEXCOORD0;
            };

            sampler2D _BaseMap;
            sampler2D _AlphaMap;
            float4 _BaseMap_ST;
            float4 _Tint;
            float _Cutoff;

            v2f vert(appdata v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = TRANSFORM_TEX(v.uv, _BaseMap);
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                fixed4 col = tex2D(_BaseMap, i.uv) * _Tint;
                fixed alpha = tex2D(_AlphaMap, i.uv).r * col.a;
                clip(alpha - _Cutoff);
                col.a = alpha;
                return col;
            }
            ENDCG
        }
    }

    FallBack "Unlit/Transparent Cutout"
}
