import io
import json
from argparse import ArgumentParser
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from labelohlcv.modules.base import LabelPipeline, load_dataframe, save_csv
from labelohlcv.modules import load_module_class

FAKE_RULES = {
    "rules": [{
        "id": "no-overnight-sl033-tp132-tsl035-fc1425",
        "risk_management": {
            "stop_loss": {"value": 0.33},
        }
    }]
}


def _fake_urlopen(url, *args, **kwargs):
    data = json.dumps(FAKE_RULES).encode("utf-8")
    return io.BytesIO(data)


# --- load_dataframe ---

def test_load_dataframe_reads_all_columns(tmp_path: Path):
    csv_path = tmp_path / "ohlcv.csv"
    csv_path.write_text(
        "Date,Open,High,Low,Close,Volume\n"
        "2024-01-01,100,110,99,105,1200\n"
        "2024-01-02,105,106,98,99,900\n",
        encoding="utf-8",
    )

    df = load_dataframe(csv_path)

    assert list(df.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 2
    assert df["Close"].tolist() == [105.0, 99.0]


def test_load_dataframe_with_index(tmp_path: Path):
    csv_path = tmp_path / "ohlcv.csv"
    csv_path.write_text(
        "Date,Open,High,Low,Close,Volume\n"
        "2024-01-01,100,110,99,105,1200\n",
        encoding="utf-8",
    )

    df = load_dataframe(csv_path, index_col="Date", parse_dates=True)

    assert df.index.name == "Date"
    assert "Open" in df.columns


def test_load_dataframe_missing_required_header(tmp_path: Path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("Open,High,Low,Close\n100,110,99,105\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required fields"):
        load_dataframe(csv_path)


def test_load_dataframe_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_dataframe(Path("nonexistent.csv"))


# --- validate ---

def test_validate_raises_on_nan_in_ohlcv(tmp_path: Path):
    csv_path = tmp_path / "ohlcv.csv"
    csv_path.write_text(
        "Open,High,Low,Close,Volume\n"
        "100,110,,105,1000\n",
        encoding="utf-8",
    )
    module = load_module_class("vn30f1m")()

    with pytest.raises(ValueError, match="NaN"):
        df = load_dataframe(csv_path)
        module.validate(df)


def test_validate_raises_on_zero_open(tmp_path: Path):
    csv_path = tmp_path / "ohlcv.csv"
    csv_path.write_text(
        "Open,High,Low,Close,Volume\n"
        "0,110,99,105,1000\n",
        encoding="utf-8",
    )
    module = load_module_class("vn30f1m")()

    with pytest.raises(ValueError, match="Open"):
        df = load_dataframe(csv_path)
        module.validate(df)


def test_validate_raises_on_non_numeric_ohlcv(tmp_path: Path):
    csv_path = tmp_path / "ohlcv.csv"
    csv_path.write_text(
        "Open,High,Low,Close,Volume\n"
        "abc,110,99,105,1000\n",
        encoding="utf-8",
    )
    module = load_module_class("vn30f1m")()

    with pytest.raises(ValueError, match="numeric"):
        df = load_dataframe(csv_path)
        module.validate(df)


# --- vn30f1m label ---

def _make_df():
    return pd.DataFrame(
        {
            "Open":   [100.0, 100.0, 100.0],
            "High":   [110.0, 101.0, 101.0],
            "Low":    [99.0,  90.0,  99.0],
            "Close":  [105.0, 94.0,  100.5],
            "Volume": [1000.0, 900.0, 800.0],
        },
        index=pd.to_datetime(["2024-01-01 09:15", "2024-01-01 09:20", "2024-01-01 09:25"]),
    )


def test_vn30f1m_label_produces_allow_entry_column():
    from labelohlcv.modules.vn30f1m import Module

    df = _make_df()
    args = type("Args", (), {})()

    with patch("labelohlcv.modules.vn30f1m.urlopen", _fake_urlopen):
        result = Module().label(df, args)

    assert "allow_entry" in result.columns


def test_vn30f1m_does_not_mutate_input():
    from labelohlcv.modules.vn30f1m import Module

    df = _make_df()
    original_cols = list(df.columns)
    args = type("Args", (), {})()

    with patch("labelohlcv.modules.vn30f1m.urlopen", _fake_urlopen):
        Module().label(df, args)

    assert list(df.columns) == original_cols


# --- LabelPipeline is base class ---

def test_label_pipeline_is_abstract():
    assert issubclass(load_module_class("vn30f1m"), LabelPipeline)


# --- save_csv ---

def test_save_csv_writes_file(tmp_path: Path):
    output_path = tmp_path / "out.csv"
    df = pd.DataFrame({"Open": [100.0], "allow_entry": ["Bullish"]})

    save_csv(df, output_path)

    assert output_path.exists()
    loaded = pd.read_csv(output_path)
    assert list(loaded.columns) == ["Open", "allow_entry"]
    assert loaded["allow_entry"].tolist() == ["Bullish"]


def test_load_module_class_returns_module():
    module_class = load_module_class("vn30f1m")

    assert module_class.__name__ == "Module"


# --- codex label ---

def _make_codex_df():
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(
                [
                    "2024-01-01 09:00",
                    "2024-01-01 09:05",
                    "2024-01-01 09:10",
                    "2024-01-01 09:15",
                ]
            ),
            "Open": [100.0, 100.5, 102.0, 103.0],
            "High": [100.5, 102.0, 103.5, 104.0],
            "Low": [99.5, 100.2, 101.8, 102.7],
            "Close": [100.0, 101.0, 103.0, 103.5],
            "Volume": [1000.0, 1100.0, 1200.0, 900.0],
        }
    )


