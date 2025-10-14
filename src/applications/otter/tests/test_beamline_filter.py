"""
Test beamline filtering in data source.
"""

import sys
from pathlib import Path

# Add project src to path (we're in src/applications/otter/tests/)
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from applications.otter.data_sources.badger_archive import BadgerArchiveDataSource

def test_beamline_filter():
    """Test that beamline filter works correctly."""

    archive_path = "/Users/zhezhang/Desktop/Otter/data/archive"

    print("=" * 80)
    print("BEAMLINE FILTER TEST")
    print("=" * 80)
    print()

    # Initialize data source
    ds = BadgerArchiveDataSource(archive_path)

    # Test 1: Filter by cu_hxr beamline
    print("Test 1: Filter by beamline='cu_hxr', limit=3")
    print("-" * 80)
    runs = ds.list_runs(beamline="cu_hxr", limit=3)
    print(f"✅ Found {len(runs)} runs from cu_hxr beamline")
    for i, run in enumerate(runs, 1):
        # Check that all runs are from cu_hxr directory
        if run.startswith("cu_hxr/"):
            print(f"  {i}. {run} ✓")
        else:
            print(f"  {i}. {run} ✗ (NOT from cu_hxr!)")
            return False
    print()

    # Test 2: Filter by non-existent beamline
    print("Test 2: Filter by beamline='lcls_ii' (doesn't exist)")
    print("-" * 80)
    runs = ds.list_runs(beamline="lcls_ii", limit=3)
    if len(runs) == 0:
        print(f"✅ Correctly returned 0 runs for non-existent beamline")
    else:
        print(f"✗ Expected 0 runs, got {len(runs)}")
        return False
    print()

    # Test 3: No beamline filter (gets from all beamlines)
    print("Test 3: No beamline filter, limit=5")
    print("-" * 80)
    runs = ds.list_runs(limit=5)
    print(f"✅ Found {len(runs)} runs from all beamlines")
    beamlines_seen = set()
    for i, run in enumerate(runs, 1):
        beamline = run.split('/')[0]
        beamlines_seen.add(beamline)
        print(f"  {i}. {run} (beamline: {beamline})")
    print(f"  Beamlines represented: {sorted(beamlines_seen)}")
    print()

    # Test 4: Load metadata and verify beamline field
    print("Test 4: Load metadata from cu_hxr run and verify beamline field")
    print("-" * 80)
    cu_hxr_runs = ds.list_runs(beamline="cu_hxr", limit=1)
    if cu_hxr_runs:
        metadata = ds.load_run_metadata(cu_hxr_runs[0])
        print(f"  Run: {cu_hxr_runs[0]}")
        print(f"  Beamline (from metadata): {metadata.get('beamline')}")
        print(f"  Badger Environment (from run file): {metadata.get('badger_environment')}")

        if metadata.get('beamline') == 'cu_hxr':
            print(f"  ✅ Beamline field correctly extracted from path")
        else:
            print(f"  ✗ Expected beamline='cu_hxr', got '{metadata.get('beamline')}'")
            return False
    else:
        print("  ✗ No cu_hxr runs found")
        return False
    print()

    print("=" * 80)
    print("✅ All beamline filter tests passed!")
    print("=" * 80)

    return True

if __name__ == "__main__":
    success = test_beamline_filter()
    sys.exit(0 if success else 1)
