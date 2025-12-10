"""
Integration tests for Monte Carlo FVS keywords.

These tests run actual FVS simulations to verify that:
- FixMort keyword affects mortality rates
- NoCaLib keyword disables calibration
- RanNSeed keyword sets random seed

These tests are SLOW (each FVS run takes ~2-5 seconds) and should be run
separately from unit tests:

    uv run pytest tests/test_monte_carlo_integration.py -v

Use markers to skip in regular test runs:
    uv run pytest tests/ -m "not integration"
"""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import fvs_tools as fvs

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def test_data():
    """Load a single stand for testing (fast runs)."""
    stands = fvs.load_stands()
    trees = fvs.load_trees()

    # Use just one stand for speed
    single_stand, single_trees = fvs.filter_by_plot_ids(stands, trees, [99])

    return single_stand, single_trees


@pytest.fixture(scope="module")
def output_base(tmp_path_factory):
    """Create a temporary output directory."""
    return tmp_path_factory.mktemp("fvs_integration")


def _generate_keyword_content(stand, config, output_dir):
    """Helper to generate keyword file and return content."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    keyword_file = output_dir / "test.key"
    fvs.build_keyword_file(
        stand=stand,
        tree_filename="FVS_Data.db",
        config=config,
        filepath=keyword_file,
        use_database=True,
    )
    return keyword_file.read_text()


class TestFixMortKeyword:
    """Test that FixMort keyword affects mortality rates."""

    def test_fixmort_generates_keyword(self, test_data, output_base):
        """Verify FixMort keyword appears in generated keyword file."""
        stands, trees = test_data

        config = fvs.FVSSimulationConfig(
            name="test_fixmort",
            num_years=20,
            cycle_length=10,
            mortality_multiplier=1.5,
        )

        keyword_content = _generate_keyword_content(
            stands.iloc[0], config, output_base / "fixmort_keyword"
        )

        assert "FixMort" in keyword_content
        assert "1.50" in keyword_content

    def test_fixmort_runs_without_error(self, test_data, output_base):
        """Verify FVS accepts and runs with FixMort keyword."""
        stands, trees = test_data
        output_dir = output_base / "fixmort_test"
        output_dir.mkdir(exist_ok=True)

        config = fvs.FVSSimulationConfig(
            name="fixmort_test",
            num_years=20,
            cycle_length=10,
            mortality_multiplier=1.5,
        )

        # Create input database
        input_db = output_dir / "FVS_Data.db"
        fvs.create_fvs_input_db(stands, trees, input_db)

        # Run simulation
        results = fvs.run_batch_simulation(
            stands=stands,
            trees=trees,
            config=config,
            output_base=output_dir,
            use_database=True,
            input_database=input_db,
        )

        # Verify success
        status = results["run_status"]
        assert status["success"].all(), f"FVS run failed: {status}"

        # Check for FVS errors
        errors = fvs.collect_batch_errors(output_dir)
        # Filter out non-critical warnings
        critical_errors = errors[
            ~errors["Message"].str.contains("WARNING", case=False, na=False)
        ]
        assert len(critical_errors) == 0, f"FVS errors: {critical_errors}"


class TestNoCaLibKeyword:
    """Test that NoCaLib keyword disables calibration."""

    def test_nocalib_generates_keyword(self, test_data, output_base):
        """Verify NoCaLib keyword appears when calibration disabled."""
        stands, trees = test_data

        config = fvs.FVSSimulationConfig(
            name="test_nocalib",
            num_years=20,
            cycle_length=10,
            enable_calibration=False,
        )

        keyword_content = _generate_keyword_content(
            stands.iloc[0], config, output_base / "nocalib_keyword"
        )

        assert "NoCaLib" in keyword_content

    def test_nocalib_not_present_when_enabled(self, test_data, output_base):
        """Verify NoCaLib not present when calibration enabled (default)."""
        stands, trees = test_data

        config = fvs.FVSSimulationConfig(
            name="test_calib_enabled",
            num_years=20,
            cycle_length=10,
            enable_calibration=True,  # default
        )

        keyword_content = _generate_keyword_content(
            stands.iloc[0], config, output_base / "calib_enabled"
        )

        assert "NoCaLib" not in keyword_content

    def test_nocalib_runs_without_error(self, test_data, output_base):
        """Verify FVS accepts and runs with NoCaLib keyword."""
        stands, trees = test_data
        output_dir = output_base / "nocalib_test"
        output_dir.mkdir(exist_ok=True)

        config = fvs.FVSSimulationConfig(
            name="nocalib_test",
            num_years=20,
            cycle_length=10,
            enable_calibration=False,
        )

        input_db = output_dir / "FVS_Data.db"
        fvs.create_fvs_input_db(stands, trees, input_db)

        results = fvs.run_batch_simulation(
            stands=stands,
            trees=trees,
            config=config,
            output_base=output_dir,
            use_database=True,
            input_database=input_db,
        )

        status = results["run_status"]
        assert status["success"].all(), f"FVS run failed: {status}"

    def test_calibration_affects_output(self, test_data, output_base):
        """Compare runs with and without calibration - results should differ."""
        stands, trees = test_data

        # Run WITH calibration
        output_calib = output_base / "with_calib"
        output_calib.mkdir(exist_ok=True)

        config_calib = fvs.FVSSimulationConfig(
            name="with_calib",
            num_years=50,
            cycle_length=10,
            enable_calibration=True,
        )

        input_db_calib = output_calib / "FVS_Data.db"
        fvs.create_fvs_input_db(stands, trees, input_db_calib)

        results_calib = fvs.run_batch_simulation(
            stands=stands,
            trees=trees,
            config=config_calib,
            output_base=output_calib,
            use_database=True,
            input_database=input_db_calib,
        )

        # Run WITHOUT calibration
        output_no_calib = output_base / "no_calib"
        output_no_calib.mkdir(exist_ok=True)

        config_no_calib = fvs.FVSSimulationConfig(
            name="no_calib",
            num_years=50,
            cycle_length=10,
            enable_calibration=False,
        )

        input_db_no_calib = output_no_calib / "FVS_Data.db"
        fvs.create_fvs_input_db(stands, trees, input_db_no_calib)

        results_no_calib = fvs.run_batch_simulation(
            stands=stands,
            trees=trees,
            config=config_no_calib,
            output_base=output_no_calib,
            use_database=True,
            input_database=input_db_no_calib,
        )

        # Compare final basal area - should be different
        ba_calib = results_calib["summary_all"]["BA"].iloc[-1]
        ba_no_calib = results_no_calib["summary_all"]["BA"].iloc[-1]

        # They should differ (calibration adjusts growth rates)
        # Allow small tolerance for numerical precision
        assert abs(ba_calib - ba_no_calib) > 0.1, (
            f"Calibration should affect results: "
            f"with_calib={ba_calib:.2f}, no_calib={ba_no_calib:.2f}"
        )


class TestRanNSeedKeyword:
    """Test that RanNSeed keyword sets FVS random seed."""

    def test_ransnseed_generates_keyword(self, test_data, output_base):
        """Verify RanNSeed keyword appears in generated keyword file."""
        stands, trees = test_data

        config = fvs.FVSSimulationConfig(
            name="test_ransnseed",
            num_years=20,
            cycle_length=10,
            fvs_random_seed=12345,
        )

        keyword_content = _generate_keyword_content(
            stands.iloc[0], config, output_base / "ransnseed_keyword"
        )

        assert "RanNSeed" in keyword_content
        assert "12345" in keyword_content

    def test_ransnseed_runs_without_error(self, test_data, output_base):
        """Verify FVS accepts and runs with RanNSeed keyword."""
        stands, trees = test_data
        output_dir = output_base / "ransnseed_test"
        output_dir.mkdir(exist_ok=True)

        config = fvs.FVSSimulationConfig(
            name="ransnseed_test",
            num_years=20,
            cycle_length=10,
            fvs_random_seed=42,
        )

        input_db = output_dir / "FVS_Data.db"
        fvs.create_fvs_input_db(stands, trees, input_db)

        results = fvs.run_batch_simulation(
            stands=stands,
            trees=trees,
            config=config,
            output_base=output_dir,
            use_database=True,
            input_database=input_db,
        )

        status = results["run_status"]
        assert status["success"].all(), f"FVS run failed: {status}"


class TestCombinedKeywords:
    """Test that multiple new keywords work together."""

    def test_all_new_keywords_together(self, test_data, output_base):
        """Run with FixMort + NoCaLib + RanNSeed simultaneously."""
        stands, trees = test_data
        output_dir = output_base / "combined_test"
        output_dir.mkdir(exist_ok=True)

        config = fvs.FVSSimulationConfig(
            name="combined_test",
            num_years=30,
            cycle_length=10,
            mortality_multiplier=0.8,
            enable_calibration=False,
            fvs_random_seed=99999,
        )

        # Check keyword file has all three
        keyword_content = _generate_keyword_content(
            stands.iloc[0], config, output_dir / "keywords"
        )

        assert "FixMort" in keyword_content
        assert "0.80" in keyword_content
        assert "NoCaLib" in keyword_content
        assert "RanNSeed" in keyword_content
        assert "99999" in keyword_content

        # Run simulation
        input_db = output_dir / "FVS_Data.db"
        fvs.create_fvs_input_db(stands, trees, input_db)

        results = fvs.run_batch_simulation(
            stands=stands,
            trees=trees,
            config=config,
            output_base=output_dir,
            use_database=True,
            input_database=input_db,
        )

        status = results["run_status"]
        assert status["success"].all(), f"FVS run failed: {status}"

        # Verify we got output
        summary = results["summary_all"]
        assert len(summary) > 0, "No summary output produced"
        assert "BA" in summary.columns, "Missing BA column"


class TestMortalityEffect:
    """Test that FixMort actually changes mortality rates."""

    def test_high_mortality_reduces_trees(self, test_data, output_base):
        """Higher mortality multiplier should result in fewer trees."""
        stands, trees = test_data

        # Run with normal mortality (multiplier=1.0)
        output_normal = output_base / "mort_normal"
        output_normal.mkdir(exist_ok=True)

        config_normal = fvs.FVSSimulationConfig(
            name="mort_normal",
            num_years=50,
            cycle_length=10,
            mortality_multiplier=1.0,
            enable_calibration=False,  # Disable to isolate mortality effect
        )

        input_db_normal = output_normal / "FVS_Data.db"
        fvs.create_fvs_input_db(stands, trees, input_db_normal)

        results_normal = fvs.run_batch_simulation(
            stands=stands,
            trees=trees,
            config=config_normal,
            output_base=output_normal,
            use_database=True,
            input_database=input_db_normal,
        )

        # Run with HIGH mortality (multiplier=2.0)
        output_high = output_base / "mort_high"
        output_high.mkdir(exist_ok=True)

        config_high = fvs.FVSSimulationConfig(
            name="mort_high",
            num_years=50,
            cycle_length=10,
            mortality_multiplier=2.0,
            enable_calibration=False,
        )

        input_db_high = output_high / "FVS_Data.db"
        fvs.create_fvs_input_db(stands, trees, input_db_high)

        results_high = fvs.run_batch_simulation(
            stands=stands,
            trees=trees,
            config=config_high,
            output_base=output_high,
            use_database=True,
            input_database=input_db_high,
        )

        # Compare final Tpa (trees per acre)
        tpa_normal = results_normal["summary_all"]["Tpa"].iloc[-1]
        tpa_high = results_high["summary_all"]["Tpa"].iloc[-1]

        # High mortality should result in fewer trees
        assert tpa_high < tpa_normal, (
            f"Higher mortality should reduce Tpa: "
            f"normal={tpa_normal:.1f}, high={tpa_high:.1f}"
        )

        print("\nMortality effect confirmed:")
        print(f"  Normal mortality (1.0x): {tpa_normal:.1f} TPA")
        print(f"  High mortality (2.0x): {tpa_high:.1f} TPA")
        print(f"  Reduction: {(1 - tpa_high/tpa_normal)*100:.1f}%")


class TestOutputExtraction:
    """Integration tests for output extraction functions."""

    def test_extract_harvest_scenario(self, tmp_path):
        """
        Integration test: Run harvest scenario and verify output extraction.

        This test replicates the Assignment 5 harvest scenario to verify:
        1. extract_run_summary correctly computes cumulative harvest (flow field)
        2. extract_run_summary correctly computes final carbon (pool fields)
        3. extract_time_series produces monotonically increasing cumulative harvest
        4. Merch_Carbon_Stored is treated as pool balance (not cumsum'd)
        5. Results match expected values from Assignment 5 notebook
        """
        from fvs_tools.monte_carlo import extract_run_summary, extract_time_series

        # Load Section 6 data
        stands_full = fvs.load_stands()
        trees_full = fvs.load_trees()
        section6_plots = [99, 100, 101, 293, 294, 295, 296, 297]
        stands, trees = fvs.filter_by_plot_ids(stands_full, trees_full, section6_plots)

        print(f"\nSection 6: {len(stands)} stands, {len(trees)} trees")

        # Configure harvest scenario (matches Assignment 5)
        config = fvs.FVSSimulationConfig(
            name="harv1_integration_test",
            num_years=100,
            cycle_length=10,
            output_treelist=True,
            output_carbon=True,
            compute_canopy_cover=True,
            thin_q_factor=2.0,
            thin_residual_ba=65.0,
            thin_trigger_ba=100.0,
            thin_min_dbh=2.0,
            thin_max_dbh=24.0,
            min_harvest_volume=4500.0,
        )

        # Run simulation
        output_dir = tmp_path / "harvest_test"
        output_dir.mkdir(exist_ok=True)

        input_db = output_dir / "FVS_Data.db"
        fvs.create_fvs_input_db(stands, trees, input_db)

        results = fvs.run_batch_simulation(
            stands=stands,
            trees=trees,
            config=config,
            output_base=output_dir,
            use_database=True,
            input_database=input_db,
        )

        # Verify all runs succeeded
        assert results["run_status"]["success"].all(), "Some FVS runs failed"

        print("\n=== Test 1: extract_run_summary ===")
        summary = extract_run_summary(results)

        # Check cumulative harvest (FLOW field - summed across periods)
        # Expected from Assignment 5: ~17000 bdft/ac total
        cumulative_harvest = summary["cumulative_harvest_bdft"]
        print(f"Cumulative harvest: {cumulative_harvest:.1f} bdft/ac")
        assert cumulative_harvest > 0, "Should have harvested timber"
        assert 15000 < cumulative_harvest < 20000, (
            f"Cumulative harvest ({cumulative_harvest:.1f}) outside expected range "
            f"(15000-20000 bdft/ac from Assignment 5)"
        )

        # Check final carbon (POOL fields - values at final year)
        final_live_c = summary["final_live_carbon"]
        final_stored_c = summary["final_stored_carbon"]
        final_total_c = summary["final_total_carbon"]

        print(f"Final live carbon: {final_live_c:.1f} tons/ac")
        print(f"Final stored carbon: {final_stored_c:.1f} tons/ac")
        print(f"Final total carbon: {final_total_c:.1f} tons/ac")

        # From Assignment 5: Live ~20, Stored ~15, Total ~38 tons/ac
        assert final_live_c > 0, "Should have live carbon"
        assert final_stored_c > 0, "Should have stored carbon from harvest"
        assert (
            15 < final_live_c < 30
        ), f"Live carbon {final_live_c:.1f} outside expected range"
        assert (
            10 < final_stored_c < 20
        ), f"Stored carbon {final_stored_c:.1f} outside expected range"
        assert (
            30 < final_total_c < 50
        ), f"Total carbon {final_total_c:.1f} outside expected range"

        print("\n=== Test 2: extract_time_series ===")
        ts = extract_time_series(results)

        # Check that we have data for all periods
        assert len(ts) == 11, f"Expected 11 periods (0-100 years by 10), got {len(ts)}"
        assert ts["year"].min() == 2023
        assert ts["year"].max() == 2123

        # Check cumulative harvest is monotonically increasing (FLOW field)
        cumulative = ts["cumulative_harvest"].values
        print(f"Cumulative harvest by period: {cumulative}")
        assert all(
            cumulative[i] <= cumulative[i + 1] for i in range(len(cumulative) - 1)
        ), "Cumulative harvest should be monotonically increasing"

        # Verify final cumulative matches summary
        ts_final_harvest = ts["cumulative_harvest"].iloc[-1]
        assert abs(ts_final_harvest - cumulative_harvest) < 1, (
            f"Time series final harvest ({ts_final_harvest:.1f}) doesn't match "
            f"summary ({cumulative_harvest:.1f})"
        )

        # Check that Merch_Carbon_Stored is present and reasonable (POOL balance)
        if "merch_carbon_stored" in ts.columns:
            stored_c_series = ts["merch_carbon_stored"].values
            print(f"Stored carbon by period: {stored_c_series}")

            # Should be non-negative
            assert (stored_c_series >= 0).all(), "Stored carbon should be non-negative"

            # Should increase initially then stabilize (due to decay)
            # NOT necessarily monotonic (decay can reduce it)
            assert stored_c_series[-1] > 0, "Should have stored carbon at end"

            # Final value should match summary
            assert abs(stored_c_series[-1] - final_stored_c) < 0.1, (
                f"Time series stored carbon ({stored_c_series[-1]:.1f}) doesn't match "
                f"summary ({final_stored_c:.1f})"
            )

        # Check carbon pools are reasonable (not cumsum'd)
        live_c_series = ts["aboveground_c_live"].values
        print(f"Live carbon by period: {live_c_series}")

        # Live carbon should fluctuate (thinning reduces it, growth increases it)
        # Not monotonic like cumulative harvest
        assert (live_c_series >= 0).all(), "Live carbon should be non-negative"
        assert live_c_series[-1] > 0, "Should have live carbon at end"

        print("\n✓ All extraction tests passed!")
        print(f"  Cumulative harvest: {cumulative_harvest:.1f} bdft/ac")
        print(f"  Final total carbon: {final_total_c:.1f} tons/ac")
        print("  Results consistent with Assignment 5 notebook")


class TestBatchExecution:
    """Test full Monte Carlo batch execution with parallel processing."""

    def test_small_batch(self, test_data, output_base):
        """Run a small Monte Carlo batch to verify parallel execution works end-to-end."""
        from fvs_tools.config import FVSSimulationConfig
        from fvs_tools.monte_carlo import MonteCarloConfig, UniformParameterSpec
        from fvs_tools.monte_carlo.executor import run_monte_carlo_batch

        stands, trees = test_data
        batch_output = output_base / "batch_test"
        batch_output.mkdir(exist_ok=True)

        # Create a very small batch: 3 samples, 2 workers, 20 years
        base_config = FVSSimulationConfig(
            name="batch_test_base",
            num_years=20,
            cycle_length=10,
        )

        mc_config = MonteCarloConfig(
            batch_seed=42,
            n_samples=3,
            n_workers=2,
            parameter_specs=[
                UniformParameterSpec("thin_q_factor", 1.5, 2.5),
                UniformParameterSpec("mortality_multiplier", 0.8, 1.2),
            ],
            base_config=base_config,
        )

        # Run batch
        print(f"\n{'='*70}")
        print("Testing Monte Carlo batch execution")
        print(f"{'='*70}\n")

        results_db_path = run_monte_carlo_batch(mc_config, stands, trees, batch_output)

        # Verify database exists
        assert results_db_path.exists()
        print(f"✓ Results database created: {results_db_path}")

        # Check database contents
        import sqlite3

        conn = sqlite3.connect(results_db_path)

        # Check batch metadata
        cursor = conn.execute("SELECT * FROM MC_BatchMeta")
        batch_meta = cursor.fetchone()
        assert batch_meta is not None
        print(f"✓ Batch metadata written (batch_id: {batch_meta[0]})")

        # Check run registry
        cursor = conn.execute("SELECT COUNT(*) FROM MC_RunRegistry")
        num_runs = cursor.fetchone()[0]
        assert num_runs == 3, f"Expected 3 runs, got {num_runs}"
        print(f"✓ Run registry has {num_runs} runs")

        # Check successful runs
        cursor = conn.execute(
            "SELECT COUNT(*) FROM MC_RunRegistry WHERE status='complete'"
        )
        num_complete = cursor.fetchone()[0]
        print(f"✓ {num_complete}/{num_runs} runs completed successfully")
        assert num_complete >= 2, "At least 2/3 runs should succeed"

        # Check summary metrics
        cursor = conn.execute("SELECT COUNT(*) FROM MC_RunSummary")
        num_summaries = cursor.fetchone()[0]
        assert num_summaries == num_complete
        print(f"✓ {num_summaries} run summaries written")

        # Verify metrics are reasonable
        cursor = conn.execute(
            "SELECT cumulative_harvest_bdft, final_total_carbon FROM MC_RunSummary"
        )
        for harvest, carbon in cursor:
            # 20 years may not have harvest events, so just check >= 0
            assert harvest >= 0, f"Harvest should be non-negative, got {harvest}"
            assert carbon > 0, f"Carbon should be positive, got {carbon}"
        print("✓ All summary metrics are reasonable (harvest >= 0, carbon > 0)")

        # Check time series
        cursor = conn.execute("SELECT COUNT(*) FROM MC_TimeSeries")
        num_ts_rows = cursor.fetchone()[0]
        # Each run should have ~2 cycles = 2 rows
        assert (
            num_ts_rows >= num_complete * 2
        ), f"Expected at least {num_complete*2} time series rows, got {num_ts_rows}"
        print(f"✓ {num_ts_rows} time series rows written")

        conn.close()

        print(f"\n{'='*70}")
        print("✓ Batch execution integration test passed!")
        print(f"{'='*70}\n")
