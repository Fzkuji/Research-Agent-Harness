# review_corpus 使用经验总结

`review_corpus/source/` 里的 57 篇 OpenReview 真人审稿（NeurIPS 2023-2024、ICLR 2022/2024、COLM 2024）一开始是为了帮自动 reviewer 输出"看起来像人写的"审稿——具体目标是把 GPTZero AI% 降到 ≤20%（ACM MM 2026 lab 的硬要求）。

为达到这个目标尝试过 9 种方法。8 种失败，1 种成功。下面记录每种方法、为什么失败、以及最终找到的有效方法所依赖的原理。后续做类似工作的人可以直接跳到「有效方法」一节。

## 背景：检测器看的是什么

GPTZero 的 token-level AI% 检测看两件事：
- 每个 token 在前 N 个 token 条件下的 **perplexity**（LLM 在该位置选这个词的"意外度"）
- 句长方差（**burstiness**）

LLM 写出来"AI 味重"是因为：RLHF 后的 next-token 分布高度 mode-collapsed，每个位置选的都是高概率词，token 序列在统计上跟训练分布完美对齐。

**Prompt 层面的指令几乎不影响 token 分布**——prompt 改的是 high-level intent，不动采样分布的尾部。这是后面 7 种方法失败的根本原因。

## 失败的 8 种方法

### 1. voice sample（archived/basic.py，已删）
**做法**：把 `processed/human_reviews.json` 里的真人审稿全文作为 few-shot example 喂给 `humanize_text`，让 LLM 模仿这种风格改写。

**结果**：GPTZero 100% AI。

**为什么**：few-shot 让 LLM 理解"reviewer 风格 = 严谨 + hedge + 第一人称"，但生成时仍然按 RLHF 后的 token 分布采样，只是把表面 mode 切到"reviewer"。token 概率分布的形状跟无 few-shot 时几乎一样。

### 2. phrase library 硬约束（archived/strict.py，已删）
**做法**：从 `processed/phrase_library.json` 里抽真人 hedge 词频、句长 percentile、opening 模板等统计，作为 schema 约束逼 LLM 生成。

**结果**：100% AI。

**为什么**：硬约束的是 phrase 选择和句长分布，仍然是 prompt 层面的元指令——LLM 在被约束的位置仍按自己的 default 分布采样。检测器无感。

### 3. 跨模型 paraphrase（archived/cross_model.py，已删）
**做法**：链式 paraphrase——先 `openai-codex` 改写，输出再喂 `claude-code`，输出再喂 `gemini-cli`。假设是不同模型 fingerprint 不同，叠加后能洗掉单一模型的统计特征。

**结果**：100% AI。

**为什么**：每个 LLM 的 next-token 分布形状高度相似（都是 RLHF 后的 mode-collapsed 学术英文分布），叠加多次没有让分布偏离"LLM-like"的整体 cluster。检测器看的是分布形状，不是哪个具体 LLM。

### 4-7. 各种 prompt 改写（v1-v3 humanize 实验，没有进 archived/）

| 版本 | 策略 | GPTZero AI% |
|---|---|---|
| v1 | 抽象 prompt：hedge / 第一人称 / ban list | 100% |
| v2 | 强化 prompt：fragment / aside / self-correction（未测） | — |
| v3 | 手写 expression bank（codex 自由组合 BANK 内 phrase） | 100% |

四种都是给 codex 抽象规则或词频，让它**自己组合**句子——它仍然走 LLM 默认 token 分布。只换出现频率最高的 marker 词（"delve" 等）没用，因为检测器学的是 n-gram co-occurrence 模式，不是某个词的有无。

### 8. 数据校准统计 bank（v5 native generation）
**做法**：从真人 corpus 抽出每个维度的精确频率（句长 p10/p50/p90、contractions 2.82/1000 词、第一人称 1.3/100 词、parenthetical 1.94/1000 chars），让 codex 严格按这些 percentile 生成。

**结果**：100% AI。**反直觉地比 v4 87% 更糟**。

**为什么**：真人审稿的 phrase 分布跟 LLM 标准学术英文输出**重合度极高**。模仿真人 = 让 LLM 走自己最 default 的轨道 = AI% 接近 100%。

