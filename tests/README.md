# tests/

测试与验证脚本，按功能分目录存放。所有脚本均通过 `python -m tests.<子目录>.<文件名>` 运行（需在项目根目录下）。

## 目录结构

```
tests/
├── hardware/          # 真实机械臂硬件测试
├── socket/            # socket 流式控制测试（仿真 ↔ 真实臂）
├── gamepad/           # 手柄遥操控制测试
└── socket_old/        # 旧版 socket 测试（已废弃，仅供参考）
```

## hardware/ — 硬件连接与初始化

| 文件 | 说明 |
|------|------|
| `connect_init.py` | CAN 连接 → 使能臂和夹爪 → 回零位 → 等待用户按 Enter → 安全失能。用于验证基本硬件连通性，也作为其他测试（如手柄遥操）的前置脚本。 |

```bash
python -m tests.hardware.connect_init
```

## socket/ — Socket 流式控制

### sim→robot 方向（仿真滑条控制真实臂）

需要两个终端配合，真实臂侧先启动：

| 文件 | 角色 | 端口 | 说明 |
|------|------|------|------|
| `socket_joint_realtime_follow.py` | 接收端（真实臂） | 15001 | 监听 socket，将收到的关节帧下发给真实机械臂。启动后等待发送端连接。按 `q` 停止。 |
| `pybullet_socket_stream_sender.py` | 发送端（仿真） | 15001 | 启动 PyBullet 滑条 UI，将仿真状态以 200Hz 发送到接收端。 |

```bash
# 终端 1：真实臂接收端
python -m tests.socket.socket_joint_realtime_follow

# 终端 2：仿真发送端
python -m tests.socket.pybullet_socket_stream_sender
```

### robot→sim 方向（真实臂镜像到仿真）

需要两个终端配合，仿真侧先启动：

| 文件 | 角色 | 端口 | 说明 |
|------|------|------|------|
| `real_to_sim_receiver.py` | 接收端（仿真） | 15002 | 启动 PyBullet 可视化，监听 socket。收到第一帧后瞬移到真实臂位姿，之后持续跟随。 |
| `real_to_sim_sender.py` | 发送端（真实臂） | 15002 | 连接真实机械臂，以 200Hz 读取关节/夹爪状态并通过 socket 发送。 |

```bash
# 终端 1：仿真接收端
python -m tests.socket.real_to_sim_receiver

# 终端 2：真实臂发送端
python -m tests.socket.real_to_sim_sender
```

## gamepad/ — 手柄遥操

| 文件 | 说明 |
|------|------|
| `gamepad_joint_control.py` | 通过 pygame 手柄遥操控制机械臂关节。**前置条件**：需要先在另一个终端运行 `tests.hardware.connect_init` 使机械臂进入使能+零位状态。支持摇杆控制 6 轴、扳机控制夹爪、LB/RB 切换速度档位。 |

```bash
# 终端 1：先启动硬件初始化
python -m tests.hardware.connect_init

# 终端 2：手柄遥操
python -m tests.gamepad.gamepad_joint_control
```

## socket_old/ — 旧版测试（已废弃）

旧版 socket 流测试脚本，使用过时的控制流和协议。**不作为新代码的参考实现**，仅保留供历史对照。

| 文件 | 说明 |
|------|------|
| `socket_joint_stream_test.py` | 早期 socket 关节流跟随测试（单线程 sender + receiver） |
| `pybullet_socket_stream_sender.py` | 早期 PyBullet 滑条 sender（无夹爪支持） |
| `socket_joint_realtime_follow.py` | 早期实时跟随（无夹爪、无共享安全流程） |
