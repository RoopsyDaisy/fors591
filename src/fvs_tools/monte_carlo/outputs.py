"""
Output extraction for Monte Carlo simulations.

Converts raw FVS batch results into standardized metrics for database storage.

CRITICAL: FVS outputs mix per-period flows and pool balances (cumulative).
- FLOW fields (e.g., RBdFt): Per-period activity. SUM across periods for total.
- POOL fields (e.g., BA, carbon): State at end of period. Use value at time point.

See module constants below for field classification.
"""

from typing import Any

import pandas as pd


# ============================================================================
# Field Semantics Constants
# ============================================================================

# POOL BALANCE fields: Represent state at end of period (stock variables)
# Do NOT cumsum these - use value at specific time point
POOL_FIELDS = {
    "BA",  # Basal area (ft²/ac)
    "Tpa",  # Trees per acre
    "BdFt",  # Standing board feet
    "CCF",  # Crown competition factor
    "TopHt",  # Top height
    "QMD",  # Quadratic mean diameter
    "SDI",  # Stand density index
    "Aboveground_Total_Live",  # Live carbon pool
    "Above_Ground_Total_Live",  # Alternative name
    "Aboveground_C_Live",  # Alternative name
    "Standing_Dead",  # Dead carbon pool
    "Merch_Carbon_Stored",  # Carbon in wood products pool (includes decay)
    "PC_CAN_C",  # Canopy cover percentage
    "Pc_can_cover",  # Alternative name
    "CanopyCov",  # Alternative name
    "Canopy_Cover_Pct",  # Alternative name
}

# FLOW fields: Represent per-period activity (flux variables)
# SUM these across periods to get cumulative total
FLOW_FIELDS = {
    "RBdFt",  # Board feet removed this period
    "RTpa",  # Trees removed this period
    "Mort",  # Mortality this period
    "Acc",  # Accretion this period
}

# Column name variations (FVS output is inconsistent across tables)
CARBON_LIVE_COLS = [
    "Aboveground_Total_Live",
    "Above_Ground_Total_Live",
    "Aboveground_C_Live",
]
CARBON_DEAD_COLS = ["Standing_Dead"]
CANOPY_COLS = ["PC_CAN_C", "Pc_can_cover", "CanopyCov", "Canopy_Cover_Pct"]
HARVEST_FLOW_COLS = ["RBdFt"]  # Per-period flow
STORED_CARBON_COLS = ["Merch_Carbon_Stored"]  # Pool balance


# ============================================================================
# Helper Functions
# ============================================================================


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """
    Find first matching column name from candidates list.

    Args:
        df: DataFrame to search
        candidates: List of possible column names

    Returns:
        First matching column name, or None if no match
    """
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _validate_time_series(ts: pd.DataFrame) -> None:
    """
    Sanity checks on extracted time series.

    Raises:
        ValueError: If data looks incorrect

    Checks:
        - Cumulative harvest is monotonically increasing
        - Carbon pools are non-negative
    """
    # Cumulative harvest should be monotonically increasing
    if "cumulative_harvest" in ts.columns:
        cumul = ts["cumulative_harvest"].dropna()
        if len(cumul) > 1:
            diffs = cumul.diff().dropna()
            if not (diffs >= -0.01).all():  # Allow small numerical errors
                raise ValueError(
                    "cumulative_harvest is not monotonically increasing - "
                    "check that RBdFt is being handled as a flow field"
                )

    # Carbon pools should be non-negative
    for col in ["aboveground_c_live", "standing_dead_c", "total_carbon"]:
        if (
            col in ts.columns and (ts[col] < -0.01).any()
        ):  # Allow small numerical errors
            raise ValueError(f"{col} contains negative values")


# ============================================================================
# Main Extraction Functions
# ============================================================================