这个反直觉发现非常重要：**phrase 层面"像真人"和"被检测器判 AI"是正相关，不是负相关**。学术英文这个领域，人类和 LLM 写出来的标准 prose 在 token 分布上区别极小。

## 部分有效的方法

### v4 native generation + 手写"博客腔" BANK
**做法**：让 codex 直接写审稿（不是改写），prompt 里手写 BANK：openers 用"OK so the setup is this." / "Big problem: fit." / "Honestly,"，aside 用"(I had to reread Table X three times.)"。

**结果**：GPTZero 87% AI（首次跌破 100%）。

**为什么**：不是因为"像真人"，而是因为这些 phrase**强制偏离了 LLM 默认分布**——LLM 写学术 review 时不会自发选 "OK so" 开头，被强制使用就在这些位置产生了高 perplexity token。

但 87% 仍然远超 ≤20% 的 KPI，且输出**不像真审稿**（reviewer 不会写"OK so the setup is this."）。

## 唯一有效方法（GPTZero 0%）

### v6 native generation + verbatim 句子模板池
**做法**：
1. 从 52 篇 GPTZero-verified 真人审稿里抽出 319 行**完整句子**，按功能分类（SUMMARY / STRENGTH / WEAKNESS / TRANSITION / HEDGE / QUESTION / CLOSING / GENERIC）
2. 把这 319 行原句**verbatim 塞进 prompt**
3. 给 codex 唯一规则：**每写一句话必须是这 319 行中某句的最小修改——只允许把 paper-specific 的名词/数字替换成目标 paper 的内容**，不允许写任何不在模板池里有句法骨架对应的句子

**结果**：
- Run 1: GPTZero 0% AI / 100% human / "highly confident entirely human"
- Run 2: 同样 0% / 100% / 同样 verdict
- 事实保真完美（数字、术语、视角、5-6 个 question 全保留）

**为什么有效**：
- 之前所有方法都让 codex **自由组词**，它必然走 LLM 默认 token 分布
- v6 把 codex 的自由度降到**名词级别**——句子结构、连接词、时态、hedge 位置全部强制复制真人原句
- token-level pattern 因此被锁死在真人样本的分布里，绕过了 LLM 默认采样

**抽取脚本**：项目里已有 `mine_phrases.py`（统计角度），但 v6 用的是另一个抽取——直接抽完整句子按功能分桶。这部分如果要复用，可以参考 `~/Downloads/extract_sentence_templates.py`（备份在 git 历史里，commit 时可以加进 pipeline/）。

## 给后续工作的建议

1. **不要重做 voice sample / phrase library 硬约束 / 跨模型 paraphrase 实验**——这三种被 archived 的方法都已验证 100% AI。
2. **不要尝试通过抽象规则（hedge 频率、ban list、第一人称密度）让 LLM"像人"**——LLM 自由组词时分布回归 default，prompt 元指令动不到 token 层。
3. **如果检测器换成 Pangram 或 OriginalityAI 等 supervised classifier**：v6 路径不一定继续有效。Pangram 2025-08 公开数据显示对 19 家商业 humanizer 召回率最低 90.3%。需要重新验证。
4. **如果要扩 corpus**：当前 57 篇全是 oral / accept paper（`pipeline/collect_from_openreview.py:50` 的 `list_oral_neurips_v2` 只抓 Oral）。加 reject paper 能让 WEAKNESS / QUESTION 句子模板池的多样性显著上升——尤其是真正负面的批评句式。
5. **真人审稿 phrase ≠ 真人审稿 token 分布**：phrase library 的统计有用（用于做完整性校验、debugging），但不要直接喂给 LLM 当生成约束——v5 已经证明这条路无效。
6. **句子模板池的工作机制**：本质是把"风格"问题降维成"槽位填充"问题。这是当前 closed LLM API（不能调 temperature 或 logit_bias 的 codex 后端）下唯一能控制 token 分布的方法。

## 重大补充发现：模型差异 > prompt 差异

把同一份 v6 prompt（含 sentence template pool）做成 Claude Code skill (`skills/paper-review/SKILL.md`) 让 Claude 在 chat session 里执行：

