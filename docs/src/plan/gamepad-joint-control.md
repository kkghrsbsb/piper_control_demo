# 手柄遥操关节控制

## 功能目标

在 `tests/gamepad_joint_control.py` 中实现基于 pygame 手柄的关节级遥操，使用纯 `piper_control` 控制真实 Piper 机械臂的 6 个关节和夹爪。本阶段只做关节模式控制，不做位姿（末端笛卡尔）控制；位姿控制后续用 URDF + pinocchio 实现。

脚本只依赖 `piper_control` 和 `pygame`，不使用 `src/piper_control_demo/` 中的库代码，以便后续迁移到其他仓库复用。

## 参考来源

- [`docs/reference/kehuanjack-gamepad_piper-8a5edab282632443.txt`](/home/xinger/MyWork/piper_control_demo/docs/reference/kehuanjack-gamepad_piper-8a5edab282632443.txt)
  kehuanjack 的 `Gamepad_PiPER` 仓库，基于 `piper_sdk` 和 pygame，提供了手柄关节/位姿双模式遥操。我们参考它的手柄映射逻辑和关节增量控制思路，但不复用其代码，而是用 `piper_control` 重写。

## 当前问题与动机

- 当前仓库只有 `move_debug.py` 式的"写死目标位 → 一次运动"调试流程，没有实时交互式关节控制。
- 需要一种操作者可以实时微调每个关节的方式，用于调试姿态、验证关节限位、探索工作空间。
- 手柄遥操是最直观的实时交互方式之一。

## 前置条件

手柄控制脚本本身不负责初始化机械臂。操作者需要先在另一个终端运行 `tests/connect_init.py`，使机械臂进入使能 + 零位状态。本脚本启动后通过独立的 `PiperInterface` 连接同一个 CAN 总线，验证使能和零位后才进入控制循环。

## 设计概述

### 整体架构

在已有的 `tests/gamepad_joint_control.py` 骨架上，补全 `gamepad_control()` 函数。

脚本逻辑分为三个阶段：

1. **检测阶段**（已完成）：通过独立 CAN 连接 → 多次采样检测使能状态 → 检查是否在零位附近（阈值 0.05 rad）。
2. **手柄控制循环**（待实现）：pygame 初始化 → 检测手柄连接 → 以固定频率读取手柄输入 → 计算关节增量 → 通过 `robot.command_joint_positions()` 和 `robot.command_gripper()` 下发。
3. **退出阶段**：A 键退出循环 → 回零位（`builtin_move` 方式） → 检测零位稳定 → 提示用户在 `connect_init.py` 终端完成失能。

### 手柄映射（仅关节模式）

参考 kehuanjack 的映射方案，本阶段只保留关节模式部分：

| 控制元素 | 功能 |
|---------|------|
| 左摇杆 左/右 | J1（底座旋转） |
| 左摇杆 上/下 | J2（肩部） |
| 右摇杆 上/下 | J3（肘部） |
| 右摇杆 左/右 | J6（腕旋转） |
| D-pad 左/右 | J4（腕偏航） |
| D-pad 上/下 | J5（腕俯仰） |
| LT（左扳机） | 夹爪关闭 |
| RT（右扳机） | 夹爪打开 |
| Y 按键 | 回零位（builtin_move 方式移动到零位 → 检测零位稳定后才恢复手柄控制） |
| A 按键 | 退出控制循环（先回零位并检测零位稳定，再退出） |
| LB 短按 | 增加速度因子 |
| RB 短按 | 减少速度因子 |

### 回零位流程（Y 键和 A 键共用）

回零位不能用手柄增量的方式，而要用与 `connect_init.py` 中 `builtin_move` 一样的 `BuiltinJointPositionController` 阻塞式移动：

1. 暂停手柄增量控制
2. 通过 `BuiltinJointPositionController` + `move_to_position([0,0,0,0,0,0])` 阻塞式回零
3. 回零后，按 `check_arm_status` 的方式多次采样检测关节位是否已在零位附近且稳定
4. Y 键：检测通过后恢复手柄控制循环
5. A 键：检测通过后退出控制循环

### 关节增量控制

