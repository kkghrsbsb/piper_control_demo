# PyBullet 真实状态流切换说明

## 这次改了什么

这次改动只集中在一条关键语义切换上：

- 把 PyBullet socket 发送端从“发送滑条目标命令流”
- 改成了“发送仿真真实状态流”

对应实现主要改在：

- [`src/piper_socket_bridge/sim_adapter/pybullet_sender.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py)

同时同步更新了：

- [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md)
- [`README.md`](/home/xinger/MyWork/piper_control_demo/README.md)

## 为什么改

之前发送端的流程本质上是：

1. 读滑条值
2. 把滑条值写给 `setJointMotorControl2(... targetPosition=...)`
3. 直接把滑条值打包成 `{"q": ..., "gripper": ...}` 发出去

这意味着发出去的是：

- 控制目标

而不是：

- 仿真机械臂这一时刻真正已经达到的状态

这在“把流当成目标命令流”时没有问题，但如果后续要做：

- PyBullet -> 真实机械臂
- 真实机械臂 -> PyBullet
- 主臂 / 从臂状态映射

那语义就会出错，因为接收端可能会误以为收到的是“真实反馈状态”。

## 现在怎么改的

### 1. 拆开了“写目标”和“读状态”

现在 [`pybullet_sender.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py) 里分成了两步：

- `apply_slider_targets(...)`
  负责把滑条目标写进 PyBullet 控制器
- `read_robot_state_frame(...)`
  负责在仿真推进后读取当前真实状态并打包成协议帧

### 2. 发送时机变了

现在主循环的顺序是：

1. 读取滑条目标
2. 写入 `setJointMotorControl2(...)`
3. `p.stepSimulation()`
4. 读取真实关节状态
5. 读取真实夹爪状态
6. 发送 `PoseStreamFrame`

这意味着当前发出去的流，不再是“用户刚刚想让它去哪里”，而是“仿真推进后现在实际在哪里”。

### 3. 夹爪状态不再直接取滑条值

夹爪这次也一起切到了真实状态语义。

因为在仿真里夹爪实际由两个关节构成：

- `joint7`
- `joint8`

当前实现会：

- 读取两个关节的当前真实状态
- 按各自的镜像比例恢复成单一控制语义
- 再把它平均回一个独立 `gripper` 字段

这样发送出来的 `gripper` 更接近“仿真当前真实夹爪状态”，而不是“滑条命令值”。

## 影响了什么

### 1. 协议字段没变

协议仍然是：

```json
{"t": ..., "q": [...], "gripper": ...}
```

所以接收端字段名和解析逻辑不需要改。

### 2. 协议语义变了

真正变化的是语义：

- 之前：
  目标命令流
- 现在：
  仿真真实状态流

这对后续主臂/从臂设计更合理。

### 3. 更适合做状态映射

切成真实状态流后，这条链路更适合用于：

- 仿真作为主臂时，把当前仿真真实状态映射给真实机械臂
- 后续与真实机械臂状态流形成语义对齐

## 风险与兼容性问题

### 风险 1

真实状态流天然比目标值更“滞后”。

因为它表达的是：

- 仿真推进之后当前到达的位置

而不是：

- 用户刚设的目标位置

这不是缺点，而是语义更真实后的自然结果。

### 风险 2

如果以后某些实验明确需要“目标命令流”，就不能再直接把当前这个发送端当成目标流发送器使用。

也就是说，这次切换之后：

- 当前默认发送端更适合状态同步
- 不再适合被误解成滑条目标广播器

### 风险 3

夹爪状态恢复现在采用的是“按镜像比例恢复后取平均”的方式。

这在当前 `slider_arm_gripper.py` 语义下是合理的，但如果未来仿真夹爪映射规则变化，这里也需要同步调整。

## 一句话总结

这次改动没有改协议字段，而是把 PyBullet 发送端的语义从“发送滑条目标命令”切成了“发送仿真真实状态”，从而让后续主臂/从臂映射和双向流设计建立在更正确的数据基础上。
