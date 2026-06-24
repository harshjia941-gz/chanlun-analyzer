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

# Check fast-path shortcuts first
IF shortcut_triggered(compute_result):
    RETURN fast_path_result

# Normal gate execution
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

**Fast-path rule**: Check shortcuts BEFORE GATE 3. If triggered, skip directly to action ceiling determination — see Fast-Path Shortcuts section below.

---

## Gate Specifications

### GATE 1: level_gate

| | |
|---|---|
| **Input** | `trade_level`, `confirm_level`, `trigger_level` (operator-declared strings) |
| **Check** | All three fields are non-empty and follow the level hierarchy: `confirm_level` (coarsest, e.g. W) > `trade_level` (operating, e.g. D) > `trigger_level` (finest, e.g. 60F) |
| **Valid levels** | `1F, 5F, 15F, 30F, 60F, D, W, M` |
| **Pass** | All three present and hierarchically consistent |
| **Fail** | Any missing, or hierarchy violated (e.g., `trigger_level` coarser than `confirm_level`, or `trade_level` finer than `trigger_level`) |
| **On fail** | Return `definition_mode: "untradable_unclear"`, stop audit |

#### Single-Level Mode

When only one timeframe of data is available (e.g., Daily only, no Weekly confirm + no 60F trigger):

| | |
|---|---|
| **When to use** | User requests single-period analysis without multi-level data |
| **Behavior** | GATE 1 auto-passes with `trigger_status = "missing"` and `approximation_loss = "high"` |
| **Effect** | Action ceiling auto-set to `observe`; structural analysis still produced but no entry/exit actions generated |
| **Declaration** | Set `trigger_level = None` or omit it to signal single-level intent |
| **Warning** | Single-level analysis is inherently incomplete — multi-level recursion is the standard for strict mode |

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

---

### ⚡ Fast-Path Shortcuts

These shortcuts apply BEFORE executing GATE 4-8. If triggered, skip directly to deciding action ceiling.

| Condition | Trigger | Action | Rationale |
|-----------|---------|--------|-----------|
| `divergence_count == 0` AND `buy_sell_point_count == 0` | No signal at all | Skip GATE 4-7; `action_ceiling = observe`; `definition_mode` unchanged | Nothing to validate. Structure exists but no actionable entry/exit. |
| `pivot_count == 0` | No center formed | Skip GATE 3-7; `definition_mode = structure_proxy`; `action_ceiling = observe` | Without a pivot, there is no center to classify or diverge from. |
| `pivot_count == 1` AND `divergence_count == 0` | Single pivot, no trend | Auto-pass GATE 4 (divergence needs ≥2 displaced pivots for trend); continue GATE 5-7 normally | A single pivot cannot form trend divergence; comparison gate is N/A. |

**Fast-Path Decision Flow:**

```
IF divergence_count == 0 AND bsp_count == 0:
    → Skip GATE 4-5-6-7 (auto-pass)
    → ceiling = observe (no signal to act on)
    → rationale: "Structure exists but no actionable signal"

ELSE IF pivot_count == 0:
    → definition_mode = structure_proxy
    → ceiling = observe
    → rationale: "No center formed; structure incomplete"

ELSE IF pivot_count == 1 AND divergence_count == 0:
    → GATE 4 auto-PASS (single pivot, no trend comparison possible)
    → Continue GATE 5-6-7-8 normally
```

**Fast-path is NOT a downgrade** — `definition_mode` is preserved (except for 0-pivot case). It simply short-circuits unnecessary gate evaluation when the structural prerequisites for those gates don't exist.

---

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
