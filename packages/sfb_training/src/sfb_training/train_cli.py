from __future__ import annotations
import argparse, json
from pathlib import Path
from .config_io import read_config
from .eval.clean_render_eval import evaluate_clean_render_images
from .model_card import generate_model_card
from .model_registry import export_checkpoint_to_comfy, load_model_registry, promote_checkpoint
from .registry import init_training_run, list_runs, load_run, scan_checkpoints, find_checkpoint, save_run
from .runners.base import build_training_command, run_training
from .runners.external_process import shell_join, write_command

def _print(data): print(json.dumps(data, indent=2, ensure_ascii=False))
def main(argv: list[str] | None=None)->int:
    parser=argparse.ArgumentParser(prog='sfb-train'); sub=parser.add_subparsers(dest='command', required=True)
    p=sub.add_parser('init-run'); p.add_argument('--config', required=True); p.add_argument('--out'); p.add_argument('--overwrite', action='store_true')
    p=sub.add_parser('command'); p.add_argument('--run-dir', required=True); p.add_argument('--write', action='store_true')
    p=sub.add_parser('run'); p.add_argument('--run-dir', required=True); p.add_argument('--dry-run', action='store_true')
    p=sub.add_parser('runs'); ss=p.add_subparsers(dest='runs_command', required=True); q=ss.add_parser('list'); q.add_argument('--runs-root', default='runs'); q=ss.add_parser('inspect'); q.add_argument('run_dir')
    p=sub.add_parser('checkpoints'); ss=p.add_subparsers(dest='ckpt_command', required=True); q=ss.add_parser('list'); q.add_argument('--run-dir', required=True); q=ss.add_parser('inspect'); q.add_argument('--run-dir', required=True); q.add_argument('--checkpoint', required=True)
    p=sub.add_parser('eval-clean-render'); p.add_argument('--images', required=True); p.add_argument('--run-dir'); p.add_argument('--checkpoint'); p.add_argument('--eval-id', default='clean_render_eval'); p.add_argument('--out')
    p=sub.add_parser('eval-pipeline'); p.add_argument('--run-dir', required=True); p.add_argument('--checkpoint', required=True)
    p=sub.add_parser('promote'); p.add_argument('--run-dir', required=True); p.add_argument('--checkpoint', required=True); p.add_argument('--alias', required=True)
    p=sub.add_parser('model-registry'); p.add_argument('--runs-root', default='runs')
    p=sub.add_parser('export-comfy'); p.add_argument('--runs-root', default='runs'); p.add_argument('--alias'); p.add_argument('--run-dir'); p.add_argument('--checkpoint'); p.add_argument('--comfy-lora-dir', required=True); p.add_argument('--filename')
    p=sub.add_parser('model-card'); p.add_argument('--run-dir', required=True); p.add_argument('--checkpoint'); p.add_argument('--out')
    args=parser.parse_args(argv)
    if args.command=='init-run':
        r=init_training_run(args.config, args.out, args.overwrite); _print({'ok':True,'run_dir':r['output_dir'],'run_id':r['run_id'],'status':r['status']}); return 0
    if args.command=='command':
        r=load_run(args.run_dir); cfg=read_config(Path(args.run_dir)/r['config']['path']); cmd=build_training_command(cfg,args.run_dir)
        if args.write: write_command(args.run_dir, cmd)
        _print({'ok':True,'command':cmd,'shell':shell_join(cmd),'written':bool(args.write)}); return 0
    if args.command=='run':
        r=run_training(args.run_dir, dry_run=args.dry_run); _print({'ok':True,'run_id':r['run_id'],'status':r['status'],'dry_run':r.get('dry_run',False)}); return 0
    if args.command=='runs':
        _print({'runs':list_runs(args.runs_root)} if args.runs_command=='list' else load_run(args.run_dir)); return 0
    if args.command=='checkpoints':
        _print({'checkpoints':scan_checkpoints(args.run_dir)} if args.ckpt_command=='list' else find_checkpoint(args.run_dir,args.checkpoint)); return 0
    if args.command=='eval-clean-render':
        out=args.out; run_data=None; ckpt=args.checkpoint
        if args.run_dir:
            run_data=load_run(args.run_dir); out=out or str(Path(args.run_dir)/'eval'/args.eval_id)
            if args.checkpoint: ckpt=find_checkpoint(args.run_dir,args.checkpoint)['checkpoint_id']
        else: out=out or 'eval_clean_render'
        report=evaluate_clean_render_images(args.images,out_dir=out,eval_id=args.eval_id,run_id=(run_data or {}).get('run_id'),checkpoint_id=ckpt)
        if args.run_dir:
            r=load_run(args.run_dir); rp=str(Path(out).resolve()); r.setdefault('eval_reports',[])
            if rp not in r['eval_reports']: r['eval_reports'].append(rp)
            r.setdefault('metrics',{})[args.eval_id]=report['metrics']
            if report['decision_hint']=='candidate': r['status']='evaluated'; r['decision']='candidate'
            save_run(args.run_dir,r)
        _print({'ok':True,'out':out,'decision_hint':report['decision_hint'],'metrics':report['metrics']}); return 0
    if args.command=='eval-pipeline':
        _print({'ok':False,'status':'not_implemented','message':'Planned: checkpoint → ComfyUI generation → TripoSplat → SFB Baker evaluation.','run_dir':args.run_dir,'checkpoint':args.checkpoint}); return 2
    if args.command=='promote': _print({'ok':True,'promoted':promote_checkpoint(args.run_dir,args.checkpoint,args.alias)}); return 0
    if args.command=='model-registry': _print(load_model_registry(args.runs_root)); return 0
    if args.command=='export-comfy': _print(export_checkpoint_to_comfy(runs_root=args.runs_root,alias=args.alias,run_dir=args.run_dir,checkpoint=args.checkpoint,comfy_lora_dir=args.comfy_lora_dir,filename=args.filename)); return 0
    if args.command=='model-card': _print({'ok':True,'path':str(generate_model_card(args.run_dir,args.checkpoint,args.out))}); return 0
    return 2
if __name__=='__main__': raise SystemExit(main())
