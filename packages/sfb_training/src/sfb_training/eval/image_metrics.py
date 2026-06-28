from __future__ import annotations
from pathlib import Path
from typing import Any
import math, numpy as np
from PIL import Image

def _load_rgb(path: str | Path) -> np.ndarray: return np.asarray(Image.open(path).convert('RGB')).astype(np.float32)/255.0
def _border_pixels(arr: np.ndarray, border: int=8)->np.ndarray:
    h,w,_=arr.shape; b=max(1, min(border, h//8, w//8)); return np.concatenate([arr[:b,:,:].reshape(-1,3),arr[-b:,:,:].reshape(-1,3),arr[:,:b,:].reshape(-1,3),arr[:,-b:,:].reshape(-1,3)], axis=0)
def _foreground_mask(arr: np.ndarray)->np.ndarray:
    bg=np.median(_border_pixels(arr), axis=0); diff=np.linalg.norm(arr-bg[None,None,:], axis=2); thr=max(0.07, float(np.percentile(diff,85))*0.35); return diff>thr
def _bbox(mask: np.ndarray):
    ys,xs=np.where(mask)
    if len(xs)==0: return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
def compute_image_metrics(path: str | Path)->dict[str,Any]:
    arr=_load_rgb(path); h,w,_=arr.shape; border=_border_pixels(arr); border_std=float(np.mean(np.std(border, axis=0))); bg_uniform=float(max(0,min(1,1-border_std*8)))
    mask=_foreground_mask(arr); coverage=float(mask.mean()); bb=_bbox(mask)
    if bb is None: centering=0.0; touch=1.0; bbox_norm=None
    else:
        x0,y0,x1,y1=bb; cx=(x0+x1)/2/max(1,w-1); cy=(y0+y1)/2/max(1,h-1); dist=math.sqrt((cx-.5)**2+(cy-.5)**2); centering=float(max(0,min(1,1-dist*2))); touches=int(x0<=1)+int(y0<=1)+int(x1>=w-2)+int(y1>=h-2); touch=float(touches/4); bbox_norm=[x0/w,y0/h,x1/w,y1/h]
    brightness=arr.mean(axis=2); maxc=arr.max(axis=2); minc=arr.min(axis=2); sat=np.where(maxc>1e-6,(maxc-minc)/np.maximum(maxc,1e-6),0)
    border_luma=np.mean(border, axis=1); shadow=float(max(0,min(1,np.std(border_luma)*6))); silhouette=float(max(0,min(1,coverage*2))*(1-min(1,touch)))
    return {'image':str(path),'width':w,'height':h,'background_uniformity':round(bg_uniform,4),'object_centering':round(centering,4),'border_touch_ratio':round(touch,4),'foreground_coverage':round(coverage,4),'brightness_mean':round(float(brightness.mean()),4),'brightness_std':round(float(brightness.std()),4),'saturation_mean':round(float(sat.mean()),4),'possible_shadow_score':round(shadow,4),'silhouette_score':round(silhouette,4),'bbox_norm':bbox_norm}
