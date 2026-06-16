# Skill → Function 整合蓝图

## 目标

把所有参考来源(skill 文档、ARS 协议、references 资产)的内容,统一收口进 research
harness 的运行流程,**不再依赖大模型单独"用 skill"**:

- **论文流程相关的 skill**(写作/评审/去AI化/引用/研究流程)→ 转成 `@agentic_function`,
  内容(规则、注意事项、写作哲学)写进 **docstring**。调用时框架经 session/docstring 机制
  (见 unified-session-context.md)自动把这些指令注入 prompt。
- **非论文流程的能力**(canvas 画图、docx 操作 Word、一般文档协作)→ **不进 research 流程**,
  作为独立 **SKILL.md 迁移到 OpenProgram 的 skill 目录**(`<repo>/skills/`),agent 需要时
  自行调用,不污染论文流水线。

原则:**内容照搬来源,不发挥。** 编排(拆分/合并/串接/接线)是 harness 这边的设计;
写作内容本身完全来自参考来源。

## 内容资产位置(已盘点)

| 资产 | 位置 | 状态 |
|---|---|---|
| WRITING_PRINCIPLES(Nanda/Farquhar/Gopen&Swan 写作哲学) | `references/writing_principles.py` | 现成字符串,**未接线** |
| CITATION_DISCIPLINE(防引用幻觉) | `references/citation_discipline.py` | 现成,**未接线** |
| VENUE_CHECKLISTS(会议清单) | `references/venue_checklists.py` | 现成 |
| venue_scoring(会议评分,55KB) | `references/venue_scoring.py` | review 已接线 ✓ |
| ml-paper-writing(写作哲学/工作流/LaTeX 模板说明/引用验证) | `skills/20-ml-paper-writing/SKILL.md` | 文档,**未接线** |
| humanizer(25 种 AI 模式 + 注魂) | `skills/humanizer/SKILL.md` | 文档 |
| self-review / peer-review(评审) | `skills/*/SKILL.md` | 文档 |
| gptzero-check(AI 检测) | `skills/gptzero-check/SKILL.md` | 文档 |
| agentic-research(研究流程编排) | `skills/agentic-research/SKILL.md` | 文档 |

现有函数:`stages/writing/` 26 个 + `stages/experiment/` 4 个。**很多已是 skill 内容的对应物**
(write_section, polish_natural, humanize_text, design_experiments...)——整合主要是
**把 skill 文档内容补进这些已有函数的 docstring**,该拆的拆、该合的合,而非从零新建。

---

## A 部分:论文流程 skill → agentic functions

按内容大类组织。每类标注:已有函数(补 docstring)/ 该新建 / 该拆分。

### A1. 写作哲学与结构(来源:ml-paper-writing + writing_principles)

| 函数 | 现状 | 整合动作 | docstring 承载(照搬来源) |
|---|---|---|---|
| `write_section` | 已有(被我误改成 md) | 改回 LaTeX 输出;docstring 补 WRITING_PRINCIPLES 的 section 规则 | 5 句 abstract 公式(Farquhar)、intro 结构、Gopen&Swan 7 原则、Lipton 词选 |
| `outline_paper_structure` | 无 | 新建 | narrative 原则(What/Why/So What)、reviewer 阅读顺序、时间分配 |
| `define_core_contribution` | 无 | 新建 | "一句话讲不清贡献=框架没收敛"(Karpathy)、3 支柱 |
| `polish_rigorous` / `polish_natural` | 已有 | docstring 补 Gopen&Swan + Lipton + Perez 微观规则 | prose 打磨规则 |
| `check_conference_requirements` | 无(review 有 venue_scoring) | 新建,复用 venue_scoring/venue_checklists | 页数/必需项/匿名规则 |

### A2. 引用纪律(来源:ml-paper-writing CRITICAL + citation_discipline)

