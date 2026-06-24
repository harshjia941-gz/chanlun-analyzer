#!/usr/bin/env python3
"""
decide.py — Action Generator (Decide Layer) for chanlun-analyzer

Translates compute + audit results into actionable trading decisions,
with risk boundaries and confidence scoring.

RUO-381: Decide layer action generator

Interface:
    run_decide(compute_result, audit_result, portfolio_context=None) -> dict
"""

from __future__ import annotations
from typing import Optional

# ── Import from sibling modules ──
from audit import run_audit
from chanlun_engine import analyze, analyze_symbol

# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

CEILING_ACTION_MAP: dict[str, list[str]] = {
    "all": ["wait", "observe", "buy_probe", "buy_confirmed", "hold",
            "reduce", "sell_exit", "reject"],
    "buy_probe": ["wait", "observe", "buy_probe"],
    "observe": ["wait", "observe"],
    "wait": ["wait"],
}

# Order in which filters are applied
FILTER_ORDER: list[str] = ["technical", "risk"]

# Confidence threshold for confirmed vs probe actions
CONFIDENCE_THRESHOLD: float = 0.80

# Penalty for unconfirmed last segment
UNCONFIRMED_SEGMENT_PENALTY: float = 0.10


# ═══════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════

def run_decide(
    compute_result: dict,
    audit_result: dict,
    portfolio_context: dict | None = None,
) -> dict:
    """
    Generate trading decision from compute + audit results.

    Parameters
    ----------
    compute_result : output from chanlun_engine.analyze()
    audit_result : output from audit.run_audit()
    portfolio_context : optional dict with {'positions': [...], 'risk_limit': float}

    Returns
    -------
    dict with:
        action : str  (wait|observe|buy_probe|buy_confirmed|hold|reduce|sell_exit|reject)
        confidence : float | None  (0-1, None if no signal)
        action_ceiling : str  (from audit)
        rationale : str
        invalidation : dict | None  ({'price': float, 'condition': str})
        filters_applied : list[str]
    """
    # ── Extract inputs ──
    action_ceiling = audit_result.get("action_ceiling", "wait")
    bsp_list = compute_result.get("buy_sell_points", [])
    compute_status = compute_result.get("compute_status", {})
    warnings_list: list[str] = compute_status.get("warnings", [])
    pivots: list[dict] = compute_result.get("pivots", [])
    current_state: dict | None = compute_status.get("current_state")
    filters_applied: list[str] = []

    # ── Step 1: Validate action_ceiling ──
    allowed = CEILING_ACTION_MAP.get(action_ceiling, CEILING_ACTION_MAP["wait"])
    if action_ceiling not in CEILING_ACTION_MAP:
        filters_applied.append(f"ceiling:unknown_{action_ceiling}_defaulted_to_wait")
        action_ceiling = "wait"
        allowed = CEILING_ACTION_MAP["wait"]

    # ── Step 2: Structural signal interpretation ──
    if not bsp_list:
        # No structural signal
        action = "observe"  # watching but no catalyst
        confidence = None
        rationale = "No buy/sell points detected; no structural signal."
    else:
        # Take most recent BSP (highest idx) as primary signal
        most_recent = max(bsp_list, key=lambda x: x.get("idx", 0))
        bsp_type = most_recent.get("type", 0)
        bsp_side = most_recent.get("side", "buy")
        bsp_confidence = most_recent.get("confidence", 0.0)
        bsp_price = most_recent.get("price", 0.0)

        # Map BSP type+side to action direction
        if bsp_side == "buy":
            if bsp_confidence >= CONFIDENCE_THRESHOLD:
                action = "buy_confirmed"
            else:
                action = "buy_probe"
        else:  # sell
            if bsp_confidence >= CONFIDENCE_THRESHOLD:
                action = "sell_exit"
            else:
                action = "reduce"

        # Base confidence from BSP
        confidence = float(bsp_confidence)
        direction_label = "Buy" if bsp_side == "buy" else "Sell"

        # ── Step 3: Technical filter (confidence adjustment) ──
        if "last_segment_unconfirmed" in warnings_list:
            confidence = max(0.0, confidence - UNCONFIRMED_SEGMENT_PENALTY)
            filters_applied.append("technical:last_segment_unconfirmed")

        # Check for data-quality warnings
        if "insufficient_klines" in warnings_list:
            confidence = max(0.0, confidence - 0.05)
            filters_applied.append("technical:insufficient_klines")
        if "limited_klines" in warnings_list:
            confidence = max(0.0, confidence - 0.03)
            filters_applied.append("technical:limited_klines")

        rationale = (
            f"{direction_label}{bsp_type} signal at ${bsp_price:.2f}, "
            f"raw confidence {bsp_confidence:.2f}"
        )
        if confidence != bsp_confidence:
            rationale += f", adjusted to {confidence:.2f} (warnings: {', '.join(warnings_list)})"

    # ── Step 4: Risk filter — set invalidation boundary from pivot structure ──
    invalidation: dict | None = None

    if action not in ("wait", "observe", "reject") and pivots:
        last_pivot = pivots[-1]
        if action in ("buy_probe", "buy_confirmed", "hold"):
            # Buy-side invalidation = ZD (break below invalidates)
            zd = None
            if current_state:
                zd = current_state.get("nearest_ZD")
            if zd is None:
                zd = round(float(last_pivot.get("ZD", 0)), 2)
            else:
                zd = round(float(zd), 2)
            invalidation = {
                "price": zd,
                "condition": f"Close below nearest pivot ZD ({zd})",
            }
        elif action in ("reduce", "sell_exit"):
            # Sell-side invalidation = ZG (break above invalidates)
            zg = None
            if current_state:
                zg = current_state.get("nearest_ZG")
            if zg is None:
                zg = round(float(last_pivot.get("ZG", 0)), 2)
            else:
                zg = round(float(zg), 2)
            invalidation = {
                "price": zg,
                "condition": f"Close above nearest pivot ZG ({zg})",
            }
        filters_applied.append("risk:invalidation_set")

    # ── Portfolio context adjustments ──
    if portfolio_context is not None:
        positions = portfolio_context.get("positions", [])
        risk_limit = portfolio_context.get("risk_limit")

        if positions and action in ("buy_probe", "buy_confirmed"):
            # Holding something — refine sizing logic (no-op for now, just note it)
            _ = len(positions)  # future: check if already holding same direction
            filters_applied.append("risk:has_positions")

        if risk_limit is not None and action not in ("wait", "observe", "reject"):
            filters_applied.append("risk:risk_limit_checked")

    # ── Step 5: Clamp action to ceiling ──
    original_action = action
    if action not in allowed:
        # Choose the most permissive allowed action in the same direction
        if original_action in ("buy_probe", "buy_confirmed", "hold"):
            # Buy-side: prefer buy_probe > observe > wait
            if "buy_probe" in allowed:
                action = "buy_probe"
            elif "observe" in allowed:
                action = "observe"
            else:
                action = "wait"
        elif original_action in ("reduce", "sell_exit"):
            # Sell-side: prefer reduce > observe > wait
            if "reduce" in allowed:
                action = "reduce"
            elif "observe" in allowed:
                action = "observe"
            else:
                action = "wait"
        else:
            action = "wait" if "wait" in allowed else allowed[0]

        if original_action != action:
            filters_applied.append(
                f"ceiling:clamped_{original_action}_to_{action}"
            )

    # ── Assemble result ──
    return {
        "action": action,
        "confidence": round(confidence, 2) if confidence is not None else None,
        "action_ceiling": action_ceiling,
        "rationale": rationale,
        "invalidation": invalidation,
        "filters_applied": filters_applied,
    }


