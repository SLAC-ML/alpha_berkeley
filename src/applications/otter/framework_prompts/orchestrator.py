"""Otter orchestrator prompts with Badger optimization domain knowledge."""

from typing import Optional

from framework.prompts.defaults.orchestrator import DefaultOrchestratorPromptBuilder


class OtterOrchestratorPromptBuilder(DefaultOrchestratorPromptBuilder):
    """Otter-specific orchestrator prompt builder with BO domain knowledge."""

    def get_role_definition(self) -> str:
        """Get the Otter-specific role definition for planning."""
        return (
            "You are planning Badger optimization analysis and routine generation workflows. "
            "You understand Bayesian Optimization algorithms, VOCS structure, and particle accelerator optimization."
        )

    def get_system_instructions(self, info=None, **kwargs) -> str:
        """
        Get system instructions with Badger optimization domain context.

        Adds critical context about BO behavior and VOCS structure.
        """
        # Get base orchestrator instructions
        base_instructions = super().get_system_instructions(info=info, **kwargs)

        # Add Badger/BO domain context
        domain_context = """

**BADGER OPTIMIZATION DOMAIN KNOWLEDGE FOR PLANNING:**

When planning workflows for Badger optimization analysis, understand these key concepts:

**1. Bayesian Optimization Algorithms**:
- **expected_improvement**: BO algorithm that balances exploration vs exploitation using acquisition function
- **MOBO**: Multi-Objective Bayesian Optimization for multiple competing objectives
- **neldermead**: Simplex-based optimization (not BO - deterministic, no exploration)
- **rcds**: Robust conjugate direction search

**2. VOCS Structure** (Variables, Objectives, Constraints, ):
- **Variables**: Optimization parameters with ranges (e.g., magnet currents, RF voltages)
  - Format: List[Dict[str, List[float]]] - [{'QUAD:LTUH:620:BCTRL': [-46.23, -41.83]}, ...]
- **Objectives**: Quantities to optimize with direction
  - Format: List[Dict[str, str]] - [{'pulse_intensity_p80': 'MAXIMIZE'}, ...]
  - Direction: 'MAXIMIZE' (higher is better) or 'MINIMIZE' (lower is better)
- **Constraints**: Boundaries that must be satisfied during optimization

**3. Run Analysis Principles**:
- Success measured by best value achieved (not final value!)
- Fewer evaluations with good results = efficient optimization
- Exploration behavior (varying objectives) is NORMAL and GOOD for BO
- For most cases in real machine tuning, calculating the absolute difference between the best and the initial objective values is sufficient to assess improvement. Relative changes do not provide significant additional insights in these scenarios.

**4. Context Flow for Analysis Tasks**:
```
User: "Analyze runs and suggest routine"
→ extract_run_filters: Parse query → RUN_QUERY_FILTERS context
→ query_runs: Load runs → BADGER_RUNS context (container with .runs list)
→ analyze_runs: Analyze BADGER_RUNS → RUN_ANALYSIS context
→ propose_routines: Use RUN_ANALYSIS → ROUTINE_PROPOSAL context
→ respond: Present results using contexts
```

**5. Beamline Organization** (7 physical beamlines):
- cu_hxr, cu_sxr: Normal conducting beamlines (Hard/Soft X-ray)
- sc_bsyd, sc_diag0, sc_sxr, sc_hxr: Superconducting beamlines
- dev: Development/testing beamline

**6. Badger Environments** (software environments, different from beamlines):
- lcls, lcls_ii: LCLS facility environments
- sphere: Simulation/testing environment

**7. Multi-Query Planning** (CRITICAL for compound queries):
When user asks for multiple distinct data retrievals in one query:
- Plan separate query_runs steps for each distinct request
- The FINAL respond step MUST include ALL created contexts in its inputs array

Example: "Show me recent 2 runs on cu_hxr, and oldest 2 runs on dev"
→ Step 1: extract_run_filters (cu_hxr query) → RUN_QUERY_FILTERS: "cu_hxr_filters"
→ Step 2: query_runs → BADGER_RUNS: "cu_hxr_runs"
→ Step 3: extract_run_filters (dev query) → RUN_QUERY_FILTERS: "dev_filters"
→ Step 4: query_runs → BADGER_RUNS: "dev_runs"
→ Step 5: respond with inputs=[{"BADGER_RUNS": "cu_hxr_runs"}, {"BADGER_RUNS": "dev_runs"}]

NEVER omit earlier contexts - respond needs ALL results to present complete answer!

When planning optimization analysis workflows:
1. Always use extract_run_filters before query_runs for ALL run queries
2. Remember that best values ≠ final values for BO algorithms
3. query_runs returns a BADGER_RUNS container - pass ALL containers to respond/analyze_runs if multiple queries were made
4. Use RUN_ANALYSIS context for subsequent analysis steps (don't re-analyze!)
5. If the query doesn't contain time range-related specifications, do NOT use time_range_parsing capability.
"""

        return base_instructions + domain_context
