from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
from tqdm import tqdm

from .base import LabelPipeline, load_dataframe

RULE_URL = 'https://raw.githubusercontent.com/tempusoneps/trading-rules/refs/heads/main/VN30F1M/close_position_rules.json'
CACHE_DIR = Path(__file__).parent
CACHE_FILE = CACHE_DIR / "close_position_rules.json"

DEFAULT_FALLBACK_RULES = {
    "rules": [{
        "id": "no-overnight-sl033-tp132-tsl035-fc1425",
        "risk_management": {
            "stop_loss": {"value": 0.33},
        }
    }]
}

_L, _H = 0.3, 0.7


def _load_rules(url: str = RULE_URL) -> dict:
    try:
        with urlopen(url, timeout=5) as response:
            data = response.read().decode('utf-8')
            rules = json.loads(data)
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                CACHE_FILE.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception:
                pass
            return rules
    except Exception:
        if CACHE_FILE.exists():
            try:
                return json.loads(CACHE_FILE.read_text(encoding='utf-8'))
            except Exception:
                pass
        return DEFAULT_FALLBACK_RULES


def _day_shape(group: pd.DataFrame, narrow_threshold: float) -> str:
    day_high = group['High'].max()
    day_low = group['Low'].min()
    price_range = day_high - day_low

    if price_range < narrow_threshold:
        return 'narrow_range'

    open_price = group['Open'].iloc[0]
    close_price = group['Close'].iloc[-1]
    open_pos = (open_price - day_low) / price_range
    close_pos = (close_price - day_low) / price_range
    high_first = group['High'].idxmax() < group['Low'].idxmin()

    def zone(p: float) -> str:
        return 'low' if p <= _L else ('high' if p >= _H else 'mid')

    o, c = zone(open_pos), zone(close_pos)

    if high_first:
        if c == 'high':
            return 'bear_trap' if o in ('mid', 'high') else 'bull_reversal'
        if c == 'low':
            return 'strong_bear' if o == 'high' else 'bear_grind'
        return 'two_sided_bear' if o == 'high' else 'two_sided_neutral'
    else:
        if c == 'low':
            return 'bull_trap' if o in ('mid', 'low') else 'bear_reversal'
        if c == 'high':
            return 'strong_bull' if o == 'low' else 'bull_grind'
        return 'two_sided_bull' if o == 'low' else 'two_sided_neutral'


