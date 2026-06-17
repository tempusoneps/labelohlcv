from __future__ import annotations

import argparse
from argparse import Namespace

import pandas as pd

from .base import OHLCV_COLUMNS, LabelPipeline, load_dataframe

DATE_COLUMN = "Date"
DEFAULT_HORIZON = 6
DEFAULT_THRESHOLD_PCT = 0.002


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be greater than or equal to 0")
    return parsed


def _arg(args: Namespace, name: str, default):
    return getattr(args, name, default)


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if DATE_COLUMN in df.columns:
        data = df.copy()
    elif isinstance(df.index, pd.DatetimeIndex):
        data = df.reset_index()
        data = data.rename(columns={data.columns[0]: DATE_COLUMN})
    else:
        raise ValueError("CSV must contain a Date column or use a DatetimeIndex")

    data[DATE_COLUMN] = pd.to_datetime(data[DATE_COLUMN], errors="raise")
    return data.sort_values(DATE_COLUMN, kind="mergesort").reset_index(drop=True)


def _session_key(data: pd.DataFrame, *, allow_cross_session: bool) -> pd.Series:
    if allow_cross_session:
        return pd.Series(0, index=data.index)
    return data[DATE_COLUMN].dt.date


def _future_shift(
    data: pd.DataFrame,
    session: pd.Series,
    column: str,
    steps: int,
) -> pd.Series:
    return data.groupby(session, sort=False)[column].shift(-steps)


def _future_extreme(
    data: pd.DataFrame,
    session: pd.Series,
    column: str,
    horizon: int,
    direction: str,
) -> pd.Series:
    shifted = [
        _future_shift(data, session, column, step)
        for step in range(1, horizon + 1)
    ]
    window = pd.concat(shifted, axis=1)
    if direction == "max":
        return window.max(axis=1)
    if direction == "min":
        return window.min(axis=1)
    raise ValueError(f"Unsupported future extreme direction: {direction}")


def _first_hit_step(
    data: pd.DataFrame,
    session: pd.Series,
    column: str,
    target: pd.Series,
    horizon: int,
    op: str,
) -> pd.Series:
    hit_step = pd.Series(float("nan"), index=data.index)
    for step in range(1, horizon + 1):
        future_value = _future_shift(data, session, column, step)
        if op == "ge":
            hit = future_value >= target
        elif op == "le":
            hit = future_value <= target
        else:
            raise ValueError(f"Unsupported hit comparison: {op}")
        hit_step = hit_step.mask(hit & hit_step.isna(), float(step))
    return hit_step


def _trade_outcome(
    take_profit_step: pd.Series,
    stop_loss_step: pd.Series,
    complete: pd.Series,
) -> pd.Series:
    outcome = pd.Series("none", index=take_profit_step.index, dtype="object")
    tp_hit = take_profit_step.notna()
    sl_hit = stop_loss_step.notna()
    both_hit = tp_hit & sl_hit

    outcome.loc[tp_hit & ~sl_hit] = "tp"
    outcome.loc[sl_hit & ~tp_hit] = "sl"
    outcome.loc[both_hit & (take_profit_step < stop_loss_step)] = "tp"
    outcome.loc[both_hit & (stop_loss_step < take_profit_step)] = "sl"
    outcome.loc[both_hit & (take_profit_step == stop_loss_step)] = "ambiguous"
    outcome.loc[~complete] = "unknown"
    return outcome


