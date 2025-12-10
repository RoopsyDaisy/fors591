"""
Batch simulation orchestration.

Run FVS on multiple stands and aggregate results.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import FVSSimulationConfig
from .data_loader import get_stand_trees
from .keyword_builder import build_keyword_file
from .output_parser import (
    extract_calibration_stats,
    get_carbon_table,
    get_compute_table,
    get_harvest_carbon_table,
    get_summary_table,
    summarize_by_year,
)
from .runner import check_fvs_errors, run_fvs
from .tree_file import write_tree_file


def _write_batch_registry(
    output_base: Path,
    batch_id: str,
    run_records: list[dict],
) -> Path:
    """
    Write batch run registry to SQLite database.

    Creates a table mapping (batch_id, run_index) to run parameters
    for later cross-referencing with results.

    Args:
        output_base: Base output directory
        batch_id: Unique batch identifier
        run_records: List of dicts with run metadata

    Returns:
        Path to the registry database
    """
    db_path = output_base / "batch_registry.db"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create registry table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS run_registry (
            batch_id          TEXT NOT NULL,
            run_index         INTEGER NOT NULL,
            stand_id          TEXT,
            config_name       TEXT,
            num_years         INTEGER,
            cycle_length      INTEGER,
            thin_q_factor     REAL,
            thin_residual_ba  REAL,
            thin_trigger_ba   REAL,
            thin_min_dbh      REAL,
            thin_max_dbh      REAL,
            min_harvest_volume REAL,
            output_dir        TEXT,
            success           INTEGER,
            error_message     TEXT,
            created_at        TEXT,
            PRIMARY KEY (batch_id, run_index)
        )
    """
    )

    # Insert records
    for record in run_records:
        cursor.execute(
            """
            INSERT OR REPLACE INTO run_registry (
                batch_id, run_index, stand_id, config_name,
                num_years, cycle_length,
                thin_q_factor, thin_residual_ba, thin_trigger_ba,
                thin_min_dbh, thin_max_dbh, min_harvest_volume,
                output_dir, success, error_message, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["batch_id"],
                record["run_index"],
                record["stand_id"],
                record["config_name"],
                record["num_years"],
                record["cycle_length"],
                record.get("thin_q_factor"),
                record.get("thin_residual_ba"),
                record.get("thin_trigger_ba"),
                record.get("thin_min_dbh"),
                record.get("thin_max_dbh"),
                record.get("min_harvest_volume"),
                record["output_dir"],
                1 if record["success"] else 0,
                record.get("error_message"),
                record["created_at"],
            ),
        )

    conn.commit()
    conn.close()

    return db_path


def run_single_stand(
    stand: pd.Series,
    trees: pd.DataFrame,
    config: FVSSimulationConfig,
    output_dir: Path,
    use_database: bool = False,
    input_database: Path | None = None,
) -> dict:
    """
    Run FVS simulation for a single stand.

    Args:
        stand: Series with stand attributes
        trees: DataFrame with trees for this stand
        config: Simulation configuration
        output_dir: Directory for outputs
        use_database: If True, use database input instead of tree files
        input_database: Path to FVS input database (required if use_database=True)

    Returns:
        Dictionary with:
            - stand_id: Stand identifier
            - success: Boolean indicating successful run
            - summary: Summary DataFrame
            - carbon: Carbon DataFrame
            - compute: Computed variables DataFrame
            - calibration: Calibration statistics dict
            - errors: List of error messages
    """
    stand_id = str(stand["STAND_ID"])
    stand_dir = output_dir / stand_id
    stand_dir.mkdir(parents=True, exist_ok=True)

    # Set start year from stand's inventory year for target_end_year calculation
    inv_year = int(stand.get("INV_YEAR", 2023))
    config._start_year = inv_year

    # Create input files
    key_file = stand_dir / "run.key"

    try:
        if use_database:
            # Use database input
            if input_database is None:
                raise ValueError(
                    "input_database must be provided when use_database=True"
                )

            # Write keyword file with database reference
            build_keyword_file(
                stand, "FVS_Data.db", config, key_file, use_database=True
            )

            # Run FVS with database input
            result = run_fvs(
                key_file, stand_dir, config.fvs_binary, input_database=input_database
            )
        else:
            # Use tree file input (original method)
            tree_file = stand_dir / "run.tre"

            # Write tree list
            write_tree_file(trees, stand, tree_file)

            # Write keyword file
            build_keyword_file(stand, "run.tre", config, key_file, use_database=False)

            # Run FVS
            result = run_fvs(key_file, stand_dir, config.fvs_binary)

        if not result["success"]:
            errors = check_fvs_errors(stand_dir)
            return {
                "stand_id": stand_id,
                "success": False,
                "errors": errors,
                "exit_code": result["exit_code"],
            }

        # Parse outputs, filtering to target_end_year (removes extra cycle data)
        db_path = stand_dir / "FVSOut.db"
        max_year = config.target_end_year

        summary = get_summary_table(db_path, max_year=max_year)
        carbon = get_carbon_table(db_path, max_year=max_year)
        harvest_carbon = get_harvest_carbon_table(db_path, max_year=max_year)
        compute = get_compute_table(db_path, max_year=max_year)
        calibration = extract_calibration_stats(db_path)
        errors = check_fvs_errors(stand_dir)

        return {
            "stand_id": stand_id,
            "success": True,
            "summary": summary,
            "carbon": carbon,
            "harvest_carbon": harvest_carbon,
            "compute": compute,
            "calibration": calibration,
            "errors": errors,
        }

    except Exception as e:
        return {
            "stand_id": stand_id,
            "success": False,
            "errors": [str(e)],
        }


def run_batch_simulation(
    stands: pd.DataFrame,
    trees: pd.DataFrame,
    config: FVSSimulationConfig,
    output_base: Path,
    use_database: bool = False,
    input_database: Path | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Run FVS simulations for multiple stands and aggregate results.

    Args:
        stands: DataFrame with stand records
        trees: DataFrame with all tree records
        config: Simulation configuration
        output_base: Base directory for all outputs
        use_database: If True, use database input instead of tree files
        input_database: Path to FVS input database (required if use_database=True)

    Returns:
        Dictionary with aggregated results:
            - batch_id: Unique identifier for this batch run
            - summary_all: Combined summary data for all stands
            - carbon_all: Combined carbon data for all stands
            - compute_all: Combined computed variables for all stands
            - calibration_stats: Calibration statistics by stand
            - run_status: Status of each stand run
            - registry_db: Path to batch registry database
    """
    output_base = Path(output_base)
    output_base.mkdir(parents=True, exist_ok=True)

    # Use batch ID from config if provided, otherwise auto-generate
    if config.batch_id:
        batch_id = config.batch_id
    else:
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    results = []
    run_records = []  # For batch registry
    all_summaries = []
    all_carbon = []
    all_harvest_carbon = []
    all_compute = []
    calibration_by_stand = {}

    print(f"\nRunning {len(stands)} stands with configuration: {config.name}")
    print(f"Batch ID: {batch_id}")
    print(f"Projection: {config.num_years} years ({config.num_cycles} cycles)")
    print(f"Output directory: {output_base}")
    print()

    for idx, (_, stand) in enumerate(stands.iterrows()):
        stand_id = str(stand["STAND_ID"])
        run_index = idx  # 0-based index within batch

        # Set batch tracking on config
        config.batch_id = batch_id
        config.run_index = run_index

        # Get trees for this stand
        try:
            stand_trees = get_stand_trees(stand_id, trees)
        except ValueError as e:
            print(f"[{run_index + 1}/{len(stands)}] {stand_id}: ERROR - {e}")
            results.append(
                {
                    "stand_id": stand_id,
                    "success": False,
                    "error": str(e),
                }
            )
            # Add to registry even on failure
            run_records.append(
                {
                    "batch_id": batch_id,
                    "run_index": run_index,
                    "stand_id": stand_id,
                    "config_name": config.name,
                    "num_years": config.num_years,
                    "cycle_length": config.cycle_length,
                    "thin_q_factor": config.thin_q_factor,
                    "thin_residual_ba": config.thin_residual_ba,
                    "thin_trigger_ba": config.thin_trigger_ba,
                    "thin_min_dbh": (
                        config.thin_min_dbh if config.thin_min_dbh != 0.0 else None
                    ),
                    "thin_max_dbh": (
                        config.thin_max_dbh if config.thin_max_dbh != 999.0 else None
                    ),
                    "min_harvest_volume": config.min_harvest_volume,
                    "output_dir": str(output_base / stand_id),
                    "success": False,
                    "error_message": str(e),
                    "created_at": datetime.now().isoformat(),
                }
            )
            continue

        # Run simulation
        result = run_single_stand(
            stand, stand_trees, config, output_base, use_database, input_database
        )

        if result["success"]:
            print(f"[{run_index + 1}/{len(stands)}] {stand_id}: ✓", flush=True)

            # Collect outputs
            if result.get("summary") is not None:
                all_summaries.append(result["summary"])

            if result.get("carbon") is not None:
                all_carbon.append(result["carbon"])

            if result.get("compute") is not None:
                all_compute.append(result["compute"])

            if result.get("harvest_carbon") is not None:
                all_harvest_carbon.append(result["harvest_carbon"])

            if result.get("calibration") is not None:
                calibration_by_stand[stand_id] = result["calibration"]
        else:
            print(
                f"[{run_index + 1}/{len(stands)}] {stand_id}: ✗ - {result.get('errors', ['Unknown error'])}",
                flush=True,
            )

        results.append(
            {
                "stand_id": stand_id,
                "success": result["success"],
                "errors": result.get("errors", []),
            }
        )

        # Add to registry
        run_records.append(
            {
                "batch_id": batch_id,
                "run_index": run_index,
                "stand_id": stand_id,
                "config_name": config.name,
                "num_years": config.num_years,
                "cycle_length": config.cycle_length,
                "thin_q_factor": config.thin_q_factor,
                "thin_residual_ba": config.thin_residual_ba,
                "thin_trigger_ba": config.thin_trigger_ba,
                "thin_min_dbh": (
                    config.thin_min_dbh if config.thin_min_dbh != 0.0 else None
                ),
                "thin_max_dbh": (
                    config.thin_max_dbh if config.thin_max_dbh != 999.0 else None
                ),
                "min_harvest_volume": config.min_harvest_volume,
                "output_dir": str(output_base / stand_id),
                "success": result["success"],
                "error_message": (
                    "; ".join(result.get("errors", []))
                    if not result["success"]
                    else None
                ),
                "created_at": datetime.now().isoformat(),
            }
        )

    # Aggregate results
    aggregated = {}

    if all_summaries:
        aggregated["summary_all"] = pd.concat(all_summaries, ignore_index=True)

    if all_carbon:
        aggregated["carbon_all"] = pd.concat(all_carbon, ignore_index=True)

    if all_compute:
        aggregated["compute_all"] = pd.concat(all_compute, ignore_index=True)

    if all_harvest_carbon:
        aggregated["harvest_carbon_all"] = pd.concat(
            all_harvest_carbon, ignore_index=True
        )

    if calibration_by_stand:
        # Calibration data is now DataFrames, so concatenate them
        all_calib = []
        for _stand_id, calib_df in calibration_by_stand.items():
            if calib_df is not None and isinstance(calib_df, pd.DataFrame):
                all_calib.append(calib_df)
        if all_calib:
            aggregated["calibration_stats"] = pd.concat(all_calib, ignore_index=True)

    # Run status
    aggregated["run_status"] = pd.DataFrame(results)

    # Write batch registry
    registry_db = _write_batch_registry(output_base, batch_id, run_records)
    aggregated["batch_id"] = batch_id
    aggregated["registry_db"] = registry_db

    # Print summary
    print()
    print("=" * 60)
    successful = sum(1 for r in results if r["success"])
    print(f"Batch ID: {batch_id}")
    print(f"Completed: {successful}/{len(results)} stands successful")
    print(f"Registry: {registry_db}")
    print("=" * 60)

    return aggregated


def aggregate_by_period(
    summary_df: pd.DataFrame,
    carbon_df: pd.DataFrame | None = None,
    compute_df: pd.DataFrame | None = None,
    harvest_carbon_df: pd.DataFrame | None = None,
    years_per_period: int = 10,
) -> pd.DataFrame:
    """
    Aggregate results by time period across all stands.

    Computes mean values across stands for each time period.

    Args:
        summary_df: Combined summary data
        carbon_df: Combined carbon data (optional)
        compute_df: Combined computed variables (optional)
        harvest_carbon_df: Combined harvest carbon data (optional)
        years_per_period: Years per aggregation period

    Returns:
        DataFrame with average metrics by period
    """
    # Combine all data
    combined = summarize_by_year(summary_df, carbon_df, compute_df)

    # Build aggregation dict based on available columns
    # FVS uses mixed case: Tpa, BA, TCuFt, MCuFt, BdFt, CCF, RBdFt
    agg_dict = {}

    for col in [
        "BA",
        "Tpa",
        "TCuFt",
        "MCuFt",
        "BdFt",
        "CCF",
        "RBdFt",
        "Cumulative_RBdFt",
    ]:
        if col in combined.columns:
            agg_dict[col] = "mean"

    # Group by year and compute means
    result = combined.groupby("Year").agg(agg_dict)

    # Rename Tpa to TPA for consistency
    if "Tpa" in result.columns:
        result = result.rename(columns={"Tpa": "TPA"})

    # Add carbon if available (handle different column name variations)
    carbon_col = None
    for col_name in [
        "Aboveground_Total_Live",
        "Above_Ground_Total_Live",
        "Aboveground_C_Live",
    ]:
        if col_name in combined.columns:
            carbon_col = col_name
            break
    if carbon_col:
        result["Aboveground_C_Live"] = combined.groupby("Year")[carbon_col].mean()

    if "Standing_Dead" in combined.columns:
        result["Standing_Dead_C"] = combined.groupby("Year")["Standing_Dead"].mean()

    # Add canopy cover if available (handle different column name variations)
    canopy_col = None
    for col_name in ["PC_CAN_C", "Pc_can_cover", "CanopyCov", "Canopy_Cover_Pct"]:
        if col_name in combined.columns:
            canopy_col = col_name
            break
    if canopy_col:
        result["Canopy_Cover_Pct"] = combined.groupby("Year")[canopy_col].mean()

    # Add harvest carbon (merchantable carbon stored in wood products)
    if harvest_carbon_df is not None and len(harvest_carbon_df) > 0:
        # Look for Merch_Carbon_Stored column (carbon in long-term wood products)
        if "Merch_Carbon_Stored" in harvest_carbon_df.columns:
            hrv_agg = harvest_carbon_df.groupby("Year")["Merch_Carbon_Stored"].mean()
            result = result.join(hrv_agg.rename("Merch_Carbon_Stored"), how="left")
            result["Merch_Carbon_Stored"] = result["Merch_Carbon_Stored"].fillna(0)

    result = result.reset_index()

    return result


def collect_batch_errors(
    output_base: Path,
    stand_ids: list[str] | None = None,
) -> pd.DataFrame:
    """
    Collect all FVS error messages from simulations in a batch.

    Scans all stand output directories for FVS_Error tables and
    aggregates them into a single DataFrame. Handles the case where
    successful runs don't have an FVS_Error table (this is good!).

    Args:
        output_base: Base output directory containing stand subdirectories
        stand_ids: Optional list of stand IDs to check. If None, scans all
                   subdirectories that contain FVSOut.db files.

    Returns:
        DataFrame with columns: StandID, Message, (and any other FVS_Error columns)
        Returns empty DataFrame if no errors found (good news!).

    Example:
        >>> errors = fvs.collect_batch_errors(output_dir)
        >>> if errors.empty:
        ...     print("No errors - all runs successful!")
        >>> else:
        ...     print(f"Found {len(errors)} error messages")
        ...     print(errors)
    """
    output_base = Path(output_base)
    all_errors = []

    # Find all stand directories to check
    if stand_ids is not None:
        dirs_to_check = [output_base / sid for sid in stand_ids]
    else:
        # Scan for directories containing FVSOut.db
        dirs_to_check = [
            d
            for d in output_base.iterdir()
            if d.is_dir() and (d / "FVSOut.db").exists()
        ]

    for stand_dir in dirs_to_check:
        db_path = stand_dir / "FVSOut.db"
        if not db_path.exists():
            continue

        stand_id = stand_dir.name

        try:
            conn = sqlite3.connect(str(db_path))

            # Check if FVS_Error table exists
            tables = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='FVS_Error'",
                conn,
            )

            if len(tables) > 0:
                # Table exists - read errors
                errors_df = pd.read_sql_query("SELECT * FROM FVS_Error", conn)
                if len(errors_df) > 0:
                    errors_df["StandID"] = stand_id
                    all_errors.append(errors_df)

            conn.close()

        except Exception as e:
            # Log but don't fail - we want to collect all errors we can
            print(f"Warning: Could not read errors from {stand_id}: {e}", flush=True)

    if all_errors:
        result = pd.concat(all_errors, ignore_index=True)
        # Reorder columns to put StandID first
        cols = ["StandID"] + [c for c in result.columns if c != "StandID"]
        return result[cols]
    else:
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=["StandID", "Message"])