def test_codex_module_is_pipeline():
    assert issubclass(load_module_class("codex"), LabelPipeline)


def test_codex_parser_accepts_label_options():
    from labelohlcv.modules.codex import Module

    parser = ArgumentParser()
    Module.configure_parser(parser)
    args = parser.parse_args(
        [
            "--horizon",
            "2",
            "--threshold-pct",
            "0.01",
            "--prefix",
            "test",
            "--allow-cross-session",
        ]
    )

    assert args.horizon == 2
    assert args.threshold_pct == 0.01
    assert args.prefix == "test"
    assert args.allow_cross_session is True


def test_codex_label_adds_targets_without_mutating_input():
    from labelohlcv.modules.codex import Module

    df = _make_codex_df()
    original_columns = list(df.columns)
    args = type(
        "Args",
        (),
        {
            "horizon": 2,
            "threshold_pct": 0.01,
            "take_profit_pct": None,
            "stop_loss_pct": None,
            "prefix": "test",
            "allow_cross_session": False,
        },
    )()

    result = Module().label(df, args)

    assert list(df.columns) == original_columns
    assert result.loc[0, "test_label"] == "Bullish"
    assert result.loc[0, "test_target"] == 1
    assert result.loc[0, "test_entry_signal"] == "Long"
    assert bool(result.loc[0, "test_future_complete"]) is True
    assert result.loc[0, "test_long_outcome"] == "tp"
    assert result.loc[2, "test_label"] == "Unknown"
    assert "allow_entry" in result.columns
    assert "Date" in result.columns
    assert "Open" not in result.columns
    assert "test_range" not in result.columns
    assert "test_return_1" not in result.columns


# --- vn30f1m rule caching tests ---

def test_load_rules_creates_cache(tmp_path: Path):
    from labelohlcv.modules.vn30f1m import _load_rules
    cache_file = tmp_path / "cache.json"

    with patch("labelohlcv.modules.vn30f1m.CACHE_FILE", cache_file), \
         patch("labelohlcv.modules.vn30f1m.CACHE_DIR", tmp_path), \
         patch("labelohlcv.modules.vn30f1m.urlopen", _fake_urlopen):
        rules = _load_rules()

    assert rules == FAKE_RULES
    assert cache_file.exists()
    assert json.loads(cache_file.read_text(encoding="utf-8")) == FAKE_RULES


def test_load_rules_uses_cache_on_network_error(tmp_path: Path):
    from labelohlcv.modules.vn30f1m import _load_rules
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps(FAKE_RULES), encoding="utf-8")

    def _error_urlopen(url, timeout=5):
        raise OSError("Network offline")

    with patch("labelohlcv.modules.vn30f1m.CACHE_FILE", cache_file), \
         patch("labelohlcv.modules.vn30f1m.urlopen", _error_urlopen):
        rules = _load_rules()

    assert rules == FAKE_RULES


def test_load_rules_uses_fallback_when_offline_and_no_cache(tmp_path: Path):
    from labelohlcv.modules.vn30f1m import _load_rules, DEFAULT_FALLBACK_RULES
    cache_file = tmp_path / "nonexistent.json"

    def _error_urlopen(url, timeout=5):
        raise OSError("Network offline")

    with patch("labelohlcv.modules.vn30f1m.CACHE_FILE", cache_file), \
         patch("labelohlcv.modules.vn30f1m.urlopen", _error_urlopen):
        rules = _load_rules()

    assert rules == DEFAULT_FALLBACK_RULES

