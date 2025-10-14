"""
Otter Application Registry Configuration

This module defines the component registry for the Otter Badger optimization run assistant.
All Otter-specific capabilities, context classes, and data sources are declared here.
"""

from framework.registry import (
    CapabilityRegistration,
    ContextClassRegistration,
    DataSourceRegistration,
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
                    name="query_runs",
                    module_path="applications.otter.capabilities.query_runs",
                    class_name="QueryRunsCapability",
                    description="Query Badger optimization runs from archive with time and count filters",
                    provides=["BADGER_RUN"],
                    requires=[]
                ),
                # Future capabilities will be added here:
                # - analyze_runs: Generate statistics and analysis from historical runs
                # - search_runs: Find runs matching complex criteria (VOCS-based filtering)
                # - infer_terminology: Map ambiguous terms to actual objective/variable names
                # - compose_routine: Generate complete Badger routine from specifications
            ],

            # ====================
            # Context Classes
            # ====================
            context_classes=[
                ContextClassRegistration(
                    context_type="BADGER_RUN",
                    module_path="applications.otter.context_classes",
                    class_name="BadgerRunContext"
                ),
                # Future context classes will be added here:
                # - RUN_ANALYSIS: For statistics and analysis results
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
            # Not needed for Phase 1 - using default framework prompts
            # Can be added later if we need Otter-specific orchestration or classification prompts
            framework_prompt_providers=[],

            # ====================
            # Framework Exclusions
            # ====================
            # Not needed for Phase 1 - no conflicts with framework capabilities
            framework_exclusions={}
        )
