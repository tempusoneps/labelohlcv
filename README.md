# labelohlcv

`labelohlcv` is a small Python package for labeling OHLCV candles.

## Install from Git

With `uv`:

```bash
uv add git+https://github.com/tempusoneps/labelohlcv.git
```

Or with `uv pip`:

```bash
uv pip install git+https://github.com/tempusoneps/labelohlcv.git
```

## Local development

```bash
uv sync
uv run pytest
uv run labelohlcv path/to/ohlcv.csv --mod vn30f1m
```

## Input format

The CLI expects a CSV file with these headers:

```csv
Open,High,Low,Close,Volume
100,110,99,105,1200
105,106,98,99,900
```

## Modules

The `--mod` flag loads a class named `Module` from `labelohlcv.modules.<name>`.

For example:

```bash
uv run labelohlcv path/to/ohlcv.csv --mod vn30f1m
```

This imports `labelohlcv.modules.vn30f1m`, instantiates `Module`, and calls its `run(args)` method.

## Writing A Module

Create a file such as `src/labelohlcv/modules/vn30f1m.py` with a class like:

```python
from labelohlcv.modules.base import LabelModule

class Module(LabelModule):
    @classmethod
    def configure_parser(cls, parser):
        parser.add_argument("--up-threshold", type=float, default=0.01)
        parser.add_argument("--down-threshold", type=float, default=0.01)
        return parser

    def label(self, candles, args):
        ...
```

The module controls how candles are labeled, how outputs are produced, and can override `run()` if it needs a fully custom flow.
