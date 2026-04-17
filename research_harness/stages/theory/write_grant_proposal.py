from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(compress=True, summarize={"depth": 0, "siblings": 0})
def write_grant_proposal(direction: str, grant_type: str,
                         runtime: Runtime) -> str:
    """Draft a structured, reviewer-ready grant proposal from research ideas and
    literature.

    Supports:
    - KAKENHI (Japan/JSPS): 基盤研究 A/B/C, 若手研究, スタート支援, DC1/DC2.
      Sections: 研究目的, 研究計画・方法, 準備状況, 人権の保護.
      Review criteria: 学術的重要性, 独創性, 研究計画の妥当性, 研究遂行能力.
    - NSF (US): Standard Grant, CAREER, CRII, RAPID, EAGER.
      Sections: Project Summary (1p), Project Description (15p max), References,
      Bio Sketch, Budget Justification, Data Management Plan.
      Review criteria: Intellectual Merit, Broader Impacts.
    - NSFC (China/国家自然科学基金): 面上/青年/优青/杰青/海外优青/重点.
      Sections: 立项依据, 研究内容, 研究目标, 研究方案, 可行性分析, 创新性,
      预期成果, 研究基础.
      Review criteria: 科学意义, 创新性, 可行性, 研究队伍.
    - ERC (EU): Starting/Consolidator/Advanced Grant.
      Sections: Extended Synopsis (5p), Scientific Proposal Part B2 (15p).
      Emphasis on high-risk/high-gain, Gantt chart expected.
    - DFG (Germany): State of the Art, Objectives, Work Programme, CV.
    - SNSF (Switzerland): Summary, Research Plan, Timetable, Budget.
    - ARC (Australia): Project Description, Feasibility, Benefit, Budget.
    - NWO (Netherlands): Summary, Proposed Research, Knowledge Utilisation.
    - GENERIC: User provides section names, page limits, review criteria.

    Pipeline: research-lit -> novelty-check -> structure design -> draft ->
    research-review -> revise -> final proposal.

    Rules:
    - Ground every claim in literature or preliminary results. No vague plans.
    - One clear thesis, not a laundry list of ideas.
    - Match tone/structure to the specific grant agency's expectations and
      cultural norms.
    - Include preliminary results if available to demonstrate feasibility.
    - Explicit yearly milestones with concrete expected outputs (papers, datasets).
    - Budget justification integrated into the research plan.
    - For NSFC: heavy emphasis on 国际前沿 positioning and 研究基础 section.
    - For NSF: Broader Impacts must be concrete and specific, not generic.
    - For ERC: methodology table with WP/deliverables/milestones expected.
    - Search for competing funded projects in the same area (KAKEN database,
      NSF Award Search, etc.) to position the proposal.

    Output: Structured grant proposal document matching the agency format,
    with language auto-detected from grant type (KAKENHI->Japanese,
    NSF->English, NSFC->Chinese, etc.).
    

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Choose a descriptive filename based on the function and context (e.g., survey_llm_uncertainty.md).
    After saving, return a brief summary (2-3 sentences) of what you produced, including the file path.
    Format: "Saved to <path>. <summary of content>."
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"Research direction:\n{direction}\n\n"
            f"Grant type: {grant_type}"
        )},
    ])
