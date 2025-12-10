"""
Data loading utilities for FVS-ready CSV files.
"""

from pathlib import Path

import pandas as pd

from .config import DEFAULT_STAND_DATA, DEFAULT_TREE_DATA
from .db_input import create_fvs_input_db


def load_stands(filepath: Path | str | None = None) -> pd.DataFrame:
    """
    Load FVS stand initialization data from CSV.

    Args:
        filepath: Path to FVS_StandInit CSV file (defaults to Lubrecht 2023 data)

    Returns:
        DataFrame with stand-level attributes
    """
    if filepath is None:
        filepath = DEFAULT_STAND_DATA

    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Stand data file not found: {filepath}")

    df = pd.read_csv(filepath)

    # Ensure key columns exist
    required_cols = ["STAND_ID", "VARIANT", "INV_YEAR", "PlotID"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Stand data missing required columns: {missing}")

    return df


def load_trees(filepath: Path | str | None = None) -> pd.DataFrame:
    """
    Load FVS tree initialization data from CSV.

    Args:
        filepath: Path to FVS_TreeInit CSV file (defaults to Lubrecht 2023 data)

    Returns:
        DataFrame with individual tree records
    """
    if filepath is None:
        filepath = DEFAULT_TREE_DATA

    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Tree data file not found: {filepath}")

    df = pd.read_csv(filepath)

    # Ensure key columns exist
    required_cols = ["STAND_ID", "PLOT_ID", "TREE_ID", "SPECIES", "DIAMETER"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Tree data missing required columns: {missing}")

    return df


def filter_by_plot_ids(
    stands: pd.DataFrame, trees: pd.DataFrame, plot_ids: list[int]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Filter stand and tree data to specified plot IDs.

    Args:
        stands: Stand initialization DataFrame
        trees: Tree initialization DataFrame
        plot_ids: List of plot IDs to include (e.g., [99, 100, 101])

    Returns:
        Tuple of (filtered_stands, filtered_trees)
    """
    # Filter stands
    filtered_stands = stands[stands["PlotID"].isin(plot_ids)].copy()

    if len(filtered_stands) == 0:
        raise ValueError(f"No stands found for plot IDs: {plot_ids}")

    # Get corresponding stand IDs
    stand_ids = filtered_stands["STAND_ID"].tolist()

    # Filter trees to matching stands
    filtered_trees = trees[trees["STAND_ID"].isin(stand_ids)].copy()

    if len(filtered_trees) == 0:
        raise ValueError(f"No trees found for stands: {stand_ids}")

    return filtered_stands, filtered_trees


def get_stand_trees(stand_id: str, trees: pd.DataFrame) -> pd.DataFrame:
    """
    Get all trees for a specific stand.

    Args:
        stand_id: Stand identifier (e.g., "CARB_99")
        trees: Full tree DataFrame

    Returns:
        DataFrame containing only trees from the specified stand
    """
    stand_trees = trees[trees["STAND_ID"] == stand_id].copy()

    if len(stand_trees) == 0:
        raise ValueError(f"No trees found for stand: {stand_id}")

    return stand_trees


def prepare_fvs_database(
    stands: pd.DataFrame,
    trees: pd.DataFrame,
    output_db: Path | str,
) -> None:
    """
    Create FVS input database from loaded stand and tree data.

    This is a convenience wrapper around create_fvs_input_db.

    Args:
        stands: Stand DataFrame from load_stands()
        trees: Tree DataFrame from load_trees()
        output_db: Path to output database file (e.g., "FVS_Data.db")
    """
    create_fvs_input_db(stands, trees, output_db)


def get_carbon_plot_ids(stands: pd.DataFrame) -> list[int]:
    """
    Get plot IDs for carbon plots (CARB_* prefix stands).

    Carbon plots are identified by STAND_ID starting with "CARB_".
    This excludes LEF_* and other non-carbon plot types.

    Args:
        stands: Stand initialization DataFrame with STAND_ID and PlotID columns

    Returns:
        Sorted list of plot IDs for carbon plots

    Example:
        >>> stands = load_stands()
        >>> carbon_plots = get_carbon_plot_ids(stands)
        >>> print(carbon_plots[:5])
        [2, 3, 4, 5, 7]
    """
    carbon_stands = stands[stands["STAND_ID"].str.startswith("CARB_")]
    plot_ids = sorted(carbon_stands["PlotID"].unique().tolist())
    return plot_ids


def validate_stands(
    stands: pd.DataFrame,
    trees: pd.DataFrame,
    min_trees: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Validate stand/tree data and exclude invalid stands.

    Checks each stand has at least `min_trees` trees. Stands without
    sufficient trees are excluded with a warning in the report.

    Args:
        stands: Stand initialization DataFrame
        trees: Tree initialization DataFrame
        min_trees: Minimum number of trees required per stand (default 1)

    Returns:
        Tuple of (valid_stands, valid_trees, validation_report)

        validation_report contains:
            - total_stands: Original number of stands
            - valid_stands: Number of valid stands
            - excluded_stands: List of dicts with stand_id, plot_id, reason
            - tree_counts: Dict mapping stand_id to tree count

    Example:
        >>> stands = load_stands()
        >>> trees = load_trees()
        >>> valid_stands, valid_trees, report = validate_stands(stands, trees)
        >>> print(f"Valid: {report['valid_stands']}/{report['total_stands']}")
        Valid: 268/296
        >>> for exc in report['excluded_stands'][:3]:
        ...     print(f"  {exc['stand_id']}: {exc['reason']}")
    """
    # Count trees per stand
    tree_counts = trees.groupby("STAND_ID").size().to_dict()

    # Check each stand
    excluded = []
    valid_stand_ids = []

    for _, stand in stands.iterrows():
        stand_id = stand["STAND_ID"]
        plot_id = stand["PlotID"]
        count = tree_counts.get(stand_id, 0)

        if count < min_trees:
            excluded.append(
                {
                    "stand_id": stand_id,
                    "plot_id": plot_id,
                    "tree_count": count,
                    "reason": f"insufficient trees ({count} < {min_trees})",
                }
            )
        else:
            valid_stand_ids.append(stand_id)

    # Filter to valid stands
    valid_stands = stands[stands["STAND_ID"].isin(valid_stand_ids)].copy()
    valid_trees = trees[trees["STAND_ID"].isin(valid_stand_ids)].copy()

    # Build report
    report = {
        "total_stands": len(stands),
        "valid_stands": len(valid_stands),
        "excluded_stands": excluded,
        "tree_counts": tree_counts,
    }

    return valid_stands, valid_trees, report


def print_validation_report(report: dict) -> None:
    """
    Print a human-readable validation report.

    Args:
        report: Validation report from validate_stands()
    """
    total = report["total_stands"]
    valid = report["valid_stands"]
    excluded = report["excluded_stands"]

    print("\nStand Validation Report:")
    print(f"  Total stands:    {total}")
    print(f"  Valid stands:    {valid}")
    print(f"  Excluded stands: {len(excluded)}")

    if excluded:
        print("\n  Excluded stands:")
        for exc in excluded:
            print(f"    {exc['stand_id']} (plot {exc['plot_id']}): {exc['reason']}")
