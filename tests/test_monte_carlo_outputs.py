"""
Unit tests for Monte Carlo output extraction.

Tests verify correct handling of per-period flows (RBdFt) vs pool balances (carbon, BA).
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fvs_tools.monte_carlo import extract_run_summary, extract_time_series


class TestExtractRunSummary:
    """Test extract_run_summary function."""

    def test_complete_data(self):
        """Test extraction with all data present."""
        # Mock complete results
        results = {
            "summary_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A", "B", "B", "B"],
                    "Year": [2023, 2033, 2043, 2023, 2033, 2043],
                    "BA": [120, 115, 110, 125, 120, 115],
                    "Tpa": [300, 280, 260, 310, 290, 270],
                    "RBdFt": [1000, 500, 300, 1200, 600, 400],  # Per-period flow
                }
            ),
            "carbon_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A", "B", "B", "B"],
                    "Year": [2023, 2033, 2043, 2023, 2033, 2043],
                    "Aboveground_Total_Live": [40, 38, 36, 42, 40, 38],  # Pool
                    "Standing_Dead": [3, 4, 5, 3, 4, 5],  # Pool
                }
            ),
            "compute_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A", "B", "B", "B"],
                    "Year": [2023, 2033, 2043, 2023, 2033, 2043],
                    "PC_CAN_C": [60, 55, 50, 62, 57, 52],  # Pool
                }
            ),
            "harvest_carbon_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A", "B", "B", "B"],
                    "Year": [2023, 2033, 2043, 2023, 2033, 2043],
                    "Merch_Carbon_Stored": [5, 10, 14, 6, 11, 15],  # Pool with decay
                }
            ),
            "run_status": pd.DataFrame({"success": [True, True]}),
        }

        summary = extract_run_summary(results)

        # Check all keys present
        expected_keys = {
            "final_total_carbon",
            "avg_carbon_stock",
            "final_live_carbon",
            "final_dead_carbon",
            "final_stored_carbon",
            "min_canopy_cover",
            "final_canopy_cover",
            "cumulative_harvest_bdft",
            "n_stands",
        }
        assert set(summary.keys()) == expected_keys

        # Check n_stands
        assert summary["n_stands"] == 2

        # Check final carbon (pool balances at final year)
        assert summary["final_live_carbon"] == pytest.approx(37.0, abs=0.1)  # (36+38)/2
        assert summary["final_dead_carbon"] == pytest.approx(5.0, abs=0.1)  # (5+5)/2
        assert summary["final_stored_carbon"] == pytest.approx(
            14.5, abs=0.1
        )  # (14+15)/2
        assert summary["final_total_carbon"] == pytest.approx(
            56.5, abs=0.1
        )  # 37+5+14.5

        # Check canopy (pool balance)
        assert summary["min_canopy_cover"] == pytest.approx(
            51.0, abs=0.1
        )  # min of means
        assert summary["final_canopy_cover"] == pytest.approx(
            51.0, abs=0.1
        )  # (50+52)/2

        # CRITICAL: Check harvest (flow field - average across stands per year, then sum)
        # Year 2023: (1000+1200)/2 = 1100
        # Year 2033: (500+600)/2 = 550
        # Year 2043: (300+400)/2 = 350
        # Total: 1100+550+350 = 2000 bdft/ac (per-acre cumulative harvest)
        assert summary["cumulative_harvest_bdft"] == pytest.approx(2000.0, abs=0.1)

    def test_harvest_is_summed_not_final(self):
        """Verify RBdFt (flow) is summed, not taken at final year."""
        results = {
            "summary_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A"],
                    "Year": [2023, 2033, 2043],
                    "RBdFt": [1000, 500, 300],  # Per-period removals
                }
            ),
            "run_status": pd.DataFrame({"success": [True]}),
        }

        summary = extract_run_summary(results)

        # Should be sum (1800), NOT final year value (300)
        assert summary["cumulative_harvest_bdft"] == 1800.0

    def test_carbon_is_final_not_summed(self):
        """Verify carbon (pool) uses final year, not sum."""
        results = {
            "summary_all": pd.DataFrame(
                {"StandID": ["A", "A", "A"], "Year": [2023, 2033, 2043]}
            ),
            "carbon_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A"],
                    "Year": [2023, 2033, 2043],
                    "Aboveground_Total_Live": [40, 38, 36],  # Declining pool
                }
            ),
            "run_status": pd.DataFrame({"success": [True]}),
        }

        summary = extract_run_summary(results)

        # Should be final year (36), NOT sum (114)
        assert summary["final_live_carbon"] == 36.0

    def test_missing_carbon(self):
        """Test with no carbon_all data."""
        results = {
            "summary_all": pd.DataFrame(
                {"StandID": ["A"], "Year": [2023], "BA": [120]}
            ),
            "run_status": pd.DataFrame({"success": [True]}),
        }

        summary = extract_run_summary(results)

        assert summary["n_stands"] == 1
        assert (
            summary["final_live_carbon"] is None or summary["final_live_carbon"] == 0.0
        )
        assert (
            summary["final_total_carbon"] is None
            or summary["final_total_carbon"] == 0.0
        )

    def test_missing_canopy(self):
        """Test with no compute_all data."""
        results = {
            "summary_all": pd.DataFrame(
                {"StandID": ["A"], "Year": [2023], "BA": [120]}
            ),
            "run_status": pd.DataFrame({"success": [True]}),
        }

        summary = extract_run_summary(results)

        assert summary["min_canopy_cover"] is None
        assert summary["final_canopy_cover"] is None

    def test_missing_harvest(self):
        """Test with no harvest data."""
        results = {
            "summary_all": pd.DataFrame(
                {"StandID": ["A"], "Year": [2023], "BA": [120]}
            ),
            "run_status": pd.DataFrame({"success": [True]}),
        }

        summary = extract_run_summary(results)

        # No harvest = 0
        assert summary["cumulative_harvest_bdft"] == 0.0

    def test_empty_results(self):
        """Test with empty results dict."""
        summary = extract_run_summary({})

        # Should return dict with all None/0 values
        assert summary["n_stands"] == 0
        assert summary["cumulative_harvest_bdft"] == 0.0
        assert summary["final_total_carbon"] is None

    def test_merch_carbon_stored_is_pool(self):
        """Verify Merch_Carbon_Stored is treated as pool balance, not summed."""
        results = {
            "summary_all": pd.DataFrame(
                {"StandID": ["A", "A", "A"], "Year": [2023, 2033, 2043]}
            ),
            "harvest_carbon_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A"],
                    "Year": [2023, 2033, 2043],
                    "Merch_Carbon_Stored": [5, 10, 14],  # Pool with decay
                }
            ),
            "run_status": pd.DataFrame({"success": [True]}),
        }

        summary = extract_run_summary(results)

        # Should be final value (14), NOT sum (29)
        assert summary["final_stored_carbon"] == 14.0


class TestExtractTimeSeries:
    """Test extract_time_series function."""

    def test_complete_data(self):
        """Test extraction with all data present."""
        results = {
            "summary_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A", "B", "B", "B"],
                    "Year": [2023, 2033, 2043, 2023, 2033, 2043],
                    "BA": [120, 115, 110, 125, 120, 115],
                    "Tpa": [300, 280, 260, 310, 290, 270],
                    "RBdFt": [1000, 500, 300, 1200, 600, 400],
                }
            ),
            "carbon_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A", "B", "B", "B"],
                    "Year": [2023, 2033, 2043, 2023, 2033, 2043],
                    "Aboveground_Total_Live": [40, 38, 36, 42, 40, 38],
                    "Standing_Dead": [3, 4, 5, 3, 4, 5],
                }
            ),
            "compute_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A", "B", "B", "B"],
                    "Year": [2023, 2033, 2043, 2023, 2033, 2043],
                    "PC_CAN_C": [60, 55, 50, 62, 57, 52],
                }
            ),
        }

        ts = extract_time_series(results)

        assert len(ts) == 3  # 3 years
        assert list(ts["year"]) == [2023, 2033, 2043]

        # Check pool balances (mean across stands)
        assert ts.loc[0, "ba"] == pytest.approx(122.5, abs=0.1)  # (120+125)/2
        assert ts.loc[0, "tpa"] == pytest.approx(305.0, abs=0.1)  # (300+310)/2
        assert ts.loc[0, "aboveground_c_live"] == pytest.approx(
            41.0, abs=0.1
        )  # (40+42)/2
        assert ts.loc[0, "canopy_cover_pct"] == pytest.approx(
            61.0, abs=0.1
        )  # (60+62)/2

        # Check harvest (flow field, mean per period)
        assert ts.loc[0, "harvest_bdft"] == pytest.approx(
            1100.0, abs=0.1
        )  # (1000+1200)/2
        assert ts.loc[1, "harvest_bdft"] == pytest.approx(550.0, abs=0.1)  # (500+600)/2
        assert ts.loc[2, "harvest_bdft"] == pytest.approx(350.0, abs=0.1)  # (300+400)/2

    def test_cumulative_harvest_is_cumsum(self):
        """Verify cumulative_harvest is cumsum of harvest_bdft."""
        results = {
            "summary_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A"],
                    "Year": [2023, 2033, 2043],
                    "RBdFt": [1000, 500, 300],
                }
            )
        }

        ts = extract_time_series(results)

        assert list(ts["harvest_bdft"]) == [1000, 500, 300]
        assert list(ts["cumulative_harvest"]) == [1000, 1500, 1800]

        # Verify monotonically increasing
        assert ts["cumulative_harvest"].is_monotonic_increasing

    def test_carbon_pools_not_cumsum(self):
        """Verify carbon pools are NOT cumsum'd."""
        results = {
            "summary_all": pd.DataFrame(
                {"StandID": ["A", "A", "A"], "Year": [2023, 2033, 2043]}
            ),
            "carbon_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A"],
                    "Year": [2023, 2033, 2043],
                    "Aboveground_Total_Live": [40, 38, 36],
                }
            ),
        }

        ts = extract_time_series(results)

        # Should be actual values, NOT cumsum
        assert list(ts["aboveground_c_live"]) == [40, 38, 36]

    def test_missing_data(self):
        """Test with partial data."""
        results = {
            "summary_all": pd.DataFrame(
                {"StandID": ["A", "A"], "Year": [2023, 2033], "BA": [120, 115]}
            )
        }

        ts = extract_time_series(results)

        assert len(ts) == 2
        assert "ba" in ts.columns
        # Missing columns should have 0 or NaN
        if "harvest_bdft" in ts.columns:
            assert (ts["harvest_bdft"] == 0).all()

    def test_empty_results(self):
        """Test with empty results."""
        ts = extract_time_series({})
        assert len(ts) == 0

    def test_validation_catches_non_monotonic(self):
        """Test that validation catches incorrectly computed cumulative."""
        # This shouldn't happen with correct implementation, but tests the validator
        results = {
            "summary_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "A"],
                    "Year": [2023, 2033, 2043],
                    "RBdFt": [1000, 500, 300],
                }
            )
        }

        ts = extract_time_series(results)

        # Manually corrupt cumulative to test validator
        ts["cumulative_harvest"] = [1000, 1500, 1400]  # Decreases!

        with pytest.raises(ValueError, match="not monotonically increasing"):
            from fvs_tools.monte_carlo.outputs import _validate_time_series

            _validate_time_series(ts)


