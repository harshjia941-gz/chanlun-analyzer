#!/usr/bin/env python3
"""
audit.py — 8-Gate Audit Module for chanlun-analyzer

Executes the strict 8-gate audit on compute output.
Fast-path shortcuts short-circuit unnecessary gate evaluation.

Interface: run_audit(compute_result, trade_level, confirm_level, trigger_level) → dict
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

# ── Valid levels (index = coarseness rank, higher index = coarser) ──
# F = 分钟级别 (e.g. 60F = 60分钟线)
VALID_LEVELS = ["1F", "5F", "15F", "30F", "60F", "D", "W", "M"]

# Alias normalization (common user input → canonical level)
LEVEL_ALIASES = {
    "60m": "60F", "30m": "30F", "15m": "15F", "5m": "5F", "1m": "1F",
    "1h": "60F", "4h": "60F",  # 4h maps to 60F (closest available)
    "daily": "D", "weekly": "W", "monthly": "M",
}


@dataclass
class GateResult:
    gate: int
    passed: bool
    definition_mode: str | None = None
    approximation_loss: str | None = None
    rationale: str = ""


def _level_index(level: str) -> int:
    """Return index in VALID_LEVELS, normalizing aliases first. Returns -1 if invalid."""
    normalized = LEVEL_ALIASES.get(level, level)
    try:
        return VALID_LEVELS.index(normalized)
    except ValueError:
        return -1


# ═══════════════════════════════════════════════════════════════════════
# GATE 1: Level Gate
# ═══════════════════════════════════════════════════════════════════════

def _gate_1_level(trade: str, confirm: str, trigger: str) -> GateResult:
    """Verify all three levels are valid and hierarchically consistent."""
    ti = _level_index(trade)
    ci = _level_index(confirm)
    tri = _level_index(trigger)

    if ti == -1 or ci == -1 or tri == -1:
        invalid = [l for l, i in [(trade, ti), (confirm, ci), (trigger, tri)] if i == -1]
        return GateResult(1, False, "untradable_unclear", "high",
                          f"Invalid level(s): {invalid}")

    # confirm_level (coarsest) > trade_level > trigger_level (finest)
    if not (ci > ti > tri):
        return GateResult(1, False, "untradable_unclear", "high",
                          f"Level hierarchy violated: confirm={confirm}({ci}) > trade={trade}({ti}) > trigger={trigger}({tri})")

    return GateResult(1, True, rationale="All levels valid and hierarchical")


# ═══════════════════════════════════════════════════════════════════════
# GATE 2: Structure Gate
# ═══════════════════════════════════════════════════════════════════════

CRITICAL_WARNINGS = {"insufficient_klines", "too_few_pens", "no_pivots_found"}

def _gate_2_structure(cs: dict) -> GateResult:
    """Verify compute pipeline completed and no critical warnings."""
    done_flags = {k: cs.get(k) for k in
                  ["inclusion_done", "fractals_done", "strokes_done",
                   "segments_done", "centers_done"]}
    warnings = set(cs.get("warnings", []))

    # Critical warnings → proxy_research
    if warnings & CRITICAL_WARNINGS:
        return GateResult(2, False, "proxy_research", "high",
                          f"Critical warnings: {warnings & CRITICAL_WARNINGS}")

    # Steps 1-3 done but 4 or 5 incomplete → structure_proxy
    if done_flags["inclusion_done"] and done_flags["fractals_done"] and done_flags["strokes_done"]:
        if not done_flags.get("segments_done") or not done_flags.get("centers_done"):
            return GateResult(2, False, "structure_proxy", "low",
                              "Steps 1-3 done but segments/centers incomplete")

    # All done
    if all(done_flags.values()):
        return GateResult(2, True, rationale="All structure steps complete, no critical warnings")

    # Steps 1-2 incomplete
    return GateResult(2, False, "proxy_research", "high", "Fundamental steps incomplete")


# ═══════════════════════════════════════════════════════════════════════
# Fast-Path Shortcuts
# ═══════════════════════════════════════════════════════════════════════

def _check_fast_path(compute_result: dict) -> dict | None:
    """Check for fast-path shortcuts. Returns audit dict if triggered, else None."""
    summary = compute_result.get("summary", {})
    pivots = compute_result.get("pivots", [])
    bsp_count = summary.get("buy_sell_point_count", 0)
    div_count = summary.get("divergence_count", 0)
    pivot_count = summary.get("pivot_count", len(pivots))
    cs = compute_result.get("compute_status", {})

    shortcuts = []

    # Shortcut 1: No signal at all → skip GATE 4-7, ceiling=observe
    if div_count == 0 and bsp_count == 0:
        shortcuts.append("no_signal_fast_path")
        gate_details = {}
        # GATE 4,5,7: auto-pass (nothing to validate)
        # GATE 6: marked as failed because trigger data is missing
        for g in (4, 5, 7):
            gate_details[f"gate_{g}"] = {"passed": True, "rationale": "fast-path: auto-pass (no signal to validate)", "fast_path": True}
        return {
            "definition_mode": _determine_mode(cs, []),
            "trigger_status": "missing",
            "approximation_loss": "medium",
            "action_ceiling": "observe",
            "gates_passed": [1, 2, 4, 5, 7],
            "gates_failed": [6],
            "gate_details": gate_details,
            "shortcuts_triggered": shortcuts,
            "fast_path_rationale": "Structure exists but provides no actionable signal (0 divergence, 0 buy/sell points). Trigger gate failed due to missing lower-level data."
        }

    # Shortcut 2: No pivots → structure_proxy
    if pivot_count == 0:
        shortcuts.append("no_pivot_fast_path")
        return {
            "definition_mode": "structure_proxy",
            "trigger_status": "missing",
            "approximation_loss": "high",
            "action_ceiling": "observe",
            "gates_passed": [1, 2],
            "gates_failed": [3, 4, 5, 6, 7],
            "gate_details": {},
            "shortcuts_triggered": shortcuts,
            "fast_path_rationale": "No center formed; structure incomplete."
        }

    return None


def _determine_mode(cs: dict, failed_gates: list[int]) -> str:
    """Determine definition_mode from compute_status and failed gates."""
    # Start from strict_chanlun, degrade by worst gate failure
    warnings = set(cs.get("warnings", []))
    if warnings & CRITICAL_WARNINGS:
        return "proxy_research"
    return "strict_chanlun"


# ═══════════════════════════════════════════════════════════════════════
# GATE 3: Type Gate
# ═══════════════════════════════════════════════════════════════════════

def _gate_3_type(compute_result: dict) -> GateResult:
    """Classify current market state relative to latest pivot."""
    pivots = compute_result.get("pivots", [])
    if not pivots:
        return GateResult(3, False, "structure_proxy", "medium", "No pivots to classify")

    latest_pv = pivots[-1]
    current_state = compute_result.get("compute_status", {}).get("current_state")
    if not current_state:
        # Fallback: read from segments
        segments = compute_result.get("segments", [])
        # Use data_quality kl count for rough price
        dq = compute_result.get("compute_status", {}).get("data_quality", {})
        return GateResult(3, False, "untradable_unclear", "medium",
                          "Cannot determine current price position")

    pos = current_state.get("position_vs_pivot", "untradable_unclear")
    state_map = {
        "inside_center": "center_oscillation",
        "above_ZG": "center_breakout",
        "below_ZD": "center_breakout",
    }
    state = state_map.get(pos, "untradable_unclear")

    if state == "untradable_unclear":
        return GateResult(3, False, "untradable_unclear", "medium",
                          f"Unclassifiable position: {pos}")

    return GateResult(3, True, rationale=f"State classified as: {state} (position: {pos})")


# ═══════════════════════════════════════════════════════════════════════
# GATE 4: Comparison Gate
# ═══════════════════════════════════════════════════════════════════════

def _gate_4_comparison(compute_result: dict) -> GateResult:
    """Validate divergence entries against pivot structure."""
    divergence = compute_result.get("divergence", [])
    pivots = compute_result.get("pivots", [])

    # Fast-path: no divergence and single pivot → auto-pass
    if len(divergence) == 0:
        if len(pivots) <= 1:
            return GateResult(4, True, rationale="No divergence entries; single pivot, comparison N/A")
        return GateResult(4, True, rationale="No divergence entries to validate")

    # Validate each divergence entry
    for d in divergence:
        pivot_idx = d.get("pivot_idx", -1)
        if pivot_idx < 0 or pivot_idx >= len(pivots):
            return GateResult(4, False, "indicator_proxy", "high",
                              f"Divergence references invalid pivot_idx={pivot_idx}")

    return GateResult(4, True, rationale=f"All {len(divergence)} divergence entries validated")


# ═══════════════════════════════════════════════════════════════════════
# GATE 5: Buy/Sell Point Gate
# ═══════════════════════════════════════════════════════════════════════

BSP_REQUIRED_KEYS = {"type", "side", "price", "confidence", "pivot_ref"}

def _gate_5_bsp(compute_result: dict) -> GateResult:
    """Validate buy/sell point structure."""
    bsp_list = compute_result.get("buy_sell_points", [])

    # No BSP → auto-pass
    if len(bsp_list) == 0:
        return GateResult(5, True, rationale="No buy/sell points to validate")

    # Validate each BSP has required keys
    for bp in bsp_list:
        missing = BSP_REQUIRED_KEYS - set(bp.keys())
        if missing:
            return GateResult(5, False, "indicator_proxy", "high",
                              f"BSP missing keys: {missing}")

        # Verify pivot_ref
        pivot_ref = bp.get("pivot_ref", -1)
        pivots = compute_result.get("pivots", [])
        if isinstance(pivot_ref, int) and (pivot_ref < 0 or pivot_ref >= len(pivots)):
            return GateResult(5, False, "indicator_proxy", "high",
                              f"BSP references invalid pivot_ref={pivot_ref}")

    return GateResult(5, True, rationale=f"All {len(bsp_list)} buy/sell points structurally valid")


# ═══════════════════════════════════════════════════════════════════════
# GATE 6: Trigger Gate
# ═══════════════════════════════════════════════════════════════════════

def _gate_6_trigger(has_lower_level_data: bool = False) -> GateResult:
    """Verify lower-level trigger confirmation exists."""
    if has_lower_level_data:
        return GateResult(6, True, rationale="Lower-level data available")

    return GateResult(6, False, rationale="No lower-level trigger data available",
                      approximation_loss="medium")


# ═══════════════════════════════════════════════════════════════════════
# GATE 7: Risk Gate
# ═══════════════════════════════════════════════════════════════════════

def _gate_7_risk(compute_result: dict) -> GateResult:
    """Verify every buy/sell candidate has invalidation boundary."""
    bsp_list = compute_result.get("buy_sell_points", [])

    if len(bsp_list) == 0:
        return GateResult(7, True, rationale="No positions to validate risk for")

    for bp in bsp_list:
        if "invalidation" not in bp:
            return GateResult(7, False, rationale="BSP missing invalidation boundary")

    return GateResult(7, True, rationale=f"All {len(bsp_list)} positions have invalidation boundaries")


# ═══════════════════════════════════════════════════════════════════════
# GATE 8: Downgrade Gate
# ═══════════════════════════════════════════════════════════════════════

ACTION_CEILING_TABLE = {
    ("strict_chanlun", "confirmed"): "all",
    ("strict_chanlun", "pending"): "observe",
    ("strict_chanlun", "missing"): "observe",
    ("structure_proxy", "confirmed"): "buy_probe",
    ("structure_proxy", "pending"): "observe",
    ("structure_proxy", "missing"): "observe",
    ("signal_proxy", "confirmed"): "buy_probe",
    ("signal_proxy", "pending"): "observe",
    ("signal_proxy", "missing"): "observe",
    ("indicator_proxy", "confirmed"): "observe",
    ("indicator_proxy", "pending"): "observe",
    ("indicator_proxy", "missing"): "observe",
    ("untradable_unclear", "confirmed"): "wait",
    ("untradable_unclear", "pending"): "wait",
    ("untradable_unclear", "missing"): "wait",
    ("proxy_research", "confirmed"): "wait",
    ("proxy_research", "pending"): "wait",
    ("proxy_research", "missing"): "wait",
}


def _gate_8_downgrade(gate_results: list[GateResult],
                      compute_result: dict,
                      trigger_status: str) -> dict:
    """Aggregate all gate results into final audit output."""
    # Determine worst mode
    mode_priority = ["strict_chanlun", "structure_proxy", "signal_proxy",
                     "indicator_proxy", "untradable_unclear", "proxy_research"]
    worst_mode = "strict_chanlun"
    for mode in mode_priority:
        for gr in gate_results:
            if gr.definition_mode and gr.definition_mode == mode:
                worst_mode = mode

    # Determine approximation loss
    losses = [gr.approximation_loss for gr in gate_results if gr.approximation_loss]
    # trigger_status affects loss: missing → at least medium
    if trigger_status == "missing":
        losses.append("medium")
    loss_priority = ["none", "low", "medium", "high"]
    worst_loss = "none"
    for l in loss_priority:
        if l in losses:
            worst_loss = l

    # Action ceiling
    ceiling = ACTION_CEILING_TABLE.get((worst_mode, trigger_status), "observe")

    return {
        "definition_mode": worst_mode,
        "trigger_status": trigger_status,
        "approximation_loss": worst_loss,
        "action_ceiling": ceiling,
    }


# ═══════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════

def run_audit(
    compute_result: dict,
    trade_level: str = "D",
    confirm_level: str = "W",
    trigger_level: str = "60F",
    has_lower_level_data: bool = False,
) -> dict:
    """
    Execute 8-gate audit on compute output.

    Parameters
    ----------
    compute_result : output dict from chanlun_engine.analyze()
    trade_level : operating timeframe (1F/5F/15F/30F/60F/D/W/M)
    confirm_level : confirming timeframe (coarser than trade)
    trigger_level : entry timing timeframe (finer than trade)
    has_lower_level_data : whether lower-level compute data exists for GATE 6

    Returns
    -------
    dict with keys:
        definition_mode, trigger_status, approximation_loss,
        action_ceiling, gates_passed, gates_failed, gate_details, shortcuts_triggered
    """
    gate_results: list[GateResult] = []
    gate_details: dict[str, dict] = {}

    # ── GATE 1 ──
    r1 = _gate_1_level(trade_level, confirm_level, trigger_level)
    gate_results.append(r1)
    gate_details["gate_1"] = {"passed": r1.passed, "rationale": r1.rationale}
    if not r1.passed:
        return _build_output(gate_results, gate_details, [], compute_result, "missing")

    # ── GATE 2 ──
    cs = compute_result.get("compute_status", {})
    r2 = _gate_2_structure(cs)
    gate_results.append(r2)
    gate_details["gate_2"] = {"passed": r2.passed, "rationale": r2.rationale}
    if not r2.passed:
        mode = r2.definition_mode or "proxy_research"
        loss = r2.approximation_loss or "high"
        gate_details["gate_2"]["definition_mode"] = mode
        gate_details["gate_2"]["approximation_loss"] = loss

    # ── FAST-PATH CHECK ──
    fast_path = _check_fast_path(compute_result)
    if fast_path is not None:
        fp_result = fast_path
        # Merge gate 1-2 results into fast-path output
        fp_result["gate_details"]["gate_1"] = gate_details["gate_1"]
        fp_result["gate_details"]["gate_2"] = gate_details["gate_2"]
        # GATE 8 still needs to run for final mode determination
        downgrade = _gate_8_downgrade(gate_results, compute_result, fp_result["trigger_status"])
        fp_result.update(downgrade)
        # Re-compute gates_failed if trigger is not confirmed
        if downgrade["trigger_status"] == "missing":
            fp_result["gates_failed"] = list(set(fp_result.get("gates_failed", []) + [6]))
            if 6 in fp_result["gates_passed"]:
                fp_result["gates_passed"].remove(6)
        return fp_result

    # ── GATE 3 ──
    r3 = _gate_3_type(compute_result)
    gate_results.append(r3)
    gate_details["gate_3"] = {"passed": r3.passed, "rationale": r3.rationale}
    if not r3.passed:
        gate_details["gate_3"]["definition_mode"] = r3.definition_mode

    # ── GATE 4 ──
    r4 = _gate_4_comparison(compute_result)
    gate_results.append(r4)
    gate_details["gate_4"] = {"passed": r4.passed, "rationale": r4.rationale}

    # ── GATE 5 ──
    r5 = _gate_5_bsp(compute_result)
    gate_results.append(r5)
    gate_details["gate_5"] = {"passed": r5.passed, "rationale": r5.rationale}

    # ── GATE 6 ──
    r6 = _gate_6_trigger(has_lower_level_data)
    gate_results.append(r6)
    gate_details["gate_6"] = {"passed": r6.passed, "rationale": r6.rationale}
    trigger_status = "confirmed" if r6.passed else "missing"
    if not r6.passed:
        gate_details["gate_6"]["approximation_loss"] = r6.approximation_loss

    # ── GATE 7 ──
    r7 = _gate_7_risk(compute_result)
    gate_results.append(r7)
    gate_details["gate_7"] = {"passed": r7.passed, "rationale": r7.rationale}

    # ── GATE 8 ──
    downgrade = _gate_8_downgrade(gate_results, compute_result, trigger_status)

    return _build_output(gate_results, gate_details, [],
                          compute_result, trigger_status, downgrade)


def _build_output(gate_results: list[GateResult],
                  gate_details: dict,
                  shortcuts: list[str],
                  compute_result: dict,
                  trigger_status: str,
                  downgrade: dict | None = None) -> dict:
    """Build final audit output dict."""
    passed = [gr.gate for gr in gate_results if gr.passed]
    failed = [gr.gate for gr in gate_results if not gr.passed]

    if downgrade is None:
        downgrade = _gate_8_downgrade(gate_results, compute_result, trigger_status)

    return {
        "definition_mode": downgrade["definition_mode"],
        "trigger_status": downgrade["trigger_status"],
        "approximation_loss": downgrade["approximation_loss"],
        "action_ceiling": downgrade["action_ceiling"],
        "gates_passed": passed,
        "gates_failed": failed,
        "gate_details": gate_details,
        "shortcuts_triggered": shortcuts,
    }


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python audit.py <compute_result.json> [trade_level] [confirm_level] [trigger_level]")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    result = run_audit(
        data,
        trade_level=sys.argv[2] if len(sys.argv) > 2 else "D",
        confirm_level=sys.argv[3] if len(sys.argv) > 3 else "W",
        trigger_level=sys.argv[4] if len(sys.argv) > 4 else "60m",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