def extract_run_summary(results: dict[str, Any]) -> dict[str, float | int | None]:
    """
    Extract scalar summary metrics from FVS batch results.

    Computes aggregate metrics across all stands for storage in MC_RunSummary table.

    CRITICAL: Handles per-period flows (RBdFt) vs pool balances (carbon) correctly:
    - Carbon: Uses final year value (pool balance)
    - Harvest: Sums RBdFt across all years and stands (flow)

    Args:
        results: Dict returned by run_batch_simulation() with keys:
            - summary_all: DataFrame with FVS summary data
            - carbon_all: DataFrame with carbon data (optional)
            - compute_all: DataFrame with canopy cover (optional)
            - harvest_carbon_all: DataFrame with stored carbon (optional)
            - run_status: DataFrame with success/failure status

    Returns:
        Dict with keys matching MC_RunSummary columns:
            - final_total_carbon: Live + dead + stored at final year (tons/ac)
            - avg_carbon_stock: Mean total carbon across all years (tons/ac)
            - final_live_carbon: Live carbon at final year (tons/ac)
            - final_dead_carbon: Dead carbon at final year (tons/ac)
            - final_stored_carbon: Stored carbon at final year (tons/ac)
            - min_canopy_cover: Minimum canopy cover across all years (%)
            - final_canopy_cover: Canopy cover at final year (%)
            - cumulative_harvest_bdft: Total harvest across all years (bdft/ac)
            - n_stands: Number of successful stands

    Example:
        >>> results = fvs.run_batch_simulation(...)
        >>> summary = extract_run_summary(results)
        >>> summary["cumulative_harvest_bdft"]  # Total harvest over simulation
        17234.5
        >>> summary["final_total_carbon"]  # Carbon at end
        38.2
    """
    # Initialize output dict with all required keys
    output = {
        "final_total_carbon": None,
        "avg_carbon_stock": None,
        "final_live_carbon": None,
        "final_dead_carbon": None,
        "final_stored_carbon": None,
        "min_canopy_cover": None,
        "final_canopy_cover": None,
        "cumulative_harvest_bdft": 0.0,
        "n_stands": 0,
    }

    # Count successful stands
    if "run_status" in results:
        output["n_stands"] = int(results["run_status"]["success"].sum())

    # Return early if no data
    if "summary_all" not in results or results["summary_all"] is None:
        return output

    summary_df = results["summary_all"]
    if len(summary_df) == 0:
        return output

    # Import here to avoid circular dependency
    from ..batch import summarize_by_year

    # Combine all data sources
    combined = summarize_by_year(
        summary_df,
        results.get("carbon_all"),
        results.get("compute_all"),
    )

    if len(combined) == 0:
        return output

    # Find final year
    final_year = combined["Year"].max()

    # Extract carbon metrics (POOL BALANCES - use final year)
    live_col = _find_column(combined, CARBON_LIVE_COLS)
    if live_col:
        # Final year: mean across stands
        final_live = combined[combined["Year"] == final_year][live_col].mean()
        output["final_live_carbon"] = float(final_live) if pd.notna(final_live) else 0.0

        # Average over all time
        output["avg_carbon_stock"] = float(combined[live_col].mean())

    dead_col = _find_column(combined, CARBON_DEAD_COLS)
    if dead_col:
        final_dead = combined[combined["Year"] == final_year][dead_col].mean()
        output["final_dead_carbon"] = float(final_dead) if pd.notna(final_dead) else 0.0

    # Stored carbon (POOL BALANCE from separate table)
    if "harvest_carbon_all" in results and results["harvest_carbon_all"] is not None:
        hrv_df = results["harvest_carbon_all"]
        stored_col = _find_column(hrv_df, STORED_CARBON_COLS)
        if stored_col and len(hrv_df) > 0:
            # Final year value, mean across stands
            final_stored = hrv_df[hrv_df["Year"] == final_year][stored_col].mean()
            output["final_stored_carbon"] = (
                float(final_stored) if pd.notna(final_stored) else 0.0
            )

    # Total carbon (pool balances)
    live = output["final_live_carbon"] or 0.0
    dead = output["final_dead_carbon"] or 0.0
    stored = output["final_stored_carbon"] or 0.0
    output["final_total_carbon"] = live + dead + stored

    # Update avg_carbon_stock to include dead + stored if available
    if dead_col and live_col:
        combined["total_c"] = combined[live_col].fillna(0) + combined[dead_col].fillna(
            0
        )
        if stored and "harvest_carbon_all" in results:
            # Join stored carbon
            hrv_df = results["harvest_carbon_all"]
            stored_col = _find_column(hrv_df, STORED_CARBON_COLS)
            if stored_col:
                hrv_mean = hrv_df.groupby("Year")[stored_col].mean()
                combined = combined.merge(
                    hrv_mean.rename("stored_c"),
                    left_on="Year",
                    right_index=True,
                    how="left",
                )
                combined["total_c"] += combined["stored_c"].fillna(0)
        output["avg_carbon_stock"] = float(combined["total_c"].mean())

    # Canopy cover (POOL BALANCE - use min and final)
    canopy_col = _find_column(combined, CANOPY_COLS)
    if canopy_col:
        # Group by year first, then compute stats
        canopy_by_year = combined.groupby("Year")[canopy_col].mean()
        output["min_canopy_cover"] = float(canopy_by_year.min())
        output["final_canopy_cover"] = float(canopy_by_year.iloc[-1])

    # Harvest (FLOW FIELD - average across stands per year, then sum across years)
    harvest_col = _find_column(summary_df, HARVEST_FLOW_COLS)
    if harvest_col and harvest_col in summary_df.columns:
        # RBdFt is per-period flow (bdft/ac removed this period)
        # Step 1: Average across stands for each year to get mean per-acre removal
        # Step 2: Sum across all years to get total cumulative harvest per acre
        harvest_by_year = summary_df.groupby("Year")[harvest_col].mean()
        cumulative_harvest = harvest_by_year.sum()
        output["cumulative_harvest_bdft"] = float(cumulative_harvest)

    return output


