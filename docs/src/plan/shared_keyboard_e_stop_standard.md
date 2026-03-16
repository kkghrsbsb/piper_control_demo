# 公共软件层急停标准方案

## 目标

把当前只存在于 [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py) 中的“按 `q` 做软件层急停”能力，抽取到 [`src/piper_control_demo`](/home/xinger/MyWork/piper_control_demo/src/piper_control_demo) 作为公共模块。

目标不是只让 `move_debug.py` 能用，而是建立一个可复用的项目标准：

- 以后凡是存在

```python
with piper_control.BuiltinJointPositionController(...)
```

这类真实机械臂控制上下文的脚本，都应默认考虑接入同一套软件层急停能力。

同时，这条“默认接入公共软件层急停”的标准，也要写进项目文档。

## 当前现状

目前软件层急停只存在于：

- [`scripts/move_debug.py`](/home/xinger/MyWork/piper_control_demo/scripts/move_debug.py)

当前实现包含两部分：

1. `RawTerminal`
   - 用于非阻塞读取键盘单键
2. `move_to_position_with_keyboard_stop(...)`
   - 用于分步下发关节目标
   - 在控制循环中轮询键盘
   - 按下 `q` 时停止继续下发目标位

这说明我们已经有一版可工作的脚本级实现，但它现在的问题也很明显：

- 逻辑只在 `move_debug.py` 里
- 不能被其它脚本直接复用
- 如果以后另一个脚本也要加急停，很容易复制粘贴
- 一旦后续要改按键、阈值或提示语，就会多处漂移

## 功能方案判断

你现在提出把它上升为公共模块和安全标准，这个判断是合理的，而且是必要的。

原因很直接：

- 真实机械臂控制脚本中，软件层急停应当是默认能力，而不是个别脚本的临时技巧
- 一旦形成项目标准，后续新脚本就更不容易遗漏这一层安全保护
- 急停逻辑集中在公共模块里，后续维护成本更低

## 这次方案的核心原则

这次不是单纯“把两个函数搬文件”。

应该明确成下面三层：

1. 公共工具层
   - 放在 `src/piper_control_demo/`
   - 提供统一的软件层急停输入与分步控制能力
2. 业务脚本层
   - 例如 `move_debug.py`
   - 只负责组装目标位、夹爪命令、后续人工确认
3. 文档标准层
   - 在文档中明确：涉及 `BuiltinJointPositionController` 的真实机械臂控制脚本，应默认考虑接入这套软件层急停能力

## 建议放在哪个模块

我建议不要把这套逻辑继续放在 `config.py`。

原因：

- `config.py` 当前更偏连接、CAN、使能状态探测
- 软件层急停和分步控制，更接近“控制辅助工具”

更合适的放置方式有两个：

### 方案 A：新增控制辅助模块

例如新增：

- `src/piper_control_demo/core/control.py`

或：

- `src/piper_control_demo/core/safety.py`

我更推荐：

- `src/piper_control_demo/core/control.py`

因为这里不只是安全输入，还包含一个“分步位置控制循环”。

### 方案 B：放进新的顶层工具模块

例如：

- `src/piper_control_demo/control.py`

也可以，但从你当前的项目结构看，放在 `core/` 下更自然。

## 公共模块应该抽出哪些能力

我建议至少抽出下面两块：

### 1. 非阻塞键盘读取

例如：

- `RawTerminal`

职责：

- 切换终端到 cbreak/raw 模式
- 非阻塞读取单键
- 返回按键内容

这是一个通用能力，不仅 `move_debug.py`，以后任何交互式控制脚本都可能用到。

### 2. 可中断的分步关节移动

例如一个函数：

- `move_to_position_with_keyboard_stop(...)`

建议职责：

- 接收 `robot`
- 接收 `controller`
- 接收 `target_position`
- 在固定频率循环中分步下发关节目标
- 每轮检查是否按下 `q`
- 返回：
  - 是否到达目标
  - 是否触发急停

