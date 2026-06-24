# Compute Layer — Execution Guide

> Loaded when the Agent needs to **execute or interpret** chanlun computation.
> For architecture overview, read parent `SKILL.md` instead.

---

## Input Contract

```
DataFrame columns (required): date, open, high, low, close, volume
```

| Field | Type | Constraint |
|-------|------|------------|
| date | datetime / ISO string | ascending, no duplicates |
| open | float | ≥ 0 |
| high | float | ≥ max(open, close) |
| low | float | ≤ min(open, close) |
| close | float | ≥ 0 |
| volume | float | ≥ 0 (0 allowed for indices) |

**Minimum data**: 30 klines. **Recommended**: ≥ 100 klines.

---

## Pipeline → Algorithm Reference

Each step's pseudocode lives in `compute/algorithms.md`. Reference by section:

| Step | algorithms.md § | Engine function | done flag |
|------|-----------------|-----------------|-----------|
| 1. K线包含处理 | §1 | `process_inclusion()` | `inclusion_done` |
| 2. 分型识别 | §2 | `find_fractals()` | `fractals_done` |
| 3. 笔划分 | §3 | `build_pens()` | `strokes_done` |
| 4. 线段划分 | §4 | `build_segments()` | `segments_done` |
| 5. 中枢识别 | §5 | `find_pivots()` | `centers_done` |
| 6. 趋势判定 | — | (derived from pivots) | (included in `centers_done`) |
| 7. 背驰检测 | §6 | `detect_divergence()` | `divergence_done` |
| 8. 买卖点标注 | §7 | `find_buy_sell_points()` | `buy_sell_points_done` |

Step 6 (趋势判定) is not a separate function — it's derived from pivot sequence analysis. The engine classifies trend vs. consolidation based on whether successive pivots are displaced in the same direction.

---

## compute_status Schema

```json
{
  "compute_status": {
    "pipeline_version": "2.0",
    "inclusion_done": true,
    "fractals_done": true,
    "strokes_done": true,
    "segments_done": true,
    "centers_done": true,
    "divergence_done": true,
    "buy_sell_points_done": true,
    "warnings": [],
    "data_quality": {
      "klines_count": 240,
      "after_inclusion_count": 180,
      "missing_sessions": 0,
      "sufficient": true
    }
  }
}
```

### Warning Catalog

The engine emits warnings when computation quality may be degraded. Each warning has a code and description:

| Code | Trigger | Impact |
|------|---------|--------|
| `insufficient_klines` | < 30 klines | All results unreliable |
| `limited_klines` | < 100 klines | Segment/center count may be too few for meaningful pattern detection |
| `high_inclusion_ratio` | > 50% klines merged | Reduced effective data points; fractal/stroke quality degraded |
| `too_few_fractals` | < 3 fractals after inclusion | Cannot form valid pens |
| `too_few_pens` | < 3 pens | Segment/center/divergence analysis not meaningful |
| `no_pivots_found` | 0 centers detected | Buy/sell point detection returns empty |
| `last_segment_unconfirmed` | Final segment may still be revised | Do not trade on unconfirmed segments |

### data_quality Rules

| Field | Calculation |
|-------|-------------|
| `klines_count` | `len(input_df)` |
| `after_inclusion_count` | `len(df_inc)` post Step 1 |
| `missing_sessions` | Count of gaps in date index exceeding expected trading interval (0 for CSV without session awareness) |
| `sufficient` | `klines_count >= 30 AND too_few_pens not in warnings` |

---

## Engine Usage

### Python API

```python
from chanlun_engine import analyze

result = analyze(df, pen_mode="new")
# result["compute_status"]  ← status + data_quality
# result["summary"]         ← counts
# result["fractals"]        ← list[dict]
# result["pens"]            ← list[dict]
# result["segments"]        ← list[dict]
# result["pivots"]          ← list[dict]
# result["divergence"]      ← list[dict]
# result["buy_sell_points"] ← list[dict]
```

### CLI

```bash
python scripts/chanlun_engine.py --csv data.csv -o result.json
python scripts/chanlun_engine.py --sample --pen-mode old
python scripts/chanlun_engine.py --sample --summary-only
```

---

## Known Simplifications

The engine implements these simplifications vs. strict 缠论:

1. **线段第二种情况（有缺口）**: Direct confirmation without second feature-sequence fractal verification.
2. **首根K线方向**: Defaults to upward (`direction = 1`).
3. **未完成走势**: Final pen/segment not tagged as `confirmed: false` — the Agent should treat the last element of each list as potentially unconfirmed.
4. **中枢构建**: Built from consecutive segments (≥3) checking for price overlap, not from recursive sublevel trend types.
5. **背驰面积**: Uses MACD histogram area as the sole force metric. Does not cross-validate with slope or lower-level interval nesting.

These map to `definition_mode` downgrade in the Audit layer. See `audit/SKILL.md`.

---

## Multi-Level Computation

For multi-level analysis (e.g., Daily + 30F + 5F):

1. **Fetch data for each timeframe independently** (yfinance interval, akshare period, or separate CSVs).
2. **Run `analyze()` on each timeframe separately** — the engine is single-level.
3. **Aggregate results** in the Agent:
   - Operating level (e.g., Daily) → defines trade context and buy/sell candidates.
   - Confirm level (e.g., 30F) → verifies structure.
   - Trigger level (e.g., 5F) → entry timing.
4. **Pass the `compute_status` from each level** to the Audit layer for multi-level gate checks.

**Do NOT mix timeframes in a single `analyze()` call.** The engine assumes one consistent timeframe per invocation.

---

## Interface to Audit Layer

The compute output JSON flows directly into the Audit layer. The audit gates consume:

- `compute_status` → GATE 2 (structure_gate) checks done flags and warnings
- `pivots` → GATE 3 (type_gate) classifies current state
- `divergence` → GATE 4 (comparison_gate) validates divergence claims
- `buy_sell_points` → GATE 5 (buy_sell_gate) checks signal strictness

No transformation needed — pass the compute output dict directly.
