from __future__ import annotations

import json
from argparse import Namespace
from urllib.request import urlopen

import pandas as pd
from tqdm import tqdm

from .base import LabelPipeline, load_dataframe

RULE_URL = 'https://raw.githubusercontent.com/tempusoneps/trading-rules/refs/heads/main/VN30F1M/close_position_rules.json'

_L, _H = 0.3, 0.7


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
    with urlopen(RULE_URL) as response:
        rules = json.loads(response.read().decode('utf-8'))
    rule_id = "no-overnight-sl033-tp132-tsl035-fc1425"
    rule = next((r for r in rules["rules"] if r["id"] == rule_id), None)
    if not rule:
        return None
    label_data = df.copy()
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
        if longable and shortable:
            new_entry_allowed.append('No - Sideway')
        elif longable:
            new_entry_allowed.append('Yes - Buy')
        elif shortable:
            new_entry_allowed.append('Yes - Sell')
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

    return label_data


class Module(LabelPipeline):
    def load(self, args: Namespace) -> pd.DataFrame:
        return load_dataframe(args.input, index_col='Date', parse_dates=True)

    def label(self, df: pd.DataFrame, args: Namespace) -> pd.DataFrame:
        result = do_label_data(df)
        if result is None:
            raise ValueError("Rule not found — cannot label data")
        return result
