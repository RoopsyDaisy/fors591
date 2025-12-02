#!/usr/bin/env Rscript
# Quick script to inspect the Excel data file structure

if (!requireNamespace("readxl", quietly = TRUE)) {
    # Create user library if needed
    user_lib <- Sys.getenv("R_LIBS_USER")
    if (!dir.exists(user_lib)) dir.create(user_lib, recursive = TRUE)
    install.packages("readxl", lib = user_lib, repos = "https://cloud.r-project.org")
}
library(readxl)

DATA_FILE <- "/workspaces/fors591/data/plot48_fvsready_simplified.xlsx"

cat("Inspecting:", DATA_FILE, "\n\n")

# List sheets
sheets <- excel_sheets(DATA_FILE)
cat("Sheets:", paste(sheets, collapse = ", "), "\n\n")

# Read and display each sheet
for (sheet in sheets) {
    cat("=== Sheet:", sheet, "===\n")
    df <- as.data.frame(read_xlsx(DATA_FILE, sheet = sheet))
    cat("Dimensions:", nrow(df), "rows x", ncol(df), "columns\n")
    cat("Columns:", paste(names(df), collapse = ", "), "\n")
    cat("\nFirst few rows:\n")
    print(head(df, 3))
    cat("\n")
}
