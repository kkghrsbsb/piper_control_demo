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

# 失能前的安全运动速度，采用 BuiltinJointPositionController 回安全位
SAFE_DISABLE_SPEED = 10
# 失能前回到的安全关节位姿
SAFE_DISABLE_POSITION = [0.0, 0.0, 0.0, 0.02, 0.5, 0.0]



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
):
    """Step toward a joint target while polling a keyboard stop key."""

    target_q = np.array(target_position, dtype=float)
    start_time = time.time()
    dt = 1.0 / speed_hz
    emergency_stop_triggered = False

    with RawTerminal() as term:
        print(f"press '{stop_key}' during motion to stop and exit control.")
        while time.time() - start_time < timeout:
            key = term.get_key()
            if key == stop_key:
                emergency_stop_triggered = True
                print("\nemergency stop requested by keyboard.")
                break

            current_q = np.array(robot.get_joint_positions(), dtype=float)
            error = target_q - current_q
            if np.max(np.abs(error)) <= threshold:
                return True, emergency_stop_triggered

            next_q = current_q + error * step_alpha
            controller.command_joints(next_q.tolist())
            time.sleep(dt)

    return False, emergency_stop_triggered


def confirm_and_shutdown(
        robot,
        *,
        emergency_stop_triggered=False,
        safe_position=SAFE_DISABLE_POSITION,
        safe_speed=SAFE_DISABLE_SPEED,
        threshold=MOVE_THRESHOLD,
        timeout=MOVE_TIMEOUT_SECONDS,
):
    """Ask whether to move to a safe pose and disable gripper/arm."""

    if emergency_stop_triggered:
        disable_prompt = "Motion interrupted by emergency stop. Disable arm at safe position now? [y/N]: "
    else:
        disable_prompt = "Move complete. Disable arm at safe position now? [y/N]: "

    disable_confirm = input(disable_prompt).strip().lower()
    if disable_confirm not in {"y", "yes", "Y"}:
        print("skip disabling arm.")
        return False, False, False

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
        return True, True, True

    print("safe position not reached, skip disabling arm.")
    print(f"current joints: {robot.get_joint_positions()}")
    return True, False, False
