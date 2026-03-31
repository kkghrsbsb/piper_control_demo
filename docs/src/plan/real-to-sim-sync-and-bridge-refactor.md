# 真实机械臂到仿真同步 & piper_socket_bridge 重构方案

## 功能目标

1. **重构 `piper_socket_bridge` 模块**：提取通用的"读取真实机械臂状态并以 200Hz socket 流发送"能力，使模块同时支持 sim→robot 和 robot→sim 两个方向。
2. **新增 real→sim 同步测试脚本**：在 `tests/` 中编写脚本，将真实机械臂状态以 200Hz 流式推送到 PyBullet 仿真环境，实现实时数字孪生。
3. **仿真启动时先对齐初始位姿**：PyBullet 仿真启动后，先接收真实机械臂当前关节状态，将仿真模型瞬移至该位姿，再开始持续同步。

## 当前问题 / 动机

- `piper_socket_bridge` 当前只有 sim→robot 方向的发送/接收实现，缺少 robot→sim 方向。
- `scripts/show_status.py` 已经实现了 200Hz 读取真实机械臂状态的循环，但它只做 stdout 打印，没有抽象为可复用的 sender。
- 仿真侧目前只有滑条驱动（`sim_adapter/pybullet_sender.py`），没有"从 socket 接收并驱动仿真关节"的 receiver。

## 设计方案

### 1. 新增 `robot_sender` —— 真实机械臂状态流发送器

在 `src/piper_socket_bridge/` 下新建 `robot_sender.py`（与 `receiver/` 平级），参考 `show_status.py` 的 200Hz 循环模式：

```
piper_socket_bridge/
├── protocol.py               # 不变
├── robot_sender.py            # 新增：真实机械臂 → socket 流
├── sim_adapter/
│   ├── pybullet_sender.py     # 已有：仿真滑条 → socket 流
│   └── pybullet_receiver.py   # 新增：socket 流 → 仿真关节驱动
└── receiver/
    └── robot_follow.py        # 已有：socket 流 → 真实机械臂
```

**`robot_sender.py` 核心职责：**

- 连接 CAN、初始化 `PiperInterface`
- 启动 TCP server（或 connect 到远端），以 200Hz 发送 `PoseStreamFrame`
- 采用与 `show_status.py` 相同的定频循环：`perf_counter` + `frame_count * dt` 补偿
- 读取 `robot.get_joint_positions()` 和 `robot.get_gripper_state()` 打包为 `PoseStreamFrame`

**关于 sender 角色选择（TCP server vs client）：**

当前 `pybullet_sender.py` 是 TCP client 连接 `robot_follow.py` 的 server。对于 robot→sim 方向，建议 **robot_sender 做 TCP server，仿真侧做 client 连接**，理由：
- 真实机械臂侧通常先启动、持续运行
- 仿真侧可以随时启动/重连
- 与现有 sim→robot 方向保持对称：数据源做 server 不合适——但考虑到现有代码 receiver 做 server 已经是约定，**保持一致更重要**：robot_sender 做 TCP client，pybullet_receiver 做 TCP server，与现有方向的 sender/receiver 角色保持对称

**最终决定：robot_sender 做 TCP client，pybullet_receiver 做 TCP server**，与现有 `pybullet_sender`(client) → `robot_follow`(server) 保持一致的模式。

### 2. 新增 `sim_adapter/pybullet_receiver.py` —— 仿真侧 socket 接收器

**核心职责：**

- 启动 PyBullet GUI 环境（加载 URDF，但不创建滑条）
- 做 TCP server 监听，等待 robot_sender 连接
- 接收第一帧后，**先将仿真关节瞬移到该帧的位姿**（用 `p.resetJointState` 而非 position control），完成初始对齐
- 之后持续接收帧，用 `p.setJointMotorControl2` position control 驱动仿真关节跟随
- 调用 `p.stepSimulation()` 推进物理

