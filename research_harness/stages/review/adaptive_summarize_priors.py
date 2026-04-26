from __future__ import annotations

from openprogram.agentic_programming.function import agentic_function
from openprogram.agentic_programming.runtime import Runtime


@agentic_function(render_range={"depth": 0, "siblings": 0})
def adaptive_summarize_priors(paper_content: str, selected_json: str,
                              max_total_tokens: int, runtime: Runtime) -> str:
    """# Role
    你是 prior-work 摘要员。你拿到一组已经被筛选过的相关论文 (selected_json),
    每篇都标了 summarize_strategy ("abstract" 或 "fulltext")。你的工作:
    把它们整理成 reviewer 能直接消化的 prior_work_context, 整段控制在
    max_total_tokens 以内 (默认 8000)。

    # Inputs
    - paper_content:     被审论文的全文 (用于决定 focus area: 摘要时该突出
                         哪些方面, 和被审论文形成有效对比)。
    - selected_json:     filter_relevant_priors 的输出, 含每篇的 abstract +
                         summarize_strategy + why_relevant。
    - max_total_tokens:  整段输出的 token 预算 (典型 8000)。

    # Task
    Pass 1 (Plan budget):
      统计选中的 N 篇。把 token 预算分配:
      - "abstract" 策略每篇 ~150-200 token (基本就用原 abstract 精简)
      - "fulltext" 策略每篇 ~400-600 token (需要更详细)
      - 留 ~500 token 给整体的 framing 段
      若总和超 max_total_tokens, 优先压 "abstract" 策略的, 不动 "fulltext" 的
      (因为 fulltext 是高 relevance 的, 内容更重要)。

    Pass 2 (Per-paper summarize):
      对每一篇:

      如果 strategy == "abstract":
        - 直接基于已有 abstract 提炼。1 段, 3-5 句。包括:
          - 它解决什么 problem
          - 用什么 method
          - 主要 result / claim
        - 不需要去抓全文 (省事 + 省 token)。

      如果 strategy == "fulltext":
        - 你**有 shell 工具** (类似 search_arxiv 的写法)。可以:
          ```bash
          curl -L "https://arxiv.org/pdf/<id>.pdf" -o /tmp/<id>.pdf
          # 然后用 pdftotext 或 PyMuPDF 抽文本
          ```
          或直接抓 arxiv html 版:
          ```bash
          curl -s "https://arxiv.org/html/<id>" | <strip-tags>
          ```
          如果抓全文失败 (网络问题 / paywall / 旧论文无 html), **回退到
          仅基于 abstract 做更精细的总结**, 并在该篇标注 `fulltext_failed: true`。

        - 决定 focus area: 看被审论文 (paper_content) 的核心 claim 是什么,
          这篇 prior work 应该重点对比哪一面? 例子:
          - 被审论文 claim "我们提出第一个支持 long-context 的 X 方法",
            prior work 应该重点摘出: 它的 context length / 支持 long-context 的方式 / 局限。
          - 被审论文 claim "在 ImageNet-1K 上 SOTA", prior work 应该重点摘出:
            它在 ImageNet-1K 上的具体数字 / 用了什么 trick。

        - 摘要 1-2 段, 控在 400-600 token, 包括:
          - problem + method (1-2 句)
          - **focus area 上的具体细节** (这是关键, 比 abstract 多的内容)
          - 与被审论文最直接的对比点 (1 句, "和被审论文的差别在 X")

    Pass 3 (Assemble):
      按相关度 (relevance_score) 降序排列。每篇前缀编号 [1], [2], ...
      让 reviewer 引用时用 "see [3]" 这种简洁标记。

    # Output format (strict, Markdown)

    ```markdown
    ## Related Work Context (auto-retrieved, NOT author-curated)

    The following N most relevant prior works were retrieved from arXiv based
    on this paper's stated problem and method. Use this as ground truth when
    judging novelty and contextualization. When you cite these in your review,
    use the [N] notation.

    ### [1] <Authors short> (<year>) — <Title>
    arXiv:<id> · relevance: <score> · category: <category>
    <missing_citation marker if true: "⚠ Not cited by the paper.">

    <summary text, 3-5 sentences for abstract / 1-2 paragraphs for fulltext>

    **vs. paper under review**: <1 sentence comparison point>

    ### [2] ...

    ...

    ### [N] ...

    ---

    **Retrieval notes**:
    - Total retrieved: <int>
    - After relevance filter: <int>
    - fulltext_failed: <list of [N] indices if any>
    - Approximate token count: <int>
    ```

    # Persistence
    Save your COMPLETE output to a file in the current working directory.
    Filename: prior_work_context.md (or with a round suffix if obvious from context).
    After saving, return:
    `Saved to <path>. <N> priors summarized (<A> abstract, <F> fulltext, <X> failed); ~<T> tokens.`
    """
    return runtime.exec(content=[
        {"type": "text", "text": (
            f"max_total_tokens = {max_total_tokens}\n\n"
            f"=== SELECTED PRIORS (JSON) ===\n{selected_json}\n\n"
            f"=== PAPER UNDER REVIEW (for focus-area decisions) ===\n{paper_content}"
        )},
    ])
