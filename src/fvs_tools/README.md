# FVS Tools Library

Python library for running Forest Vegetation Simulator (FVS) batch simulations.

## Overview

This library provides a clean interface for:
- Loading FVS-ready stand and tree inventory data
- Generating FVS keyword and tree list files
- Running FVS simulations programmatically
- Parsing FVS SQLite output databases
- Batch processing multiple stands
- Aggregating results across stands and time periods

## Installation

The library is located in `src/fvs_tools/` and can be imported after adding `src/` to your Python path:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent / "src"))

import fvs_tools as fvs
```

## Quick Start

### Load and Filter Data

```python
# Load full Lubrecht 2023 dataset
stands = fvs.load_stands()
trees = fvs.load_trees()

# Filter to specific plots
section6_plots = [99, 100, 101, 293, 294, 295, 296, 297]
stands_sec6, trees_sec6 = fvs.filter_by_plot_ids(stands, trees, section6_plots)
```

### Configure Simulation

```python
config = fvs.FVSSimulationConfig(
    name="base_no_management",
    num_years=100,
    calibrate=True,
    tripling=False,
    add_regen=False,
    output_carbon=True,
    compute_canopy_cover=True
)
```

### Run Batch Simulation

```python
from pathlib import Path

results = fvs.run_batch_simulation(
    stands=stands_sec6,
    trees=trees_sec6,
    config=config,
    output_base=Path("outputs/my_simulation")
)

# Access results
summary = results["summary_all"]       # All stand summaries
carbon = results["carbon_all"]         # Carbon pools
compute = results["compute_all"]       # Computed variables
calibration = results["calibration_stats"]  # Calibration statistics
```

### Aggregate by Period

```python
summary_by_period = fvs.aggregate_by_period(
    summary_df=results["summary_all"],
    carbon_df=results["carbon_all"],
    compute_df=results["compute_all"],
    years_per_period=10
)
```

## Module Reference

### `config.py`
- `FVSSimulationConfig`: Dataclass for simulation configuration
- Default paths and constants

### `data_loader.py`
- `load_stands()`: Load stand CSV data
- `load_trees()`: Load tree CSV data
- `filter_by_plot_ids()`: Filter data to specific plots
- `get_stand_trees()`: Get trees for a single stand

### `keyword_builder.py`
- `build_keyword_file()`: Generate FVS keyword file with full options
- `build_keyword_file_simple()`: Simple wrapper for basic keyword files

### `tree_file.py`
- `write_tree_file()`: Write FVS tree list in fixed-width format

### `runner.py`
- `run_fvs()`: Execute FVS binary and capture output
- `check_fvs_errors()`: Parse FVS error file
- `get_fvs_output_files()`: Locate output files

### `output_parser.py`
- `parse_fvs_db()`: Extract all tables from FVS SQLite database
- `get_summary_table()`: Get FVS_Summary table
- `get_carbon_table()`: Get FVS_Carbon table
- `get_compute_table()`: Get FVS_Compute table
- `extract_calibration_stats()`: Extract calibration statistics
- `summarize_by_year()`: Combine summary, carbon, and compute data

### `batch.py`
- `run_single_stand()`: Run simulation for one stand
- `run_batch_simulation()`: Run multiple stands and aggregate
- `aggregate_by_period()`: Average results by time period

## Design Principles

1. **Reusable**: Functions are modular and can be used independently
2. **Configurable**: All simulation options are exposed through `FVSSimulationConfig`
3. **Testable**: Each module has clear inputs/outputs
4. **Extensible**: Easy to add new management scenarios or output parsers

## Examples

See `notebooks/Assignment5.ipynb` for a complete example of Part I analysis.

## Testing

Run the test script to validate the library:

```bash
python scripts/test_fvs_tools.py
```

## Requirements

- Python 3.11+
- pandas
- FVS binary (Inland Empire variant)

## Project Structure

```
src/fvs_tools/
├── __init__.py           # Package exports
├── config.py             # Configuration dataclasses
├── data_loader.py        # Data loading utilities
├── keyword_builder.py    # Keyword file generation
├── tree_file.py          # Tree list file writing
├── runner.py             # FVS execution
├── output_parser.py      # SQLite database parsing
└── batch.py              # Batch orchestration
```

## Future Enhancements

Potential additions for Part II (uneven-aged management):
- Management action keywords (Q-factor thinning, MINHARV)
- Harvest volume tracking
- Merchantable carbon calculations
- Scenario comparison utilities
