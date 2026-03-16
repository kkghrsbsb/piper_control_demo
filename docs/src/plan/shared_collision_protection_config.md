# 共享碰撞保护配置方案

## 功能目标

把当前只存在于 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 中的碰撞保护设置与验证逻辑，抽取到 [`src/piper_control_demo/config.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/config.py) 作为公共能力，后续真实机械臂脚本直接复用。

## 当前问题

目前碰撞保护相关逻辑存在几个问题：

- 设置和验证逻辑只写在 `move_debug.py`，复用性差
- 等待时间、采样次数、采样间隔这些参数也散落在脚本里
- 后续如果别的真实机械臂脚本也要配置碰撞保护，容易重复实现
- `move_debug.py` 既负责动作流程，又负责设备参数配置，职责偏杂

## 拟议设计

在 [`src/piper_control_demo/config.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/config.py) 中新增公共碰撞保护辅助能力，建议至少包含：

- 碰撞保护默认参数常量
- `verify_collision_protection(...)`
- `configure_collision_protection(...)`

其中：

- `verify_collision_protection(...)`
  负责在给定目标等级后，等待并多次读取反馈，返回是否至少有一次匹配
- `configure_collision_protection(...)`
  负责统一执行“写入 + 验证 + 打印结果”，供脚本直接调用

## 影响文件

- [`src/piper_control_demo/config.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/config.py)
- [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py)
- [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md)

## 兼容性与风险

- 这次改动不改变碰撞保护的底层设置方式，仍然通过 `robot.set_collision_protection(...)` 和 `robot.get_collision_protection()` 完成
- 主要变化是职责位置调整和复用方式优化
- 需要注意不要误把“公共化”做成“所有脚本都自动强制启用”，先只让 `move_debug.py` 显式调用即可

## 实施步骤

1. 在 `config.py` 中提取碰撞保护默认常量与验证函数
2. 在 `config.py` 中补一个面向脚本调用的公共配置函数
3. 删除 `move_debug.py` 中本地的碰撞保护验证实现，改为调用公共函数
4. 更新 `docs/src/README.md`，说明碰撞保护已抽成公共配置能力

## 预期结果

- `move_debug.py` 更聚焦在动作流程本身
- 碰撞保护设置与验证逻辑统一收敛到 `config.py`
- 后续其他真实机械臂脚本更容易复用同一套碰撞保护配置流程
