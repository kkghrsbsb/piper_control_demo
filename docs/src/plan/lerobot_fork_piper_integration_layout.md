# LeRobot Fork 中的 Piper 移植与接入目录结构方案

## 功能目标

为你后续在自己 fork 的 LeRobot 仓库中接入 Piper 机械臂提供一套清晰的目录结构建议，目标是：

- 在 LeRobot 现有架构里新增 Piper 相关代码文件夹与入口
- 让真实机械臂控制继续复用你当前仓库已经验证过的控制基线
- 尽量减少把实验性控制逻辑直接散落进 LeRobot 主仓
- 为后续主从臂、socket 桥接、dataset 录制、teleoperate 和 policy 接入留下扩展空间

这次只整理结构方案，不改代码。

## 当前动机

你后面大概率会走这条路线：

1. 先在当前仓库里把 Piper 的控制、安全、socket、仿真语义打磨清楚
2. 再把其中一部分沉淀成可复用库
3. 在你 fork 的 LeRobot 仓库中做真正的机器人接入与移植

结合你已经放进 [`docs/reference/huggingface-lerobot-8a5edab282632443.txt`](/home/xinger/MyWork/piper_control_demo/docs/reference/huggingface-lerobot-8a5edab282632443.txt) 的导出材料来看，LeRobot 当前比较重要的结构线索是：

- `src/lerobot/robots/`
- `src/lerobot/teleoperators/`
- `src/lerobot/processor/`
- `src/lerobot/scripts/`
- `tests/robots/`
- `tests/teleoperators/`

所以如果要把 Piper 接进去，最合理的做法不是把你当前仓库整个塞进 LeRobot，而是只在 LeRobot 里增加“薄适配层”。

## 核心设计判断

### 判断 1

你当前仓库中的这些内容，不适合原样直接搬进 LeRobot 主体：

- `piper_control_demo.config`
- `piper_control_demo.control`
- `piper_socket_bridge`
- `piper_pybullet_sim`

因为它们现在仍然同时承载：

- 真实硬件初始化
- 安全流程
- 实验脚本语义
- socket 桥接探索
- PyBullet 专项映射

这部分更适合作为你自己的外部依赖库，或者后续抽成独立包后供 LeRobot 调用。

### 判断 2

你在 fork 的 LeRobot 仓库里，应该只新增“LeRobot 侧的 Piper 接入层”，而不是把全部底层逻辑重新写一遍。

也就是说：

- 复杂真实硬件控制逻辑
  尽量留在你自己的库里
- LeRobot 中的 Piper 代码
  负责遵守 LeRobot 的 `Robot` / `Teleoperator` / `Processor` 结构，对外暴露 LeRobot 期望的接口

### 判断 3

如果后续会考虑 Rust 重构，那么更应该把“Piper 硬件控制核心”和“LeRobot 适配层”分离。

这样以后：

- Rust 或 Python 实现的 Piper 核心库
  可以稳定演进
- fork 的 LeRobot
  只做适配和胶水层

## 推荐总体结构

我更建议你在 fork 的 LeRobot 仓库里采用“薄适配 + 外部 Piper 库”的方式。

### 外部库职责

你的外部 Piper 库负责：

- 连接 CAN
- 机械臂/夹爪使能
- 碰撞保护配置
- 软件层急停
- 公共收尾失能
- socket 桥接
- PyBullet 夹爪映射
- 状态流 / 命令流协议

这部分就是你现在这个仓库后续会继续沉淀的核心。

### LeRobot fork 职责

你的 LeRobot fork 负责：

- 声明 Piper 机器人配置
- 实现 LeRobot 风格的 `Robot`
- 需要时实现 LeRobot 风格的 `Teleoperator`
- 把 LeRobot 的 action/observation 和你自己的 Piper 库对接起来
- 提供 LeRobot 风格的脚本入口和测试

## 推荐的新目录结构

下面这套结构最适合你当前阶段。

