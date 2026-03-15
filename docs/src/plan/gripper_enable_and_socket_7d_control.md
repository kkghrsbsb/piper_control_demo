# move_debug 夹爪使能与 7 维目标位方案

## 目标

这次只改一个程序：

- [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py)

并配套在：

- [`src/piper_control_demo/config.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/config.py)

中新增一个夹爪使能探测函数，供 `move_debug.py` 调用。

本轮不做 socket 接收端设计，不做 7 维网络流拆分，不做其它测试脚本改造。

## 这次要实现的具体行为

需求收敛后，这次要做的是：

1. 在 `config.py` 中新增一个类似 `probe_arm_enabled_state()` 的夹爪使能探测函数。
2. 在 `move_debug.py` 中，`reset_gripper(robot)` 后调用这个新函数，确认夹爪已使能。
3. 在 `move_debug.py` 中预先写一个可手改的 7 维目标位。
4. 将这个 7 维目标位拆成：
   - 前 6 维：`reach_position`
   - 第 7 维：`gripper_position`
5. 前 6 维继续交给 `BuiltinJointPositionController`
6. 第 7 维通过 `robot.command_gripper(...)` 控制夹爪
7. 在 `disable_confirm` 进入失能流程时，同时处理夹爪失能

## 当前代码基础

### 1. 机械臂使能探测已经存在

[`src/piper_control_demo/config.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/config.py) 当前已经有：

- `connect_can()`
- `probe_arm_enabled_state()`

它的模式是：

- 等待状态稳定
- 多次采样
- 避免瞬时误判

这非常适合直接复制思路，用于夹爪使能探测。

### 2. move_debug.py 当前结构

[`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 目前已经有这些关键步骤：

1. 连接 CAN
2. 提醒操作者确认即将运动
3. 初始化 `PiperInterface`
4. 设置安装方向
5. 设置碰撞保护
6. 必要时 `reset_arm`
7. `reset_gripper`
8. 使用 `BuiltinJointPositionController`
9. 控制 6 个关节到目标位
10. 根据人工确认决定是否失能

这说明现在只差：

- 夹爪 reset 后的使能确认
- 在目标位控制里把夹爪位置也纳入
- 在失能阶段把夹爪一起处理

## 已确认的夹爪接口

当前依赖里的 `PiperInterface` 已确认有这些能力：

- `is_gripper_enabled()`
- `enable_gripper()`
- `disable_gripper()`
- `get_gripper_state()`
- `command_gripper(position=..., effort=...)`

以及：

- `robot.gripper_angle_max`
- `robot.gripper_effort_max`

因此这次方案是可实施的。

## 设计建议 1：新增夹爪使能探测函数

建议在 [`src/piper_control_demo/config.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/config.py) 中新增：

- `probe_gripper_enabled_state()`

行为建议与 `probe_arm_enabled_state()` 尽量保持一致：

1. 初始等待短时间
2. 多次采样 `robot.is_gripper_enabled()`
3. 只要任一采样为真，就视为已使能
4. 打印采样结果
5. 返回布尔值

建议参数也保持同风格：

- `settle_seconds`
- `sample_count`
- `sample_interval`

## 设计建议 2：move_debug.py 中 reset_gripper 后如何接入

建议顺序是：

1. `piper_init.reset_gripper(robot)`
2. `probe_gripper_enabled_state(robot)`
3. 如果探测结果是未使能，则补一次 `robot.enable_gripper()`
4. 可选地再探测一次并打印最终结果

这样做的原因是：

- `reset_gripper()` 虽然逻辑上已经会重新 enable
- 但状态回读可能存在短暂延迟
- 加一次探测/补救后，后续夹爪控制会更稳

## 设计建议 3：7 维目标位在 move_debug.py 中如何表达

这次不是网络流，而是本地手工写一个“预置 7 维目标位”。

建议改成类似下面的结构：

```python
target_pose = [j1, j2, j3, j4, j5, j6, gripper_pos]
```

然后在代码里拆成：

```python
reach_position = target_pose[:6]
gripper_position = target_pose[6]
```

