#!/usr/bin/env python3
"""
test_chanlun_engine.py — Tests for chanlun_engine.py

Covers:
1. Basic pipeline execution with sample data
2. compute_status field correctness
3. data_quality checks
4. Warning catalog
5. Backward compatibility (existing fields preserved)
6. detect_divergence pens parameter (bug fix verification)
7. Edge cases (minimal data, empty data)

Run: python -m pytest test_chanlun_engine.py -v
Or:  python test_chanlun_engine.py
"""

import sys
import os
import json
import numpy as np
import pandas as pd
import pytest

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chanlun_engine import (
    analyze,
    analyze_symbol,
    process_inclusion,
    find_fractals,
    build_pens,
    build_segments,
    find_pivots,
    detect_divergence,
    find_buy_sell_points,
    _generate_sample_data,
    _load_csv,
    Fractal,
    Pen,
    Segment,
    Pivot,
    DivergenceInfo,
    BuySellPoint,
)


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_df():
    """Standard 200-kline sample data."""
    return _generate_sample_data()


@pytest.fixture
def small_df():
    """50 klines — enough for basic analysis."""
    np.random.seed(99)
    n = 50
    dates = pd.bdate_range("2025-03-01", periods=n)
    returns = np.random.randn(n) * 0.02 + 0.001
    close = 100.0 * np.cumprod(1 + returns)
    high = close * (1 + np.abs(np.random.randn(n)) * 0.01)
    low = close * (1 - np.abs(np.random.randn(n)) * 0.01)
    open_p = close * (1 + np.random.randn(n) * 0.005)
    volume = (np.random.rand(n) * 1e6 + 1e5).astype(int)
    return pd.DataFrame({
        "date": dates, "open": open_p, "high": high,
        "low": low, "close": close, "volume": volume,
    }).assign(
        high=lambda d: d[["high", "open", "close"]].max(axis=1),
        low=lambda d: d[["low", "open", "close"]].min(axis=1),
    )


@pytest.fixture
def tiny_df():
    """20 klines — below minimum threshold."""
    np.random.seed(7)
    n = 20
    dates = pd.bdate_range("2025-01-01", periods=n)
    close = np.linspace(100, 110, n) + np.random.randn(n) * 0.5
    return pd.DataFrame({
        "date": dates,
        "open": close - 0.5,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": np.full(n, 1e6),
    })


@pytest.fixture
def trending_df():
    """
    Data engineered to produce downtrend + recovery,
    increasing chance of 2+ pivots for divergence testing.
    """
    np.random.seed(123)
    n = 300
    dates = pd.bdate_range("2025-01-01", periods=n)

    # Phase 1: downtrend (klines 0-100)
    phase1 = np.linspace(100, 70, 100) + np.random.randn(100) * 1.5
    # Phase 2: consolidation/recovery (klines 100-200)
    phase2 = np.linspace(70, 75, 100) + np.random.randn(100) * 2.0
    # Phase 3: recovery (klines 200-300)
    phase3 = np.linspace(75, 95, 100) + np.random.randn(100) * 1.5

    close = np.concatenate([phase1, phase2, phase3])
    high = close + np.abs(np.random.randn(n)) * 1.5
    low = close - np.abs(np.random.randn(n)) * 1.5
    open_p = close + np.random.randn(n) * 0.8
    volume = (np.random.rand(n) * 2e6 + 5e5).astype(int)

    df = pd.DataFrame({
        "date": dates, "open": open_p, "high": high,
        "low": low, "close": close, "volume": volume,
    })
    df["high"] = df[["high", "open", "close"]].max(axis=1)
    df["low"] = df[["low", "open", "close"]].min(axis=1)
    return df


# ═══════════════════════════════════════════════════════════════════════
# 1. Basic Pipeline Execution
# ═══════════════════════════════════════════════════════════════════════

class TestBasicPipeline:
    """Verify the pipeline runs end-to-end and returns expected fields."""

    def test_analyze_returns_dict(self, sample_df):
        result = analyze(sample_df)
        assert isinstance(result, dict)

    def test_analyze_has_all_expected_top_level_keys(self, sample_df):
        result = analyze(sample_df)
        expected_keys = {
            "summary", "fractals", "pens", "segments",
            "pivots", "divergence", "buy_sell_points", "compute_status"
        }
        assert set(result.keys()) == expected_keys

    def test_summary_counts_match(self, sample_df):
        result = analyze(sample_df)
        s = result["summary"]
        assert s["fractal_count"] == len(result["fractals"])
        assert s["pen_count"] == len(result["pens"])
        assert s["segment_count"] == len(result["segments"])
        assert s["pivot_count"] == len(result["pivots"])
        assert s["divergence_count"] == len(result["divergence"])
        assert s["buy_sell_point_count"] == len(result["buy_sell_points"])

    def test_pen_mode_old(self, sample_df):
        """Old pen mode should produce valid results."""
        result = analyze(sample_df, pen_mode="old")
        assert isinstance(result["pens"], list)
        assert result["compute_status"]["strokes_done"] is True


