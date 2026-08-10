# Add `is_peak_10` and `is_valley_10` Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `is_peak_10` and `is_valley_10` boolean columns to the `vn30f1m` module.

**Architecture:** Calculate 10-candle centered peak and valley indicators using vectorized `pd.Series.rolling(window=21, center=True, min_periods=1)` on `High` and `Low` columns in `do_label_data` in `src/labelohlcv/modules/vn30f1m.py`. Update documentation in `src/labelohlcv/modules/vn30f1m.md`.

**Tech Stack:** Python 3.12, Pandas, Pytest, UV.

## Global Constraints
- Target module: `src/labelohlcv/modules/vn30f1m.py`
- Added columns: `is_peak_10` (bool), `is_valley_10` (bool)
- Window: 21-candle centered window (10 candles before, target candle, 10 candles after), cross-session across dataset.

---

### Task 1: Implement `is_peak_10` and `is_valley_10` in `vn30f1m.py`

**Files:**
- Modify: `src/labelohlcv/modules/vn30f1m.py`
- Modify: `src/labelohlcv/modules/vn30f1m.md`
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: `label_data['High']`, `label_data['Low']`
- Produces: `label_data['is_peak_10']` (bool), `label_data['is_valley_10']` (bool)

- [ ] **Step 1: Write failing tests in `tests/test_core.py`**

Add `test_vn30f1m_label_produces_peak_and_valley_10_columns` to `tests/test_core.py`:

```python
def test_vn30f1m_label_produces_peak_and_valley_10_columns():
    from labelohlcv.modules.vn30f1m import Module

    # Create 25 candles where candle 10 has highest High and candle 15 has lowest Low
    highs = [100.0] * 25
    lows = [90.0] * 25
    highs[10] = 150.0  # Peak 10
    lows[15] = 50.0    # Valley 10

    dates = pd.date_range("2024-01-01 09:00", periods=25, freq="5min")
    df = pd.DataFrame(
        {
            "Open": [100.0] * 25,
            "High": highs,
            "Low": lows,
            "Close": [100.0] * 25,
            "Volume": [1000.0] * 25,
        },
        index=dates,
    )
    args = type("Args", (), {})()

    with patch("labelohlcv.modules.vn30f1m.urlopen", _fake_urlopen):
        result = Module().label(df, args)

    assert "is_peak_10" in result.columns
    assert "is_valley_10" in result.columns

    assert bool(result.loc[10, "is_peak_10"]) is True
    assert bool(result.loc[9, "is_peak_10"]) is False
    assert bool(result.loc[15, "is_valley_10"]) is True
    assert bool(result.loc[14, "is_valley_10"]) is False
```

- [ ] **Step 2: Run pytest to verify the test fails**

Run: `uv run pytest tests/test_core.py -k test_vn30f1m_label_produces_peak_and_valley_10_columns`
Expected: FAIL with `KeyError: 'is_peak_10'` or `AssertionError`.

- [ ] **Step 3: Implement `is_peak_10` and `is_valley_10` in `do_label_data`**

In `src/labelohlcv/modules/vn30f1m.py`, right after computing `intraday_position`:

```python
    roll_high_10 = label_data["High"].rolling(window=21, center=True, min_periods=1).max()
    roll_low_10 = label_data["Low"].rolling(window=21, center=True, min_periods=1).min()
    label_data["is_peak_10"] = label_data["High"] == roll_high_10
    label_data["is_valley_10"] = label_data["Low"] == roll_low_10
```

Also update `src/labelohlcv/modules/vn30f1m.md` to document the new columns under "Nhóm 2 — Đặc tính ngày":
```markdown
#### `is_peak_10` / `is_valley_10`

Xác định nến là đỉnh (Peak) hoặc đáy (Valley) cục bộ trong bán kính 10 nến trước và 10 nến sau (cửa sổ 21 nến):
- `is_peak_10`: `True` nếu `High == max(High trong cửa sổ 21 nến centered)`, ngược lại `False`.
- `is_valley_10`: `True` nếu `Low == min(Low trong cửa sổ 21 nến centered)`, ngược lại `False`.
```

- [ ] **Step 4: Run pytest to verify all tests pass**

Run: `uv run pytest`
Expected: PASS (all 13 tests pass).

- [ ] **Step 5: Commit changes**

```bash
git add src/labelohlcv/modules/vn30f1m.py src/labelohlcv/modules/vn30f1m.md tests/test_core.py
git commit -m "feat(vn30f1m): add is_peak_10 and is_valley_10 label columns"
```
