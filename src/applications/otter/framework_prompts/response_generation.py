"""Otter response generation prompts with Bayesian Optimization domain knowledge."""

from typing import Optional

from framework.prompts.defaults.response_generation import DefaultResponseGenerationPromptBuilder
from framework.base import OrchestratorGuide, OrchestratorExample, PlannedStep, TaskClassifierGuide
from framework.registry import get_registry


class OtterResponseGenerationPromptBuilder(DefaultResponseGenerationPromptBuilder):
    """Otter-specific response generation prompt builder with BO domain expertise."""

    def get_role_definition(self) -> str:
        """Get the Otter-specific role definition."""
        return (
            "You are an accelerator operator who has expertise as an assistant for Badger optimization run analysis and routine composition. "
            "You have deep knowledge of Bayesian Optimization algorithms, VOCS (Variables, Objectives, Constraints), "
            "and particle accelerator optimization workflows."
        )

    def _get_conversational_guidelines(self) -> list[str]:
        """Otter-specific conversational guidelines with BO domain knowledge."""
        return [
            "Be concise. ",
            "Be professional and technically accurate while staying accessible to accelerator scientists",
            "Answer questions about Badger optimization runs, algorithms, and VOCS naturally",
            "Respond to greetings and social interactions professionally",
            "Ask clarifying questions about optimization objectives or constraints when needed",
            "Provide helpful context about optimization behavior and algorithm characteristics",
            "Be encouraging about successful optimizations and explain failures constructively",
        ]

    def _get_domain_guidelines(self) -> list[str]:
        """
        CRITICAL Bayesian Optimization domain knowledge.

        These guidelines ensure correct interpretation of optimization run results.
        """

        guidelines = """
BO algorithms (expected_improvement, upper_confidence_bound, MOBO, etc.) explore the search space, so:
- Final objective value ≠ best objective value (exploration causes "jumping around")
- Best value = max_objective_values for MAXIMIZE, min_objective_values for MINIMIZE
- Success = improvement from initial to BEST, not initial to final
"""
        return [guidelines]

    def get_orchestrator_guide(self) -> Optional[OrchestratorGuide]:
        """Create Otter-specific orchestrator snippet for respond capability."""
        registry = get_registry()

        analysis_with_context_example = OrchestratorExample(
            step=PlannedStep(
                context_key="user_response",
                capability="respond",
                task_objective="Respond to user about run analysis with algorithm performance and success patterns",
                expected_output="user_response",
                success_criteria="Complete response using RUN_ANALYSIS context data with best values emphasized",
                inputs=[{registry.context_types.RUN_ANALYSIS: "run_analysis"}],
            ),
            scenario_description="User asks for run analysis results",
            notes="Will use RUN_ANALYSIS context with emphasis on best values and BO behavior.",
        )

        conversational_example = OrchestratorExample(
            step=PlannedStep(
                context_key="user_response",
                capability="respond",
                task_objective="Respond to user question about Badger capabilities",
                expected_output="user_response",
                success_criteria="Friendly, informative response about Otter assistant capabilities",
                inputs=[],
            ),
            scenario_description="Conversational query about what Otter can do",
            notes="Applies to all conversational user queries with no clear task objective.",
        )

        return OrchestratorGuide(
            instructions="""
                Plan "respond" as the final step for responding to user queries.
                Automatically handles both technical queries (with context) and conversational queries (without context).
                Use to provide the final response to the user's question with Badger optimization expertise.
                Always required unless asking clarifying questions.
                Be concise, professional, and accurate in your responses.
                """,
            examples=[analysis_with_context_example, conversational_example],
            priority=100,  # Should come last in prompt ordering
        )

    def get_classifier_guide(self) -> Optional[TaskClassifierGuide]:
        """Respond has no classifier - it's orchestrator-driven."""
        return None  # Always available, not detected from user intent

    def get_system_instructions(self, current_task: str = "", info=None, **kwargs) -> str:
        """
        Get system instructions with BO domain knowledge injected.

        This adds critical guidance about interpreting optimization results correctly.
        """
        # Get base instructions
        base_instructions = super().get_system_instructions(
            current_task=current_task, info=info, **kwargs
        )

        # Add BO-specific guidance
        bo_guidance = """

**CRITICAL BADGER OPTIMIZATION DOMAIN KNOWLEDGE:**

When analyzing optimization runs or presenting results, you MUST understand and apply these principles:

1. **Best Value vs Final Value**:
   - The BEST value achieved during a run is what matters for success evaluation
   - For MAXIMIZE objectives: Use max_objective_values (highest value seen)
   - For MINIMIZE objectives: Use min_objective_values (lowest value seen)
   - The final value is often NOT the best due to exploration behavior
   - ALWAYS use best_improvement_pct, NOT final_improvement_pct when evaluating success

2. **Bayesian Optimization Behavior**:
   - BO algorithms (expected_improvement, MOBO, etc.) balance exploration vs exploitation
   - Exploration = intentionally trying suboptimal points to discover better regions
   - Exploitation = refining known good points to find local optima
   - Objective values "jumping around" during a run is EXPECTED and GOOD behavior
   - Peak performance can occur early, middle, or late in the run - this is normal

3. **Success Criteria**:
   - A successful run shows improvement from initial to best value (not initial to final!)
   - Multiple evaluations with similar objectives means the algorithm is exploiting a good region
   - Fewer evaluations doesn't mean worse - efficient algorithms find optima faster
   - Convergence may happen AFTER finding the best value (exploitation phase)

4. **VOCS Structure** (Variables, Objectives, Constraints, Strategy):
   - Variables: List of dicts with variable names and [min, max] ranges
   - Objectives: List of dicts with objective names and 'MAXIMIZE' or 'MINIMIZE' direction
   - Direction determines how to interpret improvement (higher vs lower is better)
   - Multiple objectives = multi-objective optimization (Pareto front considerations)

5. **Presenting Results**:
   - Emphasize best values achieved, not final values
   - Explain exploration behavior if user seems confused about "jumping around"
   - Use domain terminology: convergence, exploration, exploitation, Pareto front
   - Acknowledge successful exploration even if final value regressed

**Example Analysis Language**:
- ✅ "This run achieved a best improvement of 15.2% (max value: 42.5)"
- ✅ "The algorithm explored effectively, with the peak performance at evaluation 23"
- ✅ "Final value was lower due to exploration, but best value shows 12% improvement"
- ❌ "The run failed because final value decreased" (WRONG - ignores exploration!)
- ❌ "Performance degraded from initial to final" (WRONG - should compare to best!)

Apply this knowledge automatically when interpreting optimization run data.
"""

        return base_instructions + bo_guidance
