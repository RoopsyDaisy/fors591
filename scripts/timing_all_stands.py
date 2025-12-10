#!/usr/bin/env python
"""
Timing test: Run 1 sample across all 268 valid carbon stands with 20 workers.

This script measures the wall-clock time to run a single Monte Carlo sample
across all valid carbon plots in the Lubrecht dataset.

Expected:
- 1 batch ID (single MC batch)
- 1 run ID (single parameter sample)
- 268 stand IDs (all valid carbon plots)

Usage:
    cd /workspaces/fors591
    uv run python scripts/timing_all_stands.py

Monitor with:
    htop
    # or
    watch -n 0.5 'ps aux | grep FVSiec | grep -v grep | wc -l'
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import fvs_tools as fvs
from fvs_tools.config import FVSSimulationConfig
from fvs_tools.monte_carlo import (
    MonteCarloConfig,
    UniformParameterSpec,
    run_monte_carlo_batch,
    load_mc_results,
)


def main():
    """Run timing test: 1 sample, all stands, 20 workers."""

    # Configuration
    N_SAMPLES = 1  # Single sample only
    N_WORKERS = 20  # Maximum parallelism
    NUM_YEARS = 100  # Full projection
    CYCLE_LENGTH = 10

    print("=" * 70)
    print("TIMING TEST: All Valid Carbon Stands")
    print("=" * 70)

    # Load and validate data
    print("\nLoading and validating data...")
    stands = fvs.load_stands()
    trees = fvs.load_trees()

    # Get all carbon plots
    carbon_plot_ids = fvs.get_carbon_plot_ids(stands)
    print(f"Carbon plots found: {len(carbon_plot_ids)}")

    # Filter to carbon plots
    stands, trees = fvs.filter_by_plot_ids(stands, trees, carbon_plot_ids)

    # Validate (exclude empty stands)
    stands, trees, report = fvs.validate_stands(stands, trees)
    if report["excluded_stands"]:
        print(f"\nExcluded {len(report['excluded_stands'])} stands with no trees:")
        for exc in report["excluded_stands"]:
            print(f"  - {exc['stand_id']}")

    n_stands = len(stands)
    print(f"\nValid stands: {n_stands}")
    print(f"Total trees: {len(trees)}")

    print("\n" + "=" * 70)
    print("Configuration:")
    print(f"  Samples:     {N_SAMPLES}")
    print(f"  Workers:     {N_WORKERS}")
    print(f"  Stands:      {n_stands}")
    print(f"  Years:       {NUM_YEARS}")
    print(f"  Cycles:      {NUM_YEARS // CYCLE_LENGTH}")
    print(
        f"\nTotal FVS stand simulations: {N_SAMPLES} × {n_stands} = {N_SAMPLES * n_stands}"
    )
    print("=" * 70 + "\n")

    # Create base config matching Assignment 5 Part 2 (harv1)
    base_config = FVSSimulationConfig(
        name="timing_test",
        num_years=NUM_YEARS,
        cycle_length=CYCLE_LENGTH,
        output_treelist=True,
        output_carbon=True,
        compute_canopy_cover=True,
        # Management Parameters (Assignment 5 harv1)
        thin_q_factor=2.0,
        thin_residual_ba=65.0,
        thin_trigger_ba=100.0,
        thin_min_dbh=2.0,
        thin_max_dbh=24.0,
        min_harvest_volume=4500.0,
    )

    # Create MC config - single parameter just to have something to vary
    # Using a very narrow range so it's essentially fixed
    mc_config = MonteCarloConfig(
        batch_seed=42,
        n_samples=N_SAMPLES,
        n_workers=N_WORKERS,
        # Don't specify plot_ids - we already filtered the data
        parameter_specs=[
            # Minimal variation - just need one parameter
            UniformParameterSpec("thin_q_factor", 2.0, 2.01),
        ],
        base_config=base_config,
    )

    print(f"Batch ID: {mc_config.batch_id}")
    print(f"Run ID: 0 (single sample)\n")

    # Output directory
    output_dir = Path("outputs/timing_all_stands")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run with timing
    print("=" * 70)
    print("STARTING TIMING RUN")
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    start_time = time.time()

    results_db = run_monte_carlo_batch(
        mc_config,
        stands,
        trees,
        output_dir,
    )

    elapsed = time.time() - start_time

    # Results
    print("\n" + "=" * 70)
    print("TIMING RESULTS")
    print("=" * 70)

    results = load_mc_results(results_db)
    summary = results["summary"]

    print(f"\nEnd time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nTotal wall time: {elapsed:.1f} seconds ({elapsed/60:.2f} minutes)")
    print(f"Stands processed: {n_stands}")
    print(f"Average time per stand: {elapsed/n_stands:.2f} seconds")
    print(f"Effective parallelism: {n_stands / elapsed:.1f} stands/second")

    if len(summary) > 0:
        print(f"\nCarbon Summary (across {n_stands} stands):")
        print(
            f"  Mean final carbon: {summary['final_total_carbon'].mean():.1f} tons/ac"
        )

    print(f"\nResults database: {results_db}")
    print(f"Batch ID: {mc_config.batch_id}")

    print("\n" + "=" * 70)
    print("TIMING TEST COMPLETE")
    print("=" * 70)

    return results_db, elapsed


if __name__ == "__main__":
    main()
