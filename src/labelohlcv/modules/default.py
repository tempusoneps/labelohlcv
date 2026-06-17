from __future__ import annotations

from argparse import Namespace
from typing import Iterable

from .base import LabelModule
from .base import Candle, LabelResult
from .vn30f1m import Module as Vn30F1mModule


class Module(LabelModule):
    def __init__(self) -> None:
        self._impl = Vn30F1mModule()

    @classmethod
    def configure_parser(cls, parser):
        return Vn30F1mModule.configure_parser(parser)

    def label(self, candles: Iterable[Candle], args: Namespace) -> list[LabelResult]:
        return self._impl.label(candles, args)
