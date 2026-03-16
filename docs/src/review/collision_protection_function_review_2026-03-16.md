# 碰撞保护功能设置与用途审查记录

## 结论先行

### 主要结论 1

当前底层库里“碰撞保护”确实是一个真实存在的机械臂参数配置能力，不是仓库脚本自己假设出来的功能。

依据见：

- [`piper_interface.py`](/home/xinger/MyWork/piper_control_demo/.venv/lib/python3.10/site-packages/piper_control/piper_interface.py#L894)
- [`piper_interface.py`](/home/xinger/MyWork/piper_control_demo/.venv/lib/python3.10/site-packages/piper_control/piper_interface.py#L926)

`PiperInterface` 明确提供了：

- `set_collision_protection(levels)`
- `get_collision_protection()`

而且约束写得很清楚：

- 必须是 6 个关节各自一个等级
- 每个等级范围是 `0` 到 `8`
- `0` 表示关闭碰撞检测
- `1` 到 `8` 表示递增的检测阈值

### 主要结论 2

当前底层库并没有在 Python 层进一步解释“1 到 8 分别对应多大的力阈值、扭矩阈值或灵敏度曲线”。  
也就是说，我们目前能确认的是“等级越高，阈值递增”，但不能只根据这层 Python 封装就精确解释成“越高越敏感”还是“越高越迟钝”。

这一点非常重要，因为 `piper-control` 的文档字符串只写了：

- `0: No collision detection`
- `1-8: Increasing detection thresholds`

这里的 `thresholds` 更像“阈值递增”，但没有直接写出工程语义。

### 主要结论 3

底层状态枚举里确实存在 `ArmStatus.COLLISION = 0x07`，说明硬件/SDK 体系里明确有“碰撞”这一状态概念。

依据见：

- [`piper_interface.py`](/home/xinger/MyWork/piper_control_demo/.venv/lib/python3.10/site-packages/piper_control/piper_interface.py#L256)

这说明“碰撞保护等级”不是孤立配置项，它和机械臂状态机是有关联的。

## 已核对的底层实现

### 1. 设置接口做了什么

`PiperInterface.set_collision_protection(levels)` 做了三件事：

1. 校验输入长度必须为 6
2. 校验每个关节等级必须在 `0..8`
3. 调用底层 SDK 的 `CrashProtectionConfig(...)`

也就是说，当前项目脚本里调用：

```python
robot.set_collision_protection([5, 5, 5, 5, 5, 5])
```

确实是在向底层发送真实配置命令，而不是只改 Python 本地变量。

### 2. 查询接口做了什么

`PiperInterface.get_collision_protection()` 并不是读取 Python 侧缓存，而是：

1. 先调用 `ArmParamEnquiryAndConfig(0x02, 0x00, 0x00, 0x00, 0x03)`
2. 再读取 `GetCrashProtectionLevelFeedback()`
3. 从反馈对象里取出 6 个关节的等级

这意味着：

- 读取值来自设备反馈链路
- 它天然可能存在刷新延迟
- “刚写入后立刻读到旧值”是合理现象，不能直接据此判定设置失败

这也和你之前实测到的结果一致：第一帧是全 `0`，后续采样才稳定成 `[5, 5, 5, 5, 5, 5]`。

### 3. 当前仓库脚本是怎么用的

[`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py#L31) 当前把碰撞保护作为显式前置步骤：

- 目标等级固定为 `COLLISION_PROTECTION_LEVELS = [5, 5, 5, 5, 5, 5]`
- 在 `ensure_arm_and_gripper_enabled(robot)` 之后执行
- 不再“写完立刻只读一次”
- 改成“等待 + 多次采样 + 是否至少一次匹配”

这比之前的实现更接近底层接口的真实行为。

## 这个功能的用途应该怎么理解

### 用途 1：给 6 个关节分别配置碰撞相关阈值

从接口设计看，这个功能不是一个总开关，而是每个关节单独可设等级：

```python
[j1_level, j2_level, j3_level, j4_level, j5_level, j6_level]
```

这意味着它适合做：

- 整机统一等级配置
- 或者针对特定关节做差异化保护

例如理论上可以让更容易接触环境的关节设置得更保守。

### 用途 2：作为真实机械臂动作前的运行保护参数

从工程位置上看，这个配置更像：

- 运动前要下发的运行参数
- 而不是轨迹规划算法的一部分

所以现在把它放在 `move_debug.py` 的初始化链路里是合理的。

### 用途 3：与机械臂状态联动，用于碰撞事件响应

因为底层已经定义了 `ArmStatus.COLLISION`，后续如果你要做更完整的安全逻辑，可以考虑把碰撞保护和状态监测配套使用，例如：

- 启动前写入等级
- 运动过程中持续看 `robot.arm_status`
- 一旦变成 `COLLISION`，立即进入脚本层停止/人工处理流程

当前仓库还没有把这层状态联动真正写进公共控制模块，这一点仍然是后续可增强项。

## 当前最需要避免的误解

### 误解 1

不要把 `piper_control/collision_checking.py` 当成真实机械臂碰撞保护实现。

[`collision_checking.py`](/home/xinger/MyWork/piper_control_demo/.venv/lib/python3.10/site-packages/piper_control/collision_checking.py#L1) 是 MuJoCo 仿真接触检测工具，做的是：

- 读取仿真接触
- 统计接触体对
- 判断是否有碰撞

它服务的是仿真模型几何碰撞检查，不是 CAN 链路上的机械臂碰撞保护参数配置。

也就是说，这里实际上有两套“collision”概念：

- 真实机械臂侧：`set_collision_protection()` / `get_collision_protection()`
- 仿真侧：`collision_checking.py`

后续文档和代码注释里最好持续把这两者区分开。

### 误解 2

不要把“等级数字更大”直接草率解释成“更安全”。

从当前 Python 封装能确认的是“阈值递增”，但还缺少厂商级解释来说明：

- 阈值更高是否意味着更不容易触发碰撞停机
- 还是表示保护能力更强

在没有更底层文档或官方说明前，项目文档更稳妥的说法应该是：

- `0` 为关闭碰撞检测
- `1..8` 为递增的碰撞保护阈值等级
- 具体等级对灵敏度/触发条件的影响，需以设备官方资料或实机验证为准

## 对当前实现的审查意见

### 发现 1

当前 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py#L38) 里的 `verify_collision_protection(...)` 仍然只是“验证写入是否最终能回读匹配”，还没有把“匹配失败”升级成明确的流程控制。

这意味着当前即使多次采样都不匹配，脚本还是会继续往下执行。

影响：

- 对调试阶段还可以接受
- 对后续更正式的真实动作脚本，安全边界偏弱

建议：

- 后续可把它改成返回结构化结果
- 并允许调用方在不匹配时直接中止后续运动

### 发现 2

当前项目已经证明“反馈存在延迟”，但等待参数仍然写在 `move_debug.py` 本地常量里：

- `COLLISION_PROTECTION_SETTLE_SECONDS`
- `COLLISION_PROTECTION_SAMPLE_COUNT`
- `COLLISION_PROTECTION_SAMPLE_INTERVAL`

如果后续更多真实机械臂脚本都要配置碰撞保护，这套逻辑更适合继续上收成公共模块能力。

建议：

- 可以后续考虑抽到 `src/piper_control_demo/control.py`
- 做成类似 `configure_and_verify_collision_protection(...)`

### 发现 3

当前仓库文档里已经写了“将 6 个关节的碰撞保护等级固定设为 5”，但还没有明确提醒读者：

- 这个 `5` 是当前项目的经验默认值
- 不是从底层库文档中推导出的“官方推荐值”

建议：

- 后续在项目入口文档里把这点写得更明确
- 避免别人误以为 `5` 是底层 SDK 的标准默认配置

## 修改建议

### 建议 1

后续文档里讲碰撞保护时，统一使用下面这类说法：

“Piper 底层支持为 6 个关节分别设置 `0..8` 的碰撞保护等级；`0` 表示关闭碰撞检测，`1..8` 为递增阈值等级。当前仓库默认将其作为真实机械臂运动前的运行保护参数配置。”

### 建议 2

后续如果有新的真实机械臂运动脚本，也应默认评估是否要在使能完成后统一下发碰撞保护配置，而不是只在 `move_debug.py` 里做。

### 建议 3

后续如果要继续增强安全性，优先方向不是继续美化打印，而是把两件事接起来：

1. 写入并验证碰撞保护等级
2. 运行中监控 `robot.arm_status == ArmStatus.COLLISION`

这样才更接近“配置 + 运行期响应”的完整链路。

## 一句话总结

当前底层库里的碰撞保护，实质上是“面向真实机械臂的 6 关节碰撞阈值配置能力”，用途是作为动作前的运行保护参数；它和仿真里的几何碰撞检测不是一回事，而当前仓库脚本已经基本证明这项配置能成功下发，只是设备反馈存在延迟。
