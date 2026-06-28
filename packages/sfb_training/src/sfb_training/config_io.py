from __future__ import annotations
import json
from pathlib import Path
from typing import Any
try:
    import yaml
except Exception:
    yaml=None  # type: ignore

def read_config(path: str | Path) -> dict[str, Any]:
    p=Path(path); text=p.read_text(encoding='utf-8')
    if p.suffix.lower()=='.json': return json.loads(text)
    if p.suffix.lower() in {'.yaml','.yml'}:
        if yaml is None: raise RuntimeError('PyYAML is required to read YAML training configs.')
        data=yaml.safe_load(text) or {}
        if not isinstance(data, dict): raise ValueError(f'Config must be a mapping: {p}')
        return data
    raise ValueError(f'Unsupported config extension: {p.suffix}')

def write_config(path: str | Path, data: dict[str, Any]) -> None:
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower()=='.json':
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8'); return
    if p.suffix.lower() in {'.yaml','.yml'}:
        if yaml is None: p.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        else: p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding='utf-8')
        return
    raise ValueError(f'Unsupported config extension: {p.suffix}')
