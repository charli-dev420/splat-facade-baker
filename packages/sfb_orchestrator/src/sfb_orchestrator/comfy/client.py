from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx


class ComfyClient:
    """Small ComfyUI HTTP client used by the local orchestrator.

    ComfyUI remains an external worker. This client only handles:
    - status checks;
    - image upload;
    - prompt submission;
    - history polling;
    - basic output reference extraction.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def status(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.base_url}/system_stats")
                response.raise_for_status()
                return {"ok": True, "base_url": self.base_url, "system_stats": response.json()}
        except Exception as exc:
            return {"ok": False, "base_url": self.base_url, "error": str(exc)}

    def queue(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.base_url}/queue")
            response.raise_for_status()
            return response.json()

    def upload_image(self, path: str | Path, *, subfolder: str = "sfb", image_type: str = "input", overwrite: bool = True) -> dict[str, Any]:
        path = Path(path)
        with httpx.Client(timeout=self.timeout) as client:
            with path.open("rb") as f:
                files = {"image": (path.name, f, "application/octet-stream")}
                data = {"subfolder": subfolder, "type": image_type, "overwrite": str(overwrite).lower()}
                response = client.post(f"{self.base_url}/upload/image", data=data, files=files)
            response.raise_for_status()
            return response.json()

    def submit_prompt(self, workflow: dict[str, Any], client_id: str) -> dict[str, Any]:
        payload = {"prompt": workflow, "client_id": client_id}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/prompt", json=payload)
            response.raise_for_status()
            return response.json()

    def history(self, prompt_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.base_url}/history/{prompt_id}")
            response.raise_for_status()
            return response.json()

    def interrupt(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/interrupt")
            response.raise_for_status()
            if response.content:
                return response.json()
            return {"ok": True}

    def wait_for_history(self, prompt_id: str, *, poll_interval: float = 1.0, timeout_s: float = 3600.0) -> dict[str, Any]:
        start = time.monotonic()
        while True:
            data = self.history(prompt_id)
            if prompt_id in data:
                return data[prompt_id]
            if time.monotonic() - start > timeout_s:
                raise TimeoutError(f"ComfyUI prompt timed out: {prompt_id}")
            time.sleep(poll_interval)

    def output_refs_from_history(self, history_item: dict[str, Any]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        outputs = history_item.get("outputs", {})
        for node_id, node_outputs in outputs.items():
            if not isinstance(node_outputs, dict):
                continue
            for kind in ["images", "gifs", "videos", "files"]:
                for item in node_outputs.get(kind, []) or []:
                    if isinstance(item, dict):
                        refs.append({"node_id": node_id, "kind": kind, **item})
        return refs
