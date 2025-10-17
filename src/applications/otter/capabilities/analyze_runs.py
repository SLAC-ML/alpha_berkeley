"""
Analyze Runs Capability

Capability for analyzing and comparing multiple Badger optimization runs.
Performs statistical analysis, trend detection, and pattern identification across runs.
"""

import logging
import textwrap
from typing import Dict, Any, Optional, List
from collections import defaultdict, Counter
from statistics import mean, median, stdev
from datetime import datetime, timedelta

# Framework imports
from framework.base.decorators import capability_node
from framework.base.capability import BaseCapability
from framework.base.errors import ErrorClassification, ErrorSeverity
from framework.base.examples import (
    OrchestratorGuide, OrchestratorExample,
    TaskClassifierGuide, ClassifierExample, ClassifierActions
)
from framework.base.planning import PlannedStep
from framework.state import AgentState, StateManager
from framework.registry import get_registry
from framework.context.context_manager import ContextManager
from configs.logger import get_logger
from configs.streaming import get_streamer
from configs.config import get_config_value

# Application imports
from applications.otter.context_classes import BadgerRunContext

logger = get_logger("otter", "analyze_runs")
registry = get_registry()


# ====================
# Custom Exceptions
# ====================

class AnalyzeRunsError(Exception):
    """Base class for analyze runs errors."""
    pass


class InsufficientDataError(AnalyzeRunsError):
    """Raised when not enough runs provided for analysis."""
    pass


# ====================
# Capability Definition
# ====================

