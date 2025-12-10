"""
FVS keyword file builder.

Generates FVS keyword files matching the Web GUI's minimal keyword structure.
This ensures accurate calibration by letting FVS use database-provided stand
attributes and default calibration behavior.

Key principle: When using database input (DSNin), FVS reads stand attributes
(aspect, slope, elevation, site index, calibration parameters) directly from
FVS_StandInit and FVS_TreeInit tables. Extra keywords like STDINFO, SITECODE,
DESIGN, and GROWTH override or interfere with this data-driven calibration.

See docs/fvs_keyword_discovery.md for detailed analysis.
"""

from pathlib import Path

import pandas as pd

from .config import FVSSimulationConfig


def build_keyword_file(
    stand: pd.Series,
    tree_filename: str,
    config: FVSSimulationConfig,
    filepath: Path | str,
    use_database: bool = False,
) -> None:
    """
    Generate FVS keyword file with specified configuration.

    Uses the minimal keyword structure matching the FVS Web GUI, which allows
    FVS to read all stand/tree attributes from the database and apply proper
    data-driven calibration.

    Args:
        stand: Series containing stand-level attributes
        tree_filename: Name of tree list file (relative to keyword file) or database name
        config: Simulation configuration
        filepath: Output path for keyword file
        use_database: If True, use DSNin database input instead of TREELIST
    """
    filepath = Path(filepath)

    # Normalize stand keys to uppercase to handle DB vs CSV input differences
    stand = stand.copy()
    stand.index = stand.index.str.upper()

    # Extract stand attributes
    stand_id = str(stand["STAND_ID"])
    inv_year = int(stand["INV_YEAR"])

    # Start building keyword file
    keywords = []

    if use_database:
        # === WEB GUI MINIMAL STYLE (for database input) ===
        # This matches the FVS Web GUI structure which produces correct calibration

        # Stand identification (Web GUI format: 26-char stand ID field)
        keywords.append("StdIdent")
        keywords.append(f"{stand_id:26s}{config.name}")

        # StandCN - required for multi-stand runs
        keywords.append("StandCN")
        keywords.append(stand_id)

        # Management ID (optional, matches Web GUI)
        keywords.append("MgmtId")
        keywords.append("A002")

        # Inventory year
        keywords.append(f"InvYear       {inv_year}")

        # Time interval and number of cycles
        # Use internal_num_cycles (+1) to ensure carbon/compute output for final year
        keywords.append(f"TimeInt                 {config.cycle_length} ")
        keywords.append(f"NumCycle     {config.internal_num_cycles} ")
        keywords.append("")

        # Database output block
        keywords.append("DataBase")
        keywords.append("DSNOut")
        keywords.append("FVSOut.db")

        # Summary with append mode (2 = append to existing table)
        keywords.append("Summary        2")

        # Compute variables output
        if config.compute_canopy_cover:
            keywords.append("Computdb          0         1")

        keywords.append("End")
        keywords.append("")

        # Tree Lists and Cut Lists output (Web GUI style)
        keywords.append("Treelist       0                   0")
        keywords.append("Cutlist        0                   0")
        keywords.append("Atrtlist       0                   0")
        keywords.append("Database")
        keywords.append("TreeLiDB       2")
        keywords.append("CutLiDB        2")
        keywords.append("Atrtlidb       2")
        keywords.append("End")
        keywords.append("")

        # Carbon and Fuels output (Web GUI style)
        if config.output_carbon:
            keywords.append("FMIn")
            keywords.append("CarbRept        2")
            keywords.append("CarbCut")
            keywords.append("CarbCalc")
            keywords.append("FuelOut         0")
            keywords.append("FuelRept")
            keywords.append("End")
            keywords.append("Database")
            keywords.append("CarbReDB        2")
            keywords.append("FuelReDB        2")
            keywords.append("FuelsOut        2")
            keywords.append("End")
            keywords.append("")

        # Calibration Statistics output
        keywords.append("Database")
        keywords.append("CalbStDB")
        keywords.append("End")
        keywords.append("")

        # Inventory Statistics output
        keywords.append("Stats")
        keywords.append("Database")
        keywords.append("InvStats")
        keywords.append("End")
        keywords.append("")

        # Delete old output tables (Web GUI style)
        keywords.append("DelOTab            1")
        keywords.append("DelOTab            2")
        keywords.append("DelOTab            4")
        keywords.append("")

        # Database input using DSNin with %StandID% placeholder
        # FVS replaces %StandID% at runtime with the current stand ID
        # Note: FVS_StandInit uses Stand_ID, FVS_TreeInit uses Stand_CN
        keywords.append("Database")
        keywords.append("DSNIn")
        keywords.append(tree_filename)  # Database filename (e.g., FVS_Data.db)
        keywords.append("StandSQL")
        keywords.append("SELECT * FROM FVS_StandInit")
        keywords.append("WHERE Stand_ID= '%StandID%'")
        keywords.append("EndSQL")
        keywords.append("TreeSQL")
        keywords.append("SELECT * FROM FVS_TreeInit")
        keywords.append("WHERE Stand_CN= '%StandID%'")
        keywords.append("EndSQL")
        keywords.append("END")
        keywords.append("")

        # Monte Carlo Keywords (Phase 3)
        # RanNSeed: Set FVS random seed for reproducibility
        if config.fvs_random_seed is not None:
            keywords.append("!Exten:base Title:Set FVS random seed")
            keywords.append(f"RanNSeed  {config.fvs_random_seed:10d}")
            keywords.append("")

        # NoCaLib: Disable growth calibration
        if not config.enable_calibration:
            keywords.append("!Exten:base Title:Disable growth calibration")
            keywords.append("NoCaLib")
            keywords.append("")

        # FixMort: Adjust mortality rates
        if config.mortality_multiplier is not None:
            keywords.append("!Exten:base Title:Adjust mortality rates")
            keywords.append(
                f"FixMort            0       All      {config.mortality_multiplier:4.2f}"
                "       0.0     999.0         3         0"
            )
            keywords.append("")

        # Compute canopy cover
        if config.compute_canopy_cover:
            keywords.append("Compute            0")
            # SPMCDBH(7, All, pt, minDBH, maxDBH, minHT, maxHT, flag)
            # Attribute 7 = Percent Canopy Cover
            keywords.append("Pc_can_cover=SPMCDBH(7,All,0,1,200,0,500,0,0)")
            keywords.append("End")
            keywords.append("")

        # Conditional Q-factor thinning with MINHARV (Web GUI style)
        if config.thin_q_factor is not None and config.thin_residual_ba is not None:
            cycle = config.cycle_length

            # MinHarv: Specify minimum acceptable harvest standards
            # Must be OUTSIDE the If block and applied at the start (inv_year)
            # Format matches Web GUI 'simpass5': MinHarv Year 0 0 0 0 Volume
            if config.min_harvest_volume is not None:
                keywords.append(
                    "!Exten:base Title:MinHarv: Specify minimum acceptable harvest standards"
                )
                keywords.append(
                    f"MinHarv         {inv_year}         0         0         0         0      {int(config.min_harvest_volume)}"
                )
                keywords.append("")

            # IF-THEN block for conditional thinning
            if config.thin_trigger_ba is not None:
                keywords.append("!Exten:base Title:Specified Basal Area is exceeded")
                keywords.append(f"If                {cycle}")
                keywords.append(f"bba gt    {int(config.thin_trigger_ba)}")
                keywords.append("Then")

            # ThinQFA with Parms() syntax (Web GUI style)
            # Use cycle 0 inside IF block to apply whenever condition is met
            thin_cycle = 0
            min_dbh = int(config.thin_min_dbh)
            max_dbh = int(config.thin_max_dbh)
            q_factor = int(config.thin_q_factor)
            class_width = 2  # 2" DBH classes per assignment
            residual = int(config.thin_residual_ba)

            keywords.append("!Exten:base Title:Thin to a Q-factor")
            keywords.append(
                "* Arguments: SmDBH, LgDBH, Species, Q-Factor, D-class, ResDensity, DensityUnits"
            )
            keywords.append(
                f"ThinQFA           {thin_cycle}     Parms({min_dbh},{max_dbh},All,{q_factor},{class_width},{residual},0)"
            )

            # ThinDBH to remove trees above max_dbh (Web GUI includes this)
            keywords.append("* Arguments: SmDBH, LgDBH, CutEff, Species, ResTPA, ResBA")
            keywords.append(
                f"ThinDBH           {thin_cycle}     Parms({max_dbh},999,1,All,0,0)"
            )

            # Close IF block
            if config.thin_trigger_ba is not None:
                keywords.append("EndIf")

            keywords.append("")

        # Standalone MINHARV (only if no thinning configured)
        elif config.min_harvest_volume is not None:
            keywords.append(
                "!Exten:base Title:MinHarv: Specify minimum acceptable harvest standards"
            )
            keywords.append(
                f"MinHarv         {inv_year}         0         0         0         0      {int(config.min_harvest_volume)}"
            )
            keywords.append("")

        # Stand/group labels (for reporting)
        keywords.append("SPLabel")
        keywords.append("  All_Stands, & ")
        keywords.append("  Section6")

        # Process and stop
        keywords.append("Process")
        keywords.append("STOP")
        keywords.append("")

    else:
        # === LEGACY FILE-BASED INPUT ===
        # This method may have issues with COMPUTE keyword but is kept for compatibility

        # Extract additional stand attributes needed for file-based input
        forest = int(stand["FOREST"])
        pv_code = str(int(stand["PV_CODE"]))
        aspect = float(stand["ASPECT"])
        slope = float(stand["SLOPE"])
        elevation_ft = float(stand["ELEVFT"])
        elevation_hundreds = elevation_ft / 100.0
        baf = float(stand["BASAL_AREA_FACTOR"])
        num_plots = int(stand["NUM_PLOTS"])

        # Calibration parameters
        dg_trans = int(stand["DG_TRANS"])
        dg_measure = int(stand["DG_MEASURE"])
        htg_trans = int(stand["HTG_TRANS"])
        htg_measure = int(stand["HTG_MEASURE"])
        mort_measure = int(stand["MORT_MEASURE"])

        # Optional columns
        age = float(stand["AGE"]) if pd.notna(stand.get("AGE")) else 0.0
        site_species_val = stand.get("SITE_SPECIES")
        site_species = str(int(site_species_val)) if pd.notna(site_species_val) else "0"
        site_index = (
            int(stand["SITE_INDEX"]) if pd.notna(stand.get("SITE_INDEX")) else 0
        )

        # Stand identification
        keywords.append("STDIDENT")
        keywords.append(f"{stand_id:<10s}  {config.name}")
        keywords.append("")

        # Stand info
        keywords.append(
            f"STDINFO   {forest:10d}{pv_code:>10s}"
            f"{age:10.1f}{aspect:10.1f}{slope:10.1f}{elevation_hundreds:10.0f}"
        )
        keywords.append("")

        # Site index
        keywords.append(f"SITECODE  {site_species:>10s}{site_index:10d}         1")
        keywords.append("")

        # Inventory year
        keywords.append(f"INVYEAR   {inv_year:10d}")
        keywords.append("")

        # Tree format
        keywords.append("TREEFMT")
        keywords.append(
            "(I4,I4,F8.3,I1,A3,F5.1,F5.1,2F5.1,F5.1,I1,6I2,2I1,I2,2I3,2I1,F3.0)"
        )
        keywords.append("")

        # Tree input file
        keywords.append(
            "TREELIST          0         0         0         0         0         0         0"
        )
        keywords.append(tree_filename)
        keywords.append("")

        # Sample design
        keywords.append(
            f"DESIGN    {baf:10.1f}         0         0{num_plots:10d}"
            "         0         0       1.0"
        )
        keywords.append("")

        # Calibration - using GROWTH keyword (legacy behavior)
        keywords.append(
            f"GROWTH    {dg_trans:10d}{dg_measure:10d}"
            f"{htg_trans:10d}{htg_measure:10d}{mort_measure:10d}"
        )
        keywords.append("")

        # Number of cycles
        # Use internal_num_cycles (+1) to ensure carbon/compute output for final year
        keywords.append(f"NUMCYCLE  {config.internal_num_cycles:10d}")
        keywords.append("")

        # Database output
        keywords.append("DATABASE")
        keywords.append("DSNOUT")
        keywords.append("FVSOut.db")
        keywords.append("SUMMARY")
        keywords.append("CalbStDB")  # Calibration statistics output
        if config.output_carbon:
            keywords.append("CARBREDB")
        if config.compute_canopy_cover:
            keywords.append("COMPUTDB")
        keywords.append("END")
        keywords.append("")

        # Enable Carbon/Fuels Extension if requested
        if config.output_carbon:
            keywords.append("FMIN")
            keywords.append("END")
            keywords.append("")

        # Process and stop
        keywords.append("PROCESS")
        keywords.append("STOP")
        keywords.append("")

    # Write to file
    filepath.write_text("\n".join(keywords))


