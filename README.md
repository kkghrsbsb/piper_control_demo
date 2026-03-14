# piper_control_demo

这是一个基于 `piper-control` 的 Piper 机械臂实验仓库，用来整理真实硬件上的连接、初始化、基础控制、状态观察，以及重力补偿/轨迹录制相关探索。

更完整的项目入口说明见 [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md)。根目录 `README.md` 适合作为仓库首页总览；当 [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md) 更新项目结构、脚本用途、执行方式或安全边界时，这里的内容也应同步调整。

```bash
# docs/ 使用mdbook构建，可在线查看
cargo install mdbook
mdbook serve docs
```

## 文件结构

下面只展示当前仓库的基本架构，不追求完整列出所有文件。

```text
piper_control_demo/
├── AGENTS.md                    # AI 在仓库内的工作约定
├── README.md                    # 仓库首页总览
├── assets/                      # 资源目录，如机器人描述文件
├── pyproject.toml               # Python 项目配置与依赖声明
├── uv.lock                      # uv 锁文件
├── docs/
│   ├── book.toml                # mdBook 配置
│   └── src/
│       ├── README.md            # 更完整的项目入口文档
│       ├── SUMMARY.md           # mdBook 导航目录
│       └── reference/           # 参考资料
├── scripts/
│   ├── README.md                # scripts 目录补充说明
│   ├── disable_safe.py          # 安全失能机械臂
│   ├── move_debug.py            # 基础运动调试
│   ├── piper-generate-udev-rule # 生成 CAN udev 规则
│   ├── record_trajectories.py   # 轨迹录制/回放实验
│   └── show_status.py           # 查看机械臂状态
├── src/
│   └── piper_control_demo/
│       ├── config.py            # CAN 连接与状态探测辅助
│       ├── core/path.py         # 项目根目录与 URDF 等资源路径索引
│       └── models/piper_grav_comp.xml  # 重力补偿模型
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
- 涉及风险边界、项目结构和脚本用途的更完整说明，以 [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md) 为准。
