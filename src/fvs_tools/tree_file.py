"""
FVS tree list file generation.

Writes tree data in FVS fixed-width format.
"""

from pathlib import Path

import pandas as pd


def write_tree_file(
    trees: pd.DataFrame, stand: pd.Series, filepath: Path | str
) -> list[str]:
    """
    Write FVS tree file in fixed-width format.

    FVS expects the following format:
    (I4,I4,F8.3,I1,A3,F5.1,F5.1,2F5.1,F5.1,I1,6I2,2I1,I2,2I3,2I1,F3.0)

    Fields:
        Plot(4) TreeID(4) Count(8.3) History(1) Species(A3) DBH(5.1) DG(5.1)
        HT(5.1) HTTOPK(5.1) HTG(5.1) CRcode(1)
        DAM1(2) SEV1(2) DAM2(2) SEV2(2) DAM3(2) SEV3(2)
        TVAL(1) CUT(1) SLOPE(2) ASPECT(3) PVCODE(3) TOPO(1) SPREP(1) AGE(3)

    Args:
        trees: DataFrame with tree records for this stand
        stand: Series with stand-level attributes
        filepath: Output file path

    Returns:
        List of formatted tree record lines
    """
    filepath = Path(filepath)
    lines = []

    # Sort trees to ensure consistent ordering
    trees = trees.sort_values(["PLOT_ID", "TREE_ID"]).reset_index(drop=True)

    for i, (_, tree) in enumerate(trees.iterrows(), start=1):
        # Species code as 3-character string (zero-padded)
        spp_code = f"{int(tree['SPECIES']):03d}"

        # Extract values with defaults for missing data
        plot_id = int(tree.get("PLOT_ID", 1))
        tree_count = float(tree.get("TREE_COUNT", 1.0))
        history = int(tree.get("HISTORY", 1))
        diameter = float(tree["DIAMETER"])

        # Optional fields - use measured values if available, otherwise blank
        dg = f"{float(tree['DG']):5.1f}" if pd.notna(tree.get("DG")) else "     "
        ht = f"{float(tree['HT']):5.1f}" if pd.notna(tree.get("HT")) else "     "
        httopk = (
            f"{float(tree['HTTOPK']):5.1f}" if pd.notna(tree.get("HTTOPK")) else "     "
        )
        htg = f"{float(tree['HTG']):5.1f}" if pd.notna(tree.get("HTG")) else "     "

        # Crown ratio code (convert to class if present)
        if pd.notna(tree.get("CRRATIO")):
            cr_code = min(9, max(1, int(float(tree["CRRATIO"]) / 10 + 0.5)))
            cr_str = f"{cr_code:1d}"
        else:
            cr_str = " "

        # Damage codes (use if available)
        dam1 = f"{int(tree['DAMAGE1']):2d}" if pd.notna(tree.get("DAMAGE1")) else "  "
        sev1 = (
            f"{int(tree['SEVERITY1']):2d}" if pd.notna(tree.get("SEVERITY1")) else "  "
        )
        dam2 = f"{int(tree['DAMAGE2']):2d}" if pd.notna(tree.get("DAMAGE2")) else "  "
        sev2 = (
            f"{int(tree['SEVERITY2']):2d}" if pd.notna(tree.get("SEVERITY2")) else "  "
        )
        dam3 = f"{int(tree['DAMAGE3']):2d}" if pd.notna(tree.get("DAMAGE3")) else "  "
        sev3 = (
            f"{int(tree['SEVERITY3']):2d}" if pd.notna(tree.get("SEVERITY3")) else "  "
        )

        # Tree value and cut codes
        tval = " "
        cut = " "

        # Stand-level attributes - these always have data in our dataset
        slope = int(stand["SLOPE"])
        aspect = int(stand["ASPECT"])
        pv_code = str(int(stand["PV_CODE"]))
        topo = " "
        sprep = " "
        age = "   "

        # Build the fixed-width line
        line = (
            f"{plot_id:4d}"  # Plot ID (I4)
            f"{i:4d}"  # Tree ID (I4) - sequential
            f"{tree_count:8.3f}"  # Count (F8.3)
            f"{history:1d}"  # History (I1)
            f"{spp_code:>3s}"  # Species (A3)
            f"{diameter:5.1f}"  # DBH (F5.1)
            f"{dg}"  # DG (F5.1)
            f"{ht}"  # HT (F5.1)
            f"{httopk}"  # HTTOPK (F5.1)
            f"{htg}"  # HTG (F5.1)
            f"{cr_str}"  # CRcode (I1)
            f"{dam1}"  # DAM1 (I2)
            f"{sev1}"  # SEV1 (I2)
            f"{dam2}"  # DAM2 (I2)
            f"{sev2}"  # SEV2 (I2)
            f"{dam3}"  # DAM3 (I2)
            f"{sev3}"  # SEV3 (I2)
            f"{tval}"  # TVAL (I1)
            f"{cut}"  # CUT (I1)
            f"{slope:2d}"  # SLOPE (I2)
            f"{aspect:3d}"  # ASPECT (I3)
            f"{pv_code:>3s}"  # PVCODE (I3)
            f"{topo}"  # TOPO (I1)
            f"{sprep}"  # SPREP (I1)
            f"{age}"  # AGE (F3.0)
        )
        lines.append(line)

    # Write to file
    filepath.write_text("\n".join(lines) + "\n")

    return lines
