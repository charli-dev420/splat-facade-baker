from __future__ import annotations
import json, shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .registry import find_checkpoint, load_run, save_run, scan_checkpoints

def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _registry_path(root): return Path(root)/'model_registry.json'
def load_model_registry(runs_root: str | Path)->dict[str,Any]:
    p=_registry_path(runs_root)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'schema':'sfb.model_registry.v1','created_at':_now(),'aliases':{},'models':[]}
def save_model_registry(runs_root, data):
    p=_registry_path(runs_root); p.parent.mkdir(parents=True, exist_ok=True); data['updated_at']=_now(); p.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
def _ckpt_abs(run_dir, ckpt):
    p=Path(ckpt['path']); return p if p.is_absolute() else Path(run_dir)/p
def _weight_abs(run_dir, ckpt):
    p=_ckpt_abs(run_dir, ckpt); weight=ckpt.get('weight_file')
    if p.is_dir():
        if weight: return p/weight
        weights=sorted(list(p.glob('*.safetensors'))+list(p.glob('*.bin')))
        if weights: return weights[0]
        raise FileNotFoundError(f'Checkpoint directory contains no weight file: {p}')
    return p
def promote_checkpoint(run_dir: str | Path, checkpoint: str, alias: str)->dict[str,Any]:
    run_dir=Path(run_dir); run=load_run(run_dir); checkpoints=scan_checkpoints(run_dir); ckpt=find_checkpoint(run_dir, checkpoint); ckpt.update({'promotion_status':'approved','promoted_alias':alias,'promoted_at':_now()})
    for item in checkpoints:
        if item['checkpoint_id']==ckpt['checkpoint_id']: item.update(ckpt)
    run['checkpoints']=checkpoints; run['decision']='approved'; run['status']='approved'; save_run(run_dir, run)
    entry={'alias':alias,'run_id':run['run_id'],'run_dir':str(run_dir),'checkpoint_id':ckpt['checkpoint_id'],'checkpoint_path':str(_ckpt_abs(run_dir, ckpt)),'weight_file':ckpt.get('weight_file'),'task':run.get('task'),'backend':run.get('backend'),'base_model':run.get('base_model'),'promoted_at':_now()}
    reg=load_model_registry(run_dir.parent); reg.setdefault('aliases',{})[alias]=entry; reg['models']=[m for m in reg.get('models',[]) if not (m.get('alias')==alias and m.get('checkpoint_id')==ckpt['checkpoint_id'])]+[entry]; save_model_registry(run_dir.parent, reg); return entry
def resolve_alias(runs_root: str | Path, alias: str)->dict[str,Any]:
    reg=load_model_registry(runs_root)
    if alias not in reg.get('aliases',{}): raise KeyError(f'Alias not found in model registry: {alias}')
    return reg['aliases'][alias]
def export_checkpoint_to_comfy(*, runs_root: str | Path, alias: str|None=None, run_dir: str|Path|None=None, checkpoint: str|None=None, comfy_lora_dir: str|Path, filename: str|None=None)->dict[str,Any]:
    if alias:
        entry=resolve_alias(runs_root, alias); run_dir_path=Path(entry['run_dir']); ckpt=find_checkpoint(run_dir_path, entry['checkpoint_id'])
    else:
        if not run_dir or not checkpoint: raise ValueError('Either alias or run_dir+checkpoint is required')
        run_dir_path=Path(run_dir); ckpt=find_checkpoint(run_dir_path, checkpoint)
    src=_weight_abs(run_dir_path, ckpt)
    if not src.exists(): raise FileNotFoundError(f'Checkpoint weight file does not exist: {src}')
    dest_dir=Path(comfy_lora_dir); dest_dir.mkdir(parents=True, exist_ok=True); dest=dest_dir/(filename or src.name); shutil.copy2(src,dest); return {'ok':True,'source':str(src),'dest':str(dest),'checkpoint_id':ckpt['checkpoint_id']}
