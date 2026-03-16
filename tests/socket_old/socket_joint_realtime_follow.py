# socket 实时关节跟随测试
import json
import select
import socket
import sys
import termios
import time
import tty

from piper_control import (
    piper_control,
    piper_init,
    piper_interface,
)
from piper_control_demo.config import connect_can, probe_arm_enabled_state


HOST = "127.0.0.1"
PORT = 15001
ZERO_POSITION = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
SAFE_DISABLE_POSITION = [0.0, 0.0, 0.0, 0.02, 0.5, 0.0]
ZERO_THRESHOLD = 0.01
ZERO_CHECK_FRAMES = 5
PRINT_HZ = 20.0
SOCKET_POLL_TIMEOUT = 0.01


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


def joints_near_zero(q: list[float], threshold: float = ZERO_THRESHOLD) -> bool:
    return all(abs(value) <= threshold for value in q)


def receive_and_follow_stream(
        robot: piper_interface.PiperInterface,
        controller: piper_control.BuiltinJointPositionController,
        host: str = HOST,
        port: int = PORT,
) -> tuple[int, bool]:
    """接收实时关节流；按 q 键结束跟随。"""

    processed_frames = 0
    zero_confirmed = False
    near_zero_count = 0
    warned_not_zero = False
    next_print_time = time.perf_counter()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        print(f"listening for realtime joint stream on {host}:{port}")

        conn, addr = server.accept()
        conn.settimeout(SOCKET_POLL_TIMEOUT)
        print(f"sender connected from {addr}")

        with conn, RawTerminal() as term:
            print("press 'q' to stop realtime follow and enter disable prompt.")
            buffer = ""

            while True:
                key = term.get_key()
                if key == "q":
                    print("\nmanual stop requested.")
                    break

                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    chunk = b""

                if not chunk:
                    if chunk == b"":
                        readable = select.select([conn], [], [], 0)[0]
                        if readable:
                            print("sender disconnected.")
                            break
                    continue

                buffer += chunk.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    frame = json.loads(line)
                    q = frame.get("q")
                    if not isinstance(q, list) or len(q) != 6:
                        raise ValueError(f"invalid joint frame: {frame}")

                    if not zero_confirmed:
                        if joints_near_zero(q):
                            near_zero_count += 1
                            if near_zero_count >= ZERO_CHECK_FRAMES:
                                zero_confirmed = True
                                print("sender is at zero position, realtime follow started.")
                        else:
                            near_zero_count = 0
                            if not warned_not_zero:
                                print("sender is not at zero position yet, please return sender to zero.")
                                warned_not_zero = True
                        continue

                    controller.command_joints(q)
                    processed_frames += 1

                    now = time.perf_counter()
                    if now >= next_print_time:
                        print(f"current joints: {robot.get_joint_positions()}")
                        next_print_time = now + 1.0 / PRINT_HZ

    return processed_frames, zero_confirmed


def main():
    ports = connect_can()

    input("WARNING: the robot will move. Press Enter to continue...")

    robot = piper_interface.PiperInterface(can_port=ports[0])
    robot.set_installation_pos(piper_interface.ArmInstallationPos.UPRIGHT)

    is_enabled = probe_arm_enabled_state(robot)
    if not is_enabled:
        print("resetting arm")
        piper_init.reset_arm(
            robot,
            arm_controller=piper_interface.ArmController.POSITION_VELOCITY,
            move_mode=piper_interface.MoveMode.JOINT,
        )

    print("resetting gripper")
    piper_init.reset_gripper(robot)
    robot.show_status()

    reached_zero_position = False
    reached_safe_position = False

    with piper_control.BuiltinJointPositionController(
            robot,
            rest_position=None,
    ) as controller:
        robot.set_arm_mode(speed=10)
        print(f"current joints: {robot.get_joint_positions()}")

        print(f"moving to zero position: {ZERO_POSITION}")
        reached_zero_position = controller.move_to_position(
            ZERO_POSITION, threshold=0.01, timeout=8.0
        )
        print(f"reached zero position: {reached_zero_position}")

        if not reached_zero_position:
            print("zero position not reached, skip realtime follow test.")
            return

        processed_frames, zero_confirmed = receive_and_follow_stream(robot, controller)
        print(f"realtime follow finished, processed frames: {processed_frames}")
        if not zero_confirmed:
            print("sender never reached zero confirmation; follow mode did not start.")
        print(f"current joints: {robot.get_joint_positions()}")

    disable_confirm = input(
        "Realtime follow complete. Disable arm at safe position now? [y/N]: "
    ).strip().lower()

    if disable_confirm in {"y", "yes", "Y"}:
        print("finished, disabling arm.")
        print("WARNING: the arm will power off and drop.")

        with piper_control.BuiltinJointPositionController(
                robot,
                rest_position=None,
        ) as controller:
            robot.set_arm_mode(speed=10)
            print(f"moving to safe position before disable: {SAFE_DISABLE_POSITION}")
            reached_safe_position = controller.move_to_position(
                SAFE_DISABLE_POSITION, threshold=0.01, timeout=12.0
            )
            print(f"reached safe position: {reached_safe_position}")

        if reached_safe_position:
            time.sleep(1)
            piper_init.disable_arm(robot)
        else:
            print("safe position not reached, skip disabling arm.")
            print(f"current joints: {robot.get_joint_positions()}")
    else:
        print("skip disabling arm.")


if __name__ == "__main__":
    main()
