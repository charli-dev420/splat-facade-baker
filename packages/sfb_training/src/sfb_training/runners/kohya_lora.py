from __future__ import annotations
from pathlib import Path
from typing import Any

def build_kohya_lora_command(config: dict[str, Any], run_dir: str | Path) -> list[str]:
    runner=config.get('runner',{}) if isinstance(config.get('runner',{}),dict) else {}; ds=config.get('dataset',{}) if isinstance(config.get('dataset',{}),dict) else {}; model=config.get('model',{}) if isinstance(config.get('model',{}),dict) else {}; train=config.get('training',{}) if isinstance(config.get('training',{}),dict) else {}
    dataset=ds.get('path') or config.get('dataset'); base=model.get('base_model') or config.get('base_model')
    if not dataset or not base: raise ValueError('Kohya LoRA config requires dataset.path and model.base_model')
    cmd=[runner.get('python_bin','python'), str(runner.get('script_path','train_network.py')), '--pretrained_model_name_or_path', str(base), '--train_data_dir', str(dataset), '--output_dir', str(Path(run_dir)/'checkpoints'), '--resolution', str(train.get('resolution',1024)), '--network_dim', str(train.get('rank',16)), '--learning_rate', str(train.get('learning_rate',1e-4)), '--max_train_steps', str(train.get('max_train_steps',1000))]
    if isinstance(runner.get('extra_args',[]), list): cmd += [str(x) for x in runner.get('extra_args',[])]
    return cmd
