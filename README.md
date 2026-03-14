# piper_control_demo

这是一个基于 `piper-control` 的 Piper 机械臂实验仓库，用来整理真实硬件上的连接、初始化、基础控制、状态观察，以及重力补偿/轨迹录制相关探索。

更完整的项目入口说明见 [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md)。根目录 `README.md` 适合作为仓库首页总览；当 [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md) 更新项目结构、脚本用途、执行方式或安全边界时，这里的内容也应同步调整。

```bash
# docs/ 使用mdbook构建，可在线查看
cargo install mdbook
mdbook serve docs
```

## 文件结构

```text
piper_control_demo/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── uv.lock
├── docs/
│   ├── book.toml
│   └── src/
│       ├── README.md
│       ├── SUMMARY.md
│       └── reference/
├── scripts/
│   ├── README.md
│   ├── piper-generate-udev-rule
│   └── record_trajectories.py
├── src/
│   └── piper_control_demo/
│       ├── config.py
│       ├── core/path.py
│       └── models/piper_grav_comp.xml
└── tests/
    ├── show_status.py
    ├── move_debug.py
    └── disable_safe.py
```

## 基本文件说明

- [`AGENTS.md`](/home/xinger/MyWork/piper_control_demo/AGENTS.md)
  约定 AI 在这个仓库中的文档入口与维护规则。
- [`README.md`](/home/xinger/MyWork/piper_control_demo/README.md)
  仓库首页说明，提供快速总览、目录结构和常用命令。
- [`pyproject.toml`](/home/xinger/MyWork/piper_control_demo/pyproject.toml)
  Python 项目元数据与依赖声明，当前依赖 `piper-control[gravity]` 和 `pinocchio`。
- [`uv.lock`](/home/xinger/MyWork/piper_control_demo/uv.lock)
  `uv` 生成的锁文件，用于固定依赖版本。
- [`docs/book.toml`](/home/xinger/MyWork/piper_control_demo/docs/book.toml)
  `mdBook` 配置文件。
- [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md)
  项目的主入口文档，后续理解项目时应优先阅读。
- [`docs/src/SUMMARY.md`](/home/xinger/MyWork/piper_control_demo/docs/src/SUMMARY.md)
  `mdBook` 导航目录。
- [`scripts/README.md`](/home/xinger/MyWork/piper_control_demo/scripts/README.md)
  `scripts/` 目录下工具与实验脚本的补充说明。
- [`scripts/piper-generate-udev-rule`](/home/xinger/MyWork/piper_control_demo/scripts/piper-generate-udev-rule)
  生成 CAN 设备持久化识别与自动配置规则的脚本。
- [`scripts/record_trajectories.py`](/home/xinger/MyWork/piper_control_demo/scripts/record_trajectories.py)
  交互式轨迹录制、保存、加载与回放脚本，可选结合重力补偿。
- [`src/piper_control_demo/config.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/config.py)
  负责 CAN 端口发现、激活，以及机械臂使能状态探测。
- [`src/piper_control_demo/core/path.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/core/path.py)
  负责定位项目根目录，便于脚本访问资源文件。
- [`src/piper_control_demo/models/piper_grav_comp.xml`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/models/piper_grav_comp.xml)
  重力补偿实验使用的模型文件。
- [`tests/show_status.py`](/home/xinger/MyWork/piper_control_demo/tests/show_status.py)
  连接机械臂后打印状态与关节信息。
- [`tests/move_debug.py`](/home/xinger/MyWork/piper_control_demo/tests/move_debug.py)
  用于基础运动调试，包含初始化、移动和可选安全失能流程。
- [`tests/disable_safe.py`](/home/xinger/MyWork/piper_control_demo/tests/disable_safe.py)
  用于在确认安全姿态后手动失能机械臂。

## 执行说明

### 安装依赖

```bash
uv sync
```

### 常用命令

```bash
# 查看机械臂状态
uv run python tests/show_status.py

# 基础运动调试
uv run python tests/move_debug.py

# 手动失能机械臂
uv run python tests/disable_safe.py

# 轨迹录制 / 回放实验
uv run python scripts/record_trajectories.py --robots can0

# 本地预览 mdBook 文档
mdbook serve docs
```

## 重要说明

- 这个仓库连接真实机械臂，`tests/` 下的文件不是普通单元测试脚本。
- 任何会让机械臂上电、使能、复位、驱动夹爪或发生实际运动的操作，都属于高风险动作。
- AI 可以协助读代码、写代码、改文档、整理命令和分析流程，但不能代替人工去执行激活机械臂并进行运动控制的尝试。
- 涉及风险边界、项目结构和脚本用途的更完整说明，以 [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md) 为准。
