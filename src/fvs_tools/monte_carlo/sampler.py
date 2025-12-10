"""
Parameter sampling for Monte Carlo simulations.

Provides deterministic sampling from parameter specifications using
a seeded random number generator for reproducibility.
"""

import random
from typing import Any

from .config import (
    BooleanParameterSpec,
    DiscreteUniformSpec,
    MonteCarloConfig,
    ParameterSpec,
    UniformParameterSpec,
)


def _sample_parameter(spec: ParameterSpec, rng: random.Random) -> Any:
    """
    Sample a single value from a parameter specification.

    Args:
        spec: Parameter specification defining the distribution
        rng: Random number generator (must be seeded for reproducibility)

    Returns:
        Sampled value (float, bool, or int depending on spec type)
    """
    if isinstance(spec, UniformParameterSpec):
        return rng.uniform(spec.min_value, spec.max_value)
    elif isinstance(spec, BooleanParameterSpec):
        return rng.random() < spec.probability_true
    elif isinstance(spec, DiscreteUniformSpec):
        return rng.randint(spec.min_value, spec.max_value)
    else:
        raise TypeError(f"Unknown parameter spec type: {type(spec)}")


def generate_parameter_samples(config: MonteCarloConfig) -> list[dict]:
    """
    Generate parameter samples for Monte Carlo batch simulation.

    Uses the batch_seed for deterministic sampling. Each sample includes:
    - run_id: Sequential integer (0 to n_samples-1)
    - run_seed: Unique seed for this run (for FVS RNG)
    - Parameter values from each ParameterSpec

    Args:
        config: Monte Carlo configuration

    Returns:
        List of parameter sample dictionaries. Each dict contains:
        {
            "run_id": int,
            "run_seed": int,
            "param_name_1": value_1,
            "param_name_2": value_2,
            ...
        }

    Example:
        >>> config = MonteCarloConfig(
        ...     batch_seed=42,
        ...     n_samples=3,
        ...     parameter_specs=[
        ...         UniformParameterSpec("thin_q_factor", 1.5, 2.5),
        ...         BooleanParameterSpec("enable_calibration"),
        ...     ],
        ...     base_config=base_config,
        ... )
        >>> samples = generate_parameter_samples(config)
        >>> len(samples)
        3
        >>> samples[0].keys()
        dict_keys(['run_id', 'run_seed', 'thin_q_factor', 'enable_calibration'])
    """
    # Initialize RNG with batch seed for reproducibility
    rng = random.Random(config.batch_seed)

    samples = []
    for run_id in range(config.n_samples):
        # Generate a unique seed for this run
        # Use a large random integer to avoid seed collisions
        run_seed = rng.randint(1, 99999)

        # Build sample dict starting with metadata
        sample = {
            "run_id": run_id,
            "run_seed": run_seed,
        }

        # Sample each parameter
        for spec in config.parameter_specs:
            sample[spec.name] = _sample_parameter(spec, rng)

        samples.append(sample)

    return samples
