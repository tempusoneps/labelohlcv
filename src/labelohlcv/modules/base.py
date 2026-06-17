from __future__ import annotations

from abc import ABC, abstractmethod
from argparse import Namespace
from pathlib import Path
from typing import Sequence

import pandas as pd

OHLCV_COLUMNS = ("Open", "High", "Low", "Close", "Volume")
DEFAULT_CSV_HEADERS = OHLCV_COLUMNS


def validate_input_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Input path is not a file: {path}")


def load_dataframe(
    path: Path,
    *,
    required_headers: Sequence[str] = DEFAULT_CSV_HEADERS,
    **kwargs,
) -> pd.DataFrame:
    validate_input_file(path)
    df = pd.read_csv(path, **kwargs)
    all_cols = set(df.columns) | ({df.index.name} if df.index.name else set())
    missing = set(required_headers) - all_cols
    if missing:
        raise ValueError(f"CSV header is missing required fields: {', '.join(sorted(missing))}")
    return df


def save_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)


def print_tail(df: pd.DataFrame, n: int = 20) -> None:
    print(df.tail(n).to_string())


class LabelPipeline(ABC):
    """Base class for OHLCV labeling pipelines.

    Subclasses must implement `label()`. The other steps (`load`, `validate`,
    `output`) have sensible defaults but can be overridden per-module.
    """

    @classmethod
    def configure_parser(cls, parser):
        return parser

    # --- Pipeline entry point ---

    def run(self, args: Namespace) -> int:
        df = self.load(args)
        df = self.validate(df)
        df = self.label(df, args)
        self.output(df, args)
        return 0

    # --- Steps (override as needed) ---

    def load(self, args: Namespace) -> pd.DataFrame:
        return load_dataframe(args.input)

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in OHLCV_COLUMNS:
            if not pd.api.types.is_numeric_dtype(df[col]):
                raise ValueError(f"Column '{col}' must be numeric, got {df[col].dtype}")
        nan_cols = [col for col in OHLCV_COLUMNS if df[col].isna().any()]
        if nan_cols:
            raise ValueError(f"NaN values found in columns: {', '.join(nan_cols)}")
        if (df["Open"] == 0).any():
            raise ValueError("Column 'Open' must not contain zero values")
        return df

    @abstractmethod
    def label(self, df: pd.DataFrame, args: Namespace) -> pd.DataFrame:
        raise NotImplementedError

    def output(self, df: pd.DataFrame, args: Namespace) -> None:
        path = getattr(args, "output", None)
        if path:
            save_csv(df, path)
        else:
            print_tail(df)
