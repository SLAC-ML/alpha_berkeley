"""
Otter Application Registry Configuration

This module defines the component registry for the Otter Badger optimization run assistant.
All Otter-specific capabilities, context classes, and data sources are declared here.
"""

from framework.registry import (
    CapabilityRegistration,
    ContextClassRegistration,
    DataSourceRegistration,
    FrameworkPromptProviderRegistration,
    RegistryConfig,
    RegistryConfigProvider
)


class OtterRegistryProvider(RegistryConfigProvider):
    """Registry provider for Otter application."""

    def get_registry_config(self) -> RegistryConfig:
        """
        Get Otter application registry configuration.

        Returns:
            RegistryConfig: Registry configuration for Otter application
        """
        return RegistryConfig(

            # ====================
            # Capabilities
            # ====================
            capabilities=[
                CapabilityRegistration(
                    name="extract_run_filters",
                    module_path="applications.otter.capabilities.extract_run_filters",
                    class_name="ExtractRunFiltersCapability",
                    description="Extract structured run query filters from natural language",
                    provides=["RUN_QUERY_FILTERS"],
                    requires=[]
                ),
                CapabilityRegistration(
                    name="query_runs",
                    module_path="applications.otter.capabilities.query_runs",
                    class_name="QueryRunsCapability",
                    description="Query Badger optimization runs from archive using filters from extract_run_filters",
                    provides=["BADGER_RUNS"],  # Returns container with multiple runs
                    requires=["RUN_QUERY_FILTERS"]
                ),
                CapabilityRegistration(
                    name="analyze_runs",
                    module_path="applications.otter.capabilities.analyze_runs",
                    class_name="AnalyzeRunsCapability",
                    description="Analyze and compare multiple runs",
                    provides=["RUN_ANALYSIS"],
                    requires=["BADGER_RUNS"]  # Updated to use BADGER_RUNS container
                ),
                # TODO: propose_routines capability needs rework - disabled for now
                # The current implementation doesn't properly generate actionable routines
                # Will be re-enabled after rework with proper VOCS generation
                # CapabilityRegistration(
                #     name="propose_routines",
                #     module_path=(
                #         "applications.otter.capabilities.propose_routines"
                #     ),
                #     class_name="ProposeRoutinesCapability",
                #     description="Generate routine proposals from analysis",
                #     provides=["ROUTINE_PROPOSAL"],
                #     requires=["RUN_ANALYSIS"]
                # ),
                # Future capabilities:
                # - search_runs: Find runs matching complex criteria (VOCS-based filtering)
                # - infer_terminology: Map ambiguous terms to actual objective/variable names
                # - compose_routine: Generate complete Badger routine from specifications
            ],

            # ====================
            # Context Classes
            # ====================
            context_classes=[
                ContextClassRegistration(
                    context_type="RUN_QUERY_FILTERS",
                    module_path="applications.otter.context_classes",
                    class_name="RunQueryFilters"
                ),
                ContextClassRegistration(
                    context_type="BADGER_RUN",
                    module_path="applications.otter.context_classes",
                    class_name="BadgerRunContext"
                ),
                ContextClassRegistration(
                    context_type="BADGER_RUNS",
                    module_path="applications.otter.context_classes",
                    class_name="BadgerRunsContext"
                ),
                ContextClassRegistration(
                    context_type="RUN_ANALYSIS",
                    module_path="applications.otter.context_classes",
                    class_name="RunAnalysisContext"
                ),
                # TODO: Re-enable after propose_routines capability rework
                # ContextClassRegistration(
                #     context_type="ROUTINE_PROPOSAL",
                #     module_path="applications.otter.context_classes",
                #     class_name="RoutineProposalContext"
                # ),
                # Future context classes:
                # - ROUTINE_SPEC: For VOCS specifications
                # - BADGER_ROUTINE: For complete executable routines
            ],

            # ====================
            # Data Sources
            # ====================
            data_sources=[
                DataSourceRegistration(
                    name="badger_archive",
                    module_path="applications.otter.data_sources.badger_archive",
                    class_name="BadgerArchiveDataSource",
                    description="Badger optimization runs archive with health monitoring",
                    health_check_required=True
                )
            ],

            # ====================
            # Framework Prompt Providers
            # ====================
            # Otter-specific prompts inject Bayesian Optimization domain knowledge
            framework_prompt_providers=[
                FrameworkPromptProviderRegistration(
                    application_name="otter",
                    module_path="applications.otter.framework_prompts",
                    description="Otter-specific framework prompts with Badger/BO domain knowledge for correct run analysis",
                    prompt_builders={
                        "response_generation": "OtterResponseGenerationPromptBuilder",
                        "orchestrator": "OtterOrchestratorPromptBuilder",
                    }
                )
            ],

            # ====================
            # Framework Exclusions
            # ====================
            # Not needed for Phase 1 - no conflicts with framework capabilities
            framework_exclusions={}
        )
