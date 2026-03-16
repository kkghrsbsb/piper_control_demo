# 2026-03-16 真实机械臂主臂到 PyBullet 从臂方案

## 目标

后续实现这样一条链路：

- 真实机械臂作为主臂
- 持续输出当前状态流
- PyBullet 仿真环境作为从臂
- 接收该状态流并驱动仿真中的 Piper 模型
- 最终用于在仿真中完成夹取任务验证

## 先回答核心问题

### PyBullet 能不能接受当前这个格式帧做正确控制

可以，前提是接收端按正确方式解析并映射。

当前已经统一的协议是：

```json
{"t": 0.000, "q": [j1, j2, j3, j4, j5, j6], "gripper": 0.8}
```

PyBullet 侧完全可以接受这类帧，因为它本来就是逐关节调用：

- `setJointMotorControl2(...)`

去写入目标位置。

所以只要接收端做到两件事，就能正确控制：

1. 把 `q` 的 6 个关节值按正确索引映射到仿真机械臂前 6 个控制关节
2. 把 `gripper` 映射成 `slider_arm_gripper.py` 已经定义好的单一夹爪控制语义，再内部同步驱动：
   - `joint7`
   - `joint8`

也就是说，协议本身没有问题，关键在于：

- 仿真接收端要参考 [`slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py) 的夹爪映射方式
- 而不是把 `gripper` 当成某一个单独关节直接写死

## 为什么这条路线是合理的

当前仓库已经有三块基础可以拼起来：

### 1. 主臂状态输出格式已经有参考

[`scripts/show_status.py`](/home/xinger/MyWork/piper_control_demo/scripts/show_status.py)
现在已经会以约 `200Hz` 输出：

```json
{"t": ..., "q": [...], "gripper": ...}
```

这已经很接近“主臂状态流”的发送格式。

### 2. 仿真夹爪语义已经整理好了

[`slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py)
已经把仿真夹爪从：

- `joint7`
- `joint8`

整理成单一：

- `gripper_position`

并在内部用镜像关系驱动两侧手指。

这正好适合作为“仿真从臂接收 `gripper` 字段”的实现依据。

### 3. socket 协议层已经初步搭好

[`src/piper_socket_bridge`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge)
已经初步具备：

- 协议结构
- 发送端方向
- 接收端方向

所以现在补“真实机械臂 -> PyBullet”是顺着现有结构扩展，而不是另起一套。

## 拟议实现

### 方向定义

这次要新增的是：

- 主臂：真实机械臂
- 从臂：PyBullet 仿真

也就是和当前已有的：

- PyBullet -> 真实机械臂

形成另一条单向链路。

### 建议新增的模块位置

建议放到：

- `src/piper_socket_bridge/sim_adapter/pybullet_receiver.py`

它的职责是：

- 接收 `{"t": ..., "q": [...], "gripper": ...}` 帧
- 把 `q` 映射到前 6 关节
- 把 `gripper` 映射到仿真夹爪双指
- 持续推进仿真

### 建议新增的测试入口

建议在 `tests/` 下新增一个新的入口，例如：

- `tests/robot_state_to_pybullet_follow.py`

它的职责是：

- 启动 PyBullet 接收端
- 让它作为从臂等待主臂状态流

与之对应，主臂发送端可以先直接复用或轻改：

- [`scripts/show_status.py`](/home/xinger/MyWork/piper_control_demo/scripts/show_status.py)

或者后续再抽成：

- `src/piper_socket_bridge/robot_state_sender.py`

## 控制语义建议

### 1. 主臂流

主臂发送的是“当前状态”，不是“规划目标”。

也就是说，这条链路里：

- `q`
  表示主臂当前 6 关节角
- `gripper`
  表示主臂当前夹爪位置

### 2. 从臂流

PyBullet 从臂接收到帧后，应按下面方式控制：

- 前 6 关节：
  逐个 `POSITION_CONTROL`
- 夹爪：
  参考 `slider_arm_gripper.py` 的镜像控制语义，同时驱动两侧夹爪手指

### 3. 夹取任务语义

如果你的目标是“主臂带着从臂在仿真里做夹取任务”，那么仿真端的目标应该是：

- 忠实跟随主臂状态
- 在视觉上和运动语义上保持一致

而不是要求：

- 仿真和真实机械臂动力学细节完全一致

## 风险和边界

### 风险 1

真实机械臂当前状态流和仿真关节索引必须严格对齐。

如果关节顺序错位，仿真会“能动，但姿态错误”。

### 风险 2

夹爪字段虽然是单一 `gripper`，但仿真端内部仍要按双指镜像去实现。

这一层如果偷懒写成“只写一个关节”，从臂夹爪动作就会不正确。

### 风险 3

主臂到从臂这条链路本质上更像“状态映射”而不是“闭环控制”。

所以第一版重点应该是：

- 流能通
- 姿态能对
- 夹爪能对

而不是先追求复杂任务成功率。

## 推荐实施顺序

1. 新增 PyBullet 接收端模块，能吃 `q + gripper` 帧
2. 先用本地假数据流验证仿真从臂能否正确动起来
3. 再接真实机械臂当前状态流
4. 最后再做“主臂带从臂夹取”的任务级验证

## 一句话结论

PyBullet 可以正确接受当前 `{"t": ..., "q": [...], "gripper": ...}` 这种帧来做从臂控制；关键不是协议本身，而是仿真接收端必须按 [`slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py) 的语义正确处理 `gripper`，这样真实机械臂作为主臂、PyBullet 作为从臂的单向映射路线是成立的。
