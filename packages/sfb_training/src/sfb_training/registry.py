from __future__ import annotations
import json, shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .config_io import read_config
from .hashing import sha256_file, sha256_tree

def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def read_json(path: str | Path) -> dict[str, Any]: return json.loads(Path(path).read_text(encoding='utf-8'))
def write_json(path: str | Path, data: dict[str, Any]) -> None:
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')

def _copy_config(config_path: Path, run_dir: Path) -> Path:
    target=run_dir/'config'/config_path.name; target.parent.mkdir(parents=True, exist_ok=True)
    if config_path.resolve()!=target.resolve(): shutil.copy2(config_path, target)
    return target

def init_training_run(config_path: str | Path, out_dir: str | Path | None=None, overwrite: bool=False) -> dict[str, Any]:
    config_path=Path(config_path); config=read_config(config_path)
    run_cfg=config.get('run',{}) if isinstance(config.get('run',{}),dict) else {}
    run_id=run_cfg.get('run_id') or config.get('run_id')
    if not run_id: raise ValueError('Training config must define run.run_id or run_id')
    run_dir=Path(out_dir or config.get('output_dir') or Path('runs')/str(run_id))
    if run_dir.exists() and not overwrite and (run_dir/'run.json').exists(): raise FileExistsError(f'Run already exists: {run_dir}')
    run_dir.mkdir(parents=True, exist_ok=True); copied=_copy_config(config_path, run_dir)
    ds_cfg=config.get('dataset',{}) if isinstance(config.get('dataset',{}),dict) else {}; ds_path=ds_cfg.get('path') or config.get('dataset') or ''
    ds_export_id=ds_cfg.get('export_id') or (Path(str(ds_path)).name if ds_path else 'unknown')
    model_cfg=config.get('model',{}) if isinstance(config.get('model',{}),dict) else {}; base_model=model_cfg.get('base_model') or config.get('base_model') or 'unknown'; family=model_cfg.get('model_family') or 'unknown'
    run={'schema':'sfb.training_run.v1','run_id':run_id,'task':config.get('task','lora_clean_render'),'backend':config.get('backend','diffusers'),'status':'created','created_at':now_iso(),'started_at':None,'ended_at':None,'dry_run':False,'dataset_export':{'path':str(ds_path),'export_id':str(ds_export_id),'hash':sha256_tree(ds_path) if ds_path else 'sha256:none'},'dataset_export_id':str(ds_export_id),'dataset_hash':sha256_tree(ds_path) if ds_path else 'sha256:none','config':{'source_path':str(config_path),'path':str(copied.relative_to(run_dir)),'hash':sha256_file(copied)},'config_hash':sha256_file(copied),'base_model':{'name':str(base_model),'type':str(family)},'checkpoints':[],'eval_reports':[],'metrics':{},'decision':'draft','output_dir':str(run_dir)}
    write_json(run_dir/'run.json', run); return run

def load_run(run_dir: str | Path) -> dict[str, Any]: return read_json(Path(run_dir)/'run.json')
def save_run(run_dir: str | Path, run: dict[str, Any]) -> None: write_json(Path(run_dir)/'run.json', run)
def update_run_status(run_dir: str | Path, status: str, **updates: Any) -> dict[str, Any]:
    run=load_run(run_dir); run['status']=status; run.update(updates)
    if status=='running' and not run.get('started_at'): run['started_at']=now_iso()
    if status in {'completed','failed','cancelled','evaluated','approved','archived'}: run['ended_at']=run.get('ended_at') or now_iso()
    save_run(run_dir, run); return run

def list_runs(runs_root: str | Path='runs') -> list[dict[str, Any]]:
    root=Path(runs_root); out=[]
    if not root.exists(): return []
    for f in sorted(root.glob('*/run.json')):
        try: out.append(read_json(f))
        except Exception: pass
    return out
@dataclass(frozen=True)
class CheckpointInfo:
    checkpoint_id: str; run_id: str; step: int | None; path: str; weight_file: str | None; format: str
    def as_dict(self)->dict[str,Any]: return {'schema':'sfb.checkpoint.v1','checkpoint_id':self.checkpoint_id,'run_id':self.run_id,'step':self.step,'path':self.path,'weight_file':self.weight_file,'format':self.format,'created_at':now_iso(),'eval_status':'not_evaluated','promotion_status':'none'}
def _parse_step(name: str)->int|None:
    digits=''.join(ch for ch in name if ch.isdigit()); return int(digits) if digits else None
def scan_checkpoints(run_dir: str | Path)->list[dict[str,Any]]:
    run_dir=Path(run_dir); run=load_run(run_dir); run_id=run['run_id']; candidates=[]; cdir=run_dir/'checkpoints'
    if cdir.exists(): candidates += [p for p in cdir.iterdir() if p.is_dir()] + list(cdir.glob('*.safetensors'))
    candidates += [p for p in run_dir.glob('checkpoint-*') if p.is_dir()]
    infos=[]; seen=set()
    for p in sorted(candidates):
        key=str(p.resolve())
        if key in seen: continue
        seen.add(key)
        if p.is_dir():
            weights=sorted(list(p.glob('*.safetensors'))+list(p.glob('*.bin'))); weight=weights[0].name if weights else None; fmt=weight.split('.')[-1] if weight else 'directory'
        else: weight=p.name; fmt=p.suffix.lstrip('.') or 'file'
        step=_parse_step(p.name); ckpt_id=f'{run_id}_step_{step}' if step is not None else f'{run_id}_{p.stem}'; rel=str(p.relative_to(run_dir)) if p.is_relative_to(run_dir) else str(p)
        infos.append(CheckpointInfo(ckpt_id, run_id, step, rel, weight, fmt).as_dict())
    run['checkpoints']=infos; save_run(run_dir, run); return infos
def find_checkpoint(run_dir: str | Path, checkpoint: str)->dict[str,Any]:
    for ckpt in scan_checkpoints(run_dir):
        if checkpoint in {ckpt['checkpoint_id'], Path(ckpt['path']).name, ckpt['path']}: return ckpt
    raise FileNotFoundError(f'Checkpoint not found in {run_dir}: {checkpoint}')
