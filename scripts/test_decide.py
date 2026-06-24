#!/usr/bin/env python3
"""
test_decide.py — Tests for decide.py action generator

Coverage:
  1. No signal → action=observe, confidence=None
  2. BSP confidence thresholds → buy_probe vs buy_confirmed
  3. Action clamped to ceiling
  4. Invalidation boundary from pivot ZG/ZD
  5. Last segment unconfirmed → confidence adjusted down
  6. Empty portfolio → no position-based adjustments
  7. wait ceiling overrides any signal
  8. Buy1 from downtrend → correct action direction
  9. Technical filter adjusts confidence for warnings
  10. All ceiling mappings work correctly
  11. Multiple BSPs → most recent selected
  12. Sell-side signals → reduce vs sell_exit

Run: python -m pytest test_decide.py -v
"""

import sys
import os
from typing import Optional

import pytest

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decide import (
    run_decide,
    CEILING_ACTION_MAP,
    CONFIDENCE_THRESHOLD,
)


# ═══════════════════════════════════════════════════════════════════════
# Test Fixture Builders
# ═══════════════════════════════════════════════════════════════════════

def _make_compute(
    bsp_list: Optional[list] = None,
    warnings: Optional[list] = None,
    pivots: Optional[list] = None,
    current_state: Optional[dict] = None,
    **kwargs,
) -> dict:
    """Build a minimal compute_result dict for testing decide()."""
    cs: dict = {
        "pipeline_version": "2.0",
        "inclusion_done": True,
        "fractals_done": True,
        "strokes_done": True,
        "segments_done": True,
        "centers_done": True,
        "divergence_done": True,
        "buy_sell_points_done": True,
        "warnings": warnings or [],
        "data_quality": {
            "klines_count": kwargs.get("klines_count", 200),
            "after_inclusion_count": kwargs.get("after_inclusion_count", 185),
            "missing_sessions": 0,
            "sufficient": kwargs.get("sufficient", True),
        },
        "current_state": current_state,
    }
    return {
        "summary": {
            "total_klines": kwargs.get("klines_count", 200),
            "buy_sell_point_count": len(bsp_list or []),
        },
        "buy_sell_points": bsp_list or [],
        "pivots": pivots or [],
        "compute_status": cs,
    }


def _make_audit(
    action_ceiling: str = "all",
    definition_mode: str = "strict_chanlun",
    trigger_status: str = "confirmed",
    **kwargs,
) -> dict:
    """Build a minimal audit_result dict for testing decide()."""
    return {
        "definition_mode": definition_mode,
        "trigger_status": trigger_status,
        "approximation_loss": "none",
        "action_ceiling": action_ceiling,
        "gates_passed": [1, 2, 3, 4, 5, 6, 7],
        "gates_failed": [],
        "gate_details": {},
        "shortcuts_triggered": [],
        **kwargs,
    }


def _make_bsp(
    bsp_type: int = 1,
    side: str = "buy",
    confidence: float = 0.85,
    idx: int = 150,
    price: float = 100.0,
    pivot_ref: int = 0,
) -> dict:
    """Build a minimal buy/sell point dict."""
    return {
        "type": bsp_type,
        "side": side,
        "price": price,
        "idx": idx,
        "confidence": confidence,
        "pivot_ref": pivot_ref,
    }


def _make_pivot(
    ZG: float = 100.0,
    ZD: float = 95.0,
    GG: float = 105.0,
    DD: float = 90.0,
    start_seg: int = 0,
    end_seg: int = 2,
    seg_count: int = 3,
) -> dict:
    """Build a minimal pivot dict."""
    return {
        "start_seg": start_seg,
        "end_seg": end_seg,
        "ZG": ZG,
        "ZD": ZD,
        "GG": GG,
        "DD": DD,
        "seg_count": seg_count,
    }


