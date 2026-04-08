# Templates

Ready-to-use templates for the research pipeline. Copy, fill in your content, and run the corresponding function.

## Workflow Input Templates

| Template | For Stage | What to do |
|----------|-----------|------------|
| [RESEARCH_BRIEF_TEMPLATE.md](RESEARCH_BRIEF_TEMPLATE.md) | Literature / Idea | Detailed research direction as document input |
| [RESEARCH_CONTRACT_TEMPLATE.md](RESEARCH_CONTRACT_TEMPLATE.md) | Idea → Experiment | Define problem boundaries, non-goals, active idea context |
| [EXPERIMENT_PLAN_TEMPLATE.md](EXPERIMENT_PLAN_TEMPLATE.md) | Experiment | Claim-driven experiment roadmap with run order and budgets |
| [NARRATIVE_REPORT_TEMPLATE.md](NARRATIVE_REPORT_TEMPLATE.md) | Writing | Research narrative with claims, experiments, results |
| [PAPER_PLAN_TEMPLATE.md](PAPER_PLAN_TEMPLATE.md) | Writing | Pre-made outline to skip planning phase |

## Output / Log Templates

| Template | Written by | Purpose |
|----------|-----------|---------|
| [IDEA_CANDIDATES_TEMPLATE.md](IDEA_CANDIDATES_TEMPLATE.md) | Idea stage | Top 3-5 surviving ideas with killed ideas log |
| [EXPERIMENT_LOG_TEMPLATE.md](EXPERIMENT_LOG_TEMPLATE.md) | Experiment stage | Structured experiment record (results + reproduction) |
| [FINDINGS_TEMPLATE.md](FINDINGS_TEMPLATE.md) | Review stage | Cross-stage discovery log (research + engineering) |

## Usage

```bash
# Copy a template into your project
cp templates/EXPERIMENT_PLAN_TEMPLATE.md my_project/EXPERIMENT_PLAN.md

# Edit with your content, then use in pipeline
from research_harness import research_pipeline
research_pipeline(project_dir="my_project/", ...)
```
