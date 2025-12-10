"""
Database layer for Monte Carlo batch simulations.

Provides SQLite schema and functions for storing/loading Monte Carlo results:
- Batch metadata and configuration
- Run registry with sampled parameters
- Aggregated summary metrics per run
- Time series data per run per year
- Error logging for failed runs
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from .config import MonteCarloConfig


# SQL Schema Definitions
SCHEMA_MC_BATCH_META = """
CREATE TABLE IF NOT EXISTS MC_BatchMeta (
    batch_id      TEXT PRIMARY KEY,
    batch_seed    INTEGER NOT NULL,
    n_samples     INTEGER NOT NULL,
    n_workers     INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    completed_at  TEXT,
    status        TEXT NOT NULL,  -- running/complete/partial
    config_json   TEXT NOT NULL   -- Full MonteCarloConfig serialized
);
"""

SCHEMA_MC_RUN_REGISTRY = """
CREATE TABLE IF NOT EXISTS MC_RunRegistry (
    batch_id             TEXT NOT NULL,
    run_id               INTEGER NOT NULL,
    run_seed             INTEGER NOT NULL,
    status               TEXT DEFAULT 'pending',  -- pending/running/complete/failed
    created_at           TEXT,
    completed_at         TEXT,
    -- Sampled parameters (all nullable since not all params used in every batch)
    thin_q_factor        REAL,
    thin_residual_ba     REAL,
    thin_trigger_ba      REAL,
    thin_min_dbh         REAL,
    thin_max_dbh         REAL,
    min_harvest_volume   REAL,
    mortality_multiplier REAL,
    enable_calibration   INTEGER,  -- 0/1
    fvs_random_seed      INTEGER,
    PRIMARY KEY (batch_id, run_id)
);
"""

SCHEMA_MC_RUN_SUMMARY = """
CREATE TABLE IF NOT EXISTS MC_RunSummary (
    batch_id                TEXT NOT NULL,
    run_id                  INTEGER NOT NULL,
    -- Carbon metrics (tons/ac)
    final_total_carbon      REAL,
    avg_carbon_stock        REAL,
    final_live_carbon       REAL,
    final_dead_carbon       REAL,
    final_stored_carbon     REAL,
    -- Canopy metrics (%)
    min_canopy_cover        REAL,
    final_canopy_cover      REAL,
    -- Harvest metrics
    cumulative_harvest_bdft REAL,
    -- Metadata
    run_duration_sec        REAL,
    n_stands                INTEGER,
    PRIMARY KEY (batch_id, run_id),
    FOREIGN KEY (batch_id, run_id) REFERENCES MC_RunRegistry(batch_id, run_id)
);
"""

SCHEMA_MC_TIME_SERIES = """
CREATE TABLE IF NOT EXISTS MC_TimeSeries (
    batch_id              TEXT NOT NULL,
    run_id                INTEGER NOT NULL,
    year                  INTEGER NOT NULL,
    -- Carbon pools (tons/ac)
    aboveground_c_live    REAL,
    standing_dead_c       REAL,
    merch_carbon_stored   REAL,
    total_carbon          REAL,
    -- Stand metrics
    canopy_cover_pct      REAL,
    ba                    REAL,
    tpa                   REAL,
    -- Harvest
    harvest_bdft          REAL,
    cumulative_harvest    REAL,
    PRIMARY KEY (batch_id, run_id, year),
    FOREIGN KEY (batch_id, run_id) REFERENCES MC_RunRegistry(batch_id, run_id)
);
"""

SCHEMA_MC_BATCH_ERRORS = """
CREATE TABLE IF NOT EXISTS MC_BatchErrors (
    batch_id    TEXT NOT NULL,
    run_id      INTEGER NOT NULL,
    stand_id    TEXT,
    error_type  TEXT NOT NULL,
    error_msg   TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    PRIMARY KEY (batch_id, run_id, stand_id)
);
"""


def create_mc_database(db_path: Path) -> sqlite3.Connection:
    """
    Create SQLite database with Monte Carlo schema.

    Creates all required tables for storing Monte Carlo batch results.
    Safe to call on existing database (uses IF NOT EXISTS).

    Args:
        db_path: Path to SQLite database file

    Returns:
        Open connection to the database

    Example:
        >>> db_path = Path("outputs/mc_batch_abc123/mc_results.db")
        >>> conn = create_mc_database(db_path)
        >>> # Use connection for write/read operations
        >>> conn.close()
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)

    # Create all tables
    conn.execute(SCHEMA_MC_BATCH_META)
    conn.execute(SCHEMA_MC_RUN_REGISTRY)
    conn.execute(SCHEMA_MC_RUN_SUMMARY)
    conn.execute(SCHEMA_MC_TIME_SERIES)
    conn.execute(SCHEMA_MC_BATCH_ERRORS)

    conn.commit()
    return conn


