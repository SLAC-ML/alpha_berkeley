"""Wind Turbine response generation prompts.

This module provides custom response generation prompts for wind turbine analysis,
ensuring consistent formatting with tables, proper industry threshold references,
and educational clarity.
"""

from typing import Optional
import textwrap

from framework.prompts.defaults.response_generation import DefaultResponseGenerationPromptBuilder
from framework.base import OrchestratorGuide, OrchestratorExample, PlannedStep, TaskClassifierGuide
from framework.registry import get_registry


class WindTurbineResponseGenerationPromptBuilder(DefaultResponseGenerationPromptBuilder):
    """Wind turbine-specific response generation prompt builder."""
    
    def get_role_definition(self) -> str:
        """Get the wind turbine-specific role definition."""
        return "You are an expert wind turbine performance analyst providing detailed technical analysis and maintenance recommendations."
    
    def _get_conversational_guidelines(self) -> list[str]:
        """Wind turbine-specific conversational guidelines."""
        return [
            "Be warm, professional, and knowledgeable about wind turbine operations",
            "Answer general questions about turbine monitoring and performance analysis naturally",
            "Respond to greetings and social interactions professionally", 
            "Ask clarifying questions to better understand user needs when appropriate",
            "Provide helpful context about industry standards and best practices when relevant",
            "Be encouraging about the technical assistance available"
        ]
    
    def get_instructions(self) -> str:
        """Get wind turbine-specific instructions with enhanced formatting requirements."""
        return textwrap.dedent("""
            WIND TURBINE ANALYSIS FORMATTING REQUIREMENTS:

            **Data Presentation:**
            - Use well-formatted tables for turbine performance comparisons and rankings
            - Include clear column headers for metrics like capacity factor, efficiency ratio, power output
            - Round numerical values appropriately for readability (e.g., 1 decimal place for percentages)

            **Industry Standards Reference:**
            - When industry thresholds are available in context, reference them explicitly
            - Use retrieved knowledge base values rather than making assumptions
            - Categorize turbine performance relative to actual standards when available

            **Structure for Technical Analysis:**
            - Organize with clear headings (Performance Overview, Rankings, Recommendations)
            - Specify time periods and data scope
            - Prioritize maintenance recommendations with clear reasoning
            - Include any data limitations or warnings
            """).strip()
    
    def get_orchestrator_guide(self) -> Optional[OrchestratorGuide]:
        """Create wind turbine-specific orchestrator guidance for response capability."""
        registry = get_registry()
        
        # Example 1: Full analysis with knowledge retrieval step included
        comprehensive_analysis_example = OrchestratorExample(
            step=PlannedStep(
                context_key="user_response",
                capability="respond",
                task_objective="Present comprehensive wind turbine performance analysis with industry benchmark comparison",
                expected_output="user_response",
                success_criteria="Complete turbine analysis report with performance tables and maintenance priorities using industry standards",
                inputs=[
                    {registry.context_types.ANALYSIS_RESULTS: "performance_analysis_results"},
                    {registry.context_types.TURBINE_KNOWLEDGE: "industry_standards"}
                ]
            ),
            scenario_description="User requested turbine performance analysis against industry standards - previous steps retrieved both performance data and knowledge base thresholds",
            notes="Include TURBINE_KNOWLEDGE because a knowledge_retrieval step was executed to get industry benchmarks for comparison. Use actual threshold values from knowledge base rather than assumptions."
        )
        
        # Example 2: Data-only analysis without knowledge retrieval
        data_only_analysis_example = OrchestratorExample(
            step=PlannedStep(
                context_key="user_response",
                capability="respond",
                task_objective="Present turbine performance data summary and fleet comparison",
                expected_output="user_response", 
                success_criteria="Clear presentation of turbine performance metrics with relative rankings",
                inputs=[
                    {registry.context_types.ANALYSIS_RESULTS: "performance_data"}
                ]
            ),
            scenario_description="User requested a summary of turbine performance data - only analysis results were needed",
            notes="Response focuses on the available analysis data without external reference sources. Use relative comparisons within the provided dataset."
        )
        
        # Example 3: Status inquiry using recent data
        status_inquiry_example = OrchestratorExample(
            step=PlannedStep(
                context_key="user_response",
                capability="respond",
                task_objective="Report current operational status based on recent data",
                expected_output="user_response",
                success_criteria="Clear status update based on available recent data",
                inputs=[
                    {registry.context_types.TURBINE_DATA: "current_readings"}
                ]
            ),
            scenario_description="Simple status inquiry using only current sensor readings",
            notes="Basic status response using only the available sensor data without additional context sources."
        )
        
        return OrchestratorGuide(
            instructions="""
                Plan "respond" as the final step for user queries.
                
                CRITICAL: Only include knowledge base inputs if a knowledge_retrieval step was executed in the plan.
                - When external knowledge was retrieved: Include relevant reference data for comparison
                - When no knowledge step: Focus on analysis within available execution context
                
                Automatically formats data in tables and provides structured analysis.
                Always required as the final step unless asking clarifying questions.
                """,
            examples=[comprehensive_analysis_example, data_only_analysis_example, status_inquiry_example],
            priority=100  # Should come last in prompt ordering
        )
    
    def get_classifier_guide(self) -> Optional[TaskClassifierGuide]:
        """Respond has no classifier - it's orchestrator-driven."""
        return None  # Always available, not detected from user intent