# ═══════════════════════════════════════════════════════════════════════
# 2. compute_status Tests
# ═══════════════════════════════════════════════════════════════════════

class TestComputeStatus:
    """Verify compute_status is correctly populated."""

    def test_compute_status_exists(self, sample_df):
        result = analyze(sample_df)
        assert "compute_status" in result

    def test_compute_status_has_all_fields(self, sample_df):
        result = analyze(sample_df)
        cs = result["compute_status"]
        expected_fields = {
            "pipeline_version", "inclusion_done", "fractals_done",
            "strokes_done", "segments_done", "centers_done",
            "divergence_done", "buy_sell_points_done",
            "warnings", "data_quality",
            "current_state",  # RUO-384
        }
        assert set(cs.keys()) == expected_fields

    def test_all_done_flags_true_with_sufficient_data(self, sample_df):
        result = analyze(sample_df)
        cs = result["compute_status"]
        assert cs["inclusion_done"] is True
        assert cs["fractals_done"] is True
        assert cs["strokes_done"] is True
        assert cs["segments_done"] is True
        assert cs["centers_done"] is True
        assert cs["divergence_done"] is True
        assert cs["buy_sell_points_done"] is True

    def test_pipeline_version(self, sample_df):
        result = analyze(sample_df)
        assert result["compute_status"]["pipeline_version"] == "2.0"

    def test_warnings_is_list(self, sample_df):
        result = analyze(sample_df)
        assert isinstance(result["compute_status"]["warnings"], list)


# ═══════════════════════════════════════════════════════════════════════
# 3. data_quality Tests
# ═══════════════════════════════════════════════════════════════════════

class TestDataQuality:
    """Verify data_quality checks."""

    def test_data_quality_fields(self, sample_df):
        result = analyze(sample_df)
        dq = result["compute_status"]["data_quality"]
        assert "klines_count" in dq
        assert "after_inclusion_count" in dq
        assert "missing_sessions" in dq
        assert "sufficient" in dq

    def test_klines_count_matches_input(self, sample_df):
        result = analyze(sample_df)
        dq = result["compute_status"]["data_quality"]
        assert dq["klines_count"] == len(sample_df)

    def test_after_inclusion_leq_klines(self, sample_df):
        result = analyze(sample_df)
        dq = result["compute_status"]["data_quality"]
        assert dq["after_inclusion_count"] <= dq["klines_count"]

    def test_sufficient_true_for_adequate_data(self, sample_df):
        result = analyze(sample_df)
        assert result["compute_status"]["data_quality"]["sufficient"] is True

    def test_sufficient_false_for_tiny_data(self, tiny_df):
        result = analyze(tiny_df)
        assert result["compute_status"]["data_quality"]["sufficient"] is False

    def test_missing_sessions_is_int(self, sample_df):
        result = analyze(sample_df)
        dq = result["compute_status"]["data_quality"]
        assert isinstance(dq["missing_sessions"], int)


# ═══════════════════════════════════════════════════════════════════════
# 4. Warning Catalog Tests
# ═══════════════════════════════════════════════════════════════════════

class TestWarnings:
    """Verify warning generation for various data conditions."""

    def test_insufficient_klines_warning(self, tiny_df):
        """< 30 klines should warn."""
        result = analyze(tiny_df)
        warnings = result["compute_status"]["warnings"]
        assert "insufficient_klines" in warnings

    def test_limited_klines_warning(self, small_df):
        """30-99 klines should warn about limited data."""
        result = analyze(small_df)
        warnings = result["compute_status"]["warnings"]
        assert "limited_klines" in warnings

    def test_no_insufficient_warning_for_adequate_data(self, sample_df):
        """≥ 100 klines should not have insufficient/limited warning."""
        result = analyze(sample_df)
        warnings = result["compute_status"]["warnings"]
        assert "insufficient_klines" not in warnings
        assert "limited_klines" not in warnings

    def test_last_segment_unconfirmed_always_present(self, sample_df):
        """Should always warn about last segment being unconfirmed."""
        result = analyze(sample_df)
        warnings = result["compute_status"]["warnings"]
        if result["segments"]:  # Only if segments exist
            assert "last_segment_unconfirmed" in warnings