class Module(LabelPipeline):
    @classmethod
    def configure_parser(cls, parser):
        parser.add_argument(
            "--horizon",
            type=positive_int,
            default=DEFAULT_HORIZON,
            help="Number of future candles used for target labels.",
        )
        parser.add_argument(
            "--threshold-pct",
            type=non_negative_float,
            default=DEFAULT_THRESHOLD_PCT,
            help="Future close return threshold for Bullish/Bearish labels.",
        )
        parser.add_argument(
            "--take-profit-pct",
            type=non_negative_float,
            help="Barrier take-profit percent; defaults to --threshold-pct.",
        )
        parser.add_argument(
            "--stop-loss-pct",
            type=non_negative_float,
            help="Barrier stop-loss percent; defaults to --threshold-pct.",
        )
        parser.add_argument(
            "--prefix",
            default="codex",
            help="Prefix for generated columns.",
        )
        parser.add_argument(
            "--allow-cross-session",
            action="store_true",
            help="Allow future labels to cross trading dates.",
        )
        return parser

    def load(self, args: Namespace) -> pd.DataFrame:
        return load_dataframe(
            args.input,
            required_headers=(DATE_COLUMN, *OHLCV_COLUMNS),
            parse_dates=[DATE_COLUMN],
        )

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        super().validate(df)
        if DATE_COLUMN not in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("CSV must contain a Date column or use a DatetimeIndex")
        if (df["Close"] == 0).any():
            raise ValueError("Column 'Close' must not contain zero values")
        return df

    def label(self, df: pd.DataFrame, args: Namespace) -> pd.DataFrame:
        horizon = _arg(args, "horizon", DEFAULT_HORIZON)
        threshold_pct = _arg(args, "threshold_pct", DEFAULT_THRESHOLD_PCT)
        take_profit_pct = _arg(args, "take_profit_pct", None)
        stop_loss_pct = _arg(args, "stop_loss_pct", None)
        prefix = _arg(args, "prefix", "codex")
        allow_cross_session = bool(_arg(args, "allow_cross_session", False))

        if horizon <= 0:
            raise ValueError("horizon must be greater than 0")
        if threshold_pct < 0:
            raise ValueError("threshold_pct must be greater than or equal to 0")
        if not prefix:
            raise ValueError("prefix must not be empty")

        take_profit_pct = threshold_pct if take_profit_pct is None else take_profit_pct
        stop_loss_pct = threshold_pct if stop_loss_pct is None else stop_loss_pct
        if take_profit_pct < 0 or stop_loss_pct < 0:
            raise ValueError("take_profit_pct and stop_loss_pct must be non-negative")

        labeled = _prepare_dataframe(df)
        session = _session_key(labeled, allow_cross_session=allow_cross_session)
        grouped = labeled.groupby(session, sort=False)

        bars_left = grouped["Close"].transform("size") - grouped.cumcount() - 1
        future_complete = bars_left >= horizon

        label_columns = self._add_future_labels(
            labeled,
            session,
            horizon,
            threshold_pct,
            take_profit_pct,
            stop_loss_pct,
            future_complete,
            prefix,
        )

        labeled[f"{prefix}_future_complete"] = future_complete
        return labeled[[DATE_COLUMN, *label_columns, f"{prefix}_future_complete"]]

    def _add_future_labels(
        self,
        labeled: pd.DataFrame,
        session: pd.Series,
        horizon: int,
        threshold_pct: float,
        take_profit_pct: float,
        stop_loss_pct: float,
        future_complete: pd.Series,
        prefix: str,
    ) -> list[str]:
        close = labeled["Close"]
        future_close = _future_shift(labeled, session, "Close", horizon).where(
            future_complete
        )
        future_date = _future_shift(labeled, session, DATE_COLUMN, horizon).where(
            future_complete
        )
        future_high = _future_extreme(labeled, session, "High", horizon, "max").where(
            future_complete
        )
        future_low = _future_extreme(labeled, session, "Low", horizon, "min").where(
            future_complete
        )
        future_return = future_close / close - 1
        future_max_return = future_high / close - 1
        future_min_return = future_low / close - 1

        labeled[f"{prefix}_future_date"] = future_date
        labeled[f"{prefix}_future_close"] = future_close
        labeled[f"{prefix}_future_return"] = future_return
        labeled[f"{prefix}_future_high"] = future_high
        labeled[f"{prefix}_future_low"] = future_low
        labeled[f"{prefix}_future_max_return"] = future_max_return
        labeled[f"{prefix}_future_min_return"] = future_min_return
        labeled[f"{prefix}_future_range_return"] = (
            future_max_return - future_min_return
        )

        label = pd.Series("Sideway", index=labeled.index, dtype="object")
        label.loc[future_return >= threshold_pct] = "Bullish"
        label.loc[future_return <= -threshold_pct] = "Bearish"
        label.loc[~future_complete] = "Unknown"

        target = pd.Series(0, index=labeled.index, dtype="Int64")
        target.loc[label == "Bullish"] = 1
        target.loc[label == "Bearish"] = -1
        target.loc[label == "Unknown"] = pd.NA

        entry_signal = pd.Series("Flat", index=labeled.index, dtype="object")
        entry_signal.loc[label == "Bullish"] = "Long"
        entry_signal.loc[label == "Bearish"] = "Short"
        entry_signal.loc[label == "Unknown"] = "Unknown"

        labeled[f"{prefix}_label"] = label
        labeled[f"{prefix}_target"] = target
        labeled[f"{prefix}_entry_signal"] = entry_signal
        labeled["allow_entry"] = label

        long_tp = close * (1 + take_profit_pct)
        long_sl = close * (1 - stop_loss_pct)
        short_tp = close * (1 - take_profit_pct)
        short_sl = close * (1 + stop_loss_pct)

        long_tp_step = _first_hit_step(
            labeled, session, "High", long_tp, horizon, "ge"
        ).where(future_complete)
        long_sl_step = _first_hit_step(
            labeled, session, "Low", long_sl, horizon, "le"
        ).where(future_complete)
        short_tp_step = _first_hit_step(
            labeled, session, "Low", short_tp, horizon, "le"
        ).where(future_complete)
        short_sl_step = _first_hit_step(
            labeled, session, "High", short_sl, horizon, "ge"
        ).where(future_complete)

        long_outcome = _trade_outcome(long_tp_step, long_sl_step, future_complete)
        short_outcome = _trade_outcome(short_tp_step, short_sl_step, future_complete)

        barrier_label = pd.Series("NoTrade", index=labeled.index, dtype="object")
        long_wins = long_outcome == "tp"
        short_wins = short_outcome == "tp"
        ambiguous = (long_outcome == "ambiguous") | (short_outcome == "ambiguous")
        barrier_label.loc[long_wins & ~short_wins] = "Long"
        barrier_label.loc[short_wins & ~long_wins] = "Short"
        barrier_label.loc[long_wins & short_wins] = "Both"
        barrier_label.loc[ambiguous] = "Ambiguous"
        barrier_label.loc[~future_complete] = "Unknown"

        labeled[f"{prefix}_long_tp_step"] = long_tp_step
        labeled[f"{prefix}_long_sl_step"] = long_sl_step
        labeled[f"{prefix}_long_outcome"] = long_outcome
        labeled[f"{prefix}_short_tp_step"] = short_tp_step
        labeled[f"{prefix}_short_sl_step"] = short_sl_step
        labeled[f"{prefix}_short_outcome"] = short_outcome
        labeled[f"{prefix}_barrier_label"] = barrier_label
        return [
            f"{prefix}_future_date",
            f"{prefix}_future_close",
            f"{prefix}_future_return",
            f"{prefix}_future_high",
            f"{prefix}_future_low",
            f"{prefix}_future_max_return",
            f"{prefix}_future_min_return",
            f"{prefix}_future_range_return",
            f"{prefix}_label",
            f"{prefix}_target",
            f"{prefix}_entry_signal",
            "allow_entry",
            f"{prefix}_long_tp_step",
            f"{prefix}_long_sl_step",
            f"{prefix}_long_outcome",
            f"{prefix}_short_tp_step",
            f"{prefix}_short_sl_step",
            f"{prefix}_short_outcome",
            f"{prefix}_barrier_label",
        ]