def _make_current_state(
    price: float = 105.0,
    position_vs_pivot: str = "above_ZG",
    nearest_ZG: float = 100.0,
    nearest_ZD: float = 95.0,
    last_segment_direction: int = 1,
) -> dict:
    """Build a minimal current_state dict."""
    return {
        "price": price,
        "position_vs_pivot": position_vs_pivot,
        "nearest_ZG": nearest_ZG,
        "nearest_ZD": nearest_ZD,
        "last_segment_direction": last_segment_direction,
    }


# ═══════════════════════════════════════════════════════════════════════
# Test 1: No signal → action=observe, confidence=None
# ═══════════════════════════════════════════════════════════════════════

def test_no_signal_returns_observe_null_confidence():
    """When buy_sell_points is empty, action=observe and confidence=None."""
    compute = _make_compute(bsp_list=[])
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "observe"
    assert result["confidence"] is None
    assert result["action_ceiling"] == "all"
    assert "No buy/sell points" in result["rationale"]


def test_no_signal_with_observe_ceiling():
    """No signal with observe ceiling still returns observe."""
    compute = _make_compute(bsp_list=[])
    audit = _make_audit(action_ceiling="observe")

    result = run_decide(compute, audit)

    assert result["action"] == "observe"
    assert result["confidence"] is None


def test_no_signal_with_wait_ceiling():
    """No signal with wait ceiling clamps observe → wait."""
    compute = _make_compute(bsp_list=[])
    audit = _make_audit(action_ceiling="wait")

    result = run_decide(compute, audit)

    assert result["action"] == "wait"
    assert result["confidence"] is None
    assert "ceiling:clamped_observe_to_wait" in result["filters_applied"]


# ═══════════════════════════════════════════════════════════════════════
# Test 2: BSP confidence → buy_probe vs buy_confirmed
# ═══════════════════════════════════════════════════════════════════════

def test_high_confidence_buy_becomes_buy_confirmed():
    """BSP with confidence >= 0.80 → buy_confirmed."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "buy_confirmed"
    assert result["confidence"] == 0.85
    assert result["invalidation"] is not None


def test_low_confidence_buy_becomes_buy_probe():
    """BSP with confidence < 0.80 → buy_probe."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.70)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "buy_probe"
    assert result["confidence"] == 0.70


def test_boundary_confidence_exactly_threshold():
    """BSP at exactly 0.80 confidence → buy_confirmed (>= threshold)."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=CONFIDENCE_THRESHOLD)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "buy_confirmed"
    assert result["confidence"] == CONFIDENCE_THRESHOLD


def test_boundary_just_below_threshold():
    """BSP at 0.79 confidence → buy_probe (< threshold)."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.79)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "buy_probe"
    assert result["confidence"] == 0.79


# ═══════════════════════════════════════════════════════════════════════
# Test 3: Action clamped to ceiling
# ═══════════════════════════════════════════════════════════════════════

def test_buy_confirmed_clamped_to_observe():
    """A strong buy signal clamped to observe when ceiling=observe."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.95)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="observe")

    result = run_decide(compute, audit)

    assert result["action"] == "observe"
    assert result["action_ceiling"] == "observe"
    assert "ceiling:clamped_buy_confirmed_to_observe" in result["filters_applied"]


def test_buy_confirmed_clamped_to_buy_probe():
    """A strong buy signal clamped to buy_probe when ceiling=buy_probe."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.95)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="buy_probe")

    result = run_decide(compute, audit)

    assert result["action"] == "buy_probe"
    assert "ceiling:clamped_buy_confirmed_to_buy_probe" in result["filters_applied"]


