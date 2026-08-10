# Module: vn30f1m

Dán nhãn dữ liệu OHLCV cho hợp đồng tương lai **VN30F1M** (hợp đồng tháng gần nhất của chỉ số VN30).

---

## Nguồn quy tắc

Quy tắc giao dịch được tải động từ remote và tự động lưu cache trực tiếp trong thư mục module project (`close_position_rules.json`):

```
https://raw.githubusercontent.com/tempusoneps/trading-rules/refs/heads/main/VN30F1M/close_position_rules.json
```
*(Nếu không có mạng hoặc request lỗi, hệ thống sẽ tự động sử dụng file cache local hoặc rule fallback)*

Rule được sử dụng: **`no-overnight-sl033-tp132-tsl035-fc1425`**

| Tham số | Giá trị | Ý nghĩa |
|---------|---------|---------|
| `no-overnight` | — | Không giữ lệnh qua đêm |
| `sl033` | 0.33% | Stop Loss |
| `tp132` | 1.32% | Take Profit |
| `tsl035` | 0.35% | Trailing Stop Loss |
| `fc1425` | 14:25 | Force close cuối phiên |

---

## Input / Output

**Input**: CSV có cột `Date` (dùng làm index datetime) và các cột OHLCV tiêu chuẩn.

**Output**: DataFrame gốc với các cột label bên dưới.

---

## Các cột label

### Nhóm 1 — Entry signal (theo từng nến, dùng dữ liệu phía trước)

Với mỗi nến, lấy cửa sổ `data_to_end_day` = tất cả nến từ thời điểm hiện tại đến **14:30:00 cùng ngày**.
Nếu không còn nến phía trước → tất cả cột nhóm này = `None` / `""`.

**Biến trung gian:**
```
entry_price = Close của nến hiện tại
high_max    = max(High)  trong data_to_end_day
low_min     = min(Low)   trong data_to_end_day
long_sl     = entry_price × (1 - sl%)
short_sl    = entry_price × (1 + sl%)
```

#### `allow_entry`

| `longable` | `shortable` | Giá trị | Diễn giải |
|:---:|:---:|---|---|
| ✅ | ✅ | `No - Sideway` | Cả hai SL chưa bị chạm → giá đi ngang |
| ✅ | ❌ | `Yes - Buy` | Short SL bị chạm → giá tăng mạnh |
| ❌ | ✅ | `Yes - Sell` | Long SL bị chạm → giá giảm mạnh |
| ❌ | ❌ | `No - None` | Cả hai SL đều bị chạm |
| — | — | `""` | Nến cuối ngày, không còn dữ liệu phía trước |

#### `remain_session_volatility`

Biên độ giá của phần còn lại trong phiên:
```
remain_session_volatility = high_max - low_min
```

#### `remain_session_net_move`

Hướng thiên của phần còn lại trong phiên so với entry:
```
remain_session_net_move = high_max + low_min - 2 × entry_price
```
- `> 0` → thiên tăng
- `< 0` → thiên giảm
- `≈ 0` → đối xứng

#### `long_mae` / `short_mae` — Maximum Adverse Excursion (%)

Mức giá bất lợi nhất phải chịu nếu vào Long hoặc Short:
```
long_mae  = (entry_price - low_min)  / entry_price × 100
short_mae = (high_max - entry_price) / entry_price × 100
```
So với SL 0.33%: nếu `long_mae > 0.33` → vị thế Long bị cắt lỗ trong phiên đó.

#### `long_mfe` / `short_mfe` — Maximum Favorable Excursion (%)

Lợi nhuận tốt nhất có thể đạt được nếu vào Long hoặc Short:
```
long_mfe  = (high_max - entry_price) / entry_price × 100
short_mfe = (entry_price - low_min)  / entry_price × 100
```

#### `rr_long` / `rr_short` — Risk/Reward thực tế

```
rr_long  = long_mfe  / long_mae   (None nếu long_mae = 0)
rr_short = short_mfe / short_mae  (None nếu short_mae = 0)
```

#### `eod_return_long` / `eod_return_short` — Kết quả thực khi hold đến cuối phiên (%)

