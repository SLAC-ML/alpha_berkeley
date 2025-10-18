"""
Extract Run Filters Capability

This capability uses an LLM to extract structured filter criteria from natural
language queries for Badger run searches. It handles disambiguation between
beamline directories, Badger environment names, algorithms, and objectives.
"""
from __future__ import annotations
from typing import Dict, Any, Optional, TYPE_CHECKING
import asyncio
import textwrap

if TYPE_CHECKING:
    from framework.state import AgentState

# Framework imports
from framework.base.decorators import capability_node
from framework.base.capability import BaseCapability
from framework.base.errors import ErrorClassification, ErrorSeverity
from framework.base.planning import PlannedStep
from framework.base.examples import (
    OrchestratorGuide, OrchestratorExample,
    TaskClassifierGuide, ClassifierExample, ClassifierActions
)
from framework.state import StateManager
from framework.registry import get_registry

# Application imports
from applications.otter.context_classes import RunQueryFilters

# Model and configuration
from framework.models import get_chat_completion
from configs.config import get_model_config
from configs.streaming import get_streamer
from configs.logger import get_logger

logger = get_logger("otter", "extract_run_filters")
registry = get_registry()


# ===================================================================
# Filter Extraction Errors
# ===================================================================

class FilterExtractionError(Exception):
    """Base class for all filter extraction errors."""
    pass


class InvalidFilterError(FilterExtractionError):
    """Raised when extracted filters contain invalid values."""
    pass


# ===================================================================
# Filter Extraction Logic
# ===================================================================

from pydantic import BaseModel, Field as PydanticField

class ExtractedFilters(BaseModel):
    """Result from LLM-based filter extraction."""
    num_runs: Optional[int] = None
    beamline: Optional[str] = None
    algorithm: Optional[str] = None
    badger_environment: Optional[str] = None
    objective: Optional[str] = None
    sort_order: str = "newest_first"  # Default to newest_first


async def extract_filters_from_query(user_query: str) -> ExtractedFilters:
    """
    Use a lightweight LLM to extract structured filter criteria from natural language.

    Args:
        user_query: User's natural language query about Badger runs

    Returns:
        ExtractedFilters with parsed filter values
    """
    system_prompt = textwrap.dedent("""
        You are a Badger run filter extraction assistant. Extract structured filter criteria from natural language queries.

        Available filter fields:
        - num_runs: int (how many runs to retrieve - default to 10 if not explicitly specified)
        - beamline: str (ONLY these 7 physical beamline directories: 'cu_hxr', 'cu_sxr', 'sc_bsyd', 'sc_diag0', 'sc_sxr', 'sc_hxr', 'dev')
        - badger_environment: str (Badger software environment: 'lcls', 'lcls_ii', 'sphere', etc.)
        - algorithm: str (optimization algorithm: 'expected_improvement', 'neldermead', 'mobo', 'rcds', etc.)
        - objective: str (objective function name: 'pulse_intensity_p80', etc.)
        - sort_order: str (ONLY 'newest_first' or 'oldest_first' - default to 'newest_first')

        CRITICAL DISAMBIGUATION RULES:
        1. 'lcls_ii' is a BADGER_ENVIRONMENT (software environment), NOT a beamline!
        2. 'lcls' is also a BADGER_ENVIRONMENT
        3. Only these are beamlines: cu_hxr, cu_sxr, sc_bsyd, sc_diag0, sc_sxr, sc_hxr, dev
        4. When user says "environment" without specifying which field, they likely mean badger_environment
        5. When user says "beamline" they mean the physical beamline directory
        6. Default to num_runs=10 if user says "recent runs" or "last runs" without specifying a number
        7. "recent", "last", "latest", "newest" → sort_order='newest_first' (default)
        8. "oldest", "first", "earliest" → sort_order='oldest_first'

        Examples:

        Query: "last 10 runs from cu_hxr beamline"
        Response: {"num_runs": 10, "beamline": "cu_hxr", "sort_order": "newest_first"}

        Query: "recent runs for lcls_ii environment"
        Response: {"num_runs": 10, "badger_environment": "lcls_ii", "sort_order": "newest_first"}

        Query: "show me the oldest run on lcls_ii"
        Response: {"num_runs": 1, "badger_environment": "lcls_ii", "sort_order": "oldest_first"}

        Query: "runs from lcls_ii"
        Response: {"num_runs": 10, "badger_environment": "lcls_ii", "sort_order": "newest_first"}

        Query: "5 neldermead runs from sc_sxr"
        Response: {"num_runs": 5, "algorithm": "neldermead", "beamline": "sc_sxr", "sort_order": "newest_first"}

        Query: "cu_hxr runs optimizing pulse_intensity_p80"
        Response: {"num_runs": 10, "beamline": "cu_hxr", "objective": "pulse_intensity_p80", "sort_order": "newest_first"}

        Query: "last 15 runs that used expected_improvement for lcls environment"
        Response: {"num_runs": 15, "algorithm": "expected_improvement", "badger_environment": "lcls", "sort_order": "newest_first"}

        Query: "show me dev beamline neldermead runs"
        Response: {"num_runs": 10, "beamline": "dev", "algorithm": "neldermead", "sort_order": "newest_first"}

        Query: "recent sc_diag0 runs"
        Response: {"num_runs": 10, "beamline": "sc_diag0", "sort_order": "newest_first"}

        Query: "analyze the last 3 runs"
        Response: {"num_runs": 3, "sort_order": "newest_first"}

        Query: "show me the first run ever on cu_hxr"
        Response: {"num_runs": 1, "beamline": "cu_hxr", "sort_order": "oldest_first"}

        Query: "earliest 5 runs from lcls environment"
        Response: {"num_runs": 5, "badger_environment": "lcls", "sort_order": "oldest_first"}

        Respond ONLY with the JSON object. Leave fields null if not mentioned in the query.
        """)

    try:
        # Use framework's filter_extraction model (configured in config.yml)
        model_config = get_model_config("framework", "filter_extraction")

        response = await asyncio.to_thread(
            get_chat_completion,
            model_config=model_config,
            message=f"{system_prompt}\n\nQuery: {user_query}",
            output_model=ExtractedFilters,
        )

        if isinstance(response, ExtractedFilters):
            logger.info(f"Extracted filters from query '{user_query}': {response}")
            return response
        else:
            logger.warning(f"Filter extraction did not return expected type, got: {type(response)}")
            # Fallback to default
            return ExtractedFilters(num_runs=10)

    except Exception as e:
        logger.error(f"Error during filter extraction: {e}")
        # Fallback to default
        return ExtractedFilters(num_runs=10)


