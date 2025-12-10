"""
FVS execution wrapper.

Handles running the FVS binary and capturing outputs.
"""

import shutil
import subprocess
from pathlib import Path


def run_fvs(
    keyword_file: Path | str,
    working_dir: Path | str,
    fvs_binary: Path | str,
    timeout: int = 300,
    input_database: Path | str | None = None,
) -> dict:
    """
    Run FVS executable with the given keyword file.

    FVS reads the keyword filename from stdin and writes outputs to the working directory.

    Args:
        keyword_file: Path to FVS keyword file
        working_dir: Directory to run FVS in (outputs will be written here)
        fvs_binary: Path to FVS executable
        timeout: Maximum execution time in seconds
        input_database: Path to FVS input database (FVS_Data.db) to copy to working_dir

    Returns:
        Dictionary with:
            - exit_code: FVS exit code (0 = success)
            - stdout: Standard output text
            - stderr: Standard error text
            - success: Boolean indicating successful run

    Raises:
        subprocess.TimeoutExpired: If execution exceeds timeout
        FileNotFoundError: If FVS binary or keyword file not found
    """
    keyword_file = Path(keyword_file)
    working_dir = Path(working_dir)
    fvs_binary = Path(fvs_binary)

    # Validate inputs
    if not keyword_file.exists():
        raise FileNotFoundError(f"Keyword file not found: {keyword_file}")

    if not fvs_binary.exists():
        raise FileNotFoundError(f"FVS binary not found: {fvs_binary}")

    if not working_dir.exists():
        working_dir.mkdir(parents=True, exist_ok=True)

    # Copy input database if provided
    if input_database is not None:
        input_database = Path(input_database)
        if not input_database.exists():
            raise FileNotFoundError(f"Input database not found: {input_database}")

        target_db = working_dir / input_database.name
        shutil.copy2(input_database, target_db)

    # FVS expects the keyword filename (not full path) on stdin
    keyword_filename = keyword_file.name

    # Clean up previous database output to ensure fresh results
    # NOTE: When running batch simulations in the same directory, we might want to append
    # to the database instead of deleting it. However, FVS behavior with existing DBs
    # can be tricky. For now, we assume one run per directory or that the caller handles this.
    # If we are running multiple stands in the same directory, we should NOT delete this
    # every time.

    # db_file = working_dir / "FVSOut.db"
    # if db_file.exists():
    #     db_file.unlink()

    # Run FVS
    result = subprocess.run(
        [str(fvs_binary)],
        input=keyword_filename,
        capture_output=True,
        text=True,
        cwd=working_dir,
        timeout=timeout,
    )

    # Save stdout and stderr to files in working directory
    (working_dir / "fvs.out").write_text(result.stdout)
    (working_dir / "fvs.err").write_text(result.stderr)

    # FVS returns exit code 20 for successful completion and writes "STOP 20" to stderr
    # STOP 10 means completed with warnings (benign SDI adjustments, etc.) - also success
    # Check for these patterns rather than relying on exit code == 0
    fvs_success = (
        "STOP 20" in result.stderr
        or "STOP 10" in result.stderr
        or result.returncode == 0
    )

    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": fvs_success,
    }


def check_fvs_errors(working_dir: Path | str) -> list[str]:
    """
    Check FVS error file for warnings/errors.

    Args:
        working_dir: Directory containing FVS outputs

    Returns:
        List of error/warning messages (empty if none)

    Note:
        Filters out FVS completion codes:
        - STOP 20: Normal completion (no warnings)
        - STOP 10: Completed with warnings (e.g., SDI adjustments)
    """
    working_dir = Path(working_dir)
    err_file = working_dir / "fvs.err"

    if not err_file.exists():
        return []

    content = err_file.read_text().strip()
    if not content:
        return []

    # Split into lines and filter out empty lines
    errors = [line.strip() for line in content.splitlines() if line.strip()]

    # Filter out FVS completion codes (both normal and completed-with-warnings)
    # STOP 20 = normal completion
    # STOP 10 = completed with warnings (benign SDI adjustments, etc.)
    errors = [err for err in errors if err.strip() not in ("STOP 20", "STOP 10")]

    return errors


def get_fvs_output_files(working_dir: Path | str) -> dict[str, Path]:
    """
    Locate FVS output files in the working directory.

    Args:
        working_dir: Directory containing FVS outputs

    Returns:
        Dictionary mapping file types to paths:
            - database: FVSOut.db
            - stdout: fvs.out
            - stderr: fvs.err
            - summary: run.sum (if exists)
            - treelist: run.tre (if exists)
    """
    working_dir = Path(working_dir)

    files = {
        "database": working_dir / "FVSOut.db",
        "stdout": working_dir / "fvs.out",
        "stderr": working_dir / "fvs.err",
    }

    # Optional files
    for name, pattern in [("summary", "*.sum"), ("treelist", "run.tre")]:
        matches = list(working_dir.glob(pattern))
        if matches:
            files[name] = matches[0]

    # Filter to existing files
    return {k: v for k, v in files.items() if v.exists()}
