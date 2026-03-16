# 基于 slider_arm_gripper 的新仿真适配与双向流测试方案

## 功能目标

以后续 [`src/piper_socket_bridge`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge) 的搭建为主线，明确把 [`src/piper_pybullet_sim/slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py) 作为新的仿真参考实现，而不是继续沿用基于 [`src/piper_pybullet_sim/joint_slider_control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/joint_slider_control.py) 的旧思路。

同时，为后续“新仿真环境 <-> 真实机械臂”的双向流测试预留清晰结构。

## 当前问题

历史 socket 测试主要有两个局限：

1. 它们大多是从 `joint_slider_control.py` 那条旧仿真控制路径延伸出来的
2. 它们只覆盖了前 6 个关节的实时流，夹爪语义没有真正按新的独立 `gripper` 字段方式接入

而你现在已经在 [`slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py) 里完成了更正确的仿真夹爪控制语义：

- `joint7`
- `joint8`

不再以两个独立滑条直接暴露，而是收敛成单一：

- `gripper_position`

并在程序内部按镜像比例同步驱动两侧夹爪手指。

这意味着：

- 它比 `joint_slider_control.py` 更适合作为新 socket 仿真侧的参考
- 也更适合作为后续双向流测试里的仿真端基线

## 已核对的关键实现点

[`src/piper_pybullet_sim/slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py) 当前有几个很重要的设计点：

### 1. 使用 `SliderControl` / `JointTarget` 做映射

它没有把“一个滑条对应一个关节”写死，而是显式定义了：

- `SliderControl`
- `JointTarget`

这使得“一个滑条驱动多个关节目标”变成了明确的数据结构。

### 2. 夹爪控制做成单一滑条

通过 `get_gripper_control(...)`：

- 找到 `joint7`
- 找到 `joint8`
- 创建单一 `gripper_position` 滑条

然后把它映射成：

- `joint7 * 1.0`
- `joint8 * -1.0`

这正是你想要的“夹爪分离控制，但用户操作上只看一个夹爪位置”的正确语义。

### 3. 仿真主循环已经天然适合做发送端参考

主循环里本来就是：

1. 读所有滑条值
2. 按映射关系写回仿真关节
3. 以固定步长推进仿真

这很适合扩展成：

- 读滑条
- 组装统一协议帧
- 发送 socket 数据

## 为什么它比 joint_slider_control.py 更适合作为新参考

`joint_slider_control.py` 的价值主要在于：

- 演示按关节逐个暴露滑条
- 快速搭建早期 6 关节发送端

但它的夹爪语义不够理想。

相比之下，`slider_arm_gripper.py` 的优势是：

- 已经收敛成独立 `gripper_position`
- 与新的 `{"q": [...], "gripper": ...}` 协议更一致
- 更接近真实机械臂侧“6 关节命令 + 单独夹爪命令”的双通道控制事实

因此，后续新仿真环境适配和双向流测试都应优先参考它。

## 拟议设计

### 1. 仿真适配层以 slider_arm_gripper.py 为核心参考

后续 `src/piper_socket_bridge/sim_adapter/` 里的新仿真适配，不应再围绕 `joint_slider_control.py` 的“所有控制量都按单关节滑条处理”来设计。

应改成围绕 `slider_arm_gripper.py` 这套语义：

- `q` 对应 6 关节
- `gripper` 对应单一夹爪位置

也就是说，仿真端最终发出的协议应类似：

```json
{"t": 0.000, "q": [j1, j2, j3, j4, j5, j6], "gripper": 0.8}
```

### 2. 新仿真发送端应从旧 tests 脚本中脱离

原来基于 `tests/socket_old/pybullet_socket_stream_sender.py` 的思路，可以保留历史参考价值，但不应继续作为新发送端基线。

新的实现更适合放到：

- `src/piper_socket_bridge/sim_adapter/`

或者至少应作为该目录下的新模块来实现。

### 3. 双向流测试需要拆成两个方向

后续“新仿真环境和真实机械臂双向流的测试”，建议不要混成一个含糊说法，而是分成：

- 仿真 -> 真实机械臂
  用于验证仿真滑条和真实机械臂跟随
- 真实机械臂 -> 仿真
  用于验证真实机械臂当前状态能否回传并驱动仿真显示或对照

如果再进一步，可以有：

- 仿真 <-> 真实机械臂双向回环观察

但这应该放在更后面，不要作为第一版目标。

## 对 piper_socket_bridge 的结构建议

基于这次新增背景，建议进一步细化：

- `src/piper_socket_bridge/sim_adapter/slider_source.py`
  负责参考 `slider_arm_gripper.py` 生成统一协议帧
- `src/piper_socket_bridge/sim_adapter/sender.py`
  负责 socket 发送逻辑
- `src/piper_socket_bridge/receiver/robot_follow.py`
  负责真实机械臂接收端
- `src/piper_socket_bridge/sim_adapter/robot_state_sink.py`
  后续如果要做真实机械臂 -> 仿真，可作为状态接收或仿真映射入口

## 建议的测试路径

### 第一阶段

先做单向：

- PyBullet 新仿真发送端
- 真实机械臂接收端

目标是验证：

- `q` 正常跟随
- `gripper` 正常跟随
- 新协议可用
- 新控制链路不再依赖 `socket_old`

### 第二阶段

再做另一单向：

- 真实机械臂状态输出
- 仿真端显示或映射

目标是验证：

- 真实机械臂当前关节角
- 当前夹爪位置

能否稳定回传并驱动仿真端同步显示。

### 第三阶段

如果前两者稳定，再考虑：

- 双向同时在场的回环测试

但这一步风险和复杂度更高，应后置。

## 风险与边界

### 风险 1

双向流测试很容易把“协议验证”和“控制验证”混在一起。

所以第一版一定要先做单向链路。

### 风险 2

仿真夹爪语义虽然已经整理成单一 `gripper_position`，但真实夹爪与仿真夹爪的实际响应仍可能不完全一致。

所以测试时应把目标放在：

- 协议和控制语义一致

而不是：

- 仿真与真实物理细节完全重合

### 风险 3

如果继续从 `socket_old` 拷贝 `main()`，很容易把旧版 6 关节逻辑、旧协议结构和旧安全流程一并带回来。

这正是这次需要避免的。

## 实施步骤

1. 明确把 `slider_arm_gripper.py` 设为新仿真适配参考实现
2. 在 `src/piper_socket_bridge/sim_adapter/` 下设计新的仿真发送端结构
3. 用新的 `{"t": ..., "q": [...], "gripper": ...}` 协议替代旧的 6 关节流
4. 接收端继续复用新版 `move_debug.py` 所代表的公共控制标准
5. 先做仿真 -> 真实机械臂单向测试，再考虑真实机械臂 -> 仿真和双向回环

## 预期输出

如果按这条路线推进，后续会得到：

1. 一个不再依赖 `joint_slider_control.py` 旧语义的新仿真适配基线
2. 一个和单一 `gripper` 字段一致的仿真发送协议
3. 一套更清晰的新单向 / 双向测试分层
4. 一个更适合继续扩展的 `piper_socket_bridge` 结构

## 一句话结论

后续这个库的搭建和新的仿真 <-> 真实机械臂测试，应优先参考 [`src/piper_pybullet_sim/slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py) 这套“单一 `gripper_position` 控制语义”，而不是继续从早期基于 `joint_slider_control.py` 的旧 socket 测试主流程出发。