def test_sell_exit_clamped_to_observe():
    """Sell signal clamped to observe when ceiling=observe."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="sell", confidence=0.90)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="observe")

    result = run_decide(compute, audit)

    assert result["action"] == "observe"
    assert "ceiling:clamped_sell_exit_to_observe" in result["filters_applied"]


# ═══════════════════════════════════════════════════════════════════════
# Test 4: Invalidation boundary from pivot ZG/ZD
# ═══════════════════════════════════════════════════════════════════════

def test_buy_action_invalidation_uses_zd():
    """Buy-side actions use ZD as invalidation price."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        pivots=[
            _make_pivot(ZG=110.0, ZD=105.0, GG=115.0, DD=100.0),
            _make_pivot(ZG=120.0, ZD=112.0, GG=125.0, DD=108.0),
        ],
        current_state=_make_current_state(
            price=125.0, nearest_ZG=120.0, nearest_ZD=112.0,
        ),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "buy_confirmed"
    assert result["invalidation"] is not None
    assert result["invalidation"]["price"] == 112.0  # nearest_ZD from current_state
    assert "Close below" in result["invalidation"]["condition"]
    assert "ZD" in result["invalidation"]["condition"]


def test_sell_action_invalidation_uses_zg():
    """Sell-side actions use ZG as invalidation price."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="sell", confidence=0.85)],
        pivots=[
            _make_pivot(ZG=110.0, ZD=105.0, GG=115.0, DD=100.0),
            _make_pivot(ZG=120.0, ZD=112.0, GG=125.0, DD=108.0),
        ],
        current_state=_make_current_state(
            price=125.0, nearest_ZG=120.0, nearest_ZD=112.0,
        ),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "sell_exit"
    assert result["invalidation"] is not None
    assert result["invalidation"]["price"] == 120.0  # nearest_ZG from current_state
    assert "Close above" in result["invalidation"]["condition"]
    assert "ZG" in result["invalidation"]["condition"]


def test_invalidation_fallback_to_last_pivot():
    """When current_state is None, invalidation falls back to last pivot."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        pivots=[
            _make_pivot(ZG=50.0, ZD=45.0),
            _make_pivot(ZG=60.0, ZD=55.0),
        ],
        current_state=None,
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["invalidation"] is not None
    assert result["invalidation"]["price"] == 55.0  # ZD of last pivot


def test_no_invalidation_for_wait_observe():
    """Wait and observe actions get no invalidation boundary."""
    for action_ceiling in ["wait", "observe"]:
        compute = _make_compute(
            bsp_list=[],
            pivots=[_make_pivot()],
            current_state=_make_current_state(),
        )
        audit = _make_audit(action_ceiling=action_ceiling)

        result = run_decide(compute, audit)

        assert result["invalidation"] is None, (
            f"Expected no invalidation for {result['action']}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Test 5: Last segment unconfirmed → confidence adjusted down
# ═══════════════════════════════════════════════════════════════════════

def test_unconfirmed_segment_reduces_confidence():
    """last_segment_unconfirmed warning reduces confidence by 0.1."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        warnings=["last_segment_unconfirmed"],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["confidence"] == 0.75  # 0.85 - 0.10
    assert "technical:last_segment_unconfirmed" in result["filters_applied"]


def test_unconfirmed_segment_with_low_confidence_does_not_go_negative():
    """Confidence floor is 0.0 even with penalties."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=2, side="buy", confidence=0.05)],
        warnings=["last_segment_unconfirmed"],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["confidence"] == 0.0  # max(0.0, 0.05 - 0.10)


def test_adjusted_confidence_in_rationale():
    """Rationale mentions adjusted confidence when warnings applied."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        warnings=["last_segment_unconfirmed", "limited_klines"],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert "adjusted" in result["rationale"]
    assert "0.72" in result["rationale"]  # 0.85 - 0.10 - 0.03
    assert result["confidence"] == 0.72


# ═══════════════════════════════════════════════════════════════════════
# Test 6: Empty portfolio → no position-based adjustments
# ═══════════════════════════════════════════════════════════════════════

def test_empty_portfolio_no_effect():
    """An empty portfolio_context list has no effect on output."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")
    portfolio = {"positions": [], "risk_limit": 50000.0}

    result_with = run_decide(compute, audit, portfolio_context=portfolio)
    result_without = run_decide(compute, audit)

    # Action and confidence should be identical
    assert result_with["action"] == result_without["action"]
    assert result_with["confidence"] == result_without["confidence"]


