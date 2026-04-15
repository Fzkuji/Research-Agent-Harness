"""
Research Agent Harness — autonomous research from topic to submission.

Built on Agentic Programming. Python controls flow, LLM reasons via docstrings.

Quick start:
    from research_harness import research_agent

    result = research_agent(task="Survey LLM uncertainty", runtime=my_runtime)
"""

from research_harness.main import research_agent, agentic_research
from research_harness.pipeline import research_pipeline, STAGES

__all__ = [
    "research_agent",
    "agentic_research",
    "research_pipeline",
    "STAGES",
]
