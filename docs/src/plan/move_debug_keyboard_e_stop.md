# move_debug 键盘急停方案

## 目标

在 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 中，为：

```python
with piper_control.BuiltinJointPositionController(...)
```

这一段控制流程增加一个“急停”按键。

目标行为是：

- 机械臂在运动过程中
- 操作者按下键盘 `q`
- 能尽快停止继续运动
- 退出 `BuiltinJointPositionController` 上下文
- 让后续异常处理或人工处置能够及时接管

这次只先做方案，不改代码。

## 当前代码现状

[`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 当前的关键控制段是：

1. 进入 `BuiltinJointPositionController`
2. 设置 `robot.set_arm_mode(speed=JOINT_SAFE_SPEED)`
3. 调用：

```python
controller.move_to_position(reach_position, threshold=0.01, timeout=12.0)
```

4. 再调用：

```python
robot.command_gripper(gripper_position, GRIPPER_EFFORT_NOW)
```

问题在于：

- `move_to_position(...)` 是阻塞调用
- 进入这段调用后，当前脚本没有机会实时读键盘输入
- 也就是说，现在不能在“运动进行中”及时按键中断

## 功能方案判断

这个需求是合理的，而且在真实机械臂控制里非常有必要。

但要注意一点：

- 如果继续直接使用阻塞式 `controller.move_to_position(...)`
- 就很难在运动过程里响应 `q`

因此，这次真正要实现急停，核心不是单纯加一个按键监听，而是要把“阻塞式 move_to_position”改成“可轮询按键的分步控制循环”。

## 推荐设计思路

我建议这次把原本：

```python
controller.move_to_position(reach_position, ...)
```

替换成脚本内自己的“小步逼近控制循环”。

这样每一小步都可以：

1. 读一次键盘输入
2. 判断是否按了 `q`
3. 如果没有，就继续往目标位推进
4. 如果按了，就立刻结束循环并退出上下文

## 为什么不能直接靠 BuiltinJointPositionController 自动急停

`BuiltinJointPositionController` 本身并没有暴露一个现成的“异步停止正在进行的 move_to_position”接口。

当前已知行为是：

- `move_to_position(...)` 内部自己循环发命令直到到位或超时
- 脚本在调用期间拿不到控制权

所以，如果你要真正做到“运动中按 q 立刻响应”，就必须把这层循环拿到 `move_debug.py` 自己手里。

## 推荐实现结构

### 1. 增加非阻塞按键读取

可以复用仓库里已经存在的思路，例如参考：

- `scripts/record_trajectories.py` 中的 `RawTerminal`

建议在 `move_debug.py` 中加入一个轻量版本：

- 进入 raw/cbreak 模式
- 非阻塞读取单键
- 按到 `q` 时返回停止信号

## 2. 将关节运动改成脚本内分步控制

建议不再直接调用一次性阻塞的：

```python
controller.move_to_position(...)
```

而是改成：

1. 读当前关节角
2. 计算到目标位的误差
3. 每个控制周期发一次：

```python
controller.command_joints(next_q)
```

4. 每次循环前先检查键盘有没有按下 `q`

只要按下 `q`，就立即：

- 停止继续发送新的目标位
- 退出循环
- 离开 `with BuiltinJointPositionController(...)` 上下文

## 3. 夹爪命令的时机

当前 `move_debug.py` 里夹爪命令是在关节运动完成后才发：

```python
robot.command_gripper(gripper_position, GRIPPER_EFFORT_NOW)
```

这对急停是有好处的，因为：

- 如果关节运动途中按下 `q`
- 可以直接跳过后续夹爪动作

也就是说，这次急停逻辑建议默认覆盖：

- 关节运动急停
- 并阻止后续夹爪动作继续执行

## 建议的控制循环行为

关节运动段建议变成：

1. 获取 `current_q`
2. 获取 `reach_position`
3. 设定控制周期，例如 `100Hz` 或 `200Hz`
4. 每次循环：
   - 检查键盘是否按了 `q`
   - 如果按了：标记 `emergency_stop_triggered = True`，打印提示并跳出
   - 如果没按：计算下一步命令并 `controller.command_joints(...)`
   - 检查是否已经到达阈值
   - 若到达则正常结束
   - 若超时则按超时结束

这样可以同时支持：

- 正常到位
- 超时退出
- 人工 `q` 急停

## 急停触发后应该发生什么

我建议急停触发后的行为明确为：

1. 打印：
   - 已触发急停
   - 已停止继续下发目标位
2. 不再执行后续夹爪位置命令
3. 退出 `with BuiltinJointPositionController(...)`
4. 进入后续人工确认逻辑，而不是自动继续执行其它动作

也就是说，急停不应继续“自动补后续动作”。

## 是否要自动失能

这次不建议把按下 `q` 直接等同于“自动失能机械臂”。

理由：

- 机械臂正在什么姿态下被中断并不确定
- 直接掉使能可能造成下坠或姿态更危险

更合理的策略是：

- `q` 只负责停止进一步运动并退出上下文
- 然后回到人工决策阶段
- 由操作者判断是否继续执行安全位、失能或其它处置

## 和现有 disable_confirm 的关系

当前脚本已有：

```python
disable_confirm = input("Move complete. Disable arm at safe position now? [y/N]: ")
```

急停后建议：

- 可以沿用这套人工确认逻辑
- 但提示语最好区分“正常完成”和“急停中断”

例如后续实现时可变成：

- 正常结束：`Move complete...`
- 急停结束：`Motion interrupted by emergency stop...`

这样操作者更清楚当前状态。

## 推荐实现步骤

如果后续开始改代码，建议按这个顺序做：

1. 在 `move_debug.py` 中加入非阻塞键盘读取工具
2. 把阻塞式 `move_to_position(...)` 改成脚本内分步控制循环
3. 在控制循环里加入 `q` 检测
4. 约定按下 `q` 时设置 `emergency_stop_triggered`
5. 急停触发后跳过夹爪动作
6. 急停触发后退出 `BuiltinJointPositionController` 上下文
7. 最后进入人工确认阶段，而不是自动失能

## 风险与边界

虽然目标是“急停”，但这里的“急停”本质上仍是脚本层面的快速停止，不是硬件级安全回路。

因此必须明确：

- 它只能做到“尽快停止继续下发运动命令”
- 不等于硬件急停
- 不应替代真正的现场安全措施
- 如果机械臂已经因惯性、控制延迟或底层驱动继续短暂运动，这是预期内风险

换句话说，这次方案是“软件层人工中断”，不是认证级安全急停。

## 预期输出

确认后，下一步实施应包含：

1. 在 `scripts/move_debug.py` 中加入非阻塞键盘读取
2. 把关节运动从阻塞式 `move_to_position(...)` 改成可轮询按键的分步控制循环
3. 支持在运动中按 `q` 停止继续运动
4. 按下 `q` 后退出 `BuiltinJointPositionController` 上下文
5. 急停触发后跳过后续夹爪动作，并回到人工确认阶段
