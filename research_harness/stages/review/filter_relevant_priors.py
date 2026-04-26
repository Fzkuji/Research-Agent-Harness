from __future__ import annotations

import json

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime

from research_harness.utils import call_with_schema


_SELECTED_SCHEMA = {
    "type": "object",
    "properties": {
        "selected": {
            "type": "array",
            "description": "The top-k most relevant prior works, ranked by relevance.",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "arXiv ID, e.g. 'arXiv:2403.12345'"},
                    "title": {"type": "string"},
                    "year": {"type": "string", "description": "Publication year as string"},
                    "relevance_score": {
                        "type": "number",
                        "description": "0.0-1.0; 1.0 = direct prior work, must-cite",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["benchmark", "same_problem", "same_technique"],
                    },
                    "missing_citation": {
                        "type": "boolean",
                        "description": "True if highly relevant but not cited by the paper",
                    },
                    "why_relevant": {
                        "type": "string",
                        "description": "1-2 sentence justification",
                    },
                    "abstract": {
                        "type": "string",
                        "description": "Copy verbatim from the candidate metadata",
                    },
                    "summarize_strategy": {
                        "type": "string",
                        "enum": ["abstract", "fulltext"],
                        "description": (
                            "abstract: relevance < 0.7 OR abstract suffices. "
                            "fulltext: relevance >= 0.7 AND needs deeper detail."
                        ),
                    },
                },
                "required": ["id", "title", "relevance_score", "category",
                             "why_relevant", "abstract", "summarize_strategy"],
            },
        },
        "rejected_count": {
            "type": "integer",
            "description": "How many candidates were considered but not selected.",
        },
        "notes": {
            "type": "string",
            "description": "Any caveats (e.g. 'no benchmark-category candidates retrieved').",
        },
    },
    "required": ["selected", "rejected_count", "notes"],
}


@agentic_function(render_range={"depth": 0, "siblings": 0})
def filter_relevant_priors(paper_content: str, candidates_json: str,
                           top_k: int, runtime: Runtime) -> str:
    """Select the top-k most relevant prior works from arXiv candidates.

    Uses tool-use to force structured output. Returns a JSON string matching
    {"selected": [...], "rejected_count": int, "notes": str}.
    """
    instructions = (
        f"You are a prior-work relevance filter.\n\n"
        f"Below are arXiv candidate papers retrieved for a paper under review. "
        f"Score each candidate 0.0-1.0 by relevance to the paper's novelty / "
        f"contextualization assessment, then select the top {top_k} by relevance "
        f"with category diversity (don't put all benchmark or all same_problem). "
        f"For each selected paper, decide summarize_strategy: 'abstract' for "
        f"relevance < 0.7, 'fulltext' for relevance >= 0.7 needing deeper detail.\n\n"
        f"Mark missing_citation=true for highly relevant papers the paper does NOT cite.\n\n"
        f"Call the submit_selected tool with your decisions.\n\n"
        f"top_k = {top_k}\n\n"
        f"=== CANDIDATES (JSON) ===\n{candidates_json}\n\n"
        f"=== PAPER UNDER REVIEW ===\n{paper_content}"
    )
    result = call_with_schema(
        runtime=runtime,
        instructions=instructions,
        schema_name="submit_selected",
        schema_description=(
            f"Submit the top-{top_k} most relevant prior works with relevance "
            f"scores, categories, and summarization strategies."
        ),
        parameters=_SELECTED_SCHEMA,
    )
    return json.dumps(result, ensure_ascii=False)
