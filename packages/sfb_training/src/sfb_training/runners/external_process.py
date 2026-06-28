from __future__ import annotations
import os, shlex, subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
@dataclass
class ProcessResult:
    returncode:int; command:list[str]; stdout_log:str; stderr_log:str; dry_run:bool=False
def shell_join(command: Sequence[str]) -> str: return ' '.join(shlex.quote(str(x)) for x in command)
def write_command(run_dir: str | Path, command: Sequence[str]) -> Path:
    p=Path(run_dir)/'command.sh'; p.write_text('#!/usr/bin/env bash\nset -euo pipefail\n'+shell_join(command)+'\n', encoding='utf-8')
    try: p.chmod(0o755)
    except Exception: pass
    return p
def run_external_process(command: Sequence[str], run_dir: str | Path, *, dry_run: bool=False, env: dict[str,str]|None=None)->ProcessResult:
    run_dir=Path(run_dir); logs=run_dir/'logs'; logs.mkdir(parents=True, exist_ok=True); out=logs/'stdout.log'; err=logs/'stderr.log'; write_command(run_dir, command)
    if dry_run:
        out.write_text('dry-run: command not executed\n'+shell_join(command)+'\n', encoding='utf-8'); err.write_text('', encoding='utf-8'); return ProcessResult(0, list(command), str(out), str(err), True)
    merged=os.environ.copy();
    if env: merged.update(env)
    with out.open('w', encoding='utf-8') as stdout, err.open('w', encoding='utf-8') as stderr:
        proc=subprocess.run(list(command), cwd=run_dir, env=merged, stdout=stdout, stderr=stderr, text=True)
    return ProcessResult(proc.returncode, list(command), str(out), str(err), False)
