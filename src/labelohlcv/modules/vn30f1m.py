from __future__ import annotations

from argparse import ArgumentParser, Namespace
from typing import Iterable

from .base import LabelModule
from .base import Candle, LabelResult


class Module(LabelModule):
    @classmethod
    def configure_parser(cls, parser: ArgumentParser):
        parser.add_argument("--up-threshold", type=float, default=0.01, help="Return threshold for buy labels")
        parser.add_argument("--down-threshold", type=float, default=0.01, help="Return threshold for sell labels")
        return parser

    def label(self, candles: Iterable[Candle], args: Namespace) -> list[LabelResult]:
        results: list[LabelResult] = []
        up_threshold = float(args.up_threshold)
        down_threshold = float(args.down_threshold)

        for candle in candles:
            if candle.open == 0:
                raise ValueError("candle.open must be non-zero")

            change = (candle.close - candle.open) / candle.open
            if change >= up_threshold:
                label = "buy"
            elif change <= -down_threshold:
                label = "sell"
            else:
                label = "hold"

            results.append(LabelResult(candle=candle, label=label))

        return results
