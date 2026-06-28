from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image, ImageDraw
from .image_metrics import compute_image_metrics

def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _find_images(root: str | Path): return sorted(p for p in Path(root).rglob('*') if p.is_file() and p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'})
def _mean(rows, key):
    vals=[float(r[key]) for r in rows if key in r]; return round(float(np.mean(vals)),4) if vals else 0.0
def _decision(m):
    w=[]
    if m['background_uniformity']<.75: w.append('background_uniformity below 0.75')
    if m['object_centering']<.7: w.append('object_centering below 0.70')
    if m['border_touch_ratio']>.05: w.append('some images touch borders')
    if m['possible_shadow_score']>.25: w.append('possible cast shadows or non-uniform background')
    if m['brightness_mean']<.18 or m['brightness_mean']>.88: w.append('brightness_mean outside recommended range')
    return ('candidate' if not w else 'needs_review' if len(w)<=2 else 'reject_or_retrain', w)
def _grid(images, out_path: Path, max_images:int=16):
    sel=images[:max_images]
    if not sel: return
    thumbs=[]
    for p in sel:
        im=Image.open(p).convert('RGB'); im.thumbnail((160,160)); can=Image.new('RGB',(160,180),(245,245,245)); can.paste(im,((160-im.width)//2,0)); ImageDraw.Draw(can).text((4,164),p.stem[:24], fill=(0,0,0)); thumbs.append(can)
    cols=4; rows=(len(thumbs)+cols-1)//cols; grid=Image.new('RGB',(cols*160,rows*180),(230,230,230))
    for i,t in enumerate(thumbs): grid.paste(t,((i%cols)*160,(i//cols)*180))
    out_path.parent.mkdir(parents=True, exist_ok=True); grid.save(out_path)
def evaluate_clean_render_images(images_dir: str | Path, *, out_dir: str | Path, eval_id: str='clean_render_eval', run_id: str|None=None, checkpoint_id: str|None=None)->dict[str,Any]:
    images=_find_images(images_dir); rows=[compute_image_metrics(p) for p in images]
    metrics={'images_total':len(rows),'background_uniformity':_mean(rows,'background_uniformity'),'object_centering':_mean(rows,'object_centering'),'border_touch_ratio':_mean(rows,'border_touch_ratio'),'foreground_coverage':_mean(rows,'foreground_coverage'),'brightness_mean':_mean(rows,'brightness_mean'),'brightness_std':_mean(rows,'brightness_std'),'saturation_mean':_mean(rows,'saturation_mean'),'possible_shadow_score':_mean(rows,'possible_shadow_score'),'silhouette_score':_mean(rows,'silhouette_score')}
    hint,warns=_decision(metrics); report={'schema':'sfb.eval_report.v1','eval_id':eval_id,'task':'clean_render_eval','status':'completed' if images else 'failed','created_at':_now(),'run_id':run_id,'checkpoint_id':checkpoint_id,'images_dir':str(images_dir),'metrics':metrics,'warnings':warns if images else ['no images found'],'decision_hint':hint if images else 'failed','records':rows}
    out=Path(out_dir); out.mkdir(parents=True, exist_ok=True); (out/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8'); _grid(images, out/'preview_grid.png'); return report
