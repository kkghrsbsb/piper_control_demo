# PyBullet Socket 实时跟随测试方案

## 功能目标

实现一组放在 `tests/` 下的专项测试程序，用于把 PyBullet 图形界面的滑条操作，实时映射到真实 Piper 机械臂。

整体链路如下：

1. 启动仿真发送程序
2. 在 PyBullet 中通过滑条调节前 6 个关节
3. 发送程序以 `200Hz` 持续发送 socket JSON 数据流
4. 启动真实机械臂接收程序
5. 接收程序先让机械臂回到零位
6. 接收程序检查发送端前几帧是否为零位
7. 若发送端已在零位，则开始实时跟随
8. 在发送端继续拖动滑条时，真实机械臂同步运动
9. 通过键盘介入结束实时跟随，并进入失能提醒流程

## 当前基础

现有仓库已经具备两块可复用基础：

### 1. 仿真端基础

[`src/piper_pybullet_sim/joint_slider_control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/joint_slider_control.py) 已经实现：

- 打开 PyBullet GUI
- 加载 Piper URDF
- 为可控关节创建滑条
- 在 `200Hz` 仿真循环中读取滑条值
- 将滑条值回写到对应关节

这意味着仿真端已经具备“实时读取当前关节目标”的核心能力，只差把前 6 个关节打包成 socket 数据流发送出去。

### 2. 真实机械臂接收端基础

[`tests/socket_joint_stream_test.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_joint_stream_test.py) 已经实现：

- 连接真实机械臂
- 必要时使能与复位
- 使用 `BuiltinJointPositionController`
- `robot.set_arm_mode(speed=5)`
- 先回零位
- 接收 JSON socket 数据流
- 每收到一帧就调用 `controller.command_joints(q)`
- 最后保留人工确认是否失能

这意味着真实控制侧已经具备“按流式关节角驱动”的基本骨架。

## 方案可行性判断

这个方案总体上是可行的，而且路径比较自然：

- 仿真端负责“产生 200Hz 关节角流”
- 接收端负责“把 200Hz 关节角流下发到真实机械臂”
- 两边用 localhost 或局域网 socket 连接
- 真实机械臂在启动跟随前强制先回零位，能减少初始姿态偏差带来的突变风险

## 我认为合理的部分

- 拆成两个 Python 程序是合理的
  因为仿真 GUI 和真实机械臂控制本来就属于两个职责，拆开后更好调试，也更接近将来“仿真端与真实端分机运行”的方向。
- 接收端在开始跟随前检查前几帧是否零位是合理的
  这样能避免机械臂刚回零位时，发送端却已经处在别的姿态，导致一接入就发生突跳。
- 先启动仿真发送程序，再启动真实机械臂接收程序，这个操作顺序也合理
  因为这样一来，接收端在回零位后能立即检查发送端当前姿态是否满足要求。

## 我认为需要优化的地方

### 1. “200Hz 同步打印当前关节角”不太理想

这个想法可以实现，但不太推荐作为默认行为。

原因：

- 终端会被 200Hz 日志快速刷满
- 真正有价值的信息会被噪声淹没
- 打印本身可能影响接收循环的实时性

更好的建议是：

- 控制命令仍然按 `200Hz` 下发
- 日志打印默认降采样到 `10Hz` 或 `20Hz`
- 如果你坚持，也可以提供一个开关支持“全量打印”

文档阶段先保留你的原始设想，但我建议实现时做成可配置行为，而不是写死。

### 2. 结束方式建议明确区分“停止跟随”和“是否失能”

你的想法里提到“要有个键盘键介入做结束失能提醒”，这个方向是对的，但建议拆成两步：

1. 键盘键只负责结束实时跟随
2. 跟随结束后，再弹出原有的“是否失能”确认

这样更安全，也更清晰：

- 先停流和停跟随
- 再由人决定是否失能

## 建议新增的两个测试脚本

建议新增下面两个文件：

### 1. 发送端

- `tests/pybullet_socket_stream_sender.py`

职责：

- 参考 [`src/piper_pybullet_sim/joint_slider_control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/joint_slider_control.py)
- 启动 PyBullet GUI
- 在 200Hz 循环中读取滑条值
- 只提取前 6 个关节
- 发送 JSON 行流：

```json
{"t": 0.000, "q": [0.0, 0.1, -0.2, 0.3, 0.0, 1.57]}
```

- 启动时默认就在零位
- 支持键盘退出或窗口关闭后断开 socket

### 2. 接收端

- `tests/socket_joint_realtime_follow.py`

职责：

- 参考 [`tests/socket_joint_stream_test.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_joint_stream_test.py)
- 连接机械臂并初始化
- 使用 `BuiltinJointPositionController`
- `robot.set_arm_mode(speed=5)`
- 先运动到零位
- 接收发送端的 200Hz 数据流
- 在前几帧检查是否为零位
- 若不是零位，则警告并拒绝进入实时跟随，或等待发送端回零后再继续
- 若是零位，则进入实时跟随
- 跟随期间持续输出当前关节角
- 通过键盘键结束实时跟随
- 跟随后进入是否失能确认

## 推荐的数据流协议

首版协议可以保持尽量简单：