```
session_close      = Close của nến cuối cùng trong data_to_end_day
eod_return_long  = (session_close - entry_price) / entry_price × 100
eod_return_short = (entry_price - session_close) / entry_price × 100
```
Dương = có lời, âm = lỗ.

---

### Nhóm 2 — Đặc tính ngày (dùng toàn bộ dữ liệu trong ngày)

Tính bằng `groupby(date)` vectorized, áp dụng cho tất cả nến trong cùng ngày.

#### `price_range`

Biên độ toàn ngày:
```
price_range = day_high - day_low
```

#### `intraday_position`

Vị trí của nến trong range ngày:

| Giá trị | Điều kiện |
|---------|-----------|
| `peak` | `High == day_high` (nến giữ High cao nhất ngày) |
| `valley` | `Low == day_low` (nến giữ Low thấp nhất ngày) |
| `norm` | Còn lại |

Nếu một nến vừa có `High == day_high` vừa có `Low == day_low` → ưu tiên `peak`.

#### `price_shape`

Phân loại hành vi giá cả ngày dựa trên 3 yếu tố:
- `high_first` = High xuất hiện trước Low trong ngày
- `open_pos = (open - day_low) / price_range` → zone: `low ≤ 0.3`, `mid`, `high ≥ 0.7`
- `close_pos = (close - day_low) / price_range` → zone tương tự

Ngưỡng `narrow_range`: `price_range < median(price_range toàn dataset) × 0.3`

| Giá trị | `high_first` | `open_pos` | `close_pos` | Mô tả |
|---------|:---:|:---:|:---:|-------|
| `strong_bull` | False | low | high | Tăng thẳng suốt ngày |
| `bull_grind` | False | mid/high | high | Tăng dần |
| `bull_reversal` | True | low | high | Giảm trước, phục hồi mạnh vượt open |
| `bull_trap` | False | low/mid | low | Bật lên rồi bị bán tháo |
| `strong_bear` | True | high | low | Giảm thẳng suốt ngày |
| `bear_grind` | True | low/mid | low | Giảm dần |
| `bear_reversal` | False | high | low | Tăng trước, đảo chiều mạnh dưới open |
| `bear_trap` | True | mid/high | high | Giảm rồi bị squeeze lên cao |
| `two_sided_bull` | False | low | mid | Hai chiều, đóng cửa phần trên |
| `two_sided_bear` | True | high | mid | Hai chiều, đóng cửa phần dưới |
| `two_sided_neutral` | any | mid | mid | Giằng co, đóng cửa giữa range |
| `narrow_range` | — | — | — | Biên độ ngày quá hẹp (< 30% median) |

#### `is_peak_10` / `is_valley_10`

Xác định nến là đỉnh (Peak) hoặc đáy (Valley) cục bộ trong bán kính 10 nến trước và 10 nến sau (cửa sổ 21 nến cross-session):
- `is_peak_10`: `True` nếu `High == max(High trong cửa sổ 21 nến centered)`, ngược lại `False`.
- `is_valley_10`: `True` nếu `Low == min(Low trong cửa sổ 21 nến centered)`, ngược lại `False`.

---

## Sơ đồ tổng quan

```
Mỗi nến (vòng lặp có progress bar)
    │
    ├─ Không có dữ liệu phía trước? ──► tất cả cột nhóm 1 = None / ""
    │
    ├─ Tính high_max, low_min từ data_to_end_day
    │
    ├─ allow_entry     (longable / shortable vs SL)
    ├─ remain_session_volatility  (high_max - low_min)
    ├─ remain_session_net_move    (high_max + low_min - 2×entry)
    ├─ long_mae / short_mae       (% bất lợi tối đa)
    ├─ long_mfe / short_mfe       (% có lợi tối đa)
    ├─ rr_long / rr_short         (MFE / MAE)
    └─ eod_return_long / short    (kết quả thực khi hold đến cuối phiên)

Sau vòng lặp (vectorized groupby theo ngày)
    ├─ price_range        (day_high - day_low)
    ├─ intraday_position  (peak / valley / norm)
    └─ price_shape        (12 pattern dựa trên open_pos, close_pos, high_first)
```
