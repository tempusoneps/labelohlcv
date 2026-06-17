from __future__ import annotations

import csv
import json
from abc import ABC, abstractmethod
from argparse import Namespace
from pathlib import Path
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Callable, Iterable, Sequence

Label = str


@dataclass(frozen=True, slots=True)
class Candle:
    """Simple OHLCV candle."""

    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True, slots=True)
class LabelResult:
    """A candle with its assigned label."""

    candle: Candle
    label: Label


DEFAULT_CSV_HEADERS = ("Open", "High", "Low", "Close", "Volume")


def validate_input_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Input path is not a file: {path}")


def load_candles(
    path: Path,
    *,
    required_headers: Sequence[str] = DEFAULT_CSV_HEADERS,
) -> list[Candle]:
    validate_input_file(path)

    candles: list[Candle] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(required_headers) - set(reader.fieldnames or [])
        if missing:
            missing_fields = ", ".join(sorted(missing))
            raise ValueError(f"CSV header is missing required fields: {missing_fields}")

        for row in reader:
            if not row:
                continue
            if not any((value or "").strip() for value in row.values()):
                continue

            candles.append(
                Candle(
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row.get("Volume") or 0.0),
                )
            )
    return candles


def label_data(candles: Iterable[Candle], labeler: Callable[..., Any], **kwargs: Any) -> Any:
    return labeler(candles, **kwargs)


def print_output(data: Any) -> None:
    print(json.dumps(_to_jsonable(data), indent=2, ensure_ascii=False))


def save_output(data: Any, path: Path) -> None:
    path.write_text(json.dumps(_to_jsonable(data), indent=2, ensure_ascii=False), encoding="utf-8")


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


class LabelModule(ABC):
    """Base class for labeling modules."""

    @classmethod
    def configure_parser(cls, parser):
        return parser

    def run(self, args: Namespace) -> int:
        validate_input_file(args.input)
        candles = load_candles(args.input)
        results = self.label(candles, args)
        print_output(results)

        output = getattr(args, "output", None)
        if output:
            save_output(results, output)
        return 0

    @abstractmethod
    def label(self, candles: Iterable[Candle], args: Namespace) -> Any:
        raise NotImplementedError
