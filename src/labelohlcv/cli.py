from __future__ import annotations

import argparse
import sys
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
        default="vn30f1m",
        help="Labeling module name inside labelohlcv.modules (default: vn30f1m)",
    )
    parser.add_argument("--output", type=Path, help="Optional path to save labeled output as CSV")
    return parser


def _build_probe_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mod", default="vn30f1m")
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = argv if argv is not None else sys.argv[1:]

    # Handle --help/-h before loading module so it never crashes
    if not args_list or "-h" in args_list or "--help" in args_list:
        known_args, _ = _build_probe_parser().parse_known_args(args_list)
        module_class = load_module_class(known_args.mod)
        parser = build_parser()
        module_class.configure_parser(parser)
        parser.parse_args(args_list)
        return 0

    known_args, _ = _build_probe_parser().parse_known_args(args_list)
    module_class = load_module_class(known_args.mod)
    parser = build_parser()
    module_class.configure_parser(parser)
    args = parser.parse_args(args_list)

    module = module_class()
    return module.run(args)
