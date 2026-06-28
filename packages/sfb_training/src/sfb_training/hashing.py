from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    p=Path(path); h=hashlib.sha256()
    with p.open('rb') as f:
        while True:
            b=f.read(chunk_size)
            if not b: break
            h.update(b)
    return 'sha256:'+h.hexdigest()

def sha256_text(text: str) -> str:
    return 'sha256:'+hashlib.sha256(text.encode('utf-8')).hexdigest()

def sha256_json(data: Any) -> str:
    return sha256_text(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')))

def sha256_tree(path: str | Path, include_exts: set[str] | None=None) -> str:
    root=Path(path); h=hashlib.sha256()
    if not root.exists(): return 'sha256:missing'
    if root.is_file(): return sha256_file(root)
    for file in sorted(p for p in root.rglob('*') if p.is_file()):
        if include_exts is not None and file.suffix.lower() not in include_exts: continue
        rel=file.relative_to(root).as_posix(); h.update(rel.encode()); h.update(b'\0')
        with file.open('rb') as f:
            while True:
                b=f.read(1024*1024)
                if not b: break
                h.update(b)
        h.update(b'\0')
    return 'sha256:'+h.hexdigest()
