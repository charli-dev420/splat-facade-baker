from __future__ import annotations

import argparse
import json
from pathlib import Path


_PATHLIKE_PREFIXES = ("mesh/", "textures/", "collision/", "preview/", "reports/", "debug/")


def _collect_paths(data: object, prefix: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            child = f"{prefix}.{key}" if prefix else key
            found.extend(_collect_paths(value, child))
    elif isinstance(data, list):
        for idx, value in enumerate(data):
            found.extend(_collect_paths(value, f"{prefix}[{idx}]"))
    elif isinstance(data, str) and data.startswith(_PATHLIKE_PREFIXES):
        found.append((prefix, data))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", help="Path to asset.sfb.json")
    args = parser.parse_args()
    package_path = Path(args.package)
    data = json.loads(package_path.read_text(encoding="utf-8"))
    root = package_path.parent
    missing = []
    for field, rel in _collect_paths(data):
        if not (root / rel).exists():
            missing.append(f"{field}: {rel}")
    print(json.dumps({"ok": not missing, "missing": missing}, indent=2))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
