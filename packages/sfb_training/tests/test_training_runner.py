from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw
from sfb_training.config_io import write_config, read_config
from sfb_training.eval.clean_render_eval import evaluate_clean_render_images
from sfb_training.model_card import generate_model_card
from sfb_training.model_registry import export_checkpoint_to_comfy, promote_checkpoint
from sfb_training.registry import init_training_run, scan_checkpoints
from sfb_training.runners.base import build_training_command, run_training

def _make_lora_export(tmp_path: Path) -> Path:
    root=tmp_path/'training_exports'/'lora_clean_render_v0'; (root/'images').mkdir(parents=True); (root/'captions').mkdir(parents=True); rows=[]
    for split in ['train','val','test']:
        img=root/'images'/f'{split}_asset_front.png'; Image.new('RGB',(128,128),(230,230,230)).save(img); cap=root/'captions'/f'{split}_asset_front.txt'; cap.write_text('sfb_clean_render, orthographic object render', encoding='utf-8')
        row={'image':str(img.relative_to(root)),'caption':str(cap.relative_to(root)),'caption_text':cap.read_text(),'split':split,'asset_id':f'asset_{split}'}; rows.append(row); (root/f'{split}.jsonl').write_text(json.dumps(row)+'\n', encoding='utf-8')
    (root/'metadata.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows), encoding='utf-8'); return root

def _config(tmp_path: Path, dataset: Path, backend: str='diffusers') -> Path:
    cfg={'schema':'sfb.training_config.v1','task':'lora_clean_render','backend':backend,'run':{'run_id':'clean_render_lora_test','seed':123},'dataset':{'path':str(dataset),'export_id':'lora_clean_render_v0','train_file':'train.jsonl','val_file':'val.jsonl','test_file':'test.jsonl'},'model':{'base_model':'test/base','model_family':'sdxl','output_weight_name':'test_lora.safetensors'},'runner':{'script_path':'train_text_to_image_lora.py','accelerate_bin':'accelerate'},'training':{'resolution':512,'train_batch_size':1,'max_train_steps':10,'checkpointing_steps':5,'rank':4}}
    path=tmp_path/'config.yaml'; write_config(path,cfg); return path

def test_init_run_and_diffusers_command(tmp_path: Path) -> None:
    dataset=_make_lora_export(tmp_path); config=_config(tmp_path,dataset); run_dir=tmp_path/'runs'/'clean_render_lora_test'; run=init_training_run(config,run_dir)
    assert run['status']=='created'; assert (run_dir/'run.json').exists(); command=build_training_command(read_config(run_dir/run['config']['path']), run_dir); assert command[:2]==['accelerate','launch']; assert '--train_data_dir' in command; assert str(dataset) in command

def test_dry_run_writes_command(tmp_path: Path) -> None:
    dataset=_make_lora_export(tmp_path); config=_config(tmp_path,dataset); run_dir=tmp_path/'runs'/'clean_render_lora_test'; init_training_run(config,run_dir); run=run_training(run_dir,dry_run=True); assert run['status']=='completed'; assert run['dry_run'] is True; assert (run_dir/'command.sh').exists(); assert (run_dir/'dry_run_report.json').exists()

def test_checkpoint_scan_promote_export_and_model_card(tmp_path: Path) -> None:
    dataset=_make_lora_export(tmp_path); config=_config(tmp_path,dataset); run_dir=tmp_path/'runs'/'clean_render_lora_test'; init_training_run(config,run_dir); ckpt_dir=run_dir/'checkpoints'/'checkpoint-0005'; ckpt_dir.mkdir(parents=True); (ckpt_dir/'test_lora.safetensors').write_bytes(b'fake-weights')
    checkpoints=scan_checkpoints(run_dir); assert len(checkpoints)==1; assert checkpoints[0]['step']==5; promoted=promote_checkpoint(run_dir,'checkpoint-0005','clean-render-current'); assert promoted['alias']=='clean-render-current'
    export_dir=tmp_path/'ComfyUI'/'models'/'loras'; result=export_checkpoint_to_comfy(runs_root=run_dir.parent, alias='clean-render-current', comfy_lora_dir=export_dir); assert Path(result['dest']).exists(); card=generate_model_card(run_dir, checkpoint='checkpoint-0005'); assert card.exists(); assert 'clean_render_lora_test' in card.read_text(encoding='utf-8')

def _draw_clean_image(path: Path, offset:int=0)->None:
    img=Image.new('RGB',(160,160),(230,230,230)); draw=ImageDraw.Draw(img); draw.rectangle((50+offset,35,110+offset,125), fill=(120,120,120)); img.save(path)

def test_clean_render_eval(tmp_path: Path) -> None:
    images=tmp_path/'images'; images.mkdir(); _draw_clean_image(images/'a.png'); _draw_clean_image(images/'b.png', offset=2); out=tmp_path/'eval'; report=evaluate_clean_render_images(images,out_dir=out,eval_id='test_eval'); assert report['status']=='completed'; assert report['metrics']['images_total']==2; assert report['metrics']['background_uniformity']>.8; assert (out/'report.json').exists(); assert (out/'preview_grid.png').exists()
