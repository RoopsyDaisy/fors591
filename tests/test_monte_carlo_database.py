"""
Unit tests for Monte Carlo database layer.

Tests schema creation, write/read operations, and data integrity.
"""

import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from fvs_tools.config import FVSSimulationConfig
from fvs_tools.monte_carlo import (
    MonteCarloConfig,
    UniformParameterSpec,
    create_mc_database,
    generate_parameter_samples,
    load_mc_results,
    update_batch_status,
    update_run_status,
    write_batch_error,
    write_batch_meta,
    write_run_registry,
    write_run_summary,
    write_time_series,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_mc.db"
        yield db_path


@pytest.fixture
def base_config():
    """Basic FVS configuration."""
    return FVSSimulationConfig(name="test", num_years=50, cycle_length=10)


@pytest.fixture
def mc_config(base_config):
    """Monte Carlo configuration."""
    return MonteCarloConfig(
        batch_seed=42,
        n_samples=5,
        parameter_specs=[
            UniformParameterSpec("thin_q_factor", 1.5, 2.5),
            UniformParameterSpec("thin_residual_ba", 50.0, 80.0),
        ],
        base_config=base_config,
    )


@pytest.fixture
def samples(mc_config):
    """Generate parameter samples."""
    return generate_parameter_samples(mc_config)


class TestSchemaCreation:
    def test_creates_database_file(self, temp_db):
        """Database file is created."""
        assert not temp_db.exists()
        conn = create_mc_database(temp_db)
        conn.close()
        assert temp_db.exists()

    def test_creates_all_tables(self, temp_db):
        """All required tables are created."""
        conn = create_mc_database(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected_tables = {
            "MC_BatchMeta",
            "MC_RunRegistry",
            "MC_RunSummary",
            "MC_TimeSeries",
            "MC_BatchErrors",
        }
        assert expected_tables.issubset(tables)

    def test_idempotent_creation(self, temp_db):
        """Can call create_mc_database multiple times."""
        conn1 = create_mc_database(temp_db)
        conn1.close()

        # Should not raise error
        conn2 = create_mc_database(temp_db)
        conn2.close()


class TestBatchMeta:
    def test_write_batch_meta(self, temp_db, mc_config):
        """Write batch metadata successfully."""
        conn = create_mc_database(temp_db)
        write_batch_meta(conn, mc_config)

        cursor = conn.execute("SELECT * FROM MC_BatchMeta")
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        # Check key fields
        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row, strict=True))
        assert data["batch_id"] == mc_config.batch_id
        assert data["batch_seed"] == mc_config.batch_seed
        assert data["n_samples"] == mc_config.n_samples
        assert data["status"] == "running"

    def test_update_batch_status(self, temp_db, mc_config):
        """Update batch status."""
        conn = create_mc_database(temp_db)
        write_batch_meta(conn, mc_config)

        update_batch_status(conn, mc_config.batch_id, "complete")

        cursor = conn.execute(
            "SELECT status, completed_at FROM MC_BatchMeta WHERE batch_id = ?",
            (mc_config.batch_id,),
        )
        row = cursor.fetchone()
        conn.close()

        assert row[0] == "complete"
        assert row[1] is not None  # completed_at should be set


class TestRunRegistry:
    def test_write_run_registry(self, temp_db, mc_config, samples):
        """Write run registry with sampled parameters."""
        conn = create_mc_database(temp_db)
        write_run_registry(conn, mc_config.batch_id, samples)

        cursor = conn.execute("SELECT COUNT(*) FROM MC_RunRegistry")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == len(samples)

    def test_registry_contains_sampled_params(self, temp_db, mc_config, samples):
        """Registry rows contain sampled parameter values."""
        conn = create_mc_database(temp_db)
        write_run_registry(conn, mc_config.batch_id, samples)

        cursor = conn.execute(
            "SELECT run_id, thin_q_factor, thin_residual_ba FROM MC_RunRegistry ORDER BY run_id"
        )
        rows = cursor.fetchall()
        conn.close()

        for i, row in enumerate(rows):
            run_id, q_factor, residual_ba = row
            assert run_id == samples[i]["run_id"]
            assert q_factor == pytest.approx(samples[i]["thin_q_factor"])
            assert residual_ba == pytest.approx(samples[i]["thin_residual_ba"])

    def test_update_run_status(self, temp_db, mc_config, samples):
        """Update individual run status."""
        conn = create_mc_database(temp_db)
        write_run_registry(conn, mc_config.batch_id, samples)

        # Update first run to complete
        update_run_status(
            conn, mc_config.batch_id, 0, "complete", "2024-12-09T12:00:00"
        )

        cursor = conn.execute(
            "SELECT status, completed_at FROM MC_RunRegistry WHERE batch_id = ? AND run_id = 0",
            (mc_config.batch_id,),
        )
        row = cursor.fetchone()
        conn.close()

        assert row[0] == "complete"
        assert row[1] == "2024-12-09T12:00:00"


