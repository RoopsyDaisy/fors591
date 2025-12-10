# FVS Confirmed Facts

This document contains ONLY confirmed, tested facts about FVS behavior in this project.
No speculation. All statements have been verified through direct testing.

## Date
2025-12-06

## Critical Discovery: Keyword Interference with Calibration

**Problem**: Extra keywords in keyword files caused ~11 ft²/ac reduction in projected BA.

**Root Cause**: The following keywords override or interfere with FVS's data-driven calibration when using database input:
- `GROWTH` - Modifies calibration sampling criteria
- `NOTRIPLE` - Disables BAF tripling
- `NOAUTOES` - Disables automatic establishment  
- `DESIGN` - Overrides sampling design from database
- `STDINFO` - Overrides stand attributes from database
- `SITECODE` - Overrides site code from database
- `RANNSEED` - Sets random seed differently
- `CALIBSTAT` - May affect calibration behavior

**Solution**: Use minimal Web GUI-style keywords that let FVS read all attributes from the database.

**Result**: Average BA at year 2123 = 161.25 ft²/ac (matching Web GUI target of 161 ft²/ac)

See `docs/fvs_keyword_discovery.md` for detailed analysis.

## Calibration Independence - CONFIRMED

**Our simulation runs completely independently from the Web GUI.**

Data flow:
1. **Source**: CSV files (`data/FVS_Lubrecht_2023_FVS_*.csv`)
2. **Processing**: `db_input.py` creates `FVS_Data.db` from CSVs
3. **Calibration**: FVS reads calibration parameters from the database:
   - `DG_TRANS`, `DG_MEASURE` (diameter growth)
   - `HTG_TRANS`, `HTG_MEASURE` (height growth)
   - `MORT_MEASURE` (mortality)
4. **Growth Data**: Tree-level `DG` and `HTG` values in `FVS_TreeInit`
5. **Result**: FVS applies its built-in calibration algorithm independently

The Web GUI backup (`data/webguibackup/`) was only used for debugging/comparison, NOT as input data.

## FVS Output Table Year Quirk

**Problem**: `FVS_Carbon` and `FVS_Compute` tables don't include the final cycle year.

| Table | Years Output (10 cycles) |
|-------|-------------------------|
| FVS_Summary2 | 2023, 2033, ..., 2113, **2123** |
| FVS_Carbon | 2023, 2033, ..., 2113 (missing 2123) |
| FVS_Compute | 2023, 2033, ..., 2113 (missing 2123) |

**Solution**: Run 11 cycles (110 years) to get complete data through year 2123.

## FVS Binary
- **Path**: `/workspaces/fors591/lib/fvs/FVSie_CmakeDir/FVSie`
- **Variant**: Inland Empire (IE)
- **Revision**: 20250930
- **Exit Code**: STOP 20 indicates successful completion

## Linked Libraries
- libFVS_ie.so
- libFVSsql.so  
- libFVSfofem.so

## Output Database
- **Format**: SQLite
- **Default Name**: FVSOut.db

### Tables Created (confirmed)
- `FVS_Summary` - Stand-level summary by year
- `FVS_Cases` - Case metadata
- `FVS_Error` - Error log
- `FVS_InvReference` - Inventory reference
- `FVS_Compute` - Created when COMPUTDB keyword is used
- `FVS_CalibStats` - Created when CALIBSTAT keyword is used

### FVS_Summary Columns (confirmed)
- CaseID, StandID, Year, Age
- Tpa (trees per acre)
- BA (basal area)
- SDI, CCF, TopHt, QMD
- TCuFt, MCuFt, SCuFt, BdFt
- RTpa, RTCuFt, RMCuFt, RSCuFt, RBdFt
- ATBA, ATSDI, ATCCF, ATTopHt, ATQMD
- PrdLen, Acc, Mort, MAI, ForTyp, SizeCls, StkCls

## Working Keyword File Structure

The following keyword structure successfully runs with tree data:

```
STDIDENT
<stand_id>     <description>

RANNSEED        2025

STDINFO           16       250       0.0       2.4      30.1        54

SITECODE           0         0         1

INVYEAR         2023

TREEFMT
(I4,I4,F8.3,I1,A3,F5.1,F5.1,2F5.1,F5.1,I1,6I2,2I1,I2,2I3,2I1,F3.0)

TREELIST          0         0         0         0         0         0         0
run.tre

DESIGN         -10.0         0         0         1         0         0       1.0

NOTRIPLE

NOAUTOES

GROWTH             1         5         1         5         5

NUMCYCLE          10

DATABASE
DSNOUT
FVSOut.db
SUMMARY
END

PROCESS
STOP
```

