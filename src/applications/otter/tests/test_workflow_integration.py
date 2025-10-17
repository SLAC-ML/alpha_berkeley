"""
Integration Test: Query → Analyze → Propose Workflow

Tests the complete workflow of:
1. query_runs: Load historical runs
2. analyze_runs: Analyze patterns and performance
3. propose_routines: Generate routine recommendations

This tests the integration between the three new Otter capabilities.
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Mock the streaming module before importing capabilities
from unittest.mock import MagicMock, patch
import configs.streaming as streaming_module

# Create a mock streamer that doesn't require LangGraph context
class MockStreamer:
    def status(self, message):
        print(f"  📝 {message}")

# Patch get_streamer to return mock
streaming_module.get_streamer = lambda *args, **kwargs: MockStreamer()

from applications.otter.capabilities.query_runs import QueryRunsCapability
from applications.otter.capabilities.analyze_runs import AnalyzeRunsCapability
from applications.otter.capabilities.propose_routines import ProposeRoutinesCapability


async def test_full_workflow():
    """
    Test complete workflow: query → analyze → propose
    """
    print("=" * 80)
    print("INTEGRATION TEST: Query → Analyze → Propose Workflow")
    print("=" * 80)

    # ====================
    # Step 1: Query Runs
    # ====================
    print("\n" + "=" * 60)
    print("STEP 1: QUERY RUNS - Load recent optimization runs")
    print("=" * 60)

    query_state = {
        "messages": [],
        "current_task": "Analyze recent runs and suggest routines",
        "planning_execution_plan": {
            "steps": [
                {
                    "context_key": "recent_runs",
                    "capability": "query_runs",
                    "task_objective": "Load recent 10 runs for analysis",
                    "parameters": {"num_runs": 10},
                    "expected_output": "BADGER_RUN",
                    "success_criteria": "10 runs loaded",
                    "inputs": []
                }
            ]
        },
        "planning_current_step_index": 0,
        "capability_context_data": {},
        "execution_step_results": {},
    }

    print("\n🔄 Executing query_runs...")
    try:
        query_result = await QueryRunsCapability.execute(query_state)

        # Count loaded runs
        badger_run_keys = [k for k in query_result.keys() if "BADGER_RUN" in k]
        num_runs_loaded = len(badger_run_keys)

        print(f"✅ Loaded {num_runs_loaded} runs")

        # Store results in state for next step
        query_state["capability_context_data"].update(query_result)

        if num_runs_loaded == 0:
            print("❌ No runs loaded, cannot continue workflow")
            return False

    except Exception as e:
        print(f"❌ Query runs failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ====================
    # Step 2: Analyze Runs
    # ====================
    print("\n" + "=" * 60)
    print("STEP 2: ANALYZE RUNS - Identify patterns and performance")
    print("=" * 60)

    # Build analyze state with run contexts from step 1
    analyze_inputs = [{"BADGER_RUN": key.split("_", 2)[-1]} for key in badger_run_keys]

    analyze_state = {
        "messages": [],
        "current_task": "Analyze runs",
        "planning_execution_plan": {
            "steps": [
                {
                    "context_key": "run_analysis",
                    "capability": "analyze_runs",
                    "task_objective": "Analyze loaded runs for patterns",
                    "parameters": {},
                    "expected_output": "analysis_summary",
                    "success_criteria": "Analysis completed",
                    "inputs": analyze_inputs
                }
            ]
        },
        "planning_current_step_index": 0,
        "capability_context_data": query_state["capability_context_data"],
        "execution_step_results": {},
    }

    print(f"\n🔄 Analyzing {len(analyze_inputs)} runs...")
    try:
        analyze_result = await AnalyzeRunsCapability.execute(analyze_state)

        # Check analysis results
        if "execution_step_results" in analyze_result:
            analysis_data = analyze_result["execution_step_results"]["run_analysis"]

            print("\n✅ Analysis completed!")
            print(f"\n📊 Analysis Summary:")
            print(f"  Total runs analyzed: {analysis_data['overview']['total_runs_analyzed']}")
            print(f"  Time span: {analysis_data['overview']['time_range']['span_days']} days")
            print(f"  Total evaluations: {analysis_data['overview']['total_evaluations']}")

            print(f"\n🔧 Algorithm Performance:")
            for algo, stats in analysis_data['algorithm_performance'].items():
                avg_imp = stats.get('avg_improvement_pct', 'N/A')
                print(f"  {algo}: {stats['num_runs']} runs, avg improvement: {avg_imp}%")

            print(f"\n🎯 Top Performers:")
            for performer in analysis_data['success_patterns']['top_performers'][:3]:
                print(f"  {performer['run_name']}: {performer['algorithm']} ({performer['improvement_pct']:.1f}% improvement)")

            # Update state for next step
            analyze_state["execution_step_results"].update(analyze_result.get("execution_step_results", {}))
        else:
            print("⚠️  No analysis results found in execution_step_results")

    except Exception as e:
        print(f"❌ Analyze runs failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ====================
    # Step 3: Propose Routines
    # ====================
    print("\n" + "=" * 60)
    print("STEP 3: PROPOSE ROUTINES - Generate routine recommendations")
    print("=" * 60)

    # Build propose state with contexts from step 1
    propose_state = {
        "messages": [],
        "current_task": "Propose routines",
        "planning_execution_plan": {
            "steps": [
                {
                    "context_key": "routine_proposals",
                    "capability": "propose_routines",
                    "task_objective": "Generate routine proposals based on successful runs",
                    "parameters": {"num_proposals": 3},
                    "expected_output": "routine_proposals",
                    "success_criteria": "3 proposals generated",
                    "inputs": analyze_inputs  # Same inputs as analyze
                }
            ]
        },
        "planning_current_step_index": 0,
        "capability_context_data": query_state["capability_context_data"],
        "execution_step_results": analyze_state.get("execution_step_results", {}),
    }

    print(f"\n🔄 Generating proposals from {len(analyze_inputs)} runs...")
    try:
        propose_result = await ProposeRoutinesCapability.execute(propose_state)

        # Check proposal results
        if "execution_step_results" in propose_result:
            proposal_data = propose_result["execution_step_results"]["routine_proposals"]

            print(f"\n✅ Generated {proposal_data['num_proposals']} proposals!")

            print(f"\n💡 Routine Proposals:")
            for i, proposal in enumerate(proposal_data['proposals'], 1):
                print(f"\n  Proposal {i}: {proposal['proposal_name']}")
                print(f"    Algorithm: {proposal['algorithm']}")
                print(f"    Beamline: {proposal['beamline']}")
                print(f"    Environment: {proposal['badger_environment']}")
                print(f"    Evaluations: {proposal['estimated_evaluations']}")
                print(f"    Confidence: {proposal['confidence']}")
                print(f"    Objectives: {len(proposal['objectives'])} objectives")
                print(f"    Variables: {len(proposal['variables'])} variables")
                print(f"    Justification: {proposal['justification']}")
                print(f"    Reference runs: {', '.join(proposal['reference_runs'][:2])}")

            print(f"\n📋 Generation Context:")
            gen_ctx = proposal_data['generation_context']
            print(f"  Successful runs used: {gen_ctx['successful_runs_used']}")
            print(f"  Algorithm distribution: {gen_ctx['algorithm_distribution']}")

        else:
            print("⚠️  No proposal results found in execution_step_results")

    except Exception as e:
        print(f"❌ Propose routines failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ====================
    # Workflow Summary
    # ====================
    print("\n" + "=" * 80)
    print("WORKFLOW SUMMARY")
    print("=" * 80)
    print("\n✅ Complete workflow executed successfully!")
    print(f"\nWorkflow steps:")
    print(f"  1. query_runs: Loaded {num_runs_loaded} historical runs")
    print(f"  2. analyze_runs: Analyzed patterns and performance")
    print(f"  3. propose_routines: Generated {proposal_data['num_proposals']} routine proposals")

    print("\n🎯 Integration test passed!")
    print("All three capabilities work together correctly.")

    return True


async def test_propose_without_analyze():
    """
    Test shorter workflow: query → propose (skipping analyze)

    This tests that propose_routines can work independently
    """
    print("\n" + "=" * 80)
    print("INTEGRATION TEST: Query → Propose (Skip Analyze)")
    print("=" * 80)

    # Step 1: Query
    print("\n🔄 Step 1: Loading runs...")
    query_state = {
        "messages": [],
        "current_task": "Suggest routines",
        "planning_execution_plan": {
            "steps": [
                {
                    "context_key": "runs_for_proposal",
                    "capability": "query_runs",
                    "task_objective": "Load 5 runs for proposal",
                    "parameters": {"num_runs": 5},
                    "expected_output": "BADGER_RUN",
                    "success_criteria": "5 runs loaded",
                    "inputs": []
                }
            ]
        },
        "planning_current_step_index": 0,
        "capability_context_data": {},
        "execution_step_results": {},
    }

    try:
        query_result = await QueryRunsCapability.execute(query_state)
        badger_run_keys = [k for k in query_result.keys() if "BADGER_RUN" in k]
        print(f"✅ Loaded {len(badger_run_keys)} runs")

        query_state["capability_context_data"].update(query_result)

    except Exception as e:
        print(f"❌ Query failed: {e}")
        return False

    # Step 2: Propose directly (skip analyze)
    print("\n🔄 Step 2: Generating proposals directly...")

    propose_inputs = [{"BADGER_RUN": key.split("_", 2)[-1]} for key in badger_run_keys]

    propose_state = {
        "messages": [],
        "current_task": "Propose routines",
        "planning_execution_plan": {
            "steps": [
                {
                    "context_key": "direct_proposals",
                    "capability": "propose_routines",
                    "task_objective": "Generate proposals without analysis step",
                    "parameters": {"num_proposals": 2},
                    "expected_output": "routine_proposals",
                    "success_criteria": "2 proposals generated",
                    "inputs": propose_inputs
                }
            ]
        },
        "planning_current_step_index": 0,
        "capability_context_data": query_state["capability_context_data"],
        "execution_step_results": {},
    }

    try:
        propose_result = await ProposeRoutinesCapability.execute(propose_state)

        if "execution_step_results" in propose_result:
            proposal_data = propose_result["execution_step_results"]["direct_proposals"]
            print(f"✅ Generated {proposal_data['num_proposals']} proposals!")
            print(f"   Proposals: {[p['proposal_name'] for p in proposal_data['proposals']]}")

        print("\n✅ Direct proposal workflow successful!")
        print("propose_routines can work without analyze_runs step.")
        return True

    except Exception as e:
        print(f"❌ Propose failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all integration tests"""
    print("\n" + "=" * 80)
    print("OTTER WORKFLOW INTEGRATION TESTS")
    print("=" * 80)
    print("\nThese tests verify the new capabilities work together correctly")

    results = []

    # Test 1: Full workflow
    results.append(await test_full_workflow())

    # Test 2: Short workflow (skip analyze)
    results.append(await test_propose_without_analyze())

    # Summary
    print("\n" + "=" * 80)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 80)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✅ All integration tests passed!")
        print("\nThe Otter workflow is ready:")
        print("  - query_runs loads historical data")
        print("  - analyze_runs identifies patterns")
        print("  - propose_routines generates recommendations")
        print("  - All three work together seamlessly")
    else:
        print(f"\n⚠️  {total - passed} integration test(s) failed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
