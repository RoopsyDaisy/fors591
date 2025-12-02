#!/usr/bin/env Rscript
# =============================================================================
# Simple FVS Run Script
# Runs FVS on simplified Lubrecht plot data using command-line FVS
#
# This script reads the FVS-ready data, generates keyword and tree files,
# then runs the standalone FVS executable.
#
# Run: Rscript scripts/run_fvs_lubrecht_plot48.R
# =============================================================================

library(readxl)

cat("\n")
cat("============================================================\n")
cat("FVS SIMPLE RUN - Lubrecht Plot 48\n")
cat("============================================================\n")

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
FVS_DIR <- Sys.getenv("FVS_LIB_DIR", "/workspaces/fors591/lib/fvs/FVSie_CmakeDir")
FVS_BIN <- file.path(FVS_DIR, "FVSie")
DATA_FILE <- "/workspaces/fors591/data/plot48_fvsready_simplified.xlsx"
OUTPUT_DIR <- "/workspaces/fors591/outputs/fvs_lubrecht_plot48"

# Create output directory
dir.create(OUTPUT_DIR, recursive = TRUE, showWarnings = FALSE)

cat("\nConfiguration:\n")
cat("  FVS Binary:", FVS_BIN, "\n")
cat("  Data File: ", DATA_FILE, "\n")
cat("  Output Dir:", OUTPUT_DIR, "\n")

# -----------------------------------------------------------------------------
# Read the input data
# -----------------------------------------------------------------------------
cat("\n--- Loading Data ---\n")

FVS_StandInit <- as.data.frame(read_xlsx(DATA_FILE, sheet = "FVS_StandInit"))
FVS_TreeInit <- as.data.frame(read_xlsx(DATA_FILE, sheet = "FVS_TreeInit"))

cat("Stand data:", nrow(FVS_StandInit), "rows\n")
cat("Tree data:", nrow(FVS_TreeInit), "rows\n")

# Use the first (only) stand
stand <- FVS_StandInit[1, ]
trees <- FVS_TreeInit

cat("\nStand:", stand$STAND_ID, "\n")
cat("Variant:", stand$VARIANT, "\n")
cat("Inventory Year:", stand$INV_YEAR, "\n")
cat("Trees:", nrow(trees), "\n")

# -----------------------------------------------------------------------------
# FVS Projection Parameters
# -----------------------------------------------------------------------------
num_years <- 20
num_cycles <- ceiling(num_years / 10)

cat("\nProjection:", num_years, "years (", num_cycles, "cycles)\n")

# -----------------------------------------------------------------------------
# Create FVS Input Files
# -----------------------------------------------------------------------------
cat("\n--- Creating FVS Input Files ---\n")

# Change to output directory
old_wd <- getwd()
setwd(OUTPUT_DIR)

# Tree file format for FVS - must use full format that FVS expects
# Format from reference: (I4,I4,F8.3,I1,A3,F5.1,F5.1,2F5.1,F5.1,I1,6I2,2I1,I2,2I3,2I1,F3.0)
# Fields: Plot(4) TreeID(4) Count(8.3) History(1) Species(A3) DBH(5.1) DG(5.1)
#         HT(5.1) HTTOPK(5.1) HTG(5.1) CRcode(1)
#         DAM1(2) SEV1(2) DAM2(2) SEV2(2) DAM3(2) SEV3(2)
#         TVAL(1) CUT(1) SLOPE(2) ASPECT(3) PVCODE(3) TOPO(1) SPREP(1) AGE(3)
tree_lines <- character(nrow(trees))
for (i in seq_len(nrow(trees))) {
    t <- trees[i, ]
    spp_code <- sprintf("%03d", as.integer(t$SPECIES))
    # Use full format with blanks for missing values
    tree_lines[i] <- sprintf(
        "%4d%4d%8.3f%1d%3s%5.1f%5s%5s%5s%5s%1s%2s%2s%2s%2s%2s%2s%1s%1s%2d%3d%3s%1s%1s%3s",
        as.integer(t$PLOT_ID),
        i,
        as.numeric(t$TREE_COUNT),
        as.integer(t$HISTORY),
        spp_code,
        as.numeric(t$DIAMETER),
        "", # DG - diameter growth
        "", # HT - height
        "", # HTTOPK - height to top kill
        "", # HTG - height growth
        "", # CRcode - crown ratio code
        "", # DAM1
        "", # SEV1
        "", # DAM2
        "", # SEV2
        "", # DAM3
        "", # SEV3
        "", # TVAL
        "", # CUT
        as.integer(stand$SLOPE),
        as.integer(stand$ASPECT),
        stand$PV_CODE,
        "", # TOPO
        "", # SPREP
        "" # AGE
    )
}