这样你后续手改目标位时会更直观，也更不容易忘记夹爪。

## 设计建议 4：关节与夹爪分别怎么下发

因为 `BuiltinJointPositionController` 只处理 6 个关节，所以这次方案必须拆开控制：

### 1. 6 个关节

继续沿用当前方式：

```python
success = controller.move_to_position(reach_position, ...)
```

### 2. 夹爪

在合适时机单独调用：

```python
robot.command_gripper(gripper_position, some_effort)
```

也就是说：

- 关节位置控制仍由 `BuiltinJointPositionController` 负责
- 夹爪位置控制由 `robot.command_gripper(...)` 单独负责

## 设计建议 5：夹爪命令下发时机

这一步有两种可选方式：

### 方式 A：先关节后夹爪

流程：

1. 先让 6 个关节到 `reach_position`
2. 再执行一次 `command_gripper(gripper_position, ...)`

优点：

- 改动最小
- 行为最容易理解
- 更适合作为首版

### 方式 B：关节和夹爪近似同时开始

流程：

1. 刚进入控制段时就先发夹爪命令
2. 然后开始 `move_to_position(reach_position, ...)`

优点：

- 更接近“同时到位”

缺点：

- 时序不如方式 A 清楚
- 调试时不容易判断问题来自关节还是夹爪

我更推荐方式 A，先把行为做稳。

## 设计建议 6：夹爪 effort 怎么取

这次首版建议不要把 effort 做成另一个可调目标。

建议先固定为：

- `robot.gripper_effort_max`

或者一个你已经确认更保守的常量。

也就是先只让你手改：

- `gripper_position`

不要同时让你再手改：

- `gripper_effort`

这样更简单，也更安全。

## 设计建议 7：是否要读当前 gripper_pos

这次实现不一定必须读当前夹爪位置，但我建议至少保留一个打印点，方便调试：

```python
gripper_pos, gripper_effort = robot.get_gripper_state()
print(...)
```

这样你能知道：

- reset 后夹爪当前大概处在什么位置
- 发命令后夹爪状态是否有变化

## 设计建议 8：失能时如何处理夹爪

你已经明确提出：在 `disable_confirm` 的失能流程里，夹爪也要一起失能。

这点我建议这样做：

1. 先保持现有安全位逻辑，让机械臂回到安全位
2. 在确认安全位到达后
3. 先处理夹爪失能
4. 再处理机械臂失能

推荐顺序是：

- 先 `robot.disable_gripper()`
- 再 `piper_init.disable_arm(robot)`

这样更符合“夹爪和机械臂一起进入非激活状态”的意图。

## 推荐实现顺序

后续真开始改代码时，建议按下面顺序做：

1. 在 `config.py` 中新增 `probe_gripper_enabled_state()`
2. 在 `move_debug.py` 的 `reset_gripper` 后接入夹爪使能确认
3. 把目标位从 6 维改成 7 维预置列表
4. 在 `move_debug.py` 中拆出 `reach_position` 和 `gripper_position`
5. 先实现“6 关节到位后，再执行夹爪命令”
6. 在失能逻辑中加入夹爪失能

## 风险与边界

虽然这次不涉及 socket，但风险依然比当前 6 关节版本更高，因为：

- 夹爪会开始主动动作
- 如果 `gripper_position` 设置不当，可能出现意外闭合
- 如果失能顺序处理不好，末端行为可能不符合预期

所以这次首版仍建议：

- 用明显安全的 `gripper_position`
- 保守设置夹爪 effort
- 保留人工确认
- 不做自动化执行

## 预期输出

确认后，下一步实施应只包含下面这些内容：

1. `config.py` 中新增夹爪使能探测函数
2. `move_debug.py` 中在 `reset_gripper` 后调用夹爪使能确认
3. `move_debug.py` 中把目标位改成可手改的 7 维目标位
4. `move_debug.py` 中把前 6 维传给 `reach_position`，第 7 维传给 `gripper_position` 并调用 `command_gripper`
5. `move_debug.py` 的失能流程中同时处理夹爪失能
