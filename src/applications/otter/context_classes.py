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
