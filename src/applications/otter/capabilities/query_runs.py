"""
Query Runs Capability

Capability for querying Badger optimization runs from the archive with time and count filters.
The orchestrator provides structured filters in the step definition.
"""

import logging
import textwrap
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

# Framework imports
from framework.base.decorators import capability_node
from framework.base.capability import BaseCapability
from framework.base.errors import ErrorClassification, ErrorSeverity
from framework.base.examples import (
    OrchestratorGuide,
    OrchestratorExample,
    TaskClassifierGuide,
    ClassifierExample,
    ClassifierActions,
)
from framework.base.planning import PlannedStep
from framework.state import AgentState, StateManager
from framework.registry import get_registry
from configs.logger import get_logger
from configs.streaming import get_streamer
from configs.config import get_config_value

# Application imports
from applications.otter.context_classes import BadgerRunContext, BadgerRunsContext
from applications.otter.data_sources.badger_archive import BadgerArchiveDataSource

logger = get_logger("otter", "query_runs")
registry = get_registry()


# ====================
# Custom Exceptions
# ====================


class QueryRunsError(Exception):
    """Base class for query runs errors."""

    pass


class ArchiveAccessError(QueryRunsError):
    """Raised when archive cannot be accessed."""

    pass


class RunLoadError(QueryRunsError):
    """Raised when run file cannot be loaded."""

    pass


# ====================
# Capability Definition
# ====================


