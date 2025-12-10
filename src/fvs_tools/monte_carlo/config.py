"""
Configuration dataclasses for Monte Carlo batch simulations.

Defines parameter specifications and batch configuration for sampling
FVS input parameters to perform sensitivity analysis and uncertainty
quantification.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import FVSSimulationConfig


# Valid parameter names that can be sampled
# These match FVSSimulationConfig attributes or new MC-specific parameters
VALID_PARAMETER_NAMES = {
    # Existing FVSSimulationConfig parameters
    "thin_q_factor",
    "thin_residual_ba",
    "thin_trigger_ba",
    "thin_min_dbh",
    "thin_max_dbh",
    "min_harvest_volume",
    # New parameters to be added in Phase 3
    "mortality_multiplier",
    "enable_calibration",
    "fvs_random_seed",
}


@dataclass
class UniformParameterSpec:
    """
    Specification for a continuous uniform distribution parameter.

    Attributes:
        name: Parameter name (must match FVSSimulationConfig attribute)
        min_value: Minimum value (inclusive)
        max_value: Maximum value (inclusive)
    """

    name: str
    min_value: float
    max_value: float

    def __post_init__(self):
        """Validate parameter specification."""
        if self.name not in VALID_PARAMETER_NAMES:
            raise ValueError(
                f"Invalid parameter name '{self.name}'. "
                f"Valid names: {sorted(VALID_PARAMETER_NAMES)}"
            )
        if self.min_value >= self.max_value:
            raise ValueError(
                f"min_value ({self.min_value}) must be < max_value ({self.max_value})"
            )


@dataclass
class BooleanParameterSpec:
    """
    Specification for a boolean parameter.

    Attributes:
        name: Parameter name
        probability_true: Probability of True value (default 0.5)
    """

    name: str
    probability_true: float = 0.5

    def __post_init__(self):
        """Validate parameter specification."""
        if self.name not in VALID_PARAMETER_NAMES:
            raise ValueError(
                f"Invalid parameter name '{self.name}'. "
                f"Valid names: {sorted(VALID_PARAMETER_NAMES)}"
            )
        if not 0.0 <= self.probability_true <= 1.0:
            raise ValueError(
                f"probability_true must be in [0, 1], got {self.probability_true}"
            )


@dataclass
class DiscreteUniformSpec:
    """
    Specification for a discrete uniform distribution parameter (integers).

    Attributes:
        name: Parameter name
        min_value: Minimum value (inclusive)
        max_value: Maximum value (inclusive)
    """

    name: str
    min_value: int
    max_value: int

    def __post_init__(self):
        """Validate parameter specification."""
        if self.name not in VALID_PARAMETER_NAMES:
            raise ValueError(
                f"Invalid parameter name '{self.name}'. "
                f"Valid names: {sorted(VALID_PARAMETER_NAMES)}"
            )
        if self.min_value > self.max_value:
            raise ValueError(
                f"min_value ({self.min_value}) must be <= max_value ({self.max_value})"
            )


# Type alias for any parameter specification
ParameterSpec = UniformParameterSpec | BooleanParameterSpec | DiscreteUniformSpec


@dataclass
class MonteCarloConfig:
    """
    Configuration for a Monte Carlo batch simulation.

    Attributes:
        batch_seed: Random seed for deterministic sampling
        n_samples: Number of parameter samples to generate
        parameter_specs: List of parameter specifications to sample
        base_config: Template FVSSimulationConfig (will be modified per run)
        batch_id: Unique batch identifier (auto-generated if None)
        n_workers: Number of parallel workers (default 4)
        stand_ids: Optional list of stand IDs to filter to
        plot_ids: Optional list of plot IDs to filter to
        output_base: Base directory for outputs (auto-generated if None)
    """

    batch_seed: int
    n_samples: int
    parameter_specs: list[ParameterSpec]
    base_config: "FVSSimulationConfig"  # Forward reference, imported at runtime
    batch_id: str | None = None
    n_workers: int = 4
    stand_ids: list[str] | None = None
    plot_ids: list[int] | None = None
    output_base: Path | None = None

    def __post_init__(self):
        """Validate configuration and set defaults."""
        # Import here to avoid circular dependency
        from ..config import FVSSimulationConfig

        # Validate counts
        if self.n_samples <= 0:
            raise ValueError(f"n_samples must be > 0, got {self.n_samples}")
        if self.n_workers <= 0:
            raise ValueError(f"n_workers must be > 0, got {self.n_workers}")
        if len(self.parameter_specs) == 0:
            raise ValueError("parameter_specs cannot be empty")

        # Validate base_config type
        if not isinstance(self.base_config, FVSSimulationConfig):
            raise TypeError(
                f"base_config must be FVSSimulationConfig, got {type(self.base_config)}"
            )

        # Auto-generate batch_id if not provided
        if self.batch_id is None:
            self.batch_id = f"mc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Auto-generate output_base if not provided
        if self.output_base is None:
            self.output_base = Path(f"outputs/mc_batch_{self.batch_id}")
        else:
            self.output_base = Path(self.output_base)

        # Validate parameter names are unique
        param_names = [spec.name for spec in self.parameter_specs]
        if len(param_names) != len(set(param_names)):
            duplicates = [name for name in param_names if param_names.count(name) > 1]
            raise ValueError(f"Duplicate parameter names: {set(duplicates)}")