@capability_node
class AnalyzeRunsCapability(BaseCapability):
    """
    Analyze and compare multiple Badger optimization runs.

    This capability takes multiple BADGER_RUN contexts as input and performs:
    - Statistical analysis (mean, median, variance of success metrics)
    - Algorithm performance comparison
    - Temporal trend detection
    - Common pattern identification
    - Success factor analysis

    Returns a structured analysis summary for downstream use or user presentation.
    """

    name = "analyze_runs"
    description = "Analyze and compare multiple Badger optimization runs"
    provides = ["RUN_ANALYSIS"]
    requires = ["BADGER_RUN"]

    @staticmethod
    async def execute(state: AgentState, **kwargs) -> Dict[str, Any]:
        """Execute run analysis."""

        step = StateManager.get_current_step(state)
        streamer = get_streamer("otter", "analyze_runs", state)

        try:
            # Get context manager to retrieve run contexts
            context_manager = ContextManager(state)

            # Extract BADGER_RUN contexts from inputs
            step_inputs = step.get("inputs", [])
            if not step_inputs:
                raise InsufficientDataError("No run contexts provided for analysis")

            # Collect all BADGER_RUN contexts
            run_contexts: List[BadgerRunContext] = []
            for input_item in step_inputs:
                if "BADGER_RUN" in input_item:
                    run_key = input_item["BADGER_RUN"]
                    run_context = context_manager.get_context(
                        registry.context_types.BADGER_RUN,
                        run_key
                    )
                    if run_context:
                        run_contexts.append(run_context)

            if not run_contexts:
                raise InsufficientDataError("No valid BADGER_RUN contexts found in inputs")

            streamer.status(f"Analyzing {len(run_contexts)} runs...")

            # ====================
            # Analysis Section 1: Overview Statistics
            # ====================
            streamer.status("Computing overview statistics...")

            total_runs = len(run_contexts)
            total_evaluations = sum(run.num_evaluations for run in run_contexts)
            avg_evaluations = total_evaluations / total_runs if total_runs > 0 else 0

            # Time range
            timestamps = [run.timestamp for run in run_contexts]
            earliest_run = min(timestamps)
            latest_run = max(timestamps)
            time_span = (latest_run - earliest_run).total_seconds() / 86400  # days

            # ====================
            # Analysis Section 2: Algorithm Performance
            # ====================
            streamer.status("Analyzing algorithm performance...")

            algorithm_stats = defaultdict(lambda: {
                "count": 0,
                "total_evaluations": 0,
                "improvements": [],
                "runs": []
            })

            for run in run_contexts:
                algo = run.algorithm
                stats = algorithm_stats[algo]
                stats["count"] += 1
                stats["total_evaluations"] += run.num_evaluations
                stats["runs"].append(run.run_name)

                # Calculate improvement if available
                if run.initial_objective_values and run.final_objective_values:
                    for obj_name in run._get_objective_names():
                        if obj_name in run.initial_objective_values and obj_name in run.final_objective_values:
                            initial = run.initial_objective_values[obj_name]
                            final = run.final_objective_values[obj_name]
                            direction = run._get_objective_direction(obj_name)

                            if initial != 0:
                                if direction == 'MAXIMIZE':
                                    improvement = ((final - initial) / abs(initial)) * 100
                                else:  # MINIMIZE
                                    improvement = ((initial - final) / abs(initial)) * 100
                                stats["improvements"].append(improvement)

            # Compute algorithm summary
            algorithm_summary = {}
            for algo, stats in algorithm_stats.items():
                summary = {
                    "num_runs": stats["count"],
                    "total_evaluations": stats["total_evaluations"],
                    "avg_evaluations_per_run": stats["total_evaluations"] / stats["count"],
                    "run_names": stats["runs"]
                }

                if stats["improvements"]:
                    summary["avg_improvement_pct"] = mean(stats["improvements"])
                    summary["median_improvement_pct"] = median(stats["improvements"])
                    if len(stats["improvements"]) > 1:
                        summary["stdev_improvement_pct"] = stdev(stats["improvements"])

                algorithm_summary[algo] = summary

            # ====================
            # Analysis Section 3: Beamline Distribution
            # ====================
            streamer.status("Analyzing beamline distribution...")

            beamline_counts = Counter(run.beamline for run in run_contexts)
            badger_env_counts = Counter(run.badger_environment for run in run_contexts)

            # ====================
            # Analysis Section 4: Objectives Analysis
            # ====================
            streamer.status("Analyzing objectives...")

            objective_stats = defaultdict(lambda: {
                "count": 0,
                "directions": Counter(),
                "improvements": []
            })

            for run in run_contexts:
                for obj_dict in run.objectives:
                    obj_name = list(obj_dict.keys())[0]
                    obj_direction = obj_dict[obj_name]

                    objective_stats[obj_name]["count"] += 1
                    objective_stats[obj_name]["directions"][obj_direction] += 1

                    # Collect improvement if available
                    if run.initial_objective_values and run.final_objective_values:
                        if obj_name in run.initial_objective_values and obj_name in run.final_objective_values:
                            initial = run.initial_objective_values[obj_name]
                            final = run.final_objective_values[obj_name]

                            if initial != 0:
                                if obj_direction == 'MAXIMIZE':
                                    improvement = ((final - initial) / abs(initial)) * 100
                                else:
                                    improvement = ((initial - final) / abs(initial)) * 100
                                objective_stats[obj_name]["improvements"].append(improvement)

            # Compute objective summary
            objective_summary = {}
            for obj_name, stats in objective_stats.items():
                summary = {
                    "num_runs": stats["count"],
                    "direction": stats["directions"].most_common(1)[0][0]
                }

                if stats["improvements"]:
                    summary["avg_improvement_pct"] = mean(stats["improvements"])
                    summary["median_improvement_pct"] = median(stats["improvements"])
                    if len(stats["improvements"]) > 1:
                        summary["stdev_improvement_pct"] = stdev(stats["improvements"])

                objective_summary[obj_name] = summary

            # ====================
            # Analysis Section 5: Success Patterns
            # ====================
            streamer.status("Identifying success patterns...")

            # Identify most successful runs (top 20% by improvement)
            runs_with_improvement = []
            for run in run_contexts:
                if run.initial_objective_values and run.final_objective_values:
                    improvements = []
                    for obj_name in run._get_objective_names():
                        if obj_name in run.initial_objective_values and obj_name in run.final_objective_values:
                            initial = run.initial_objective_values[obj_name]
                            final = run.final_objective_values[obj_name]
                            direction = run._get_objective_direction(obj_name)

                            if initial != 0:
                                if direction == 'MAXIMIZE':
                                    improvement = ((final - initial) / abs(initial)) * 100
                                else:
                                    improvement = ((initial - final) / abs(initial)) * 100
                                improvements.append(improvement)

                    if improvements:
                        avg_improvement = mean(improvements)
                        runs_with_improvement.append((run, avg_improvement))

            # Sort by improvement
            runs_with_improvement.sort(key=lambda x: x[1], reverse=True)

            # Top performers
            top_n = max(1, len(runs_with_improvement) // 5)  # Top 20%
            top_performers = runs_with_improvement[:top_n]

            success_patterns = {
                "top_algorithms": Counter(run.algorithm for run, _ in top_performers),
                "top_beamlines": Counter(run.beamline for run, _ in top_performers),
                "top_performers": [
                    {
                        "run_name": run.run_name,
                        "algorithm": run.algorithm,
                        "beamline": run.beamline,
                        "improvement_pct": improvement
                    }
                    for run, improvement in top_performers
                ]
            }

            # ====================
            # Build Final Analysis Summary
            # ====================
            streamer.status("Compiling analysis results...")

            analysis_result = {
                "overview": {
                    "total_runs_analyzed": total_runs,
                    "time_range": {
                        "earliest": earliest_run.isoformat(),
                        "latest": latest_run.isoformat(),
                        "span_days": round(time_span, 1)
                    },
                    "total_evaluations": total_evaluations,
                    "avg_evaluations_per_run": round(avg_evaluations, 1)
                },
                "algorithm_performance": dict(algorithm_summary),
                "beamline_distribution": dict(beamline_counts),
                "badger_environment_distribution": dict(badger_env_counts),
                "objective_analysis": dict(objective_summary),
                "success_patterns": {
                    "top_algorithms": dict(success_patterns["top_algorithms"]),
                    "top_beamlines": dict(success_patterns["top_beamlines"]),
                    "top_performers": success_patterns["top_performers"][:5]  # Limit to top 5
                }
            }

            streamer.status(f"Analysis complete! Analyzed {total_runs} runs.")
            logger.success(f"Successfully analyzed {total_runs} runs")

            # Create RunAnalysisContext and store it
            from applications.otter.context_classes import RunAnalysisContext

            analysis_context = RunAnalysisContext(
                analysis_data=analysis_result
            )

            # Store context and return updates
            context_key = step.get("context_key", "run_analysis")
            return StateManager.store_context(
                state,
                registry.context_types.RUN_ANALYSIS,
                context_key,
                analysis_context
            )

        except InsufficientDataError as e:
            logger.error(f"Insufficient data for analysis: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error in analyze_runs: {e}")
            raise

    @staticmethod
    def classify_error(exc: Exception, context: dict) -> ErrorClassification:
        """
        Error classification for analyze runs capability.
        """

        if isinstance(exc, InsufficientDataError):
            return ErrorClassification(
                severity=ErrorSeverity.CRITICAL,
                user_message=f"Cannot perform analysis: {str(exc)}",
                metadata={
                    "technical_details": str(exc),
                    "resolution": "Ensure at least one BADGER_RUN context is provided as input"
                }
            )

        else:
            # Unknown error - default to retriable
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message=f"Analysis error: {str(exc)}",
                metadata={"technical_details": str(exc)}
            )

    def _create_orchestrator_guide(self) -> Optional[OrchestratorGuide]:
        """
        Create comprehensive guide for orchestrator to plan run analysis.
        """

        # Example 1: Analyze recent runs
        simple_analysis_example = OrchestratorExample(
            step=PlannedStep(
                context_key="recent_runs_analysis",
                capability="analyze_runs",
                task_objective="Analyze the most recent 5 runs to identify patterns",
                expected_output="analysis_summary",
                success_criteria="Statistical analysis of runs completed",
                inputs=[
                    {"BADGER_RUN": "run_0"},
                    {"BADGER_RUN": "run_1"},
                    {"BADGER_RUN": "run_2"},
                    {"BADGER_RUN": "run_3"},
                    {"BADGER_RUN": "run_4"}
                ],
                parameters={}
            ),
            scenario_description="User wants to understand patterns in recent runs",
            notes="Provide all BADGER_RUN contexts from previous query_runs step as inputs. "
                  "Analysis will compare algorithms, objectives, and success rates."
        )

        # Example 2: Algorithm comparison workflow (2-step)
        algorithm_comparison_example = OrchestratorExample(
            step=PlannedStep(
                context_key="algorithm_comparison",
                capability="analyze_runs",
                task_objective="Compare algorithm performance across different beamlines",
                expected_output="analysis_summary",
                success_criteria="Algorithm performance metrics calculated",
                inputs=[
                    {"BADGER_RUN": "neldermead_runs"},  # From step 1
                ],
                parameters={}
            ),
            scenario_description="User asks 'Which algorithm performed best?' - requires 2 steps:\n"
                                "Step 1: query_runs to load all runs\n"
                                "Step 2: analyze_runs with those contexts to compare algorithms",
            notes="IMPORTANT: analyze_runs requires BADGER_RUN contexts as input. "
                  "It cannot query runs itself - use query_runs first!"
        )

        # Example 3: Trend analysis
        trend_analysis_example = OrchestratorExample(
            step=PlannedStep(
                context_key="monthly_trend_analysis",
                capability="analyze_runs",
                task_objective="Analyze optimization trends over the past month",
                expected_output="analysis_summary",
                success_criteria="Temporal trends and success patterns identified",
                inputs=[
                    {"BADGER_RUN": "monthly_runs"}  # From query_runs with time filter
                ],
                parameters={}
            ),
            scenario_description="User wants to see how optimization performance changed over time",
            notes="Use query_runs with time_range filter first, then analyze_runs"
        )

        return OrchestratorGuide(
            instructions=textwrap.dedent(f"""
                **When to plan "analyze_runs" steps:**
                - User asks for comparison across multiple runs (algorithms, objectives, beamlines)
                - User wants statistics or trends from historical data
                - User needs success patterns or best practices identification
                - User asks questions like "which algorithm is best?", "what patterns do you see?"

                **CRITICAL: This capability REQUIRES input from query_runs!**
                analyze_runs cannot query runs itself. It only processes BADGER_RUN contexts.

                **Typical workflow (2 steps):**
                Step 1: query_runs - Load runs from archive (creates contexts: run_0, run_1, run_2, ...)
                Step 2: analyze_runs - Analyze those contexts (inputs=[{{"BADGER_RUN": "run_0"}}, {{"BADGER_RUN": "run_1"}}, ...])

                **CRITICAL: Input Requirements:**
                - Requires at least ONE BADGER_RUN context in inputs array
                - Can process any number of BADGER_RUN contexts (1 to hundreds)
                - Each input should be: {{"BADGER_RUN": "context_key"}}
                - query_runs creates contexts with keys: run_0, run_1, run_2, run_3, ... (sequential numbering)
                - You MUST include ALL run contexts from query_runs in the inputs array!

                **How to construct inputs array:**
                - If query_runs loaded 3 runs → inputs=[{{"BADGER_RUN": "run_0"}}, {{"BADGER_RUN": "run_1"}}, {{"BADGER_RUN": "run_2"}}]
                - If query_runs loaded 5 runs → inputs=[{{"BADGER_RUN": "run_0"}}, {{"BADGER_RUN": "run_1"}}, {{"BADGER_RUN": "run_2"}}, {{"BADGER_RUN": "run_3"}}, {{"BADGER_RUN": "run_4"}}]
                - If query_runs loaded 10 runs → inputs=[{{"BADGER_RUN": "run_0"}}, {{"BADGER_RUN": "run_1"}}, ..., {{"BADGER_RUN": "run_9"}}]
                - Pattern: run_0 through run_N-1 where N is the number of runs loaded by query_runs

                **Analysis Provided:**
                - Overview statistics (total runs, time range, evaluations)
                - Algorithm performance comparison (success rate, avg improvement)
                - Beamline distribution
                - Objective analysis (most common, success rates)
                - Success patterns (top performers, common factors)

                **Output Format:**
                - Creates RUN_ANALYSIS context for downstream use
                - Available to respond capability for user presentation
                - Available to propose_routines capability for proposal generation
                - Contains quantitative metrics (means, medians, counts)

                **Example User Query → Plan:**

                "Compare algorithms used in the last 10 runs"
                → Step 1: query_runs with parameters={{"num_runs": 10}}
                   (creates: run_0, run_1, run_2, ..., run_9)
                → Step 2: analyze_runs with inputs=[{{"BADGER_RUN": "run_0"}}, {{"BADGER_RUN": "run_1"}}, ..., {{"BADGER_RUN": "run_9"}}]
                → Step 3: respond to present analysis results

                "Analyze runs and suggest a routine"
                → Step 1: query_runs with parameters={{"num_runs": 10}}
                   (creates: run_0, run_1, ..., run_9)
                → Step 2: analyze_runs with inputs=[{{"BADGER_RUN": "run_0"}}, ..., {{"BADGER_RUN": "run_9"}}]
                   (creates RUN_ANALYSIS context)
                → Step 3: propose_routines with inputs=[{{"RUN_ANALYSIS": "run_analysis"}}]
                → Step 4: respond to present analysis + proposals

                "Analyze the last 3 runs from lcls_ii environment"
                → Step 1: extract_run_filters
                   (creates RUN_QUERY_FILTERS)
                → Step 2: query_runs with inputs=[{{"RUN_QUERY_FILTERS": "filters"}}]
                   (creates: run_0, run_1, run_2)
                → Step 3: analyze_runs with inputs=[{{"BADGER_RUN": "run_0"}}, {{"BADGER_RUN": "run_1"}}, {{"BADGER_RUN": "run_2"}}]
                → Step 4: respond to present analysis results

                **IMPORTANT:**
                - analyze_runs PRODUCES a RUN_ANALYSIS context (for propose_routines)
                - Results also useful for direct user presentation via respond
                - Required input for propose_routines capability
                """).strip(),
            examples=[
                simple_analysis_example,
                algorithm_comparison_example,
                trend_analysis_example
            ],
            priority=6
        )

    def _create_classifier_guide(self) -> Optional[TaskClassifierGuide]:
        """
        Create classifier guide to identify run analysis tasks.
        """
        return TaskClassifierGuide(
            instructions="Determine if the task requires analyzing or comparing multiple optimization runs.",
            examples=[
                ClassifierExample(
                    query="Which algorithm performed best?",
                    result=True,
                    reason="Requires comparing algorithms across multiple runs."
                ),
                ClassifierExample(
                    query="What patterns do you see in recent runs?",
                    result=True,
                    reason="Pattern identification requires analyzing multiple runs."
                ),
                ClassifierExample(
                    query="Compare success rates across beamlines",
                    result=True,
                    reason="Beamline comparison requires run analysis."
                ),
                ClassifierExample(
                    query="Show me trends over the past month",
                    result=True,
                    reason="Trend analysis requires analyzing runs over time."
                ),
                ClassifierExample(
                    query="What was the best performing run?",
                    result=True,
                    reason="Identifying best run requires comparison analysis."
                ),
                ClassifierExample(
                    query="Show me the most recent run",
                    result=False,
                    reason="This only requires query_runs, not analysis."
                ),
                ClassifierExample(
                    query="Load runs from last week",
                    result=False,
                    reason="This is run querying, not analysis (use query_runs)."
                ),
            ],
            actions_if_true=ClassifierActions()
        )
