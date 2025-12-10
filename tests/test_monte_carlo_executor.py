"""
Unit tests for Monte Carlo executor.

Tests the parallel execution engine without running actual FVS.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fvs_tools.config import FVSSimulationConfig
from fvs_tools.monte_carlo import MonteCarloConfig, UniformParameterSpec
from fvs_tools.monte_carlo.executor import (
    MC_TO_FVS_PARAM_MAP,
    execute_single_run,
    run_monte_carlo_batch,
)


@pytest.fixture
def base_fvs_config():
    """Base FVS configuration for tests."""
    return FVSSimulationConfig(
        name="test_base",
        num_years=20,
        cycle_length=10,
    )


class TestParameterMapping:
    """Test that Monte Carlo parameters map correctly to FVS config."""

    def test_all_valid_parameters_mapped(self):
        """Verify all parameter specs can be mapped to FVS config."""
        # All parameters from VALID_PARAMETER_NAMES should be in the map
        from fvs_tools.monte_carlo import VALID_PARAMETER_NAMES

        for param in VALID_PARAMETER_NAMES:
            assert param in MC_TO_FVS_PARAM_MAP, f"Parameter {param} not in mapping"

    def test_parameter_values_passed_through(self):
        """Test that parameter values are correctly passed to FVS config."""
        run_params = {
            "run_id": 0,
            "run_seed": 12345,
            "thin_q_factor": 2.3,
            "mortality_multiplier": 1.1,
            "enable_calibration": False,
        }

        base_config = {
            "num_years": 50,
            "cycle_length": 10,
        }

        # Build config dict (same logic as in execute_single_run)
        fvs_config_dict = base_config.copy()
        for mc_param, fvs_param in MC_TO_FVS_PARAM_MAP.items():
            if mc_param in run_params:
                fvs_config_dict[fvs_param] = run_params[mc_param]

        # Verify parameters were mapped
        assert fvs_config_dict["thin_q_factor"] == 2.3
        assert fvs_config_dict["mortality_multiplier"] == 1.1
        assert fvs_config_dict["enable_calibration"] is False
        assert fvs_config_dict["num_years"] == 50  # Base config preserved


class TestExecuteSingleRun:
    """Test execute_single_run function."""

    @patch("fvs_tools.monte_carlo.executor.run_batch_simulation")
    @patch("fvs_tools.monte_carlo.executor.create_fvs_input_db")
    def test_success_case(self, mock_create_db, mock_run_batch, tmp_path):
        """Test successful execution of a single run."""
        # Mock FVS run results
        mock_run_batch.return_value = {
            "run_status": pd.DataFrame({"success": [True, True]}),
            "summary_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "B", "B"],
                    "Year": [2023, 2033, 2023, 2033],
                    "BA": [120, 115, 125, 120],
                    "RBdFt": [1000, 500, 1200, 600],
                }
            ),
            "carbon_all": pd.DataFrame(
                {
                    "StandID": ["A", "A", "B", "B"],
                    "Year": [2023, 2033, 2023, 2033],
                    "Aboveground_Total_Live": [40, 38, 42, 40],
                }
            ),
        }

        run_params = {
            "run_id": 0,
            "run_seed": 12345,
            "thin_q_factor": 2.0,
        }

        base_config = {
            "num_years": 20,
            "cycle_length": 10,
        }

        stands = pd.DataFrame({"STAND_ID": ["A", "B"]})
        trees = pd.DataFrame({"STAND_ID": ["A", "B"], "TREE_ID": [1, 2]})

        result = execute_single_run(
            run_params, stands, trees, base_config, tmp_path, "test_batch_123"
        )

        # Verify success
        assert result["success"] is True
        assert result["run_id"] == 0
        assert result["error"] is None

        # Verify summary extracted
        assert result["summary"] is not None
        assert "cumulative_harvest_bdft" in result["summary"]
        assert result["summary"]["cumulative_harvest_bdft"] > 0

        # Verify time series extracted
        assert result["time_series"] is not None
        assert len(result["time_series"]) > 0

        # Verify output directory created
        run_dir = tmp_path / "run_0000"
        assert run_dir.exists()

    @patch("fvs_tools.monte_carlo.executor.run_batch_simulation")
    @patch("fvs_tools.monte_carlo.executor.create_fvs_input_db")
    def test_partial_failure(self, mock_create_db, mock_run_batch, tmp_path):
        """Test when some stands fail."""
        # Mock FVS run with one failed stand
        mock_run_batch.return_value = {
            "run_status": pd.DataFrame(
                {
                    "success": [True, False],
                    "stand_id": ["A", "B"],
                }
            ),
            "summary_all": pd.DataFrame(),
        }

        run_params = {"run_id": 0, "run_seed": 12345}
        base_config = {"num_years": 20, "cycle_length": 10}
        stands = pd.DataFrame({"STAND_ID": ["A", "B"]})
        trees = pd.DataFrame({"STAND_ID": ["A", "B"], "TREE_ID": [1, 2]})

        result = execute_single_run(
            run_params, stands, trees, base_config, tmp_path, "test_batch_123"
        )

        # Verify failure reported
        assert result["success"] is False
        assert result["error"] is not None
        assert "B" in result["error"]  # Failed stand mentioned

    @patch("fvs_tools.monte_carlo.executor.run_batch_simulation")
    @patch("fvs_tools.monte_carlo.executor.create_fvs_input_db")
    def test_exception_handling(self, mock_create_db, mock_run_batch, tmp_path):
        """Test exception handling."""
        # Mock exception during FVS run
        mock_run_batch.side_effect = RuntimeError("FVS crashed")

        run_params = {"run_id": 0, "run_seed": 12345}
        base_config = {"num_years": 20, "cycle_length": 10}
        stands = pd.DataFrame({"STAND_ID": ["A"]})
        trees = pd.DataFrame({"STAND_ID": ["A"], "TREE_ID": [1]})

        result = execute_single_run(
            run_params, stands, trees, base_config, tmp_path, "test_batch_123"
        )

        # Verify exception captured
        assert result["success"] is False
        assert result["error"] == "FVS crashed"

    @patch("fvs_tools.monte_carlo.executor.run_batch_simulation")
    @patch("fvs_tools.monte_carlo.executor.create_fvs_input_db")
    def test_output_directory_structure(self, mock_create_db, mock_run_batch, tmp_path):
        """Verify correct output directory structure."""
        mock_run_batch.return_value = {
            "run_status": pd.DataFrame({"success": [True]}),
            "summary_all": pd.DataFrame(
                {"StandID": ["A"], "Year": [2023], "BA": [120]}
            ),
        }

        run_params = {"run_id": 5, "run_seed": 12345}
        base_config = {"num_years": 20, "cycle_length": 10}
        stands = pd.DataFrame({"STAND_ID": ["A"]})
        trees = pd.DataFrame({"STAND_ID": ["A"], "TREE_ID": [1]})

        execute_single_run(
            run_params, stands, trees, base_config, tmp_path, "test_batch_123"
        )

        # Verify directory name format
        run_dir = tmp_path / "run_0005"
        assert run_dir.exists()


class TestRunMonteCarloBatch:
    """
    Test run_monte_carlo_batch orchestrator.

    NOTE: Mocking ProcessPoolExecutor is complex due to pickling issues.
    These tests are skipped in favor of integration tests that run real (small) batches.
    """

    @pytest.mark.skip(
        reason="Mocking ProcessPoolExecutor has pickling issues - use integration test instead"
    )
    @patch("fvs_tools.monte_carlo.executor.ProcessPoolExecutor")
    @patch("fvs_tools.monte_carlo.executor.as_completed")
    def test_single_worker(
        self, mock_as_completed, mock_pool_class, base_fvs_config, tmp_path
    ):
        """Test batch execution with single worker (serial)."""
        # Create mock futures with results
        mock_futures = []
        for run_id in range(3):
            mock_future = MagicMock()
            mock_future.result.return_value = {
                "run_id": run_id,
                "success": True,
                "summary": {
                    "cumulative_harvest_bdft": 1000.0,
                    "final_total_carbon": 40.0,
                },
                "time_series": pd.DataFrame({"year": [2023], "ba": [120]}),
                "error": None,
            }
            mock_futures.append(mock_future)

        # Mock executor
        mock_pool = MagicMock()
        mock_pool.submit.side_effect = mock_futures
        mock_pool.__enter__.return_value = mock_pool
        mock_pool.__exit__.return_value = None
        mock_pool_class.return_value = mock_pool

        # Mock as_completed to return futures with run_id mapping
        future_to_run = {fut: i for i, fut in enumerate(mock_futures)}
        mock_as_completed.return_value = iter(mock_futures)

        # Patch the future_to_run_id dict access
        with patch.dict(
            "fvs_tools.monte_carlo.executor.__dict__",
            {"future_to_run_id": future_to_run},
            clear=False,
        ):
            mc_config = MonteCarloConfig(
                batch_seed=42,
                n_samples=3,
                n_workers=1,
                parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
                base_config=base_fvs_config,
            )

            stands = pd.DataFrame({"STAND_ID": ["A"], "PlotID": [1]})
            trees = pd.DataFrame({"STAND_ID": ["A"], "TREE_ID": [1]})

            results_db = run_monte_carlo_batch(mc_config, stands, trees, tmp_path)

            # Verify database created
            assert results_db.exists()
            assert results_db.name == "mc_results.db"

            # Verify all runs submitted
            assert mock_pool.submit.call_count == 3

    @pytest.mark.skip(
        reason="Mocking ProcessPoolExecutor has pickling issues - use integration test instead"
    )
    @patch("fvs_tools.monte_carlo.executor.execute_single_run")
    def test_multiple_workers(self, mock_execute, base_fvs_config, tmp_path):
        """Test batch execution with multiple workers (parallel)."""

        # Mock successful runs
        def mock_run(run_params, stands, trees, base_config, output_dir):
            return {
                "run_id": run_params["run_id"],
                "success": True,
                "summary": {
                    "cumulative_harvest_bdft": 1000.0,
                    "final_total_carbon": 40.0,
                },
                "time_series": pd.DataFrame({"year": [2023], "ba": [120]}),
                "error": None,
            }

        mock_execute.side_effect = mock_run

        mc_config = MonteCarloConfig(
            batch_seed=42,
            n_samples=5,
            n_workers=2,
            parameter_specs=[
                UniformParameterSpec("thin_q_factor", 1.5, 2.5),
            ],
            base_config=base_fvs_config,
        )

        stands = pd.DataFrame({"STAND_ID": ["A"], "PlotID": [1]})
        trees = pd.DataFrame({"STAND_ID": ["A"], "TREE_ID": [1]})

        results_db = run_monte_carlo_batch(mc_config, stands, trees, tmp_path)

        # Verify all runs executed
        assert mock_execute.call_count == 5
        assert results_db.exists()

    @pytest.mark.skip(
        reason="Mocking ProcessPoolExecutor has pickling issues - use integration test instead"
    )
    @patch("fvs_tools.monte_carlo.executor.execute_single_run")
    def test_progress_callback(self, mock_execute, base_fvs_config, tmp_path):
        """Test that progress callback is called correctly."""

        # Mock successful runs
        def mock_run(run_params, stands, trees, base_config, output_dir):
            return {
                "run_id": run_params["run_id"],
                "success": True,
                "summary": {"cumulative_harvest_bdft": 1000.0},
                "time_series": pd.DataFrame(),
                "error": None,
            }

        mock_execute.side_effect = mock_run

        # Track callback invocations
        callback_calls = []

        def progress_callback(completed, total):
            callback_calls.append((completed, total))

        mc_config = MonteCarloConfig(
            batch_seed=42,
            n_samples=3,
            n_workers=1,
            parameter_specs=[
                UniformParameterSpec("thin_q_factor", 1.5, 2.5),
            ],
            base_config=base_fvs_config,
        )

        stands = pd.DataFrame({"STAND_ID": ["A"], "PlotID": [1]})
        trees = pd.DataFrame({"STAND_ID": ["A"], "TREE_ID": [1]})

        run_monte_carlo_batch(
            mc_config, stands, trees, tmp_path, progress_callback=progress_callback
        )

        # Verify callback called for each completion
        assert len(callback_calls) == 3
        assert callback_calls[0] == (1, 3)
        assert callback_calls[1] == (2, 3)
        assert callback_calls[2] == (3, 3)

    @pytest.mark.skip(
        reason="Mocking ProcessPoolExecutor has pickling issues - use integration test instead"
    )
    @patch("fvs_tools.monte_carlo.executor.execute_single_run")
    def test_partial_failure_handling(self, mock_execute, base_fvs_config, tmp_path):
        """Test handling when some runs succeed and some fail."""

        # Mock mixed results
        def mock_run(run_params, stands, trees, base_config, output_dir):
            run_id = run_params["run_id"]
            if run_id == 1:  # Second run fails
                return {
                    "run_id": run_id,
                    "success": False,
                    "error": "Simulated failure",
                    "summary": None,
                    "time_series": None,
                }
            return {
                "run_id": run_id,
                "success": True,
                "summary": {"cumulative_harvest_bdft": 1000.0},
                "time_series": pd.DataFrame(),
                "error": None,
            }

        mock_execute.side_effect = mock_run

        mc_config = MonteCarloConfig(
            batch_seed=42,
            n_samples=3,
            n_workers=1,
            parameter_specs=[
                UniformParameterSpec("thin_q_factor", 1.5, 2.5),
            ],
            base_config=base_fvs_config,
        )

        stands = pd.DataFrame({"STAND_ID": ["A"], "PlotID": [1]})
        trees = pd.DataFrame({"STAND_ID": ["A"], "TREE_ID": [1]})

        # Should complete with partial status (not raise exception)
        results_db = run_monte_carlo_batch(mc_config, stands, trees, tmp_path)

        assert results_db.exists()

        # Check database for status (would need to read it to verify)
        # For now, just verify it completed without exception

    @pytest.mark.skip(
        reason="Mocking ProcessPoolExecutor has pickling issues - use integration test instead"
    )
    @patch("fvs_tools.monte_carlo.executor.execute_single_run")
    def test_all_runs_fail(self, mock_execute, base_fvs_config, tmp_path):
        """Test that RuntimeError is raised when all runs fail."""

        # Mock all failures
        def mock_run(run_params, stands, trees, base_config, output_dir):
            return {
                "run_id": run_params["run_id"],
                "success": False,
                "error": "All runs fail",
                "summary": None,
                "time_series": None,
            }

        mock_execute.side_effect = mock_run

        mc_config = MonteCarloConfig(
            batch_seed=42,
            n_samples=2,
            n_workers=1,
            parameter_specs=[
                UniformParameterSpec("thin_q_factor", 1.5, 2.5),
            ],
            base_config=base_fvs_config,
        )

        stands = pd.DataFrame({"STAND_ID": ["A"], "PlotID": [1]})
        trees = pd.DataFrame({"STAND_ID": ["A"], "TREE_ID": [1]})

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="All Monte Carlo runs failed"):
            run_monte_carlo_batch(mc_config, stands, trees, tmp_path)

    @pytest.mark.skip(
        reason="Mocking ProcessPoolExecutor has pickling issues - use integration test instead"
    )
    @patch("fvs_tools.monte_carlo.executor.execute_single_run")
    def test_plot_filtering(self, mock_execute, base_fvs_config, tmp_path):
        """Test that plot_ids filter is applied."""

        # Mock successful runs
        def mock_run(run_params, stands, trees, base_config, output_dir):
            return {
                "run_id": run_params["run_id"],
                "success": True,
                "summary": {"cumulative_harvest_bdft": 1000.0},
                "time_series": pd.DataFrame(),
                "error": None,
            }

        mock_execute.side_effect = mock_run

        mc_config = MonteCarloConfig(
            batch_seed=42,
            n_samples=2,
            n_workers=1,
            plot_ids=[99, 100],  # Filter to specific plots
            parameter_specs=[
                UniformParameterSpec("thin_q_factor", 1.5, 2.5),
            ],
            base_config=base_fvs_config,
        )

        # Create stands with multiple plot IDs
        stands = pd.DataFrame(
            {
                "STAND_ID": ["A", "B", "C"],
                "PlotID": [99, 100, 200],  # Only first two should be included
            }
        )
        trees = pd.DataFrame(
            {
                "STAND_ID": ["A", "A", "B", "B", "C", "C"],
                "TREE_ID": [1, 2, 3, 4, 5, 6],
            }
        )

        run_monte_carlo_batch(mc_config, stands, trees, tmp_path)

        # Verify execute_single_run was called with filtered data
        # Get the stands argument from first call
        call_args = mock_execute.call_args_list[0]
        stands_arg = call_args[0][1]  # Second positional arg

        # Should only have 2 stands (plot 99 and 100)
        assert len(stands_arg) == 2
        assert set(stands_arg["PlotID"]) == {99, 100}
