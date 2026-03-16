# move_debug.py 审查记录

## 结论

当前 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 已经完成了几件重要的结构性改进：

- 夹爪使能探测已经抽到 [`src/piper_control_demo/config.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/config.py)
- 软件层键盘急停已经抽到 [`src/piper_control_demo/control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/control.py)
- 收尾失能流程也已经抽到 [`src/piper_control_demo/control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/control.py)

整体方向是对的，代码已经比前几轮更可复用，也更接近项目级标准。

但从“代码更清晰、更标准”的角度看，当前实现还有一些值得继续收敛的点。

## 主要问题

### 1. `TARGET_POSE_7D` 的数据结构与注释不一致

位置：

- [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py):15

现状：

- 注释把它定义为 7 维：
  - `[j1, j2, j3, j4, j5, j6, gripper_pos]`
- 但当前实际值写成了 8 个元素：

```python
TARGET_POSE_7D = [0.2, 0.2, -0.2, 0.3, -0.2, 0.5, 0.08, 0.0]
```

风险：

- 这会直接误导后续维护者
- 当前代码虽然只取 `[:6]` 和 `[6]`，第 8 个元素会被静默忽略
- 这种“数据结构不一致但程序还能跑”的状态最容易埋隐患

建议：

- 立即把 `TARGET_POSE_7D` 收敛成真正的 7 个元素
- 如果确实计划扩展更多维度，应该显式改名并同步更新文档和拆分逻辑

### 2. 运动控制参数在 `move_debug.py` 和 `control.py` 双处定义，职责边界不清

位置：

- [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py):31
- [`src/piper_control_demo/control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/control.py):10

现状：

- `MOVE_CONTROL_HZ`
- `MOVE_TIMEOUT_SECONDS`
- `MOVE_THRESHOLD`
- `MOVE_STEP_ALPHA`

这组参数已经在公共模块 [`control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/control.py) 里定义过一次，但 `move_debug.py` 又重新定义了一份，并在调用时显式传进去。

风险：

- 参数来源分裂
- 后续修改时容易只改一边
- 阅读者不容易判断“哪份才是标准值”

建议：

- 如果这些参数是项目级默认值，就只保留在 [`control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/control.py)
- `move_debug.py` 只在确实需要覆盖默认值时再显式传参
- 如果这些参数是脚本局部调参项，就不应在公共模块里再保留同名默认常量

### 3. `confirm_and_shutdown()` 的返回值语义不够清晰

位置：

- [`src/piper_control_demo/control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/control.py):74

现状：

- 函数返回的是三元组：

```python
return False, False, False
return True, True, True
return True, False, False
```

但调用侧目前完全没有使用这些返回值，也没有显式的命名语义。

风险：

- 后续一旦别的脚本开始复用，很容易忘记三个布尔值分别代表什么
- 接口可读性较弱

建议：

- 至少把返回值写成具名结构，例如 `NamedTuple` / `dataclass`
- 或者如果当前调用方并不需要结果，先返回 `None`
- 若保留三元组，建议在 docstring 中明确写出每一位的含义

### 4. `move_debug.py` 里仍然混杂了“配置常量”“业务流程”“调试输出”，可进一步分段

位置：

- [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py)

现状：

- 当前文件顶部已经整理了常量，这是好的
- 但 `main()` 里仍然顺序串着：
  - 连接
  - 初始化
  - 使能探测
  - 控制执行
  - 夹爪控制
  - 收尾失能

整体可读性还可以，但仍偏长，后续继续加逻辑会变得难维护

建议：

- 继续把 `main()` 切成几个小函数，例如：
  - `setup_robot(...)`
  - `ensure_arm_and_gripper_enabled(...)`
  - `run_joint_and_gripper_motion(...)`
- 这样以后读代码时更容易一眼看出每段职责

## 次要建议

### 1. 注释风格再统一一点

位置：

- [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py)
- [`src/piper_control_demo/control.py`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo/control.py)

建议：

- 现在中英文混合注释是可接受的，但建议统一为“中文为主 + 必要英文术语”
- 一些注释可以更短，例如“重置或失能机械臂关节与夹爪”其实更准确应表述为“必要时 reset_arm，随后 reset_gripper”

### 2. 常量命名可以再更聚焦

例如：

- `GRIPPER_EFFORT_NOW`

这个名字能看懂，但不够标准。更自然的命名可能是：

- `GRIPPER_COMMAND_EFFORT`

或：

- `DEFAULT_GRIPPER_EFFORT`

## 推荐修改顺序

如果后续要继续优化，我建议优先按这个顺序：

1. 先修正 `TARGET_POSE_7D` 的元素数量与注释不一致问题
2. 收敛 `MOVE_*` 参数到底归公共模块还是归脚本局部
3. 改善 `confirm_and_shutdown()` 的返回值接口
4. 再把 `main()` 进一步拆函数

## 总体评价

这份实现已经从“能跑”提升到了“开始有公共标准”的阶段，这是很好的方向。

当前最值得尽快修的是：

- `TARGET_POSE_7D` 的结构一致性
- 参数职责边界

这两点修完以后，代码的稳定性和可维护性都会更好。