这个函数才是“软件层急停控制标准”的核心。

## 公共函数的建议接口

为了让后续脚本更容易复用，建议接口尽量通用。

例如：

```python
success, emergency_stop_triggered = move_to_position_with_keyboard_stop(
    robot=robot,
    controller=controller,
    target_position=reach_position,
    speed_hz=...,
    threshold=...,
    timeout=...,
    stop_key="q",
    step_alpha=...,
)
```

这样好处是：

- 以后不同脚本可以共用一套函数
- 但仍可按场景调整频率、超时、步进比例
- 如果以后要把 `q` 改成别的键，不需要改所有脚本内部逻辑

## move_debug.py 后续应该如何改造

一旦公共模块存在，`move_debug.py` 里应该尽量只保留业务逻辑，不再自己定义 `RawTerminal` 和控制循环。

建议后续结构变成：

1. 导入公共急停工具
2. 在 `with BuiltinJointPositionController(...)` 内调用公共函数
3. 根据返回值判断：
   - 正常到位
   - 超时
   - 急停触发
4. 再决定是否跳过夹爪动作
5. 最后进入人工确认流程

这样 `move_debug.py` 会明显更清晰，也更符合“公共安全能力 + 具体业务流程”分层。

## 以后哪些地方应默认复用

你提到“以后都要注意和复用”，这一点我建议在文档里明确成标准。

建议标准表述为：

- 任何真实机械臂控制脚本，如果在 `with piper_control.BuiltinJointPositionController(...)` 中持续下发关节目标，就应默认评估是否接入公共软件层急停能力。

进一步一点，可以写成更明确的项目习惯：

- 没有特殊理由时，应优先接入公共软件层急停。
- 如果某个脚本暂时不接入，应在文档或代码注释里说明原因。

## 这条标准要写进哪些文档

至少建议同步到两处：

### 1. [`docs/src/README.md`](/home/xinger/MyWork/piper_control_demo/docs/src/README.md)

写成项目级说明，例如：

- `move_debug.py` 已经使用软件层急停
- 后续涉及 `BuiltinJointPositionController` 的真实机械臂控制脚本，应默认复用公共软件层急停能力

### 2. [`README.md`](/home/xinger/MyWork/piper_control_demo/README.md)

写成首页级简短说明，例如：

- 项目正在把软件层急停上升为公共控制标准

如果你后续愿意，这条标准也值得写进：

- `AGENTS.md`

因为它已经属于“项目安全与复用约定”。

## 需要明确的边界

这次上升为“标准”时，必须继续强调：

- 这仍然是软件层急停
- 它的含义是“尽快停止继续下发目标位”
- 它不是硬件级急停
- 不能替代真实现场的急停按钮、断电措施或安全回路

也就是说，文档里要写“默认接入”，但也要同时写清“能力边界”。

## 推荐实现顺序

如果后续开始改代码，建议按下面顺序推进：

1. 在 `src/piper_control_demo/core/` 下新增公共控制辅助模块
2. 把 `RawTerminal` 抽到公共模块
3. 把 `move_to_position_with_keyboard_stop(...)` 抽到公共模块
4. 修改 `scripts/move_debug.py`，改为导入并使用公共实现
5. 验证 `move_debug.py` 行为不变
6. 更新 `docs/src/README.md`
7. 更新 `README.md`
8. 可选：再把这条标准补入 `AGENTS.md`

## 预期输出

确认后，下一步实施应包含：

1. 在 `src/piper_control_demo/` 中新增公共软件层急停辅助模块
2. 将 `move_debug.py` 中的 `RawTerminal` 和可中断分步运动逻辑抽取到公共模块
3. 修改 `scripts/move_debug.py` 以复用公共实现
4. 在文档中明确：涉及 `BuiltinJointPositionController` 的真实机械臂控制脚本，应默认考虑复用这套公共软件层急停能力
