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
- **rcds**: Random Coordinate Descent Search
- **cmaes**: Covariance Matrix Adaptation Evolution Strategy
- **LiGPS**: Likelihood-Guided Particle Swarm

BO algorithms (expected_improvement, MOBO, etc.) explore the search space, so:
- Final objective value ≠ best objective value (exploration causes "jumping around")
- Best value = max_objective_values for MAXIMIZE, min_objective_values for MINIMIZE
- Success = improvement from initial to BEST, not initial to final

**2. VOCS Structure** (Variables, Objectives, Constraints, Strategy):
- **Variables**: Optimization parameters with ranges (e.g., magnet currents, RF voltages)
  - Format: List[Dict[str, List[float]]] - [{'QUAD:LTUH:620:BCTRL': [-46.23, -41.83]}, ...]
- **Objectives**: Quantities to optimize with direction
  - Format: List[Dict[str, str]] - [{'pulse_intensity_p80': 'MAXIMIZE'}, ...]
  - Direction: 'MAXIMIZE' (higher is better) or 'MINIMIZE' (lower is better)
- **Constraints**: Boundaries that must be satisfied during optimization
- **Strategy**: Optimization configuration (algorithm, evaluations, etc.)

**3. Run Analysis Principles**:
- Success measured by best value achieved (not final value!)
- Multiple objectives → Pareto front analysis (trade-offs between objectives)
- Fewer evaluations with good results = efficient optimization
- Exploration behavior (varying objectives) is NORMAL and GOOD for BO

**4. Context Flow for Analysis Tasks**:
```
User: "Analyze runs and suggest routine"
→ query_runs: Load runs → BADGER_RUN contexts (run_0, run_1, ...)
→ analyze_runs: Analyze BADGER_RUN contexts → RUN_ANALYSIS context
→ propose_routines: Use RUN_ANALYSIS → ROUTINE_PROPOSAL context
→ respond: Present results using contexts
```

**5. Beamline Organization** (7 physical beamlines):
- cu_hxr, cu_sxr: Copper linac beamlines (Hard/Soft X-ray)
- sc_bsyd, sc_diag0, sc_sxr, sc_hxr: Superconducting linac beamlines
- dev: Development/testing beamline

**6. Badger Environments** (software environments, different from beamlines):
- lcls, lcls_ii: LCLS facility environments
- sphere: Simulation environment
- epics: Generic EPICS environment
- Many others specific to different experimental setups

**CRITICAL**: 'lcls_ii' is a BADGER ENVIRONMENT, not a beamline!

When planning optimization analysis workflows:
1. Always use extract_run_filters for ambiguous queries (e.g., "lcls_ii runs")
2. Remember that best values ≠ final values for BO algorithms
3. Plan analyze_runs with ALL run contexts from query_runs (run_0, run_1, ..., run_N-1)
4. Use RUN_ANALYSIS context for propose_routines (don't re-analyze!)
5. Present results emphasizing best values and BO exploration behavior
"""

        return base_instructions + domain_context
