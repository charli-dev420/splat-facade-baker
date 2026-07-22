from __future__ import annotations


class SFBExperimentalBakeMapsScaffold:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"package_name": ("STRING", {"default": "SFB_Asset"})}}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "run"
    CATEGORY = "SFB"

    def run(self, package_name: str):
        return (f"SFB experimental ComfyUI scaffold active for {package_name}. Actual bake runs through sfb_core.",)


NODE_CLASS_MAPPINGS = {"SFBExperimentalBakeMapsScaffold": SFBExperimentalBakeMapsScaffold}
NODE_DISPLAY_NAME_MAPPINGS = {"SFBExperimentalBakeMapsScaffold": "SFB Experimental Bake Maps Scaffold"}