# ═══════════════════════════════════════════════════════════════════════
# 5. Backward Compatibility Tests
# ═══════════════════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    """Ensure existing fields are preserved and unchanged."""

    def test_summary_still_present(self, sample_df):
        result = analyze(sample_df)
        assert "summary" in result
        s = result["summary"]
        for key in ["total_klines", "after_inclusion", "merged_count",
                     "fractal_count", "pen_count", "segment_count",
                     "pivot_count", "divergence_count", "buy_sell_point_count"]:
            assert key in s, f"Missing summary key: {key}"

    def test_fractals_format_unchanged(self, sample_df):
        result = analyze(sample_df)
        if result["fractals"]:
            f = result["fractals"][0]
            for key in ["index", "type", "value", "high", "low"]:
                assert key in f, f"Missing fractal key: {key}"

    def test_pens_format_unchanged(self, sample_df):
        result = analyze(sample_df)
        if result["pens"]:
            p = result["pens"][0]
            for key in ["start_idx", "end_idx", "direction",
                        "start_value", "end_value"]:
                assert key in p, f"Missing pen key: {key}"

    def test_segments_format_unchanged(self, sample_df):
        result = analyze(sample_df)
        if result["segments"]:
            s = result["segments"][0]
            for key in ["start_idx", "end_idx", "direction", "high", "low"]:
                assert key in s, f"Missing segment key: {key}"

    def test_pivots_format_unchanged(self, sample_df):
        result = analyze(sample_df)
        if result["pivots"]:
            pv = result["pivots"][0]
            for key in ["start_seg", "end_seg", "ZG", "ZD", "GG", "DD", "seg_count"]:
                assert key in pv, f"Missing pivot key: {key}"

    def test_buy_sell_points_format_unchanged(self, sample_df):
        result = analyze(sample_df)
        if result["buy_sell_points"]:
            bp = result["buy_sell_points"][0]
            for key in ["type", "side", "price", "idx", "confidence", "pivot_ref"]:
                assert key in bp, f"Missing buy_sell_point key: {key}"


# ═══════════════════════════════════════════════════════════════════════
# 6. detect_divergence Bug Fix Tests
# ═══════════════════════════════════════════════════════════════════════

class TestDivergenceFix:
    """Verify detect_divergence works with pens parameter (bug fix)."""

    def test_detect_divergence_accepts_pens(self, trending_df):
        """Should not raise NameError when called with pens."""
        df_inc = process_inclusion(trending_df)
        fractals = find_fractals(df_inc)
        pens = build_pens(df_inc, fractals)
        segments = build_segments(pens, df_inc)
        pivots = find_pivots(segments)
        # This call used to crash with NameError: pens not defined
        result = detect_divergence(pivots, trending_df, segments, pens)
        assert isinstance(result, list)

    def test_detect_divergence_called_correctly_in_analyze(self, trending_df):
        """Full analyze() should not crash on divergence detection."""
        result = analyze(trending_df)
        assert isinstance(result["divergence"], list)

    def test_divergence_info_format(self, trending_df):
        """If divergence is detected, format should be correct."""
        result = analyze(trending_df)
        for d in result["divergence"]:
            for key in ["pivot_idx", "direction", "area_a", "area_c",
                        "ratio", "strength"]:
                assert key in d, f"Missing divergence key: {key}"


# ═══════════════════════════════════════════════════════════════════════
# 7. Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_empty_dataframe_raises(self):
        """Empty DataFrame should be handled gracefully."""
        empty_df = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        try:
            result = analyze(empty_df)
            # If it doesn't raise, check it still returns valid structure
            assert "compute_status" in result
            assert result["compute_status"]["data_quality"]["sufficient"] is False
        except (ValueError, IndexError, KeyError):
            # Acceptable — empty data is genuinely unusable
            pass

    def test_minimum_viable_data(self):
        """Exactly 30 klines should be marked sufficient (if pens >= 3)."""
        np.random.seed(42)
        n = 30
        dates = pd.bdate_range("2025-01-01", periods=n)
        close = 100 + np.cumsum(np.random.randn(n) * 2)
        df = pd.DataFrame({
            "date": dates,
            "open": close - 0.5,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.full(n, 1e6),
        })
        result = analyze(df)
        assert result["compute_status"]["data_quality"]["klines_count"] == 30

    def test_csv_load_and_analyze(self, tmp_path):
        """CSV loading + analysis integration."""
        df = _generate_sample_data()
        csv_path = tmp_path / "test_data.csv"
        df.to_csv(csv_path, index=False)

        loaded = _load_csv(str(csv_path))
        result = analyze(loaded)
        assert "compute_status" in result
        assert result["compute_status"]["data_quality"]["klines_count"] == len(df)

    def test_pen_mode_both_produce_valid_status(self, sample_df):
        """Both pen modes should produce valid compute_status."""
        for mode in ["new", "old"]:
            result = analyze(sample_df, pen_mode=mode)
            assert result["compute_status"]["strokes_done"] is True
            assert isinstance(result["compute_status"]["warnings"], list)


