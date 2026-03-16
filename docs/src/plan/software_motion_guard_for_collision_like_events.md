# 程序层运动异常保护方案

## 功能目标

在现有底层硬件碰撞保护之外，再增加一层“程序层运动异常保护”。

这层保护不依赖底层 `set_collision_protection(...)` 是否触发，而是通过脚本控制循环里能读到的状态，尽早发现“关节目标持续下发但机械臂明显没有正常接近目标”的异常情况，并主动停止继续下发运动命令。

## 当前动机

你现在已经确认了两件事：

1. 底层库确实支持真实机械臂的碰撞保护等级设置
2. 但官方 CLI 过于轻量，现场鲁棒性一般，而且底层碰撞保护本身也不一定覆盖所有“运动明显异常但还没进入硬件碰撞状态”的情况

因此，增加一层程序级保护是有意义的，尤其适合用于：

- 小范围调试动作
- 人工实验阶段
- 需要及时发现“关节没往目标靠近”的异常

## 这层保护要解决什么问题

建议优先不要把它叫成“新的碰撞保护”，而是更准确地叫：

- 程序层运动异常保护
- 或软件层运动守护

因为它本质上检测的是：

- 目标误差长期不下降
- 运动卡住
- 下发命令后关节响应异常
- 可能发生了阻挡、卡滞、未释放、模式不对或其他异常

它并不能直接证明“已经发生物理碰撞”，只能说明“运动过程不正常，应该及时停下”。

## 拟议设计

建议把这部分能力抽到 [`src/piper_control_demo/control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/control.py)，因为它与当前已存在的这些公共能力属于同一层职责：

- `move_to_position_with_keyboard_stop(...)`
- 公共软件层急停
- 公共收尾失能流程

也就是说，底层硬件参数配置继续放在 [`config.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/config.py)，而“运动中如何守护和中止”继续放在 `control.py` 更合适。

## 第一版建议的检测信号

### 1. 目标误差长期不下降

每次循环已经能拿到：

- `current_q`
- `target_q`
- `error = target_q - current_q`

第一版最实用的守护规则可以是：

- 如果连续若干个控制周期里，最大关节误差几乎没有下降
- 或下降幅度小于某个很小阈值
- 就判定为“运动进展异常”

这很适合检测：

- 被轻微阻挡
- 关节没有按预期响应
- 运动模式不对
- 设备处在某种非正常状态但还没直接报错

### 2. 关节速度长期接近零，但目标误差仍然很大

如果后续想再增强一层，可以结合：

- `robot.get_joint_velocities()`

做一个更强的条件：

- 误差仍然明显大
- 但关节速度长期接近 0

这通常意味着“命令在发，但实际没动起来”。

### 3. 设备状态直接进入异常

后续还可以接入：

- `robot.arm_status`

如果直接变成：

- `COLLISION`
- `EMERGENCY_STOP`
- `JOINT_STATUS_ABNORMAL`
- `JOINT_COMMUNICATION_EXCEPTION`

就立即停止控制循环。

这一条很值得做，但为了第一版收敛，我建议可以先把“误差不收敛检测”做出来，再决定要不要把状态枚举联动一起并入。

## 第一版建议规则

为了保持简单可控，第一版我建议只做这套规则：

1. 进入关节分步控制循环后，持续计算最大关节误差
2. 记录最近一小段窗口内的误差变化
3. 如果连续 `N` 次循环里误差下降不到 `min_error_drop`
4. 且当前最大误差仍然大于 `stuck_error_threshold`
5. 就判定为“运动卡住/异常”，停止继续下发命令

这样第一版不需要额外引入复杂状态机，也容易调试。

## 建议新增的返回语义

当前 `move_to_position_with_keyboard_stop(...)` 返回的是：

- `success`
- `emergency_stop_triggered`

如果要接入程序层异常保护，建议后续升级为具名结果，而不是继续塞布尔值。

例如可以设计：

- `motion_completed`
- `keyboard_stop_triggered`
- `timeout_triggered`
- `motion_guard_triggered`

这样调用方能明确知道：

- 是正常到位
- 还是人工按 `q`
- 还是超时
- 还是程序层异常保护触发

## 可能影响的文件

- [`src/piper_control_demo/control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/control.py)
- [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py)
- [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md)

如果后续真的做成公共标准，也可能需要同步更新：

- [`AGENTS.md`](/home/xinger/MyWork/piper_control_demo/AGENTS.md)

## 风险与边界

### 风险 1

程序层异常保护不能代替硬件急停，也不能代替底层碰撞保护。

它只是“脚本检测到可疑运动后尽快停止继续下发新目标位”。

### 风险 2

阈值太紧会误报。

例如：

- 本来动作就很慢
- 某些关节接近目标时收敛速度自然变小
- 反馈有抖动

都可能让“误差下降不足”被误判成异常。

### 风险 3

阈值太松又会漏报。

所以这类保护参数需要先用保守默认值，再通过实机逐步标定。

## 实施建议

建议分两步做，而不是一步塞太多判断：

### 第一步

先在 `control.py` 的分步运动循环里增加“误差收敛监测”。

### 第二步

如果第一步稳定，再考虑把：

- `robot.arm_status`
- `robot.get_joint_velocities()`

一起接入，做成更完整的程序层运动守护。

## 预期输出

如果按这个方案实现，最终效果会是：

1. `move_to_position_with_keyboard_stop(...)` 在原有键盘急停基础上，再具备一层程序级异常中止能力
2. 当关节长期不接近目标时，脚本会主动停下，不再持续发命令
3. `move_debug.py` 可以把这种中止原因打印清楚，提醒操作者人工检查
4. 这套能力可复用于后续所有基于 `BuiltinJointPositionController` 的真实机械臂控制脚本

## 一句话结论

这个方向是可行的，而且值得做；但最稳妥的落法不是“再造一套硬件碰撞保护”，而是在现有公共控制模块里增加“程序层运动异常守护”，先从“误差长期不下降就停”这条最直接的规则开始。
