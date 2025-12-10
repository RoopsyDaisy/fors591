"""
Scenario management for FVS simulations.

Defines the Scenario class and helpers to generate simulation scenarios
for Assignment 5 (Carbon & Management).
"""

from dataclasses import dataclass
from .config import FVSSimulationConfig


@dataclass
class Scenario:
    """
    Defines a specific FVS simulation scenario.
    """

    name: str
    description: str
    config: FVSSimulationConfig

    @classmethod
    def base(cls, num_years: int = 110) -> "Scenario":
        """
        Create the base scenario (no management).

        Note: Default is 110 years (11 cycles) because FVS_Carbon and FVS_Compute
        don't output the final cycle year. Running 110 years ensures we have
        complete data through year 2123 (10 full cycles of output).
        """
        config = FVSSimulationConfig(
            name="base",
            num_years=num_years,
            output_carbon=True,
            compute_canopy_cover=True,
        )
        return cls(name="base", description="Base run (no management)", config=config)

    @classmethod
    def harvest_min_volume(cls, volume: float, num_years: int = 110) -> "Scenario":
        """Create a scenario with a minimum harvest volume constraint."""
        name = f"minharv_{int(volume)}"
        config = FVSSimulationConfig(
            name=name,
            num_years=num_years,
            output_carbon=True,
            compute_canopy_cover=True,
            min_harvest_volume=volume,
        )
        return cls(
            name=name,
            description=f"Minimum harvest volume: {volume} bdft/ac",
            config=config,
        )

    @classmethod
    def thinning(
        cls,
        q_factor: float,
        residual_ba: float,
        trigger_ba: float | None = None,
        min_dbh: float = 0.0,
        max_dbh: float = 999.0,
        year: int = 2023,
        num_years: int = 100,
    ) -> "Scenario":
        """Create a thinning scenario (Thin from below to Q-factor)."""
        name = f"thin_q{q_factor}_ba{int(residual_ba)}"
        config = FVSSimulationConfig(
            name=name,
            num_years=num_years,
            output_carbon=True,
            compute_canopy_cover=True,
            thin_q_factor=q_factor,
            thin_residual_ba=residual_ba,
            thin_trigger_ba=trigger_ba,
            thin_min_dbh=min_dbh,
            thin_max_dbh=max_dbh,
            thin_year=year,
        )
        return cls(
            name=name,
            description=f"Thinning: Q={q_factor}, ResBA={residual_ba}, Trigger={trigger_ba}",
            config=config,
        )

    @classmethod
    def harv1(cls, num_years: int = 110) -> "Scenario":
        """
        Create the 'harv1' scenario for Assignment 5 Part II.

        Specs:
        - Q-factor: 2.0
        - Residual BA: 65.0
        - Trigger BA: 100.0
        - DBH Range: 2.0 - 24.0
        - Min Harvest Volume: 4500.0 bdft/ac

        Note: Default is 110 years to get complete Carbon/Compute data through 2123.
        """
        name = "harv1"
        config = FVSSimulationConfig(
            name=name,
            num_years=num_years,
            output_carbon=True,
            compute_canopy_cover=True,
            # Thinning specs
            thin_q_factor=2.0,
            thin_residual_ba=65.0,
            thin_trigger_ba=100.0,
            thin_min_dbh=2.0,
            thin_max_dbh=24.0,
            thin_year=None,  # Apply whenever trigger is met
            # Harvest specs
            min_harvest_volume=4500.0,
        )
        return cls(
            name=name,
            description="Part II: Q=2, ResBA=65, TrigBA=100, MinHarv=4500",
            config=config,
        )


def generate_assignment5_scenarios() -> list[Scenario]:
    """
    Generate the list of scenarios required for Assignment 5.
    """
    scenarios = []

    # 1. Base Scenario
    scenarios.append(Scenario.base())

    # 2. Part II: Harvest 1 Scenario
    scenarios.append(Scenario.harv1())

    return scenarios
