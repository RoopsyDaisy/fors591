"""
Create FVS input database from CSV data files.

Converts from TREELIST format to DSNin database format for FVS simulation.
"""

import sqlite3
from pathlib import Path

import pandas as pd


def create_fvs_input_db(
    stands: pd.DataFrame,
    trees: pd.DataFrame,
    output_db: Path | str,
) -> None:
    """
    Create FVS_Data.db with FVS_StandInit and FVS_TreeInit tables.

    Args:
        stands: DataFrame with stand-level attributes from FVS_StandInit CSV
        trees: DataFrame with tree records from FVS_TreeInit CSV
        output_db: Path to output database file

    Note:
        Stand_CN is used as the primary key and foreign key, matching Stand_ID.
        This allows FVS to reference stands using the StandCN keyword.
    """
    output_db = Path(output_db)

    # Remove existing database if present
    if output_db.exists():
        output_db.unlink()

    conn = sqlite3.connect(output_db)
    cursor = conn.cursor()

    # Create FVS_StandInit table with exact FVS schema
    stand_schema = """
        CREATE TABLE FVS_StandInit (
            Stand_CN TEXT PRIMARY KEY,
            Stand_ID TEXT,
            Variant TEXT,
            Inv_Year INTEGER,
            Groups TEXT,
            AddFiles TEXT,
            FVSKeywords TEXT,
            Latitude REAL,
            Longitude REAL,
            Region INTEGER,
            Forest INTEGER,
            District INTEGER,
            Compartment INTEGER,
            Location INTEGER,
            Ecoregion TEXT,
            PV_Code TEXT,
            PV_Ref_Code TEXT,
            Age INTEGER,
            Aspect REAL,
            Slope REAL,
            Elevation REAL,
            ElevFt REAL,
            Basal_Area_Factor REAL,
            Inv_Plot_Size REAL,
            Brk_DBH REAL,
            Num_Plots INTEGER,
            NonStk_Plots INTEGER,
            Sam_Wt REAL,
            Stk_Pcnt REAL,
            DG_Trans INTEGER,
            DG_Measure INTEGER,
            HTG_Trans INTEGER,
            HTG_Measure INTEGER,
            Mort_Trans INTEGER,
            Mort_Measure INTEGER,
            BA_Max REAL,
            SDI_Max REAL,
            Site_Species TEXT,
            Site_Index REAL,
            Model_Type INTEGER,
            Physio_Region INTEGER,
            Forest_Type INTEGER,
            State INTEGER,
            County INTEGER,
            Fuel_Model TEXT,
            Fuel_0_25_H REAL,
            Fuel_25_1_H REAL,
            Fuel_1_3_H REAL,
            Fuel_3_6_H REAL,
            Fuel_6_12_H REAL,
            Fuel_12_20_H REAL,
            Fuel_20_35_H REAL,
            Fuel_35_50_H REAL,
            Fuel_gt_50_H REAL,
            Fuel_0_25_S REAL,
            Fuel_25_1_S REAL,
            Fuel_1_3_S REAL,
            Fuel_3_6_S REAL,
            Fuel_6_12_S REAL,
            Fuel_12_20_S REAL,
            Fuel_20_35_S REAL,
            Fuel_35_50_S REAL,
            Fuel_gt_50_S REAL,
            Fuel_Litter REAL,
            Fuel_Duff REAL,
            Photo_Ref INTEGER,
            Photo_Code TEXT
        )
    """
    cursor.execute(stand_schema)

    # Create FVS_TreeInit table with exact FVS schema
    tree_schema = """
        CREATE TABLE FVS_TreeInit (
            Stand_CN TEXT,
            StandPlot_CN TEXT,
            Tree_CN TEXT PRIMARY KEY,
            Tree_ID INTEGER,
            Tree_Count REAL,
            History INTEGER,
            Species TEXT,
            DBH REAL,
            DG REAL,
            Ht REAL,
            HtTopK REAL,
            HtG REAL,
            CrRatio INTEGER,
            Damage1 INTEGER,
            Severity1 INTEGER,
            Damage2 INTEGER,
            Severity2 INTEGER,
            Damage3 INTEGER,
            Severity3 INTEGER,
            TreeValue INTEGER,
            Prescription INTEGER,
            Age INTEGER,
            Plot_ID INTEGER,
            Tree_Status INTEGER,
            TopoCode INTEGER,
            SitePrep INTEGER,
            FOREIGN KEY (Stand_CN) REFERENCES FVS_StandInit(Stand_CN)
        )
    """
    cursor.execute(tree_schema)

    # Transform and insert stand data
    stand_records = []
    for _, stand in stands.iterrows():
        stand_id = str(stand["STAND_ID"])

        # Map CSV columns to FVS_StandInit schema
        record = {
            "Stand_CN": stand_id,  # Use Stand_ID as Stand_CN
            "Stand_ID": stand_id,
            "Variant": str(stand.get("VARIANT", "IE")),
            "Inv_Year": (
                int(stand["INV_YEAR"]) if pd.notna(stand.get("INV_YEAR")) else None
            ),
            "Groups": (
                str(stand.get("GROUPS", "")) if pd.notna(stand.get("GROUPS")) else None
            ),
            "AddFiles": (
                str(stand.get("ADDFILES", ""))
                if pd.notna(stand.get("ADDFILES"))
                else None
            ),
            "FVSKeywords": (
                str(stand.get("FVSKEYWORDS", ""))
                if pd.notna(stand.get("FVSKEYWORDS"))
                else None
            ),
            "Latitude": (
                float(stand["LATITUDE"]) if pd.notna(stand.get("LATITUDE")) else None
            ),
            "Longitude": (
                float(stand["LONGITUDE"]) if pd.notna(stand.get("LONGITUDE")) else None
            ),
            "Region": int(stand["REGION"]) if pd.notna(stand.get("REGION")) else None,
            "Forest": int(stand["FOREST"]) if pd.notna(stand.get("FOREST")) else None,
            "District": (
                int(stand["DISTRICT"]) if pd.notna(stand.get("DISTRICT")) else None
            ),
            "Compartment": (
                int(stand["COMPARTMENT"])
                if pd.notna(stand.get("COMPARTMENT"))
                else None
            ),
            "Location": (
                int(stand["LOCATION"]) if pd.notna(stand.get("LOCATION")) else None
            ),
            "Ecoregion": (
                str(stand.get("ECOREGION", ""))
                if pd.notna(stand.get("ECOREGION"))
                else None
            ),
            "PV_Code": (
                str(int(stand["PV_CODE"])) if pd.notna(stand.get("PV_CODE")) else None
            ),
            "PV_Ref_Code": (
                str(stand.get("PV_REF_CODE", ""))
                if pd.notna(stand.get("PV_REF_CODE"))
                else None
            ),
            "Age": int(stand["AGE"]) if pd.notna(stand.get("AGE")) else None,
            "Aspect": float(stand["ASPECT"]) if pd.notna(stand.get("ASPECT")) else None,
            "Slope": float(stand["SLOPE"]) if pd.notna(stand.get("SLOPE")) else None,
            "Elevation": (
                float(stand["ELEVATION"]) if pd.notna(stand.get("ELEVATION")) else None
            ),
            "ElevFt": float(stand["ELEVFT"]) if pd.notna(stand.get("ELEVFT")) else None,
            "Basal_Area_Factor": (
                float(stand["BASAL_AREA_FACTOR"])
                if pd.notna(stand.get("BASAL_AREA_FACTOR"))
                else None
            ),
            "Inv_Plot_Size": (
                float(stand["INV_PLOT_SIZE"])
                if pd.notna(stand.get("INV_PLOT_SIZE"))
                else None
            ),
            "Brk_DBH": (
                float(stand["BRK_DBH"]) if pd.notna(stand.get("BRK_DBH")) else None
            ),
            "Num_Plots": (
                int(stand["NUM_PLOTS"]) if pd.notna(stand.get("NUM_PLOTS")) else None
            ),
            "NonStk_Plots": (
                int(stand["NONSTK_PLOTS"])
                if pd.notna(stand.get("NONSTK_PLOTS"))
                else None
            ),
            "Sam_Wt": float(stand["SAM_WT"]) if pd.notna(stand.get("SAM_WT")) else None,
            "Stk_Pcnt": (
                float(stand["STK_PCNT"]) if pd.notna(stand.get("STK_PCNT")) else None
            ),
            "DG_Trans": (
                int(stand["DG_TRANS"]) if pd.notna(stand.get("DG_TRANS")) else None
            ),
            "DG_Measure": (
                int(stand["DG_MEASURE"]) if pd.notna(stand.get("DG_MEASURE")) else None
            ),
            "HTG_Trans": (
                int(stand["HTG_TRANS"]) if pd.notna(stand.get("HTG_TRANS")) else None
            ),
            "HTG_Measure": (
                int(stand["HTG_MEASURE"])
                if pd.notna(stand.get("HTG_MEASURE"))
                else None
            ),
            "Mort_Trans": None,  # Not in CSV
            "Mort_Measure": (
                int(stand["MORT_MEASURE"])
                if pd.notna(stand.get("MORT_MEASURE"))
                else None
            ),
            "BA_Max": float(stand["MAX_BA"]) if pd.notna(stand.get("MAX_BA")) else None,
            "SDI_Max": (
                float(stand["MAX_SDI"]) if pd.notna(stand.get("MAX_SDI")) else None
            ),
            "Site_Species": (
                str(int(stand["SITE_SPECIES"]))
                if pd.notna(stand.get("SITE_SPECIES"))
                else None
            ),
            "Site_Index": (
                float(stand["SITE_INDEX"])
                if pd.notna(stand.get("SITE_INDEX"))
                else None
            ),
            "Model_Type": (
                int(stand["MODEL_TYPE"]) if pd.notna(stand.get("MODEL_TYPE")) else None
            ),
            "Physio_Region": (
                int(stand["PHYSIO_REGION"])
                if pd.notna(stand.get("PHYSIO_REGION"))
                else None
            ),
            "Forest_Type": (
                int(stand["FOREST_TYPE"])
                if pd.notna(stand.get("FOREST_TYPE"))
                else None
            ),
            "State": int(stand["STATE"]) if pd.notna(stand.get("STATE")) else None,
            "County": int(stand["COUNTY"]) if pd.notna(stand.get("COUNTY")) else None,
            "Fuel_Model": (
                str(stand.get("FUEL_MODEL", ""))
                if pd.notna(stand.get("FUEL_MODEL"))
                else None
            ),
            "Fuel_0_25_H": (
                float(stand["FUEL_0_25"]) if pd.notna(stand.get("FUEL_0_25")) else None
            ),
            "Fuel_25_1_H": (
                float(stand["FUEL_25_1"]) if pd.notna(stand.get("FUEL_25_1")) else None
            ),
            "Fuel_1_3_H": (
                float(stand["FUEL_1_3"]) if pd.notna(stand.get("FUEL_1_3")) else None
            ),
            "Fuel_3_6_H": (
                float(stand["FUEL_3_6_H"])
                if pd.notna(stand.get("FUEL_3_6_H"))
                else None
            ),
            "Fuel_6_12_H": (
                float(stand["FUEL_6_12_H"])
                if pd.notna(stand.get("FUEL_6_12_H"))
                else None
            ),
            "Fuel_12_20_H": (
                float(stand["FUEL_12_20_H"])
                if pd.notna(stand.get("FUEL_12_20_H"))
                else None
            ),
            "Fuel_20_35_H": (
                float(stand["FUEL_20_35_H"])
                if pd.notna(stand.get("FUEL_20_35_H"))
                else None
            ),
            "Fuel_35_50_H": (
                float(stand["FUEL_35_50_H"])
                if pd.notna(stand.get("FUEL_35_50_H"))
                else None
            ),
            "Fuel_gt_50_H": (
                float(stand["FUEL_GT_50_H"])
                if pd.notna(stand.get("FUEL_GT_50_H"))
                else None
            ),
            "Fuel_0_25_S": None,  # Not in CSV
            "Fuel_25_1_S": None,  # Not in CSV
            "Fuel_1_3_S": None,  # Not in CSV
            "Fuel_3_6_S": (
                float(stand["FUEL_3_6_S"])
                if pd.notna(stand.get("FUEL_3_6_S"))
                else None
            ),
            "Fuel_6_12_S": (
                float(stand["FUEL_6_12_S"])
                if pd.notna(stand.get("FUEL_6_12_S"))
                else None
            ),
            "Fuel_12_20_S": (
                float(stand["FUEL_12_20_S"])
                if pd.notna(stand.get("FUEL_12_20_S"))
                else None
            ),
            "Fuel_20_35_S": (
                float(stand["FUEL_20_35_S"])
                if pd.notna(stand.get("FUEL_20_35_S"))
                else None
            ),
            "Fuel_35_50_S": (
                float(stand["FUEL_35_50_S"])
                if pd.notna(stand.get("FUEL_35_50_S"))
                else None
            ),
            "Fuel_gt_50_S": (
                float(stand["FUEL_GT_50_S"])
                if pd.notna(stand.get("FUEL_GT_50_S"))
                else None
            ),
            "Fuel_Litter": (
                float(stand["FUEL_LITTER"])
                if pd.notna(stand.get("FUEL_LITTER"))
                else None
            ),
            "Fuel_Duff": (
                float(stand["FUEL_DUFF"]) if pd.notna(stand.get("FUEL_DUFF")) else None
            ),
            "Photo_Ref": (
                int(stand["PHOTO_REF"]) if pd.notna(stand.get("PHOTO_REF")) else None
            ),
            "Photo_Code": (
                str(stand.get("PHOTO_CODE", ""))
                if pd.notna(stand.get("PHOTO_CODE"))
                else None
            ),
        }

        stand_records.append(record)

    # Insert stand records
    if stand_records:
        columns = list(stand_records[0].keys())
        placeholders = ",".join(["?" for _ in columns])
        sql = f"INSERT INTO FVS_StandInit ({','.join(columns)}) VALUES ({placeholders})"

        for record in stand_records:
            cursor.execute(sql, [record[col] for col in columns])

    # Transform and insert tree data
    tree_records = []
    for idx, (_, tree) in enumerate(trees.iterrows(), start=1):
        stand_id = str(tree["STAND_ID"])

        # Create unique tree identifier
        tree_cn = f"{stand_id}_T{idx}"

        # Map CSV columns to FVS_TreeInit schema
        record = {
            "Stand_CN": stand_id,  # Foreign key to FVS_StandInit
            "StandPlot_CN": f"{stand_id}_P{tree.get('PLOT_ID', 1)}",
            "Tree_CN": tree_cn,
            "Tree_ID": (
                int(tree.get("TREE_ID", idx)) if pd.notna(tree.get("TREE_ID")) else idx
            ),
            "Tree_Count": (
                float(tree["TREE_COUNT"]) if pd.notna(tree.get("TREE_COUNT")) else 1.0
            ),
            "History": (
                int(tree.get("HISTORY", 1)) if pd.notna(tree.get("HISTORY")) else 1
            ),
            "Species": str(int(tree["SPECIES"])),  # Convert to string (3-digit code)
            "DBH": float(tree["DIAMETER"]) if pd.notna(tree.get("DIAMETER")) else None,
            "DG": float(tree["DG"]) if pd.notna(tree.get("DG")) else None,
            "Ht": float(tree["HT"]) if pd.notna(tree.get("HT")) else None,
            "HtTopK": float(tree["HTTOPK"]) if pd.notna(tree.get("HTTOPK")) else None,
            "HtG": float(tree["HTG"]) if pd.notna(tree.get("HTG")) else None,
            "CrRatio": int(tree["CRRATIO"]) if pd.notna(tree.get("CRRATIO")) else None,
            "Damage1": int(tree["DAMAGE1"]) if pd.notna(tree.get("DAMAGE1")) else None,
            "Severity1": (
                int(tree["SEVERITY1"]) if pd.notna(tree.get("SEVERITY1")) else None
            ),
            "Damage2": int(tree["DAMAGE2"]) if pd.notna(tree.get("DAMAGE2")) else None,
            "Severity2": (
                int(tree["SEVERITY2"]) if pd.notna(tree.get("SEVERITY2")) else None
            ),
            "Damage3": int(tree["DAMAGE3"]) if pd.notna(tree.get("DAMAGE3")) else None,
            "Severity3": (
                int(tree["SEVERITY3"]) if pd.notna(tree.get("SEVERITY3")) else None
            ),
            "TreeValue": (
                int(tree["TREEVALUE"]) if pd.notna(tree.get("TREEVALUE")) else None
            ),
            "Prescription": (
                int(tree["PRESCRIPTION"])
                if pd.notna(tree.get("PRESCRIPTION"))
                else None
            ),
            "Age": int(tree["AGE"]) if pd.notna(tree.get("AGE")) else None,
            "Plot_ID": (
                int(tree.get("PLOT_ID", 1)) if pd.notna(tree.get("PLOT_ID")) else 1
            ),
            "Tree_Status": None,  # Not in CSV
            "TopoCode": (
                int(tree["TOPOCODE"]) if pd.notna(tree.get("TOPOCODE")) else None
            ),
            "SitePrep": (
                int(tree["SITEPREP"]) if pd.notna(tree.get("SITEPREP")) else None
            ),
        }

        tree_records.append(record)

    # Insert tree records
    if tree_records:
        columns = list(tree_records[0].keys())
        placeholders = ",".join(["?" for _ in columns])
        sql = f"INSERT INTO FVS_TreeInit ({','.join(columns)}) VALUES ({placeholders})"

        for record in tree_records:
            cursor.execute(sql, [record[col] for col in columns])

    conn.commit()
    conn.close()

    print(f"Created FVS input database: {output_db}")
    print(f"  - {len(stand_records)} stands in FVS_StandInit")
    print(f"  - {len(tree_records)} trees in FVS_TreeInit")


