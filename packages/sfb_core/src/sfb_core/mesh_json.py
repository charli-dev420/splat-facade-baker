from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import trimesh


def export_sfbmesh_json(mesh: trimesh.Trimesh, path: str | Path) -> None:
    """Write a simple deterministic mesh JSON for the Unity importer skeleton.

    This is not meant to replace GLB for all tools. It is a transparent fallback
    format that Unity can parse without a third-party glTF importer.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    uv = getattr(mesh.visual, "uv", None)
    vertices = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=int)
    normals = np.asarray(mesh.vertex_normals, dtype=float) if len(vertices) else np.zeros((0, 3), dtype=float)
    data = {
        "schema": "sfb.mesh.v1",
        "vertex_count": int(len(vertices)),
        "triangle_count": int(len(faces)),
        "vertices": vertices.round(6).tolist(),
        "triangles": faces.tolist(),
        "normals": normals.round(6).tolist(),
        "uv": np.asarray(uv, dtype=float).round(6).tolist() if uv is not None else [],
        "bounds": {
            "min": np.asarray(mesh.bounds[0], dtype=float).round(6).tolist() if len(vertices) else [0, 0, 0],
            "max": np.asarray(mesh.bounds[1], dtype=float).round(6).tolist() if len(vertices) else [0, 0, 0],
        },
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
