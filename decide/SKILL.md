# Decide Layer — Action Selection Guide

> Loaded when the Agent needs to **translate audit results into actions**.
> For action space overview and filter types, see parent `SKILL.md`.
> For detailed buy/sell playbooks, see `decide/buy-sell-playbooks.md`.
> For risk and invalidation rules, see `decide/invalidation-risk.md`.

---

## Execution Algorithm

```
INPUT:  compute_result (from compute layer)
        audit_report (from audit layer)
        portfolio_context (current positions, risk limits)
OUTPUT: decision (JSON with action + confidence + invalidation)

# Step 1: Determine action ceiling from structure filter
action_ceiling = get_action_ceiling(audit.definition_mode, audit.trigger_status)

# Step 2: Start with structural signal
structural_signal = interpret_buy_sell_points(compute_result.buy_sell_points, audit)

# Step 3: Apply filters in order
for filter in [technical, risk]:
    structural_signal = apply_filter(structural_signal, filter, compute_result)

# Step 4: Clamp to ceiling
final_action = clamp(structural_signal.action, ceiling=action_ceiling)

# Step 5: Build decision output
RETURN decision
```

---

## Action Ceiling Rules

The `definition_mode` and `trigger_status` from the audit layer set a hard ceiling on what actions are allowed:

| definition_mode | trigger_status | Action Ceiling |
|-----------------|----------------|----------------|
| `strict_chanlun` | `confirmed` | All actions allowed |
| `strict_chanlun` | `pending` | `observe` max |
| `structure_proxy` | `confirmed` | `buy_probe` max |
| `structure_proxy` | `pending` | `observe` max |
| `signal_proxy` | `confirmed` | `buy_probe` max |
| `signal_proxy` | `missing` | `observe` max |
| `indicator_proxy` | any | `observe` max |
| `untradable_unclear` | any | `wait` only |

**Hard rule**: No filter or indicator can override the ceiling. The ceiling is structural.

---

## Filter Application Order

Filters apply sequentially. Each filter can confirm, downgrade, or veto.

### Filter 1: Technical (confidence adjustment)

| Source | Data | Effect |
|--------|------|--------|
| MACD | `divergence[].ratio`, `divergence[].strength` | If ratio < 0.5: confidence +0.1. If ratio > 0.8: confidence -0.15 |
| RSI | Compute from close prices | RSI < 30 at Buy1: +0.1. RSI > 70 at Sell1: +0.1. RSI 40-60 at Buy3: neutral |
| Volume | From OHLCV data | Volume expanding on breakout: +0.1. Volume shrinking on breakout: -0.15 |
| Moving Averages | Compute from close | Price above MA60 at Buy3: +0.05. Price below MA60 at Buy1: neutral (expected) |
| Turnover / Money Flow | If available | Main-money outflow at Buy candidate: veto. Inflow at Sell candidate: veto (hold) |

### Filter 2: Risk (position sizing + veto)

| Check | Condition | Effect |
|-------|-----------|--------|
| Position limit | Already at max position for symbol | Veto buy actions |
| Stop-loss distance | Invalidation > 10% away from current price | Reduce position size by 50% |
| Market environment | Broad index in downtrend (if known) | Confidence -0.2 |
| Liquidity | Avg volume < threshold | Veto large positions |

---

## Confidence Calculation

Base confidence comes from the compute layer's `buy_sell_points[].confidence` (0-1 scale, derived from MACD area ratio).

```
final_confidence = base_confidence
                 + macd_adjustment
                 + rsi_adjustment
                 + volume_adjustment
                 + ma_adjustment
                 + market_adjustment

final_confidence = clamp(final_confidence, 0.0, 1.0)
```

If any filter returns **veto**, `action` is forced to `wait` or `observe` regardless of confidence.

---

## Action Selection Logic

```
IF no buy/sell points detected:
    action = "wait"

ELSE IF audit_ceiling == "wait":
    action = "wait"

ELSE IF audit_ceiling == "observe":
    action = "observe"

ELSE:
    # Structural signal exists and ceiling allows action
    FOR each buy_sell_point (most recent first):
        IF side == "buy":
            IF point.type == 1 AND trigger_confirmed:
                action = "buy_probe"   # First buy: always probe first
            IF point.type == 2 AND trigger_confirmed:
                action = "buy_confirmed"  # Second buy: can confirm
            IF point.type == 3:
                action = "buy_confirmed" IF first/second context exists
                         ELSE "buy_probe"
        IF side == "sell":
            IF holding_position:
                IF point.type == 1:
                    action = "sell_exit"  # Trend reversal
                IF point.type == 2:
                    action = "reduce"     # Risk reduction
                IF point.type == 3:
                    action = "reduce"     # Short-term risk

    # Apply filter vetos
    IF any_filter_veto:
        action = downgrade_action(action)

    # Apply ceiling clamp
    action = clamp_to_ceiling(action, audit_ceiling)
```

---

## Decision Output Schema

```json
{
  "decision": {
    "action": "wait|observe|buy_probe|buy_confirmed|hold|reduce|sell_exit|rebut|reject",
    "signal_source": {
      "point_type": 1,
      "side": "buy",
      "price": 100.5,
      "confidence_structural": 0.85
    },
    "confidence_final": 0.78,
    "invalidation": {
      "type": "price_level",
      "value": 95.2,
      "description": "Break below first-buy low at 95.2"
    },
    "next_observe": "30F center formation inside daily final down segment",
    "filters_applied": [
      {"name": "macd", "result": "confirm", "adjustment": 0.1},
      {"name": "volume", "result": "neutral", "adjustment": 0},
      {"name": "market", "result": "caution", "adjustment": -0.2}
    ],
    "filter_vetoes": [],
    "rationale": "First buy candidate with 30F trigger confirmed. MACD area ratio 0.42 supports divergence. Market environment cautious."
  }
}
```

---

## Holding Logic

If already in a position, the decide layer checks for sell-side signals instead of buy-side:

| Current State | Signal | Action |
|---------------|--------|--------|
| Holding from Buy1/2 | No sell signal, structure intact | `hold` |
| Holding from Buy1/2 | Operating-level Sell1 appears | `sell_exit` |
| Holding from Buy3 | No sell signal, trend continues | `hold` |
| Holding from Buy3 | Lower-level Sell3 appears (not operating-level) | `hold` (or `reduce` if position is large) |
| Any position | Invalidated | `sell_exit` immediately |
| Reduced/Sold | Buy signal reappears without structural damage | `rebut` |

---

## Interaction with Audit

The decide layer **only reads** the audit report — it does not re-check gates or override `definition_mode`.

If `audit.trigger_status == "missing"` and the Agent has lower-level data available that wasn't checked:
- The Agent may re-run the audit with updated lower-level data.
- But the decide layer processes whatever the audit layer output, not raw data.
