# FVS Keyword Discovery: Web GUI vs Custom Keywords

**Date**: 2025-12-06  
**Status**: ROOT CAUSE IDENTIFIED AND RESOLVED

## Summary

After extensive debugging, we discovered that **extra keywords** in our custom keyword generation caused a **~11 ft²/ac reduction** in projected basal area compared to the FVS Web GUI output.

- **Our Custom Keywords**: 150.1 ft²/ac average BA at year 2123
- **Web GUI Minimal Keywords**: 161.25 ft²/ac average BA at year 2123
- **Target**: 161 ft²/ac ✅

## Root Cause

The following keywords, when added to keyword files, **suppress growth calibration or modify model behavior**:

| Keyword | Effect | Impact on BA |
|---------|--------|--------------|
| `GROWTH 1 5 1 5 5` | Modifies diameter/height growth calibration sampling | **MAJOR** - Changes calibration behavior |
| `NOTRIPLE` | Disables BAF tripling for small trees | Reduces small tree representation |
| `NOAUTOES` | Disables automatic regeneration establishment | May affect ingrowth |
| `DESIGN -10.0...` | Overrides sampling design from data | Redundant with DB input |
| `STDINFO` | Overrides stand attributes | Redundant - data is in database |
| `SITECODE` | Overrides site code | Redundant - data is in database |
| `RANNSEED` | Sets random seed | Different randomization |
| `CALIBSTAT` | Outputs calibration stats | Minor, but adds overhead |

### The Critical Issue: `GROWTH` Keyword

The `GROWTH` keyword specifies which tree records to use for calibration:
```
GROWTH    dg_trans  dg_measure  htg_trans  htg_measure  mort_measure
```

- `dg_trans=1`: Use only trees with ≥1 year of transition period growth
- `dg_measure=5`: Use only trees with ≥5 years of measured growth

When these values are too restrictive, **fewer trees qualify for calibration**, leading to:
1. Less accurate calibration factors
2. Calibration closer to default (1.0) rather than data-driven
3. Different projected growth rates

## Web GUI Keyword Structure (CORRECT)

The FVS Web GUI generates **minimal keyword files** that rely on database input for all stand/tree attributes:

```
StdIdent
{stand_id:26s}{project_name}
StandCN
{stand_id}
MgmtId
A002
InvYear       {inv_year}
TimeInt                 10 
NumCycle     {num_cycles} 

DataBase
DSNOut
{output_db}
Summary        2
End

Database
DSNIn
FVS_Data.db
StandSQL
SELECT * FROM FVS_StandInit
WHERE Stand_ID= '%StandID%'
EndSQL
TreeSQL
SELECT * FROM FVS_TreeInit
WHERE Stand_ID= '%StandID%'
EndSQL
END

Compute            0
Pc_can_cover=SPMCDBH(7,All,0,1,200,0,500,0,0)
End
SPLabel
  All_Stands, & 
  {group_label}
Process
```

### Key Differences from Our Implementation

1. **No `STDINFO`** - Stand attributes (aspect, slope, elevation) come from database
2. **No `SITECODE`** - Site index comes from database
3. **No `DESIGN`** - Sampling design comes from database  
4. **No `GROWTH`** - Let FVS use default calibration behavior
5. **No `NOTRIPLE`** - Allow default tripling behavior
6. **No `NOAUTOES`** - Allow default establishment behavior
7. **No `RANNSEED`** - Use default randomization
8. **`MgmtId A002`** - Management identifier (optional but matches Web GUI)
9. **`TimeInt 10`** - Time interval between cycles
10. **`Summary 2`** - Output to database with append mode

## Calibration Per-Stand (NOT Pooled)

Initial hypothesis that Web GUI uses "pooled" species-level calibration was **WRONG**.

Actual Web GUI calibration is **per-stand**, showing wide variation:

| Stand | PSME Scale | ABLA Scale |
|-------|------------|------------|
| CARB_99 | 0.913 | - |
| CARB_100 | 0.802 | 0.398 |
| CARB_101 | 1.996 | 0.687 |
| CARB_293 | 0.709 | 0.398 |
| CARB_294 | 0.866 | 0.398 |
| CARB_295 | 0.416 | - |
| CARB_296 | 1.017 | 0.398 |
| CARB_297 | 0.416 | 0.398 |

The per-stand calibration happens automatically when:
1. `DG_TRANS`, `DG_MEASURE`, `HTG_TRANS`, `HTG_MEASURE`, `MORT_MEASURE` are in `FVS_StandInit`
2. Growth increment data (`DG`, `HTG`) is in `FVS_TreeInit`
3. FVS is allowed to apply its **default** calibration algorithm (no `GROWTH` keyword override)

## Verification Results

Test run with Web GUI style keywords (Section 6 plots):

| Stand | BA 2123 (ft²/ac) |
|-------|------------------|
| CARB_99 | 168.4 |
| CARB_100 | 101.8 |
| CARB_101 | 177.6 |
| CARB_293 | 220.1 |
| CARB_294 | 162.3 |
| CARB_295 | 138.7 |
| CARB_296 | 168.3 |
| CARB_297 | 152.9 |
| **AVERAGE** | **161.25** |
| **TARGET** | **161.0** |

## Implementation Changes Required

### 1. `src/fvs_tools/keyword_builder.py`
- Remove: `STDINFO`, `SITECODE`, `DESIGN`, `GROWTH`, `NOTRIPLE`, `NOAUTOES`, `RANNSEED`, `CALIBSTAT`
- Add: `MgmtId`, `TimeInt`
- Keep: Database input blocks, `COMPUTE`, management keywords (MINHARV, THINQ)

### 2. `src/fvs_tools/config.py`
- Remove or make optional: `tripling`, `add_regen`, `random_seed`, `output_calibration`
- These should only be used for advanced/debugging scenarios

### 3. Database Input Format
- Change `TreeSQL` from `WHERE Stand_CN = '{stand_id}'` to `WHERE Stand_ID = '%StandID%'`
- The `%StandID%` placeholder is replaced by FVS at runtime

## Debugging Commands Used

```bash
# Compare database schemas
uv run python -c "import sqlite3; ..."

# Compare TreeInit data between Web GUI and our generation
# (Found: IDENTICAL data - problem was keywords, not data)

# Test minimal keywords
cat > test.key << 'EOF'
StdIdent
CARB_99...
EOF
./FVSie < test.ctrl
```

## References

- Web GUI backup: `/workspaces/fors591/data/webguibackup/`
- Web GUI keyword file: `1a6650cc-a19e-4387-a314-0cfeb90d06ac.key`
- Our test output: `/workspaces/fors591/outputs/test_webgui_style/`
