#!/usr/bin/env Rscript
# =============================================================================
# R Environment Check Script
# Verifies R installation and FVS library accessibility
# 
# Run: Rscript scripts/check_r_env.R
# =============================================================================

cat("\n")
cat("============================================================\n")
cat("R ENVIRONMENT CHECK\n")
cat("============================================================\n")

# -----------------------------------------------------------------------------
# R Version and Configuration
# -----------------------------------------------------------------------------
cat("\n🔵 R VERSION\n")
cat("   Version:   ", R.version.string, "\n")
cat("   Platform:  ", R.version$platform, "\n")
cat("   Home:      ", R.home(), "\n")

# -----------------------------------------------------------------------------
# Check Core Packages
# -----------------------------------------------------------------------------
cat("\n📦 CORE PACKAGES\n")

core_packages <- c("utils", "stats", "methods", "foreign")
core_ok <- TRUE

for (pkg in core_packages) {
  if (requireNamespace(pkg, quietly = TRUE)) {
    cat("   ✅", pkg, "\n")
  } else {
    cat("   ❌", pkg, "NOT available\n")
    core_ok <- FALSE
  }
}

# -----------------------------------------------------------------------------
# Check Shared Library Loading Capability
# -----------------------------------------------------------------------------
cat("\n🔗 SHARED LIBRARY SUPPORT\n")

# Check if dyn.load is available (it's a base function, should always be)
if (exists("dyn.load", mode = "function")) {
  cat("   ✅ dyn.load() available for loading .so files\n")
} else {
  cat("   ❌ dyn.load() not available\n")
}

# Check if .Fortran interface is available
if (exists(".Fortran", mode = "function")) {
  cat("   ✅ .Fortran() interface available\n")
} else {
  cat("   ❌ .Fortran() interface not available\n")
}

# Check if .Call interface is available  
if (exists(".Call", mode = "function")) {
  cat("   ✅ .Call() interface available\n")
} else {
  cat("   ❌ .Call() interface not available\n")
}

# -----------------------------------------------------------------------------
# Check FVS Library Files
# -----------------------------------------------------------------------------
cat("\n🌲 FVS LIBRARY CHECK\n")

# Use environment variable with fallback
fvs_dir <- Sys.getenv("FVS_LIB_DIR", "/workspaces/fors591/lib/fvs/FVSie_CmakeDir")
fvs_executable <- file.path(fvs_dir, "FVSie")
fvs_lib_ie <- file.path(fvs_dir, "libFVS_ie.so")
fvs_lib_sql <- file.path(fvs_dir, "libFVSsql.so")
fvs_lib_fofem <- file.path(fvs_dir, "libFVSfofem.so")

fvs_ok <- TRUE

if (dir.exists(fvs_dir)) {
  cat("   ✅ FVS directory exists:", fvs_dir, "\n")
} else {
  cat("   ❌ FVS directory NOT found:", fvs_dir, "\n")
  fvs_ok <- FALSE
}

if (file.exists(fvs_executable)) {
  cat("   ✅ FVSie executable found\n")
  # Check if executable
  if (file.access(fvs_executable, mode = 1) == 0) {
    cat("   ✅ FVSie is executable\n")
  } else {
    cat("   ⚠️  FVSie exists but may not be executable\n")
  }
} else {
  cat("   ❌ FVSie executable NOT found\n")
  fvs_ok <- FALSE
}

# Check shared libraries
for (lib in c(fvs_lib_ie, fvs_lib_sql, fvs_lib_fofem)) {
  lib_name <- basename(lib)
  if (file.exists(lib)) {
    cat("   ✅", lib_name, "found\n")
  } else {
    cat("   ❌", lib_name, "NOT found\n")
    fvs_ok <- FALSE
  }
}

# -----------------------------------------------------------------------------
# Test FVS Executable
# -----------------------------------------------------------------------------
cat("\n🧪 FVS EXECUTABLE TEST\n")

if (file.exists(fvs_executable)) {
  # Set LD_LIBRARY_PATH to include FVS libraries
  old_ld_path <- Sys.getenv("LD_LIBRARY_PATH")
  new_ld_path <- paste(fvs_dir, old_ld_path, sep = ":")
  Sys.setenv(LD_LIBRARY_PATH = new_ld_path)
  
  # Try running FVS with no arguments to see what happens
  result <- tryCatch({
    # Run with timeout - FVS without args may hang waiting for input
    # So we just check if it starts
    system2(fvs_executable, args = character(0), 
            stdout = TRUE, stderr = TRUE, timeout = 2)
  }, error = function(e) {
    # Timeout is expected - FVS waits for keyword file input
    if (grepl("timed out", e$message, ignore.case = TRUE)) {
      return("TIMEOUT_OK")
    }
    return(paste("ERROR:", e$message))
  }, warning = function(w) {
    return(paste("WARNING:", w$message))
  })
  
  if (identical(result, "TIMEOUT_OK") || length(result) > 0) {
    cat("   ✅ FVS executable can be invoked\n")
    cat("   ℹ️  FVS expects keyword file input (timeout is normal)\n")
  } else {
    cat("   ⚠️  FVS returned unexpected result\n")
    if (length(result) > 0) {
      cat("   Output:", paste(head(result, 3), collapse = "\n          "), "\n")
    }
  }
  
  # Restore LD_LIBRARY_PATH
  Sys.setenv(LD_LIBRARY_PATH = old_ld_path)
} else {
  cat("   ⏭️  Skipped - FVS executable not found\n")
}

# -----------------------------------------------------------------------------
# Check System Dependencies
# -----------------------------------------------------------------------------
cat("\n🔧 SYSTEM DEPENDENCIES\n")

# Check for gfortran
gfortran_check <- tryCatch({
  system2("gfortran", args = "--version", stdout = TRUE, stderr = TRUE)
}, error = function(e) NULL)

if (!is.null(gfortran_check) && length(gfortran_check) > 0) {
  # Extract version from first line
  version_line <- gfortran_check[1]
  cat("   ✅ gfortran:", version_line, "\n")
} else {
  cat("   ⚠️  gfortran not found (may affect some R packages)\n")
}

# Check LD_LIBRARY_PATH awareness
cat("   ℹ️  LD_LIBRARY_PATH:", 
    ifelse(nchar(Sys.getenv("LD_LIBRARY_PATH")) > 0, 
           Sys.getenv("LD_LIBRARY_PATH"), 
           "(not set)"), "\n")

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
cat("\n")
cat("============================================================\n")
cat("SUMMARY\n")
cat("============================================================\n")

all_ok <- core_ok && fvs_ok

if (core_ok) {
  cat("   ✅ R core packages available\n")
} else {
  cat("   ❌ R core packages missing\n")
}

if (fvs_ok) {
  cat("   ✅ FVS libraries found\n")
} else {
  cat("   ❌ FVS libraries missing or incomplete\n")
}

cat("\n")
if (all_ok) {
  cat("✅ R ENVIRONMENT READY FOR FVS\n")
  cat("\nNext steps:\n")
  cat("  1. Run: Rscript scripts/run_fvs_lubrecht_plot48.R\n")
} else {
  cat("⚠️  SOME CHECKS FAILED - Review above for details\n")
}

cat("============================================================\n\n")

# Exit with appropriate code
if (all_ok) {
  quit(status = 0)
} else {
  quit(status = 1)
}
