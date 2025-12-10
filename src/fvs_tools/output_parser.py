"""
FVS output database parser.

Extracts data from FVS SQLite output databases.
"""

import sqlite3
from pathlib import Path

import pandas as pd


def parse_fvs_db(db_path: Path | str) -> dict[str, pd.DataFrame]:
    """
    Parse FVS output database and extract all tables.

    Args:
        db_path: Path to FVSOut.db SQLite database

    Returns:
        Dictionary mapping table names to DataFrames:
            - FVS_Summary: Stand-level summary by year
            - FVS_Carbon: Carbon pools by year
            - FVS_Fuels: Fuel loads by year
            - FVS_TreeList: Individual tree records (if requested)
            - FVS_Compute: Computed variables (if any)
            - FVS_CalibrationStats: Calibration statistics (if requested)

    Raises:
        FileNotFoundError: If database file doesn't exist
    """
    db_path = Path(db_path)

    if not db_path.exists():
        raise FileNotFoundError(f"FVS output database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))

    try:
        # Get list of available tables
        tables_query = """
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """
        available_tables = pd.read_sql_query(tables_query, conn)["name"].tolist()

        # Extract each table
        result = {}

        for table_name in available_tables:
            try:
                df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
                result[table_name] = df
            except Exception as e:
                print(f"Warning: Could not read table {table_name}: {e}")

        return result

    finally:
        conn.close()


def get_summary_table(
    db_path: Path | str, max_year: int | None = None
) -> pd.DataFrame | None:
    """
    Extract FVS summary table from database.

    Prefers FVS_Summary2 which contains the standard growth projections.
    Falls back to FVS_Summary if FVS_Summary2 doesn't exist.

    Args:
        db_path: Path to FVSOut.db
        max_year: If provided, filter to Year <= max_year

    Returns:
        DataFrame with summary statistics, or None if table doesn't exist
    """
    db_path = Path(db_path)

    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))

    try:
        # Prefer FVS_Summary2 which has correct growth projections
        # FVS_Summary shows "after treatment" values which can be misleading
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='FVS_Summary2'"
        )
        if cursor.fetchone():
            df = pd.read_sql_query("SELECT * FROM FVS_Summary2", conn)
        else:
            df = pd.read_sql_query("SELECT * FROM FVS_Summary", conn)

        # Remove duplicate rows (can occur from multiple runs or append mode)
        if df is not None and len(df) > 0:
            df = df.drop_duplicates()
            # Filter to max_year if specified (for extra-cycle trimming)
            if max_year is not None and "Year" in df.columns:
                df = df[df["Year"] <= max_year]

        return df
    except Exception:
        return None
    finally:
        conn.close()


def get_carbon_table(
    db_path: Path | str, max_year: int | None = None
) -> pd.DataFrame | None:
    """
    Extract FVS_Carbon table from database.

    Args:
        db_path: Path to FVSOut.db
        max_year: If provided, filter to Year <= max_year

    Returns:
        DataFrame with carbon pools, or None if table doesn't exist
    """
    db_path = Path(db_path)

    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))

    try:
        df = pd.read_sql_query("SELECT * FROM FVS_Carbon", conn)
        # Filter to max_year if specified (for extra-cycle trimming)
        if df is not None and max_year is not None and "Year" in df.columns:
            df = df[df["Year"] <= max_year]
        return df
    except Exception:
        return None
    finally:
        conn.close()


def get_harvest_carbon_table(
    db_path: Path | str, max_year: int | None = None
) -> pd.DataFrame | None:
    """
    Extract FVS_Hrv_Carbon table from database.

    This table contains carbon stored in harvested wood products,
    which represents long-term off-site carbon storage.

    Args:
        db_path: Path to FVSOut.db
        max_year: If provided, filter to Year <= max_year

    Returns:
        DataFrame with harvest carbon data, or None if table doesn't exist
        Key columns include:
        - Merch_Carbon_Stored: Carbon in merchantable wood products (tons/ac)
        - Merch_Carbon_Removed: Total carbon removed in harvest
    """
    db_path = Path(db_path)

    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))

    try:
        df = pd.read_sql_query("SELECT * FROM FVS_Hrv_Carbon", conn)
        # Filter to max_year if specified
        if df is not None and max_year is not None and "Year" in df.columns:
            df = df[df["Year"] <= max_year]
        return df
    except Exception:
        return None
    finally:
        conn.close()


def get_compute_table(
    db_path: Path | str, max_year: int | None = None
) -> pd.DataFrame | None:
    """
    Extract FVS_Compute table from database.

    Args:
        db_path: Path to FVSOut.db
        max_year: If provided, filter to Year <= max_year

    Returns:
        DataFrame with computed variables, or None if table doesn't exist
    """
    db_path = Path(db_path)

    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))

    try:
        df = pd.read_sql_query("SELECT * FROM FVS_Compute", conn)
        # Filter to max_year if specified (for extra-cycle trimming)
        if df is not None and max_year is not None and "Year" in df.columns:
            df = df[df["Year"] <= max_year]
        return df
    except Exception:
        return None
    finally:
        conn.close()


def extract_calibration_stats(db_path: Path | str) -> pd.DataFrame | None:
    """
    Extract calibration statistics from FVS output.

    Calibration stats are in the FVS_CalibStats table.

    Args:
        db_path: Path to FVSOut.db (or working directory)

    Returns:
        DataFrame with calibration statistics, or None if not available
    """
    db_path = Path(db_path)

    # If db_path is a directory, look for database in it
    if db_path.is_dir():
        db_path = db_path / "FVSOut.db"

    if not db_path.exists():
        return None

    conn = sqlite3.connect(str(db_path))

    try:
        # Try to get calibration stats table
        # Note: Table name is usually FVS_CalibStats
        try:
            df = pd.read_sql_query("SELECT * FROM FVS_CalibStats", conn)
        except Exception:
            # Fallback or try other names
            try:
                df = pd.read_sql_query("SELECT * FROM FVS_CalibrationStats", conn)
            except Exception:
                return None

        if df.empty:
            return None

        return df

    except Exception:
        return None

    finally:
        conn.close()


def summarize_by_year(
    summary_df: pd.DataFrame,
    carbon_df: pd.DataFrame | None = None,
    compute_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Combine summary, carbon, and compute tables into a single per-year summary.

    Args:
        summary_df: FVS_Summary table
        carbon_df: FVS_Carbon table (optional)
        compute_df: FVS_Compute table (optional)

    Returns:
        DataFrame with combined metrics by year
    """
    # Start with summary
    result = summary_df.copy()

    # Add carbon metrics if available
    if carbon_df is not None and len(carbon_df) > 0:
        # Key carbon columns (FVS uses CamelCase without underscores between words)
        carbon_cols = [
            "Year",
            "StandID",
            "Aboveground_Total_Live",
            "Standing_Dead",
            "Belowground_Live",
            "Belowground_Dead",
        ]
        available_cols = [col for col in carbon_cols if col in carbon_df.columns]

        if len(available_cols) > 2:  # At least Year, StandID, and one data column
            carbon_subset = carbon_df[available_cols].copy()
            result = result.merge(carbon_subset, on=["Year", "StandID"], how="left")

    # Add computed variables if available
    # FVS uses PC_CAN_C for canopy cover from COMPUTE keyword
    if (
        compute_df is not None
        and len(compute_df) > 0
        and "PC_CAN_C" in compute_df.columns
    ):
        # Get canopy cover if computed
        compute_subset = compute_df[["Year", "StandID", "PC_CAN_C"]].copy()
        result = result.merge(compute_subset, on=["Year", "StandID"], how="left")

    return result