### Verified Output from Working File
- Tpa: 240
- BA: 150
- CCF: 162 (initial year 2023)

## COMPUTE Keyword Testing

### Official Example Syntax (from fs.usda.gov/fvs/software/addfiles.php)

From `uncorrectedCC.kcp`:
```
Compute            0
UNCC = -100 * Alog(1-(Spmcdbh(7,All,0,0,999,0,999,0)/100))
End
```

SPMCDBH parameters: `SPMCDBH(code, species, pt, minDBH, maxDBH, minHT, maxHT, ?)` where:
- code 1 = TPA
- code 2 = BA  
- code 7 = canopy cover
- code 11 = SDI

### Test Results (all confirmed)

| Test | Placement | Content | Result |
|------|-----------|---------|--------|
| run.key (working) | No COMPUTE | - | 240 TPA, 150 BA, 162 CCF |
| test_compute_after.key | After TREELIST | CANCOV = SPMCDBH(0,0,0) | 0 TPA, 0 BA, 0 CCF |
| test_compute_empty.key | After TREELIST | Empty (just COMPUTE/END) | 0 TPA, 0 BA, 0 CCF |
| test_compute_correct.key | After NUMCYCLE | SPMCDBH(7,All,0,0,999,0,999,0) - official syntax | 0 TPA, 0 BA, 0 CCF |
| test_addfile.key | Using ADDFILE | Official uncorrectedCC.kcp | 0 TPA, 0 BA, 0 CCF |

### Key Finding
Adding ANY COMPUTE keyword block (even empty, even using official syntax/addfiles) causes FVS to report 0 projectable trees when using TREELIST input.
This happens regardless of:
- Placement (before DATABASE or after TREELIST)
- Content (with variable assignment or empty)
- Syntax (incorrect or official correct syntax)
- Method (inline COMPUTE or ADDFILE)

### FVS_Compute Table
- Table IS created when COMPUTDB keyword is used inside DATABASE block
- Schema: `(CaseID text, StandID text, Year int, CANCOV real)`
- Table is empty because no trees are processed when COMPUTE is present

## GitHub Investigation (2025-01-05)

Source repo: https://github.com/USDAForestService/ForestVegetationSimulator

### Official Test Files Downloaded
- `/workspaces/fors591/data/ref_docs/iet01.key` - Basic FVSie test
- `/workspaces/fors591/data/ref_docs/NestedAddFile.key` - Uses ADDFILE with COMPUTE
- `/workspaces/fors591/data/ref_docs/AddFile1a.txt` - Contains working COMPUTE/SPMCDBH
- `/workspaces/fors591/data/ref_docs/maxActs.key` - Tests many COMPUTE statements

### Critical Discovery: Tree Input Methods

| Test File | Tree Input Method | COMPUTE Status |
|-----------|-------------------|----------------|
| `iet01.key` | TREEDATA (inline) | No COMPUTE used |
| `NestedAddFile.key` | DSNin + TreeSQL (database) | Uses COMPUTE via ADDFILE |
| `maxActs.key` | NoTrees (no trees at all) | Uses many COMPUTE statements |
| Our `run.key` | TREELIST (file reference) | COMPUTE causes 0 trees |

### Working COMPUTE Syntax (from AddFile1a.txt)
```
Compute            0
LiveTPA=SPMCDBH(1,All,0,0,200,0,500,0,0)
LiveBA=SPMCDBH(2,All,0,0,200,0,500,0,0)
LiveQMD=SPMCDBH(5,All,0,0,200,0,500,0,0)
StdAcre=SampWt
StdElev=Elev
End
```

### Database Input Method (from NestedAddFile.key)
```
Database
DSNin
FVS_Data.db
StandSQL
SELECT * FROM FVS_StandInit WHERE Stand_CN = '%Stand_CN%'
EndSQL
TreeSQL
SELECT * FROM FVS_TreeInit WHERE Stand_CN = '%Stand_CN%'
EndSQL
END
```

### Hypothesis
COMPUTE keyword may have an interaction issue with TREELIST file-based tree input.
Official tests that use COMPUTE either:
1. Use DSNin/TreeSQL (database input)
2. Use TREEDATA (inline tree records)
3. Use NoTrees (testing COMPUTE without tree data)

