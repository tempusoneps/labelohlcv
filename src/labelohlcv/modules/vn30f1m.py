from __future__ import annotations

import json
from argparse import Namespace
from urllib.request import urlopen

import pandas as pd

from .base import LabelPipeline, load_dataframe

RULE_URL = 'https://raw.githubusercontent.com/tempusoneps/trading-rules/refs/heads/main/VN30F1M/close_position_rules.json'


def do_label_data(df: pd.DataFrame) -> pd.DataFrame | None:
    with urlopen(RULE_URL) as response:
        rules = json.loads(response.read().decode('utf-8'))
    rule_id = "no-overnight-sl033-tp132-tsl035-fc1425"
    rule = next((r for r in rules["rules"] if r["id"] == rule_id), None)
    if not rule:
        return None
    label_data = df.copy()
    new_entry_allowed = []
    for i, row in label_data.iterrows():
        current_date = row.name.strftime('%Y-%m-%d ').format()
        current_time = row.name
        data_to_end_day = label_data[(label_data.index > current_time) & (label_data.index < current_date + ' 14:30:00')]
        if not len(data_to_end_day):
            new_entry_allowed.append("")
            continue
        entry_price = row['Close']
        long_sl = entry_price - entry_price * rule['risk_management']['stop_loss']['value'] / 100
        short_sl = entry_price + entry_price * rule['risk_management']['stop_loss']['value'] / 100
        longable = shortable = True
        if data_to_end_day['High'].max() >= short_sl:
            shortable = False
        if data_to_end_day['Low'].min() <= long_sl:
            longable = False
        if longable and shortable:
            new_entry_allowed.append('Sideway')
        elif longable:
            new_entry_allowed.append('Bullish')
        elif shortable:
            new_entry_allowed.append('Bearish')
        else:
            new_entry_allowed.append("None")
    label_data['allow_entry'] = new_entry_allowed
    return label_data


class Module(LabelPipeline):
    def load(self, args: Namespace) -> pd.DataFrame:
        return load_dataframe(args.input, index_col='Date', parse_dates=True)

    def label(self, df: pd.DataFrame, args: Namespace) -> pd.DataFrame:
        result = do_label_data(df)
        if result is None:
            raise ValueError("Rule not found — cannot label data")
        return result
