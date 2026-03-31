# scripts/

日常操作脚本，直接对真实机械臂执行操作。所有 Python 脚本通过 `python -m scripts.<文件名>` 运行（需在项目根目录下）。

## 脚本列表

| 文件 | 说明 | 是否控制真实臂 |
|------|------|:-:|
| `show_status.py` | 以 200Hz 读取并打印机械臂关节位置和夹爪状态（JSON 格式），不发送任何控制命令。用于观测和调试。 | 只读 |
| `move_debug.py` | 运动调试脚本。使能机械臂 → 设置碰撞保护 → 移动到指定位姿（支持键盘 `q` 急停 + 软件运动守护） → 控制夹爪 → 安全失能。修改 `TARGET_Q` 和 `TARGET_GRIPPER` 变量来指定目标位姿。 | **是** |
| `disable_safe.py` | 安全失能脚本。使能臂和夹爪后立即失能，用于紧急或手动复位场景。 | **是** |
| `old_move_debug.py` | 旧版运动调试脚本（无键盘急停、无软件运动守护、无共享安全流程），仅供参考对照，不推荐使用。 | **是** |
| `piper-generate-udev-rule` | Bash 脚本。为 CAN 适配器生成 udev 规则，实现即插即用（自动配置 bitrate + 可选重命名）。需 `sudo` 执行。 | 否 |

## 使用示例

### 查看机械臂状态

```bash
python -m scripts.show_status
```

输出示例（每行一个 JSON，200Hz）：

```json
{"t": 0.005, "q": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "gripper": 0.0}
```

### 运动调试

编辑 `move_debug.py` 中的目标位姿后运行：

```bash
python -m scripts.move_debug
```

运动过程中按 `q` 键可触发软件急停。

### 安全失能

```bash
python -m scripts.disable_safe
```

### 生成 CAN udev 规则

```bash
sudo ./scripts/piper-generate-udev-rule -i can0 -b 1000000
```

一次执行后 CAN 适配器即插即用，无需每次手动初始化。

> 来源: [piper_control/scripts/piper-generate-udev-rule](https://github.com/Reimagine-Robotics/piper_control/blob/main/scripts/piper-generate-udev-rule)
