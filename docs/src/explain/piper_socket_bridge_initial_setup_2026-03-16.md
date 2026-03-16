# piper_socket_bridge 初步搭建说明

## 这次改了什么

这次改动主要围绕三件事展开：

1. 初步搭建新的 [`src/piper_socket_bridge`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge) 库骨架
2. 在 [`tests`](/home/xinger/MyWork/piper_control_demo/tests) 下恢复新的“仿真滑条 -> 真实机械臂”单向测试入口
3. 把状态输出、调试脚本和项目文档统一到新的 `q + gripper` 协议语义

### 1. 新增 `piper_socket_bridge` 库骨架

新增的核心文件有：

- [`protocol.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/protocol.py)
- [`sim_adapter/pybullet_sender.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/sim_adapter/pybullet_sender.py)
- [`receiver/robot_follow.py`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge/receiver/robot_follow.py)

其中：

- `protocol.py`
  定义了统一帧结构 `PoseStreamFrame`
- `sim_adapter/pybullet_sender.py`
  提供新的 PyBullet 发送端实现
- `receiver/robot_follow.py`
  提供新的真实机械臂接收端实现

### 2. 新增新的测试入口脚本

新增：

- [`tests/pybullet_socket_stream_sender.py`](/home/xinger/MyWork/piper_control_demo/tests/pybullet_socket_stream_sender.py)
- [`tests/socket_joint_realtime_follow.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_joint_realtime_follow.py)

这两个入口脚本很薄，主要作用是直接调用新库，而不是继续把旧测试逻辑塞在 `tests/` 里。

### 3. 调整了协议相关脚本

这次还顺手统一了两个已有脚本：

- [`scripts/show_status.py`](/home/xinger/MyWork/piper_control_demo/scripts/show_status.py)
  现在改为以约 `200Hz` 输出：
  `{"t": ..., "q": [j1, ..., j6], "gripper": ...}`
- [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py)
  本地调试目标位变量从混合数组调整为：
  - `TARGET_Q`
  - `TARGET_GRIPPER`

## 为什么这样改

### 原因 1：把协议从旧测试脚本里抽出来

原来的 socket 路径主要散落在：

- [`tests/socket_old/pybullet_socket_stream_sender.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_old/pybullet_socket_stream_sender.py)
- [`tests/socket_old/socket_joint_realtime_follow.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_old/socket_joint_realtime_follow.py)

这些文件能提供早期参考，但不适合继续作为新实现基线。

这次改动的核心目的，就是把：

- 协议定义
- 仿真发送逻辑
- 真实机械臂接收逻辑

从旧测试脚本中拆出来，开始沉淀到可复用的库里。

### 原因 2：协议语义改成 `q + gripper`

这次明确放弃了“把夹爪塞进 7 元数组”的协议语义，统一改成：

```json
{"t": 0.000, "q": [j1, j2, j3, j4, j5, j6], "gripper": 0.8}
```

这么改有几个直接好处：

- `q` 明确只表示 6 个关节
- `gripper` 单独成字段，更贴近底层接口现实
- 仿真、真实机械臂、LeRobot 后续都更容易适配

### 原因 3：仿真端改以 `slider_arm_gripper.py` 为参考

新的发送端不再围绕早期 [`joint_slider_control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/joint_slider_control.py) 的旧语义来搭，而是直接参考：

- [`slider_arm_gripper.py`](/home/xinger/MyWork/piper_control_demo/src/piper_pybullet_sim/slider_arm_gripper.py)

这意味着：

- 仿真侧已经按单一 `gripper_position` 滑条语义组织
- 更适合作为新的 `q + gripper` 发送协议来源

## 具体影响了什么

### 1. 协议层

统一协议现在已经初步固定成：

- `t`
- `q`
- `gripper`

后续新的 socket 相关实现都应默认沿用这套格式。

### 2. 仿真侧测试路径

新的 [`tests/pybullet_socket_stream_sender.py`](/home/xinger/MyWork/piper_control_demo/tests/pybullet_socket_stream_sender.py)
不再直接复制旧测试文件，而是走：

- `piper_socket_bridge.sim_adapter.pybullet_sender`

### 3. 真实机械臂接收侧测试路径

新的 [`tests/socket_joint_realtime_follow.py`](/home/xinger/MyWork/piper_control_demo/tests/socket_joint_realtime_follow.py)
会复用：

- `connect_can()`
- `ensure_arm_and_gripper_enabled()`
- `configure_collision_protection()`
- `confirm_and_shutdown()`

也就是说，它已经开始和新版 [`move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 的控制标准对齐。

### 4. 文档和入口理解路径

这次同步更新了：

- [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md)
- [`README.md`](/home/xinger/MyWork/piper_control_demo/README.md)

现在仓库文档已经把这条新的 socket 路径记录成“当前正在形成中的新基线”。

## 当前实现的范围

这次是“初步搭建”，不是完整完成。

已经有的部分：

- 统一协议骨架
- PyBullet 发送端骨架
- 真实机械臂接收端骨架
- 新测试入口
- 文档同步

还没有完整做完的部分：

- 双向流测试
- LeRobot 适配
- 更细的模块拆分
- 更完整的异常恢复与状态回传

## 风险与兼容性问题

### 风险 1：当前仍是初版骨架

虽然结构已经搭起来了，但它仍然是第一版，主要风险是：

- 后续模块边界可能还会继续微调
- 某些参数可能还要继续收敛

所以当前更适合把它看作“新基线起点”，而不是最终架构。

### 风险 2：没有声明硬件验证结果

这次改动只完成了代码和文档层搭建，没有在说明里宣称：

- 真实机械臂联调已完成
- PyBullet GUI 联调已完成
- socket 全链路已在现场跑通

这一点必须保持明确。

### 风险 3：旧路径和新路径暂时并存

当前仓库里仍然保留了：

- [`tests/socket_old/`](/home/xinger/MyWork/piper_control_demo/tests/socket_old)

所以短期内会存在：

- 旧历史实现
- 新库骨架

并存的状态。

兼容性上不是坏事，但需要团队持续遵守文档约定：

- 新实现优先参考新库和新版 `move_debug.py`
- 旧测试只作历史参考

### 风险 4：实时跟随的安全边界仍然存在

新的接收端虽然已经对齐了：

- 初始化
- 碰撞保护配置
- 收尾失能流程

但它本质上仍然是会真实驱动机械臂的测试脚本，所以仍然属于高风险动作。

## 一句话总结

这次改动的本质，是把原本散落在旧测试里的 socket 试验路径，开始收敛成一个新的 `piper_socket_bridge` 库骨架，并把协议统一成 `q + gripper`，同时用新的单向测试脚本把 PyBullet 发送端和真实机械臂接收端重新接起来，为后续双向流和 LeRobot 适配打基础。
