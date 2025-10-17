"""Otter application framework prompts package.

These prompts override framework defaults to inject Badger optimization domain knowledge.
"""

from .response_generation import OtterResponseGenerationPromptBuilder
from .orchestrator import OtterOrchestratorPromptBuilder

__all__ = [
    "OtterResponseGenerationPromptBuilder",
    "OtterOrchestratorPromptBuilder",
]
