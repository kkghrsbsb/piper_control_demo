# piper_control_demo

`piper_control_demo` 是一个基于 `piper-control` 的 Piper 机械臂实验仓库。

这个仓库当前的重点不是封装一套完整业务系统，而是把“连接机械臂、初始化、执行基础动作、观察状态、尝试重力补偿与轨迹录制”这些实际调试动作沉淀成可复用的脚本和少量辅助代码。后续阅读项目时，建议先从这里开始，再进入具体脚本与源码。

## 文档职责

- 根目录 [`README.md`](/home/xinger/MyWork/piper_control_demo/README.md) 负责提供仓库首页级别的快速总览和最常用执行命令。
- 本页 [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md) 是更完整的项目入口说明，用来沉淀项目定位、结构解释、脚本用途、执行边界与安全约束。
- 当本页内容因为项目演进而更新时，根目录 [`README.md`](/home/xinger/MyWork/piper_control_demo/README.md) 也应根据这里的变化同步更新，尤其是常用命令和安全说明。
- `docs/src/` 下的 Markdown 文档只要发生新建、删除、重命名或移动，就必须同步更新 [`docs/src/SUMMARY.md`](/home/xinger/MyWork/piper_control_demo/docs/src/SUMMARY.md)，确保 mdBook 目录保持准确。

## 项目目标

从现有文件来看，这个仓库主要服务于以下几件事：

1. 验证 `piper-control` 在本地 uv 项目中的接入方式。
2. 固化 Piper 机械臂的 CAN 连接与初始化流程。
3. 提供几个面向真实硬件的调试脚本，便于快速检查状态和动作控制。
4. 保留一条“重力补偿 + 示教/轨迹回放”的实验路径，作为后续探索基础。

## 当前状态

项目还处在很早期的实验阶段，代码量不大，但方向已经比较明确：

- 包管理使用 `uv`
- 文档使用 `mdBook`
- Python 包源码位于 `src/piper_control_demo/`
- 资源文件当前已经开始整理到 `assets/`
- 主要可执行能力目前集中在 `scripts/`
- `tests/` 当前保留少量需要人工触发的专项硬件测试
- 部分能力已经可日常调试使用，部分能力仍然明确标注为实验性

## 依赖与环境

项目在 [`pyproject.toml`](/home/xinger/MyWork/piper_control_demo/pyproject.toml) 中声明了核心依赖：

- Python `>=3.10`
- `piper-control[gravity]`
- `pinocchio`

这说明项目默认面向：

- 一台已经正确连接的 Piper 机械臂
- 可用的 CAN 接口
- 需要时可启用重力补偿相关能力

## 仓库结构

### 代码包

源码位于 [`src/piper_control_demo`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo)。

- [`config.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/config.py)
  负责 CAN 端口发现、激活，以及机械臂使能状态探测。
- [`core/path.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/core/path.py)
  提供项目根目录定位，并维护 `assets/`、机器人描述和 URDF 等资源路径索引。
- [`models/piper_grav_comp.xml`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/models/piper_grav_comp.xml)
  是重力补偿实验使用的模型文件。

### 资源目录

- `assets/`
  用于放置项目资源文件；从当前 `core/path.py` 来看，已经开始纳入机器人描述与 URDF 相关路径。

- 当前默认夹爪配置按 `PiperGripperType.V2` 理解，`gripper_pos` 的常用合法区间可按 `0.0` 到 `0.1` 米、`gripper_effort` 最大值按 `2.0 Nm` 理解。

### 调试脚本

[`scripts`](/home/xinger/MyWork/piper_control_demo/scripts) 目录下现在同时包含“硬件调试脚本”和“工具/实验脚本”。

- [`show_status.py`](/home/xinger/MyWork/piper_control_demo/scripts/show_status.py)
  连接机械臂后持续打印状态与关节信息，适合确认通信是否正常。