@capability_node
class QueryRunsCapability(BaseCapability):
    """
    Query Badger optimization runs from archive using filters from RUN_QUERY_FILTERS context.

    This capability requires the extract_run_filters capability to run first, which parses
    natural language queries into structured filter criteria and creates a RUN_QUERY_FILTERS context.

    Two-step pattern:
    1. extract_run_filters: Parse query → create RUN_QUERY_FILTERS context
    2. query_runs: Use RUN_QUERY_FILTERS → load BADGER_RUNS context (container with all runs)

    Returns a single BADGER_RUNS context containing a list of BadgerRunContext objects.
    """

    name = "query_runs"
    description = "Query Badger optimization runs from archive using filters from RUN_QUERY_FILTERS context"
    provides = ["BADGER_RUNS"]  # Provides a container with multiple runs
    requires = ["RUN_QUERY_FILTERS"]  # Hard requirement: must have filters from extract_run_filters

    @staticmethod
    async def execute(state: AgentState, **kwargs) -> Dict[str, Any]:
        """Execute run query with structured filters from RUN_QUERY_FILTERS context."""

        step = StateManager.get_current_step(state)
        streamer = get_streamer("otter", "query_runs", state)

        try:
            # Extract required RUN_QUERY_FILTERS context using ContextManager
            from framework.context.context_manager import ContextManager

            context_manager = ContextManager(state)

            # RUN_QUERY_FILTERS is now a hard requirement
            try:
                contexts = context_manager.extract_from_step(
                    step, state,
                    constraints=["RUN_QUERY_FILTERS"],
                    constraint_mode="hard"
                )
                filter_context = contexts[registry.context_types.RUN_QUERY_FILTERS]
            except ValueError as e:
                raise QueryRunsError(f"Missing required RUN_QUERY_FILTERS context: {e}") from e

            # Extract parameters from filter context
            filter_params = filter_context.to_parameters()
            logger.info(f"Using filters from RUN_QUERY_FILTERS context: {filter_params}")

            # Extract optional TIME_RANGE from inputs (if provided)
            step_inputs = step.get("inputs", [])
            for input_item in step_inputs:
                if "TIME_RANGE" in input_item:
                    time_range_key = input_item["TIME_RANGE"]
                    time_range_context = context_manager.get_context(
                        registry.context_types.TIME_RANGE, time_range_key
                    )
                    if time_range_context:
                        # Convert to format expected by data source
                        filter_params["time_range"] = {
                            "start": time_range_context.start_date.isoformat(),
                            "end": time_range_context.end_date.isoformat(),
                        }
                        logger.info(f"Applied time range filter: {filter_params['time_range']}")
                        break

            # Safety default: if no num_runs specified, default to 1 run to avoid loading all runs
            if "num_runs" not in filter_params or filter_params["num_runs"] is None:
                logger.warning("No num_runs in filters, defaulting to num_runs=1")
                filter_params["num_runs"] = 1

            if filter_params:
                streamer.status(f"Querying runs with filters: {filter_params}")
            else:
                streamer.status("Querying runs (no filters specified)")

            # Load archive root from config
            # Config path: applications.otter.external_services.badger.archive_root
            archive_root = get_config_value(
                "applications.otter.external_services.badger.archive_root"
            )
            if not archive_root:
                raise ArchiveAccessError(
                    "Archive root not configured. Please set OTTER_BADGER_ARCHIVE environment variable."
                )

            # Define progress callback for index building (start and end only)
            def progress_callback(current: int, total: int, path: str):
                """Progress callback for index building - start and end messages only"""
                if path == "start":
                    streamer.status(
                        f"Building index for {total} run files (this may take a few minutes)..."
                    )
                elif path == "complete":
                    streamer.status(f"✅ Archive index built! ({total} runs indexed)")

            # Initialize data source with progress callback
            try:
                data_source = BadgerArchiveDataSource(
                    archive_root, use_cache=True, progress_callback=progress_callback
                )
            except (FileNotFoundError, NotADirectoryError) as e:
                raise ArchiveAccessError(str(e))

            # Query runs with filters
            run_paths = data_source.list_runs(
                time_range=filter_params.get("time_range"),
                limit=filter_params.get("num_runs"),
                beamline=filter_params.get("beamline"),
                algorithm=filter_params.get("algorithm"),
                badger_environment=filter_params.get("badger_environment"),
                objective=filter_params.get("objective"),
                sort_order=filter_params.get("sort_order", "newest_first"),
            )

            if not run_paths:
                streamer.status("No runs found matching filters")
                logger.info("No runs found matching filters")
                # Return empty result - respond capability will handle this
                return {}

            streamer.status(f"Found {len(run_paths)} matching runs, loading metadata...")
            logger.info(f"Found {len(run_paths)} runs matching filters")

            # Load metadata for each run and collect in a list
            loaded_runs = []

            for idx, run_path in enumerate(run_paths):
                try:
                    streamer.status(f"Loading run {idx+1}/{len(run_paths)}: {Path(run_path).name}")

                    metadata = data_source.load_run_metadata(run_path)

                    # Create BadgerRunContext with Badger-native VOCS format
                    run_context = BadgerRunContext(
                        run_filename=run_path,
                        run_name=metadata["name"],
                        timestamp=metadata["timestamp"],
                        beamline=metadata["beamline"],
                        badger_environment=metadata["badger_environment"],
                        algorithm=metadata["algorithm"],
                        variables=metadata["variables"],  # List[Dict[str, List[float]]]
                        objectives=metadata["objectives"],  # List[Dict[str, str]]
                        constraints=metadata.get("constraints", []),
                        num_evaluations=metadata["num_evaluations"],
                        initial_objective_values=metadata.get("initial_values"),
                        min_objective_values=metadata.get("min_values"),
                        max_objective_values=metadata.get("max_values"),
                        final_objective_values=metadata.get("final_values"),
                        description=metadata.get("description", ""),
                        tags=metadata.get("tags"),
                    )

                    loaded_runs.append(run_context)
                    logger.debug(f"Loaded run {idx}: {metadata['name']}")

                except yaml.YAMLError as e:
                    # Log corrupt file but continue with other runs
                    logger.warning(f"Skipping corrupt run file {run_path}: {e}")
                    streamer.status(f"Skipped corrupt file: {Path(run_path).name}")
                    continue

                except Exception as e:
                    # Log error but continue with other runs
                    logger.error(f"Failed to load run {run_path}: {e}", exc_info=True)
                    streamer.status(f"Failed to load: {Path(run_path).name}")
                    continue

            if not loaded_runs:
                # All runs failed to load
                streamer.status("Failed to load any runs")
                logger.warning("All runs failed to load")
                return {}

            # Create container context with all loaded runs
            runs_container = BadgerRunsContext(runs=loaded_runs)

            streamer.status(f"Successfully loaded {runs_container.run_count} runs")
            logger.success(f"Loaded {runs_container.run_count} runs successfully")

            # Store single container context under step's context_key
            context_updates = StateManager.store_context(
                state,
                registry.context_types.BADGER_RUNS,
                step.get("context_key"),
                runs_container
            )

            return context_updates

        except ArchiveAccessError as e:
            logger.error(f"Archive access error: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error in query_runs: {e}")
            raise

    @staticmethod
    def classify_error(exc: Exception, context: dict) -> ErrorClassification:
        """
        Otter-specific error classification for query runs capability.

        Determines severity and user message based on error type.
        """

        if isinstance(exc, ArchiveAccessError):
            return ErrorClassification(
                severity=ErrorSeverity.CRITICAL,
                user_message=f"Badger archive not accessible: {str(exc)}",
                metadata={
                    "technical_details": str(exc),
                    "resolution": "Check OTTER_BADGER_ARCHIVE environment variable and archive path",
                },
            )

        elif isinstance(exc, yaml.YAMLError):
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message=f"Encountered corrupt run file: {str(exc)}",
                metadata={
                    "technical_details": str(exc),
                    "resolution": "Run file may be corrupted - trying other runs",
                },
            )

        elif isinstance(exc, FileNotFoundError):
            return ErrorClassification(
                severity=ErrorSeverity.CRITICAL,
                user_message=f"Archive or run file not found: {str(exc)}",
                metadata={
                    "technical_details": str(exc),
                    "resolution": "Verify archive path and run file existence",
                },
            )

        elif isinstance(exc, PermissionError):
            return ErrorClassification(
                severity=ErrorSeverity.CRITICAL,
                user_message=f"Permission denied accessing archive: {str(exc)}",
                metadata={
                    "technical_details": str(exc),
                    "resolution": "Check file permissions for archive directory",
                },
            )

        elif isinstance(exc, QueryRunsError):
            # Generic query runs error
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message=f"Query error: {str(exc)}",
                metadata={"technical_details": str(exc)},
            )

        else:
            # Unknown error - default to retriable
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message=f"Unexpected error querying runs: {str(exc)}",
                metadata={"technical_details": str(exc)},
            )

    def _create_orchestrator_guide(self) -> Optional[OrchestratorGuide]:
        """
        Create comprehensive guide for orchestrator to plan run queries.

        Provides detailed examples of simple, moderate, and complex query scenarios.
        """

        # Example 1: Two-step pattern - most recent run
        most_recent_example = OrchestratorExample(
            step=PlannedStep(
                context_key="most_recent_run",
                capability="query_runs",
                task_objective="Load the most recent Badger optimization run",
                expected_output=registry.context_types.BADGER_RUNS,
                success_criteria="Most recent run metadata loaded",
                inputs=[{"RUN_QUERY_FILTERS": "recent_run_filters"}],  # From extract_run_filters
                parameters={},
            ),
            scenario_description="User asks about the most recent run - requires extract_run_filters first",
            notes="TWO-STEP PATTERN: Step 1 (extract_run_filters) creates RUN_QUERY_FILTERS context with num_runs=1, sort_order=newest_first. Step 2 (query_runs) creates BADGER_RUNS context with single run.",
        )

        # Example 2: Two-step with sorting - oldest run
        oldest_run_example = OrchestratorExample(
            step=PlannedStep(
                context_key="oldest_run",
                capability="query_runs",
                task_objective="Load the oldest Badger optimization run on lcls_ii",
                expected_output=registry.context_types.BADGER_RUNS,
                success_criteria="Oldest run metadata loaded",
                inputs=[{"RUN_QUERY_FILTERS": "oldest_run_filters"}],  # From extract_run_filters
                parameters={},
            ),
            scenario_description="User asks for the oldest run - requires extract_run_filters with sort_order=oldest_first",
            notes="TWO-STEP PATTERN: Step 1 (extract_run_filters) creates RUN_QUERY_FILTERS with num_runs=1, badger_environment=lcls_ii, sort_order=oldest_first. Step 2 (query_runs) creates BADGER_RUNS context.",
        )

        # Example 3: Beamline-specific query
        beamline_example = OrchestratorExample(
            step=PlannedStep(
                context_key="cu_hxr_recent_runs",
                capability="query_runs",
                task_objective="Load recent runs from the cu_hxr beamline",
                expected_output=registry.context_types.BADGER_RUNS,
                success_criteria="Recent cu_hxr runs loaded",
                inputs=[{"RUN_QUERY_FILTERS": "cu_hxr_filters"}],
                parameters={},
            ),
            scenario_description="User wants recent runs from specific beamline",
            notes="TWO-STEP PATTERN: extract_run_filters parses beamline and creates filter context. query_runs creates BADGER_RUNS container with multiple runs.",
        )

        # Example 4: Multi-step with information extraction
        info_extraction_example = OrchestratorExample(
            step=PlannedStep(
                context_key="algorithm_summary",
                capability="respond",
                task_objective="Tell user which algorithms were used in the loaded runs",
                expected_output="user_response",
                success_criteria="User receives information about algorithms from run contexts",
                inputs=[{"BADGER_RUNS": "recent_runs"}],  # References BADGER_RUNS container from query_runs step
                parameters={},
            ),
            scenario_description="Extract information from loaded runs",
            notes="MULTI-STEP PATTERN: Step 1: extract_run_filters → Step 2: query_runs (creates BADGER_RUNS) → Step 3: respond to extract info from BADGER_RUNS.runs list.",
        )

        return OrchestratorGuide(
            instructions=textwrap.dedent(
                f"""
                **CRITICAL: MANDATORY TWO-STEP PATTERN**
                query_runs REQUIRES RUN_QUERY_FILTERS context from extract_run_filters capability.
                ALWAYS plan extract_run_filters BEFORE query_runs - there are NO exceptions!

                **When to plan "query_runs" steps:**
                - User asks about recent runs ("most recent run", "last 5 runs", "oldest run")
                - User needs run information for analysis or comparison
                - User asks about runs from a specific beamline or environment
                - User asks about runs using a specific algorithm or optimizing an objective

                **Required Pattern:**
                Step 1: extract_run_filters → creates RUN_QUERY_FILTERS context
                Step 2: query_runs → uses RUN_QUERY_FILTERS context → creates BADGER_RUNS context

                **Example: "Show me the most recent run"**
                Step 1: extract_run_filters with task_objective="Extract filters for: most recent run"
                        → Creates RUN_QUERY_FILTERS context with num_runs=1, sort_order=newest_first
                Step 2: query_runs with inputs=[{{"RUN_QUERY_FILTERS": "filters_from_step_1"}}]
                        → Creates BADGER_RUNS context containing 1 run in .runs list

                **Example: "Show me the oldest run on lcls_ii"**
                Step 1: extract_run_filters with task_objective="Extract filters for: oldest run on lcls_ii"
                        → Creates RUN_QUERY_FILTERS with num_runs=1, badger_environment=lcls_ii, sort_order=oldest_first
                Step 2: query_runs with inputs=[{{"RUN_QUERY_FILTERS": "filters_from_step_1"}}]
                        → Creates BADGER_RUNS context with the oldest lcls_ii run

                **Sorting Support:**
                - "recent", "last", "latest", "newest" → sort_order=newest_first (default)
                - "oldest", "first", "earliest" → sort_order=oldest_first
                - extract_run_filters automatically detects sort order from query

                **Output: {registry.context_types.BADGER_RUNS}**
                - Container context holding list of BadgerRunContext objects in .runs field
                - Access individual runs via .runs[index] (zero-indexed)
                - Use .run_count to get total number of runs
                - Each run has full metadata: name, algorithm, variables, objectives, evaluations
                - Available for display or further analysis in subsequent steps

                **Empty Results:**
                - If no runs match filters, returns empty (not an error)
                - Respond capability will inform user that no runs were found

                **Time Range Filtering (optional):**
                - TIME_RANGE input is OPTIONAL - only use when user explicitly mentions dates/times
                - For "recent runs" or "last N runs", use extract_run_filters (NOT time_range_parsing)
                - extract_run_filters handles "last N runs" via num_runs parameter

                **Dependencies and sequencing:**
                - ALWAYS plan extract_run_filters before query_runs
                - Results can feed into analysis, comparison, or routine composition steps
                - Optional TIME_RANGE input (only when user mentions specific dates/times)
                """
            ).strip(),
            examples=[
                most_recent_example,
                oldest_run_example,
                beamline_example,
                info_extraction_example,
            ],
            priority=5,
        )

    def _create_classifier_guide(self) -> Optional[TaskClassifierGuide]:
        """
        Create classifier guide to help identify run query tasks.
        """
        return TaskClassifierGuide(
            instructions="Determine if the task requires querying Badger optimization run history from the archive.",
            examples=[
                ClassifierExample(
                    query="Tell me about the most recent run",
                    result=True,
                    reason="User wants information about recent optimization run.",
                ),
                ClassifierExample(
                    query="Show me the last 5 runs",
                    result=True,
                    reason="Request for multiple recent runs.",
                ),
                ClassifierExample(
                    query="What runs happened last week?",
                    result=True,
                    reason="Time-based run query.",
                ),
                ClassifierExample(
                    query="Show me runs from cu_hxr beamline",
                    result=True,
                    reason="Beamline-specific run query.",
                ),
                ClassifierExample(
                    query="Show me runs from lcls_ii",
                    result=True,
                    reason="Badger environment-specific run query (lcls_ii is a Badger environment).",
                ),
                ClassifierExample(
                    query="Show me runs that used expected_improvement",
                    result=True,
                    reason="Algorithm-specific run query.",
                ),
                ClassifierExample(
                    query="Show me neldermead runs",
                    result=True,
                    reason="Algorithm-specific run query.",
                ),
                ClassifierExample(
                    query="Show me runs from the lcls environment",
                    result=True,
                    reason="Badger environment-specific run query.",
                ),
                ClassifierExample(
                    query="Show me runs that optimized pulse intensity",
                    result=True,
                    reason="Objective-specific run query.",
                ),
                ClassifierExample(
                    query="What is the weather today?",
                    result=False,
                    reason="Not related to Badger optimization runs.",
                ),
                ClassifierExample(
                    query="Compose a routine to tune FEL intensity",
                    result=False,
                    reason="This is routine composition, not run querying (different capability).",
                ),
                ClassifierExample(
                    query="Which algorithm has been used most often?",
                    result=False,
                    reason="This requires run analysis/statistics, not just querying (different capability).",
                ),
            ],
            actions_if_true=ClassifierActions(),
        )