| 函数 | 现状 | 整合动作 | docstring |
|---|---|---|---|
| `verify_citations` | 已有 citation gate(stages 里有 citation 验证) | 确认接线;docstring 补 CITATION_DISCIPLINE | ~40% 幻觉率、必须 API 验证、验证不了标 [CITATION NEEDED]、绝不凭记忆写 BibTeX |

### A3. 去 AI 化(来源:humanizer + gptzero-check)

| 函数 | 现状 | 整合动作 | docstring |
|---|---|---|---|
| `humanize_text` | 已有(四通道) | docstring 补 humanizer 的 25 种模式清单 | 25 种 AI 模式定义 + 修复示例 |
| `remove_ai_flavor_zh` | 已有 | 同上(中文版) | 中文 AI 痕迹 |
| `add_personality_and_soul` | 无(humanize_text 可能含) | 评估:拆出或并入 | 注魂:有观点/节奏变化/第一人称/具体感受 |
| gptzero 检测 | skill 是 CLI shim | 评估是否值得函数化(依赖 Chrome CDP) | AI%≤20% 阈值 |

### A4. 评审(来源:self-review + peer-review;review stage 已有大量函数)

review stage 已经是整合最好的(review_loop, review_paper, venue_scoring...)。
self-review / peer-review 的内容**对照 review stage 现有函数**,补缺失的 docstring 规则:
8 种失败模式清单、harsh 不软化、full 1-10 打分、3 步人类化管道。多半是**补充**而非新建。

### A5. 实验(来源:experiment stage 现有 + design_experiments)

| 函数 | 现状 | 整合动作 | docstring |
|---|---|---|---|
| `design_experiments` | 已有(我已修:指令进 docstring) | 保持 | 7 章节(RQ/datasets/baselines/metrics/ablation/impl/types) |
| `run_experiment` | 已有 | docstring 补"每个数字必须 auditable" | 数据真实性 |

### A6. 研究流程编排(来源:agentic-research)

agentic-research 描述的就是 `research_agent` 的两级循环本身——**已经是 main.py 实现的**。
不新建,把 skill 里的流程说明作为 research_agent 的 docstring 补全即可。

---

## B 部分:非论文 skill → 迁移到 OpenProgram skill 目录

这几个**不进 research 流程**,迁移为独立 SKILL.md 到 `<OpenProgram repo>/skills/<slug>/SKILL.md`
(格式现成兼容:YAML frontmatter name+description + markdown body)。agent 需要时自行调用。

| skill | 迁移目标 | 为何不进流程 |
|---|---|---|
| canvas-design | `OpenProgram/skills/canvas-design/SKILL.md` | 画艺术图,与写论文无关 |
| docx | `OpenProgram/skills/docx/SKILL.md` | 操作 Word,通用工具非论文专属 |
| doc-coauthoring | `OpenProgram/skills/doc-coauthoring/SKILL.md` | 写一般文档,非论文 |

迁移 = 拷贝 SKILL.md(+ 其引用的资产文件,如有)。不改内容。

---

## 执行顺序(分批,每批独立验证)

| 批 | 做什么 | 验证 |
|---|---|---|
| **P0** | write_section 改回 LaTeX + 接 WRITING_PRINCIPLES;接 CITATION_DISCIPLINE 到引用函数 | 单跑 write_section,产 LaTeX、prompt 含写作原则 |
| **P1** | 论文写作类剩余(outline/contribution/polish docstring 补全) | 单跑各函数产真内容 |
| **P2** | 去AI化(humanize_text docstring 补 25 模式) | humanize_text 按 25 模式工作 |
| **P3** | 评审类(self/peer-review 内容对照 review stage 补全) | review 函数含失败模式清单 |
| **P4** | 非论文 skill 迁移到 OpenProgram skills/ | OpenProgram 加载到这些 skill |
| **P5** | 端到端重跑论文 run,验证整合后产 LaTeX 论文 | PAPER 是 LaTeX、含引用验证、过自评审 |

每批改完 commit + 验证,不一次性大改。
