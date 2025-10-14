# Otter Application Tests

This directory contains tests for the Otter application components.

## Test Files

### Integration Tests

### `test_otter_basic.py`
Comprehensive integration test of all Otter Phase 1 components:
- ✅ Data source initialization and health check
- ✅ Listing runs with various filters (limit, beamline, time_range)
- ✅ Loading run metadata with all new fields (beamline, badger_environment, min/max values, VOCS structure)
- ✅ BadgerRunContext creation and validation
- ✅ Context methods: `get_access_details()` and `get_summary()`

**Run:** `python src/applications/otter/tests/test_otter_basic.py`

### `test_otter_capability.py`
Tests the `query_runs` capability in isolation with mock state:
- ✅ Capability accepts parameters from execution plan step
- ✅ Defaults to `num_runs=1` when no parameters provided
- ✅ Respects `num_runs` limits (1, 5, etc.)
- ✅ Creates correct number of BADGER_RUN contexts

**Run:** `python src/applications/otter/tests/test_otter_capability.py`

**Use case:** Debug orchestrator parameter generation issues without running full framework.

### Unit Tests

### `test_otter_filtering.py`
Tests the basic filtering functionality of the BadgerArchiveDataSource:
- ✅ Limit parameter works correctly (returns exactly N runs)
- ✅ Hidden directories (`.ipynb_checkpoints`, etc.) are filtered out
- ✅ Most recent runs are returned first
- ✅ Metadata can be loaded without errors

**Run:** `python src/applications/otter/tests/test_otter_filtering.py`

### `test_beamline_filter.py`
Tests beamline filtering functionality:
- ✅ Beamline filter correctly restricts to specified beamline directory
- ✅ Non-existent beamline returns empty results (not an error)
- ✅ Without filter, returns runs from all beamlines
- ✅ Metadata correctly extracts both `beamline` (from path) and `badger_environment` (from run file)

**Run:** `python src/applications/otter/tests/test_beamline_filter.py`

### `test_objective_stats.py`
Tests objective statistics extraction:
- ✅ Initial, min, max, and final values are extracted correctly
- ✅ VOCS structure (variables and objectives) uses list-of-dicts format
- ✅ Variable ranges are extracted from VOCS
- ✅ Objective directions (MAXIMIZE/MINIMIZE) are embedded in objectives list
- ✅ Direction-aware improvement calculations

**Run:** `python src/applications/otter/tests/test_objective_stats.py`

## Running All Tests

From the project root:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run integration tests
python src/applications/otter/tests/test_otter_basic.py
python src/applications/otter/tests/test_otter_capability.py

# Run unit tests
python src/applications/otter/tests/test_otter_filtering.py
python src/applications/otter/tests/test_beamline_filter.py
python src/applications/otter/tests/test_objective_stats.py
```

## Test Data

All tests use the Badger archive at: `/Users/zhezhang/Desktop/Otter/data/archive`

This archive contains runs from multiple beamlines:
- `cu_hxr` - Copper Hard X-Ray
- `cu_sxr` - Copper Soft X-Ray
- `dev` - Development
- `sc_bsyd` - Superconducting BSYD
- `sc_diag0` - Superconducting Diagnostics
- `sc_hxr` - Superconducting Hard X-Ray
- `sc_sxr` - Superconducting Soft X-Ray

## Key Terminology

- **Beamline**: Top-level directory in archive (e.g., `cu_hxr`, `lcls_ii`)
- **Badger Environment**: Environment name from run file metadata (e.g., `lcls`, `sphere`, `epics`)
- **Run File**: YAML file containing optimization run data, named as `{env}-YYYY-MM-DD-HHMMSS.yaml`

## Notes

- Tests verify that the data source correctly handles the distinction between beamlines (directory structure) and Badger environments (run file metadata)
- All tests use filename-based timestamps rather than file modification times for robustness when files are copied/moved