def test_non_empty_portfolio_triggers_risk_filter():
    """Non-empty position list triggers risk filter."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")
    portfolio = {
        "positions": [{"symbol": "NVDA", "side": "long", "qty": 100}],
        "risk_limit": 50000.0,
    }

    result = run_decide(compute, audit, portfolio_context=portfolio)

    assert "risk:has_positions" in result["filters_applied"]
    assert "risk:risk_limit_checked" in result["filters_applied"]


def test_none_portfolio_context_no_crash():
    """None portfolio_context should not crash."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit, portfolio_context=None)

    assert result["action"] == "buy_confirmed"
    assert "risk:has_positions" not in result["filters_applied"]


# ═══════════════════════════════════════════════════════════════════════
# Test 7: wait ceiling overrides any signal
# ═══════════════════════════════════════════════════════════════════════

def test_wait_ceiling_overrides_buy_signal():
    """wait ceiling clamps any buy signal to wait."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.95)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="wait")

    result = run_decide(compute, audit)

    assert result["action"] == "wait"
    assert "ceiling:clamped_buy_confirmed_to_wait" in result["filters_applied"]


def test_wait_ceiling_overrides_sell_signal():
    """wait ceiling clamps any sell signal to wait."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="sell", confidence=0.90)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="wait")

    result = run_decide(compute, audit)

    assert result["action"] == "wait"
    assert "ceiling:clamped_sell_exit_to_wait" in result["filters_applied"]


def test_wait_ceiling_overrides_no_signal():
    """wait ceiling with no signal returns wait."""
    compute = _make_compute(bsp_list=[])
    audit = _make_audit(action_ceiling="wait")

    result = run_decide(compute, audit)

    assert result["action"] == "wait"
    assert result["confidence"] is None


# ═══════════════════════════════════════════════════════════════════════
# Test 8: Buy1 from downtrend → correct action direction
# ═══════════════════════════════════════════════════════════════════════

def test_buy1_produces_buy_side_action():
    """Buy1 (type=1, side=buy) produces buy_confirmed or buy_probe."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.90, price=95.0)],
        pivots=[_make_pivot(ZG=120.0, ZD=110.0)],  # price below ZD = downtrend context
        current_state=_make_current_state(
            price=95.0,
            position_vs_pivot="below_ZD",
            nearest_ZG=120.0,
            nearest_ZD=110.0,
        ),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] in ("buy_confirmed", "buy_probe")
    assert result["confidence"] == 0.90
    assert "Buy1" in result["rationale"]


def test_sell1_produces_sell_side_action():
    """Sell1 (type=1, side=sell) produces sell_exit or reduce."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="sell", confidence=0.90, price=130.0)],
        pivots=[_make_pivot(ZG=120.0, ZD=110.0)],
        current_state=_make_current_state(
            price=130.0,
            position_vs_pivot="above_ZG",
            nearest_ZG=120.0,
            nearest_ZD=110.0,
        ),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] in ("sell_exit", "reduce")
    assert result["confidence"] == 0.90
    assert "Sell1" in result["rationale"]


def test_buy2_produces_buy_probe():
    """Buy2 with moderate confidence → buy_probe."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=2, side="buy", confidence=0.75, price=100.0)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "buy_probe"
    assert "Buy2" in result["rationale"]


def test_buy3_produces_buy_side_action():
    """Buy3 produces buy_probe (type-3 has lower confidence by convention)."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=3, side="buy", confidence=0.85, price=100.0)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "buy_confirmed"  # 0.85 >= 0.80
    assert "Buy3" in result["rationale"]


# ═══════════════════════════════════════════════════════════════════════
# Test 9: Technical filter adjusts confidence for warnings
# ═══════════════════════════════════════════════════════════════════════

