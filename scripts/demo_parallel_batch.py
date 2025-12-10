#!/usr/bin/env python
"""
Demo script to visualize parallel Monte Carlo batch execution.

Run this script and watch CPU usage with:
    htop
    # or
    watch -n 0.5 'ps aux | grep FVSiec | grep -v grep | wc -l'

Usage:
    cd /workspaces/fors591
    uv run python scripts/demo_parallel_batch.py

Configuration mirrors Assignment 5:
- Section 6 plots: [99, 100, 101, 293, 294, 295, 296, 297]
- 100 years with 10-year cycles
- Harvesting with Q-factor thinning

Expected behavior:
- With 4 workers, you should see 4 FVS processes running simultaneously
- Each run takes ~2-5 seconds per stand
- With 8 stands × 50 samples = ~400 FVS stand simulations
- Wall time should be roughly: (400 simulations × 3s) / 4 workers ≈ 5 minutes
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
    BooleanParameterSpec,
    run_monte_carlo_batch,
    load_mc_results,
)


def main():
    """Run a parallel Monte Carlo batch to demonstrate CPU usage."""

    # Configuration - adjust these to change scale
    N_SAMPLES = 50  # Number of parameter samples (enough for good coverage)
    N_WORKERS = 4  # Number of parallel workers (adjust based on your CPU)
    NUM_YEARS = 100  # Projection length (same as Assignment 5)
    CYCLE_LENGTH = 10  # 10 cycles (same as Assignment 5)

    # Section 6 plots from Assignment 5 (NOT 102-106!)
    PLOT_IDS = [99, 100, 101, 293, 294, 295, 296, 297]
    N_STANDS = len(PLOT_IDS)

    print("=" * 70)
    print("MONTE CARLO PARALLEL EXECUTION DEMO")
    print("=" * 70)
    print("\nConfiguration:")
    print(f"  Samples:     {N_SAMPLES}")
    print(f"  Workers:     {N_WORKERS}")
    print(f"  Stands:      {N_STANDS}")
    print(f"  Years:       {NUM_YEARS}")
    print(f"  Cycles:      {NUM_YEARS // CYCLE_LENGTH}")
    print(
        f"\nExpected FVS runs: {N_SAMPLES} samples × {N_STANDS} stands = {N_SAMPLES * N_STANDS} stand simulations"
    )
    print(
        f"Expected duration: ~{(N_SAMPLES * N_STANDS * 3) // N_WORKERS // 60} minutes"
    )
    print("\n" + "=" * 70)
    print("TIP: Open another terminal and run:")
    print("  htop")
    print("  # or")
    print("  watch -n 0.5 'ps aux | grep FVSiec | head -10'")
    print("=" * 70 + "\n")

    input("Press Enter to start the batch run...")

    # Load data
    print("\nLoading stand and tree data...")
    stands = fvs.load_stands()
    trees = fvs.load_trees()

    # Get carbon plots and validate
    carbon_plot_ids = fvs.get_carbon_plot_ids(stands)
    print(f"Total carbon plots available: {len(carbon_plot_ids)}")

    # Filter to requested plots (subset of carbon plots)
    print(f"Requested plots: {PLOT_IDS}")
    stands, trees = fvs.filter_by_plot_ids(stands, trees, PLOT_IDS)

    # Validate stands have trees
    stands, trees, report = fvs.validate_stands(stands, trees)
    if report["excluded_stands"]:
        fvs.print_validation_report(report)
    print(f"Valid stands for simulation: {len(stands)}")

    # Create base FVS configuration - similar to Assignment 5 harv1
    # This includes the harvesting parameters that will trigger thinning
    base_config = FVSSimulationConfig(
        name="parallel_demo",
        num_years=NUM_YEARS,
        cycle_length=CYCLE_LENGTH,
        # Assignment 5 harvesting defaults (some will be overridden by MC sampling)
        thin_q_factor=2.0,  # Will be varied
        thin_residual_ba=65.0,  # Will be varied (60-80)
        thin_trigger_ba=100.0,  # Will be varied
        thin_min_dbh=2.0,
        thin_max_dbh=24.0,
        min_harvest_volume=4500.0,  # Will be varied
    )

    # Create Monte Carlo configuration with 4 varying parameters
    # These mirror the key sensitivity parameters from Assignment 5
    mc_config = MonteCarloConfig(
        batch_seed=42,
        n_samples=N_SAMPLES,
        n_workers=N_WORKERS,
        plot_ids=PLOT_IDS,
        parameter_specs=[
            # Parameter 1: Thinning Q-factor (Assignment 5 uses 2.0)
            UniformParameterSpec("thin_q_factor", 1.5, 2.5),
            # Parameter 2: Mortality multiplier (sensitivity to mortality rates)
            UniformParameterSpec("mortality_multiplier", 0.8, 1.2),
            # Parameter 3: Thinning residual BA (Assignment 5 uses 65)
            # Lower values = more harvesting
            UniformParameterSpec("thin_residual_ba", 60.0, 80.0),
            # Parameter 4: Minimum harvest volume (Assignment 5 uses 4500)
            # Lower values = easier to trigger harvest
            UniformParameterSpec("min_harvest_volume", 3000.0, 6000.0),
        ],
        base_config=base_config,
    )

    # Output directory
    output_dir = Path("outputs/parallel_demo")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Track timing
    start_time = time.time()

    # Run the batch
    print("\n" + "=" * 70)
    print("STARTING PARALLEL BATCH EXECUTION")
    print("Watch your CPU usage now!")
    print("=" * 70 + "\n")

    results_db = run_monte_carlo_batch(
        mc_config,
        stands,
        trees,
        output_dir,
    )

    elapsed = time.time() - start_time

    # Load and summarize results
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    results = load_mc_results(results_db)
    registry = results["registry"]
    summary = results["summary"]
    timeseries = results["timeseries"]

    print("\nExecution Statistics:")
    print(f"  Total wall time:    {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print(f"  Runs completed:     {len(summary)}/{N_SAMPLES}")
    print(f"  Runs per second:    {len(summary)/elapsed:.2f}")
    print(f"  Parallel speedup:   ~{N_WORKERS}x theoretical")

    if len(summary) > 0:
        print(f"\nOutput Metrics (across {len(summary)} runs):")
        print("  Cumulative Harvest:")
        print(f"    Mean:   {summary['cumulative_harvest_bdft'].mean():.1f} bdft/ac")
        print(f"    Std:    {summary['cumulative_harvest_bdft'].std():.1f} bdft/ac")
        print(
            f"    Range:  {summary['cumulative_harvest_bdft'].min():.1f} - {summary['cumulative_harvest_bdft'].max():.1f}"
        )

        print("  Final Total Carbon:")
        print(f"    Mean:   {summary['final_total_carbon'].mean():.1f} tons/ac")
        print(f"    Std:    {summary['final_total_carbon'].std():.1f} tons/ac")
        print(
            f"    Range:  {summary['final_total_carbon'].min():.1f} - {summary['final_total_carbon'].max():.1f}"
        )

    print(f"\nResults database: {results_db}")
    print(f"Run directories:  {output_dir}/run_*/")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)

    return results_db


if __name__ == "__main__":
    main()
