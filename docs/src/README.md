# piper_control_demo

基于 [piper-control](https://github.com/Reimagine-Robotics/piper_control) 的 Piper 机械臂实验仓库，用于沉淀真实硬件连接、基础控制、状态观察、仿真映射等调试能力。

## 文档职责

- 根目录 `README.md`：仓库首页快速总览和常用命令。
- 本页 `docs/src/README.md`：完整的项目入口说明，包含结构解释、设计决策和安全约束。
- 两者内容变化时应保持同步。
- `docs/src/` 下 Markdown 文件的新建、删除、重命名或移动，必须同步更新 `docs/src/SUMMARY.md`。

## 依赖与环境

- Python `>=3.10`，包管理使用 `uv`，文档使用 `mdBook`
- 核心依赖：`piper-control[gravity]`、`pinocchio`
- 默认面向一台已正确连接的 Piper 机械臂和可用的 CAN 接口

## 仓库结构

### 代码包

**`src/piper_control_demo/`** — 核心库

- `config.py`：CAN 端口发现与激活、机械臂/夹爪使能（`ensure_arm_and_gripper_enabled()`）、碰撞保护配置与验证（`configure_collision_protection()`）
- `control.py`：公共控制辅助——软件层键盘急停、程序层运动异常守护、公共收尾失能流程（`confirm_and_shutdown()`）
- `core/path.py`：项目根目录定位，`assets/`、URDF 等资源路径索引

**`src/piper_socket_bridge/`** — Socket 流式桥接

统一协议格式 `{"t": ..., "q": [j1..j6], "gripper": ...}`，支持双向数据流：

| 方向 | 发送端 | 接收端 | 端口 |
|------|--------|--------|------|
| sim→robot | `sim_adapter/pybullet_sender.py`（仿真滑条） | `receiver/robot_follow.py`（真实臂跟随） | 15001 |
| robot→sim | `robot_sender.py`（真实臂状态） | `sim_adapter/pybullet_receiver.py`（仿真镜像） | 15002 |

robot→sim 方向的仿真接收端会在首帧用 `resetJointState` 瞬移对齐真实臂位姿，之后用 position control 持续跟随；接收侧取最新帧丢弃中间帧，避免延迟累积。

**`src/piper_pybullet_sim/`** — PyBullet 仿真辅助

- `slider_arm_gripper.py`：将仿真夹爪从 joint7/joint8 两个独立滑条整理为单一 `gripper_position` 滑条，内部按镜像关系同步驱动两侧手指。对外语义 `[0.0, 0.1]`，仿真内部 `[0.0, 0.175]`，线性比例 `1.75` 换算。

### 脚本与测试

**`scripts/`** — 日常操作脚本（详见 `scripts/README.md`）

| 脚本 | 说明 | 控制真实臂 |
|------|------|:-:|
| `show_status.py` | 200Hz JSON 行流输出关节/夹爪状态 | 只读 |
| `move_debug.py` | 运动调试（键盘急停 + 运动守护 + 碰撞保护） | 是 |
| `disable_safe.py` | 安全失能 | 是 |
| `old_move_debug.py` | 旧版运动调试（仅供参考） | 是 |
| `piper-generate-udev-rule` | CAN udev 规则生成（bash） | 否 |

**`tests/`** — 测试脚本，按类别分目录（详见 `tests/README.md`）

| 目录 | 内容 |
|------|------|
| `hardware/` | 硬件连接与初始化（`connect_init.py`） |
| `socket/` | socket 流测试：sim→robot 和 robot→sim 两个方向 |
| `gamepad/` | 手柄遥操关节控制 |
| `socket_old/` | 旧版 socket 测试（已废弃，不作为新代码参考） |

### 其他目录

- `assets/`：机器人描述与 URDF 资源
- `docs/reference/`：外部仓库文本参考（lerobot、gamepad_piper 等）

## 设计约定

### 控制基线

新的真实机械臂控制代码应以 `scripts/move_debug.py` 的控制方式为基线，优先复用以下公共能力：

1. **使能准备**：`ensure_arm_and_gripper_enabled()`
2. **碰撞保护**：`configure_collision_protection()`
3. **键盘急停 + 运动守护**：`move_to_position_with_keyboard_stop()`
4. **收尾失能**：`confirm_and_shutdown()`

不再参考 `tests/socket_old/` 中的旧版控制流程。

### 夹爪配置

默认按 `PiperGripperType.V2` 理解：`gripper_pos` 合法区间 `[0.0, 0.1]` 米，`gripper_effort` 最大值 `2.0 Nm`。

## 推荐阅读顺序

1. 根目录 `README.md` → 快速总览
2. 本页 → 完整结构与设计约定
3. `src/piper_control_demo/config.py` → 连接与初始化逻辑
4. `scripts/move_debug.py` → 控制基线
5. `scripts/README.md` / `tests/README.md` → 脚本用途速查

## 安全说明

- 任何会让机械臂上电、使能、复位、驱动夹爪或发生实际运动的操作，都属于高风险动作，必须由人类操作者在确认现场安全后执行。
- AI 可协助读写代码和文档，但不能代替人工执行机械臂运动控制。
- 执行动作脚本前，确认机械臂周围无人和障碍物。
- 执行失能前，确认机械臂处于安全姿态（掉电后可能下坠）。