class TestColumnMapping:
    """Test column name variation handling."""

    def test_find_column_first_match(self):
        """Test _find_column returns first match."""
        from fvs_tools.monte_carlo.outputs import _find_column

        df = pd.DataFrame(
            {"Aboveground_Total_Live": [40], "Above_Ground_Total_Live": [42]}
        )

        col = _find_column(df, ["Aboveground_Total_Live", "Above_Ground_Total_Live"])
        assert col == "Aboveground_Total_Live"

    def test_find_column_no_match(self):
        """Test _find_column returns None when no match."""
        from fvs_tools.monte_carlo.outputs import _find_column

        df = pd.DataFrame({"BA": [120]})

        col = _find_column(df, ["NotPresent", "AlsoNotPresent"])
        assert col is None

    def test_alternative_carbon_column_names(self):
        """Test extraction works with standard FVS carbon column names."""
        results = {
            "summary_all": pd.DataFrame({"StandID": ["A"], "Year": [2023]}),
            "carbon_all": pd.DataFrame(
                {
                    "StandID": ["A"],
                    "Year": [2023],
                    "Aboveground_Total_Live": [40],  # Standard FVS name
                }
            ),
            "run_status": pd.DataFrame({"success": [True]}),
        }

        summary = extract_run_summary(results)
        assert summary["final_live_carbon"] == 40.0

    def test_alternative_canopy_column_names(self):
        """Test extraction works with standard FVS canopy column name."""
        results = {
            "summary_all": pd.DataFrame({"StandID": ["A"], "Year": [2023]}),
            "compute_all": pd.DataFrame(
                {
                    "StandID": ["A"],
                    "Year": [2023],
                    "PC_CAN_C": [55],  # Standard FVS name from COMPUTE keyword
                }
            ),
            "run_status": pd.DataFrame({"success": [True]}),
        }

        summary = extract_run_summary(results)
        assert summary["final_canopy_cover"] == 55.0
