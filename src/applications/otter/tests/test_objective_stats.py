"""
Test objective statistics extraction (init, min, max, final).
"""

import sys
from pathlib import Path

# Add project src to path (we're in src/applications/otter/tests/)
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from applications.otter.data_sources.badger_archive import BadgerArchiveDataSource

def test_objective_stats():
    """Test that we extract init, min, max, final values correctly."""

    archive_path = "/Users/zhezhang/Desktop/Otter/data/archive"

    print("=" * 80)
    print("OBJECTIVE STATISTICS TEST")
    print("=" * 80)
    print()

    # Initialize data source
    ds = BadgerArchiveDataSource(archive_path)

    # Get most recent run
    runs = ds.list_runs(limit=1)
    if not runs:
        print("❌ No runs found")
        return False

    run_path = runs[0]
    print(f"Testing with run: {run_path}")
    print()

    # Load metadata
    metadata = ds.load_run_metadata(run_path)

    # Check that we have the expected fields
    required_fields = [
        'initial_values',
        'min_values',
        'max_values',
        'final_values'
    ]

    for field in required_fields:
        if field not in metadata:
            print(f"❌ Missing field: {field}")
            return False
        print(f"✅ Field '{field}' present")

    # Check VOCS structure
    if 'objectives' not in metadata or not isinstance(metadata['objectives'], list):
        print("❌ objectives field missing or not a list")
        return False
    print("✅ Field 'objectives' present (list format)")

    if 'variables' not in metadata or not isinstance(metadata['variables'], list):
        print("❌ variables field missing or not a list")
        return False
    print("✅ Field 'variables' present (list format)")

    print()
    print("=" * 80)
    print("VARIABLE DETAILS")
    print("=" * 80)
    print()
    print(f"Found {len(metadata['variables'])} variables:")
    for var_dict in metadata['variables'][:3]:  # Show first 3
        var_name = list(var_dict.keys())[0]
        var_range = var_dict[var_name]
        print(f"  {var_name}: [{var_range[0]:.4f}, {var_range[1]:.4f}]")
    if len(metadata['variables']) > 3:
        print(f"  ... and {len(metadata['variables']) - 3} more")

    print()
    print("=" * 80)
    print("OBJECTIVE DETAILS")
    print("=" * 80)

    # Extract objective names and directions from list of dicts
    for obj_dict in metadata['objectives']:
        obj_name = list(obj_dict.keys())[0]
        direction = obj_dict[obj_name]

        print()
        print(f"Objective: {obj_name}")
        print(f"  Direction: {direction}")

        if metadata['initial_values']:
            init_val = metadata['initial_values'].get(obj_name)
            min_val = metadata['min_values'].get(obj_name)
            max_val = metadata['max_values'].get(obj_name)
            final_val = metadata['final_values'].get(obj_name)

            print(f"  Initial: {init_val:.4f}" if init_val is not None else "  Initial: N/A")
            print(f"  Minimum: {min_val:.4f}" if min_val is not None else "  Minimum: N/A")
            print(f"  Maximum: {max_val:.4f}" if max_val is not None else "  Maximum: N/A")
            print(f"  Final:   {final_val:.4f}" if final_val is not None else "  Final: N/A")

            # Calculate improvement based on direction
            if init_val is not None and final_val is not None:
                if direction == 'MAXIMIZE':
                    # For maximization, compare final to initial
                    # Best achieved is max_val
                    improvement = ((final_val - init_val) / abs(init_val)) * 100 if init_val != 0 else 0
                    best_improvement = ((max_val - init_val) / abs(init_val)) * 100 if init_val != 0 else 0
                    print(f"  Improvement (init→final): {improvement:.1f}%")
                    print(f"  Best improvement (init→max): {best_improvement:.1f}%")
                else:  # MINIMIZE
                    # For minimization, lower is better
                    # Best achieved is min_val
                    improvement = ((init_val - final_val) / abs(init_val)) * 100 if init_val != 0 else 0
                    best_improvement = ((init_val - min_val) / abs(init_val)) * 100 if init_val != 0 else 0
                    print(f"  Improvement (init→final): {improvement:.1f}%")
                    print(f"  Best improvement (init→min): {best_improvement:.1f}%")
        else:
            print("  No objective values available")

    print()
    print("=" * 80)
    print("✅ All objective statistics extracted successfully!")
    print("=" * 80)

    return True

if __name__ == "__main__":
    success = test_objective_stats()
    sys.exit(0 if success else 1)