```text
src/lerobot/
├── robots/
│   └── piper/
│       ├── __init__.py
│       ├── config_piper.py
│       ├── robot_piper.py
│       ├── features.py
│       ├── converters.py
│       └── safety.py
├── teleoperators/
│   └── piper_master/
│       ├── __init__.py
│       ├── config_piper_master.py
│       └── teleop_piper_master.py
├── processor/
│   └── piper/
│       ├── __init__.py
│       └── piper_action_processor.py
└── scripts/
    ├── lerobot_teleoperate_piper.py
    ├── lerobot_record_piper.py
    └── lerobot_replay_piper.py

tests/
├── robots/
│   └── piper/
│       ├── test_piper_config.py
│       ├── test_piper_robot.py
│       └── test_piper_converters.py
├── teleoperators/
│   └── test_piper_master_teleoperator.py
└── processor/
    └── test_piper_action_processor.py
```

## 各目录职责建议

### 1. `src/lerobot/robots/piper/`

这是最核心的新目录，第一阶段应该优先建设。

建议职责如下：

- `config_piper.py`
  定义 Piper 在 LeRobot 里的配置对象，例如 CAN 端口、是否启用夹爪、速度限制、是否启用安全流程、是否启用 socket 桥等。
- `robot_piper.py`
  实现 LeRobot 的 `Robot` 接口，对外暴露：
  - `connect()`
  - `disconnect()`
  - `get_observation()`
  - `send_action()`
  等 LeRobot 期望的方法。
- `features.py`
  集中定义 observation/action feature 命名，例如：
  - `observation.state`
  - `action`
  - `gripper`
  - 如果需要也包括 camera key 约定
- `converters.py`
  做 LeRobot action/observation 与 Piper `q + gripper` 语义之间的映射。
- `safety.py`
  只放 LeRobot 侧需要知道的安全策略开关和薄封装，不要把完整底层安全实现重新复制进来。

### 2. `src/lerobot/teleoperators/piper_master/`

如果你后面要做“物理 Piper 作为主臂，LeRobot teleop 作为上层入口”，这个目录很有必要。

建议职责如下：

- `config_piper_master.py`
  定义主臂 teleoperator 的配置，例如状态发送频率、是否启用夹爪、socket 地址、同步模式。
- `teleop_piper_master.py`
  实现 LeRobot 的 `Teleoperator` 接口或等价抽象，让 Piper 主臂可以输出符合 LeRobot 预期的数据。

这一层尤其适合承接：

- 真实机械臂主臂 -> PyBullet 从臂
- 真实机械臂主臂 -> follower robot
- 录制 teleop dataset

### 3. `src/lerobot/processor/piper/`

这个目录第一阶段可以很薄，甚至可以后置，但我建议先留好位置。

它的职责不是控制硬件，而是处理：

- action 维度重排
- `q + gripper` 规范化/反规范化
- delta action 或 absolute action 的转换
- policy 输出和 Piper 实际控制接口之间的最后一层桥

如果你后面发现只靠 `robots/piper/converters.py` 就够了，这个目录也可以先只有一个很薄的文件。

### 4. `src/lerobot/scripts/`

LeRobot 本身已经有很多统一脚本入口，所以在 fork 中最好继续跟这个风格一致。

你后续大概率会需要：

- `lerobot_teleoperate_piper.py`
- `lerobot_record_piper.py`
- `lerobot_replay_piper.py`

这些脚本不要直接重写底层逻辑，而是：

- 读取 LeRobot config
- 创建 `PiperRobot`
- 调用你的外部 Piper 库
- 保持 LeRobot CLI 使用习惯

## 更推荐的调用边界

### 推荐方式

在 fork 的 LeRobot 里：

- `robot_piper.py`
  直接 import 你自己的 Piper 库
- 把底层动作交给外部库处理
- 自己只负责 LeRobot 兼容接口

例如概念上是：

```python
from my_piper_lib import PiperRuntime
from my_piper_lib import PoseCommand
```

而不是在 LeRobot 里重写：

- CAN 发现
- arm/gripper 使能
- collision protection
- e-stop
- safe shutdown

### 不推荐方式

不要在 fork 的 LeRobot 里再复制一份：