def extract_time_series(results: dict[str, Any]) -> pd.DataFrame:
    """
    Extract per-year time series from FVS batch results.

    Aggregates data across stands for each year, properly handling flow vs pool fields.

    CRITICAL: Handles per-period flows (RBdFt) vs pool balances correctly:
    - Pool fields (BA, carbon): Mean across stands at each year
    - Flow fields (RBdFt): Mean across stands, then cumsum for cumulative

    Args:
        results: Dict returned by run_batch_simulation()

    Returns:
        DataFrame with columns matching MC_TimeSeries schema:
            - year: Simulation year
            - aboveground_c_live: Live carbon (tons/ac, pool)
            - standing_dead_c: Dead carbon (tons/ac, pool)
            - merch_carbon_stored: Stored carbon (tons/ac, pool)
            - total_carbon: Live + dead + stored (tons/ac)
            - canopy_cover_pct: Canopy cover (%, pool)
            - ba: Basal area (ft²/ac, pool)
            - tpa: Trees per acre (pool)
            - harvest_bdft: Harvest this period (bdft/ac, flow)
            - cumulative_harvest: Cumulative harvest (bdft/ac)

    Example:
        >>> results = fvs.run_batch_simulation(...)
        >>> ts = extract_time_series(results)
        >>> ts[["year", "ba", "harvest_bdft", "cumulative_harvest"]]
        year    ba  harvest_bdft  cumulative_harvest
        2023  120       1500              1500
        2033  110        800              2300
        2043  105        600              2900
    """
    # Return empty DataFrame if no data
    if "summary_all" not in results or results["summary_all"] is None:
        return pd.DataFrame()

    summary_df = results["summary_all"]
    if len(summary_df) == 0:
        return pd.DataFrame()

    # Import here to avoid circular dependency
    from ..batch import summarize_by_year

    # Combine all data sources
    combined = summarize_by_year(
        summary_df,
        results.get("carbon_all"),
        results.get("compute_all"),
    )

    if len(combined) == 0:
        return pd.DataFrame()

    # Group by year and compute means (pool balances)
    # Build agg dict with only present columns
    agg_dict = {}
    if "BA" in combined.columns:
        agg_dict["BA"] = "mean"
    if "Tpa" in combined.columns:
        agg_dict["Tpa"] = "mean"

    if agg_dict:
        ts = combined.groupby("Year").agg(agg_dict).reset_index()
    else:
        # No BA/Tpa, just get years
        ts = pd.DataFrame({"Year": sorted(combined["Year"].unique())})

    # Rename to match schema
    rename_map = {"Year": "year"}
    if "BA" in ts.columns:
        rename_map["BA"] = "ba"
    if "Tpa" in ts.columns:
        rename_map["Tpa"] = "tpa"
    ts = ts.rename(columns=rename_map)

    # Add carbon (POOL BALANCES)
    live_col = _find_column(combined, CARBON_LIVE_COLS)
    if live_col:
        ts["aboveground_c_live"] = combined.groupby("Year")[live_col].mean().values

    dead_col = _find_column(combined, CARBON_DEAD_COLS)
    if dead_col:
        ts["standing_dead_c"] = combined.groupby("Year")[dead_col].mean().values

    # Add stored carbon (POOL BALANCE from separate table)
    if "harvest_carbon_all" in results and results["harvest_carbon_all"] is not None:
        hrv_df = results["harvest_carbon_all"]
        stored_col = _find_column(hrv_df, STORED_CARBON_COLS)
        if stored_col:
            stored_by_year = hrv_df.groupby("Year")[stored_col].mean()
            ts = ts.merge(
                stored_by_year.rename("merch_carbon_stored"),
                left_on="year",
                right_index=True,
                how="left",
            )
            ts["merch_carbon_stored"] = ts["merch_carbon_stored"].fillna(0)

    # Total carbon (handle missing columns)
    live_c = (
        ts["aboveground_c_live"].fillna(0) if "aboveground_c_live" in ts.columns else 0
    )
    dead_c = ts["standing_dead_c"].fillna(0) if "standing_dead_c" in ts.columns else 0
    stored_c = (
        ts["merch_carbon_stored"].fillna(0)
        if "merch_carbon_stored" in ts.columns
        else 0
    )
    ts["total_carbon"] = live_c + dead_c + stored_c

    # Add canopy cover (POOL BALANCE)
    canopy_col = _find_column(combined, CANOPY_COLS)
    if canopy_col:
        ts["canopy_cover_pct"] = combined.groupby("Year")[canopy_col].mean().values

    # Add harvest (FLOW FIELD - per-period, then cumsum)
    harvest_col = _find_column(summary_df, HARVEST_FLOW_COLS)
    if harvest_col:
        # Mean across stands for each year (per-period flow)
        harvest_by_year = summary_df.groupby("Year")[harvest_col].mean()
        ts = ts.merge(
            harvest_by_year.rename("harvest_bdft"),
            left_on="year",
            right_index=True,
            how="left",
        )
        ts["harvest_bdft"] = ts["harvest_bdft"].fillna(0)

        # Cumulative is computed AFTER averaging (monotonically increasing)
        ts["cumulative_harvest"] = ts["harvest_bdft"].cumsum()

    # Fill NaN with 0 for numeric columns
    numeric_cols = ts.select_dtypes(include=["number"]).columns
    ts[numeric_cols] = ts[numeric_cols].fillna(0)

    # Validate
    _validate_time_series(ts)

    return ts
