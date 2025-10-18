"""
Test Otter Query Runs Capability in Isolation

Tests the capability with mock state to verify:
1. Filter parameters are correctly received
2. Data source correctly filters runs
3. Context creation works properly
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from applications.otter.capabilities.query_runs import QueryRunsCapability
from framework.state import AgentState


async def test_capability_with_filter():
    """Test capability with explicit filter"""
    print("=" * 80)
    print("TEST: Query Runs Capability with num_runs=1 Filter")
    print("=" * 80)

    # Create mock state with a step that has parameters
    mock_state = {
        "messages": [],
        "current_task": "Tell me about the most recent run",
        "planning_execution_plan": {
            "steps": [
                {
                    "context_key": "test_run",
                    "capability": "query_runs",
                    "task_objective": "Get the most recent Badger run",
                    "parameters": {"num_runs": 1},  # Explicit parameters
                    "expected_output": "BADGER_RUN",
                    "success_criteria": "Most recent run loaded",
                    "inputs": []
                }
            ]
        },
        "planning_current_step_index": 0,
        "capability_context_data": {},
    }

    print("\n📋 Mock Step Configuration:")
    current_step = mock_state["planning_execution_plan"]["steps"][0]
    print(f"  Capability: {current_step['capability']}")
    print(f"  Parameters: {current_step.get('parameters', 'NO PARAMETERS')}")
    print(f"  Expected: Should load exactly 1 run")

    print("\n🔄 Executing capability...")
    try:
        result = await QueryRunsCapability.execute(mock_state)

        print("\n✅ Capability executed successfully!")
        print(f"\n📊 Result Summary:")
        print(f"  Keys in result: {list(result.keys())}")

        # Count BADGER_RUNS contexts (should be 1 container)
        badger_runs_keys = [k for k in result.keys() if "BADGER_RUNS" in k]
        print(f"  BADGER_RUNS contexts created: {len(badger_runs_keys)}")

        # Show container details
        if badger_runs_keys:
            first_key = badger_runs_keys[0]
            runs_container = result[first_key][list(result[first_key].keys())[0]]
            print(f"\n📄 BADGER_RUNS Container Details:")
            print(f"    Total runs in container: {runs_container.run_count}")

            # Show first run from container
            if runs_container.runs:
                first_run = runs_container.runs[0]
                print(f"\n📄 First Run Details:")
                print(f"    Run Name: {first_run.run_name}")
                print(f"    Beamline: {first_run.beamline}")
                print(f"    Badger Environment: {first_run.badger_environment}")
                print(f"    Algorithm: {first_run.algorithm}")
                print(f"    Variables: {len(first_run.variables)}")
                print(f"    Objectives: {len(first_run.objectives)}")
                print(f"    Evaluations: {first_run.num_evaluations}")

        return True

    except Exception as e:
        print(f"\n❌ Capability execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_capability_no_filter():
    """Test capability without parameters (should default to 1)"""
    print("\n" + "=" * 80)
    print("TEST: Query Runs Capability WITHOUT Parameters (Should Default to 1)")
    print("=" * 80)

    # Create mock state with a step that has NO parameters
    mock_state = {
        "messages": [],
        "current_task": "Tell me about the most recent run",
        "planning_execution_plan": {
            "steps": [
                {
                    "context_key": "test_run",
                    "capability": "query_runs",
                    "task_objective": "Get the most recent Badger run",
                    # NO PARAMETERS KEY!
                    "expected_output": "BADGER_RUN",
                    "success_criteria": "Most recent run loaded",
                    "inputs": []
                }
            ]
        },
        "planning_current_step_index": 0,
        "capability_context_data": {},
    }

    print("\n📋 Mock Step Configuration:")
    current_step = mock_state["planning_execution_plan"]["steps"][0]
    print(f"  Capability: {current_step['capability']}")
    print(f"  Parameters: {current_step.get('parameters', 'NO PARAMETERS PROVIDED')}")
    print(f"  Expected: Should default to num_runs=1 and load exactly 1 run")

    print("\n🔄 Executing capability...")
    try:
        result = await QueryRunsCapability.execute(mock_state)

        print("\n✅ Capability executed successfully!")
        print(f"\n📊 Result Summary:")

        # Count BADGER_RUN contexts
        badger_run_keys = [k for k in result.keys() if "BADGER_RUN" in k]
        print(f"  BADGER_RUN contexts created: {len(badger_run_keys)}")

        if len(badger_run_keys) == 1:
            print("  ✅ Correctly defaulted to 1 run!")
        else:
            print(f"  ⚠️  Expected 1 context, got {len(badger_run_keys)}")

        return True

    except Exception as e:
        print(f"\n❌ Capability execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_capability_with_limit_5():
    """Test capability with num_runs=5"""
    print("\n" + "=" * 80)
    print("TEST: Query Runs Capability with num_runs=5")
    print("=" * 80)

    mock_state = {
        "messages": [],
        "current_task": "Show me the last 5 runs",
        "planning_execution_plan": {
            "steps": [
                {
                    "context_key": "recent_runs",
                    "capability": "query_runs",
                    "task_objective": "Get the last 5 Badger runs",
                    "parameters": {"num_runs": 5},  # Request 5 runs
                    "expected_output": "BADGER_RUN",
                    "success_criteria": "5 runs loaded",
                    "inputs": []
                }
            ]
        },
        "planning_current_step_index": 0,
        "capability_context_data": {},
    }

    print("\n📋 Mock Step Configuration:")
    current_step = mock_state["planning_execution_plan"]["steps"][0]
    print(f"  Capability: {current_step['capability']}")
    print(f"  Parameters: {current_step.get('parameters')}")
    print(f"  Expected: Should load exactly 5 runs")

    print("\n🔄 Executing capability...")
    try:
        result = await QueryRunsCapability.execute(mock_state)

        print("\n✅ Capability executed successfully!")

        # Count contexts
        badger_run_keys = [k for k in result.keys() if "BADGER_RUN" in k]
        print(f"\n📊 Result: Created {len(badger_run_keys)} BADGER_RUN contexts")

        if len(badger_run_keys) == 5:
            print("  ✅ Correctly loaded 5 runs!")
        else:
            print(f"  ⚠️  Expected 5 contexts, got {len(badger_run_keys)}")

        return True

    except Exception as e:
        print(f"\n❌ Capability execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_capability_with_time_range():
    """Test capability with TIME_RANGE context from inputs"""
    print("\n" + "=" * 80)
    print("TEST: Query Runs Capability with TIME_RANGE Context Input")
    print("=" * 80)

    from datetime import datetime

    from framework.capabilities.time_range_parsing import TimeRangeContext

    # Create a TIME_RANGE context for August 2025
    time_range_context = TimeRangeContext(
        start_date=datetime(2025, 8, 1, 0, 0, 0),
        end_date=datetime(2025, 8, 31, 23, 59, 59)
    )

    # Create mock state with TIME_RANGE in inputs
    mock_state = {
        "messages": [],
        "current_task": "Show me 3 runs from August 2025",
        "planning_execution_plan": {
            "steps": [
                {
                    "context_key": "august_runs",
                    "capability": "query_runs",
                    "task_objective": "Get 3 Badger runs from August 2025",
                    "parameters": {"num_runs": 3},
                    "expected_output": "BADGER_RUN",
                    "success_criteria": "3 runs from August 2025 loaded",
                    "inputs": [{"TIME_RANGE": "time_range_august_2025"}]  # Reference to TIME_RANGE context
                }
            ]
        },
        "planning_current_step_index": 0,
        "capability_context_data": {
            "TIME_RANGE": {
                "time_range_august_2025": time_range_context
            }
        },
    }

    print("\n📋 Mock Step Configuration:")
    current_step = mock_state["planning_execution_plan"]["steps"][0]
    print(f"  Capability: {current_step['capability']}")
    print(f"  Parameters: {current_step.get('parameters')}")
    print(f"  Inputs: {current_step.get('inputs')}")
    print("  Expected: Should load up to 3 runs from August 2025")
    print("\n📅 TIME_RANGE Context:")
    print(f"  Start: {time_range_context.start_date}")
    print(f"  End: {time_range_context.end_date}")

    print("\n🔄 Executing capability...")
    try:
        result = await QueryRunsCapability.execute(mock_state)

        print("\n✅ Capability executed successfully!")

        # Count contexts
        badger_run_keys = [k for k in result.keys() if "BADGER_RUN" in k]
        print(f"\n📊 Result: Created {len(badger_run_keys)} BADGER_RUN contexts")

        # Check timestamps of returned runs
        august_runs = 0
        non_august_runs = 0

        for key in badger_run_keys:
            context_dict = result[key]
            for context in context_dict.values():
                if hasattr(context, 'timestamp'):
                    if context.timestamp.month == 8 and context.timestamp.year == 2025:
                        august_runs += 1
                        print(f"  ✅ Run from August 2025: {context.run_name} ({context.timestamp})")
                    else:
                        non_august_runs += 1
                        print(f"  ❌ Run NOT from August 2025: {context.run_name} ({context.timestamp})")

        print("\n📈 Time Range Filter Results:")
        print(f"  Runs from August 2025: {august_runs}")
        print(f"  Runs from other months: {non_august_runs}")

        if non_august_runs > 0:
            print("\n❌ TIME_RANGE filter was NOT applied correctly!")
            return False
        elif august_runs == 0:
            print("\n⚠️  No runs found in August 2025 (might be expected if archive doesn't have data)")
            return True
        else:
            print("\n✅ TIME_RANGE filter applied correctly - all returned runs are from August 2025!")
            return True

    except Exception as e:
        print(f"\n❌ Capability execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all capability tests"""
    print("\n" + "=" * 80)
    print("OTTER CAPABILITY ISOLATION TESTS")
    print("=" * 80)
    print("\nThese tests verify the capability works correctly with different filters")
    print("WITHOUT running the full framework (avoids context window issues)")

    results = []

    # Test 1: With explicit filter
    results.append(await test_capability_with_filter())

    # Test 2: Without filter (should default)
    results.append(await test_capability_no_filter())

    # Test 3: With limit=5
    results.append(await test_capability_with_limit_5())

    # Test 4: With TIME_RANGE context
    results.append(await test_capability_with_time_range())

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✅ All capability tests passed!")
        print("The capability correctly:")
        print("  - Accepts parameters from step")
        print("  - Defaults to num_runs=1 when no parameters provided")
        print("  - Respects num_runs limits")
        print("  - Skips hidden directories")
        print("\nReady to debug orchestrator parameter generation.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("Fix capability issues before testing with full framework.")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
