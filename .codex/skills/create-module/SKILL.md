---
name: create-module
description: Project-local workflow for creating labelohlcv labeling modules. Use when Codex needs to add, scaffold, or modify a module under src/labelohlcv/modules/module_name.py, wire module-specific CLI arguments through Module.configure_parser(), implement OHLCV labeling with LabelPipeline, or add/update tests for new --mod behavior in this labelohlcv project.
---

# Create Module

## Workflow

1. Inspect the current module contract before editing: `src/labelohlcv/modules/base.py`, `src/labelohlcv/modules/__init__.py`, the closest existing module, `README.md`, and relevant tests.
2. Normalize the requested module name to a Python module filename. Prefer lowercase `snake_case`; the CLI `--mod` value must match the filename without `.py`.
3. Create or update `src/labelohlcv/modules/<name>.py` with a `Module` class that inherits `LabelPipeline`.
4. Implement only the pipeline steps the module needs:
   - Use `configure_parser(cls, parser)` for module-specific CLI flags and return `parser`.
   - Override `load()` only for custom CSV parsing such as `index_col="Date"` or `parse_dates=True`; prefer `load_dataframe()`.
   - Override `validate()` only for module-specific constraints; preserve base OHLCV validation unless there is a deliberate reason.
   - Implement `label(self, df, args)` as the main labeling logic.
   - Override `output()` or `run()` only for truly custom flow.
5. Add focused tests for the new behavior, then run `rtk uv run pytest`.

## Module Pattern

Use this shape unless the requested module needs a custom pipeline:

```python
from __future__ import annotations

from argparse import Namespace

import pandas as pd

from .base import LabelPipeline


class Module(LabelPipeline):
    @classmethod
    def configure_parser(cls, parser):
        parser.add_argument("--label-column", default="label")
        return parser

    def label(self, df: pd.DataFrame, args: Namespace) -> pd.DataFrame:
        labeled = df.copy()
        label_column = getattr(args, "label_column", "label")
        labeled[label_column] = ""
        return labeled
```

Do not update `src/labelohlcv/modules/__init__.py` for ordinary modules; `load_module_class()` imports by module name dynamically and requires a class named `Module`.

## Labeling Guidance

- Return a `pd.DataFrame`; raise `ValueError` for invalid module configuration or missing rules.
- Avoid mutating the caller's DataFrame unless the user explicitly asks for in-place behavior.
- Keep labels deterministic for tests. If the real workflow uses network files, URLs, clocks, or external services, isolate that access behind a small helper and mock it in tests.
- Preserve existing input expectations: OHLCV columns are `Open`, `High`, `Low`, `Close`, and `Volume`.
- If the module requires a datetime index, override `load()` with `load_dataframe(args.input, index_col="Date", parse_dates=True)` and add a test for that loader behavior.

## Tests

Place narrow tests in `tests/test_core.py` or a new test file when the module needs its own fixture set. Cover:

- `load_module_class("<name>")` returns the module's `Module` class.
- `label()` adds the expected output columns or labels for a tiny deterministic DataFrame.
- The input DataFrame is not mutated when the module copies before labeling.
- `configure_parser()` parses any new module-specific flags.
- External data access is mocked with `unittest.mock.patch`; tests must not depend on live network responses.

For CLI smoke checks, use:

```bash
rtk uv run labelohlcv path/to/sample.csv --mod <name> --help
```

Run the full suite before finishing:

```bash
rtk uv run pytest
```
