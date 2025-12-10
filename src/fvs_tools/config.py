"""
Configuration dataclasses and constants for FVS simulations.

Note: Calibration is now data-driven (from FVS_StandInit/FVS_TreeInit tables).
The tripling, add_regen, random_seed, and output_calibration options were removed
because they interfered with proper calibration when using database input.
See docs/fvs_keyword_discovery.md for details.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# Default FVS paths
DEFAULT_FVS_DIR = Path(
    os.environ.get("FVS_LIB_DIR", "/workspaces/fors591/lib/fvs/FVSie_CmakeDir")
)
DEFAULT_FVS_BIN = DEFAULT_FVS_DIR / "FVSie"

# Default data paths
DEFAULT_STAND_DATA = Path(
    "/workspaces/fors591/data/FVS_Lubrecht_2023_FVS_StandInit.csv"
)
DEFAULT_TREE_DATA = Path(
    "/workspaces/fors591/data/FVS_Lubrecht_2023_FVS_FVS_TreeInit.csv"
)


@dataclass
class FVSSimulationConfig:
    """
    Configuration for an FVS simulation run.

    Attributes:
        name: Simulation name (e.g., "base", "harv1")
        num_years: Total projection years from inventory year
        cycle_length: Years per FVS cycle (default 10)

        # Output options
        output_treelist: Include tree list in output database
        output_carbon: Include carbon reports
        compute_canopy_cover: Add computed variable for canopy cover

        # Management options
        min_harvest_volume: Minimum harvest volume (MINHARV) in bdft/ac
        thin_q_factor: Q-factor for thinning (THINQFA)
        thin_residual_ba: Residual basal area after thinning
        thin_trigger_ba: BA threshold to trigger thinning
        thin_min_dbh: Minimum DBH for thinning
        thin_max_dbh: Maximum DBH for thinning
        thin_year: Year to apply thinning (None = all years if trigger set)

        # Paths
        fvs_binary: Path to FVS executable
    """

    name: str
    num_years: int = 100
    cycle_length: int = 10

    # Run identification
    run_id: str = field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S")
    )

    # Batch tracking (set automatically by run_batch_simulation)
    batch_id: str | None = field(default=None, repr=False)
    run_index: int | None = field(default=None, repr=False)

    # Output options
    output_treelist: bool = False  # Disabled by default - large output
    output_carbon: bool = True
    compute_canopy_cover: bool = True

    # Management
    min_harvest_volume: float | None = None  # MINHARV
    thin_q_factor: float | None = None  # THINQ Q-factor
    thin_residual_ba: float | None = None  # THINQ Residual BA
    thin_trigger_ba: float | None = None  # BA threshold to trigger thinning
    thin_min_dbh: float = 0.0  # Min DBH for thinning
    thin_max_dbh: float = 999.0  # Max DBH for thinning
    thin_year: int | None = None  # Year to apply thinning

    # Monte Carlo parameters (Phase 3)
    mortality_multiplier: float | None = None  # FixMort: multiplier (0.5-2.0 typical)
    enable_calibration: bool = True  # NoCaLib: when False, disables calibration
    fvs_random_seed: int | None = None  # RanNSeed: FVS internal random seed

    # Paths
    fvs_binary: Path = field(default_factory=lambda: DEFAULT_FVS_BIN)

    # Internal: start year (set from stand data during run)
    _start_year: int | None = field(default=None, repr=False)

    @property
    def num_cycles(self) -> int:
        """Calculate number of FVS cycles needed for user-requested duration."""
        return (self.num_years + self.cycle_length - 1) // self.cycle_length

    @property
    def internal_num_cycles(self) -> int:
        """Cycles to actually run (one extra for complete carbon/compute output)."""
        return self.num_cycles + 1

    @property
    def target_end_year(self) -> int | None:
        """The final year the user expects in output (start_year + num_years)."""
        if self._start_year is None:
            return None
        return self._start_year + self.num_years

    def __post_init__(self):
        """Validate configuration."""
        if self.num_years <= 0:
            raise ValueError("num_years must be positive")
        if self.cycle_length <= 0:
            raise ValueError("cycle_length must be positive")
        if not Path(self.fvs_binary).exists():
            raise FileNotFoundError(f"FVS binary not found: {self.fvs_binary}")

        # Validate Monte Carlo parameters
        if self.mortality_multiplier is not None and not (
            0.0 < self.mortality_multiplier <= 5.0
        ):
            raise ValueError(
                f"mortality_multiplier must be in range (0.0, 5.0], got {self.mortality_multiplier}"
            )

        if self.fvs_random_seed is not None and not (
            1 <= self.fvs_random_seed <= 99999
        ):
            raise ValueError(
                f"fvs_random_seed must be in range [1, 99999], got {self.fvs_random_seed}"
            )