- 维护一个 `target_q = [j1, ..., j6]` 数组，初始值从机械臂当前位读取（零位）。
- 每个控制周期，根据摇杆偏移量 × 步长 × 速度因子计算增量，累加到 `target_q`。
- 关节角裁剪到 URDF 限位范围内。
- 通过 `robot.command_joint_positions(target_q)` 直接下发（不使用 `BuiltinJointPositionController`，以获得更直接的响应）。

### 夹爪控制

- 维护一个 `gripper_pos`，范围 `[0.0, 0.1]`（与本仓库已有语义一致）。
- LT 按下时减小，RT 按下时增大，步长按扳机模拟量缩放。
- 通过 `robot.command_gripper(gripper_pos, effort)` 下发。

### 速度因子

- 可选值：`[0.25, 0.5, 1.0, 2.0, 3.0]`
- 默认索引：`0`（即 0.25x），保证初始安全
- LB 短按增加一档，RB 短按减少一档，循环切换
- 不使用长按逻辑

### 控制频率与安全

- 控制循环目标频率 ~200Hz，`pygame.time.wait(5)` 约 5ms。
- 关节速度设为保守值（`JOINT_SAFE_SPEED = 10`）。
- 不接入程序层运动异常守护（`move_to_position_with_keyboard_stop`），因为手柄控制是连续增量模式，不存在"单次运动到目标位"的语义；操作者通过松开摇杆即可停止增量。
- 本脚本不负责失能，失能由 `connect_init.py` 终端完成。

### 不做的事情

- **不做位姿模式**：后续用 URDF + pinocchio 做正/逆运动学再加。
- **不做 viser 可视化**：参考仓库用 viser 做 Web 3D 可视化，本阶段不需要。
- **不做位置记忆/回放**：参考仓库有 A/B/X 按键的位置保存和回放功能，本阶段不做。
- **不做 0xAD 快速响应模式切换**：只使用默认位置速度控制模式。
- **不使用 `src/piper_control_demo/` 库代码**：保持脚本可独立迁移。

## 受影响文件

| 文件 | 操作 |
|------|------|
| `tests/gamepad_joint_control.py` | **修改**（在已有骨架上补全 `gamepad_control()` 函数） |
| `docs/src/README.md` | 更新：添加参考资料说明、添加新脚本说明、移除 LeRobot 未来计划描述 |
| `README.md` | 同步更新 |
| `docs/src/SUMMARY.md` | 已更新 |

## 新增依赖

通过 `uv add pygame` 添加。参考仓库要求 `pygame<2.6.2`，如遇兼容性问题再加版本约束。

## 风险与注意事项

1. **手柄兼容性**：pygame 的 joystick 映射与手柄型号、操作系统有关，参考仓库区分了 Windows/Linux 映射。我们当前只在 Linux 上运行，先按 Linux 映射实现，后续如有需要再扩展。
2. **增量累积安全**：如果操作者长时间推满摇杆，关节角会持续累积到限位。URDF 限位裁剪是第一层保护，机械臂底层碰撞保护是第二层。
3. **零位检查精度**：阈值设为 0.05 rad（约 2.9°），过严会因为零位微偏导致无法启动，过松会失去保护意义。
4. **CAN 共存**：本脚本通过独立的 `PiperInterface` 连接同一个 CAN 总线，已验证可以读取状态和发送命令。
5. **脚本会真实驱动机械臂**：与 `move_debug.py` 同级别风险，必须在人工看护下运行。

## 实现步骤

1. 通过 `uv add pygame` 添加依赖。
2. 在 `tests/gamepad_joint_control.py` 中补全 `gamepad_control()` 函数：
   - pygame 初始化与手柄检测
   - 关节限位常量定义
   - 关节增量控制循环（摇杆 → 增量 → 裁剪 → `robot.command_joint_positions()`）
   - 夹爪扳机控制（`robot.command_gripper()`）
   - Y 键回零位（`builtin_move` + `check_arm_status` 检测零位稳定）
   - A 键退出（先回零位并检测，再退出循环）
   - LB/RB 速度因子切换
3. 更新 `docs/src/README.md`：
   - 在参考资料部分添加 kehuanjack 仓库说明
   - 在测试脚本部分添加 `gamepad_joint_control.py` 和 `connect_init.py` 说明
   - 移除 LeRobot 接入相关的未来计划描述（已在其他仓库完成）
4. 同步更新 `README.md`。
