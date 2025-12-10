"""
Parallel execution engine for Monte Carlo FVS batch simulations.

This module orchestrates parallel FVS runs across multiple worker processes,
collecting results and writing to the Monte Carlo database.
"""

from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from ..batch import run_batch_simulation
from ..config import FVSSimulationConfig
from ..db_input import create_fvs_input_db
from .config import MonteCarloConfig
from .database import (
    create_mc_database,
    update_batch_status,
    update_run_status,
    write_batch_error,
    write_batch_meta,
    write_run_registry,
    write_run_summary,
    write_time_series,
)
from .outputs import extract_run_summary, extract_time_series
from .sampler import generate_parameter_samples

# Mapping from Monte Carlo parameter names to FVSSimulationConfig attributes
MC_TO_FVS_PARAM_MAP = {
    # Management parameters
    "thin_q_factor": "thin_q_factor",
    "thin_residual_ba": "thin_residual_ba",
    "thin_trigger_ba": "thin_trigger_ba",
    "min_harvest_volume": "min_harvest_volume",
    "thin_min_dbh": "thin_min_dbh",
    "thin_max_dbh": "thin_max_dbh",
    # Monte Carlo-specific parameters (Phase 3)
    "mortality_multiplier": "mortality_multiplier",
    "enable_calibration": "enable_calibration",
    "fvs_random_seed": "fvs_random_seed",
}


def execute_single_run(
    run_params: dict,
    stands: pd.DataFrame,
    trees: pd.DataFrame,
    base_config: dict,
    output_dir: Path,
    batch_id: str,
) -> dict:
    """
    Execute a single Monte Carlo run (all stands with one parameter set).

    This function is called by worker processes. It:
    1. Creates FVSSimulationConfig with sampled parameters
    2. Runs batch simulation for all stands
    3. Extracts summary and time series
    4. Returns results dict (or error info)

    Args:
        run_params: Sampled parameters including run_id and run_seed
        stands: Stand data
        trees: Tree data
        base_config: Base FVS config (num_years, cycle_length, etc.)
        output_dir: Directory for this run's outputs
        batch_id: Monte Carlo batch identifier to embed in FVS runs

    Returns:
        dict with keys:
            - run_id: int
            - success: bool
            - summary: dict (from extract_run_summary) if success
            - time_series: pd.DataFrame (from extract_time_series) if success
            - error: str | None if failed
    """
    run_id = run_params["run_id"]
    run_dir = output_dir / f"run_{run_id:04d}"
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Build FVS configuration with base settings + sampled parameters
        fvs_config_dict = base_config.copy()

        # Map sampled parameters to FVS config
        for mc_param, fvs_param in MC_TO_FVS_PARAM_MAP.items():
            if mc_param in run_params:
                fvs_config_dict[fvs_param] = run_params[mc_param]

        # Add unique name for this run (includes batch_id for traceability)
        fvs_config_dict["name"] = f"{batch_id}_run_{run_id:04d}"
        # Set batch_id to prevent run_batch_simulation from auto-generating
        fvs_config_dict["batch_id"] = batch_id

        # Create FVS configuration
        fvs_config = FVSSimulationConfig(**fvs_config_dict)

        # Create input database for this run
        input_db = run_dir / "FVS_Data.db"
        create_fvs_input_db(stands, trees, input_db)

        # Run FVS batch simulation
        results = run_batch_simulation(
            stands=stands,
            trees=trees,
            config=fvs_config,
            output_base=run_dir,
            use_database=True,
            input_database=input_db,
        )

        # Check if any runs failed
        if not results["run_status"]["success"].all():
            failed = results["run_status"][~results["run_status"]["success"]]
            error_msg = f"{len(failed)} stands failed: {failed['stand_id'].tolist()}"
            return {
                "run_id": run_id,
                "success": False,
                "error": error_msg,
                "summary": None,
                "time_series": None,
            }

        # Extract summary metrics
        summary = extract_run_summary(results)

        # Extract time series
        time_series = extract_time_series(results)

        return {
            "run_id": run_id,
            "success": True,
            "summary": summary,
            "time_series": time_series,
            "error": None,
        }

    except Exception as e:
        return {
            "run_id": run_id,
            "success": False,
            "error": str(e),
            "summary": None,
            "time_series": None,
        }


