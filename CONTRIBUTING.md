# Contributing

This repository is intentionally modular. Please keep contributions small and tied to one module when possible.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e packages/sfb_core[dev]
pytest packages/sfb_core/tests
```

## Rules for public schema changes

Any change to a public JSON format must update:

1. the schema in `schemas/`;
2. the human doc in `docs/schemas/`;
3. at least one fixture/example;
4. tests if the format is used by code;
5. `CHANGELOG.md`.

## Branches

Use descriptive branches:

```text
feature/core-cleanup-alpha
feature/dataset-view-contract
fix/bake-empty-alpha
```

## PR checklist

- Tests pass.
- Examples still run.
- Public docs updated if relevant.
- New dependencies are justified and optional when possible.
