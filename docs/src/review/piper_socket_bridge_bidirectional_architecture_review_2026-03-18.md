# piper_socket_bridge 双向扩展架构审查 2026-03-18

## Review Scope

本次审查聚焦于 [`src/piper_socket_bridge`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge) 当前这版“仿真发送 -> 真实机械臂接收”的初步实现，并评估它是否适合作为后续“真实机械臂主臂 -> PyBullet 从臂”以及进一步双向扩展的基础。

本次不改代码，只给出结构审查和后续框架建议。

## Files Reviewed

- [`src/piper_socket_bridge/protocol.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/protocol.py)
- [`src/piper_socket_bridge/sim_adapter/pybullet_sender.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py)
- [`src/piper_socket_bridge/receiver/robot_follow.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/receiver/robot_follow.py)
- [`src/piper_pybullet_sim/slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py)
- [`src/piper_pybullet_sim/joint_slider_control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/joint_slider_control.py)
- [`docs/src/plan/piper_socket_bridge_unified_7d_adapters.md`](/home/xinger/MyWork/piper_control_demo/docs/src/plan/piper_socket_bridge_unified_7d_adapters.md)
- [`docs/src/plan/slider_arm_gripper_based_sim_and_bidirectional_tests.md`](/home/xinger/MyWork/piper_control_demo/docs/src/plan/slider_arm_gripper_based_sim_and_bidirectional_tests.md)
- [`docs/src/next/2026-03-16_master_arm_to_pybullet_slave.md`](/home/xinger/MyWork/piper_control_demo/docs/src/next/2026-03-16_master_arm_to_pybullet_slave.md)

## Current Behavior Summary

当前这套实现已经完成了第一条单向链路：

- PyBullet 发送端基于 [`slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py) 的单一 `gripper_position` 语义工作
- 发送端会先写入滑条目标，再 `stepSimulation()`，最后读取仿真真实状态并发送
- 协议格式已经统一成：

```json
{"t": 0.000, "q": [j1, j2, j3, j4, j5, j6], "gripper": 0.8}
```

- 真实机械臂接收端会在回零后接收该流，并在同一个控制周期内依次执行：
  - `controller.command_joints(frame.q)`
  - `robot.command_gripper(frame.gripper, fixed_effort)`

也就是说，现在已经证明“新协议 + 新夹爪语义 + 单向仿真到真实机械臂”这条路是通的。

## Findings

### 1. 协议层还没有区分“目标命令流”和“真实状态流”

- Severity: high
- Files:
  - [`protocol.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/protocol.py)
  - [`pybullet_sender.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py)
  - [`robot_follow.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/receiver/robot_follow.py)

当前 [`PoseStreamFrame`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/protocol.py) 只有 `t/q/gripper` 三个字段，见 [`protocol.py:10`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/protocol.py#L10)。

但现在系统里已经同时存在两种不同语义：

- 仿真发送端输出的是“仿真真实状态流”，见 [`pybullet_sender.py:102`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py#L102)
- 真实机械臂接收端却把同样的帧结构当成“实时目标命令流”直接下发，见 [`robot_follow.py:116`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/receiver/robot_follow.py#L116)

这在单向链路里暂时还可接受，但一旦进入：

- 真实机械臂 -> 仿真
- 双向同时存在
- LeRobot `target_pose` 适配
- 录制、回放、日志复用

就会出现同一结构到底表示“命令”还是“状态”的歧义。

#### Root Cause

当前协议只统一了字段形状，没有统一帧语义。

#### Recommended Direction

不要马上推翻 `q + gripper`，而是在保持这三个核心字段的前提下，为后续协议升级预留额外元信息，例如：

- `kind`: `state` / `command`
- `source`: `pybullet` / `robot` / `lerobot`
- `version`
- 可选的 `seq`

第一阶段甚至可以只在内部 dataclass 层增加可选字段，先不强制所有发送端立即改完。

### 2. 方向角色和 socket 生命周期还没有被抽成可复用运行层

- Severity: high
- Files:
  - [`pybullet_sender.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py)
  - [`robot_follow.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/receiver/robot_follow.py)

当前两个主模块都把“业务逻辑 + socket 生命周期 + 循环调度 + 打印”写在一起：

- [`pybullet_sender.py:102`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py#L102)
- [`robot_follow.py:40`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/receiver/robot_follow.py#L40)
- [`robot_follow.py:136`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/receiver/robot_follow.py#L136)

这对当前一个发送端、一个接收端的演示还够用，但不利于继续补出：

- `robot_state_sender.py`
- `sim_adapter/pybullet_receiver.py`
- 双向同时在场的桥接会话

因为后续这些模块几乎必然要重复处理：

- TCP 建连/监听
- 行缓冲拆包
- 发送节流
- 断开重连
- 退出条件
- 日志节流

#### Root Cause

当前代码仍处在“功能证明”阶段，还没有进入“角色复用”阶段。

#### Recommended Direction

建议在 [`src/piper_socket_bridge`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge) 下补一层公共运行层，例如：

- `runtime/transport.py`
  - 行流读写
  - socket client/server 封装
- `runtime/session.py`
  - 单向会话
  - 双向会话
  - 停止条件
  - 基础日志

然后把现在的：

- PyBullet 发送端
- 真实机械臂接收端
- 未来的真实机械臂发送端
- 未来的 PyBullet 接收端

都降级成“适配器 + 会话装配”，而不是各自维护一套主循环。

### 3. PyBullet 的夹爪映射和读写语义还没有沉淀成共享适配器

- Severity: medium-high
- Files:
  - [`slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py)
  - [`pybullet_sender.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py)

当前最有价值的仿真语义，其实已经在 [`slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py) 里了：