def write_batch_meta(conn: sqlite3.Connection, config: "MonteCarloConfig") -> None:
    """
    Write batch metadata to database.

    Should be called once at batch start before any runs execute.

    Args:
        conn: Database connection
        config: MonteCarloConfig with batch settings
    """
    # Serialize config to JSON (exclude non-serializable objects)
    config_dict = {
        "batch_id": config.batch_id,
        "batch_seed": config.batch_seed,
        "n_samples": config.n_samples,
        "n_workers": config.n_workers,
        "stand_ids": config.stand_ids,
        "plot_ids": config.plot_ids,
        "output_base": str(config.output_base),
        "base_config_name": config.base_config.name,
        "parameter_specs": [
            {
                "type": type(spec).__name__,
                "name": spec.name,
                **{k: v for k, v in vars(spec).items() if k != "name"},
            }
            for spec in config.parameter_specs
        ],
    }
    config_json = json.dumps(config_dict, indent=2)

    conn.execute(
        """
        INSERT INTO MC_BatchMeta 
        (batch_id, batch_seed, n_samples, n_workers, created_at, status, config_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            config.batch_id,
            config.batch_seed,
            config.n_samples,
            config.n_workers,
            datetime.now().isoformat(),
            "running",
            config_json,
        ),
    )
    conn.commit()


def write_run_registry(
    conn: sqlite3.Connection, batch_id: str, samples: list[dict]
) -> None:
    """
    Pre-populate run registry with all planned runs.

    Writes one row per sample with sampled parameter values.
    All runs start with status='pending'.

    Args:
        conn: Database connection
        batch_id: Batch identifier
        samples: List of parameter sample dicts from generate_parameter_samples()
    """
    # Prepare rows for insertion
    rows = []
    for sample in samples:
        row = {
            "batch_id": batch_id,
            "run_id": sample["run_id"],
            "run_seed": sample["run_seed"],
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            # Parameter columns (set to None if not in sample)
            "thin_q_factor": sample.get("thin_q_factor"),
            "thin_residual_ba": sample.get("thin_residual_ba"),
            "thin_trigger_ba": sample.get("thin_trigger_ba"),
            "thin_min_dbh": sample.get("thin_min_dbh"),
            "thin_max_dbh": sample.get("thin_max_dbh"),
            "min_harvest_volume": sample.get("min_harvest_volume"),
            "mortality_multiplier": sample.get("mortality_multiplier"),
            "enable_calibration": sample.get("enable_calibration"),
            "fvs_random_seed": sample.get("fvs_random_seed"),
        }
        rows.append(row)

    # Bulk insert
    conn.executemany(
        """
        INSERT INTO MC_RunRegistry (
            batch_id, run_id, run_seed, status, created_at, completed_at,
            thin_q_factor, thin_residual_ba, thin_trigger_ba,
            thin_min_dbh, thin_max_dbh, min_harvest_volume,
            mortality_multiplier, enable_calibration, fvs_random_seed
        ) VALUES (
            :batch_id, :run_id, :run_seed, :status, :created_at, :completed_at,
            :thin_q_factor, :thin_residual_ba, :thin_trigger_ba,
            :thin_min_dbh, :thin_max_dbh, :min_harvest_volume,
            :mortality_multiplier, :enable_calibration, :fvs_random_seed
        )
        """,
        rows,
    )
    conn.commit()


def update_run_status(
    conn: sqlite3.Connection,
    batch_id: str,
    run_id: int,
    status: str,
    completed_at: str | None = None,
) -> None:
    """
    Update status of a run in the registry.

    Args:
        conn: Database connection
        batch_id: Batch identifier
        run_id: Run identifier (0 to n_samples-1)
        status: New status ('pending', 'running', 'complete', 'failed')
        completed_at: ISO timestamp when run completed (optional)
    """
    conn.execute(
        """
        UPDATE MC_RunRegistry
        SET status = ?, completed_at = ?
        WHERE batch_id = ? AND run_id = ?
        """,
        (status, completed_at, batch_id, run_id),
    )
    conn.commit()


def write_run_summary(
    conn: sqlite3.Connection, batch_id: str, run_id: int, metrics: dict
) -> None:
    """
    Write aggregated summary metrics for a completed run.

    Args:
        conn: Database connection
        batch_id: Batch identifier
        run_id: Run identifier
        metrics: Dictionary with summary metrics (keys match column names)

    Expected metrics keys:
        - final_total_carbon, avg_carbon_stock
        - final_live_carbon, final_dead_carbon, final_stored_carbon
        - min_canopy_cover, final_canopy_cover
        - cumulative_harvest_bdft
        - run_duration_sec, n_stands
    """
    conn.execute(
        """
        INSERT INTO MC_RunSummary (
            batch_id, run_id,
            final_total_carbon, avg_carbon_stock,
            final_live_carbon, final_dead_carbon, final_stored_carbon,
            min_canopy_cover, final_canopy_cover,
            cumulative_harvest_bdft,
            run_duration_sec, n_stands
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            batch_id,
            run_id,
            metrics.get("final_total_carbon"),
            metrics.get("avg_carbon_stock"),
            metrics.get("final_live_carbon"),
            metrics.get("final_dead_carbon"),
            metrics.get("final_stored_carbon"),
            metrics.get("min_canopy_cover"),
            metrics.get("final_canopy_cover"),
            metrics.get("cumulative_harvest_bdft"),
            metrics.get("run_duration_sec"),
            metrics.get("n_stands"),
        ),
    )
    conn.commit()