- `connect_can()`
- `ensure_arm_and_gripper_enabled()`
- `configure_collision_protection()`
- `move_to_position_with_keyboard_stop()`
- `confirm_and_shutdown()`

否则后面会出现两套安全逻辑分叉。

## 针对 Piper 的最小文件建议

如果你只想先迈出第一步，最小可用集合我建议是：

```text
src/lerobot/robots/piper/
├── __init__.py
├── config_piper.py
├── robot_piper.py
└── converters.py
```

理由是这 4 个文件已经足够支撑：

- 机器人注册
- 配置声明
- action / observation 转换
- 初版 LeRobot 机器人接入

后面再逐步补：

- `features.py`
- `safety.py`
- `teleoperators/piper_master/`
- `processor/piper/`

## 推荐的代码关系

### `config_piper.py`

建议内容：

- `PiperRobotConfig`
- CAN 端口或自动发现选项
- 是否启用夹爪
- 频率
- 安全相关开关
- 是否启用 socket bridge
- 是否启用 PyBullet 从臂同步

### `robot_piper.py`

建议内容：

- `PiperRobot`
- 连接/断开
- 获取 observation
- 发送 action
- 将 LeRobot 的 action 字典或张量转换为 `q + gripper`
- 调用外部 Piper 库执行

### `converters.py`

建议内容：

- `lerobot_action_to_piper_command(...)`
- `piper_state_to_lerobot_observation(...)`
- 夹爪范围映射
- 关节顺序映射

这部分很关键，因为它能把“LeRobot 侧语义”和“Piper 侧语义”隔开。

### `teleop_piper_master.py`

建议内容：

- 从真实 Piper 主臂读取当前状态
- 转为 LeRobot teleop action
- 供 follower、record 或 policy 桥接使用

## 与当前仓库的关系

后续最理想的关系是：

- 当前仓库继续作为：
  - Piper 硬件控制与实验仓库
  - 安全控制基线仓库
  - socket 与 PyBullet 语义验证仓库
- 你的 LeRobot fork 作为：
  - 机器人接入仓库
  - LeRobot 生态兼容层
  - dataset / teleop / policy 训练入口

也就是说：

- “怎么安全控制 Piper”
  由当前仓库回答
- “怎么让 LeRobot 使用 Piper”
  由 fork 的 LeRobot 回答

## 风险与边界

### 风险 1

如果你把当前仓库的实验脚本直接挪进 LeRobot，很容易把：

- 调试脚本语义
- 专项测试语义
- LeRobot 正式接入语义

混在一起。

### 风险 2

如果过早在 LeRobot 里直接堆 socket bridge、PyBullet 和 teleop 全部逻辑，目录会很快失控。

所以第一阶段应只先把：

- `robots/piper/`

打稳。

### 风险 3

如果后续要用 Rust 重构底层控制核心，那么 LeRobot fork 里越少放底层实现，后续迁移越轻松。

## 实施步骤

1. 先在 fork 的 LeRobot 中只新增：
   - `src/lerobot/robots/piper/`
2. 做最小的：
   - `config_piper.py`
   - `robot_piper.py`
   - `converters.py`
3. 让 `robot_piper.py` 通过外部 Piper 库调用你当前仓库沉淀出的控制能力
4. 等基本 action / observation 跑通后，再补：
   - `teleoperators/piper_master/`
5. 最后才考虑：
   - `processor/piper/`
   - dataset 录制
   - policy 接入
   - PyBullet 从臂同步

## 预期输出

按这套方案推进，后续你会得到：

1. 一个更符合 LeRobot 原生目录习惯的 Piper 接入布局
2. 一个尽量不污染 LeRobot 主仓核心结构的薄适配层
3. 一个能继续复用你当前仓库控制基线的迁移路线
4. 一个方便未来把底层 Piper 核心替换成 Rust 实现的边界划分

## 一句话结论

在你 fork 的 LeRobot 仓库里，最值得先建的是 [`src/lerobot/robots/piper/`] 这一层薄适配目录；真实机械臂控制、安全逻辑、socket 桥接和 PyBullet 语义应尽量继续留在你自己的 Piper 库里，通过接口调用接入，而不是整套复制进 LeRobot。
