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
    OrchestratorGuide, OrchestratorExample,
    TaskClassifierGuide, ClassifierExample, ClassifierActions
)
from framework.base.planning import PlannedStep
from framework.state import AgentState, StateManager
from framework.registry import get_registry
from configs.logger import get_logger
from configs.streaming import get_streamer
from configs.config import get_config_value

# Application imports
from applications.otter.context_classes import BadgerRunContext
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
    Query Badger optimization runs from archive.

    The orchestrator should use LLM to parse natural language queries into structured
    filters and include them in the step definition:

    step["filter"] = {
        "time_range": {"start": "2025-01-01", "end": "2025-12-31"},  # Optional
        "num_runs": 5,  # Optional, None = all matching
        "environment": "cu_hxr"  # Optional
    }

    Returns multiple BADGER_RUN contexts (one per matching run).
    """

    name = "query_runs"
    description = "Query Badger optimization runs from archive with time and count filters"
    provides = ["BADGER_RUN"]
    requires = []  # No hard requirements; TIME_RANGE is optional input if provided

    @staticmethod
    async def execute(state: AgentState, **kwargs) -> Dict[str, Any]:
        """Execute run query with structured filters from orchestrator."""

        step = StateManager.get_current_step(state)
        streamer = get_streamer("otter", "query_runs", state)

        try:
            # Get filter parameters from step.parameters (orchestrator puts them there)
            # Parameters is Dict[str, Union[str, int, float]] so extract filter values
            step_parameters = step.get("parameters", {})

            # Debug: Log the step to see what orchestrator provided
            logger.info(f"Current step: {step}")
            logger.info(f"Step parameters: {step_parameters}")

            # Extract filter parameters from step.parameters
            # Orchestrator should provide: parameters={"num_runs": 1} or parameters={"beamline": "lcls_ii"}
            filter_params = {}
            if "num_runs" in step_parameters:
                filter_params["num_runs"] = int(step_parameters["num_runs"])
            if "beamline" in step_parameters:
                filter_params["beamline"] = str(step_parameters["beamline"])

            # Extract time_range from inputs (optional - comes from TIME_RANGE context if provided)
            step_inputs = step.get("inputs", [])
            for input_item in step_inputs:
                if "TIME_RANGE" in input_item:
                    time_range_key = input_item["TIME_RANGE"]
                    # Get the TIME_RANGE context from state using ContextManager
                    from framework.context.context_manager import ContextManager
                    context_manager = ContextManager(state)
                    time_range_context = context_manager.get_context(
                        registry.context_types.TIME_RANGE,
                        time_range_key
                    )
                    if time_range_context:
                        # Convert to format expected by data source
                        filter_params["time_range"] = {
                            "start": time_range_context.start_date.isoformat(),
                            "end": time_range_context.end_date.isoformat()
                        }
                        logger.info(f"Applied time range filter: {filter_params['time_range']}")
                        break

            # Safety default: if no filter provided, default to 1 run to avoid loading all runs
            if not filter_params or "num_runs" not in filter_params:
                logger.warning("No num_runs in parameters, defaulting to num_runs=1")
                filter_params["num_runs"] = 1

            if filter_params:
                streamer.status(f"Querying runs with filters: {filter_params}")
            else:
                streamer.status("Querying runs (no filters specified)")

            # Load archive root from config
            # Config path: applications.otter.external_services.badger.archive_root
            archive_root = get_config_value("applications.otter.external_services.badger.archive_root")
            if not archive_root:
                raise ArchiveAccessError(
                    "Archive root not configured. Please set OTTER_BADGER_ARCHIVE environment variable."
                )

            # Initialize data source
            try:
                data_source = BadgerArchiveDataSource(archive_root)
            except (FileNotFoundError, NotADirectoryError) as e:
                raise ArchiveAccessError(str(e))

            # Query runs with filters
            run_paths = data_source.list_runs(
                time_range=filter_params.get("time_range"),
                limit=filter_params.get("num_runs"),
                beamline=filter_params.get("beamline")
            )

            if not run_paths:
                streamer.status("No runs found matching filters")
                logger.info("No runs found matching filters")
                # Return empty result - respond capability will handle this
                return {}

            streamer.status(f"Found {len(run_paths)} matching runs, loading metadata...")
            logger.info(f"Found {len(run_paths)} runs matching filters")

            # Load metadata for each run and create contexts
            updates = {}
            for idx, run_path in enumerate(run_paths):
                try:
                    streamer.status(f"Loading run {idx+1}/{len(run_paths)}: {Path(run_path).name}")

                    metadata = data_source.load_run_metadata(run_path)

                    # Create BadgerRunContext with Badger-native VOCS format
                    context = BadgerRunContext(
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
                        tags=metadata.get("tags")
                    )

                    # Store with unique key
                    context_key = f"run_{idx}"
                    updates.update(StateManager.store_context(
                        state,
                        registry.context_types.BADGER_RUN,
                        context_key,
                        context
                    ))

                    logger.debug(f"Loaded run {idx}: {metadata['name']}")

                except yaml.YAMLError as e:
                    # Log corrupt file but continue with other runs
                    logger.warning(f"Skipping corrupt run file {run_path}: {e}")
                    streamer.status(f"Skipped corrupt file: {Path(run_path).name}")
                    continue

                except Exception as e:
                    # Log error but continue with other runs
                    logger.warning(f"Failed to load run {run_path}: {e}")
                    streamer.status(f"Failed to load: {Path(run_path).name}")
                    continue

            if not updates:
                # All runs failed to load
                streamer.status("Failed to load any runs")
                logger.warning("All runs failed to load")
                return {}

            num_loaded = len([k for k in updates.keys() if k.startswith("context_BADGER_RUN")])
            streamer.status(f"Successfully loaded {num_loaded} runs")
            logger.success(f"Loaded {num_loaded} runs successfully")

            return updates

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
                    "resolution": "Check OTTER_BADGER_ARCHIVE environment variable and archive path"
                }
            )

        elif isinstance(exc, yaml.YAMLError):
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message=f"Encountered corrupt run file: {str(exc)}",
                metadata={
                    "technical_details": str(exc),
                    "resolution": "Run file may be corrupted - trying other runs"
                }
            )

        elif isinstance(exc, FileNotFoundError):
            return ErrorClassification(
                severity=ErrorSeverity.CRITICAL,
                user_message=f"Archive or run file not found: {str(exc)}",
                metadata={
                    "technical_details": str(exc),
                    "resolution": "Verify archive path and run file existence"
                }
            )

        elif isinstance(exc, PermissionError):
            return ErrorClassification(
                severity=ErrorSeverity.CRITICAL,
                user_message=f"Permission denied accessing archive: {str(exc)}",
                metadata={
                    "technical_details": str(exc),
                    "resolution": "Check file permissions for archive directory"
                }
            )

        elif isinstance(exc, QueryRunsError):
            # Generic query runs error
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message=f"Query error: {str(exc)}",
                metadata={"technical_details": str(exc)}
            )

        else:
            # Unknown error - default to retriable
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message=f"Unexpected error querying runs: {str(exc)}",
                metadata={"technical_details": str(exc)}
            )

    def _create_orchestrator_guide(self) -> Optional[OrchestratorGuide]:
        """
        Create comprehensive guide for orchestrator to plan run queries.

        Provides detailed examples of simple, moderate, and complex query scenarios.
        """

        # Example 1: Simple - most recent run
        most_recent_example = OrchestratorExample(
            step=PlannedStep(
                context_key="most_recent_run",
                capability="query_runs",
                task_objective="Get the most recent Badger optimization run",
                expected_output=registry.context_types.BADGER_RUN,
                success_criteria="Most recent run metadata loaded",
                inputs=[],
                parameters={"num_runs": 1}  # Use parameters field with simple int value
            ),
            scenario_description="User asks about the most recent run",
            notes="Use LLM to parse 'most recent' → num_runs=1 in parameters"
        )

        # Example 2: Simple list - last N runs
        last_n_example = OrchestratorExample(
            step=PlannedStep(
                context_key="recent_runs_list",
                capability="query_runs",
                task_objective="Get the last 5 Badger optimization runs",
                expected_output=registry.context_types.BADGER_RUN,
                success_criteria="Last 5 runs metadata loaded",
                inputs=[],
                parameters={"num_runs": 5}
            ),
            scenario_description="User wants to see multiple recent runs",
            notes="Creates multiple BADGER_RUN contexts (run_0, run_1, ..., run_4)"
        )

        # Example 3: Beamline-specific query
        beamline_example = OrchestratorExample(
            step=PlannedStep(
                context_key="cu_hxr_recent_runs",
                capability="query_runs",
                task_objective="Get recent runs from the cu_hxr beamline",
                expected_output=registry.context_types.BADGER_RUN,
                success_criteria="Recent cu_hxr runs loaded",
                inputs=[],
                parameters={"beamline": "cu_hxr", "num_runs": 10}
            ),
            scenario_description="User wants runs from specific beamline",
            notes="Beamline filter limits search to specific subdirectory in archive (e.g., 'cu_hxr', 'lcls_ii')"
        )

        return OrchestratorGuide(
            instructions=textwrap.dedent(f"""
                **When to plan "query_runs" steps:**
                - User asks about recent runs ("most recent run", "last 5 runs")
                - User needs run information for analysis or comparison
                - User asks about runs from a specific beamline (cu_hxr, lcls_ii, etc.)

                **CRITICAL: Use `parameters` field (NOT filter)!**
                Parse natural language into simple parameters and put them in step["parameters"]:

                User query: "Show me the most recent run"
                → step["parameters"] = {{"num_runs": 1}}

                User query: "Show me last 5 runs"
                → step["parameters"] = {{"num_runs": 5}}

                User query: "Show me runs from cu_hxr beamline"
                → step["parameters"] = {{"beamline": "cu_hxr", "num_runs": 10}}

                User query: "Show me runs from lcls_ii"
                → step["parameters"] = {{"beamline": "lcls_ii", "num_runs": 10}}

                **Available Parameters (all optional):**
                - num_runs: int (number of runs to return, default=1 if not specified)
                - beamline: str (beamline directory name, e.g., "cu_hxr", "cu_sxr", "lcls_ii")

                **IMPORTANT:** parameters field only accepts str/int/float values, NOT dictionaries!
                Time-based filtering is not supported via parameters yet.

                **Output: {registry.context_types.BADGER_RUN}**
                - Contains run metadata: name, algorithm, variables, objectives, evaluations
                - Multiple contexts created (one per run): run_0, run_1, run_2, ...
                - Available for display or further analysis in subsequent steps

                **Empty Results:**
                - If no runs match filters, returns empty (not an error)
                - Respond capability will inform user that no runs were found

                **Dependencies and sequencing:**
                - This is typically the first step in run analysis workflows
                - Results can feed into analysis, comparison, or routine composition steps
                - No input dependencies (works standalone)
                """).strip(),
            examples=[
                most_recent_example,
                last_n_example,
                beamline_example
            ],
            priority=5
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
                    reason="User wants information about recent optimization run."
                ),
                ClassifierExample(
                    query="Show me the last 5 runs",
                    result=True,
                    reason="Request for multiple recent runs."
                ),
                ClassifierExample(
                    query="What runs happened last week?",
                    result=True,
                    reason="Time-based run query."
                ),
                ClassifierExample(
                    query="Show me runs from cu_hxr beamline",
                    result=True,
                    reason="Beamline-specific run query."
                ),
                ClassifierExample(
                    query="Show me runs from lcls_ii",
                    result=True,
                    reason="Beamline-specific run query (lcls_ii is a beamline directory)."
                ),
                ClassifierExample(
                    query="What is the weather today?",
                    result=False,
                    reason="Not related to Badger optimization runs."
                ),
                ClassifierExample(
                    query="Compose a routine to tune FEL intensity",
                    result=False,
                    reason="This is routine composition, not run querying (different capability)."
                ),
                ClassifierExample(
                    query="Which algorithm has been used most often?",
                    result=False,
                    reason="This requires run analysis/statistics, not just querying (different capability)."
                ),
            ],
            actions_if_true=ClassifierActions()
        )
