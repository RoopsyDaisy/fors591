"""
FVS Tools - Library for running FVS simulations in Python.

This package provides utilities for:
- Loading and filtering FVS-ready stand and tree data
- Generating FVS keyword and tree list files
- Running FVS simulations
- Parsing FVS output databases
- Batch processing multiple stands
- Experiment management for parameter sweeps
"""

from .config import FVSSimulationConfig
from .data_loader import (
    load_stands,
    load_trees,
    filter_by_plot_ids,
    get_stand_trees,
    prepare_fvs_database,
    get_carbon_plot_ids,
    validate_stands,
    print_validation_report,
)
from .keyword_builder import build_keyword_file
from .tree_file import write_tree_file
from .runner import run_fvs
from .output_parser import parse_fvs_db
from .batch import run_batch_simulation, aggregate_by_period, collect_batch_errors
from .db_input import create_fvs_input_db, verify_fvs_input_db
from .experiment import ExperimentBatch, load_batch_registry, load_batch_results

__all__ = [
    "FVSSimulationConfig",
    "load_stands",
    "load_trees",
    "filter_by_plot_ids",
    "get_stand_trees",
    "prepare_fvs_database",
    "get_carbon_plot_ids",
    "validate_stands",
    "print_validation_report",
    "create_fvs_input_db",
    "verify_fvs_input_db",
    "build_keyword_file",
    "write_tree_file",
    "run_fvs",
    "parse_fvs_db",
    "run_batch_simulation",
    "aggregate_by_period",
    "collect_batch_errors",
    "ExperimentBatch",
    "load_batch_registry",
    "load_batch_results",
]
