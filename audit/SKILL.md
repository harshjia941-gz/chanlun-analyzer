# Audit Layer — Gate Execution Guide

> Loaded when the Agent needs to **run the 8-gate audit** on compute output.
> For gate overview and audit report format, see parent `SKILL.md`.
> For theory and concept definitions, see `audit/strict-original-system.md` and `audit/concepts.md`.

---

## Execution Algorithm

```
INPUT:  compute_result (from compute layer)
        trade_level, confirm_level, trigger_level (declared by operator)
OUTPUT: audit_report (JSON)

FOR gate IN [1..8]:
    result = run_gate(gate, compute_result, levels)
    IF result.fail:
        gates_failed.append(gate)
        apply_downgrade(result.definition_mode, result.loss)
    ELSE:
        gates_passed.append(gate)

RETURN audit_report
```

**Hard rule**: Gates execute in order 1→8. If GATE 1 fails, do not proceed — return immediately with `definition_mode: "untradable_unclear"`.

---

## Gate Specifications

### GATE 1: level_gate

| | |
|---|---|
| **Input** | `trade_level`, `confirm_level`, `trigger_level` (operator-declared strings) |
| **Check** | All three fields are non-empty and follow the level hierarchy: `trade_level > confirm_level > trigger_level` |
| **Valid levels** | `1F, 5F, 15F, 30F, 60F, D, W, M` |
| **Pass** | All three present and hierarchically consistent |
| **Fail** | Any missing, or hierarchy violated (e.g., `trigger_level > confirm_level`) |
| **On fail** | Return `definition_mode: "untradable_unclear"`, stop audit |

### GATE 2: structure_gate

| | |
|---|---|
| **Input** | `compute_status` from compute layer |
| **Check** | Steps [1]-[5] all done; no critical warnings |
| **Critical warnings** | `insufficient_klines`, `too_few_pens`, `no_pivots_found` |
| **Pass** | All done flags true; no critical warnings |
| **Partial pass** | Steps [1]-[3] done but [4] or [5] incomplete → `structure_proxy` |
| **Fail** | Steps [1]-[2] incomplete → `proxy_research` |
| **On fail** | Set `definition_mode` per partial results; record `approximation_loss` |

### GATE 3: type_gate

| | |
|---|---|
| **Input** | `pivots` array, latest price |
| **Check** | Classify current state into one of the valid labels |
| **Valid labels** | `center_oscillation`, `center_extension`, `center_breakout`, `uptrend`, `downtrend`, `transition_zhongyin`, `first_buy_candidate`, `second_buy_candidate`, `third_buy_candidate`, `untradable_unclear` |
| **Classification logic** | If price inside latest pivot [ZD, ZG] → `center_oscillation` or `center_extension` (based on extension_count). If price left pivot upward → `center_breakout` or `uptrend`. If price left pivot downward → `downtrend`. If ambiguous → `untradable_unclear`. |
| **Pass** | State is classifiable into a non-`unclear` label |
| **Fail** | `untradable_unclear`; action ceiling = `observe` |

### GATE 4: comparison_gate

| | |
|---|---|
| **Input** | `divergence` array from compute, `pivots` for context |
| **Check** | Each divergence entry names the two compared movements (A segment and C segment) and confirms they are same-level |
| **Pass** | Divergence has `pivot_idx` referencing a valid pivot; both compared segments are between/after same-level pivots |
| **Fail** | Divergence claimed without structural context → invalidate divergence; set `indicator_proxy` if relying solely on MACD |
| **Detail** | See `audit/strict-original-system.md` → "Divergence compares named same-level movements" |

### GATE 5: buy_sell_gate

| | |
|---|---|
| **Input** | `buy_sell_points` array, `pivots`, `divergence` |
| **Check** | Each buy/sell point satisfies strict definition |
| **Buy1 strict** | Prior same-level downtrend (≥2 displaced pivots) + C segment new low + divergence confirmed |
| **Buy2 strict** | Buy1 candidate exists + first rebound named + pullback doesn't break Buy1 low |
| **Buy3 strict** | Valid center with ZG/ZD named + price left above ZG + pullback doesn't re-enter center |
| **Sell mirrors** | Same logic inverted |
| **Pass** | Point meets all conditions for its class |
| **Partial** | Point has structural resemblance but missing lower-level confirmation → `signal_proxy` |
| **Fail** | Point derived from indicator only → `indicator_proxy`; action ceiling = `observe` |
| **Detail** | See `decide/buy-sell-playbooks.md` for full playbooks |

