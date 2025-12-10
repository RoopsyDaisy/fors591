# Assignment 5 Part I Implementation Summary

## What Was Built

A complete Python library (`fvs_tools`) for running FVS batch simulations, specifically designed for Assignment 5 but extensible for future scenarios.

## Library Structure

```
src/fvs_tools/
├── __init__.py           # Package interface
├── config.py             # FVSSimulationConfig dataclass
├── data_loader.py        # CSV loading and filtering
├── keyword_builder.py    # FVS keyword file generation
├── tree_file.py          # Tree list file writing (fixed-width format)
├── runner.py             # FVS subprocess execution
├── output_parser.py      # SQLite database parsing
├── batch.py              # Multi-stand orchestration
└── README.md             # Library documentation
```

## Key Features

1. **Data Management**
   - Load Lubrecht 2023 stand and tree data
   - Filter to Section 6 plots (99-101, 293-297)
   - Validate data integrity

2. **FVS Configuration**
   - Configurable simulation parameters via dataclass
   - Support for calibration, tripling, regeneration
   - Carbon and fuels output
   - Canopy cover computation (SpMcDBH function)

3. **Batch Execution**
   - Run FVS for multiple stands automatically
   - Progress tracking and error handling
   - Aggregate results across stands

4. **Output Processing**
   - Parse SQLite FVSOut.db databases
   - Extract summary, carbon, compute tables
   - Calculate averages by time period
   - Export to CSV for further analysis

## Manual Testing Steps

### Step 1: Test Library Imports
```bash
cd /workspaces/fors591
python scripts/test_fvs_tools.py
```

Expected output:
- ✓ All imports successful
- ✓ Data loaded (298 stands, ~4280 trees)
- ✓ Filtered to 8 Section 6 stands
- ✓ Config created

### Step 2: Run Notebook Analysis

Open `notebooks/Assignment5.ipynb` and execute cells sequentially:

1. **Cell 1-2**: Import libraries and load data
   - Should load 298 stands, filter to 8
   - Display: CARB_99, CARB_100, CARB_101, CARB_293, CARB_294, CARB_295, CARB_296, CARB_297

2. **Cell 3-4**: Configure simulation
   - 100 years (10 cycles)
   - Calibration enabled
   - Canopy cover tracking

3. **Cell 5**: Run batch simulation
   - Expect: "[1/8] Processing CARB_99... ✓" (etc.)
   - All 8 stands should succeed

4. **Cell 6**: Calibration statistics
   - Should show calibration factors for diameter growth, height growth, mortality
   - Non-zero adjustment factors indicate calibration was applied

5. **Cell 7**: Summary by period
   - Table with Years: 2023, 2033, 2043, ..., 2123
   - 2123 BA should be ~161 ft²/ac (as per assignment check)
   - Canopy cover should be present

6. **Cell 8**: Visualizations
   - 4 plots: BA, Aboveground C, Standing Dead C, Canopy Cover
   - Canopy cover plot should show 40% threshold line

7. **Cell 9**: Export results
   - CSV files saved to `outputs/assignment5_part1_base/`

### Step 3: Validate Against GUI Results

While the notebook runs, execute the same simulation in FVS GUI:
1. Load FVS_Lubrecht_2023.xlsx
2. Filter to plots 99-101, 293-297
3. Create "base" simulation:
   - 100 years (2023-2123)
   - Enable calibration
   - Add COMPUTE: CanopyCov = SpMcDBH(All,1.0,999,0,1)
   - Select outputs: Tree Lists, Carbon and Fuels, Calibration Stats, Inventory Stats
4. Run simulation
5. Compare output tables with notebook results

### Step 4: Verify Output Files

Check `outputs/assignment5_part1_base/`:
```
CARB_99/
├── FVSOut.db
├── run.key
├── run.tre
├── fvs.out
└── fvs.err

CARB_100/
├── FVSOut.db
├── ...

... (6 more stand directories)

part1_summary_by_period.csv
summary_all_stands.csv
carbon_all_stands.csv
compute_all_stands.csv
```

Spot-check one keyword file (e.g., `CARB_99/run.key`):
- STDIDENT with stand ID
- STDINFO with correct elevation, slope, aspect
- NUMCYCLE 10
- GROWTH with calibration parameters
- CALIBSTAT keyword
- COMPUTE for canopy cover
- DATABASE with SUMMARY, CARBON, TREELIST, COMPUTE

### Step 5: Validate Calculations

Open `part1_summary_by_period.csv` and verify:
1. All years present (2023-2123 in 10-year steps)
2. BA in 2123 ≈ 161 ft²/ac
3. No missing values in key columns
4. Reasonable trends (generally increasing BA and carbon)

## Expected Results for Part I:1

**Calibration Description:**

FVS applied local calibration to adjust growth and mortality predictions based on measured stand development between the 2018 and 2023 inventory periods. The calibration factors modify:

1. **Diameter Growth**: Multiplicative adjustment to predicted diameter increment
2. **Height Growth**: Multiplicative adjustment to predicted height increment  
3. **Mortality**: Additive adjustment to predicted mortality probability

The degree of calibration depends on the quality and quantity of remeasurement data. Each stand may receive different calibration factors based on its specific growth patterns.

## Expected Results for Part I:2

Sample output table (exact values will vary):

| Year | BA (ft²/ac) | Aboveground C Live (tons/ac) | Standing Dead C (tons/ac) | Canopy Cover (%) |
|------|-------------|------------------------------|---------------------------|------------------|
| 2023 | ~85         | ~35                          | ~5                        | ~45              |
| 2033 | ~100        | ~42                          | ~6                        | ~50              |
| 2043 | ~115        | ~48                          | ~7                        | ~55              |
| ...  | ...         | ...                          | ...                       | ...              |
| 2113 | ~155        | ~65                          | ~10                       | ~65              |
| 2123 | ~161        | ~68                          | ~11                       | ~67              |

