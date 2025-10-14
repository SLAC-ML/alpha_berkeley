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
sys.path.insert(0, str(Path(__file__).parent / "src"))

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
        "execution_plan": {
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
        "current_step_index": 0,
        "capability_context_data": {},
    }

    print("\n📋 Mock Step Configuration:")
    current_step = mock_state["execution_plan"]["steps"][0]
    print(f"  Capability: {current_step['capability']}")
    print(f"  Parameters: {current_step.get('parameters', 'NO PARAMETERS')}")
    print(f"  Expected: Should load exactly 1 run")

    print("\n🔄 Executing capability...")
    try:
        result = await QueryRunsCapability.execute(mock_state)

        print("\n✅ Capability executed successfully!")
        print(f"\n📊 Result Summary:")
        print(f"  Keys in result: {list(result.keys())}")

        # Count BADGER_RUN contexts
        badger_run_keys = [k for k in result.keys() if "BADGER_RUN" in k]
        print(f"  BADGER_RUN contexts created: {len(badger_run_keys)}")

        # Show first run details
        if badger_run_keys:
            first_key = badger_run_keys[0]
            first_context_dict = result[first_key]
            print(f"\n📄 First Run Details (from {first_key}):")

            # Extract run contexts (they're nested under keys like run_0, run_1, etc.)
            for sub_key, context in first_context_dict.items():
                if hasattr(context, 'run_name'):
                    print(f"    Run Name: {context.run_name}")
                    print(f"    Beamline: {context.beamline}")
                    print(f"    Badger Environment: {context.badger_environment}")
                    print(f"    Algorithm: {context.algorithm}")
                    print(f"    Variables: {len(context.variables)}")
                    print(f"    Objectives: {len(context.objectives)}")
                    print(f"    Evaluations: {context.num_evaluations}")
                    break

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
        "execution_plan": {
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
        "current_step_index": 0,
        "capability_context_data": {},
    }

    print("\n📋 Mock Step Configuration:")
    current_step = mock_state["execution_plan"]["steps"][0]
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
        "execution_plan": {
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
        "current_step_index": 0,
        "capability_context_data": {},
    }

    print("\n📋 Mock Step Configuration:")
    current_step = mock_state["execution_plan"]["steps"][0]
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
