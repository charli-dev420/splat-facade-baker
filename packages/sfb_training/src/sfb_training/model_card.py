from __future__ import annotations
from pathlib import Path
from typing import Any
from .registry import find_checkpoint, load_run

def generate_model_card(run_dir: str | Path, checkpoint: str|None=None, out: str|Path|None=None)->Path:
    run_dir=Path(run_dir); run=load_run(run_dir); ckpt:dict[str,Any]|None=find_checkpoint(run_dir, checkpoint) if checkpoint else None
    lines=[f"# {run['run_id']}", '', '## Summary', '', f"- Task: `{run.get('task')}`", f"- Backend: `{run.get('backend')}`", f"- Status: `{run.get('status')}`", f"- Decision: `{run.get('decision','draft')}`", f"- Dataset: `{run.get('dataset_export',{}).get('path')}`", f"- Dataset hash: `{run.get('dataset_hash')}`", f"- Config hash: `{run.get('config_hash')}`", f"- Base model: `{run.get('base_model',{}).get('name')}`", '', '## Intended use', '', 'This checkpoint is intended for SFB clean-render / controlled-view asset generation workflows. It is not a general-purpose image model release.', '']
    if ckpt: lines += ['## Checkpoint','', f"- Checkpoint ID: `{ckpt.get('checkpoint_id')}`", f"- Step: `{ckpt.get('step')}`", f"- Path: `{ckpt.get('path')}`", f"- Weight file: `{ckpt.get('weight_file')}`", '']
    if run.get('eval_reports'):
        lines += ['## Evaluation reports',''] + [f"- `{r}`" for r in run.get('eval_reports',[])] + ['']
    lines += ['## Limitations','','- Does not guarantee 3D correctness.','- Must be evaluated through the real SFB pipeline before production use.','- Dataset, base model and generated assets may have separate licenses.','']
    target=Path(out) if out else run_dir/'model_card.md'; target.parent.mkdir(parents=True, exist_ok=True); target.write_text('\n'.join(lines), encoding='utf-8'); return target
