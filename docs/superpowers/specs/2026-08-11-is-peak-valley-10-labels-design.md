# Design Specification: `is_peak_10` and `is_valley_10` Labels in `vn30f1m`

## Overview
Add two boolean label columns, `is_peak_10` and `is_valley_10`, to the `vn30f1m` module output in `labelohlcv`.

## Specification

### 1. Label Logic
For each candle at index $i$ in the DataFrame:
- **`is_peak_10`** (`bool`): `True` if `High[i]` is equal to the maximum `High` in the centered window of radius 10 (i.e. indices $i-10$ to $i+10$ inclusive across the entire dataset). Otherwise `False`.
- **`is_valley_10`** (`bool`): `True` if `Low[i]` is equal to the minimum `Low` in the centered window of radius 10 (i.e. indices $i-10$ to $i+10$ inclusive across the entire dataset). Otherwise `False`.

### 2. Implementation Details
- **Module**: `src/labelohlcv/modules/vn30f1m.py`
- **Doc update**: `src/labelohlcv/modules/vn30f1m.md`
- **Method**: Using vectorized pandas rolling operations:
  ```python
  roll_high_10 = label_data["High"].rolling(window=21, center=True, min_periods=1).max()
  roll_low_10 = label_data["Low"].rolling(window=21, center=True, min_periods=1).min()

  label_data["is_peak_10"] = label_data["High"] == roll_high_10
  label_data["is_valley_10"] = label_data["Low"] == roll_low_10
  ```
- **Output**: The columns will be included in the returned DataFrame from `vn30f1m.Module.label()`.

### 3. Testing Plan
- Test `is_peak_10` and `is_valley_10` generation on synthetic OHLCV DataFrames in `tests/test_core.py`.
- Verify behavior at boundaries (start and end of series) and peak/valley detection across sessions.
- Run `uv run pytest` to ensure all existing and new tests pass.
