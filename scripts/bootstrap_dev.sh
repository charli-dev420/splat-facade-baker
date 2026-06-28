#!/usr/bin/env bash
set -euo pipefail
python -m pip install -U pip
pip install --no-build-isolation -e 'packages/sfb_core[dev]'
pip install --no-build-isolation -e packages/sfb_dataset
pip install --no-build-isolation -e 'packages/sfb_orchestrator[dev]'
pip install --no-build-isolation -e 'packages/sfb_training[dev]'
pip install --no-build-isolation -e 'packages/sfb_scene[dev]'
