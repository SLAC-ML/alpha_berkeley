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
from applications.otter.context_classes import BadgerRunContext, BadgerRunsContext

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

    This capability takes a BADGER_RUNS context (container) as input and performs:
    - Statistical analysis (mean, median, variance of success metrics)
    - Algorithm performance comparison
    - Temporal trend detection
    - Common pattern identification
    - Success factor analysis

    Returns a structured analysis summary for downstream use or user presentation.
    """

    name = "analyze_runs"
    description = "Analyze and compare multiple Badger optimization runs from BADGER_RUNS container"
    provides = ["RUN_ANALYSIS"]
    requires = ["BADGER_RUNS"]

    @staticmethod
    async def execute(state: AgentState, **kwargs) -> Dict[str, Any]:
        """Execute run analysis."""

        step = StateManager.get_current_step(state)
        streamer = get_streamer("otter", "analyze_runs", state)

        try:
            # Get context manager to retrieve BADGER_RUNS container
            context_manager = ContextManager(state)

            # Extract BADGER_RUNS context from inputs (hard requirement)
            try:
                contexts = context_manager.extract_from_step(
                    step, state,
                    constraints=["BADGER_RUNS"],
                    constraint_mode="hard"
                )
                runs_container = contexts[registry.context_types.BADGER_RUNS]
            except ValueError as e:
                raise InsufficientDataError(f"Missing required BADGER_RUNS context: {e}") from e

            # Extract run contexts from container
            run_contexts: List[BadgerRunContext] = runs_container.runs

            if not run_contexts:
                raise InsufficientDataError("BADGER_RUNS container is empty - no runs to analyze")

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
            # Section 6: Per-Run Details Table
            # ====================
            streamer.status("Compiling per-run details for table format...")

            per_run_details = {}
            for run in run_contexts:
                # Use run_filename as unique key
                run_key = run.run_filename

                # Extract variable names from List[Dict[str, List[float]]]
                variable_names = []
                for var_dict in run.variables:
                    variable_names.extend(var_dict.keys())

                # Extract objectives with directions from List[Dict[str, str]]
                objectives_dict = {}
                for obj_dict in run.objectives:
                    objectives_dict.update(obj_dict)  # Merge all objective dicts

                # Calculate improvements per objective (initial → BEST values)
                improvements = {}
                if run.initial_objective_values:
                    for obj_name in objectives_dict.keys():
                        direction = objectives_dict[obj_name]
                        initial = run.initial_objective_values.get(obj_name)

                        # Use BEST values (not final) per BO domain knowledge
                        if direction == 'MAXIMIZE':
                            best = run.max_objective_values.get(obj_name) if run.max_objective_values else run.final_objective_values.get(obj_name)
                        else:  # MINIMIZE
                            best = run.min_objective_values.get(obj_name) if run.min_objective_values else run.final_objective_values.get(obj_name)

                        if initial is not None and best is not None and initial != 0:
                            if direction == 'MAXIMIZE':
                                improvement_pct = ((best - initial) / abs(initial)) * 100
                            else:  # MINIMIZE
                                improvement_pct = ((initial - best) / abs(initial)) * 100
                            improvements[obj_name] = round(improvement_pct, 2)

                # Build per-run entry
                per_run_details[run_key] = {
                    "run_name": run.run_name,
                    "timestamp": run.timestamp.isoformat(),
                    "beamline": run.beamline,
                    "badger_environment": run.badger_environment,
                    "algorithm": run.algorithm,
                    "num_evaluations": run.num_evaluations,
                    "variables": variable_names,
                    "objectives": objectives_dict,  # {obj_name: direction}
                    "constraints": run.constraints if run.constraints else [],
                    "improvements": improvements,  # {obj_name: improvement_pct}
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
                },
                "per_run_details": per_run_details  # New: structured per-run data for tables
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
                task_objective="Analyze the most recent runs to identify patterns",
                expected_output=registry.context_types.RUN_ANALYSIS,
                success_criteria="Statistical analysis of runs completed",
                inputs=[{"BADGER_RUNS": "recent_runs"}],  # Single container from query_runs
                parameters={}
            ),
            scenario_description="User wants to understand patterns in recent runs",
            notes="Provide BADGER_RUNS container from previous query_runs step. "
                  "Analysis will compare algorithms, objectives, and success rates across all runs in container."
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

                **Typical workflow (3 steps):**
                Step 1: extract_run_filters - Parse query into RUN_QUERY_FILTERS
                Step 2: query_runs - Load runs from archive (creates BADGER_RUNS container)
                Step 3: analyze_runs - Analyze runs from container (inputs=[{{"BADGER_RUNS": "context_key"}}])

                **CRITICAL: Input Requirements:**
                - Requires BADGER_RUNS context as input (container holding all runs)
                - The BADGER_RUNS container has a .runs field with list of BadgerRunContext objects
                - Simply pass the BADGER_RUNS context - no need to list individual runs!
                - Input format: inputs=[{{"BADGER_RUNS": "context_key_from_query_runs"}}]

                **How to construct inputs:**
                - If query_runs created context "recent_runs" → inputs=[{{"BADGER_RUNS": "recent_runs"}}]
                - If query_runs created context "cu_hxr_runs" → inputs=[{{"BADGER_RUNS": "cu_hxr_runs"}}]
                - The container automatically provides ALL runs to analyze_runs

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
                → Step 1: extract_run_filters for "last 10 runs"
                   (creates RUN_QUERY_FILTERS with num_runs=10)
                → Step 2: query_runs with inputs=[{{"RUN_QUERY_FILTERS": "filters"}}]
                   (creates BADGER_RUNS container "recent_runs" with 10 runs)
                → Step 3: analyze_runs with inputs=[{{"BADGER_RUNS": "recent_runs"}}]
                → Step 4: respond to present analysis results

                "Analyze runs and suggest a routine"
                → Step 1: extract_run_filters
                → Step 2: query_runs
                   (creates BADGER_RUNS container)
                → Step 3: analyze_runs with inputs=[{{"BADGER_RUNS": "runs"}}]
                   (creates RUN_ANALYSIS context)
                → Step 4: propose_routines with inputs=[{{"RUN_ANALYSIS": "run_analysis"}}]
                → Step 5: respond to present analysis + proposals

                "Analyze the last 3 runs from lcls_ii environment"
                → Step 1: extract_run_filters for "last 3 runs from lcls_ii"
                   (creates RUN_QUERY_FILTERS)
                → Step 2: query_runs with inputs=[{{"RUN_QUERY_FILTERS": "filters"}}]
                   (creates BADGER_RUNS container with 3 runs)
                → Step 3: analyze_runs with inputs=[{{"BADGER_RUNS": "lcls_ii_runs"}}]
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
