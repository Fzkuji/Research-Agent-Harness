# P2 — research_agent 中途干预(steering)

用户需求(原话):任务跑一半发现路线错了/想换方向,我能插一条新指令让它调整。
做法方向(用户定):**基于事件层,程序时刻监控外部事件,有用户额外消息就注入进去。**
范围(用户定):**只为 research_agent 单独设计,不跟通用 agent_loop 混。**

## 设计目标

- 任务跑着时,用户从任一端发一条"干预消息"(改方向/加约束/纠正)。
- research_agent 在**当前 step 跑完后**(优雅,不打断手头那步)读到它,把它喂进**下一轮 stage 决策**,据此调整路线。
- 不需要打断当前 step(和优雅停同源:循环检查点 poll)。

## 复用的地基

- **优雅停已有的两个检查点**:research_agent 的 stage 循环顶 + step 循环顶,已经 poll `_stop_requested()` / `_out_of_time()`。steering 检查就加在同一处。
- **进程级 stop flag 模块** `research_harness/stop.py` 的模式:steering 也做一个**会话级队列**的进程模块,同样能跨子进程(子进程 IPC 桥已有 stop_queue,可加 steering_queue 同法)。
- **事件层**:用户消息从三端 → WS/CLI → emit 一个 `session.steering` 事件 / 或直接投进会话 steering 队列。

## 机制(三层)

### 1. steering 队列(进程模块,新增 research_harness/steering.py)
- 一个会话级 list/Queue,存"待注入的用户干预消息"。
- `push(message)`(外部投递)、`drain()`(research_agent 取走全部待处理)、`pending()`(非空判断)。
- 和 stop.py 一样是进程级模块(单 worker,跨线程;子进程经 IPC 桥)。

### 2. research_agent 循环注入点
- stage 循环顶,在 `_pick_stage` 之前:`if steering.pending(): msgs = steering.drain()` → 把 msgs 作为"用户中途指令"拼进 `_pick_stage` 的 progress/task 上下文,让下一轮 stage 决策据此转向。
- step 循环顶同理:正在某 stage 内,收到干预 → 把它加进 stage_context,下一个 `_stage_step` 看得到。
- 注入语义:不打断当前 step;当前 step 完成 → 注入 → 下一步决策吃到。措辞类似:
  `"[用户中途干预] 用户说:<msg>。据此调整后续计划。"`

### 3. 三端入口(投递到 steering 队列)
- **CLI**:跑的时候本是阻塞的,要中途输入需要一个并发输入通道。最简方案:CLI 后台跑时不直接 input;干预走"另开一个 `research-harness steer --session X "<msg>"` 子命令" → 经 worker 投进队列。或 TTY 下一个非阻塞 stdin 读线程。(待定,见下方待拍板)
- **TUI / 网页端**:本就连 worker,发一个 WS action `{action:"steer", session_id, message}` → worker 投进该会话 steering 队列。
- 子进程场景:research_agent 在子进程跑时,worker 收到 steer → 经 IPC steering_queue 下发(复用 process_runner 的 IPC 桥,和 stop_queue 同法)。

## 待用户拍板
1. **CLI 怎么中途输入**:研究跑通常是后台/限时,CLI 当前进程在阻塞跑。
   - 方案 A:独立子命令 `research-harness steer --session X "msg"`(另一个终端发),走 worker 投递。干净,不碰主进程阻塞。
   - 方案 B:主进程开一个非阻塞 stdin 线程,跑的时候直接敲字注入。TTY 才有效,后台跑没用。
   - 推荐 A(对"后台/限时跑"最实用;TUI/网页端是主要交互面)。
2. **注入后是否强制重新 _pick_stage**:收到干预,是只把消息加进上下文让模型自己决定要不要转向,还是强制重跑一次 stage 决策?推荐前者(模型自己权衡,更自然)。

## 验证
任务跑到 stage 2 时,从 TUI/网页端发"别写实验了,先补文献",确认:
- 当前 step 不被打断、正常收尾;
- 下一轮 stage 决策的上下文里出现这条干预;
- 路线据此转向(进了 literature 或调整了 sub_task)。