- 传输方式：TCP
- 每帧一行 JSON
- 字段：
  - `t`: 发送端相对时间
  - `q`: 6 维关节角数组

首版不额外加入：

- 校验和
- 握手协议
- 双向 ACK
- 心跳包

## 发送端设计

发送端可按下面逻辑工作：

1. 启动 PyBullet GUI
2. 加载 URDF
3. 创建滑条
4. 启动 socket server 或 client
5. 每个仿真步读取滑条值
6. 提取前 6 个关节
7. 打包 JSON
8. 按 `200Hz` 发送

这里有一个设计选择：

- 方案 A：发送端作为 client，主动连接接收端
- 方案 B：发送端作为 server，等待接收端来连

我更推荐方案 A：

- 保持和现有 `tests/socket_joint_stream_test.py` 的习惯一致
- 真实机械臂接收端监听，仿真端连接
- 便于以后继续沿用接收端“先回零再等待流”的控制方式

## 接收端设计

接收端流程建议如下：

### 1. 初始化阶段

直接参考 [`tests/socket_joint_stream_test.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_joint_stream_test.py)：

- `connect_can()`
- 人工确认即将运动
- 创建 `PiperInterface`
- 设置安装方向
- 必要时 `reset_arm`
- `reset_gripper`
- `robot.show_status()`

### 2. 回零阶段

进入 `BuiltinJointPositionController` 后：

- 调用 `robot.set_arm_mode(speed=5)`
- 先执行 `move_to_position(ZERO_POSITION, ...)`

只有在真实机械臂成功到零位后，才开始真正接收和判定发送端数据。

### 3. 零位检查阶段

接收端在收到前几帧时，检查 `q` 是否接近：

```python
[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
```

建议不要用完全相等，而是用一个小阈值判断，例如每个关节误差小于 `0.01`。

处理策略建议：

- 如果前几帧都在阈值内：提示“发送端已在零位，开始实时跟随”
- 如果前几帧明显不在零位：提示“发送端未在零位，请先回零”

这里有两个可选策略：

1. 严格策略
   直接拒绝进入跟随并退出
2. 宽松策略
   持续监听，直到发送端回到零位后再开始

我更推荐宽松策略，用户体验更好，也更符合你“先开仿真、后开接收，再调整滑条”的使用方式。

## 实时跟随阶段

一旦发送端确认在零位，接收端进入实时跟随：

- 每收到一帧就调用一次 `controller.command_joints(q)`
- 不在接收端做额外插值
- 不主动改频率，保持“收到即发”

原因：

- 发送端已经是 200Hz
- `BuiltinJointPositionController.command_joints(...)` 本身不限频
- 双边再做二次节拍控制会增加时序复杂度

## 当前关节角输出策略

你希望参考 [`scripts/show_status.py`](/home/xinger/MyWork/piper_control_demo/scripts/show_status.py) 在接收端同步输出当前关节角。

这个需求可以分为两个实现层次：

### 方案 1：完全按你的想法

- 每个接收周期都打印一次 `robot.get_joint_positions()`
- 理论上接近 `200Hz`

优点：

- 最直观

缺点：

- 终端输出过载
- 对实时性不友好

### 方案 2：推荐方案

- 控制仍保持 200Hz
- 打印使用单独的节拍，例如每 0.05s 打印一次

优点：

- 更稳定
- 更容易观察

建议最终实现时做成参数或常量可切换。

## 键盘介入设计

接收端需要支持一个键盘键结束跟随。

推荐做法：

- 使用类似 `record_trajectories.py` 的非阻塞按键读取方式
- 例如约定：
  - `q`: 停止实时跟随

行为建议：

1. 按下 `q`
2. 立即停止继续接收和下发新的目标关节角
3. 打印“实时跟随结束”
4. 进入原有“是否失能”确认

这比“按一个键就直接失能”更安全。

## 建议执行步骤

最终使用流程建议为：

1. 启动 `tests/pybullet_socket_stream_sender.py`
2. 等待 PyBullet 图形界面打开
3. 保持发送端初始零位不动
4. 启动 `tests/socket_joint_realtime_follow.py`
5. 真实机械臂自动回零
6. 接收端检查发送端前几帧是否也在零位
7. 检查通过后开始实时跟随
8. 在发送端拖动滑条，观察真实机械臂同步变化
9. 在接收端按键结束跟随
10. 按提示决定是否失能

## 风险与边界

这个功能会直接让图形界面滑条映射到真实机械臂，风险高于上一版单次插值测试。

必须明确：

- 仿真端滑条变化会直接影响真实机械臂
- 初次联调必须小范围、慢速、人工在场
- `robot.set_arm_mode(speed=5)` 应保留
- 零位检查必须先通过，避免一接入就大幅跳变
- 键盘中断必须优先可靠
- 不应在没有人工看护时运行

## 首版暂不做的内容

首版建议不做以下扩展：

- 多机械臂
- 双向同步协议
- 网络重连机制
- 插值平滑器
- 滑条变化限速器
- GUI 内显示网络状态
- 自动化测试

## 预期输出

确认后，下一步实现应产出：

1. 一个 PyBullet socket 发送测试程序
2. 一个真实机械臂实时跟随接收测试程序
3. 必要的入口文档更新，说明用途、操作顺序和安全边界