| LLM | 链路 | review prose AI% | strengths AI% | weaknesses AI% | questions AI% |
|---|---|---|---|---|---|
| **codex (gpt-5.5)** | 同一份 v6 prompt 通过 codex CLI subprocess 写文件 | **0%** | **0%** | **0%** | **0%** |
| **Claude (chat mode)** | 同一份 prompt 内容 inline 进 SKILL.md，Claude 读完按 SKILL.md 执行 | 100% | 100% | 100% | 100% |

**结论：humanize-via-verbatim-template 是 codex 路径独占的能力。Claude 跑这个 skill 自己写不行。**

机制（4 层）：

1. **训练目标**：Claude 重 RLHF，被 reward 的是"流畅、对话自然"——"严格复制 example 句法骨架"在它训练里被视为低质量输出。它会主动 paraphrase 让句子更"自己的话"。GPTZero 把 paraphrased 输出的中段标为 "originally AI but rewritten" verdict——humanize 痕迹反而被识别。
2. **执行 mode**：codex subprocess 写文件——任务在它训练里没"chat 自然语气"包袱。Claude 在 session 里一直带着"我在跟用户说话"的隐式 prior。
3. **任务 framing**：codex 收到的是"按规则写文件"纯任务命令；Claude 收到的是"按 SKILL.md 这个文档执行"——一层 meta 指令多了"决定怎么执行"步骤，自由度更高。
4. **长 context attention 衰减**：SKILL.md 55KB 时 Claude 对中后段的指令遵从度低于前段——读了模板池但生成时不会强制使用。

**实操结论**：

- **要过 GPTZero KPI 的 review，必须用 codex 路径**（review_paper.py 的 stage 1，即 `_review_prose_codex.py` spawn 的 codex subprocess）
- **不要让 Claude / 其他 RLHF chat 模型自己运行 paper-review skill 写 review prose**——它会用模板里没有的句式，导致 100% AI
- skill 的真正用法：在 codex CLI session 里触发（codex 自动加载 skill metadata），或者在 Claude session 里调 Bash spawn codex subprocess（让 codex 来写）
- 这条结论是**模型差异不是 prompt 问题**——任何 prompt 优化（更严约束、CoT、self-critique、rewrite loop）的天花板大概在 50-70% AI，prompt 层面修不动

## 给后续工作的建议（更新）

1-6 同上。新增：

7. **Claude 只用来调 codex，不要自己写 review prose**。SKILL.md 应该明示这点：在 Claude session 里要写 review，用 Bash 调 `codex exec` 起 codex subprocess。
8. **采样模板池避免风格雷同**：corpus 扩到 N 倍 → 每次生成 review 时随机抽一批（比如 1/10）作为 prompt 模板池。`pipeline/sample_templates.py` 实现这件事。理由：固定模板池跑 100 次 review，每次"声音"会非常像；按批次 random sample 让批次间差异化。
9. **扩 corpus 优先级**：从当前 52 reviews / 16 papers / 5 buckets 扩到 ≥500 reviews / 100+ papers / 10+ buckets。前者是"能跑通"的最小数据，后者才能撑起 sampling 机制 + 长期使用不重复。

## 关键数字快查

| 方法 | GPTZero AI% | 事实保真 |
|---|---|---|
| LLM 直出 | 100% | ✓ |
| voice sample（basic.py） | 100% | ✓ |
| phrase library 硬约束（strict.py） | 100% | ✓ |
| 跨模型 paraphrase（cross_model.py） | 100% | ✓ |
| v1 humanize（hedge prompt） | 100% | ✓ |
| v3 humanize（手写 expression bank） | 100% | ✓ |
| v4 native generation（手写博客腔 BANK） | 87% | ✓ |
| v5 native generation（数据校准统计 bank） | 100% | ✓ |
| **v6 native generation, codex (verbatim 句子模板池)** | **0%** | **✓** |
| **v6 same prompt, Claude (chat mode skill)** | **100% (4/4 字段)** | ✓ |
| aihumanize.io（商业 humanizer 对照） | 6% | ✗（事实损失大） |

KPI 阈值：≤20%（ACM MM 2026 lab 要求）。

只有 **v6 + codex 执行** 能在 ≤20% 的同时保持事实完整。同样的 prompt 在 Claude 上执行 4/4 字段全 100% AI。