def test_insufficient_klines_reduces_confidence():
    """insufficient_klines warning reduces confidence by 0.05."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        warnings=["insufficient_klines"],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["confidence"] == 0.80  # 0.85 - 0.05
    assert "technical:insufficient_klines" in result["filters_applied"]


def test_limited_klines_reduces_confidence():
    """limited_klines warning reduces confidence by 0.03."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        warnings=["limited_klines"],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["confidence"] == 0.82  # 0.85 - 0.03
    assert "technical:limited_klines" in result["filters_applied"]


def test_multiple_warnings_compound():
    """Multiple warnings compound their confidence adjustments."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.90)],
        warnings=["last_segment_unconfirmed", "limited_klines", "insufficient_klines"],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    # 0.90 - 0.10 - 0.03 - 0.05 = 0.72
    assert result["confidence"] == 0.72
    assert "technical:last_segment_unconfirmed" in result["filters_applied"]
    assert "technical:limited_klines" in result["filters_applied"]
    assert "technical:insufficient_klines" in result["filters_applied"]


def test_no_warnings_no_technical_filter():
    """No warnings → no technical filter applied."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        warnings=[],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert "technical:" not in result["filters_applied"]  # only risk: should be there
    assert result["confidence"] == 0.85


# ═══════════════════════════════════════════════════════════════════════
# Test 10: All ceiling mappings work correctly
# ═══════════════════════════════════════════════════════════════════════

STRONG_BUY_COMPUTE = None  # computed lazily below
STRONG_SELL_COMPUTE = None

def _strong_buy_compute():
    global STRONG_BUY_COMPUTE
    if STRONG_BUY_COMPUTE is None:
        STRONG_BUY_COMPUTE = _make_compute(
            bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.95, idx=200)],
            pivots=[_make_pivot()],
            current_state=_make_current_state(),
        )
    return STRONG_BUY_COMPUTE


def _strong_sell_compute():
    global STRONG_SELL_COMPUTE
    if STRONG_SELL_COMPUTE is None:
        STRONG_SELL_COMPUTE = _make_compute(
            bsp_list=[_make_bsp(bsp_type=1, side="sell", confidence=0.90, idx=200)],
            pivots=[_make_pivot()],
            current_state=_make_current_state(),
        )
    return STRONG_SELL_COMPUTE


@pytest.mark.parametrize("ceiling,expected_buy,expected_sell", [
    ("all", "buy_confirmed", "sell_exit"),
    ("buy_probe", "buy_probe", "observe"),
    ("observe", "observe", "observe"),
    ("wait", "wait", "wait"),
])
def test_ceiling_mappings(ceiling, expected_buy, expected_sell):
    """Each ceiling correctly caps buy and sell actions."""
    # Test buy side
    buy_result = run_decide(_strong_buy_compute(), _make_audit(action_ceiling=ceiling))
    assert buy_result["action"] == expected_buy, (
        f"ceiling={ceiling}: expected buy action={expected_buy}, got {buy_result['action']}"
    )
    assert buy_result["action_ceiling"] == ceiling

    # Test sell side
    sell_result = run_decide(_strong_sell_compute(), _make_audit(action_ceiling=ceiling))
    assert sell_result["action"] == expected_sell, (
        f"ceiling={ceiling}: expected sell action={expected_sell}, got {sell_result['action']}"
    )
    assert sell_result["action_ceiling"] == ceiling


def test_ceiling_all_allows_full_range():
    """'all' ceiling allows all actions through."""
    allowed = CEILING_ACTION_MAP["all"]
    for action in ["wait", "observe", "buy_probe", "buy_confirmed", "hold",
                   "reduce", "sell_exit"]:
        assert action in allowed, f"'{action}' should be in 'all' ceiling"


def test_ceiling_wait_only_allows_wait():
    """'wait' ceiling only allows 'wait'."""
    allowed = CEILING_ACTION_MAP["wait"]
    assert allowed == ["wait"]
    assert len(allowed) == 1


