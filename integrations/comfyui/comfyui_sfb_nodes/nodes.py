from __future__ import annotations


class SFBBakeMapsPlaceholder:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"package_name": ("STRING", {"default": "SFB_Asset"})}}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "run"
    CATEGORY = "SFB"

    def run(self, package_name: str):
        return (f"SFB ComfyUI node scaffold active for {package_name}. Actual bake runs through sfb_core.",)


NODE_CLASS_MAPPINGS = {"SFBBakeMapsPlaceholder": SFBBakeMapsPlaceholder}
NODE_DISPLAY_NAME_MAPPINGS = {"SFBBakeMapsPlaceholder": "SFB Bake Maps Placeholder"}