- 单一 `gripper_position` 滑条
- 对外 `[0.0, 0.1]` 协议语义
- 对内 `[0.0, 0.175]` 仿真控制语义
- `1.75` 线性映射
- 双指镜像控制

但 [`pybullet_sender.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py) 目前只是直接导入：

- `SliderControl`
- `create_joint_sliders()`
- `GRIPPER_SLIDER_NAME`

然后自己再实现一层“写控制”和“读回真实状态”，见：

- [`pybullet_sender.py:44`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py#L44)
- [`pybullet_sender.py:64`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py#L64)

这意味着后续如果新增 PyBullet 接收端，大概率还会再复制一遍：

- `setJointMotorControl2(...)`
- gripper 双指写入
- gripper 状态恢复
- `1.75` 映射

#### Root Cause

当前 `slider_arm_gripper.py` 还是一个“可运行脚本 + 一些 helper”的状态，还不是面向桥接库的仿真适配 API。

#### Recommended Direction

建议把 PyBullet 适配层拆得更清楚：

- `src/piper_pybullet_sim/adapter.py` 或
- `src/piper_socket_bridge/sim_adapter/pybullet_model.py`

把这些能力收敛成共享函数：

- `load_piper_robot()`
- `create_slider_controls()`
- `apply_protocol_frame_to_pybullet()`
- `read_protocol_frame_from_pybullet()`
- `protocol_gripper_to_sim()`
- `sim_gripper_to_protocol()`

这样未来“PyBullet 发送端”和“PyBullet 接收端”才能真正共享同一套夹爪和关节语义。

### 4. 当前真实机械臂接收端把“启动握手”和“实时跟随”写死成单一路径

- Severity: medium
- Files:
  - [`robot_follow.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/receiver/robot_follow.py)

