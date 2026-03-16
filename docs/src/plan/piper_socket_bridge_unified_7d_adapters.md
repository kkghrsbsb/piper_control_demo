# piper_socket_bridge 统一关节流与夹爪适配方案

## 功能目标

把 [`src/piper_socket_bridge`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge) 设计成一个统一的关节流与夹爪桥接层，而不是只服务某一个历史 socket 测试脚本。

这层桥接的核心职责是：

- 接收上游输出的统一目标位流
- 统一协议语义
- 把数据转发给真实机械臂控制侧
- 保持与当前新版 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 一致的初始化、安全、守护和收尾标准

## 当前动机

你现在的 socket 方向不只服务一种场景，而是至少覆盖三类上游来源：

1. PyBullet 仿真环境
2. 真实机械臂之间或控制链路中的双向 socket 流
3. LeRobot 输出的 `target_pose` 流

这意味着后续最稳妥的设计，不是继续围绕某个单独测试脚本扩写，而是先收敛出统一的桥接层协议与目录结构。

## 统一输入语义

后续建议统一采用这类分字段协议：

```json
{"t": 0.000, "q": [j1, j2, j3, j4, j5, j6], "gripper": 0.8}
```

其中：

- `t`
  表示时间戳或发送端相对时间，可选但建议保留
- `q`
  是统一的 6 关节目标位数组
- `gripper`
  是独立的夹爪位置字段

这个语义的好处是：

- 仿真端容易生成
- 真实机械臂接收端容易拆分
- LeRobot 的 `target_pose` 也可以映射到同样的结构
- 它更符合底层本来就是“关节控制器 + 独立夹爪接口”两条通道的事实

## 关键控制原则

### 原则 1

`src/piper_socket_bridge/` 后续的真实机械臂控制标准，必须以当前新版 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 为基线。

这里的“基线”包括：

- `connect_can()`
- `set_installation_pos(...)`
- `ensure_arm_and_gripper_enabled()`
- `configure_collision_protection()`
- 公共软件层急停
- 公共程序层运动异常守护
- 公共收尾失能流程

### 原则 2

不要再参考 [`tests/socket_old`](/home/xinger/MyWork/piper_control_demo/tests/socket_old) 中旧版 `main()` 控制流程作为新实现依据。

历史 socket 测试文件的价值现在主要是：

- 看旧协议
- 看旧日志习惯
- 看早期 socket 通信基本写法

但它们不是后续桥接库的控制标准。

### 原则 3

后续实时控制的正确实现，不是把夹爪混进 `q` 里直接交给 `BuiltinJointPositionController`。

每一帧都应解析成：

- `joint_q = frame["q"]`
- `gripper_pos = frame["gripper"]`

然后在同一个控制周期里连续下发：

- `controller.command_joints(joint_q)`
- `robot.command_gripper(gripper_pos, fixed_effort)`

也就是说，桥接层要统一的是“同帧双通道语义”，而不是试图发明一个底层统一控制器。

## 建议目录结构

建议在 [`src/piper_socket_bridge`](/home/xinger/MyWork/piper_control_demo/src/piper_socket_bridge) 下拆出两个适配子目录：

- `src/piper_socket_bridge/sim_adapter/`
- `src/piper_socket_bridge/lerobot_adapter/`

另外建议同时保留一层公共模块，例如：

- `src/piper_socket_bridge/protocol.py`
- `src/piper_socket_bridge/runtime/`
- `src/piper_socket_bridge/receiver/`

这样职责会更清楚。

## 各目录职责建议

### 1. `sim_adapter/`

用于承载“面向仿真环境”的适配层。

它的职责可以包括：

- PyBullet 当前滑条值到统一 `q + gripper` 协议的映射
- 仿真侧 socket 发送端封装
- 单一 `gripper_position` 到仿真夹爪内部镜像驱动语义的对接

这层更关注：

- 仿真协议输出
- 仿真端坐标/关节语义整理
- 发送频率和 socket 发送逻辑

### 2. `lerobot_adapter/`

用于承载“面向 LeRobot 输出”的适配层。

它的职责可以包括：

- 把 LeRobot 输出的 `target_pose` 映射到统一 `q + gripper` 协议
- 对接 LeRobot 自身的数据结构、字段命名、频率与时间戳
- 必要时做维度重排、夹爪字段映射或归一化到物理量

