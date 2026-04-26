from __future__ import annotations

import json

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.utils import call_with_schema


_QUERIES_SCHEMA = {
    "type": "object",
    "properties": {
        "benchmark": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "2-3 arXiv search queries about the datasets/benchmarks/baselines "
                "the paper uses. Each query: 3-6 keywords, space-separated. "
                "Example: 'MATH GSM8K mathematical reasoning benchmark'."
            ),
            "minItems": 1,
            "maxItems": 4,
        },
        "same_problem": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "2-3 queries about the problem the paper solves (other authors "
                "tackling the same problem with possibly different methods). "
                "Example: 'efficient LLM reasoning inference cost'."
            ),
            "minItems": 1,
            "maxItems": 4,
        },
        "same_technique": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "2-3 queries about the core technique/method the paper uses "
                "(other authors using similar techniques on possibly different problems). "
                "Example: 'mentor student model collaboration reasoning'."
            ),
            "minItems": 1,
            "maxItems": 4,
        },
    },
    "required": ["benchmark", "same_problem", "same_technique"],
}


@agentic_function(render_range={"depth": 0, "siblings": 0})
def generate_multi_specificity_queries(paper_content: str,
                                       runtime: Runtime) -> str:
    """Generate arXiv search queries for prior-work grounding.

    Uses tool-use to force structured output (works on any LLM that supports
    tool calling — OpenAI, Anthropic, Gemini, etc.).

    Returns a JSON string: {"queries": {"benchmark": [...], ...}}
    """
    result = call_with_schema(
        runtime=runtime,
        instructions=(
            "Read the paper below. Then call the submit_queries tool with "
            "three lists of arXiv search queries: one for benchmarks/baselines "
            "the paper uses, one for the problem the paper solves, and one "
            "for the core technique. Each query should be 3-6 keywords. "
            "Avoid using the paper title verbatim. Avoid generic terms like "
            "'deep learning' alone.\n\n"
            f"PAPER:\n{paper_content}"
        ),
        schema_name="submit_queries",
        schema_description=(
            "Submit the three lists of arXiv search queries for prior-work "
            "retrieval (benchmark, same_problem, same_technique)."
        ),
        parameters=_QUERIES_SCHEMA,
    )
    # Wrap so downstream parse_json("queries") still works.
    return json.dumps({"queries": result}, ensure_ascii=False)