### GATE 6: trigger_gate

| | |
|---|---|
| **Input** | Lower-level compute result (if available), operating-level buy/sell candidates |
| **Check** | Lower-level trigger confirmed inside the final operating-level segment |
| **Confirmed** | Lower-level first buy/sell or center break in expected direction |
| **Missing** | No lower-level data, or lower-level structure not yet complete |
| **Pending** | Lower-level shows developing structure but not yet confirmed |
| **On missing/pending** | `trigger_status: "missing"` or `"pending"`; action ceiling = `observe` |
| **Note** | If no lower-level data is available at all, this gate fails with `trigger_missing`. Mark `approximation_loss: "medium"`. |

### GATE 7: risk_gate

| | |
|---|---|
| **Input** | Audit results so far (definition_mode, buy/sell candidates) |
| **Check** | Every buy/sell candidate has an explicit invalidation boundary |
| **Pass** | All candidates have named invalidation price/level |
| **Fail** | Any candidate without invalidation → **reject all actions**, output `action: "wait"` |
| **Rule** | Invalidations must be structural (price level), not temporal ("if it doesn't move in 3 days") |

### GATE 8: downgrade_gate

| | |
|---|---|
| **Input** | All gate results [1]-[7] |
| **Check** | Aggregate results into final `definition_mode` and `approximation_loss` |
| **Logic** | See downgrade decision tree below |
| **Output** | Final `audit` object for decide layer |

---

## Downgrade Decision Tree

```
IF gate_1 failed:
    → untradable_unclear, loss=high, STOP

IF gate_2 failed (steps 1-2 incomplete):
    → proxy_research, loss=high

IF gate_2 partial (steps 1-3 done, 4-5 incomplete):
    → structure_proxy, loss=low

IF gate_3 failed (state unclear):
    → untradable_unclear, loss=medium

IF gate_4 failed (divergence unvalidated):
    → indicator_proxy (for divergence claims only)
    → structure can still be valid for non-divergence signals

IF gate_5 failed (buy/sell not strict):
    IF structural resemblance exists:
        → signal_proxy, loss=medium
    ELSE:
        → indicator_proxy, loss=high

IF gate_6 failed (trigger missing):
    → definition_mode unchanged BUT
      trigger_status = "missing"
      action ceiling = observe

IF gate_7 failed (no invalidation):
    → reject all actions, force action = "wait"

FINAL definition_mode = worst-case among all gate results
```

---

## Shortcut Detection

The following patterns trigger automatic gate failure:

| Shortcut | Detected By | Gate | Result |
|----------|-------------|------|--------|
| MACD divergence → claiming Buy1 without downtrend context | Gate 5 checks pivot sequence | 5 | → `indicator_proxy` |
| Price breakout → claiming Buy3 without pullback confirmation | Gate 5 checks pullback existence | 5 | → reject |
| Higher high/low → claiming Buy2 without prior Buy1 | Gate 5 checks Buy1 dependency | 5 | → reject |
| Lower-level indicator treated as lower-level structure | Gate 6 checks for structural trigger, not MA/MACD | 6 | → `trigger_missing` |
| Daily signal + 30m MACD labeled as "multi-level confirmed" | Gate 4 checks that both levels have structural pivots | 4 | → invalid divergence |

---

## Interaction with Compute Output

The audit layer is **read-only** on compute output — it never modifies the compute result. It produces a separate `audit` object that the decide layer consumes.

**No transformation between compute and audit.** Pass the compute output dict directly.

---

## Interface to Decide Layer

The decide layer consumes:

- `audit.definition_mode` → sets maximum action ceiling
- `audit.gates_failed` → determines which filters apply
- `audit.trigger_status` → gates entry timing
- `audit.approximation_loss` → adjusts confidence

See `decide/SKILL.md` for action selection.