def verify_fvs_input_db(db_path: Path | str) -> dict:
    """
    Verify FVS input database contents.

    Args:
        db_path: Path to FVS_Data.db

    Returns:
        Dictionary with verification results:
            - stand_count: Number of stands
            - tree_count: Number of trees
            - stand_ids: List of stand IDs
            - trees_by_stand: Dictionary of tree counts by stand
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)

    # Get stand count and IDs
    stands_df = pd.read_sql("SELECT Stand_CN, Stand_ID FROM FVS_StandInit", conn)
    stand_count = len(stands_df)
    stand_ids = stands_df["Stand_ID"].tolist()

    # Get tree count
    tree_count_query = "SELECT COUNT(*) as count FROM FVS_TreeInit"
    tree_count = pd.read_sql(tree_count_query, conn).iloc[0]["count"]

    # Get trees by stand
    trees_by_stand_query = """
        SELECT Stand_CN, COUNT(*) as tree_count 
        FROM FVS_TreeInit 
        GROUP BY Stand_CN
    """
    trees_by_stand_df = pd.read_sql(trees_by_stand_query, conn)
    trees_by_stand = dict(
        zip(trees_by_stand_df["Stand_CN"], trees_by_stand_df["tree_count"], strict=True)
    )

    conn.close()

    return {
        "stand_count": stand_count,
        "tree_count": tree_count,
        "stand_ids": stand_ids,
        "trees_by_stand": trees_by_stand,
    }
