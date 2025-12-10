#!/usr/bin/env python3
"""
Large-scale Monte Carlo batch simulation for Assignment 5.

This script runs 50 Monte Carlo samples with parameter variation around
the Assignment 5 baseline configuration (harv1 treatment).

Parameter Ranges (Assignment5 baseline in parentheses):
- thin_q_factor: 1.5 - 2.5 (baseline: 2.0) ± 25%
- thin_residual_ba: 50 - 80 (baseline: 65)
- thin_trigger_ba: 90 - 120 (baseline: 100)
- mortality_multiplier: 0.8 - 1.2 (baseline: 1.0) ± 20%

Output: outputs/large_mc/mc_results.db
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import fvs_tools as fvs
from fvs_tools import FVSSimulationConfig
from fvs_tools.monte_carlo import (
    MonteCarloConfig,
    UniformParameterSpec,
    run_monte_carlo_batch,
)

# Configuration
N_SAMPLES = 100
N_WORKERS = 20
NUM_YEARS = 100
OUTPUT_DIR = Path(__file__).parent.parent / "outputs" / "large_mc"

# Input data
DATA_DIR = Path(__file__).parent.parent / "data"
TREE_FILE = DATA_DIR / "FVS_Lubrecht_2023_FVS_FVS_TreeInit.csv"
STAND_FILE = DATA_DIR / "FVS_Lubrecht_2023_FVS_StandInit.csv"


def main():
    """Run large Monte Carlo batch."""
    print("=" * 70)
    print("Large-Scale Monte Carlo Simulation")
    print("=" * 70)
    print(f"Samples: {N_SAMPLES}")
    print(f"Workers: {N_WORKERS}")
    print(f"Years: {NUM_YEARS}")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 70)

    start_time = time.time()

    # Load input data
    tree_df = fvs.load_trees(TREE_FILE)
    stand_df = fvs.load_stands(STAND_FILE)

    # Assignment 5 baseline configuration (harv1 treatment)
    base_config = FVSSimulationConfig(
        name="large_mc",
        num_years=NUM_YEARS,
        cycle_length=10,
        output_treelist=True,
        output_carbon=True,
        compute_canopy_cover=True,
        # Management Parameters (Assignment 5 harv1 baseline)
        thin_q_factor=2.0,
        thin_residual_ba=65.0,
        thin_trigger_ba=100.0,
        thin_min_dbh=2.0,
        thin_max_dbh=24.0,
        min_harvest_volume=4500.0,
    )

    # Monte Carlo configuration with parameter ranges
    mc_config = MonteCarloConfig(
        batch_seed=42,
        n_samples=N_SAMPLES,
        n_workers=N_WORKERS,
        parameter_specs=[
            UniformParameterSpec(name="thin_q_factor", min_value=1.5, max_value=2.5),
            UniformParameterSpec(
                name="thin_residual_ba", min_value=50.0, max_value=75.0
            ),
            UniformParameterSpec(
                name="thin_trigger_ba", min_value=95.0, max_value=125.0
            ),
            UniformParameterSpec(
                name="mortality_multiplier", min_value=0.8, max_value=1.2
            ),
            UniformParameterSpec(
                name="min_harvest_volume", min_value=3500.0, max_value=5500.0
            ),
        ],
        base_config=base_config,
    )

    # Run batch
    run_monte_carlo_batch(
        mc_config=mc_config,
        stands=stand_df,
        trees=tree_df,
        output_dir=OUTPUT_DIR,
    )

    elapsed = time.time() - start_time
    print("=" * 70)
    print(f"Batch complete in {elapsed/60:.1f} minutes")
    print(f"Results: {OUTPUT_DIR / 'mc_results.db'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