writeLines(tree_lines, "run.tre")
cat("Created tree file: run.tre\n")

# Show what we wrote
cat("\nTree file contents:\n")
for (line in tree_lines) {
    cat("  ", line, "\n")
}

# -----------------------------------------------------------------------------
# Create FVS Keyword File
# -----------------------------------------------------------------------------

# Build keyword file
key_lines <- c(
    "STDIDENT",
    sprintf("%-10s  Lubrecht Plot 48 FVS Run", stand$STAND_ID),
    "",
    # Stand info - note elevation in hundreds of feet
    sprintf(
        "STDINFO          %2.0f%10s          %10.1f%10.1f%10.0f",
        as.numeric(stand$FOREST),
        stand$PV_CODE,
        as.numeric(stand$ASPECT),
        as.numeric(stand$SLOPE),
        as.numeric(stand$ELEVFT) / 100
    ),
    "",
    # Inventory year
    sprintf("INVYEAR   %10d", as.integer(stand$INV_YEAR)),
    "",
    # Number of projection cycles (10 years each)
    sprintf("NUMCYCLE  %10d", num_cycles),
    "",
    # Tree data format - full format matching reference script
    "TREEFMT",
    "(I4,I4,F8.3,I1,A3,F5.1,F5.1,2F5.1,F5.1,I1,6I2,2I1,I2,2I3,2I1,F3.0)",
    "",
    # Tree file input
    "TREELIST          0         0         0         0         0         0         0",
    "run.tre",
    "",
    # Sample design (BAF and plot info)
    sprintf(
        "DESIGN    %10.1f         0         0%10d         0         0       1.0",
        as.numeric(stand$BASAL_AREA_FACTOR),
        as.integer(stand$NUM_PLOTS)
    ),
    "",
    # No tripling (bar tripling of tree records)
    "NOTRIPLE",
    "",
    # Echo summary to main output
    "ECHOSUM",
    "",
    # Create SQLite database output
    "DATABASE",
    "DSNOUT",
    "FVSOut.db",
    "SUMMARY",
    "END",
    "",
    # Process and stop
    "PROCESS",
    "STOP"
)

writeLines(key_lines, "run.key")
cat("Created keyword file: run.key\n")

# Show what we wrote
cat("\nKeyword file contents:\n")
for (line in key_lines) {
    cat("  ", line, "\n")
}

# -----------------------------------------------------------------------------
# Run FVS
# -----------------------------------------------------------------------------
cat("\n--- Running FVS ---\n")

fvs_result <- tryCatch(
    {
        system2(FVS_BIN,
            input = "run.key",
            stdout = "fvs.out",
            stderr = "fvs.err",
            timeout = 120
        )
    },
    error = function(e) {
        cat("Error running FVS:", e$message, "\n")
        -1
    }
)

cat("FVS exit code:", fvs_result, "\n")

# -----------------------------------------------------------------------------
# Check outputs
# -----------------------------------------------------------------------------
cat("\n--- Output Files ---\n")

output_files <- list.files(".", full.names = FALSE)
for (f in output_files) {
    fsize <- file.info(f)$size
    cat(sprintf("  %-20s %8d bytes\n", f, fsize))
}

# Show FVS output
if (file.exists("fvs.out")) {
    cat("\n--- FVS Output (first 50 lines) ---\n")
    out_lines <- readLines("fvs.out", n = 50, warn = FALSE)
    for (line in out_lines) {
        cat(line, "\n")
    }
}

# Show any errors
if (file.exists("fvs.err")) {
    err_content <- readLines("fvs.err", warn = FALSE)
    if (length(err_content) > 0 && any(nchar(err_content) > 0)) {
        cat("\n--- FVS Errors ---\n")
        for (line in err_content) {
            if (nchar(line) > 0) cat(line, "\n")
        }
    }
}

# Check for FVS database output
if (file.exists("FVSOut.db")) {
    cat("\n--- FVS Database Output ---\n")
    if (requireNamespace("RSQLite", quietly = TRUE)) {
        library(RSQLite)
        con <- dbConnect(SQLite(), "FVSOut.db")
        tables <- dbListTables(con)
        cat("Tables in FVSOut.db:", paste(tables, collapse = ", "), "\n")

        # Show summary if available
        if ("FVS_Summary" %in% tables) {
            cat("\nFVS_Summary:\n")
            summary_df <- dbReadTable(con, "FVS_Summary")
            print(summary_df)
        }

        dbDisconnect(con)
    } else {
        cat("FVSOut.db created (install RSQLite to inspect)\n")
    }
}

# Restore working directory
setwd(old_wd)

cat("\n============================================================\n")
cat("FVS RUN COMPLETE\n")
cat("Output directory:", OUTPUT_DIR, "\n")
cat("============================================================\n")