- [`move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py)
  用于基础动作调试，包含初始化、将 6 个关节的碰撞保护等级固定设为 `5`、在 `reset_gripper` 后确认夹爪使能、按手工可改的 7 维目标位分别控制 6 关节与夹爪，以及可选的安全失能流程；当前脚本前部已经整理出几个关键调参项：`TARGET_POSE_7D` 表示 `[j1, j2, j3, j4, j5, j6, gripper_pos]`，`JOINT_SAFE_SPEED` 表示内置位置速度控制模式下的安全速度建议值，`GRIPPER_EFFORT_NOW` 表示当前夹爪夹持力度，`COLLISION_PROTECTION_LEVELS` 表示 6 个关节的碰撞保护等级。
- [`disable_safe.py`](/home/xinger/MyWork/piper_control_demo/scripts/disable_safe.py)
  用于手动让机械臂失能，执行前要求机械臂已经处于安全姿态。

### 专项测试

[`tests`](/home/xinger/MyWork/piper_control_demo/tests) 目录当前用于放置少量需要人工确认、不会被当成普通自动化测试直接批量执行的专项硬件测试。

- [`socket_joint_stream_test.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_joint_stream_test.py)
  参考 `move_debug.py` 的初始化流程，在机械臂运动到零位后启动本机模拟 socket 发送，并按 200Hz 关节角流驱动机械臂从零位跟随到目标位姿。
- [`pybullet_socket_stream_sender.py`](/home/xinger/MyWork/piper_control_demo/tests/pybullet_socket_stream_sender.py)
  启动 PyBullet 滑条仿真，并把前 6 个关节的当前目标值以 200Hz socket JSON 行流持续发送出去。
- [`socket_joint_realtime_follow.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_joint_realtime_follow.py)
  在真实机械臂回零后等待发送端前几帧回到零位，确认后进入实时跟随；控制保持按流实时下发，当前关节角输出采用降采样打印，并支持按 `q` 键结束跟随后再进入失能确认。

### 实验脚本

[`scripts`](/home/xinger/MyWork/piper_control_demo/scripts) 目录包含更偏“工具化”的内容。

- [`piper-generate-udev-rule`](/home/xinger/MyWork/piper_control_demo/scripts/piper-generate-udev-rule)
  用来给 CAN 设备生成持久化识别与自动配置规则，目标是减少每次手工初始化接口的负担。
- [`record_trajectories.py`](/home/xinger/MyWork/piper_control_demo/scripts/record_trajectories.py)
  提供交互式轨迹录制、保存、加载与回放，也支持结合重力补偿进行示教实验。
- [`scripts/README.md`](/home/xinger/MyWork/piper_control_demo/scripts/README.md)
  已经记录了这部分脚本的背景和风险说明。

## 目前最值得先读的文件

如果是第一次接手这个仓库，推荐按下面顺序阅读：

1. 根目录 [`README.md`](/home/xinger/MyWork/piper_control_demo/README.md)
2. 本页 [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md)
3. [`src/piper_control_demo/config.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/config.py)
4. [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py)
5. [`scripts/README.md`](/home/xinger/MyWork/piper_control_demo/scripts/README.md)
6. [`scripts/record_trajectories.py`](/home/xinger/MyWork/piper_control_demo/scripts/record_trajectories.py)
7. [`tests/socket_joint_stream_test.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_joint_stream_test.py)
8. [`tests/pybullet_socket_stream_sender.py`](/home/xinger/MyWork/piper_control_demo/tests/pybullet_socket_stream_sender.py)
9. [`tests/socket_joint_realtime_follow.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_joint_realtime_follow.py)

这条路径基本对应了“项目定位 -> 连接流程 -> 基础控制 -> 实验方向”的理解顺序。

## 一条实际可用的理解路径

### 1. 先理解连接逻辑

`connect_can()` 会：

- 调用 `piper_connect.find_ports()` 查找可用端口
- 激活端口
- 再次读取已激活端口
- 在没有发现端口时直接报错

这意味着当前仓库默认假设“真实硬件在线”，并没有做模拟器或离线模式封装。

### 2. 再理解初始化与安全动作

