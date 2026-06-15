# research_agent 运行逻辑

`research_agent`（`research_harness/main.py`）是一个两级自治循环,负责把一个研究任务从头跑到尾——单一调研、写论文,或 idea→experiment→writing→review 的完整链路。本文记录它的控制流和防止空转/死循环的机制。

## 两级循环

- **Level 1 — 选 stage**(`_pick_stage`):从 `STAGES`(literature/idea/experiment/writing/review/rebuttal/...）里选下一个进入的阶段,或 `done` 结束。用 `runtime.exec(choices=...)` 决策。
- **Level 2 — stage 内执行**(`_stage_step`):在选中的 stage 里反复挑一个函数执行,直到 `stage_done` 或被保护栏切断。

每个 stage 通常有一个 orchestrator（`run_literature` / `run_idea` / `review_loop` / ...）。

## 核心原则:迭代由代码闭环,不靠 LLM 续杯

**一件事要循环多少次,是 orchestrator 内部 `for` 循环的事,不是让 LLM 反复调同一个函数。**

orchestrator 在**一次调用**里跑完它自己的内部循环：

- `run_literature` 内部 `for outer in range(max_outer)` 一次跑到合成 `review.md`。
- `review_loop` 内部 `for round in range(max_rounds)` 一次跑完 review→改→再 review,直到通过或到上限。

为此 `_stage_step` 给暴露 `auto_fix` 的 orchestrator（review_loop）默认注入 `auto_fix=True`,让它在 agent loop 内自闭环（CLI / pipeline 显式传参的调用方不受影响）。`_pick_stage` 的 prompt 明确："orchestrator 调一次即可,它自己迭代到底,不要为了'继续'而重调"。

这样 LLM 只负责真正需要判断的事（选哪个 stage、哪个函数），机械的轮次计数留给确定性代码。

## 完成信号归一化

stage orchestrator 的返回形态历史上不统一：`run_literature` 给 `done`,`review_loop` 给 `passed`,几个单步函数（run_idea/run_experiments/...）什么都不给。

`_stage_step` 在**一处**把它们归一成一个 `func_done` 布尔，主循环读它（而不是让 LLM 解析 `str(result)`，那正是早期空转的源头）：

| orchestrator 返回 | func_done |
|---|---|
| dict 带 `done` | 用它 |
| dict 带 `passed`（review_loop）| 映射它 |
| dict 无标志 / 非 dict（单步函数、str、None）| True（跑过即完成）|

## 防空转 / 防死循环的保护栏

控制流用确定性代码兜底，不依赖 LLM 自觉。常量见 `main.py` 顶部。

| 保护栏 | 机制 | 防的问题 |
|---|---|---|
| **全局 step 预算** `_MAX_TOTAL_STEPS=60` | 整个 run 的 Level-2 总步数硬上限 | 两 stage 间 ping-pong（review↔writing），各自不超限却烧上百步 |
| **失败摘除** `_MAX_FUNC_FAILURES=3` | 某函数全程累计失败 3 次 → 加入 `blocked`，从 catalog 摘除，LLM 不能再选 | 坏函数（环境问题、模型不调 submit 工具）被反复重试 |
| **无进展 stage 停** `_MAX_STAGE_REVISITS=3` | 同一 stage 重入 >3 次且自上次以来无新成功步 → 判定卡死,结束 run | 跨 stage 横跳，per-stage repeat guard 看不见的空转 |
| **per-stage 重复保护** `_REPEAT_WARN/_REPEAT_BREAK=3/5` | 同一 (函数, 参数) 连续调用 → 警告 → 5 次切断 stage | stage 内对同一调用的机械重试 |
| **stage 上限** `_MAX_STAGES=10` | Level-1 最多选 10 个 stage | 兜底 |
| **per-stage step 上限** `_MAX_STEPS_PER_STAGE=20` | 每 stage 内最多 20 步 | 兜底 |

run 结束时返回 `stop_reason`（`"global step budget reached"` / `"stage '...' ... stuck"` / `None`）和 `total_steps`，调用方据此区分"正常完成"与"被保护栏中断"。

## stage 依赖提示

`_pick_stage` 的 prompt 给出确定性的典型依赖链（literature→idea→experiment→writing→review→rebuttal），并说明每个 stage 需要前驱的产物（idea 需要 literature 的 gaps、review 需要写好的论文等），引导 LLM 不要跳着选导致空跑。纯文本提示，不读文件系统、不依赖具体 runtime。

## 测试

- `tests/test_main.py` — 两级循环、_pick_stage / _stage_step / research_agent 的基本行为。
- `tests/test_run_logic.py` — 本文所述保护栏:func_done 归一化、blocked 摘除、失败函数能终止 run、全局预算封顶。

全部用 `MockRuntime`，不调真实 LLM。核心断言:不管模型怎么折腾，run 一定终止并报告 why。