**初始位姿对齐细节：**

```python
# 收到第一帧后：
for i, angle in enumerate(first_frame.q):
    p.resetJointState(robot_id, joint_index_map[i], angle)
# 夹爪也做 resetJointState
# 然后再进入正常的 position control 跟随循环
```

这样仿真模型不会从零位缓慢运动到真实位姿，而是瞬间到达。

### 3. socket 流不保证同步的处理

200Hz socket 流在网络层面不保证帧同步，需要处理：

- **接收侧取最新帧**：如果 buffer 中积累了多帧，只使用最后一帧（丢弃中间帧），避免延迟累积
- **断线容忍**：如果 socket 断开，仿真保持最后一帧状态不动，终端打印提示
- **不做时间戳插值**：仿真侧以自身 `stepSimulation` 频率运行，每步取最新收到的帧即可

### 4. 测试脚本

在 `tests/` 下新建 `real_to_sim_sync.py`：

```python
# 用法：
# 终端 1: python -m tests.real_to_sim_sync   （启动仿真，等待连接）
# 终端 2: python -m tests.real_to_sim_sender  （连接真实机械臂，发送状态流）
```

或者考虑合并为单脚本双进程模式。但考虑到真实机械臂和仿真通常在不同终端运行，**拆分为两个脚本更实用**：

- `tests/real_to_sim_sender.py`：启动真实机械臂状态流发送（调用 `robot_sender` 模块）
- `tests/real_to_sim_receiver.py`：启动 PyBullet 仿真接收并跟随（调用 `pybullet_receiver` 模块）

## 涉及文件

| 操作 | 文件 |
|------|------|
| 新建 | `src/piper_socket_bridge/robot_sender.py` |
| 新建 | `src/piper_socket_bridge/sim_adapter/pybullet_receiver.py` |
| 修改 | `src/piper_socket_bridge/__init__.py`（导出新增模块） |
| 修改 | `src/piper_socket_bridge/sim_adapter/__init__.py`（导出新增模块） |
| 新建 | `tests/real_to_sim_sender.py` |
| 新建 | `tests/real_to_sim_receiver.py` |

## 风险与边界情况

1. **socket 延迟累积**：如果真实机械臂 200Hz 发送、仿真侧处理不及时，buffer 会积累。需要在接收侧实现"跳到最新帧"逻辑。
2. **夹爪映射**：真实机械臂 `get_gripper_state()` 返回的值域与 `PoseStreamFrame` 中的 `gripper` 语义需要一致。当前 protocol 中 gripper 范围是 `[0.0, 0.1]`，仿真侧通过 `GRIPPER_PROTOCOL_TO_SIM_SCALE` 映射到 `[0.0, 0.175]`。`pybullet_receiver.py` 需要复用相同的映射常量。
3. **CAN 读取频率**：`piper_interface` 的 `get_joint_positions()` 实际频率取决于 CAN 总线刷新率，200Hz 是目标但不保证每帧都有新数据，这是可接受的。
4. **仿真物理步长与接收频率**：仿真 `setTimeStep(1/200)` 与接收频率匹配即可，每次 `stepSimulation` 前取最新帧。
5. **首帧对齐后的跳变**：`resetJointState` 是瞬移，后续帧用 position control 有惯性，如果真实臂在快速运动中启动同步，可能有短暂跟随滞后——这是可接受的。

## 实现步骤

1. 编写 `robot_sender.py`：提取 `show_status.py` 的 200Hz 读取循环为可复用函数，加入 TCP client 连接和 `PoseStreamFrame` 发送
2. 编写 `sim_adapter/pybullet_receiver.py`：PyBullet 环境初始化 + TCP server + 首帧对齐 + position control 跟随循环
3. 更新 `__init__.py` 导出
4. 编写 `tests/real_to_sim_sender.py` 和 `tests/real_to_sim_receiver.py` 入口脚本
5. 本地测试验证
