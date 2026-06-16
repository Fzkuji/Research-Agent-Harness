"""Stage: interactive — attended dialogue modes that run INSIDE the harness.

# Adapted from academic-research-skills v3.12.0
# (https://github.com/Imbad0202/academic-research-skills),
# (c) Cheng-I Wu, CC BY-NC 4.0
# Changed: the Socratic mentor strategy (question taxonomy, convergence
# signals, INSIGHT extraction, questions-only rule) is distilled from
# academic-paper/agents/socratic_mentor_agent.md and reworked from a
# Claude-Code skill prompt into an ask_user()-driven Python dialogue loop.

Unlike every other stage, these functions BLOCK on user input between
model turns (OpenProgram's ask_user(): terminal stdin when run in a TTY,
or whatever handler the WebUI / a chat channel registered). They are
declared oversight="interactive" in the registry, so the autonomous
two-level loop never routes to them — entry points are the CLI
(`research-harness --chat`) and direct Python calls.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime
from openprogram.agentic_programming.decision import DecisionError
from openprogram.functions.agentics.ask_user import (
    ask_user,
    has_ask_user_handler,
)

_MAX_TURNS_DEFAULT = 25

_QUIT_WORDS = {"q", "quit", "stop", "done", "exit", "退出", "结束", "停"}

def _render_transcript(turns: list[tuple[str, str]], limit: int = 30) -> str:
    if not turns:
        return "(no dialogue yet)"
    tail = turns[-limit:]
    return "\n".join(f"Q{i + 1}: {q}\nA{i + 1}: {a}"
                     for i, (q, a) in enumerate(tail))


def _wrap_up_choice() -> dict:
    return {
        "wrap_up": (
            "The dialogue has converged (or the user asked to stop): "
            "produce the final research brief.",
            {
                "brief_markdown": (
                    "complete RESEARCH_BRIEF.md content: core question, "
                    "contribution claim (user's words), evidence & method "
                    "plan, paper structure, open risks, and the [INSIGHT] "
                    "collection — built ONLY from what the user actually "
                    "said; mark gaps as OPEN rather than inventing answers"
                ),
            },
        ),
    }


@agentic_function()
def socratic_plan(
    topic: str,
    output_dir: str = "",
    runtime: Runtime = None,
    max_turns: int = _MAX_TURNS_DEFAULT,
) -> str:
    """Interactive Socratic planning dialogue — the mentor asks you one question at a time until your research plan converges, then writes RESEARCH_BRIEF.md. Needs a human at the keyboard; never picked by the autonomous loop.

    You are a Socratic research mentor helping the user sharpen a research
    plan through dialogue. IRON RULES:
    - Ask exactly ONE question per turn. Never bundle questions.
    - QUESTIONS ONLY: never propose, substitute, rank, or select research
      questions, hypotheses, or contributions FOR the user. If the user
      asks you to decide, reflect the decision back as a question.
    - Build on the user's own words; quote them when probing.

    Rotate four question types (each planning phase should see all four):
    1. Clarifying — pin down ambiguous terms ("when you say X, do you mean
       A or B?", "give a concrete example of X").
    2. Probing — push on evidence and reasoning ("what evidence supports
       that?", "is that causation or correlation?", "what would change
       your mind?").
    3. Structuring — connect and focus ("how does this relate to what you
       said about X?", "summarize this part in one sentence").
    4. Challenging — stress-test before reviewers do ("a skeptical
       reviewer would say X — how do you respond?", "what is the strongest
       argument against your position?").

    Work through the plan in layers: core claim/question first, then
    evidence & method, then structure (what the paper must contain), then
    risks. Move on when the current layer shows >=3 convergence signals:
    the user gives consistent answers, names concrete evidence, states the
    point in one sentence, and handles a challenge without contradiction.

    After each user answer, extract at most one [INSIGHT: <tag>] — a key
    commitment in the USER'S OWN words (thesis, contribution claim, method
    choice, scope boundary). Wrap up once every layer converged, the
    insight collection covers claim/evidence/structure/risks, or the user
    asks to stop.

    Args:
        topic:      The research direction / project description to plan.
        output_dir: Where to save RESEARCH_BRIEF.md and the transcript
                    (default: cwd).
        runtime:    LLM runtime.
        max_turns:  Hard cap on questions asked (default 25).

    Returns:
        Summary string naming the saved files, or an ERROR line when no
        interactive channel is available.
    """
    if runtime is None:
        raise ValueError("socratic_plan() requires a runtime argument")
    if not has_ask_user_handler():
        return (
            "ERROR: socratic_plan needs an interactive session — a "
            "terminal (run `research-harness --work-dir X --chat "
            '"<direction>"`) or a WebUI/channel that registered an '
            "ask_user handler. No way to reach the user from here."
        )

    out = Path(os.path.expanduser(output_dir) or os.getcwd())
    out.mkdir(parents=True, exist_ok=True)

    turns: list[tuple[str, str]] = []
    insights: list[str] = []
    brief: str | None = None
    stop_note = ""

    for _turn in range(max_turns):
        choices = {
            "ask": (
                "Ask the user exactly ONE next question (Socratic rules).",
                {
                    "question": "the single next question, user-facing",
                    "qtype": "clarifying | probing | structuring | challenging",
                    "insight": (
                        "at most one [INSIGHT: tag] extracted from the "
                        "PREVIOUS answer in the user's own words; empty "
                        "string if none"
                    ),
                },
            ),
            **_wrap_up_choice(),
        }
        try:
            result = runtime.exec(
                content=[{"type": "text", "text": (
                    f"Research direction:\n{topic}\n\n"
                    f"Insights so far:\n"
                    f"{chr(10).join(insights) or '(none yet)'}\n\n"
                    f"Dialogue so far:\n{_render_transcript(turns)}\n"
                    f"{stop_note}"
                )}],
                choices=choices,
            )
        except DecisionError:
            break  # wrap up with whatever we have

        if not (isinstance(result, dict) and result.get("decision") == "ask"):
            if isinstance(result, dict):
                brief = result.get("brief_markdown")
            break

        if result.get("insight", "").strip():
            insights.append(result["insight"].strip())
        question = result.get("question", "").strip()
        if not question:
            break
        answer = ask_user(question)
        if answer is None or answer.strip().lower() in _QUIT_WORDS:
            stop_note = (
                "\nNOTE: the user has ended the dialogue — wrap up now "
                "with what you have."
            )
            turns.append((question, answer or "(no answer — user left)"))
            continue  # next exec sees the stop note; wrap_up expected
        turns.append((question, answer.strip()))

    if brief is None:
        # Forced wrap-up: dialogue ended without the model picking wrap_up.
        try:
            result = runtime.exec(
                content=[{"type": "text", "text": (
                    f"Research direction:\n{topic}\n\n"
                    f"Insights so far:\n"
                    f"{chr(10).join(insights) or '(none yet)'}\n\n"
                    f"Dialogue so far:\n{_render_transcript(turns)}\n\n"
                    "The dialogue is over. Produce the final brief."
                )}],
                choices=_wrap_up_choice(),
            )
            if isinstance(result, dict):
                brief = result.get("brief_markdown")
        except DecisionError:
            brief = None

    transcript_path = out / "dialogue_transcript.md"
    transcript_lines = [f"# Socratic planning dialogue\n\nTopic: {topic}\n"]
    for i, (q, a) in enumerate(turns, 1):
        transcript_lines.append(f"**Q{i}.** {q}\n\n> {a}\n")
    if insights:
        transcript_lines.append("## Insights\n")
        transcript_lines.extend(f"- {ins}" for ins in insights)
    transcript_path.write_text("\n".join(transcript_lines) + "\n",
                               encoding="utf-8")

    if not brief:
        return (
            f"Dialogue ended without a brief ({len(turns)} answers). "
            f"Transcript saved to {transcript_path}."
        )

    brief_path = out / "RESEARCH_BRIEF.md"
    brief_path.write_text(brief, encoding="utf-8")
    return (
        f"Saved to {brief_path} (transcript: {transcript_path}). "
        f"{len(turns)} questions answered, {len(insights)} insights. "
        f"The brief is the input for the autonomous run."
    )
