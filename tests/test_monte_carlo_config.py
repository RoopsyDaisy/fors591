"""
Unit tests for Monte Carlo configuration and sampling.

Tests validation, reproducibility, and correctness of parameter sampling.
"""

from pathlib import Path

import pytest

from fvs_tools.config import FVSSimulationConfig
from fvs_tools.monte_carlo import (
    BooleanParameterSpec,
    DiscreteUniformSpec,
    MonteCarloConfig,
    UniformParameterSpec,
    generate_parameter_samples,
)


# Fixtures
@pytest.fixture
def base_config():
    """Basic FVS configuration for testing."""
    return FVSSimulationConfig(
        name="test",
        num_years=50,
        cycle_length=10,
    )


# ParameterSpec validation tests
class TestUniformParameterSpec:
    def test_valid_spec(self):
        spec = UniformParameterSpec("thin_q_factor", 1.5, 2.5)
        assert spec.name == "thin_q_factor"
        assert spec.min_value == 1.5
        assert spec.max_value == 2.5

    def test_min_greater_than_max_raises(self):
        with pytest.raises(ValueError, match="min_value.*must be < max_value"):
            UniformParameterSpec("thin_q_factor", 2.5, 1.5)

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Invalid parameter name"):
            UniformParameterSpec("invalid_param", 1.0, 2.0)


class TestBooleanParameterSpec:
    def test_valid_spec_default_prob(self):
        spec = BooleanParameterSpec("enable_calibration")
        assert spec.name == "enable_calibration"
        assert spec.probability_true == 0.5

    def test_valid_spec_custom_prob(self):
        spec = BooleanParameterSpec("enable_calibration", 0.7)
        assert spec.probability_true == 0.7

    def test_probability_out_of_range_raises(self):
        with pytest.raises(ValueError, match="probability_true must be in"):
            BooleanParameterSpec("enable_calibration", 1.5)

        with pytest.raises(ValueError, match="probability_true must be in"):
            BooleanParameterSpec("enable_calibration", -0.1)


class TestDiscreteUniformSpec:
    def test_valid_spec(self):
        spec = DiscreteUniformSpec("fvs_random_seed", 1, 99999)
        assert spec.name == "fvs_random_seed"
        assert spec.min_value == 1
        assert spec.max_value == 99999

    def test_min_greater_than_max_raises(self):
        with pytest.raises(ValueError, match="min_value.*must be <= max_value"):
            DiscreteUniformSpec("fvs_random_seed", 100, 10)

    def test_equal_min_max_allowed(self):
        # Edge case: single value
        spec = DiscreteUniformSpec("fvs_random_seed", 42, 42)
        assert spec.min_value == spec.max_value


# MonteCarloConfig validation tests
class TestMonteCarloConfig:
    def test_valid_config_minimal(self, base_config):
        config = MonteCarloConfig(
            batch_seed=42,
            n_samples=10,
            parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
            base_config=base_config,
        )
        assert config.batch_seed == 42
        assert config.n_samples == 10
        assert len(config.parameter_specs) == 1
        assert config.n_workers == 4  # Default

    def test_batch_id_auto_generated(self, base_config):
        config = MonteCarloConfig(
            batch_seed=42,
            n_samples=10,
            parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
            base_config=base_config,
        )
        assert config.batch_id is not None
        assert config.batch_id.startswith("mc_")  # Timestamp format
        assert len(config.batch_id) == 18  # 'mc_YYYYMMDD_HHMMSS'

    def test_output_base_auto_generated(self, base_config):
        config = MonteCarloConfig(
            batch_seed=42,
            n_samples=10,
            parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
            base_config=base_config,
        )
        assert config.output_base is not None
        assert "mc_batch_" in str(config.output_base)
        assert isinstance(config.output_base, Path)

    def test_zero_samples_raises(self, base_config):
        with pytest.raises(ValueError, match="n_samples must be > 0"):
            MonteCarloConfig(
                batch_seed=42,
                n_samples=0,
                parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
                base_config=base_config,
            )

    def test_zero_workers_raises(self, base_config):
        with pytest.raises(ValueError, match="n_workers must be > 0"):
            MonteCarloConfig(
                batch_seed=42,
                n_samples=10,
                parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
                base_config=base_config,
                n_workers=0,
            )

    def test_empty_parameter_specs_raises(self, base_config):
        with pytest.raises(ValueError, match="parameter_specs cannot be empty"):
            MonteCarloConfig(
                batch_seed=42,
                n_samples=10,
                parameter_specs=[],
                base_config=base_config,
            )

    def test_duplicate_parameter_names_raises(self, base_config):
        with pytest.raises(ValueError, match="Duplicate parameter names"):
            MonteCarloConfig(
                batch_seed=42,
                n_samples=10,
                parameter_specs=[
                    UniformParameterSpec("thin_q_factor", 1.5, 2.5),
                    UniformParameterSpec("thin_q_factor", 1.0, 3.0),  # Duplicate
                ],
                base_config=base_config,
            )


