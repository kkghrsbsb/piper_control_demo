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

# 启动 PyBullet 滑条发送端
uv run python tests/pybullet_socket_stream_sender.py

# 启动真实机械臂实时跟随接收端
uv run python tests/socket_joint_realtime_follow.py

# 本地预览 mdBook 文档
mdbook serve docs
```

## 重要说明

- 这个仓库连接真实机械臂，`scripts/` 下有多份会直接操作硬件的调试脚本。
- `tests/` 下也有少量需要人工触发的专项硬件测试，例如 socket 关节流跟随和 PyBullet 实时映射测试。
- 任何会让机械臂上电、使能、复位、驱动夹爪或发生实际运动的操作，都属于高风险动作。
- AI 可以协助读代码、写代码、改文档、整理命令和分析流程，但不能代替人工去执行激活机械臂并进行运动控制的尝试。
- `scripts/move_debug.py` 当前已把关键调参项整理在文件前部，包括 `TARGET_POSE_7D`、`JOINT_SAFE_SPEED`、`GRIPPER_EFFORT_NOW` 和 `COLLISION_PROTECTION_LEVELS`，并支持在手工可改的 7 维目标位里同时控制 6 个关节与夹爪。
- `src/piper_pybullet_sim/slider_arm_gripper.py` 当前把仿真夹爪整理成单一 `gripper_position` 滑条，并在内部镜像驱动两侧夹爪手指；这是仿真控制语义的优化，后续 7 位目标位 / 7 维数据流链路仍需继续接入。
- 涉及风险边界、项目结构和脚本用途的更完整说明，以 [`docs/src/README.md`](./docs/src/README.md) 为准。
