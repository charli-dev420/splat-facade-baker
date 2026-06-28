from __future__ import annotations
from pathlib import Path
from typing import Any

def build_diffusers_lora_command(config: dict[str, Any], run_dir: str | Path) -> list[str]:
    runner=config.get('runner',{}) if isinstance(config.get('runner',{}),dict) else {}; script=runner.get('script_path','train_text_to_image_lora.py'); acc=runner.get('accelerate_bin','accelerate')
    ds=config.get('dataset',{}) if isinstance(config.get('dataset',{}),dict) else {}; model=config.get('model',{}) if isinstance(config.get('model',{}),dict) else {}; train=config.get('training',{}) if isinstance(config.get('training',{}),dict) else {}
    dataset=ds.get('path') or config.get('dataset'); base=model.get('base_model') or config.get('base_model')
    if not dataset: raise ValueError('Diffusers LoRA config requires dataset.path')
    if not base: raise ValueError('Diffusers LoRA config requires model.base_model')
    cmd=[acc,'launch',str(script),'--pretrained_model_name_or_path',str(base),'--train_data_dir',str(dataset),'--output_dir',str(Path(run_dir)/'checkpoints'),'--resolution',str(train.get('resolution',1024)),'--train_batch_size',str(train.get('train_batch_size',1)),'--gradient_accumulation_steps',str(train.get('gradient_accumulation_steps',4)),'--learning_rate',str(train.get('learning_rate',1e-4)),'--max_train_steps',str(train.get('max_train_steps',1000)),'--checkpointing_steps',str(train.get('checkpointing_steps',500)),'--rank',str(train.get('rank',16))]
    if train.get('mixed_precision'): cmd += ['--mixed_precision', str(train.get('mixed_precision'))]
    if train.get('gradient_checkpointing', False): cmd += ['--gradient_checkpointing']
    seed=train.get('seed') or (config.get('run',{}) if isinstance(config.get('run',{}),dict) else {}).get('seed')
    if seed is not None: cmd += ['--seed', str(seed)]
    if runner.get('include_output_name_flag', False) and model.get('output_weight_name'): cmd += ['--output_name', str(model.get('output_weight_name'))]
    if isinstance(runner.get('extra_args',[]), list): cmd += [str(x) for x in runner.get('extra_args',[])]
    return cmd