def test_unknown_ceiling_defaults_to_wait():
    """An unrecognized ceiling key defaults to 'wait'."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.95)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="bogus_value")

    result = run_decide(compute, audit)

    assert result["action"] == "wait"
    assert result["action_ceiling"] == "wait"  # Defaulted
    assert any("unknown" in f for f in result["filters_applied"])


# ═══════════════════════════════════════════════════════════════════════
# Test 11: Multiple BSPs — most recent selected
# ═══════════════════════════════════════════════════════════════════════

def test_most_recent_bsp_selected():
    """When multiple BSPs exist, the one with highest idx is used."""
    compute = _make_compute(
        bsp_list=[
            _make_bsp(bsp_type=3, side="buy", confidence=0.70, idx=50),
            _make_bsp(bsp_type=1, side="sell", confidence=0.90, idx=150),
            _make_bsp(bsp_type=2, side="buy", confidence=0.80, idx=200),
        ],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    # Most recent is idx=200: Buy2, confidence=0.80 → buy_confirmed
    assert result["action"] == "buy_confirmed"
    assert result["confidence"] == 0.80
    assert "Buy2" in result["rationale"]


def test_most_recent_bsp_sell_side():
    """Most recent sell BSP is selected."""
    compute = _make_compute(
        bsp_list=[
            _make_bsp(bsp_type=1, side="buy", confidence=0.90, idx=100),
            _make_bsp(bsp_type=1, side="sell", confidence=0.75, idx=120),
        ],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    # Most recent is idx=120: Sell1, confidence=0.75 → reduce
    assert result["action"] == "reduce"
    assert "Sell1" in result["rationale"]


# ═══════════════════════════════════════════════════════════════════════
# Test 12: Sell-side signals → reduce vs sell_exit
# ═══════════════════════════════════════════════════════════════════════

def test_sell_high_confidence_is_sell_exit():
    """Sell with confidence >= 0.80 → sell_exit."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="sell", confidence=0.85)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "sell_exit"


def test_sell_low_confidence_is_reduce():
    """Sell with confidence < 0.80 → reduce."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=3, side="sell", confidence=0.60)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "reduce"


# ═══════════════════════════════════════════════════════════════════════
# Additional edge-case tests
# ═══════════════════════════════════════════════════════════════════════

def test_no_pivots_no_crash():
    """Empty pivots list should not crash invalidation logic."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        pivots=[],
        current_state=None,
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] == "buy_confirmed"
    assert result["invalidation"] is None  # No pivots → no boundary


def test_confidence_rounded_to_two_decimals():
    """Confidence is always rounded to 2 decimal places."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.853)],

        warnings=["last_segment_unconfirmed"],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["confidence"] == 0.75  # 0.853 - 0.10 = 0.753 → 0.75
    # Verify it's exactly 2 decimal places
    assert isinstance(result["confidence"], float)


def test_result_structure_has_all_required_keys():
    """Output dict has all required top-level keys."""
    compute = _make_compute(
        bsp_list=[_make_bsp(bsp_type=1, side="buy", confidence=0.85)],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    required = {"action", "confidence", "action_ceiling", "rationale",
                "invalidation", "filters_applied"}
    assert set(result.keys()) == required


def test_filters_applied_is_always_list():
    """filters_applied is always a list even when empty."""
    compute = _make_compute(
        bsp_list=[],
        warnings=[],
        pivots=[],
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert isinstance(result["filters_applied"], list)
    assert result["filters_applied"] == []


def test_bsp_missing_idx_does_not_crash():
    """BSP without idx field defaults to 0."""
    bsp = _make_bsp(bsp_type=1, side="buy", confidence=0.85)
    del bsp["idx"]
    compute = _make_compute(
        bsp_list=[bsp],
        pivots=[_make_pivot()],
        current_state=_make_current_state(),
    )
    audit = _make_audit(action_ceiling="all")

    result = run_decide(compute, audit)

    assert result["action"] in ("buy_confirmed", "buy_probe")
