from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEXT_SUFFIXES = {".json", ".yaml", ".yml", ".md", ".txt", ".py", ".ps1"}


def _text_files_under(*roots: Path) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                files.append(path)
    return files


def test_public_examples_do_not_ship_placeholder_or_noop_contracts() -> None:
    public_files = _text_files_under(
        ROOT / "examples",
        ROOT / "workflows" / "comfyui" / "examples",
    )

    offenders: list[str] = []
    for path in public_files:
        text = path.read_text(encoding="utf-8").lower()
        if "placeholder" in text or "noop" in text:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_comfyui_fixture_metadata_resolves_template() -> None:
    fixture_dir = ROOT / "packages" / "sfb_orchestrator" / "tests" / "fixtures" / "comfyui_dry_run"
    metadata_path = fixture_dir / "comfy_dry_run.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    template_path = fixture_dir / metadata["template_file"]

    assert metadata["workflow_id"] == "comfy_dry_run_fixture_v1"
    assert template_path.exists()
    assert template_path.is_file()


def test_public_comfyui_metadata_examples_do_not_reference_missing_templates() -> None:
    example_dir = ROOT / "workflows" / "comfyui" / "examples"
    missing: list[str] = []
    for metadata_path in example_dir.rglob("*.metadata.json") if example_dir.exists() else []:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        template = metadata.get("template_file")
        if template and not (metadata_path.parent / template).exists():
            missing.append(str(metadata_path.relative_to(ROOT)))

    assert missing == []