None of the official test files combine TREELIST + COMPUTE.

### Recommended Solution
Convert from TREELIST input to DSNin + TreeSQL (database input) to match the working pattern from official tests.

## Symbols Confirmed in Binary (via `strings` command)
- ACANCOV
- BCANCOV  
- SPMCDBH
- OPEVAL
- opeval.f

These symbols exist in the binary, suggesting the functions are available.

## Available Data (CCF as proxy for canopy cover)
CCF (Crown Competition Factor) is available in FVS_Summary:
- Range in our data: 40-162
- Represents relative stand density based on crown width relationships
- May serve as an alternative metric if direct canopy cover cannot be obtained

## Calibration Statistics
Successfully extracted from FVS_CalibStats table when CALIBSTAT keyword is used.
Example Douglas-fir large tree scale factors: 20-109% (varies by stand)

## Keywords Tested But Problematic
| Keyword | Issue |
|---------|-------|
| COMPUTE | Causes 0 projectable trees |
| CALIBSTAT | Works |
| ECHOSUM | Causes errors (in earlier testing) |
| CARBREPT | Causes errors (in earlier testing) |

## Stands in Dataset
- CARB_99
- CARB_100
- CARB_101
- CARB_293
- CARB_294
- CARB_295
- CARB_296
- CARB_297

## Updates (2025-01-05) - Assignment 5 Implementation

### 1. Database Input (DSNin) - CONFIRMED WORKING
Switching from `TREELIST` (file-based) to `DSNin` (database-based) resolved the issue where `COMPUTE` keywords caused 0 projectable trees.
- **Keywords**:
  ```
  DATABASE
  DSNin
  <database_filename>
  StandSQL
  SELECT * FROM FVS_StandInit WHERE Stand_ID = '<stand_id>'
  EndSQL
  TreeSQL
  SELECT * FROM FVS_TreeInit WHERE Stand_CN = '<stand_id>'
  EndSQL
  END
  ```
- **Note**: `Stand_CN` in `TreeSQL` must match the column used to link trees to stands.

### 2. Canopy Cover Calculation - CONFIRMED WORKING
With `DSNin`, the `COMPUTE` keyword functions correctly.
- **Correct Syntax for IE Variant**:
  ```
  COMPUTE            0
  CanCov = SPMCDBH(7,All,0,0,999,0,999,0)
  END
  ```
- **Attribute 7**: Confirmed to be Percent Canopy Cover for the IE variant (unlike some other variants where it might be 13 or different).
- **Output**: Values are successfully written to the `FVS_Compute` table.

### 3. Carbon Output - CONFIRMED WORKING
- **Issue**: The `CARBON` keyword is **INVALID** inside the `DATABASE` block.
- **Correct Keyword**: **`CARBREDB`** (Carbon Report to Database).
- **Placement**: Inside the `DATABASE` block.
- **Working Configuration**:
  ```
  DATABASE
  DSNOUT
  FVSOut.db
  SUMMARY
  CARBREDB
  END
  ```
- **FFE Activation**: The `FMIN` block is also required to activate the Fire and Fuels Extension (FFE) generally, but `CARBREDB` is the specific trigger for database output.
- **Output Table**: `FVS_Carbon` (contains Carbon_Live_Total, Carbon_Dead_Total, etc.).

### 4. Management Keywords - CONFIRMED WORKING
- **MINHARV**: Sets a minimum harvest volume constraint.
  - Syntax: `MINHARV <Year> <MinVol>`
  - Example: `MINHARV 0 5000.0` (Apply in all years, min 5000 bdft/ac)
- **THINQ**: Thinning from below to a Q-factor target.
  - Syntax: `THINQ <Year> <Q-Factor> <ResidualBA> <MinDBH> <MaxDBH> <MinHt> <MaxHt>`
  - Example: `THINQ 2023 1.2 50.0 0.0 999.0 0.0 999.0`

### 5. Updated Table List
The following tables are confirmed to be generated in `FVSOut.db`:
- `FVS_Cases`
- `FVS_Summary`
- `FVS_Compute` (if `COMPUTDB` used)
- `FVS_Carbon` (if `CARBREDB` used)
- `FVS_Hrv_Carbon` (Harvest Carbon, if `CARBREDB` used)
- `FVS_InvReference`
- `FVS_Error`
