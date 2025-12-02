#!/bin/bash
# =============================================================================
# FVS Library Symbol Inspector
# Examines exported symbols from FVS shared libraries
#
# Run: bash scripts/inspect_fvs_symbols.sh
# =============================================================================

# Use environment variable with fallback
FVS_DIR="${FVS_LIB_DIR:-/workspaces/fors591/lib/fvs/FVSie_CmakeDir}"

echo ""
echo "============================================================"
echo "FVS LIBRARY SYMBOL INSPECTION"
echo "============================================================"
echo ""

# Check if directory exists
if [ ! -d "$FVS_DIR" ]; then
    echo "❌ FVS directory not found: $FVS_DIR"
    exit 1
fi

echo "📂 FVS Directory: $FVS_DIR"
echo ""

# List all shared libraries
echo "📦 Shared Libraries Found:"
echo "-----------------------------------------------------------"
ls -la "$FVS_DIR"/*.so 2>/dev/null || echo "   No .so files found"
echo ""

# Function to inspect a library
inspect_lib() {
    local lib_path="$1"
    local lib_name=$(basename "$lib_path")
    
    if [ ! -f "$lib_path" ]; then
        echo "   ⚠️  $lib_name not found"
        return
    fi
    
    echo "=== $lib_name ==="
    echo ""
    
    # Count total symbols
    total=$(nm -D "$lib_path" 2>/dev/null | wc -l)
    echo "Total exported symbols: $total"
    echo ""
    
    # Show text (function) symbols - these are callable
    echo "📍 Exported Functions (first 30):"
    echo "-----------------------------------------------------------"
    nm -D "$lib_path" 2>/dev/null | grep " T " | head -30
    echo ""
    
    # Look for common FVS API patterns
    echo "🔍 FVS-specific symbols (fvs, init, run, step, sim):"
    echo "-----------------------------------------------------------"
    nm -D "$lib_path" 2>/dev/null | grep -iE "fvs|init|run|step|sim|grow|mort|regen" | head -20
    echo ""
}

# Inspect main FVS library
echo ""
echo "============================================================"
echo "MAIN FVS LIBRARY (libFVS_ie.so)"
echo "============================================================"
inspect_lib "$FVS_DIR/libFVS_ie.so"

# Inspect SQL library
echo ""
echo "============================================================"
echo "SQL LIBRARY (libFVSsql.so)"
echo "============================================================"
inspect_lib "$FVS_DIR/libFVSsql.so"

# Inspect FOFEM library
echo ""
echo "============================================================"
echo "FOFEM LIBRARY (libFVSfofem.so)"
echo "============================================================"
inspect_lib "$FVS_DIR/libFVSfofem.so"

# Check executable
echo ""
echo "============================================================"
echo "FVS EXECUTABLE"
echo "============================================================"
FVS_BIN="$FVS_DIR/FVSie"

if [ -f "$FVS_BIN" ]; then
    echo "📍 Executable: $FVS_BIN"
    echo ""
    echo "File info:"
    file "$FVS_BIN"
    echo ""
    echo "Dependencies (ldd):"
    echo "-----------------------------------------------------------"
    ldd "$FVS_BIN" 2>/dev/null || echo "   Could not run ldd"
else
    echo "❌ FVS executable not found"
fi

echo ""
echo "============================================================"
echo "FORTRAN MODULE FILES (.mod)"
echo "============================================================"
echo "These indicate Fortran modules that may define interfaces:"
ls -la "$FVS_DIR"/*.mod 2>/dev/null || echo "   No .mod files found"

echo ""
echo "============================================================"
echo "INSPECTION COMPLETE"
echo "============================================================"
echo ""
echo "💡 Tips for R integration:"
echo "   1. Functions marked 'T' are exported and potentially callable"
echo "   2. Fortran symbols often have trailing underscores (e.g., 'grow_')"
echo "   3. Use .Fortran() for Fortran subroutines"
echo "   4. Use .Call() for C functions"
echo "   5. System calls to FVSie executable are the safest approach"
echo ""
