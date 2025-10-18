"""
Context Classes for Otter Application

All context classes use Pydantic for automatic serialization and type safety.
They extend CapabilityContext to provide framework integration and rich documentation.
"""

from pydantic import Field
from typing import Dict, Any, List, Optional, ClassVar
from datetime import datetime

from framework.context.base import CapabilityContext


class BadgerRunContext(CapabilityContext):
    """
    Framework context for Badger optimization run data.

    This context stores metadata about a single Badger optimization run,
    including configuration (VOCS), results summary, and provenance information.

    Note: Full evaluation data is NOT included in this context (can be 100+ MB).
    Only metadata and summary statistics are stored.
    """

    CONTEXT_TYPE: ClassVar[str] = "BADGER_RUN"
    CONTEXT_CATEGORY: ClassVar[str] = "OPTIMIZATION_DATA"

    # ====================
    # Identification
    # ====================
    run_filename: str = Field(
        description="Run filename relative to archive root (e.g., 'cu_hxr/2025/2025-09/2025-09-13/lcls-2025-09-13-065422.yaml')"
    )
    run_name: str = Field(
        description="Human-readable run name (e.g., 'cobalt-boar', 'emerald-fox')"
    )
    timestamp: datetime = Field(
        description="Run execution timestamp"
    )

    # ====================
    # Configuration
    # ====================
    beamline: str = Field(
        description="Beamline name from archive directory structure (e.g., 'cu_hxr', 'cu_sxr', 'lcls_ii')"
    )
    badger_environment: str = Field(
        description="Badger environment name from run file (e.g., 'lcls', 'sphere', 'epics')"
    )
    algorithm: str = Field(
        description="Optimization algorithm used (e.g., 'neldermead', 'LiGPS', 'cmaes')"
    )

    # ====================
    # VOCS (Variables, Objectives, Constraints, Strategy)
    # Matches Badger's native VOCS structure for consistency
    # ====================
    variables: List[Dict[str, List[float]]] = Field(
        description="List of variables with their ranges. Each dict has variable name as key and [min, max] as value. "
                    "Example: [{'QUAD:LTUH:620:BCTRL': [-46.23, -41.83]}, {'QUAD:LTUH:640:BCTRL': [47.68, 52.69]}]. "
                    "Order is preserved (Python 3.7+ dict ordering)."
    )
    objectives: List[Dict[str, str]] = Field(
        description="List of objectives with their optimization directions. Each dict has objective name as key and 'MAXIMIZE' or 'MINIMIZE' as value. "
                    "Example: [{'pulse_intensity_p80': 'MAXIMIZE'}]. "
                    "Order is preserved (Python 3.7+ dict ordering)."
    )
    constraints: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of constraints (empty if no constraints). Structure matches Badger VOCS format."
    )

    # ====================
    # Results Summary
    # ====================
    num_evaluations: int = Field(
        description="Number of evaluations performed during the run"
    )
    initial_objective_values: Optional[Dict[str, float]] = Field(
        default=None,
        description="Initial values of objectives at start of run"
    )
    min_objective_values: Optional[Dict[str, float]] = Field(
        default=None,
        description="Minimum values achieved for each objective across all evaluations"
    )
    max_objective_values: Optional[Dict[str, float]] = Field(
        default=None,
        description="Maximum values achieved for each objective across all evaluations"
    )
    final_objective_values: Optional[Dict[str, float]] = Field(
        default=None,
        description="Final values of objectives at end of run"
    )

    # ====================
    # Optional Metadata
    # ====================
    description: Optional[str] = Field(
        default="",
        description="User-provided run description"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="User-provided tags for categorization"
    )

    def _get_variable_names(self) -> List[str]:
        """Extract variable names from VOCS structure."""
        return [list(var_dict.keys())[0] for var_dict in self.variables]

    def _get_objective_names(self) -> List[str]:
        """Extract objective names from VOCS structure."""
        return [list(obj_dict.keys())[0] for obj_dict in self.objectives]

    def _get_objective_direction(self, obj_name: str) -> str:
        """Get optimization direction for a specific objective."""
        for obj_dict in self.objectives:
            if obj_name in obj_dict:
                return obj_dict[obj_name]
        return 'MAXIMIZE'  # Default

    def get_access_details(self, key_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Rich description for LLM consumption with detailed access patterns.

        This method provides comprehensive guidance to the LLM on how to access
        the run data, including examples and critical notes.

        IMPORTANT: This is consumed by the LLM in downstream capabilities,
        so it must be detailed and accurate.
        """
        key_ref = key_name if key_name else "key_name"

        # Calculate improvement using direction-aware logic
        improvement_info = {}
        objective_names = self._get_objective_names()
        if self.initial_objective_values and self.final_objective_values:
            for obj in objective_names:
                if obj in self.initial_objective_values and obj in self.final_objective_values:
                    initial = self.initial_objective_values[obj]
                    final = self.final_objective_values[obj]
                    direction = self._get_objective_direction(obj)

                    # Get min/max if available
                    min_val = self.min_objective_values.get(obj) if self.min_objective_values else None
                    max_val = self.max_objective_values.get(obj) if self.max_objective_values else None

                    obj_info = {
                        "initial": initial,
                        "final": final,
                        "direction": direction,
                    }

                    if min_val is not None:
                        obj_info["min"] = min_val
                    if max_val is not None:
                        obj_info["max"] = max_val

                    # Calculate improvement based on direction
                    if initial != 0:
                        if direction == 'MAXIMIZE':
                            # For maximization: positive change is improvement
                            final_improvement = ((final - initial) / abs(initial)) * 100
                            best_improvement = ((max_val - initial) / abs(initial)) * 100 if max_val is not None else final_improvement
                            obj_info["final_improvement_pct"] = final_improvement
                            obj_info["best_improvement_pct"] = best_improvement
                        else:  # MINIMIZE
                            # For minimization: negative change is improvement (lower is better)
                            final_improvement = ((initial - final) / abs(initial)) * 100
                            best_improvement = ((initial - min_val) / abs(initial)) * 100 if min_val is not None else final_improvement
                            obj_info["final_improvement_pct"] = final_improvement
                            obj_info["best_improvement_pct"] = best_improvement

                    improvement_info[obj] = obj_info

        return {
            "run_identification": {
                "name": self.run_name,
                "filename": self.run_filename,
                "timestamp": self.timestamp.isoformat(),
                "beamline": self.beamline,
                "badger_environment": self.badger_environment,
            },
            "optimization_config": {
                "algorithm": self.algorithm,
                "num_variables": len(self.variables),
                "num_objectives": len(self.objectives),
                "num_constraints": len(self.constraints),
            },
            "vocs_details": {
                "variables": self.variables,  # List of dicts: [{'var_name': [min, max]}, ...]
                "objectives": self.objectives,  # List of dicts: [{'obj_name': 'MAXIMIZE'}, ...]
                "constraints": self.constraints if self.constraints else [],
            },
            "results_summary": {
                "num_evaluations": self.num_evaluations,
                "improvement": improvement_info if improvement_info else "Initial/final values not available",
            },
            "CRITICAL_ACCESS_PATTERNS": {
                "get_algorithm": f"context.{self.CONTEXT_TYPE}.{key_ref}.algorithm",
                "get_variables": f"context.{self.CONTEXT_TYPE}.{key_ref}.variables",
                "get_objectives": f"context.{self.CONTEXT_TYPE}.{key_ref}.objectives",
                "get_num_evaluations": f"context.{self.CONTEXT_TYPE}.{key_ref}.num_evaluations",
                "get_timestamp": f"context.{self.CONTEXT_TYPE}.{key_ref}.timestamp",
                "get_beamline": f"context.{self.CONTEXT_TYPE}.{key_ref}.beamline",
                "get_badger_environment": f"context.{self.CONTEXT_TYPE}.{key_ref}.badger_environment",
            },
            "example_usage": f"context.{self.CONTEXT_TYPE}.{key_ref}.algorithm gives '{self.algorithm}', "
                            f"context.{self.CONTEXT_TYPE}.{key_ref}.variables gives {self.variables[:min(2, len(self.variables))]}...",
            "IMPORTANT_NOTES": [
                "Full evaluation data is NOT included in this context (too large - can be 100+ MB)",
                "Only metadata and summary statistics are available",
                "To access full data, use run_filename to reload from archive if needed",
                "Timestamp is a Python datetime object - supports full datetime operations",
                "Variables are List[Dict[str, List[float]]] - each dict has var_name: [min, max]",
                "Objectives are List[Dict[str, str]] - each dict has obj_name: 'MAXIMIZE' or 'MINIMIZE'",
                "Order is preserved in variables and objectives (Python 3.7+ dict ordering)",
            ],
            "datetime_features": "Full datetime functionality: arithmetic, comparison, formatting with .strftime(), timezone operations"
        }

    def get_summary(self, key_name: Optional[str] = None) -> Dict[str, Any]:
        """
        FOR HUMAN DISPLAY: Create readable summary for UI/debugging/response generation.

        This is what the user will see in the final response, so it should be
        clear, concise, and informative.
        """
        # Calculate improvement summary with direction awareness
        improvement_summary = []
        objective_names = self._get_objective_names()
        if self.initial_objective_values and self.final_objective_values:
            for obj in objective_names:
                if obj in self.initial_objective_values and obj in self.final_objective_values:
                    initial = self.initial_objective_values[obj]
                    final = self.final_objective_values[obj]
                    direction = self._get_objective_direction(obj)

                    # Get min/max if available
                    min_val = self.min_objective_values.get(obj) if self.min_objective_values else None
                    max_val = self.max_objective_values.get(obj) if self.max_objective_values else None

                    if initial != 0:
                        if direction == 'MAXIMIZE':
                            # For maximization: higher is better
                            final_improvement = ((final - initial) / abs(initial)) * 100
                            best_improvement = ((max_val - initial) / abs(initial)) * 100 if max_val is not None else final_improvement
                            best_val = max_val if max_val is not None else final

                            improvement_label = "improved" if final_improvement > 0 else "decreased"
                            improvement_summary.append(
                                f"{obj} (MAXIMIZE): {initial:.4f} → {final:.4f} ({improvement_label} by {abs(final_improvement):.1f}%), "
                                f"best: {best_val:.4f} ({best_improvement:+.1f}%)"
                            )
                        else:  # MINIMIZE
                            # For minimization: lower is better
                            final_improvement = ((initial - final) / abs(initial)) * 100
                            best_improvement = ((initial - min_val) / abs(initial)) * 100 if min_val is not None else final_improvement
                            best_val = min_val if min_val is not None else final

                            improvement_label = "improved" if final_improvement > 0 else "worsened"
                            improvement_summary.append(
                                f"{obj} (MINIMIZE): {initial:.4f} → {final:.4f} ({improvement_label} by {abs(final_improvement):.1f}%), "
                                f"best: {best_val:.4f} ({best_improvement:+.1f}%)"
                            )

        # Format timestamp
        timestamp_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Build summary
        summary = {
            "type": "Badger Optimization Run",
            "run_name": self.run_name,
            "timestamp": timestamp_str,
            "beamline": self.beamline,
            "badger_environment": self.badger_environment,
            "algorithm": self.algorithm,
            "vocs": {
                "variables": self.variables,
                "objectives": self.objectives,
                "constraints": self.constraints if self.constraints else [],
            },
            "execution": {
                "num_evaluations": self.num_evaluations,
                "improvement": improvement_summary if improvement_summary else "No improvement data available",
            },
        }

        if self.description:
            summary["description"] = self.description

        if self.tags:
            summary["tags"] = self.tags

        return summary


class BadgerRunsContext(CapabilityContext):
    """
    Container context for multiple Badger optimization runs from query_runs capability.

    This context stores a collection of BadgerRunContext objects, following the same
    pattern as PVValues in ALS assistant (container holding multiple items).
    """

    CONTEXT_TYPE: ClassVar[str] = "BADGER_RUNS"
    CONTEXT_CATEGORY: ClassVar[str] = "OPTIMIZATION_DATA"

    runs: list[BadgerRunContext] = Field(
        description="List of Badger run contexts"
    )

    @property
    def run_count(self) -> int:
        """Number of runs in this collection."""
        return len(self.runs)

    def get_access_details(self, key_name: Optional[str] = None) -> Dict[str, Any]:
        """Rich description for LLM consumption."""
        key_ref = key_name if key_name else "key_name"

        # Preview first few runs
        preview_count = min(3, len(self.runs))
        preview_runs = [
            {
                "run_name": run.run_name,
                "timestamp": run.timestamp.isoformat(),
                "algorithm": run.algorithm,
                "beamline": run.beamline,
            }
            for run in self.runs[:preview_count]
        ]

        return {
            "run_count": self.run_count,
            "preview": preview_runs,
            "data_structure": "List[BadgerRunContext] - access individual runs via indexing",
            "access_pattern": f"context.{self.CONTEXT_TYPE}.{key_ref}.runs[index]",
            "example_usage": f"context.{self.CONTEXT_TYPE}.{key_ref}.runs[0].algorithm gives first run's algorithm, "
                           f"context.{self.CONTEXT_TYPE}.{key_ref}.run_count gives total number of runs",
            "iteration": f"Use 'for run in context.{self.CONTEXT_TYPE}.{key_ref}.runs' to iterate over all runs",
            "IMPORTANT_NOTES": [
                "This is a container holding multiple BadgerRunContext objects",
                "Access individual runs via .runs[index] - zero-indexed",
                "Each run has full metadata: algorithm, variables, objectives, etc.",
                "Use .run_count property to get total number of runs",
            ]
        }

    def get_summary(self, key_name: Optional[str] = None) -> Dict[str, Any]:
        """FOR HUMAN DISPLAY: Create readable summary with full run details."""
        runs_summary = []
        for idx, run in enumerate(self.runs):
            # Get full summary from each run's get_summary() method
            run_summary = run.get_summary()
            # Add index for reference
            run_summary["index"] = idx
            runs_summary.append(run_summary)

        return {
            "type": "Badger Runs Collection",
            "run_count": self.run_count,
            "runs": runs_summary,
        }


class RunAnalysisContext(CapabilityContext):
    """
    Context for storing run analysis results from analyze_runs capability.

    This flexible context stores statistical analysis and pattern identification
    from multiple Badger optimization runs.
    """

    CONTEXT_TYPE: ClassVar[str] = "RUN_ANALYSIS"
    CONTEXT_CATEGORY: ClassVar[str] = "COMPUTATIONAL_DATA"

    analysis_data: Dict[str, Any] = Field(
        description="Complete analysis results including algorithm performance, beamline distribution, "
                    "objective analysis, and success patterns"
    )

    def get_access_details(self, key_name: Optional[str] = None) -> Dict[str, Any]:
        """Rich description for LLM consumption."""
        key_ref = key_name if key_name else "key_name"

        # Extract key information for preview
        overview = self.analysis_data.get("overview", {})
        total_runs = overview.get("total_runs_analyzed", 0)

        return {
            "total_runs_analyzed": total_runs,
            "available_sections": list(self.analysis_data.keys()),
            "data_structure": "Dictionary with sections: overview, algorithm_performance, beamline_distribution, "
                            "badger_environment_distribution, objective_analysis, success_patterns",
            "access_pattern": f"context.{self.CONTEXT_TYPE}.{key_ref}.analysis_data['section_name']",
            "example_usage": f"context.{self.CONTEXT_TYPE}.{key_ref}.analysis_data['algorithm_performance'] gives algorithm stats, "
                           f"context.{self.CONTEXT_TYPE}.{key_ref}.analysis_data['success_patterns']['top_performers'] gives best runs",
            "IMPORTANT_NOTES": [
                "All analysis data is in .analysis_data dictionary",
                "Use bracket notation for accessing sections",
                "Success patterns include top performers with improvement percentages",
                "Algorithm performance includes average improvement and evaluation counts"
            ]
        }

    def get_summary(self, key_name: Optional[str] = None) -> Dict[str, Any]:
        """
        FOR HUMAN DISPLAY: Create readable summary for UI/response generation.
        """
        overview = self.analysis_data.get("overview", {})
        algo_perf = self.analysis_data.get("algorithm_performance", {})
        success_patterns = self.analysis_data.get("success_patterns", {})
        per_run_details = self.analysis_data.get("per_run_details", {})

        # Format algorithm performance summary
        algo_summary = {}
        for algo, stats in algo_perf.items():
            algo_summary[algo] = {
                "runs": stats.get("num_runs", 0),
                "avg_improvement": f"{stats.get('avg_improvement_pct', 0):.1f}%"
            }

        # Format top performers
        top_performers = success_patterns.get("top_performers", [])[:3]

        return {
            "type": "Run Analysis Results",
            "overview": overview,
            "algorithm_summary": algo_summary,
            "top_performers": top_performers,
            "per_run_details": per_run_details,  # Include full per-run data for table formatting
            "available_sections": list(self.analysis_data.keys())
        }


class RoutineProposalContext(CapabilityContext):
    """
    Context for storing routine proposals from propose_routines capability.

    This context stores generated optimization routine proposals based on
    historical successful runs.
    """

    CONTEXT_TYPE: ClassVar[str] = "ROUTINE_PROPOSAL"
    CONTEXT_CATEGORY: ClassVar[str] = "COMPUTATIONAL_DATA"

    proposal_data: Dict[str, Any] = Field(
        description="Complete proposal data including multiple proposals, generation context, and usage notes"
    )

    def get_access_details(self, key_name: Optional[str] = None) -> Dict[str, Any]:
        """Rich description for LLM consumption."""
        key_ref = key_name if key_name else "key_name"

        # Extract key information
        num_proposals = self.proposal_data.get("num_proposals", 0)
        proposals = self.proposal_data.get("proposals", [])

        # Get first proposal as example
        example_proposal = proposals[0] if proposals else {}

        return {
            "num_proposals": num_proposals,
            "available_fields": list(self.proposal_data.keys()),
            "data_structure": "Dictionary with: num_proposals (int), proposals (list of dicts), "
                            "generation_context (dict), usage_notes (list)",
            "proposal_structure": "Each proposal has: proposal_name, algorithm, beamline, badger_environment, "
                                "estimated_evaluations, objectives (list), variables (list), "
                                "justification, confidence, reference_runs (list)",
            "access_pattern": f"context.{self.CONTEXT_TYPE}.{key_ref}.proposal_data['proposals'][0]['algorithm']",
            "example_usage": f"context.{self.CONTEXT_TYPE}.{key_ref}.proposal_data['proposals'][0] gives first proposal, "
                           f"context.{self.CONTEXT_TYPE}.{key_ref}.proposal_data['generation_context'] gives analysis context",
            "IMPORTANT_NOTES": [
                "All proposal data is in .proposal_data dictionary",
                "proposals is a list - use indexing to access individual proposals",
                "Each proposal includes justification and confidence level",
                "generation_context provides information about how proposals were generated",
                "reference_runs lists the successful runs each proposal is based on"
            ]
        }

    def get_summary(self, key_name: Optional[str] = None) -> Dict[str, Any]:
        """
        FOR HUMAN DISPLAY: Create readable summary for UI/response generation.
        """
        num_proposals = self.proposal_data.get("num_proposals", 0)
        proposals = self.proposal_data.get("proposals", [])
        gen_context = self.proposal_data.get("generation_context", {})

        # Summarize each proposal
        proposal_summaries = []
        for proposal in proposals:
            proposal_summaries.append({
                "name": proposal.get("proposal_name", "Unknown"),
                "algorithm": proposal.get("algorithm", "Unknown"),
                "beamline": proposal.get("beamline", "Unknown"),
                "environment": proposal.get("badger_environment", "Unknown"),
                "evaluations": proposal.get("estimated_evaluations", 0),
                "confidence": proposal.get("confidence", "unknown"),
                "num_objectives": len(proposal.get("objectives", [])),
                "num_variables": len(proposal.get("variables", []))
            })

        return {
            "type": "Routine Proposals",
            "num_proposals": num_proposals,
            "proposals": proposal_summaries,
            "generation_summary": {
                "total_runs_analyzed": gen_context.get("total_runs_analyzed", 0),
                "successful_runs_used": gen_context.get("successful_runs_used", 0)
            }
        }


class RunQueryFilters(CapabilityContext):
    """
    Context for structured run query filters extracted from natural language.

    This context stores parsed filter criteria for querying Badger runs,
    ensuring correct interpretation of user queries (e.g., distinguishing
    between beamline directories and Badger environment names).
    """

    CONTEXT_TYPE: ClassVar[str] = "RUN_QUERY_FILTERS"
    CONTEXT_CATEGORY: ClassVar[str] = "METADATA"

    num_runs: Optional[int] = Field(
        default=None,
        description="Number of runs to retrieve (None = use default)"
    )
    beamline: Optional[str] = Field(
        default=None,
        description="Beamline directory filter - ONLY these 7 values: cu_hxr, cu_sxr, sc_bsyd, sc_diag0, sc_sxr, sc_hxr, dev"
    )
    algorithm: Optional[str] = Field(
        default=None,
        description="Optimization algorithm filter (e.g., 'expected_improvement', 'neldermead', 'mobo', 'rcds')"
    )
    badger_environment: Optional[str] = Field(
        default=None,
        description="Badger software environment filter (e.g., 'lcls', 'lcls_ii', 'sphere')"
    )
    objective: Optional[str] = Field(
        default=None,
        description="Objective function name filter (e.g., 'pulse_intensity_p80')"
    )
    sort_order: Optional[str] = Field(
        default="newest_first",
        description="Sort order for results - 'newest_first' (default) or 'oldest_first'"
    )

    def to_parameters(self) -> Dict[str, Any]:
        """
        Convert filter context to query_runs parameters format.

        Returns:
            Dict with non-None filter values suitable for query_runs parameters
        """
        params = {}
        if self.num_runs is not None:
            params["num_runs"] = self.num_runs
        if self.beamline is not None:
            params["beamline"] = self.beamline
        if self.algorithm is not None:
            params["algorithm"] = self.algorithm
        if self.badger_environment is not None:
            params["badger_environment"] = self.badger_environment
        if self.objective is not None:
            params["objective"] = self.objective
        if self.sort_order is not None:
            params["sort_order"] = self.sort_order
        return params

    def get_access_details(self, key_name: Optional[str] = None) -> Dict[str, Any]:
        """Rich description for LLM consumption."""
        key_ref = key_name if key_name else "key_name"

        active_filters = self.to_parameters()

        return {
            "active_filters": active_filters,
            "num_filters": len(active_filters),
            "access_pattern": f"context.{self.CONTEXT_TYPE}.{key_ref}.to_parameters()",
            "example_usage": f"context.{self.CONTEXT_TYPE}.{key_ref}.to_parameters() returns {active_filters}",
            "IMPORTANT_NOTES": [
                "Use .to_parameters() method to get filter dict for query_runs",
                "Only beamlines: cu_hxr, cu_sxr, sc_bsyd, sc_diag0, sc_sxr, sc_hxr, dev",
                "Badger environments are separate from beamlines (e.g., 'lcls_ii' is environment, not beamline)",
                "sort_order can be 'newest_first' (default) or 'oldest_first'"
            ]
        }

    def get_summary(self, key_name: Optional[str] = None) -> Dict[str, Any]:
        """FOR HUMAN DISPLAY: Create readable summary."""
        active_filters = self.to_parameters()

        return {
            "type": "Run Query Filters",
            "filters": active_filters,
            "filter_count": len(active_filters)
        }
