# piper_control_demo

基于 [piper-control](https://github.com/Reimagine-Robotics/piper_control) 的 Piper 机械臂实验仓库。用于沉淀真实硬件连接、基础控制、状态观察、仿真映射等调试能力。

更完整的项目说明见 [`docs/src/README.md`](./docs/src/README.md)。

## 快速开始

```bash
# 安装依赖
uv sync

# 查看文档
cargo install mdbook
mdbook serve docs
```

## 仓库结构

```
src/
├── piper_control_demo/        # 核心库：CAN 连接、使能、碰撞保护、安全流程
├── piper_pybullet_sim/        # PyBullet 仿真辅助（滑条控制、夹爪映射）
└── piper_socket_bridge/       # Socket 流式桥接（sim↔robot 双向）

scripts/                       # 日常操作脚本（详见 scripts/README.md）
tests/                         # 测试脚本，按类别分目录（详见 tests/README.md）
├── hardware/                  #   硬件连接测试
├── socket/                    #   socket 流式控制测试
├── gamepad/                   #   手柄遥操测试
└── socket_old/                #   旧版测试（已废弃）

docs/                          # mdBook 文档
assets/                        # URDF 等资源文件
```

## 常用命令

```bash
# 查看机械臂状态（只读，200Hz JSON 行流）
python -m scripts.show_status

# 基础运动调试（支持键盘急停 + 运动守护）
python -m scripts.move_debug

# 手动失能机械臂
python -m scripts.disable_safe

# 手柄遥操（两个终端）
python -m tests.hardware.connect_init       # 终端 1：初始化
python -m tests.gamepad.gamepad_joint_control  # 终端 2：手柄控制

# sim→robot：仿真滑条控制真实臂（两个终端）
python -m tests.socket.socket_joint_realtime_follow   # 终端 1：真实臂接收
python -m tests.socket.pybullet_socket_stream_sender  # 终端 2：仿真发送

# robot→sim：真实臂镜像到仿真（两个终端）
python -m tests.socket.real_to_sim_receiver  # 终端 1：仿真接收
python -m tests.socket.real_to_sim_sender    # 终端 2：真实臂发送
```

## 安全说明

- 本仓库直接控制真实机械臂，`scripts/` 和 `tests/` 下多数脚本会触发实际运动。
- 执行前确认机械臂周围无人和障碍物；失能前确认处于安全姿态（掉电后可能下坠）。
- AI 可协助读写代码和文档，但不能代替人工执行机械臂运动控制。
