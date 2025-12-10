# Monte Carlo FVS Batch Runner - Implementation TODO

## Status: Phase 3 Complete ✅

See `docs/plan_monte_carlo.md` for full design document.

---

## Phase 1: Data Structures & Sampling ✅ COMPLETE
**Target: `src/fvs_tools/monte_carlo/config.py`, `sampler.py`**

- [x] Create `src/fvs_tools/monte_carlo/` package directory
- [x] Create `__init__.py` with public exports
- [x] Implement `UniformParameterSpec` dataclass
- [x] Implement `BooleanParameterSpec` dataclass
- [x] Implement `DiscreteUniformSpec` dataclass
- [x] Implement `MonteCarloConfig` dataclass
  - [x] batch_id auto-generation
  - [x] Validation (n_samples > 0, n_workers > 0, etc.)
  - [x] plot_ids / stand_ids filtering
- [x] Implement `generate_parameter_samples(config) -> list[dict]`
  - [x] Deterministic from batch_seed
  - [x] Generate run_seed for each sample
- [x] Unit tests for sampling reproducibility (25 tests, all passing)

---

## Phase 2: Database Layer ✅ COMPLETE
**Target: `src/fvs_tools/monte_carlo/database.py`**

- [x] `create_mc_database(path)` - create SQLite with schema
- [x] `write_batch_meta(db, config)` - store batch config
- [x] `write_run_registry(db, batch_id, samples)` - pre-populate
- [x] `update_run_status(db, batch_id, run_id, status)` 
- [x] `write_run_summary(db, batch_id, run_id, metrics)`
- [x] `write_time_series(db, batch_id, run_id, df)`
- [x] `write_batch_error(db, batch_id, run_id, error_info)`
- [x] `load_mc_results(db_path) -> (registry, summary, timeseries)`
- [x] Unit tests (18 tests, all passing)

---

## Phase 3: FVS Integration (New Keywords) ✅ COMPLETE
**Target: `src/fvs_tools/config.py`, `keyword_builder.py`**

- [x] Add to `FVSSimulationConfig`:
  - [x] `mortality_multiplier: float | None = None`
  - [x] `enable_calibration: bool = True`
  - [x] `fvs_random_seed: int | None = None`
- [x] Update `keyword_builder.py`:
  - [x] Add `FixMort` keyword generation
  - [x] Add `NoCaLib` keyword generation  
  - [x] Add `RanNSeed` keyword generation
- [x] Test keyword generation with new params (21 tests passing)

---

## Phase 4: Output Extraction
**Target: `src/fvs_tools/monte_carlo/outputs.py`**

- [ ] `extract_run_summary(results_dict) -> dict`
  - [ ] final_total_carbon (Live + Dead + Stored)
  - [ ] avg_carbon_stock (mean over years)
  - [ ] min_canopy_cover
  - [ ] final_canopy_cover
  - [ ] cumulative_harvest_bdft
  - [ ] Handle missing data gracefully
- [ ] `extract_time_series(results_dict) -> DataFrame`
  - [ ] Per-year: carbon, canopy, BA, harvest
  - [ ] Aggregated across stands

---

## Phase 5: Parallel Executor
**Target: `src/fvs_tools/monte_carlo/executor.py`**

- [ ] `execute_single_run(run_config) -> RunResult`
  - [ ] Build FVSSimulationConfig from sampled params
  - [ ] Create temp output directory
  - [ ] Run FVS batch for all stands
  - [ ] Extract metrics
  - [ ] Return success/failure with data
- [ ] `run_monte_carlo_batch(config, stands, trees, output_dir) -> Path`
  - [ ] Generate samples
  - [ ] Initialize database
  - [ ] Write registry
  - [ ] Parallel execution with ProcessPoolExecutor
  - [ ] Serial result collection
  - [ ] Write summaries and time series
  - [ ] Log errors
  - [ ] Return database path
- [ ] Progress reporting (print or tqdm)
- [ ] Graceful handling of worker crashes

---

## Phase 6: Analysis & Demo
**Target: `src/fvs_tools/monte_carlo/analysis.py`, `notebooks/`**

- [ ] `compute_sensitivity(df, input_cols, output_col)` - correlation analysis
- [ ] `plot_parameter_importance(df, output_col)` - bar chart
- [ ] `plot_uncertainty_bands(timeseries, metric)` - percentile ribbons
- [ ] Demo notebook: `notebooks/MonteCarlo_Demo.ipynb`
  - [ ] Full workflow example
  - [ ] Sensitivity analysis plots
  - [ ] Interpretation guidance

---

## Testing Checklist

- [ ] Sampling is deterministic (same seed = same samples)
- [ ] Database schema validates correctly
- [ ] FixMort keyword produces expected mortality changes
- [ ] NoCaLib keyword disables calibration
- [ ] Parallel execution doesn't corrupt shared state
- [ ] Failed runs are logged, don't crash batch
- [ ] Results can be loaded and joined correctly

---

## Nice-to-Haves (Post-MVP)

- [ ] tqdm progress bars
- [ ] Checkpoint/resume for interrupted batches
- [ ] HTML report generation
- [ ] Batch comparison tools