# Sampling tests
class TestGenerateParameterSamples:
    def test_correct_number_of_samples(self, base_config):
        config = MonteCarloConfig(
            batch_seed=42,
            n_samples=5,
            parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
            base_config=base_config,
        )
        samples = generate_parameter_samples(config)
        assert len(samples) == 5

    def test_all_samples_have_run_metadata(self, base_config):
        config = MonteCarloConfig(
            batch_seed=42,
            n_samples=3,
            parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
            base_config=base_config,
        )
        samples = generate_parameter_samples(config)

        for i, sample in enumerate(samples):
            assert "run_id" in sample
            assert sample["run_id"] == i
            assert "run_seed" in sample
            assert isinstance(sample["run_seed"], int)

    def test_all_parameters_sampled(self, base_config):
        config = MonteCarloConfig(
            batch_seed=42,
            n_samples=2,
            parameter_specs=[
                UniformParameterSpec("thin_q_factor", 1.5, 2.5),
                UniformParameterSpec("thin_residual_ba", 50.0, 80.0),
                BooleanParameterSpec("enable_calibration"),
            ],
            base_config=base_config,
        )
        samples = generate_parameter_samples(config)

        for sample in samples:
            assert "thin_q_factor" in sample
            assert "thin_residual_ba" in sample
            assert "enable_calibration" in sample

    def test_reproducibility_same_seed(self, base_config):
        """Same batch_seed should produce identical samples."""
        config1 = MonteCarloConfig(
            batch_seed=42,
            n_samples=10,
            parameter_specs=[
                UniformParameterSpec("thin_q_factor", 1.5, 2.5),
                BooleanParameterSpec("enable_calibration"),
            ],
            base_config=base_config,
        )
        config2 = MonteCarloConfig(
            batch_seed=42,  # Same seed
            n_samples=10,
            parameter_specs=[
                UniformParameterSpec("thin_q_factor", 1.5, 2.5),
                BooleanParameterSpec("enable_calibration"),
            ],
            base_config=base_config,
        )

        samples1 = generate_parameter_samples(config1)
        samples2 = generate_parameter_samples(config2)

        assert samples1 == samples2

    def test_different_seeds_produce_different_samples(self, base_config):
        """Different batch_seed should produce different samples."""
        config1 = MonteCarloConfig(
            batch_seed=42,
            n_samples=10,
            parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
            base_config=base_config,
        )
        config2 = MonteCarloConfig(
            batch_seed=123,  # Different seed
            n_samples=10,
            parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
            base_config=base_config,
        )

        samples1 = generate_parameter_samples(config1)
        samples2 = generate_parameter_samples(config2)

        assert samples1 != samples2

    def test_uniform_samples_in_range(self, base_config):
        """Uniform samples should fall within specified bounds."""
        config = MonteCarloConfig(
            batch_seed=42,
            n_samples=100,
            parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
            base_config=base_config,
        )
        samples = generate_parameter_samples(config)

        for sample in samples:
            assert 1.5 <= sample["thin_q_factor"] <= 2.5

    def test_boolean_samples_are_bool(self, base_config):
        """Boolean samples should be True or False."""
        config = MonteCarloConfig(
            batch_seed=42,
            n_samples=50,
            parameter_specs=[BooleanParameterSpec("enable_calibration")],
            base_config=base_config,
        )
        samples = generate_parameter_samples(config)

        for sample in samples:
            assert isinstance(sample["enable_calibration"], bool)

    def test_discrete_samples_are_integers(self, base_config):
        """Discrete samples should be integers in range."""
        config = MonteCarloConfig(
            batch_seed=42,
            n_samples=50,
            parameter_specs=[DiscreteUniformSpec("fvs_random_seed", 1, 100)],
            base_config=base_config,
        )
        samples = generate_parameter_samples(config)

        for sample in samples:
            seed = sample["fvs_random_seed"]
            assert isinstance(seed, int)
            assert 1 <= seed <= 100

    def test_run_seeds_are_unique(self, base_config):
        """Each sample should get a unique run_seed."""
        config = MonteCarloConfig(
            batch_seed=42,
            n_samples=100,
            parameter_specs=[UniformParameterSpec("thin_q_factor", 1.5, 2.5)],
            base_config=base_config,
        )
        samples = generate_parameter_samples(config)

        run_seeds = [sample["run_seed"] for sample in samples]
        # Check most are unique (small chance of collision with random.randint)
        assert len(set(run_seeds)) >= 95  # At least 95% unique