def build_keyword_file_simple(
    stand: pd.Series,
    tree_filename: str,
    filepath: Path | str,
    num_years: int = 20,
    calibrate: bool = True,
    use_database: bool = False,
) -> None:
    """
    Simple wrapper for building basic keyword files.

    Args:
        stand: Stand attributes
        tree_filename: Tree list file name or database name
        filepath: Output keyword file path
        num_years: Projection years
        calibrate: Enable calibration (ignored - calibration is now data-driven)
        use_database: If True, use DSNin database input instead of TREELIST
    """
    config = FVSSimulationConfig(
        name="projection",
        num_years=num_years,
    )

    build_keyword_file(stand, tree_filename, config, filepath, use_database)


def build_batch_keyword_file(
    stands: list[pd.Series],
    db_filename: str,
    config: FVSSimulationConfig,
    filepath: Path | str,
) -> None:
    """
    Generate a batch FVS keyword file for multiple stands.

    This matches the Web GUI's approach of running all stands in a single
    FVS invocation with Process keywords between stands.

    Args:
        stands: List of Series containing stand-level attributes
        db_filename: Name of input database (e.g., FVS_Data.db)
        config: Simulation configuration
        filepath: Output path for keyword file
    """
    filepath = Path(filepath)

    all_keywords = []
    all_keywords.append(f"!!title: {config.name}")
    all_keywords.append(f"!!built: batch-run")
    all_keywords.append("")

    for stand in stands:
        # Normalize stand keys
        stand = stand.copy()
        stand.index = stand.index.str.upper()

        stand_id = str(stand["STAND_ID"])
        inv_year = int(stand["INV_YEAR"])

        # Stand identification
        all_keywords.append("StdIdent")
        all_keywords.append(f"{stand_id:26s}{config.name}")
        all_keywords.append("StandCN")
        all_keywords.append(stand_id)
        all_keywords.append("MgmtId")
        all_keywords.append("A002")
        all_keywords.append(f"InvYear       {inv_year}")
        # Use internal_num_cycles (+1) to ensure carbon/compute output for final year
        all_keywords.append(f"TimeInt                 {config.cycle_length} ")
        all_keywords.append(f"NumCycle     {config.internal_num_cycles} ")
        all_keywords.append("")

        # Database output
        all_keywords.append("DataBase")
        all_keywords.append("DSNOut")
        all_keywords.append("FVSOut.db")
        all_keywords.append("Summary        2")
        if config.compute_canopy_cover:
            all_keywords.append("Computdb          0         1")
        if config.output_carbon:
            all_keywords.append("CarbReDB        2")
        all_keywords.append("End")
        all_keywords.append("")

        # Database input
        all_keywords.append("Database")
        all_keywords.append("DSNIn")
        all_keywords.append(db_filename)
        all_keywords.append("StandSQL")
        all_keywords.append("SELECT * FROM FVS_StandInit")
        all_keywords.append("WHERE Stand_ID= '%StandID%'")
        all_keywords.append("EndSQL")
        all_keywords.append("TreeSQL")
        all_keywords.append("SELECT * FROM FVS_TreeInit")
        all_keywords.append("WHERE Stand_CN= '%StandID%'")
        all_keywords.append("EndSQL")
        all_keywords.append("END")
        all_keywords.append("")

        # Fire and Fuels Extension
        if config.output_carbon:
            all_keywords.append("FMIn")
            all_keywords.append("CarbRept        2")
            all_keywords.append("CarbCut")
            all_keywords.append("CarbCalc")
            all_keywords.append("End")
            all_keywords.append("")

        # Compute canopy cover
        if config.compute_canopy_cover:
            all_keywords.append("Compute            0")
            all_keywords.append("Pc_can_cover=SPMCDBH(7,All,0,1,200,0,500,0,0)")
            all_keywords.append("End")
            all_keywords.append("")

        # Management keywords
        if config.min_harvest_volume is not None:
            all_keywords.append(
                f"MINHARV           0       0.0       0.0       0.0       0.0{config.min_harvest_volume:10.1f}"
            )
            all_keywords.append("")

        if config.thin_q_factor is not None and config.thin_residual_ba is not None:
            year = config.thin_year if config.thin_year is not None else 0
            all_keywords.append(
                f"THINQFA   {year:10d}{config.thin_min_dbh:10.1f}{config.thin_max_dbh:10.1f}{0:10d}"
                f"{config.thin_q_factor:10.1f}{2.0:10.1f}{config.thin_residual_ba:10.1f}"
            )
            all_keywords.append("         0")
            all_keywords.append("")

        # Labels and process
        all_keywords.append("SPLabel")
        all_keywords.append("  All_Stands, & ")
        all_keywords.append("  Section6")
        all_keywords.append("Process")
        all_keywords.append("")

    # Final stop
    all_keywords.append("Stop")

    filepath.write_text("\n".join(all_keywords))