[`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 展示了一个比较完整的动作链路：

- 查找并连接机械臂
- 提醒操作者确认即将运动
- 检查当前是否已使能
- 必要时执行 `reset_arm`
- 执行 `reset_gripper`
- 确认夹爪已使能
- 设置 6 个关节的碰撞保护等级为 `5`
- 进入位置控制器并按 7 维目标位分别控制 6 个关节和夹爪
- 可选地回到安全位后失能

如果后续要手工调试这个脚本，最先关注的通常就是：

- `TARGET_POSE_7D`
  前 6 维是关节目标，第 7 维是夹爪位置。
- `JOINT_SAFE_SPEED`
  当前用于限制基础运动调试速度，值越小通常越保守。
- `GRIPPER_EFFORT_NOW`
  当前夹爪命令使用的力度。
- `COLLISION_PROTECTION_LEVELS`
  当前 6 个关节的碰撞保护等级。

这也是目前最接近“项目主流程”的脚本。

### 3. 最后再看重力补偿实验

[`scripts/record_trajectories.py`](/home/xinger/MyWork/piper_control_demo/scripts/record_trajectories.py) 比基础调试更进一步，支持：

- 单臂或双臂
- 轨迹录制
- 轨迹回放
- 夹爪开合控制
- 保存/加载 JSON 轨迹
- 可选的重力补偿模型加载

但从 [`scripts/README.md`](/home/xinger/MyWork/piper_control_demo/scripts/README.md) 的说明来看，这部分仍然带有明显实验性质，尤其是样本采集和碰撞风险需要非常谨慎。

## 建议的常用命令

下面这些命令是根据仓库现状整理出的常见入口。

```bash
# 安装依赖
uv sync

# 查看机械臂状态
uv run python scripts/show_status.py

# 进行基础运动调试
uv run python scripts/move_debug.py

# 手动失能机械臂
uv run python scripts/disable_safe.py

# 轨迹录制 / 回放实验
uv run python scripts/record_trajectories.py --robots can0

# 启动 PyBullet 滑条发送端
uv run python tests/pybullet_socket_stream_sender.py

# 启动真实机械臂实时跟随接收端
uv run python tests/socket_joint_realtime_follow.py
```

如果需要查看文档：

```bash
mdbook serve docs
```

## 安全说明

这个项目直接控制真实机械臂，很多脚本都不是“只读操作”。

在当前仓库里，至少要默认记住下面几点：

- 文档编写、代码修改和流程分析可以由 AI 协助完成，但任何会让机械臂上电、使能、复位、解除保护、执行轨迹、驱动夹爪或发生实际运动的操作，都必须由人类操作者在确认现场安全后亲自决定并执行。
- AI 不应主动执行或代为尝试任何“激活机械臂并进行运动控制”的步骤，即使仓库里已经存在对应脚本，也只能说明用途、分析代码、补充文档或调整实现，不能把危险动作当成普通验证步骤直接运行。
- 如果某个任务需要验证真实运动效果，边界应明确理解为“可以准备代码和命令，但不能替代人工下发到真实机械臂执行”。
- 执行动作脚本前，先确认机械臂周围没有人和障碍物。
- 执行失能前，先确认机械臂处于安全姿态，因为掉电后可能下坠。
- 重力补偿采样和示教相关脚本风险更高，当前仓库已经明确提示存在碰撞风险。
- 当前会直接操作真实硬件的调试脚本已经放在 `scripts/` 下，不应按普通自动化测试理解。
- `tests/socket_joint_stream_test.py` 同样会真实驱动机械臂，只应用于人工在场、明确确认后的专项测试。
- `tests/socket_joint_realtime_follow.py` 会把仿真滑条变化实时映射到真实机械臂，风险高于单次轨迹测试，必须在人工看护下运行。

## 这个文档后续应该继续补什么

作为 mdBook 入口页，后续最值得继续拆分成独立章节的内容有：

1. 环境准备：Python、uv、CAN、udev 规则配置。
2. 首次连接 Piper 的完整步骤。
3. 基础控制流程：连接、复位、位置控制、失能。
4. 调试脚本说明：每个脚本的用途、前置条件、风险。
5. 重力补偿实验记录：样本采集、参数、已知问题。
6. 上游依赖说明：本项目依赖哪些 `piper-control` 能力，哪些行为继承自上游。

## 一句话总结

可以把这个仓库理解为：一个围绕真实 Piper 机械臂调试而建立的 `uv + mdBook` Python 实验工程，当前已经具备基础连接与运动调试能力，并保留了重力补偿和轨迹示教的探索入口。