def run_monte_carlo_batch(
    mc_config: MonteCarloConfig,
    stands: pd.DataFrame,
    trees: pd.DataFrame,
    output_dir: Path | str,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """
    Execute Monte Carlo batch simulation with parallel workers.

    Args:
        mc_config: Monte Carlo configuration (n_samples, parameter_specs, etc.)
        stands: Stand data (will be filtered by mc_config.plot_ids if set)
        trees: Tree data (will be filtered to match stands)
        output_dir: Directory for FVS outputs and results database
        progress_callback: Optional callback(completed, total) for progress updates

    Returns:
        Path to results SQLite database

    Raises:
        ValueError: If configuration is invalid
        RuntimeError: If all runs fail

    Example:
        >>> results_db = run_monte_carlo_batch(mc_config, stands, trees, "./outputs/mc_run")
        >>> registry, summary, timeseries = load_mc_results(results_db)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Filter stands if plot_ids specified
    if mc_config.plot_ids is not None:
        from ..data_loader import filter_by_plot_ids

        stands, trees = filter_by_plot_ids(stands, trees, mc_config.plot_ids)

    # Validate stands have trees (excludes empty stands with warning)
    from ..data_loader import validate_stands

    stands, trees, validation_report = validate_stands(stands, trees)
    if validation_report["excluded_stands"]:
        excluded = validation_report["excluded_stands"]
        print(f"Warning: Excluding {len(excluded)} stands with no trees:")
        for exc in excluded:
            print(f"  - {exc['stand_id']} (plot {exc['plot_id']})")
        print()

    if len(stands) == 0:
        raise ValueError("No valid stands remaining after validation")

    print(f"\n{'='*70}")
    print("Monte Carlo Batch Execution")
    print(f"{'='*70}")
    print(f"Batch ID: {mc_config.batch_id}")
    print(f"Samples: {mc_config.n_samples}")
    print(f"Workers: {mc_config.n_workers}")
    print(f"Stands: {len(stands)}")
    print(f"Output: {output_dir}")
    print(f"{'='*70}\n")

    # Create results database
    results_db_path = output_dir / "mc_results.db"
    conn = create_mc_database(results_db_path)

    # Write batch metadata
    write_batch_meta(conn, mc_config)

    # Generate parameter samples
    samples = generate_parameter_samples(mc_config)
    print(f"Generated {len(samples)} parameter samples\n")

    # Write run registry (all runs marked as "pending")
    write_run_registry(conn, mc_config.batch_id, samples)

    # Prepare base FVS config dict (shared settings across all runs)
    # Convert FVSSimulationConfig object to dict, filtering out None/private fields
    base_config_obj = mc_config.base_config
    base_config = {
        k: v
        for k, v in asdict(base_config_obj).items()
        if v is not None and not k.startswith("_")
    }

    # Execute runs in parallel
    print(f"Executing {len(samples)} runs with {mc_config.n_workers} workers...\n")

    completed_count = 0
    success_count = 0
    failure_count = 0

    with ProcessPoolExecutor(max_workers=mc_config.n_workers) as executor:
        # Submit all runs
        future_to_run = {
            executor.submit(
                execute_single_run,
                sample,
                stands,
                trees,
                base_config,
                output_dir,
                mc_config.batch_id,
            ): sample
            for sample in samples
        }

        # Process results as they complete
        for future in as_completed(future_to_run):
            sample = future_to_run[future]
            run_id = sample["run_id"]

            try:
                result = future.result()
                completed_count += 1

                if result["success"]:
                    success_count += 1

                    # Update run status
                    update_run_status(
                        conn,
                        mc_config.batch_id,
                        run_id,
                        status="complete",
                    )

                    # Write summary metrics
                    write_run_summary(
                        conn,
                        mc_config.batch_id,
                        run_id,
                        result["summary"],
                    )

                    # Write time series
                    if (
                        result["time_series"] is not None
                        and len(result["time_series"]) > 0
                    ):
                        write_time_series(
                            conn,
                            mc_config.batch_id,
                            run_id,
                            result["time_series"],
                        )

                    print(
                        f"[{completed_count}/{len(samples)}] Run {run_id:04d} "
                        f"✓ - {success_count} successful, {failure_count} failed"
                    )

                else:
                    failure_count += 1

                    # Update run status
                    update_run_status(
                        conn,
                        mc_config.batch_id,
                        run_id,
                        status="failed",
                    )

                    # Log error
                    write_batch_error(
                        conn,
                        mc_config.batch_id,
                        run_id,
                        stand_id=None,
                        error_type="execution_error",
                        error_msg=result["error"],
                    )

                    print(
                        f"[{completed_count}/{len(samples)}] Run {run_id:04d} "
                        f"✗ - {success_count} successful, {failure_count} failed"
                    )
                    print(f"  Error: {result['error']}")

                # Call progress callback if provided
                if progress_callback:
                    progress_callback(completed_count, len(samples))

            except Exception as e:
                failure_count += 1
                completed_count += 1

                # Update status and log error
                update_run_status(
                    conn,
                    mc_config.batch_id,
                    run_id,
                    status="failed",
                )
                write_batch_error(
                    conn,
                    mc_config.batch_id,
                    run_id,
                    stand_id=None,
                    error_type="worker_exception",
                    error_msg=str(e),
                )

                print(
                    f"[{completed_count}/{len(samples)}] Run {run_id:04d} "
                    f"✗ - {success_count} successful, {failure_count} failed"
                )
                print(f"  Exception: {e}")

    # Update batch status
    if success_count == len(samples):
        batch_status = "complete"
    elif success_count > 0:
        batch_status = "partial"
    else:
        batch_status = "failed"

    update_batch_status(conn, mc_config.batch_id, status=batch_status)

    # Close database connection
    conn.close()

    # Print summary
    print(f"\n{'='*70}")
    print("Batch Completion Summary")
    print(f"{'='*70}")
    print(f"Total runs: {len(samples)}")
    print(f"Successful: {success_count} ({success_count/len(samples)*100:.1f}%)")
    print(f"Failed: {failure_count} ({failure_count/len(samples)*100:.1f}%)")
    print(f"Status: {batch_status}")
    print(f"Results: {results_db_path}")
    print(f"{'='*70}\n")

    if success_count == 0:
        raise RuntimeError(
            "All Monte Carlo runs failed. Check batch errors in database."
        )

    return results_db_path