这层更关注：

- 上游数据字段兼容
- LeRobot 到本项目统一协议的转换
- 适配层不要直接混入真实机械臂控制主循环

### 3. 公共桥接层

建议放在 `piper_socket_bridge` 根目录或单独 `runtime/` 下。

它的职责可以包括：

- 协议定义
- 帧合法性校验
- 序列化/反序列化
- 接收端实时循环
- 与 `piper_control_demo` 公共控制能力对接

这层才是“真正连接上游数据源和真实机械臂”的桥。

## 推荐的模块分工

后续如果继续实现，比较稳的模块分工可以是：

- `protocol.py`
  定义统一帧格式、校验函数和解析函数
- `sim_adapter/`
  负责 PyBullet 或其他仿真来源的适配
- `lerobot_adapter/`
  负责 LeRobot 的 `target_pose` 适配
- `receiver/robot_follow.py`
  负责真实机械臂接收端，把统一流拆成关节命令和夹爪命令
- `runtime/session.py`
  负责 socket 生命周期、节流、日志和错误处理

## 与新版 `move_debug.py` 的关系

后续桥接库的真实机械臂控制侧，不应复制 `move_debug.py` 的整个 `main()`，而应复用它已经体现出的控制标准。

也就是说：

- `move_debug.py` 是当前“控制标准样板”
- `piper_socket_bridge` 是未来“协议与桥接层”

两者关系不是复制粘贴，而是：

- 桥接库复用 `piper_control_demo.config`
- 桥接库复用 `piper_control_demo.control`
- 桥接库自身只负责 socket、协议和适配层

## 对 LeRobot 适配的特别建议

### 建议 1

不要让 LeRobot 直接依赖真实机械臂控制细节。

更稳的层次是：

LeRobot 输出  
-> `lerobot_adapter` 做字段映射  
-> 转成统一 `q + gripper` 协议  
-> 再交给桥接层接收端  
-> 最后复用新版 `move_debug.py` 所代表的控制标准

### 建议 2

第一版 LeRobot 适配优先只对齐：

- 6 关节目标角
- `gripper`

不要在第一版里就把更多复杂动作语义一起塞进桥接协议。

### 建议 3

LeRobot 适配层尽量只做“数据语义转换”，不要直接承担：

- 硬件连接
- 失能
- 急停
- 碰撞保护配置

这些仍应留在公共控制/配置层。

## 风险与边界

### 风险 1

不同上游来源的关节顺序和夹爪语义可能不完全一致。

所以统一协议之前，一定要在适配层里明确：

- 关节索引顺序
- 单位
- 夹爪开合方向

### 风险 2

即使统一成 `q + gripper` 流，夹爪和 6 关节在真实机械臂上的动态响应也不会完全一致。

所以后续要把“同帧下发”理解为控制语义一致，而不是物理执行完全同步。

### 风险 3

如果把协议定义、适配逻辑和真实机械臂控制主循环都堆在一个文件里，后续会很难维护。

所以现在就先拆目录，是值得的。

## 实施步骤

1. 在 `src/piper_socket_bridge/` 下建立：
   - `sim_adapter/`
   - `lerobot_adapter/`
2. 补一个公共协议模块，定义统一 `q + gripper` 帧格式
3. 把仿真侧输出改成面向统一协议
4. 设计 LeRobot `target_pose` 到统一协议的适配层
5. 再实现一个新的真实机械臂接收端，按新版 `move_debug.py` 的控制标准执行

## 预期输出

如果按这个方案推进，后续你会得到：

1. 一个统一的 `piper_socket_bridge` 桥接层
2. 一套统一的 `q + gripper` 目标位协议
3. 两个明确分开的适配方向：
   - 仿真适配
   - LeRobot 适配
4. 一个不再依赖 `socket_old` 旧控制主流程的新实现基线

## 一句话结论

`src/piper_socket_bridge/` 后续应该被建设成“统一 `q + gripper` 目标位流桥接层”，并在其下拆出 `sim_adapter/` 和 `lerobot_adapter/` 两个子目录；其中真实机械臂控制侧一律以当前新版 `scripts/move_debug.py` 的安全控制标准为准，而不是回退参考旧的 socket 测试主流程。
