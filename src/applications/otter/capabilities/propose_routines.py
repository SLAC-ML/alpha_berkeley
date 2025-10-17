"""
Propose Routines Capability

Capability for generating optimization routine proposals based on RUN_ANALYSIS context.
Creates actionable routine configurations that can be executed in Badger.
"""

import logging
import textwrap
from typing import Dict, Any, Optional
from collections import Counter

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

logger = get_logger("otter", "propose_routines")
registry = get_registry()


# ====================
# Custom Exceptions
# ====================

class ProposeRoutinesError(Exception):
    """Base class for propose routines errors."""
    pass


class InsufficientContextError(ProposeRoutinesError):
    """Raised when not enough context provided for proposal generation."""
    pass


# ====================
# Capability Definition
# ====================

@capability_node
class ProposeRoutinesCapability(BaseCapability):
    """
    Generate optimization routine proposals based on run analysis.

    This capability takes a RUN_ANALYSIS context as input and creates actionable
    routine configurations based on the pre-computed analysis of successful runs.

    Outputs structured routine proposals with justifications.
    """

    name = "propose_routines"
    description = "Generate routine proposals from analysis"
    provides = ["ROUTINE_PROPOSAL"]
    requires = ["RUN_ANALYSIS"]

    @staticmethod
    async def execute(state: AgentState, **kwargs) -> Dict[str, Any]:
        """Execute routine proposal generation from analysis."""

        step = StateManager.get_current_step(state)
        streamer = get_streamer("otter", "propose_routines", state)

        try:
            # Get context manager and parameters
            context_manager = ContextManager(state)
            step_parameters = step.get("parameters", {})

            # Extract parameters
            target_beamline = step_parameters.get("target_beamline")
            target_objective = step_parameters.get("target_objective")
            num_proposals = int(step_parameters.get("num_proposals", 3))

            # Get RUN_ANALYSIS context from inputs
            step_inputs = step.get("inputs", [])
            if not step_inputs:
                raise InsufficientContextError("No analysis context provided")

            analysis_context = None
            for input_item in step_inputs:
                if "RUN_ANALYSIS" in input_item:
                    analysis_key = input_item["RUN_ANALYSIS"]
                    analysis_context = context_manager.get_context(
                        registry.context_types.RUN_ANALYSIS,
                        analysis_key
                    )
                    break

            if not analysis_context:
                raise InsufficientContextError("No valid RUN_ANALYSIS context found")

            streamer.status("Generating proposals from analysis...")

            # Extract analysis data
            analysis_data = analysis_context.analysis_data
            overview = analysis_data.get("overview", {})
            algo_performance = analysis_data.get("algorithm_performance", {})
            beamline_dist = analysis_data.get("beamline_distribution", {})
            badger_env_dist = analysis_data.get("badger_environment_distribution", {})
            objective_analysis = analysis_data.get("objective_analysis", {})
            success_patterns = analysis_data.get("success_patterns", {})

            # Get key metrics
            total_runs = overview.get("total_runs_analyzed", 0)
            avg_evaluations = overview.get("avg_evaluations_per_run", 100)
            top_performers = success_patterns.get("top_performers", [])
            top_algorithms = success_patterns.get("top_algorithms", {})

            # Extract reference run names from top performers
            reference_runs = [p["run_name"] for p in top_performers[:5]]

            # Determine best configurations
            algorithm_counts = Counter(top_algorithms)
            beamline_counts = Counter(beamline_dist)
            badger_env_counts = Counter(badger_env_dist)

            # Get most common objectives
            objective_list = [
                {name: data.get("direction", "MAXIMIZE")}
                for name, data in sorted(
                    objective_analysis.items(),
                    key=lambda x: x[1].get("num_runs", 0),
                    reverse=True
                )
            ]

            # ====================
            # Generate Proposals
            # ====================
            streamer.status(f"Generating {num_proposals} proposals...")

            proposals = []

            # Proposal 1: Best Algorithm
            if algorithm_counts and objective_list:
                best_algo = algorithm_counts.most_common(1)[0][0]
                best_algo_count = algorithm_counts[best_algo]
                best_beamline = target_beamline or (
                    beamline_counts.most_common(1)[0][0] if beamline_counts else "cu_hxr"
                )
                best_env = badger_env_counts.most_common(1)[0][0] if badger_env_counts else "lcls"

                proposal_1 = {
                    "proposal_name": "Best Algorithm Configuration",
                    "algorithm": best_algo,
                    "beamline": best_beamline,
                    "badger_environment": best_env,
                    "estimated_evaluations": int(avg_evaluations),
                    "objectives": objective_list[:min(2, len(objective_list))],
                    "variables": [],  # Note: Variables not available in aggregate analysis
                    "justification": f"Based on analysis of {best_algo_count} top-performing runs using {best_algo}. "
                                   f"This algorithm showed best performance across {total_runs} analyzed runs.",
                    "confidence": "high" if best_algo_count >= 3 else "medium",
                    "reference_runs": reference_runs[:3]
                }
                proposals.append(proposal_1)

            # Proposal 2: Conservative Alternative
            if len(algorithm_counts) > 1 and len(proposals) < num_proposals and objective_list:
                second_algo = algorithm_counts.most_common(2)[1][0]
                second_algo_count = algorithm_counts[second_algo]

                proposal_2 = {
                    "proposal_name": "Conservative Alternative",
                    "algorithm": second_algo,
                    "beamline": target_beamline or (
                        beamline_counts.most_common(1)[0][0] if beamline_counts else "cu_hxr"
                    ),
                    "badger_environment": badger_env_counts.most_common(1)[0][0] if badger_env_counts else "lcls",
                    "estimated_evaluations": int(avg_evaluations * 0.8),
                    "objectives": objective_list[:min(2, len(objective_list))],
                    "variables": [],
                    "justification": f"Alternative using {second_algo}, proven in {second_algo_count} successful runs. "
                                   f"Lower evaluation budget for faster results.",
                    "confidence": "medium",
                    "reference_runs": reference_runs[:2]
                }
                proposals.append(proposal_2)

            # Proposal 3: Exploration
            if len(proposals) < num_proposals and objective_list:
                exploration_algo = algorithm_counts.most_common(1)[0][0]
                if len(algorithm_counts) > 2:
                    exploration_algo = algorithm_counts.most_common(3)[2][0]

                proposal_3 = {
                    "proposal_name": "Exploration Configuration",
                    "algorithm": exploration_algo,
                    "beamline": target_beamline or (
                        beamline_counts.most_common(1)[0][0] if beamline_counts else "cu_hxr"
                    ),
                    "badger_environment": badger_env_counts.most_common(1)[0][0] if badger_env_counts else "lcls",
                    "estimated_evaluations": int(avg_evaluations * 1.5),
                    "objectives": objective_list[:min(3, len(objective_list))],
                    "variables": [],
                    "justification": f"Exploration-focused configuration with extended evaluation budget ({int(avg_evaluations * 1.5)} evals). "
                                   f"Based on successful patterns from analysis.",
                    "confidence": "medium",
                    "reference_runs": reference_runs[:3]
                }
                proposals.append(proposal_3)

            # Build result
            result = {
                "num_proposals": len(proposals),
                "proposals": proposals[:num_proposals],
                "generation_context": {
                    "total_runs_analyzed": total_runs,
                    "analysis_based": True,
                    "target_beamline": target_beamline,
                    "target_objective": target_objective,
                    "algorithm_distribution": dict(algorithm_counts),
                    "typical_evaluation_budget": int(avg_evaluations)
                },
                "usage_notes": [
                    "These proposals are based on pre-computed run analysis",
                    "Variables must be specified manually (not available in aggregate analysis)",
                    "Evaluation budgets are estimates from historical data",
                    "Confidence levels: high (3+ ref runs), medium (1-2 ref runs)",
                    "Reference runs can be examined for detailed configurations"
                ]
            }

            streamer.status(f"Generated {len(proposals)} proposals!")
            logger.success(f"Successfully generated {len(proposals)} proposals from analysis")

            # Create and store context
            from applications.otter.context_classes import RoutineProposalContext

            proposal_context = RoutineProposalContext(proposal_data=result)

            context_key = step.get("context_key", "routine_proposals")
            return StateManager.store_context(
                state,
                registry.context_types.ROUTINE_PROPOSAL,
                context_key,
                proposal_context
            )

        except InsufficientContextError as e:
            logger.error(f"Insufficient context: {e}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    @staticmethod
    def classify_error(exc: Exception, context: dict) -> ErrorClassification:
        """Error classification for propose routines capability."""

        if isinstance(exc, InsufficientContextError):
            return ErrorClassification(
                severity=ErrorSeverity.CRITICAL,
                user_message=f"Cannot generate proposals: {str(exc)}",
                metadata={
                    "technical_details": str(exc),
                    "resolution": "Ensure RUN_ANALYSIS context is provided as input"
                }
            )
        else:
            return ErrorClassification(
                severity=ErrorSeverity.RETRIABLE,
                user_message=f"Proposal generation error: {str(exc)}",
                metadata={"technical_details": str(exc)}
            )

    def _create_orchestrator_guide(self) -> Optional[OrchestratorGuide]:
        """Create guide for orchestrator."""

        example = OrchestratorExample(
            step=PlannedStep(
                context_key="routine_proposals",
                capability="propose_routines",
                task_objective="Generate routine proposals from analysis",
                expected_output="ROUTINE_PROPOSAL",
                success_criteria="Proposals generated",
                inputs=[{"RUN_ANALYSIS": "run_analysis"}],
                parameters={"num_proposals": 3}
            ),
            scenario_description="Generate proposals from analysis",
            notes="Requires RUN_ANALYSIS context from analyze_runs step"
        )

        return OrchestratorGuide(
            instructions=textwrap.dedent("""
                **When to use propose_routines:**
                - User asks for routine recommendations
                - User wants algorithm/configuration suggestions

                **CRITICAL: Requires RUN_ANALYSIS input!**

                **Workflow:**
                Step 1: query_runs - Load runs
                Step 2: analyze_runs - Analyze patterns
                Step 3: propose_routines - Generate proposals (inputs=[{{"RUN_ANALYSIS": "key"}}])
                Step 4: respond - Present to user

                **Input:** Single RUN_ANALYSIS context
                **Output:** ROUTINE_PROPOSAL context with proposals
                """).strip(),
            examples=[example],
            priority=7
        )

    def _create_classifier_guide(self) -> Optional[TaskClassifierGuide]:
        """Create classifier guide."""
        return TaskClassifierGuide(
            instructions="Identify routine proposal requests.",
            examples=[
                ClassifierExample(
                    query="Suggest a routine",
                    result=True,
                    reason="Direct proposal request"
                ),
                ClassifierExample(
                    query="What should I try?",
                    result=True,
                    reason="Asks for recommendations"
                ),
                ClassifierExample(
                    query="Show me recent runs",
                    result=False,
                    reason="Query, not proposal"
                ),
            ],
            actions_if_true=ClassifierActions()
        )