[`receive_and_follow_stream()`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/receiver/robot_follow.py#L40) 当前把这些规则写死在一个函数里：

- 必须先回零
- 发送端前几帧必须也接近零位
- 零位确认通过后才开始跟随
- `q` 键中断后进入失能确认

这条链路非常适合“仿真 -> 真实机械臂”的安全启动，但它并不适合直接反向复用到：

- 真实机械臂状态发送
- PyBullet 从臂接收
- 双向观察模式

因为这些方向的启动约束不完全一样。

#### Root Cause

当前接收端还承担了“测试流程编排”的职责，而不只是“消费帧并执行”。

#### Recommended Direction

后续最好拆成三层：

- `prepare_real_robot_follow_session()`
  - 回零
  - 使能
  - 碰撞保护
  - 启动安全确认
- `run_stream_consumer_loop()`
  - 只负责读帧、解析、调用回调
- `apply_frame_to_robot()`
  - 只负责 `q + gripper` 下发

这样未来 PyBullet 从臂只需要替换最后一层，而不是复制整个启动流程。

### 5. 当前协议没有帧序号、延迟检测和过期帧策略，不利于后续夹取任务

- Severity: medium
- Files:
  - [`protocol.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/protocol.py)
  - [`robot_follow.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/receiver/robot_follow.py)

现在协议里只有 `t`，而 `t` 只是发送端相对时间，没有统一时钟意义，接收端也没有用它做：

- 过期帧丢弃
- 顺序检测
- 丢帧检测
- 统计日志

在“仿真滑条 -> 真实机械臂”阶段，这个问题还不一定会暴露；但到“真实机械臂主臂 -> PyBullet 从臂做夹取任务”阶段，如果：

- 连接抖动
- 帧堆积
- GUI 卡顿
- 网络延迟

没有基本的帧新鲜度规则，就很容易让从臂吃到旧状态。

#### Root Cause

当前实现更像本机实验链路，没有把传输层不稳定性当成明确设计对象。

#### Recommended Direction

下一阶段至少应补一个可选 `seq`，并在 runtime 层定义最小策略：

- 只保留最新帧
- 检测序号倒退
- 对接收过慢做告警

这对双向和夹取任务都会更稳。

### 6. 当前测试入口主要是脚本包装，缺少“本地可验证”的双向扩展基座

- Severity: medium
- Files:
  - [`tests/pybullet_socket_stream_sender.py`](/home/xinger/MyWork/piper_control_demo/tests/pybullet_socket_stream_sender.py)
  - [`tests/socket_joint_realtime_follow.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_joint_realtime_follow.py)

目前 `tests/` 下的新入口很干净，但它们几乎只是运行入口：

- [`tests/pybullet_socket_stream_sender.py`](/home/xinger/MyWork/piper_control_demo/tests/pybullet_socket_stream_sender.py)
- [`tests/socket_joint_realtime_follow.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_joint_realtime_follow.py)

这对人工联调没问题，但对下一阶段的“真实机械臂 -> PyBullet”扩展还不够，因为你会需要一组不依赖真机的本地验证路径，例如：

- 本地假帧驱动 PyBullet 从臂
- 本地录制流回放到 PyBullet
- 协议字段升级后的兼容测试

#### Root Cause

当前测试更多是在验证链路能跑，而不是验证架构可扩展。

#### Recommended Direction

等下一轮开始实现双向前，建议在 `tests/` 下至少补两类入口：

- 本地假数据 -> PyBullet 从臂
- 录制状态流 -> PyBullet 从臂

这样可以先把“协议 + 仿真接收端”单独打稳，再接真实机械臂发送端。

## Recommended Architecture Direction

综合上面的问题，我更推荐把后续代码框架收敛成下面这组层次。

### 1. 协议层

- `protocol.py`
  - `PoseStreamFrame`
  - 可选 `kind/source/version/seq`
  - 序列化与反序列化

### 2. 运行层

- `runtime/transport.py`
  - 行流 socket 读写
  - client/server 基础封装
- `runtime/session.py`
  - 单向发送会话
  - 单向接收会话
  - 后续双向会话

### 3. 机器人适配层

- `robot_adapter/state_sender.py`
  - 从真实机械臂读当前状态并发出 `PoseStreamFrame`
- `robot_adapter/follow_sink.py`
  - 把 `PoseStreamFrame` 下发到真实机械臂
  - 继续复用 `piper_control_demo.config` 和 `piper_control_demo.control`

### 4. 仿真适配层

- `sim_adapter/pybullet_model.py`
  - 共享加载模型、关节索引、夹爪映射
- `sim_adapter/pybullet_sender.py`
  - 从仿真真实状态发流
- `sim_adapter/pybullet_receiver.py`
  - 接收主臂状态流并驱动仿真从臂

### 5. PyBullet 辅助层

[`src/piper_pybullet_sim`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim) 建议继续保留，但职责要更偏“仿真语义与 UI 基础设施”，而不是直接承载桥接主循环。

比较合适的分工是：

- `slider_arm_gripper.py`
  - 保留为独立可运行的仿真滑条基线
- 新增更偏库化的 helper
  - 关节枚举
  - gripper 双指映射
  - 协议/仿真范围换算

然后让 `piper_socket_bridge` 来复用它们，而不是反过来把桥接逻辑塞回 `src/piper_pybullet_sim`。

## Affected Modules for Next Stage

如果后续要真正进入“真实机械臂主臂 -> PyBullet 从臂 -> 夹取任务”的下一步，这些模块最可能被影响：

- [`src/piper_socket_bridge/protocol.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/protocol.py)
- `src/piper_socket_bridge/runtime/`
- `src/piper_socket_bridge/robot_adapter/`
- `src/piper_socket_bridge/sim_adapter/`
- [`src/piper_pybullet_sim/slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py)
- `tests/` 下新的 PyBullet 从臂验证入口

## Risks, Edge Cases, and Compatibility

- 当前 `q + gripper` 字段结构本身值得保留，问题主要在于缺少语义标注和角色分层，所以不建议下一步大改字段形状。
- 如果直接在现有 `pybullet_sender.py` / `robot_follow.py` 上继续堆双向逻辑，短期能跑，后期会很难维护。
- 夹爪的 `1.75` 映射现在已经是事实标准，后续新增 PyBullet 接收端时必须复用同一套换算，不能再各写各的。
- 真实机械臂控制侧仍应继续以当前新版 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 为安全基线，不要为了双向扩展把初始化、安全、急停和收尾逻辑重新散回 socket 脚本里。

## Suggested Implementation Order

1. 先补一层 `runtime/transport.py` 和 `runtime/session.py`，把 socket 行流生命周期收敛掉。
2. 再把 PyBullet 的读写与 gripper 映射抽成共享适配器，不要让发送端和接收端各自维护。
3. 然后新增 `sim_adapter/pybullet_receiver.py`，先用本地假流验证 PyBullet 从臂。
4. 再新增 `robot_adapter/state_sender.py`，把真实机械臂当前状态稳定地发成统一协议。
5. 最后才进入“真实机械臂主臂 -> PyBullet 从臂”的整链路夹取任务验证。

## One-Line Conclusion

当前 [`src/piper_socket_bridge`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge) 已经足够支撑“仿真真实状态 -> 真实机械臂跟随”这条第一版单向链路，但如果要顺利扩展到“真实机械臂主臂 -> PyBullet 从臂”乃至双向桥接，最值得优先补强的不是单个脚本功能，而是协议语义、运行层复用、PyBullet 共享适配器和角色分层。