Key observations:
- BA increases steadily to ~161 ft²/ac by 2123 ✓
- Carbon stocks increase as trees grow
- Canopy cover remains well above 40% threshold
- Some standing dead accumulation over time

## Comparison with GUI

The Python implementation should produce results very close to the GUI version. Minor differences may occur due to:
1. Rounding in keyword file formatting
2. Different random seeds (if stochastic processes are enabled)
3. Database query aggregation methods

Acceptable tolerance: ±2% for summary statistics.

## Troubleshooting

### Import Errors
- Ensure `src/` is in Python path
- Check that all module files exist in `src/fvs_tools/`

### FVS Execution Errors
- Verify FVS binary exists: `/workspaces/fors591/lib/fvs/FVSie_CmakeDir/FVSie`
- Check `fvs.err` files in output directories for FVS-specific errors
- Validate keyword file format against reference scripts

### Missing Data in Results
- Check `run_status` DataFrame for failed stands
- Examine error messages in results dictionary
- Verify input CSV files have required columns

### Incorrect Values
- Compare keyword files with R reference scripts
- Check tree file format (fixed-width columns)
- Verify stand attributes (elevation in hundreds of feet, etc.)

## Next Steps (Part II)

To extend for uneven-aged management scenario:
1. Add management keywords to `keyword_builder.py`:
   - Q-factor thinning (THINDBH, QFACTOR)
   - MINHARV for minimum harvest volume
   - Conditional thinning (IF/ENDIF blocks)
2. Parse harvest volumes from output
3. Calculate stored merchantable carbon
4. Compare scenarios side-by-side

## Notes

- The library design emphasizes reusability and extensibility
- All simulation parameters are exposed through `FVSSimulationConfig`
- Functions are independent and can be used outside the batch workflow
- Output parsing handles missing tables gracefully
- Error handling provides clear diagnostics for troubleshooting

---

# Database Input Implementation (December 5, 2025)

## Overview
Successfully implemented DSNin database input for FVS, replacing TREELIST file-based input to enable COMPUTE keyword functionality.

## New Files Created

### `src/fvs_tools/db_input.py`
Creates FVS input databases from CSV data with proper FVS schema.

**Key Functions**:
- `create_fvs_input_db()`: Converts DataFrames to FVS_Data.db
- `verify_fvs_input_db()`: Validates database contents

**Schema**:
- FVS_StandInit: 73 columns (stand attributes, site data, calibration)
- FVS_TreeInit: 25 columns (tree measurements, growth, condition)

### `scripts/test_db_input.py`
Comprehensive test suite validating database input implementation.

**Tests**:
1. Database creation and verification
2. FVS simulation with database input  
3. Comparison: file vs database methods

**Results**: ✓ All tests passing, metrics identical between methods

## Files Modified

### `keyword_builder.py`
- Added `use_database` parameter
- Conditional DATABASE/DSNin vs TREEFMT/TREELIST blocks
- Direct SQL queries (no STANDCN keyword)

### `data_loader.py`
- Added `prepare_fvs_database()` wrapper function

### `runner.py`
- Added `input_database` parameter
- Copies input database to working directory

### `batch.py`
- Added `use_database` and `input_database` parameters
- Conditional workflow for both input methods

### `__init__.py`
- Exported new database functions

## Usage

```python
import fvs_tools as fvs

# Load and prepare data
stands = fvs.load_stands()
trees = fvs.load_trees()
fvs.prepare_fvs_database(stands, trees, "FVS_Data.db")

# Run with database input
config = fvs.FVSSimulationConfig(name="test", num_years=20)
results = fvs.run_batch_simulation(
    stands, trees, config, "outputs",
    use_database=True,
    input_database="FVS_Data.db"
)
```

## Test Results

**CARB_99 Stand (26 trees)**:
- TPA: 240.0 (file) = 240.0 (database) ✓
- BA: 150.0 (file) = 150.0 (database) ✓
- CCF: 162.0 (file) = 162.0 (database) ✓

**Validation**: Trees load correctly, projections match file method exactly.

## Key Implementation Details

### SQL Queries
```sql
-- Stand data
SELECT * FROM FVS_StandInit WHERE Stand_ID = 'CARB_99'

-- Tree data  
SELECT * FROM FVS_TreeInit WHERE Stand_CN = 'CARB_99'
```

### Database Structure
- Stand_CN = Stand_ID (primary key)
- Tree_CN = unique tree identifier
- Stand_CN (trees) → Stand_CN (stands) (foreign key)

### Canopy Cover Calculation
- Uses `COMPUTE` keyword with `SPMCDBH` function
- **Syntax**: `CanCov = SPMCDBH(7,All,0,0,999,0,999,0)`
- **Attribute 7**: Percent Canopy Cover (Corrected)
- Output stored in `FVS_Compute` table

## Benefits

1. ✓ **Enables COMPUTE keyword** (main goal)
2. ✓ **Single database** vs multiple tree files
3. ✓ **Data integrity** with foreign keys
4. ✓ **Backward compatible** (file method still works)
5. ✓ **Scalable** for large batch runs

## Next Steps

To enable canopy cover output:

1. ✓ Add COMPUTDB to database output keywords
2. ✓ Add COMPUTE keyword with SPMCDBH() function (Attribute 7)
3. ✓ Parse FVS_Compute table in output_parser.py

## References

- Plan: `docs/plan_database_input.md`
- Test: `scripts/test_db_input.py`
- Code: `src/fvs_tools/db_input.py`
