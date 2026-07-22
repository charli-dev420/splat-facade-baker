from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from ..config_io import read_config
from ..registry import load_run, scan_checkpoints, update_run_status, save_run
from .diffusers_lora import build_diffusers_lora_command
from .external_process import write_command, run_external_process
from .kohya_lora import build_kohya_lora_command

def build_training_command(config: dict[str, Any], run_dir: str | Path) -> list[str]:
    backend=config.get('backend','diffusers')
    if backend=='diffusers': return build_diffusers_lora_command(config, run_dir)
    if backend=='kohya': return build_kohya_lora_command(config, run_dir)
    if backend=='shell':
        command=config.get('command') or (config.get('runner',{}) if isinstance(config.get('runner',{}),dict) else {}).get('command')
        if not isinstance(command, list) or not command: raise ValueError('shell backend requires command: [...]')
        return [str(x) for x in command]
    raise ValueError(f'Unsupported training backend: {backend}')

def run_training(run_dir: str | Path, *, dry_run: bool=False)->dict[str,Any]:
    run_dir=Path(run_dir); run=load_run(run_dir); config=read_config(run_dir/run['config']['path']); command=build_training_command(config, run_dir); write_command(run_dir, command)
    if dry_run:
        run['dry_run']=True; run['last_command']=command; run['status']='completed'; run['dry_run_report']='dry_run_report.json'; save_run(run_dir, run); (run_dir/'dry_run_report.json').write_text(json.dumps({'ok':True,'dry_run':True,'message':'Command generated but not executed.'}, indent=2)+'\n', encoding='utf-8'); return run
    update_run_status(run_dir, 'running'); result=run_external_process(command, run_dir); status='completed' if result.returncode==0 else 'failed'; run=update_run_status(run_dir, status, last_returncode=result.returncode, last_command=command); run['checkpoints']=scan_checkpoints(run_dir); save_run(run_dir, run); return run