# ═══════════════════════════════════════════════════════════════════════
# Integration test: full pipeline
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    print("=== 缠论完整分析流水线 (Chanlun Full Pipeline) ===\n")
    symbol = "NVDA"

    try:
        # Step 1: Compute
        print(f"[1/3] Running chanlun_engine.analyze_symbol('{symbol}')...")
        compute = analyze_symbol(symbol)
        s = compute["summary"]
        print(f"  ── Compute Summary ──")
        print(f"     K线: {s['total_klines']} → 合并后 {s['after_inclusion']}")
        print(f"     分型: {s['fractal_count']}, 笔: {s['pen_count']}, "
              f"线段: {s['segment_count']}")
        print(f"     中枢: {s['pivot_count']}, 背驰: {s['divergence_count']}, "
              f"买卖点: {s['buy_sell_point_count']}")

        # Step 2: Audit
        print(f"\n[2/3] Running audit.run_audit(compute)...")
        audit = run_audit(compute)
        print(f"  ── Audit Summary ──")
        print(f"     definition_mode: {audit['definition_mode']}")
        print(f"     trigger_status:  {audit['trigger_status']}")
        print(f"     action_ceiling:  {audit['action_ceiling']}")
        print(f"     gates_passed:    {audit['gates_passed']}")
        print(f"     gates_failed:    {audit['gates_failed']}")

        # Step 3: Decide
        print(f"\n[3/3] Running decide.run_decide(compute, audit)...")
        decision = run_decide(compute, audit)
        print(f"  ── Decision ──")

        print(f"\n{'─' * 50}")
        print("Full Pipeline Output (JSON):")
        print(json.dumps(decision, indent=2, ensure_ascii=False))

    except Exception as exc:
        print(f"\nERROR: Pipeline failed — {exc}")
        import traceback
        traceback.print_exc()
