# sfb.mesh.v1

Transparent mesh JSON fallback used by the Unity importer.

The format stores:

```text
vertices: [[x, y, z], ...]
triangles: [[a, b, c], ...]
normals: [[x, y, z], ...]
uv: [[u, v], ...]
```

It is intentionally simple and deterministic. GLB is still exported for other tools, but Unity can import this format without a third-party glTF importer.
