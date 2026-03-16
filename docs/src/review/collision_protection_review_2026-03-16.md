# 碰撞保护实现审查记录

## 现象

当前在 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 中，代码会先执行：

```python
robot.set_collision_protection(COLLISION_PROTECTION_LEVELS)
print("collision protection levels:", robot.get_collision_protection())
```

但实际终端输出仍然是：

```text
collision protection levels: [0, 0, 0, 0, 0, 0]
```

也就是说，从脚本视角看，碰撞保护“似乎没有生效”。

## 已核对的相关实现

### 调用侧

位置：

- [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py)

当前流程是：

1. 创建 `PiperInterface`
2. 设置安装方向
3. 立刻调用 `set_collision_protection(...)`
4. 立刻调用 `get_collision_protection()`
5. 然后才进入 `ensure_arm_and_gripper_enabled(robot)`

### 写入实现

`PiperInterface.set_collision_protection(...)` 当前实现是：

```python
self.piper.CrashProtectionConfig(
    levels[0],
    levels[1],
    levels[2],
    levels[3],
    levels[4],
    levels[5],
)
```

这说明脚本确实向底层发送了碰撞保护配置命令。

### 读取实现

`PiperInterface.get_collision_protection()` 当前实现是：

```python
self.piper.ArmParamEnquiryAndConfig(0x02, 0x00, 0x00, 0x00, 0x03)
feedback = self.piper.GetCrashProtectionLevelFeedback()
```

然后再从反馈消息中取出 6 个关节的等级。

## 初步判断

从当前代码链路看，问题不太像“完全没有调用设置接口”，更像是：

1. 写入和读取不是同一条本地状态链路
2. 写完立即读，设备侧反馈还没有刷新
3. 当前设置时机可能过早，设备还没进入更稳定的可控状态

## 目前不建议直接下结论为“碰撞保护没有实现”

更准确的说法应是：

- 当前脚本里的“写后立即回读校验”没有得到预期结果

这和“功能完全没实现”是两件事。

## 当前实现的主要问题

### 1. 把“写入成功”和“立即可回读”混成了一件事

当前脚本默认假设：

```python
set_collision_protection(...)
get_collision_protection()
```

应当立刻返回刚设置的值。

但从依赖实现看，这个假设并不稳。

### 2. 没有给反馈刷新留时间

目前写完就读，没有：

- 等待
- 重试
- 多次采样

所以当前脚本无法区分：

- 是真的没设置成功
- 还是反馈尚未更新

### 3. 设置时机可能不合理

当前设置发生在 `ensure_arm_and_gripper_enabled(robot)` 之前。

从工程经验看，更稳妥的顺序通常是：

1. 先让设备进入稳定、可控状态
2. 再写控制参数
3. 再查询确认

## 修改建议

### 建议 1

不要把当前 `[0, 0, 0, 0, 0, 0]` 直接解释成“碰撞保护完全不存在”。

### 建议 2

后续如果要继续改，优先尝试把碰撞保护设置移动到：

- `ensure_arm_and_gripper_enabled(robot)` 之后

### 建议 3

把单次立即回读改成“带等待和重试”的验证逻辑，类似：

- 写入
- 等待
- 多次查询
- 判断是否至少有一次反馈匹配目标值

### 建议 4

输出信息不要只打印当前反馈列表，最好同时打印：

- 目标碰撞保护等级
- 实际采样结果
- 是否匹配

## 一句话结论

当前更像是“碰撞保护的即时回读验证方式不可靠”，而不是已经证明“碰撞保护完全没实现”。
