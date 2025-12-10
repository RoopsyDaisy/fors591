# TODO List - FVS Tools and Assignment 5

## Completed ✅

- [x] Identified root cause of 11 ft²/ac BA discrepancy (extra keywords)
- [x] Updated `keyword_builder.py` to use Web GUI minimal keyword style
- [x] Updated `config.py` to remove deprecated options
- [x] Added documentation in `docs/fvs_keyword_discovery.md`
- [x] Added BA validation to `run_assignment5.py`
- [x] Added `clear_output_directory()` to ensure fresh results
- [x] Cleaned up test scripts and output directories
- [x] Fixed TreeSQL query (Stand_CN not Stand_ID)
- [x] Verified base scenario BA = 161.2 ft²/ac at 2123 ✅
- [x] Updated `analyze_assignment5.py` to handle table name variations
- [x] Fixed NaN in final year by running 110 years (11 cycles) instead of 100
- [x] Remove R from the project (kept reference scripts)
- [x] Added IF-THEN conditional thinning to keyword_builder.py
- [x] Added all required output tables: TreeLiDB, CalbStDB, InvStats, FuelReDB
- [x] **Fixed harv1 thinning** - MinHarv outside IF block, ThinQFA cycle 0
- [x] **Standardized on database input** - Notebook uses `use_database=True`
- [x] Added CalbStDB to legacy keyword path for completeness
- [x] **Fixed output parsing** - Use FVS_Summary2 instead of FVS_Summary (see note below)

## In Progress 🚧

### High Priority

- [ ] **Run full notebook validation**
  - Re-run Assignment5.ipynb with database input
  - Verify calibration statistics appear
  - Confirm 161.2 ft²/ac target for base scenario
  - Verify harv1 scenario produces actual harvests

## Pending 🔄

### Medium Priority

- [ ] **Design scalable simulation framework**
  - Support 1000+ parameter combinations
  - Consider parallel execution
  - Optimize output aggregation from multiple runs

- [ ] **Add batch run support to runner.py**
  - The `build_batch_keyword_file()` function exists
  - Need to add batch execution support to `run_fvs()`
  - Would run all stands in single FVS invocation (faster)

- [ ] **Verify canopy cover calculation**
  - Values seem low (44-52%)
  - May need to adjust SPMCDBH parameters

### Low Priority

- [ ] **Add unit tests for keyword_builder.py**
  - Test Web GUI style output format
  - Test legacy file-based output format

- [ ] **Document MINHARV and THINQFA keyword formats**
  - Add to `docs/fvs_confirmed_facts.md`

## Architecture Decisions

### Database Input vs Legacy (TREELIST) Input

**Decision: Use database input (`use_database=True`) for all production runs.**

| Factor | Legacy (TREELIST) | Database (DSNin) |
|--------|-------------------|------------------|
| Setup per run | Write .tre file per stand | Single shared input DB |
| I/O overhead | Many small files | One DB read |
| Multi-stand runs | Separate FVS invocations | Single FVS invocation with StandSQL |
| Output aggregation | Parse N separate FVSOut.db files | All output in one FVSOut.db |
| Calibration fidelity | Uses GROWTH keyword (legacy) | Data-driven from DB columns |
| Parameter sweeps | Regenerate .tre files each time | Modify only .key file |

**For 1000+ simulations with varying parameters, database input is clearly superior.**

## Notes

### Keyword Order (Web GUI Style)
```
StdIdent
StandCN  
MgmtId
InvYear
TimeInt
NumCycle
DataBase DSNOut ... End
TreeList/CutList block
Carbon/Fuels block  
CalbStDB block
InvStats block
DelOTab
Database DSNIn ... END
Compute ... End (if canopy cover)
MinHarv (OUTSIDE IF block!)
If ... bba gt X ... Then
  ThinQFA (cycle 0)
  ThinDBH  
EndIf
SPLabel
Process
STOP
```

### Key Finding
**Never use these keywords with database input** - they interfere with calibration:
- `GROWTH`
- `NOTRIPLE`
- `NOAUTOES`
- `DESIGN`
- `STDINFO`
- `SITECODE`
- `RANNSEED`
- `CALIBSTAT`

### Working Harvest Configuration (from simpass5)
The following keyword structure produces actual harvests:
- `MinHarv` placed BEFORE the IF block (not inside)
- `ThinQFA` uses cycle 0 (applies whenever condition met)
- Format: `MinHarv Year 0 0 0 0 Volume`

### FVS_Summary vs FVS_Summary2 Tables
**Always use `FVS_Summary2` for reading growth projections!**

| Table | Purpose | BA Values |
|-------|---------|-----------|
| `FVS_Summary` | After-treatment values (`ATBA`, `ATSDI`, etc.) | Shows post-removal state |
| `FVS_Summary2` | Standard growth projections | Correct BA trajectory |

When reading `FVS_Summary`, BA may appear to decline even in no-management scenarios because it shows "after treatment" values. `FVS_Summary2` shows the expected increasing BA over time.

The `output_parser.py` was updated to prefer `FVS_Summary2` when available.
