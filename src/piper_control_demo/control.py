from dataclasses import dataclass
import select
import sys
import termios
import time
import tty

import numpy as np
from piper_control import piper_control, piper_init

# 控制循环频率
MOVE_CONTROL_HZ = 200.0
# 单次运动最大允许时长，超过时自动停止
MOVE_TIMEOUT_SECONDS = 12.0
# 到位判定阈值
MOVE_THRESHOLD = 0.01
# 每次循环向目标推进的误差比例
MOVE_STEP_ALPHA = 0.2
# 连续多少次误差几乎不下降，就判定为运动进展异常
MOTION_GUARD_STUCK_CYCLES = 20
# 单次循环里，最大误差至少下降多少才算“有进展”
MOTION_GUARD_MIN_ERROR_DROP = 5e-4
# 只有当前误差仍明显大于该阈值时，才会触发“卡住”判定
MOTION_GUARD_STUCK_ERROR_THRESHOLD = 0.05

# 失能前的安全运动速度，采用 BuiltinJointPositionController 回安全位
SAFE_DISABLE_SPEED = 10
# 失能前回到的安全关节位姿
SAFE_DISABLE_POSITION = [0.0, 0.0, 0.0, 0.02, 0.5, 0.0]


@dataclass(frozen=True)
class ShutdownResult:
    disable_requested: bool
    safe_position_reached: bool
    shutdown_completed: bool


@dataclass(frozen=True)
class MotionResult:
    motion_completed: bool
    keyboard_stop_triggered: bool
    timeout_triggered: bool
    motion_guard_triggered: bool



class RawTerminal:
    """Context manager for non-blocking single-key input."""

    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.old_settings = None

    def __enter__(self):
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, *args):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def get_key(self) -> str | None:
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None


def move_to_position_with_keyboard_stop(
        robot,
        controller,
        target_position,
        *,
        speed_hz=MOVE_CONTROL_HZ,
        threshold=MOVE_THRESHOLD,
        timeout=MOVE_TIMEOUT_SECONDS,
        stop_key="q",
        step_alpha=MOVE_STEP_ALPHA,
        stuck_cycles=MOTION_GUARD_STUCK_CYCLES,
        min_error_drop=MOTION_GUARD_MIN_ERROR_DROP,
        stuck_error_threshold=MOTION_GUARD_STUCK_ERROR_THRESHOLD,
):
    """分步逼近目标关节位，并同时做键盘急停与运动异常守护。

    这层守护的目标不是替代底层硬件碰撞保护，而是在脚本控制循环里
    及时发现“目标误差长期不下降、机械臂疑似卡住或被阻挡”的情况，
    从而尽快停止继续下发新的关节目标位。

    Returns:
        MotionResult:
            motion_completed: 是否成功到达目标位
            keyboard_stop_triggered: 是否由按键急停中断
            timeout_triggered: 是否因超时中断
            motion_guard_triggered: 是否因程序层运动守护触发中断
    """

    target_q = np.array(target_position, dtype=float)
    start_time = time.time()
    dt = 1.0 / speed_hz
    keyboard_stop_triggered = False
    timeout_triggered = False
    motion_guard_triggered = False
    stagnant_cycles = 0
    previous_max_error = None

    with RawTerminal() as term:
        print(f"press '{stop_key}' during motion to stop and exit control.")
        while time.time() - start_time < timeout:
            key = term.get_key()
            if key == stop_key:
                keyboard_stop_triggered = True
                print("\nemergency stop requested by keyboard.")
                break

            current_q = np.array(robot.get_joint_positions(), dtype=float)
            error = target_q - current_q
            max_error = float(np.max(np.abs(error)))
            if max_error <= threshold:
                return MotionResult(
                    motion_completed=True,
                    keyboard_stop_triggered=False,
                    timeout_triggered=False,
                    motion_guard_triggered=False,
                )

            # 如果当前误差还明显偏大，但连续多个周期几乎没有下降，
            # 说明机械臂可能被阻挡、卡住，或当前运动状态异常。
            if previous_max_error is not None:
                error_drop = previous_max_error - max_error
                if (
                        max_error >= stuck_error_threshold
                        and error_drop < min_error_drop
                ):
                    stagnant_cycles += 1
                else:
                    stagnant_cycles = 0

                if stagnant_cycles >= stuck_cycles:
                    motion_guard_triggered = True
                    print(
                        "\nmotion guard triggered: joint error is not "
                        "decreasing as expected, stop sending new commands."
                    )
                    print(
                        "motion guard details:"
                        f" max_error={max_error:.6f},"
                        f" previous_max_error={previous_max_error:.6f},"
                        f" stagnant_cycles={stagnant_cycles}"
                    )
                    break

            previous_max_error = max_error

            next_q = current_q + error * step_alpha
            controller.command_joints(next_q.tolist())
            time.sleep(dt)

    if not keyboard_stop_triggered and not motion_guard_triggered:
        timeout_triggered = True

    return MotionResult(
        motion_completed=False,
        keyboard_stop_triggered=keyboard_stop_triggered,
        timeout_triggered=timeout_triggered,
        motion_guard_triggered=motion_guard_triggered,
    )


def confirm_and_shutdown(
        robot,
        *,
        emergency_stop_triggered=False,
        safe_position=SAFE_DISABLE_POSITION,
        safe_speed=SAFE_DISABLE_SPEED,
        threshold=MOVE_THRESHOLD,
        timeout=MOVE_TIMEOUT_SECONDS,
):
    """Ask whether to move to a safe pose and disable gripper/arm.

    Returns:
        ShutdownResult:
            disable_requested: 用户是否选择进入失能流程
            safe_position_reached: 是否成功到达安全位
            shutdown_completed: 是否最终完成夹爪与机械臂失能
    """

    if emergency_stop_triggered:
        disable_prompt = "Motion interrupted by emergency stop. Disable arm at safe position now? [y/N]: "
    else:
        disable_prompt = "Move complete. Disable arm at safe position now? [y/N]: "

    disable_confirm = input(disable_prompt).strip().lower()
    if disable_confirm not in {"y", "yes", "Y"}:
        print("skip disabling arm.")
        return ShutdownResult(
            disable_requested=False,
            safe_position_reached=False,
            shutdown_completed=False,
        )

    print("finished, disabling arm.")
    print("WARNING: the arm will power off and drop.")

    reached_safe_position = False
    if safe_position is not None:
        with piper_control.BuiltinJointPositionController(
                robot,
                rest_position=None,
        ) as controller:
            robot.set_arm_mode(speed=safe_speed)
            print(f"moving to safe position before disable: {safe_position}")
            reached_safe_position = controller.move_to_position(
                safe_position,
                threshold=threshold,
                timeout=timeout,
            )
            print(f"reached safe position: {reached_safe_position}")
    else:
        reached_safe_position = True

    if reached_safe_position:
        time.sleep(1)
        robot.disable_gripper()
        piper_init.disable_arm(robot)
        return ShutdownResult(
            disable_requested=True,
            safe_position_reached=True,
            shutdown_completed=True,
        )

    print("safe position not reached, skip disabling arm.")
    print(f"current joints: {robot.get_joint_positions()}")
    return ShutdownResult(
        disable_requested=True,
        safe_position_reached=False,
        shutdown_completed=False,
    )