def write_time_series(
    conn: sqlite3.Connection, batch_id: str, run_id: int, df: pd.DataFrame
) -> None:
    """
    Write time series data for a run.

    Args:
        conn: Database connection
        batch_id: Batch identifier
        run_id: Run identifier
        df: DataFrame with columns matching MC_TimeSeries schema
            Required column: 'year'
            Optional: aboveground_c_live, standing_dead_c, merch_carbon_stored,
                      total_carbon, canopy_cover_pct, ba, tpa,
                      harvest_bdft, cumulative_harvest
    """
    # Add batch_id and run_id columns
    df = df.copy()
    df["batch_id"] = batch_id
    df["run_id"] = run_id

    # Write to database (append mode)
    df.to_sql("MC_TimeSeries", conn, if_exists="append", index=False)
    conn.commit()


def write_batch_error(
    conn: sqlite3.Connection,
    batch_id: str,
    run_id: int,
    stand_id: str | None,
    error_type: str,
    error_msg: str,
) -> None:
    """
    Log an error for a failed run.

    Args:
        conn: Database connection
        batch_id: Batch identifier
        run_id: Run identifier
        stand_id: Stand that failed (None if batch-level failure)
        error_type: Error type/category
        error_msg: Full error message
    """
    conn.execute(
        """
        INSERT INTO MC_BatchErrors (batch_id, run_id, stand_id, error_type, error_msg, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (batch_id, run_id, stand_id, error_type, error_msg, datetime.now().isoformat()),
    )
    conn.commit()


def update_batch_status(conn: sqlite3.Connection, batch_id: str, status: str) -> None:
    """
    Update batch status in metadata table.

    Args:
        conn: Database connection
        batch_id: Batch identifier
        status: New status ('running', 'complete', 'partial')
    """
    completed_at = (
        datetime.now().isoformat() if status in ("complete", "partial") else None
    )
    conn.execute(
        """
        UPDATE MC_BatchMeta
        SET status = ?, completed_at = ?
        WHERE batch_id = ?
        """,
        (status, completed_at, batch_id),
    )
    conn.commit()


# Read functions
def load_batch_meta(conn: sqlite3.Connection) -> dict:
    """Load batch metadata."""
    cursor = conn.execute("SELECT * FROM MC_BatchMeta")
    row = cursor.fetchone()
    if row is None:
        return {}

    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row, strict=True))


def load_registry(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load run registry with sampled parameters."""
    return pd.read_sql_query("SELECT * FROM MC_RunRegistry", conn)


def load_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load run summary metrics."""
    return pd.read_sql_query("SELECT * FROM MC_RunSummary", conn)


def load_timeseries(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load time series data for all runs."""
    return pd.read_sql_query("SELECT * FROM MC_TimeSeries", conn)


def load_errors(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load error log."""
    return pd.read_sql_query("SELECT * FROM MC_BatchErrors", conn)


def load_mc_results(db_path: Path) -> dict:
    """
    Load all Monte Carlo results from a batch database.

    Args:
        db_path: Path to mc_results.db file

    Returns:
        Dictionary with keys:
            - 'batch_meta': dict with batch metadata
            - 'registry': DataFrame with run registry
            - 'summary': DataFrame with summary metrics
            - 'timeseries': DataFrame with time series data
            - 'errors': DataFrame with error log

    Example:
        >>> results = load_mc_results(Path("outputs/mc_batch_abc/mc_results.db"))
        >>> print(f"Batch {results['batch_meta']['batch_id']}")
        >>> print(f"{len(results['summary'])} completed runs")
        >>> registry = results['registry']
        >>> summary = results['summary']
        >>> # Join to analyze parameter → outcome relationships
        >>> merged = registry.merge(summary, on=['batch_id', 'run_id'])
    """
    conn = sqlite3.connect(db_path)

    try:
        results = {
            "batch_meta": load_batch_meta(conn),
            "registry": load_registry(conn),
            "summary": load_summary(conn),
            "timeseries": load_timeseries(conn),
            "errors": load_errors(conn),
        }
        return results
    finally:
        conn.close()
