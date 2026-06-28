from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..utils import read_json


@dataclass(frozen=True)
class WorkflowTemplateMetadata:
    workflow_id: str
    engine: str
    version: str
    template_path: Path | None
    description: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "WorkflowTemplateMetadata":
        p = Path(path)
        data = read_json(p)
        template_file = data.get("template_file") or data.get("template_path")
        template_path = None
        if template_file:
            candidate = Path(template_file)
            template_path = candidate if candidate.is_absolute() else (p.parent / candidate)
        return cls(
            workflow_id=data["workflow_id"],
            engine=data.get("engine", "comfyui"),
            version=data.get("version", "0.1.0"),
            template_path=template_path,
            description=data.get("description", ""),
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            raw=data,
        )


def load_workflow_template(path: str | Path) -> dict:
    return read_json(path)


def _set_path(data: dict, dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    cursor: Any = data
    for part in parts[:-1]:
        if isinstance(cursor, list):
            cursor = cursor[int(part)]
        else:
            cursor = cursor[part]
    last = parts[-1]
    if isinstance(cursor, list):
        cursor[int(last)] = value
    else:
        cursor[last] = value


def inject_node_input(workflow: dict, node_id: str, field: str, value: Any) -> dict:
    workflow = copy.deepcopy(workflow)
    workflow[str(node_id)]["inputs"][field] = value
    return workflow


def inject_template_inputs(workflow: dict, metadata: WorkflowTemplateMetadata, params: dict[str, Any]) -> dict:
    """Inject logical SFB parameters into a ComfyUI workflow template.

    Supported mapping formats in metadata.inputs:

    1. {"input_image": {"node_id": "12", "field": "image"}}
    2. {"seed": {"path": "27.inputs.seed"}}

    Missing params are ignored so a template can define optional fields.
    """

    result = copy.deepcopy(workflow)
    for logical_key, mapping in metadata.inputs.items():
        if logical_key not in params:
            continue
        value = params[logical_key]
        if "path" in mapping:
            _set_path(result, mapping["path"], value)
            continue
        node_id = str(mapping["node_id"])
        field = mapping["field"]
        result[node_id]["inputs"][field] = value
    return result