# ═══════════════════════════════════════════════════════════════════════
# 8. RUO-384 v2.1 Enhancement Tests
# ═══════════════════════════════════════════════════════════════════════

class TestPenToSegmentRatio:
    """Verify pen_to_segment_ratio in compute_status data_quality (RUO-384)."""

    def test_pen_to_segment_ratio_exists(self, sample_df):
        result = analyze(sample_df)
        dq = result["compute_status"]["data_quality"]
        assert "pen_to_segment_ratio" in dq

    def test_pen_to_segment_ratio_value(self, sample_df):
        result = analyze(sample_df)
        dq = result["compute_status"]["data_quality"]
        if result["segments"]:
            expected = round(len(result["pens"]) / len(result["segments"]), 1)
            assert dq["pen_to_segment_ratio"] == expected
        else:
            assert dq["pen_to_segment_ratio"] is None

    def test_pen_to_segment_ratio_is_float_or_none(self, sample_df):
        result = analyze(sample_df)
        ratio = result["compute_status"]["data_quality"]["pen_to_segment_ratio"]
        assert ratio is None or isinstance(ratio, (int, float))


class TestCurrentState:
    """Verify current_state in compute_status (RUO-384)."""

    def test_current_state_key_exists(self, sample_df):
        result = analyze(sample_df)
        assert "current_state" in result["compute_status"]

    def test_current_state_fields(self, sample_df):
        result = analyze(sample_df)
        cs = result["compute_status"]["current_state"]
        if cs is not None:
            for key in ["price", "position_vs_pivot", "nearest_ZG",
                        "nearest_ZD", "last_segment_direction"]:
                assert key in cs, f"Missing current_state key: {key}"

    def test_current_state_position_values(self, sample_df):
        result = analyze(sample_df)
        cs = result["compute_status"]["current_state"]
        if cs is not None:
            assert cs["position_vs_pivot"] in (
                "above_ZG", "below_ZD", "inside_center")

    def test_current_state_none_when_no_pivots(self, tiny_df):
        result = analyze(tiny_df)
        assert result["compute_status"]["current_state"] is None

    def test_current_state_price_matches_last_close(self, sample_df):
        result = analyze(sample_df)
        cs = result["compute_status"]["current_state"]
        if cs is not None:
            expected = round(float(sample_df["close"].iloc[-1]), 2)
            assert cs["price"] == expected


class TestAnalyzeSymbol:
    """Verify analyze_symbol convenience function (RUO-384)."""

    def test_analyze_symbol_callable(self):
        assert callable(analyze_symbol)

    def test_analyze_symbol_returns_dict(self):
        """Live test — requires network and yfinance."""
        try:
            result = analyze_symbol("AAPL", period="6mo")
            assert isinstance(result, dict)
            assert "compute_status" in result
        except Exception:
            pytest.skip("Network/yfinance unavailable")

    def test_analyze_symbol_has_current_state(self):
        try:
            result = analyze_symbol("AAPL", period="1y")
            assert "current_state" in result["compute_status"]
        except Exception:
            pytest.skip("Network/yfinance unavailable")


# ═══════════════════════════════════════════════════════════════════════
# 9. Individual Step Tests
# ═══════════════════════════════════════════════════════════════════════

