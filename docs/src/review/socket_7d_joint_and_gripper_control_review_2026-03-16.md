# 7 维 Socket 关节流与夹爪同步控制审查记录

## 结论先行

### 主要结论 1

当前新版 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 的 7 维目标位控制方式，本质上是：

1. 先用 `BuiltinJointPositionController` 处理前 6 个关节
2. 等 6 关节到位后
3. 再单独调用 `robot.command_gripper(...)` 控制第 7 维夹爪位置

这对“单次目标位调试”是合理的，但它不是未来 7 维 socket 流实时跟随的最终形态。

### 主要结论 2

后续 7 维 socket 流如果想实现“关节和夹爪一同控制”，不能继续沿用 `move_debug.py` 当前这种“关节完成后再发夹爪”的串行语义。

更合适的做法是：

- 每收到一帧 7 维数据
- 立刻拆成：
  - 前 6 维 `joint_q`
  - 第 7 维 `gripper_pos`
- 在同一个控制循环周期里连续下发：
  - `controller.command_joints(joint_q)`
  - `robot.command_gripper(gripper_pos, fixed_effort)`

也就是说，后续“一同控制”的正确理解，不是底层存在一个统一的 7 维控制器，而是同一帧数据在同一周期里走两条命令通道。

### 主要结论 3

当前底层接口决定了这两条通道天然是分开的：

- `BuiltinJointPositionController.command_joints(...)`
  只支持 6 个关节
- `robot.command_gripper(...)`
  是夹爪独立接口

因此，后续 7 维 socket 实现的关键不是“怎么把 7 维直接塞进 `BuiltinJointPositionController`”，而是“怎么把同一帧拆分后保持节奏一致、语义一致、日志清晰、安全策略一致”。

## 已核对的相关实现

### 1. 新版 `move_debug.py`

[`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 当前流程是：

```python
reach_position = TARGET_POSE_7D[:6]
gripper_position = TARGET_POSE_7D[6]

motion_result = move_to_position_with_keyboard_stop(...)

if motion_result.motion_completed:
    robot.command_gripper(gripper_position, GRIPPER_EFFORT_NOW)
```

这清楚说明：

- 7 维目标位现在只是“6+1”拆分使用
- 夹爪命令并不参与关节运动过程
- 它只是在关节运动成功结束后单独执行一次

### 2. 底层关节控制接口

底层 `BuiltinJointPositionController` 最终调用的是：

- [`piper_control.py`](/home/xinger/MyWork/piper_control_demo/.venv/lib/python3.10/site-packages/piper_control/piper_control.py#L178)
- [`piper_control.py`](/home/xinger/MyWork/piper_control_demo/.venv/lib/python3.10/site-packages/piper_control/piper_control.py#L210)

它内部最终转发到：

- [`piper_interface.py`](/home/xinger/MyWork/piper_control_demo/.venv/lib/python3.10/site-packages/piper_control/piper_interface.py#L721)

接口名就是：

- `command_joint_positions(positions: Sequence[float])`

并且长度就是 6 个关节。

### 3. 底层夹爪控制接口

夹爪走的是另一条独立接口：

- [`piper_interface.py`](/home/xinger/MyWork/piper_control_demo/.venv/lib/python3.10/site-packages/piper_control/piper_interface.py#L810)

接口是：

- `command_gripper(position=None, effort=None)`

这说明：

- 夹爪不是 `BuiltinJointPositionController` 的一部分
- 第 7 维必须单独调用
- 这也是为什么实时 7 维流后续一定要做“同帧拆分”

### 4. 历史 socket 实现

[`tests/socket_old/socket_joint_realtime_follow.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_old/socket_joint_realtime_follow.py) 当前只处理：

- JSON 里的 `q`
- 且要求 `len(q) == 6`
- 实时跟随阶段只调用 `controller.command_joints(q)`

所以这份旧实现只能说明“6 关节实时跟随怎么做”，不能直接回答“7 维流如何把夹爪也接进来”。

## 当前最值得明确的边界

### 边界 1

不要试图把 7 维数据直接传给 `BuiltinJointPositionController`。

原因很简单：

- 它只接受 6 个关节
- 第 7 维夹爪不属于这个控制器的接口契约

### 边界 2

后续“夹爪和关节一同控制”不等于“真正硬实时同时下发”。

在 Python 脚本这一层，最现实的实现是：

- 同一帧到达
- 同一循环里先后发两条命令

这在语义上已经足够接近“同步控制”，但不要把它误写成“单条底层 7 维原子命令”。

### 边界 3

夹爪的时间响应大概率和 6 个关节不同。

所以即使你在 200Hz 循环里每帧都同时下发：

- `controller.command_joints(joint_q)`
- `robot.command_gripper(gripper_pos, effort)`

视觉上和动力学上，夹爪也未必会和 6 关节完全同步。

这不是代码写法的问题，而是控制对象和底层执行机构本来就不同。

## 对后续实现的建议

### 建议 1

后续 7 维 socket 协议可以继续保持：

```json
{"t": 0.000, "q": [j1, j2, j3, j4, j5, j6, gripper_pos]}
```

但接收端进入控制循环后，要立即拆分：

```python
joint_q = q[:6]
gripper_pos = q[6]
```

### 建议 2

接收端的实时控制循环应改成这种语义：

1. 收到一帧 7 维数据
2. 校验长度为 7
3. 前 6 维调用 `controller.command_joints(joint_q)`
4. 第 7 维调用 `robot.command_gripper(gripper_pos, fixed_effort)`
5. 同一轮循环里完成日志、守护和按键检测

这才是对新版 `move_debug.py` 控制标准的自然延伸。

### 建议 3

夹爪 `effort` 不建议也塞进第一版 7 维实时流。

第一版更稳妥的是：

- 7 维流只传 `gripper_pos`
- `effort` 由接收端固定成一个保守常量

理由：

- 降低协议复杂度
- 避免上游发送端把力值也不断抖动地下发
- 更符合你当前 `move_debug.py` 的调试方式

### 建议 4

后续如果放到 `src/piper_socket_bridge/`，建议把实时控制主循环职责拆清楚：

- 协议解析
- 帧合法性校验
- 7 维拆分
- 同周期下发关节与夹爪命令
- 软件层急停
- 程序层运动异常守护
- 状态打印与节流

不要再把这些全部堆回一个大 `main()` 里。

## 当前实现如果直接照搬会有什么问题

### 问题 1

如果直接把 `move_debug.py` 的“先动关节、后动夹爪”照搬到 socket 流里，那夹爪只会在关节整段动作结束后才更新一次。

这就失去了 7 维实时流的意义。

### 问题 2

如果直接沿用 `tests/socket_old/` 的 6 维跟随主循环，那第 7 维夹爪会被完全忽略。

### 问题 3

如果把夹爪更新频率做得和关节一样，但没有节流、日志分离和守护策略，终端输出和异常处理会变得混乱。

所以后续设计里要明确：

- 命令下发频率可以同周期
- 打印频率应降采样
- 守护逻辑仍然应主要盯 6 关节误差，不要先把夹爪守护复杂化

## 一句话总结

后续 7 维 socket 实时控制的正确做法，不是把 7 维直接交给 `BuiltinJointPositionController`，而是把每一帧拆成“6 关节目标 + 1 个夹爪目标”，在同一个控制周期里连续下发两条命令；这样既延续了新版 `move_debug.py` 的控制标准，也避免回退到 `socket_old` 里那套只支持 6 关节的旧实现。
