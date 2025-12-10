"""
Monte Carlo batch simulation for FVS.

This subpackage provides tools for running FVS simulations with randomized
input parameters for sensitivity analysis and uncertainty quantification.

Public API:
    MonteCarloConfig: Configuration for Monte Carlo batch
    UniformParameterSpec: Continuous uniform distribution parameter
    BooleanParameterSpec: Boolean parameter with probability
    DiscreteUniformSpec: Discrete uniform distribution (integer) parameter
    ParameterSpec: Type alias for any parameter spec
    generate_parameter_samples: Generate parameter samples from config
"""

from .config import (
    VALID_PARAMETER_NAMES,
    BooleanParameterSpec,
    DiscreteUniformSpec,
    MonteCarloConfig,
    ParameterSpec,
    UniformParameterSpec,
)
from .database import (
    create_mc_database,
    load_mc_results,
    update_batch_status,
    update_run_status,
    write_batch_error,
    write_batch_meta,
    write_run_registry,
    write_run_summary,
    write_time_series,
)
from .executor import run_monte_carlo_batch
from .outputs import extract_run_summary, extract_time_series
from .sampler import generate_parameter_samples

__all__ = [
    # Configuration classes
    "MonteCarloConfig",
    "UniformParameterSpec",
    "BooleanParameterSpec",
    "DiscreteUniformSpec",
    "ParameterSpec",
    "VALID_PARAMETER_NAMES",
    # Sampling
    "generate_parameter_samples",
    # Batch execution
    "run_monte_carlo_batch",
    # Output extraction
    "extract_run_summary",
    "extract_time_series",
    # Database functions
    "create_mc_database",
    "write_batch_meta",
    "write_run_registry",
    "update_run_status",
    "write_run_summary",
    "write_time_series",
    "write_batch_error",
    "update_batch_status",
    "load_mc_results",
]