class TestRunSummary:
    def test_write_run_summary(self, temp_db, mc_config, samples):
        """Write run summary metrics."""
        conn = create_mc_database(temp_db)
        write_run_registry(conn, mc_config.batch_id, samples)

        metrics = {
            "final_total_carbon": 45.2,
            "avg_carbon_stock": 42.1,
            "final_live_carbon": 35.0,
            "final_dead_carbon": 8.0,
            "final_stored_carbon": 2.2,
            "min_canopy_cover": 38.5,
            "final_canopy_cover": 65.0,
            "cumulative_harvest_bdft": 15000.0,
            "run_duration_sec": 120.5,
            "n_stands": 8,
        }

        write_run_summary(conn, mc_config.batch_id, 0, metrics)

        cursor = conn.execute(
            "SELECT * FROM MC_RunSummary WHERE batch_id = ? AND run_id = 0",
            (mc_config.batch_id,),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row, strict=True))

        assert data["final_total_carbon"] == pytest.approx(45.2)
        assert data["min_canopy_cover"] == pytest.approx(38.5)
        assert data["n_stands"] == 8


class TestTimeSeries:
    def test_write_time_series(self, temp_db, mc_config, samples):
        """Write time series data."""
        conn = create_mc_database(temp_db)
        write_run_registry(conn, mc_config.batch_id, samples)

        # Create sample time series
        ts_data = pd.DataFrame(
            {
                "year": [2023, 2033, 2043],
                "aboveground_c_live": [40.0, 42.0, 45.0],
                "standing_dead_c": [5.0, 6.0, 8.0],
                "total_carbon": [45.0, 48.0, 53.0],
                "canopy_cover_pct": [55.0, 60.0, 65.0],
            }
        )

        write_time_series(conn, mc_config.batch_id, 0, ts_data)

        cursor = conn.execute(
            "SELECT COUNT(*) FROM MC_TimeSeries WHERE batch_id = ? AND run_id = 0",
            (mc_config.batch_id,),
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 3

    def test_time_series_data_integrity(self, temp_db, mc_config, samples):
        """Time series values are correct."""
        conn = create_mc_database(temp_db)
        write_run_registry(conn, mc_config.batch_id, samples)

        ts_data = pd.DataFrame(
            {
                "year": [2023, 2033],
                "aboveground_c_live": [40.0, 45.0],
                "canopy_cover_pct": [55.0, 65.0],
            }
        )

        write_time_series(conn, mc_config.batch_id, 0, ts_data)

        cursor = conn.execute(
            "SELECT year, aboveground_c_live, canopy_cover_pct FROM MC_TimeSeries "
            "WHERE batch_id = ? AND run_id = 0 ORDER BY year",
            (mc_config.batch_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) == 2
        assert rows[0] == (2023, 40.0, 55.0)
        assert rows[1] == (2033, 45.0, 65.0)


class TestErrorLogging:
    def test_write_batch_error(self, temp_db, mc_config, samples):
        """Log error for failed run."""
        conn = create_mc_database(temp_db)
        write_run_registry(conn, mc_config.batch_id, samples)

        write_batch_error(
            conn,
            mc_config.batch_id,
            0,
            "stand_099",
            "FVS_ERROR",
            "Keyword syntax error",
        )

        cursor = conn.execute(
            "SELECT * FROM MC_BatchErrors WHERE batch_id = ? AND run_id = 0",
            (mc_config.batch_id,),
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row, strict=True))

        assert data["stand_id"] == "stand_099"
        assert data["error_type"] == "FVS_ERROR"
        assert "Keyword syntax" in data["error_msg"]


class TestLoadResults:
    def test_load_empty_database(self, temp_db):
        """Load results from empty database."""
        conn = create_mc_database(temp_db)
        conn.close()

        results = load_mc_results(temp_db)

        assert results["batch_meta"] == {}
        assert len(results["registry"]) == 0
        assert len(results["summary"]) == 0
        assert len(results["timeseries"]) == 0
        assert len(results["errors"]) == 0

    def test_load_complete_batch(self, temp_db, mc_config, samples):
        """Load results from complete batch."""
        # Write complete batch
        conn = create_mc_database(temp_db)
        write_batch_meta(conn, mc_config)
        write_run_registry(conn, mc_config.batch_id, samples)

        # Write summary for first run
        metrics = {
            "final_total_carbon": 45.0,
            "avg_carbon_stock": 42.0,
            "n_stands": 8,
        }
        write_run_summary(conn, mc_config.batch_id, 0, metrics)

        # Write time series for first run
        ts_data = pd.DataFrame(
            {
                "year": [2023, 2033],
                "total_carbon": [40.0, 45.0],
            }
        )
        write_time_series(conn, mc_config.batch_id, 0, ts_data)

        conn.close()

        # Load all results
        results = load_mc_results(temp_db)

        assert results["batch_meta"]["batch_id"] == mc_config.batch_id
        assert len(results["registry"]) == 5
        assert len(results["summary"]) == 1
        assert len(results["timeseries"]) == 2

    def test_load_results_joins(self, temp_db, mc_config, samples):
        """Loaded dataframes can be joined."""
        conn = create_mc_database(temp_db)
        write_batch_meta(conn, mc_config)
        write_run_registry(conn, mc_config.batch_id, samples)

        metrics = {"final_total_carbon": 45.0, "n_stands": 8}
        write_run_summary(conn, mc_config.batch_id, 0, metrics)

        conn.close()

        results = load_mc_results(temp_db)

        # Join registry and summary
        merged = results["registry"].merge(
            results["summary"], on=["batch_id", "run_id"], how="left"
        )

        assert len(merged) == 5
        assert merged.loc[0, "final_total_carbon"] == 45.0
        assert pd.isna(merged.loc[1, "final_total_carbon"])  # Not completed


class TestDataIntegrity:
    def test_foreign_key_constraint(self, temp_db, mc_config):
        """Foreign key constraint is enforced (if enabled)."""
        conn = create_mc_database(temp_db)
        write_batch_meta(conn, mc_config)

        # Try to write summary without registry entry
        # SQLite doesn't enforce FK by default, so this tests the schema
        metrics = {"final_total_carbon": 45.0, "n_stands": 8}

        # This should work (FK not enforced by default in SQLite)
        # But schema has FK definition for documentation
        write_run_summary(conn, mc_config.batch_id, 999, metrics)
        conn.close()

    def test_primary_key_uniqueness(self, temp_db, mc_config, samples):
        """Primary key prevents duplicates."""
        conn = create_mc_database(temp_db)
        write_run_registry(conn, mc_config.batch_id, samples)

        # Try to insert duplicate run_id
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO MC_RunRegistry (batch_id, run_id, run_seed, status)
                VALUES (?, 0, 12345, 'pending')
                """,
                (mc_config.batch_id,),
            )

        conn.close()


class TestRoundTrip:
    def test_write_read_round_trip(self, temp_db, mc_config, samples):
        """Data survives write-read round trip."""
        # Write
        conn = create_mc_database(temp_db)
        write_batch_meta(conn, mc_config)
        write_run_registry(conn, mc_config.batch_id, samples)
        conn.close()

        # Read
        results = load_mc_results(temp_db)

        # Verify
        assert results["batch_meta"]["batch_id"] == mc_config.batch_id
        assert results["batch_meta"]["n_samples"] == 5

        registry = results["registry"]
        assert len(registry) == 5

        # Check sampled parameters match
        for i in range(5):
            row = registry[registry["run_id"] == i].iloc[0]
            assert row["thin_q_factor"] == pytest.approx(samples[i]["thin_q_factor"])
            assert row["thin_residual_ba"] == pytest.approx(
                samples[i]["thin_residual_ba"]
            )