def do_label_data(df: pd.DataFrame) -> pd.DataFrame | None:
    rules = _load_rules()
    rule_id = "no-overnight-sl033-tp132-tsl035-fc1425"
    rule = next((r for r in rules.get("rules", []) if r["id"] == rule_id), None)
    if not rule:
        return None
    label_data = df.copy()
    entry_filter_list = []
    direction_filter_list = []
    new_entry_allowed = []
    remain_session_volatility = []
    remain_session_net_move = []
    long_mae_list = []
    short_mae_list = []
    long_mfe_list = []
    short_mfe_list = []
    rr_long_list = []
    rr_short_list = []
    eod_return_long_list = []
    eod_return_short_list = []
    for i, row in tqdm(label_data.iterrows(), total=len(label_data), desc='Labeling', unit='candle', colour='green', bar_format='{l_bar}{bar:40}{r_bar}'):
        current_date = row.name.strftime('%Y-%m-%d ').format()
        current_time = row.name
        data_to_end_day = label_data[(label_data.index > current_time) & (label_data.index < current_date + ' 14:30:00')]
        if not len(data_to_end_day):
            entry_filter_list.append("")
            direction_filter_list.append("")
            new_entry_allowed.append("")
            remain_session_volatility.append(None)
            remain_session_net_move.append(None)
            long_mae_list.append(None)
            short_mae_list.append(None)
            long_mfe_list.append(None)
            short_mfe_list.append(None)
            rr_long_list.append(None)
            rr_short_list.append(None)
            eod_return_long_list.append(None)
            eod_return_short_list.append(None)
            continue
        entry_price = row['Close']
        long_sl = entry_price - entry_price * rule['risk_management']['stop_loss']['value'] / 100
        short_sl = entry_price + entry_price * rule['risk_management']['stop_loss']['value'] / 100
        longable = shortable = True
        high_max = data_to_end_day['High'].max()
        low_min = data_to_end_day['Low'].min()
        if high_max >= short_sl:
            shortable = False
        if low_min <= long_sl:
            longable = False

        # Compute entry_filter and direction_filter
        if longable and not shortable:
            ef = "Yes"
            df_val = "Long"
        elif shortable and not longable:
            ef = "Yes"
            df_val = "Short"
        else:
            ef = "No"
            df_val = "None"

        entry_filter_list.append(ef)
        direction_filter_list.append(df_val)

        # allow_entry as combination of entry_filter and direction_filter
        if ef == "Yes":
            if df_val == "Long":
                new_entry_allowed.append('Yes - Buy')
            elif df_val == "Short":
                new_entry_allowed.append('Yes - Sell')
        else:
            if longable and shortable:
                new_entry_allowed.append('No - Sideway')
            else:
                new_entry_allowed.append("No - None")

        remain_session_volatility.append(high_max - low_min)
        remain_session_net_move.append(high_max + low_min - 2 * entry_price)
        long_mae = (entry_price - low_min) / entry_price * 100
        short_mae = (high_max - entry_price) / entry_price * 100
        long_mae_list.append(long_mae)
        short_mae_list.append(short_mae)
        long_mfe = (high_max - entry_price) / entry_price * 100
        short_mfe = (entry_price - low_min) / entry_price * 100
        long_mfe_list.append(long_mfe)
        short_mfe_list.append(short_mfe)
        rr_long_list.append(long_mfe / long_mae if long_mae else None)
        rr_short_list.append(short_mfe / short_mae if short_mae else None)
        session_close = data_to_end_day['Close'].iloc[-1]
        eod_return_long_list.append((session_close - entry_price) / entry_price * 100)
        eod_return_short_list.append((entry_price - session_close) / entry_price * 100)
    label_data['entry_filter'] = entry_filter_list
    label_data['direction_filter'] = direction_filter_list
    label_data['allow_entry'] = new_entry_allowed
    label_data['remain_session_volatility'] = remain_session_volatility
    label_data['remain_session_net_move'] = remain_session_net_move
    label_data['long_mae'] = long_mae_list
    label_data['short_mae'] = short_mae_list
    label_data['long_mfe'] = long_mfe_list
    label_data['short_mfe'] = short_mfe_list
    label_data['rr_long'] = rr_long_list
    label_data['rr_short'] = rr_short_list
    label_data['eod_return_long'] = eod_return_long_list
    label_data['eod_return_short'] = eod_return_short_list

    date_keys = label_data.index.date
    day_high = label_data.groupby(date_keys)['High'].transform('max')
    day_low = label_data.groupby(date_keys)['Low'].transform('min')
    label_data['price_range'] = day_high - day_low
    intraday_pos = pd.Series('norm', index=label_data.index, dtype=str)
    intraday_pos[label_data['Low'] == day_low] = 'valley'
    intraday_pos[label_data['High'] == day_high] = 'peak'
    label_data['intraday_position'] = intraday_pos

    day_range_by_date = label_data.groupby(date_keys).apply(
        lambda g: g['High'].max() - g['Low'].min()
    )
    narrow_threshold = day_range_by_date.median() * 0.3
    shape_by_date = label_data.groupby(date_keys).apply(
        lambda g: _day_shape(g, narrow_threshold)
    )
    label_data['price_shape'] = [shape_by_date[d] for d in date_keys]

    roll_high_10 = label_data['High'].rolling(window=21, center=True, min_periods=1).max()
    roll_low_10 = label_data['Low'].rolling(window=21, center=True, min_periods=1).min()
    label_data['is_peak_10'] = label_data['High'] == roll_high_10
    label_data['is_valley_10'] = label_data['Low'] == roll_low_10

    return label_data


class Module(LabelPipeline):
    def load(self, args: Namespace) -> pd.DataFrame:
        return load_dataframe(args.input, index_col='Date', parse_dates=True)

    def label(self, df: pd.DataFrame, args: Namespace) -> pd.DataFrame:
        result = do_label_data(df)
        if result is None:
            raise ValueError("Rule not found — cannot label data")
        return (
            result
            .drop(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
            .rename_axis('Date')
            .reset_index()
        )
