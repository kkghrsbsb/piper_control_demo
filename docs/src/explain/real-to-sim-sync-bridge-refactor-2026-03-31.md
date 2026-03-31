# 真实机械臂到仿真同步 & piper_socket_bridge 重构变更说明

## 变更范围

本次变更为 `piper_socket_bridge` 模块新增了 robot→sim 方向的流式传输能力，使模块同时支持双向数据流：

- **sim→robot**（已有）：PyBullet 滑条驱动仿真，状态流推送到真实机械臂跟随
- **robot→sim**（本次新增）：真实机械臂状态流推送到 PyBullet 仿真，实现实时数字孪生

## 涉及文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `src/piper_socket_bridge/robot_sender.py` | 真实机械臂 200Hz 状态流发送器 |
| 新建 | `src/piper_socket_bridge/sim_adapter/pybullet_receiver.py` | 仿真侧 socket 接收器 |
| 修改 | `src/piper_socket_bridge/__init__.py` | 导出 `run_robot_sender` |
| 修改 | `src/piper_socket_bridge/sim_adapter/__init__.py` | 导出 `run_pybullet_receiver` |
| 新建 | `tests/real_to_sim_sender.py` | 真实机械臂发送端入口 |
| 新建 | `tests/real_to_sim_receiver.py` | PyBullet 仿真接收端入口 |
| 新建 | `docs/src/plan/real-to-sim-sync-and-bridge-refactor.md` | 方案文档 |

## 改了什么

### 1. `robot_sender.py` — 真实机械臂状态流发送器

从 `scripts/show_status.py` 提取 200Hz 定频读取模式，封装为可复用的 sender 函数。

- `read_robot_frame()`：从 `PiperInterface` 读取 6 轴关节位置 + 夹爪状态，打包为 `PoseStreamFrame`
- `connect_receiver()`：TCP client 连接，自动重试直到接收端就绪
- `run_robot_sender()`：完整流程——CAN 连接 → 机械臂初始化 → TCP 连接 → 200Hz 循环发送
- 定频策略与 `show_status.py` 一致：`perf_counter` + `frame_count * dt` 精确补偿
- 端口使用 `15002`，与现有 sim→robot 方向的 `15001` 区分

### 2. `pybullet_receiver.py` — 仿真侧 socket 接收器

全新模块，在 PyBullet 中可视化真实机械臂状态。

**首帧对齐：**
- 收到第一帧时使用 `p.resetJointState()` 将每个关节瞬移到真实位姿
- 避免仿真从零位缓慢运动到真实位姿的视觉跳变

**后续帧跟随：**
- 使用 `p.setJointMotorControl2(POSITION_CONTROL)` 驱动关节
- `MAX_VELOCITY = 5.0`（比滑条 sender 的 0.3 大得多），确保跟随速度足够快
- 仿真自身以 200Hz 执行 `stepSimulation()`，物理引擎平滑过渡

**取最新帧策略（解决延迟累积）：**
- `_extract_latest_frame()` 解析 buffer 中所有完整行，只返回最后一帧
- 中间帧被丢弃，避免网络抖动导致仿真越来越落后于真实状态
- 使用 `select()` 非阻塞读取，不会因等待数据而卡住仿真循环

**断线容忍：**
- 如果 sender 断开，仿真保持最后一帧状态不动，终端打印提示
- `ConnectionResetError` / `OSError` 均被捕获

**夹爪映射：**
- 复用 `slider_arm_gripper.py` 中的 `GRIPPER_PROTOCOL_TO_SIM_SCALE` 常量
- 协议值 `[0.0, 0.1]` → 仿真值 `[0.0, 0.175]`
- joint7 正向、joint8 反向镜像，与现有 sender 逻辑一致

**关节映射：**
- `_build_joint_maps()` 遍历 URDF 关节，按顺序收集 revolute/prismatic 类型的臂关节索引
- 跳过 joint7/joint8（夹爪），单独处理
- 复用 `slider_arm_gripper.py` 的 `CONTROL_TYPES`、`GRIPPER_JOINT_7`、`GRIPPER_JOINT_8` 常量

### 3. 测试入口脚本

两个极简入口，分终端运行：

```bash
# 终端 1：启动仿真，等待真实臂连接
python -m tests.real_to_sim_receiver

# 终端 2：连接真实机械臂，开始流式发送
python -m tests.real_to_sim_sender
```

## 为什么这样改

1. **`show_status.py` 的 200Hz 循环已经验证可用**，提取为模块函数避免重复代码
2. **首帧对齐用 `resetJointState`** 而非 position control，因为 position control 有惯性延迟，启动时会看到仿真从零位慢慢运动到真实位姿
3. **取最新帧而非逐帧回放**，因为 socket 流不保证每帧都在 5ms 内到达，逐帧回放会越来越滞后
4. **端口 15002 与 15001 分开**，避免两个方向的流互相干扰，也允许同时运行
5. **MAX_VELOCITY 设为 5.0**（比 sender 的 0.3 大很多），因为 receiver 需要快速跟上真实臂的运动，而 sender 的滑条控制本身就是慢速操作

## 模块结构变化

```
piper_socket_bridge/
├── __init__.py               # +run_robot_sender
├── protocol.py               # 不变
├── robot_sender.py            # 新增
├── sim_adapter/
│   ├── __init__.py            # +run_pybullet_receiver
│   ├── pybullet_sender.py     # 不变
│   └── pybullet_receiver.py   # 新增
└── receiver/
    └── robot_follow.py        # 不变
```

双向数据流对称：

| 方向 | 发送端 | 接收端 | 端口 |
|------|--------|--------|------|
| sim→robot | `sim_adapter/pybullet_sender.py` (client) | `receiver/robot_follow.py` (server) | 15001 |
| robot→sim | `robot_sender.py` (client) | `sim_adapter/pybullet_receiver.py` (server) | 15002 |

## 风险与兼容性

- **对现有代码零影响**：所有现有文件（`protocol.py`、`pybullet_sender.py`、`robot_follow.py`）未被修改，sim→robot 方向完全不受影响
- **CAN 读取频率**：`get_joint_positions()` 的实际刷新率取决于 CAN 总线，200Hz 是循环频率但不保证每帧都有新数据，可能出现连续帧值相同的情况——这是可接受的
- **快速运动中启动同步**：`resetJointState` 对齐的是连接时刻的位姿，如果真实臂正在快速运动，对齐后的前几帧 position control 可能有短暂滞后，物理引擎会在几帧内追上
- **仿真侧无安全限制**：`pybullet_receiver.py` 仅做可视化，不操控真实硬件，不需要键盘急停或碰撞保护
