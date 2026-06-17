from __future__ import annotations

import argparse
from pathlib import Path

from .modules import load_module_class


def build_parser(*, add_help: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="labelohlcv",
        description="Label OHLCV candles from CSV.",
        add_help=add_help,
    )
    parser.add_argument("input", type=Path, help="Path to a CSV file with OHLCV candles")
    parser.add_argument(
        "--mod",
        default="default",
        help="Labeling module name inside labelohlcv.modules, for example vn30f1m",
    )
    parser.add_argument("--output", type=Path, help="Optional path to save labeled output as JSON")
    return parser


def _build_probe_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mod", default="default")
    return parser


def main(argv: list[str] | None = None) -> int:
    known_args, _ = _build_probe_parser().parse_known_args(argv)

    module_class = load_module_class(known_args.mod)
    parser = build_parser()
    module_class.configure_parser(parser)
    args = parser.parse_args(argv)

    module = module_class()
    return module.run(args)
