from pathlib import Path

from labelohlcv.modules.base import Candle, load_candles, save_output
from labelohlcv.modules import load_module_class


def test_label_candles_labels_buy_sell_hold():
    from labelohlcv.modules.vn30f1m import Module

    candles = [
        Candle(open=100, high=110, low=99, close=105),
        Candle(open=100, high=101, low=90, close=94),
        Candle(open=100, high=101, low=99, close=100.5),
    ]

    module = Module()
    labels = [result.label for result in module.label(candles, args=type("Args", (), {"up_threshold": 0.04, "down_threshold": 0.05})())]

    assert labels == ["buy", "sell", "hold"]


def test_load_candles_reads_csv(tmp_path: Path):
    csv_path = tmp_path / "ohlcv.csv"
    csv_path.write_text(
        "Open,High,Low,Close,Volume\n"
        "100,110,99,105,1200\n"
        "105,106,98,99,900\n",
        encoding="utf-8",
    )

    candles = load_candles(csv_path)

    assert candles == [
        Candle(open=100.0, high=110.0, low=99.0, close=105.0, volume=1200.0),
        Candle(open=105.0, high=106.0, low=98.0, close=99.0, volume=900.0),
    ]


def test_vn30f1m_module_labels(tmp_path: Path):
    from labelohlcv.modules.vn30f1m import Module

    candles = [
        Candle(open=100, high=110, low=99, close=105),
        Candle(open=100, high=101, low=90, close=94),
    ]

    results = Module().label(candles, args=type("Args", (), {"up_threshold": 0.01, "down_threshold": 0.01})())

    assert [result.label for result in results] == ["buy", "sell"]


def test_save_output_writes_json(tmp_path: Path):
    output_path = tmp_path / "out.json"
    data = [{"hello": "world"}]

    save_output(data, output_path)

    assert output_path.read_text(encoding="utf-8") == '[\n  {\n    "hello": "world"\n  }\n]'


def test_load_module_class_returns_module():
    module_class = load_module_class("vn30f1m")

    assert module_class.__name__ == "Module"
