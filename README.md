# piper_control_demo

这是一个基于 `piper-control` 的 Piper 机械臂实验仓库，用来整理真实硬件上的连接、初始化、基础控制、状态观察，以及重力补偿/轨迹录制相关探索。

更完整的项目入口说明见 [`docs/src/README.md`](./docs/src/README.md)。根目录 `README.md` 适合作为仓库首页总览；当 [`docs/src/README.md`](./docs/src/README.md) 更新脚本用途、执行方式或安全边界时，这里的内容也应同步调整。

```bash
# docs/ 使用mdbook构建，可在线查看
cargo install mdbook
mdbook serve docs
```

## 执行说明

### 安装依赖

```bash
uv sync
```

### 常用命令

```bash
# 查看机械臂状态
uv run python scripts/show_status.py

# 基础运动调试
uv run python scripts/move_debug.py

# 手动失能机械臂
uv run python scripts/disable_safe.py

# 轨迹录制 / 回放实验
uv run python scripts/record_trajectories.py --robots can0

# 手柄遥操（终端 1：初始化；终端 2：手柄控制）
uv run python tests/connect_init.py
uv run python tests/gamepad_joint_control.py

# 启动 PyBullet 滑条发送端
uv run python tests/pybullet_socket_stream_sender.py

# 启动真实机械臂实时跟随接收端
uv run python tests/socket_joint_realtime_follow.py

# 本地预览 mdBook 文档
mdbook serve docs
```

## 重要说明

- 这个仓库连接真实机械臂，`scripts/` 下有多份会直接操作硬件的调试脚本。
- `tests/` 下也有少量需要人工触发的专项硬件测试，例如 socket 关节流跟随、PyBullet 实时映射测试和手柄遥操关节控制。
- `tests/gamepad_joint_control.py` 提供基于 pygame 手柄的关节级实时遥操，纯 `piper_control` 实现；需要先在另一个终端运行 `tests/connect_init.py` 完成初始化。
- `src/piper_socket_bridge/` 已作为后续 socket 关节流转发的新库目录；新实现应以当前新版 `scripts/move_debug.py` 的基础控制方式为标准，`tests/socket_old/` 仅保留作历史参考。
- `src/piper_socket_bridge/` 当前已初步搭出统一 `q + gripper` 协议、PyBullet 发送端和真实机械臂接收端骨架；其中 PyBullet 发送端现在发送的是仿真真实状态流，而不是滑条目标值。`tests/socket_old/` 仅保留作历史参考。
- `scripts/show_status.py` 当前会以约 200Hz 输出 `{"t": ..., "q": [...], "gripper": ...}` JSON 行流，可作为新的状态观察与协议参考格式。
- 任何会让机械臂上电、使能、复位、驱动夹爪或发生实际运动的操作，都属于高风险动作。
- AI 可以协助读代码、写代码、改文档、整理命令和分析流程，但不能代替人工去执行激活机械臂并进行运动控制的尝试。
- `scripts/move_debug.py` 当前已把关键调参项整理在文件前部，包括 `TARGET_Q`、`TARGET_GRIPPER`、`JOINT_SAFE_SPEED`、`GRIPPER_EFFORT_NOW` 和 `COLLISION_PROTECTION_LEVELS`，并支持在手工可改的目标位里分别控制 6 个关节与夹爪；碰撞保护的写入与验证逻辑也已抽到 `src/piper_control_demo/config.py` 统一复用。
- 项目当前已把 `move_debug.py` 中的软件层键盘急停抽为公共实现；后续涉及 `BuiltinJointPositionController` 的真实机械臂控制脚本，应默认优先复用这套能力。
- 项目当前也已把“目标误差长期不下降就停止继续下发新目标位”的程序层运动异常守护抽为公共实现；它用于尽早发现疑似阻挡、卡住或响应异常，但不能替代底层碰撞保护或硬件急停。
- 项目当前也已把“人工确认后回安全位并失能”的收尾流程抽为公共实现；后续存在类似收尾逻辑的真实机械臂控制脚本，应默认优先复用这套流程。
- `src/piper_pybullet_sim/slider_arm_gripper.py` 当前把仿真夹爪整理成单一 `gripper_position` 滑条，并在内部镜像驱动两侧夹爪手指；对外滑条语义使用 `[0.0, 0.1]`，仿真内部控制使用 `[0.0, 0.175]`，两者通过线性比例 `1.75` 换算。
- 涉及风险边界、项目结构和脚本用途的更完整说明，以 [`docs/src/README.md`](./docs/src/README.md) 为准。
