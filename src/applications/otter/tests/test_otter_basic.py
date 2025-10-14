"""
Basic test script for Otter Phase 1 implementation.

Tests:
1. BadgerArchiveDataSource initialization and health check
2. Listing runs with various filters
3. Loading run metadata
4. BadgerRunContext creation
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from applications.otter.data_sources.badger_archive import BadgerArchiveDataSource
from applications.otter.context_classes import BadgerRunContext


def test_data_source():
    """Test BadgerArchiveDataSource"""
    print("=" * 60)
    print("TEST 1: BadgerArchiveDataSource Initialization and Health Check")
    print("=" * 60)

    # Initialize data source
    archive_path = "/Users/zhezhang/Desktop/Otter/data/archive"
    print(f"Initializing data source with archive: {archive_path}")

    try:
        data_source = BadgerArchiveDataSource(archive_path)
        print("✓ Data source initialized successfully")
    except Exception as e:
        print(f"✗ Data source initialization failed: {e}")
        return False

    # Health check
    print("\nRunning health check...")
    if data_source.health_check():
        print("✓ Health check passed")
    else:
        print("✗ Health check failed")
        return False

    return data_source


def test_list_runs(data_source):
    """Test listing runs with various filters"""
    print("\n" + "=" * 60)
    print("TEST 2: Listing Runs with Filters")
    print("=" * 60)

    # Test 1: Get most recent run
    print("\n2.1: Get most recent run (limit=1)")
    runs = data_source.list_runs(limit=1)
    if runs:
        print(f"✓ Found most recent run: {runs[0]}")
    else:
        print("✗ No runs found")
        return False

    # Test 2: Get last 5 runs
    print("\n2.2: Get last 5 runs (limit=5)")
    runs = data_source.list_runs(limit=5)
    print(f"✓ Found {len(runs)} runs:")
    for i, run in enumerate(runs, 1):
        print(f"   {i}. {run}")

    # Test 3: Get runs from specific beamline
    print("\n2.3: Get runs from cu_hxr beamline (limit=3)")
    runs = data_source.list_runs(beamline="cu_hxr", limit=3)
    if runs:
        print(f"✓ Found {len(runs)} cu_hxr runs:")
        for i, run in enumerate(runs, 1):
            print(f"   {i}. {run}")
    else:
        print("  No cu_hxr runs found (might not exist in archive)")

    # Test 4: Get runs from time range
    print("\n2.4: Get runs from October 2025 (time_range filter)")
    runs = data_source.list_runs(
        time_range={"start": "2025-10-01", "end": "2025-10-31"},
        limit=3
    )
    if runs:
        print(f"✓ Found {len(runs)} runs from October 2025:")
        for i, run in enumerate(runs, 1):
            print(f"   {i}. {run}")
    else:
        print("  No runs found in October 2025 (time filter is based on file modification time)")

    # Return any runs found in earlier tests
    runs = data_source.list_runs(limit=1)
    return runs[0] if runs else None


def test_load_metadata(data_source, run_path):
    """Test loading run metadata"""
    print("\n" + "=" * 60)
    print("TEST 3: Loading Run Metadata")
    print("=" * 60)

    print(f"\nLoading metadata for: {run_path}")
    try:
        metadata = data_source.load_run_metadata(run_path)
        print("✓ Metadata loaded successfully")
        print("\nRun Details:")
        print(f"  Name: {metadata['name']}")
        print(f"  Beamline: {metadata['beamline']}")
        print(f"  Badger Environment: {metadata['badger_environment']}")
        print(f"  Algorithm: {metadata['algorithm']}")
        print(f"  Timestamp: {metadata['timestamp']}")
        # Variables are now List[Dict[str, List[float]]]
        print(f"  Variables ({len(metadata['variables'])}):")
        for var_dict in metadata['variables'][:3]:
            var_name = list(var_dict.keys())[0]
            var_range = var_dict[var_name]
            print(f"    - {var_name}: [{var_range[0]:.4f}, {var_range[1]:.4f}]")
        if len(metadata['variables']) > 3:
            print(f"    ... and {len(metadata['variables']) - 3} more")
        # Objectives are now List[Dict[str, str]]
        print(f"  Objectives ({len(metadata['objectives'])}):")
        for obj_dict in metadata['objectives']:
            obj_name = list(obj_dict.keys())[0]
            direction = obj_dict[obj_name]
            print(f"    - {obj_name}: {direction}")
        print(f"  Constraints: {metadata.get('constraints', [])}")
        print(f"  Evaluations: {metadata['num_evaluations']}")
        if metadata.get('initial_values'):
            print(f"  Initial values: {metadata['initial_values']}")
        if metadata.get('min_values'):
            print(f"  Min values: {metadata['min_values']}")
        if metadata.get('max_values'):
            print(f"  Max values: {metadata['max_values']}")
        if metadata.get('final_values'):
            print(f"  Final values: {metadata['final_values']}")

        return metadata

    except Exception as e:
        print(f"✗ Failed to load metadata: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_context_creation(metadata, run_path):
    """Test BadgerRunContext creation"""
    print("\n" + "=" * 60)
    print("TEST 4: BadgerRunContext Creation")
    print("=" * 60)

    print("\nCreating BadgerRunContext...")
    try:
        context = BadgerRunContext(
            run_filename=run_path,
            run_name=metadata["name"],
            timestamp=metadata["timestamp"],
            beamline=metadata["beamline"],
            badger_environment=metadata["badger_environment"],
            algorithm=metadata["algorithm"],
            variables=metadata["variables"],
            objectives=metadata["objectives"],
            constraints=metadata.get("constraints", []),
            num_evaluations=metadata["num_evaluations"],
            initial_objective_values=metadata.get("initial_values"),
            min_objective_values=metadata.get("min_values"),
            max_objective_values=metadata.get("max_values"),
            final_objective_values=metadata.get("final_values"),
            description=metadata.get("description", ""),
            tags=metadata.get("tags")
        )
        print("✓ Context created successfully")

        # Test get_access_details
        print("\nTesting get_access_details()...")
        access_details = context.get_access_details("test_key")
        print("✓ Access details generated:")
        print(f"  Run name: {access_details['run_identification']['name']}")
        print(f"  Algorithm: {access_details['optimization_config']['algorithm']}")
        print(f"  Variables: {access_details['optimization_config']['num_variables']}")
        print(f"  Objectives: {access_details['optimization_config']['num_objectives']}")

        # Test get_summary
        print("\nTesting get_summary()...")
        summary = context.get_summary("test_key")
        print("✓ Summary generated:")
        print(f"  Type: {summary['type']}")
        print(f"  Run name: {summary['run_name']}")
        print(f"  Timestamp: {summary['timestamp']}")
        print(f"  Algorithm: {summary['algorithm']}")

        return True

    except Exception as e:
        print(f"✗ Failed to create context: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("OTTER PHASE 1 BASIC TESTS")
    print("=" * 60)

    # Test 1: Data source
    data_source = test_data_source()
    if not data_source:
        print("\n✗ Data source tests failed - aborting")
        return False

    # Test 2: List runs
    run_path = test_list_runs(data_source)
    if not run_path:
        print("\n✗ List runs tests failed - aborting")
        return False

    # Test 3: Load metadata
    metadata = test_load_metadata(data_source, run_path)
    if not metadata:
        print("\n✗ Metadata loading tests failed - aborting")
        return False

    # Test 4: Context creation
    success = test_context_creation(metadata, run_path)
    if not success:
        print("\n✗ Context creation tests failed")
        return False

    # All tests passed
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nOtter Phase 1 implementation is working correctly.")
    print("Ready for end-to-end testing with the full framework.")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