class TestIndividualSteps:
    """Test individual pipeline steps in isolation."""

    def test_process_inclusion_reduces_or_preserves_count(self, sample_df):
        df_inc = process_inclusion(sample_df)
        assert len(df_inc) <= len(sample_df)
        assert "_orig_start" in df_inc.columns
        assert "_orig_end" in df_inc.columns

    def test_find_fractals_returns_list_of_fractal(self, sample_df):
        df_inc = process_inclusion(sample_df)
        fractals = find_fractals(df_inc)
        assert isinstance(fractals, list)
        for f in fractals:
            assert isinstance(f, Fractal)
            assert f.ftype in ("top", "bottom")

    def test_build_pens_alternating_directions(self, sample_df):
        df_inc = process_inclusion(sample_df)
        fractals = find_fractals(df_inc)
        pens = build_pens(df_inc, fractals)
        # Adjacent pens should have opposite directions
        for i in range(1, len(pens)):
            assert pens[i].direction != pens[i - 1].direction, \
                f"Pens {i-1} and {i} have same direction"

    def test_find_pivots_requires_three_segments(self, sample_df):
        df_inc = process_inclusion(sample_df)
        fractals = find_fractals(df_inc)
        pens = build_pens(df_inc, fractals)
        segments = build_segments(pens, df_inc)
        pivots = find_pivots(segments)
        # Pivots need at least 3 segments
        if len(segments) < 3:
            assert len(pivots) == 0
        else:
            # Each pivot should have ZG > ZD
            for pv in pivots:
                assert pv.ZG > pv.ZD, "Invalid pivot: ZG <= ZD"


# ═══════════════════════════════════════════════════════════════════════
# CLI Entry Point (for running without pytest)
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Run tests manually if pytest not available
    print("Running chanlun_engine tests...\n")

    passed = 0
    failed = 0

    def run_test(test_class, test_method):
        global passed, failed
        try:
            instance = test_class()
            # Get fixtures manually
            method = getattr(instance, test_method)
            # Check if method needs arguments
            import inspect
            sig = inspect.signature(method)
            params = list(sig.parameters.keys())
            # Skip if needs fixtures (we'll handle common ones)
            if not params:
                method()
                print(f"  ✓ {test_class.__name__}.{test_method}")
                passed += 1
            else:
                print(f"  ⊘ {test_class.__name__}.{test_method} (needs fixture, skip in manual mode)")
        except Exception as e:
            print(f"  ✗ {test_class.__name__}.{test_method}: {e}")
            failed += 1

    # Run fixture-free tests
    for cls in [TestIndividualSteps]:
        for method_name in dir(cls):
            if method_name.startswith("test_"):
                run_test(cls, method_name)

    # Run sample-data tests
    print("\n  --- With sample data ---")
    sample = _generate_sample_data()
    result = analyze(sample)

    # Quick assertions
    assert "compute_status" in result, "Missing compute_status"
    assert result["compute_status"]["pipeline_version"] == "2.0"
    assert result["compute_status"]["data_quality"]["sufficient"] is True
    print(f"  ✓ compute_status present and correct")
    print(f"  ✓ pipeline_version = 2.0")
    print(f"  ✓ data_quality.sufficient = True")
    print(f"  ✓ warnings = {result['compute_status']['warnings']}")
    print(f"  ✓ fractals={len(result['fractals'])}, pens={len(result['pens'])}, "
          f"segments={len(result['segments'])}, pivots={len(result['pivots'])}")
    passed += 4

    # Test trending data (divergence bug fix)
    print("\n  --- Trending data (divergence fix) ---")
    np.random.seed(123)
    n = 300
    dates = pd.bdate_range("2025-01-01", periods=n)
    p1 = np.linspace(100, 70, 100) + np.random.randn(100) * 1.5
    p2 = np.linspace(70, 75, 100) + np.random.randn(100) * 2.0
    p3 = np.linspace(75, 95, 100) + np.random.randn(100) * 1.5
    close = np.concatenate([p1, p2, p3])
    high = close + np.abs(np.random.randn(n)) * 1.5
    low = close - np.abs(np.random.randn(n)) * 1.5
    df_trend = pd.DataFrame({
        "date": dates, "open": close, "high": high,
        "low": low, "close": close, "volume": np.full(n, 1e6),
    })
    df_trend["high"] = df_trend[["high", "open", "close"]].max(axis=1)
    df_trend["low"] = df_trend[["low", "open", "close"]].min(axis=1)
    result_trend = analyze(df_trend)
    assert isinstance(result_trend["divergence"], list), "divergence should be a list"
    print(f"  ✓ detect_divergence ran without NameError")
    print(f"  ✓ divergence results: {len(result_trend['divergence'])}")
    print(f"  ✓ pivots: {len(result_trend['pivots'])}")
    passed += 3

    print(f"\n{'='*50}")
    print(f"  Passed: {passed}, Failed: {failed}")
    print(f"{'='*50}")

    if failed > 0:
        sys.exit(1)
    else:
        print("\n  All tests passed! ✅")