# ===================================================================
# Capability Implementation
# ===================================================================

@capability_node
class ExtractRunFiltersCapability(BaseCapability):
    """Extract structured run query filters from natural language."""

    name = "extract_run_filters"
    description = "Extract structured filter criteria from natural language queries for Badger run searches"
    provides = ["RUN_QUERY_FILTERS"]
    requires = []

    @staticmethod
    async def execute(
        state: AgentState,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract filter criteria from user query using LLM.

        The task_objective should contain the natural language query to parse.
        """
        step = StateManager.get_current_step(state)
        streamer = get_streamer("otter", "extract_run_filters", state)

        # Extract the query from task_objective
        query = step.get('task_objective', '')

        logger.info(f"Extracting run filters from query: {query}")
        streamer.status("Analyzing query to extract filter criteria...")

        # Use LLM to extract structured filters
        extracted = await extract_filters_from_query(query)

        # Validate beamline if provided
        valid_beamlines = {'cu_hxr', 'cu_sxr', 'sc_bsyd', 'sc_diag0', 'sc_sxr', 'sc_hxr', 'dev'}
        if extracted.beamline and extracted.beamline not in valid_beamlines:
            # Attempt to correct common mistakes
            beamline_lower = extracted.beamline.lower()
            if beamline_lower in valid_beamlines:
                extracted.beamline = beamline_lower
                logger.info(f"Corrected beamline case: {extracted.beamline}")
            else:
                logger.warning(
                    f"Extracted beamline '{extracted.beamline}' is not valid. "
                    f"Valid beamlines: {valid_beamlines}. Setting beamline to None."
                )
                extracted.beamline = None

        # Create context
        filter_context = RunQueryFilters(
            num_runs=extracted.num_runs,
            beamline=extracted.beamline,
            algorithm=extracted.algorithm,
            badger_environment=extracted.badger_environment,
            objective=extracted.objective,
            sort_order=extracted.sort_order
        )

        # Log extracted filters
        active_filters = filter_context.to_parameters()
        logger.info(f"Extracted filters: {active_filters}")
        streamer.status(f"Extracted {len(active_filters)} filter(s): {', '.join(f'{k}={v}' for k, v in active_filters.items())}")

        # Store context
        state_updates = StateManager.store_context(
            state,
            registry.context_types.RUN_QUERY_FILTERS,
            step.get("context_key"),
            filter_context
        )

        streamer.status("Filter extraction complete")
        return state_updates

    @staticmethod
    def classify_error(exc: Exception, context: dict) -> ErrorClassification:
        """Classify errors from filter extraction."""

        if isinstance(exc, InvalidFilterError):
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message=f"Invalid filter values: {str(exc)}",
                metadata={
                    "technical_details": str(exc),
                    "resolution": "Check filter values and retry"
                }
            )

        else:
            # Default: retriable for unknown errors
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message=f"Unexpected error in filter extraction: {exc}",
                metadata={"technical_details": str(exc)}
            )

    def _create_orchestrator_guide(self) -> Optional[OrchestratorGuide]:
        """Create orchestrator guide for filter extraction."""

        # Example 1: Simple environment query
        environment_example = OrchestratorExample(
            step=PlannedStep(
                context_key="lcls_ii_filters",
                capability="extract_run_filters",
                task_objective="Extract filters for: recent runs from lcls_ii environment",
                expected_output=registry.context_types.RUN_QUERY_FILTERS,
                success_criteria="Filters extracted with badger_environment=lcls_ii",
                inputs=[]
            ),
            scenario_description="User asks for runs from lcls_ii (a Badger environment)",
            notes="Output: RUN_QUERY_FILTERS with badger_environment='lcls_ii', num_runs=10"
        )

        # Example 2: Beamline query
        beamline_example = OrchestratorExample(
            step=PlannedStep(
                context_key="cu_hxr_filters",
                capability="extract_run_filters",
                task_objective="Extract filters for: 5 runs from cu_hxr beamline",
                expected_output=registry.context_types.RUN_QUERY_FILTERS,
                success_criteria="Filters extracted with beamline=cu_hxr, num_runs=5",
                inputs=[]
            ),
            scenario_description="User asks for runs from cu_hxr (a physical beamline)",
            notes="Output: RUN_QUERY_FILTERS with beamline='cu_hxr', num_runs=5"
        )

        # Example 3: Complex query with multiple filters
        complex_example = OrchestratorExample(
            step=PlannedStep(
                context_key="complex_filters",
                capability="extract_run_filters",
                task_objective="Extract filters for: last 10 neldermead runs optimizing pulse_intensity_p80",
                expected_output=registry.context_types.RUN_QUERY_FILTERS,
                success_criteria="Filters extracted with algorithm, objective, and num_runs",
                inputs=[]
            ),
            scenario_description="User asks for runs with algorithm and objective filters",
            notes="Output: RUN_QUERY_FILTERS with algorithm='neldermead', objective='pulse_intensity_p80', num_runs=10"
        )

        return OrchestratorGuide(
            instructions=textwrap.dedent(f"""
                **When to plan "extract_run_filters" steps:**
                - User query mentions run filtering criteria (beamlines, environments, algorithms, objectives)
                - Query contains ambiguous terminology that needs disambiguation (e.g., "lcls_ii environment")
                - Before query_runs step when filters need to be extracted from natural language
                - User says "last N runs", "recent runs", "most recent run" (extract num_runs, NOT time_range)

                **IMPORTANT: Use extract_run_filters for "last N runs", NOT time_range_parsing:**
                - "last 3 runs" → extract_run_filters (extracts num_runs=3)
                - "recent runs" → extract_run_filters (extracts num_runs=10 by default)
                - "most recent run" → extract_run_filters (extracts num_runs=1)
                - DO NOT use time_range_parsing for these queries!
                - Only use time_range_parsing when user explicitly mentions dates/times (e.g., "runs from last week", "runs on October 15th")

                **How this works:**
                - Extracts structured filters from natural language in task_objective
                - Disambiguates between beamline directories and Badger environment names
                - Handles "last N runs" by extracting num_runs parameter (no time filtering needed)
                - Creates RUN_QUERY_FILTERS context for use by query_runs

                **Critical distinctions:**
                - Beamlines (only 7): cu_hxr, cu_sxr, sc_bsyd, sc_diag0, sc_sxr, sc_hxr, dev
                - Badger environments (many): lcls, lcls_ii, sphere, etc.
                - 'lcls_ii' is a Badger ENVIRONMENT, NOT a beamline!

                **Two-step pattern with query_runs:**
                When user asks for filtered runs, use this pattern:

                Step 1: extract_run_filters to parse query
                        → Creates RUN_QUERY_FILTERS context with num_runs, beamline, algorithm, etc.
                Step 2: query_runs with inputs=[RUN_QUERY_FILTERS from step 1]
                        → Uses parsed filters to find runs (sorted by date, newest first)

                **Output: {registry.context_types.RUN_QUERY_FILTERS}**
                - Contains: num_runs, beamline, algorithm, badger_environment, objective
                - Available to query_runs via inputs
                - Can be inspected before running query

                **Dependencies and sequencing:**
                - Typically comes before query_runs step
                - Results feed into query_runs via inputs
                - No input dependencies (works standalone)
                """).strip(),
            examples=[
                environment_example,
                beamline_example,
                complex_example
            ],
            priority=2  # Should come early, before query_runs
        )

    def _create_classifier_guide(self) -> Optional[TaskClassifierGuide]:
        """Create classifier guide for filter extraction."""

        return TaskClassifierGuide(
            instructions="Determine if the task requires extracting structured filter criteria from a natural language query about Badger runs.",
            examples=[
                ClassifierExample(
                    query="Show me runs from lcls_ii environment",
                    result=True,
                    reason="Query contains filter criteria that need parsing (environment name)"
                ),
                ClassifierExample(
                    query="Find 10 neldermead runs from cu_hxr",
                    result=True,
                    reason="Query contains multiple filter criteria (algorithm, beamline, count)"
                ),
                ClassifierExample(
                    query="Recent runs optimizing pulse_intensity_p80",
                    result=True,
                    reason="Query contains filter criteria (objective, implicit count)"
                ),
                ClassifierExample(
                    query="What is Badger?",
                    result=False,
                    reason="General question, not requesting filtered run search"
                ),
                ClassifierExample(
                    query="Analyze this run",
                    result=False,
                    reason="Refers to existing run, not searching for runs with filters"
                ),
            ],
            actions_if_true=ClassifierActions()
        )
