# Socket 关节流跟随测试方案

## 目标

在不改动现有功能代码的前提下，先明确一个后续要实现的测试脚本方案。

目标脚本放在 `tests/` 中，行为参考 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 的前半段流程：

1. 连接机械臂
2. 人工确认即将运动
3. 检查是否已使能
4. 必要时 `reset_arm`
5. `reset_gripper`
6. 使用 `BuiltinJointPositionController`
7. `robot.set_arm_mode(speed=5)`
8. 先运动到零位 `[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]`
9. 零位后启动一个测试用 socket 数据发送函数
10. 接收 200Hz 的关节角数据流并驱动机械臂跟随
11. 跟随后保留“是否失能”的人工提醒流程

## 输入数据格式

每一帧 socket 数据预期为 JSON 文本，格式类似：

```json
{"t": 0.000, "q": [0.0, 0.1, -0.2, 0.3, 0.0, 1.57]}
```

约束：

- `t` 表示相对时间戳，单位为秒
- `q` 为 6 维关节角，单位为弧度
- 数据流目标频率为 `200Hz`

## 首版测试范围

首版只做“本机模拟发送 + 本机接收执行”的闭环测试，不引入外部仿真器。

模拟发送端的数据目标轨迹为：

- 起点：`[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]`
- 终点：`[0.2, 0.2, -0.2, 0.3, -0.2, 0.5]`

发送端按固定时长做线性插值，逐帧通过 socket 发给接收端。

## 建议脚本结构

建议先在 `tests/` 下新增一个单文件测试脚本，名字可以后续再定，例如：

- `tests/socket_joint_stream_test.py`

脚本内部建议拆成下面几个部分：

### 1. 连接与初始化部分

这一段尽量直接参考 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 前 50 行附近的流程，减少分叉：

- `connect_can()`
- 用户确认 `WARNING: the robot will move`
- 创建 `PiperInterface`
- 设置安装方向 `UPRIGHT`
- `probe_arm_enabled_state(robot)`
- 如未使能则 `piper_init.reset_arm(...)`
- `piper_init.reset_gripper(robot)`
- `robot.show_status()`

### 2. 控制器上下文

仍然使用：

```python
with piper_control.BuiltinJointPositionController(
    robot,
    rest_position=None,
) as controller:
```

进入控制器后立即设置：

```python
robot.set_arm_mode(speed=5)
```

然后先调用：

```python
controller.move_to_position([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], threshold=0.01, timeout=8.0)
```

只有在成功到达零位后，才进入 socket 测试阶段。

### 3. 测试发送端

在同一个脚本中放一个“模拟 socket 发送函数”，用途仅限测试。

建议职责：

- 绑定本机地址，例如 `127.0.0.1`
- 生成插值轨迹
- 按 `200Hz` 发送 JSON 帧
- 每帧包含 `t` 和 `q`
- 发送完成后主动关闭连接或发结束标记

建议先做最简单的线性插值：

- 总时长例如 `2.0s`
- 总帧数 `duration * 200`
- 每帧按 `alpha` 在起点和终点之间线性插值

### 4. 接收端

接收端放在同一测试脚本中，作为真实控制机械臂的一侧。

建议职责：

- 监听或连接本机 socket
- 逐帧读取 JSON
- 解析出 `q`
- 校验 `q` 长度是否为 6
- 将 `q` 直接传给 `controller.command_joints(q)`

这里不建议对每帧再额外做二次插值，因为发送端已经是 200Hz 插值流，接收端首版应尽量保持“收到什么就发什么”。

## 频率设计

根据当前已确认的 `piper-control` 实现：

- `BuiltinJointPositionController.move_to_position(...)` 内部循环频率约为 `200Hz`
- `BuiltinJointPositionController.command_joints(...)` 本身不做限频
- 因此，socket 跟随阶段的实际命令频率主要由“你接收并调用 `command_joints(...)` 的节奏”决定

因此首版建议：

- 发送端目标频率：`200Hz`
- 接收端处理策略：每收到一帧就立即调用一次 `controller.command_joints(q)`
- 不强行在接收端再 sleep 到另一个频率，避免双重节拍叠加

## 并发模型建议

首版建议采用最简单、最容易调试的结构：

- 主线程负责机械臂连接、初始化、零位、接收控制和最后的失能确认
- 一个后台线程负责模拟发送 socket 数据

这样做的好处：

- 初始化和真实控制链路集中在主线程，更接近 `move_debug.py`
- 发送端仅用于测试，和真实控制解耦
- 出现异常时更容易先停接收端，再退出控制器上下文

## 结束条件

socket 跟随阶段建议有明确的结束条件，首版可选最简单的一种：

1. 发送端发完全部轨迹帧后关闭连接
2. 接收端读到 EOF 或连接关闭后退出跟随循环
3. 跟随完成后打印当前关节角
4. 继续沿用 `move_debug.py` 里的“是否失能”提醒

## 异常与安全边界

这个测试不是普通软件测试，而是直接驱动真实机械臂。

实现时必须明确以下边界：

- 只有在机械臂成功到达零位后，才开始 socket 数据流跟随
- 如果 socket 数据格式错误、关节维度不对或连接异常，应立即停止发送新命令
- 如果零位阶段失败，不应继续进入 socket 跟随
- 保留 `robot.set_arm_mode(speed=5)`，优先降低速度风险
- 后续由你人工测试时，仍需确认周围无碰撞风险

## 实现顺序建议

后续真正开始改代码时，建议按下面顺序实施：

1. 新建测试脚本骨架，复制 `move_debug.py` 前半段初始化流程
2. 保留零位运动与 `speed=5`
3. 增加本机 socket 模拟发送函数
4. 增加接收循环，逐帧调用 `controller.command_joints(q)`
5. 增加结束条件与异常处理
6. 接回“是否失能”的提醒逻辑

## 暂不实现的内容

这次方案阶段先不做下面这些扩展：

- 多机械臂
- 双向握手协议
- 更复杂的时间同步策略
- 丢帧补偿
- 接收端再插值或平滑滤波
- 与外部仿真器联调
- 自动化测试或无人值守执行

## 预期结果

确认后，下一步要写出的脚本应能完成下面这条链路：

机械臂连接并使能 -> 运动到零位 -> 启动测试用 socket 发送 -> 接收 200Hz 关节角流 -> 从零位跟随到目标姿态 -> 人工决定是否失能
