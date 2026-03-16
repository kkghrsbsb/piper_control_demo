"""Robot-side realtime follow loop for the unified joint-and-gripper stream."""

from __future__ import annotations

import select
import socket
import time

from piper_control import piper_control, piper_interface
from piper_control_demo.config import (
    DEFAULT_COLLISION_PROTECTION_LEVELS,
    configure_collision_protection,
    connect_can,
    ensure_arm_and_gripper_enabled,
)
from piper_control_demo.control import RawTerminal, confirm_and_shutdown
from piper_socket_bridge.protocol import PoseStreamFrame


HOST = "127.0.0.1"
PORT = 15001
ZERO_Q = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
ZERO_THRESHOLD = 0.01
GRIPPER_ZERO_THRESHOLD = 0.005
ZERO_CHECK_FRAMES = 5
PRINT_HZ = 20.0
SOCKET_POLL_TIMEOUT = 0.01
JOINT_SAFE_SPEED = 10
GRIPPER_EFFORT_NOW = 1.0


def frame_near_zero(frame: PoseStreamFrame) -> bool:
    """Check whether the incoming frame is still at the agreed startup zero pose."""

    joints_near_zero = all(abs(value) <= ZERO_THRESHOLD for value in frame.q)
    gripper_near_zero = abs(frame.gripper) <= GRIPPER_ZERO_THRESHOLD
    return joints_near_zero and gripper_near_zero


def receive_and_follow_stream(
        robot: piper_interface.PiperInterface,
        controller: piper_control.BuiltinJointPositionController,
        host: str = HOST,
        port: int = PORT,
) -> tuple[int, bool, bool]:
    """Receive the realtime stream and apply joints plus gripper in the same loop."""

    processed_frames = 0
    zero_confirmed = False
    stop_requested = False
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
                    stop_requested = True
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

                    frame = PoseStreamFrame.from_json_line(line)

                    if not zero_confirmed:
                        if frame_near_zero(frame):
                            near_zero_count += 1
                            if near_zero_count >= ZERO_CHECK_FRAMES:
                                zero_confirmed = True
                                print(
                                    "sender is at zero position, realtime follow started."
                                )
                        else:
                            near_zero_count = 0
                            if not warned_not_zero:
                                print(
                                    "sender is not at zero position yet, "
                                    "please return sender to zero."
                                )
                                warned_not_zero = True
                        continue

                    controller.command_joints(frame.q)
                    robot.command_gripper(frame.gripper, GRIPPER_EFFORT_NOW)
                    processed_frames += 1

                    now = time.perf_counter()
                    if now >= next_print_time:
                        current_q = robot.get_joint_positions()
                        current_gripper, _gripper_effort = robot.get_gripper_state()
                        print(
                            PoseStreamFrame(
                                t=0.0,
                                q=current_q,
                                gripper=current_gripper,
                            ).to_json_line().decode("utf-8").strip()
                        )
                        next_print_time = now + 1.0 / PRINT_HZ

    return processed_frames, zero_confirmed, stop_requested


def run_socket_realtime_follow(host: str = HOST, port: int = PORT) -> None:
    """Connect to the real robot, return to zero, then follow the incoming stream."""

    ports = connect_can()

    input("WARNING: the robot will move. Press Enter to continue...")

    robot = piper_interface.PiperInterface(can_port=ports[0])
    robot.set_installation_pos(piper_interface.ArmInstallationPos.UPRIGHT)

    ensure_arm_and_gripper_enabled(robot)
    configure_collision_protection(robot, DEFAULT_COLLISION_PROTECTION_LEVELS)
    robot.show_status()

    stop_requested = False
    reached_zero_position = False

    with piper_control.BuiltinJointPositionController(
            robot,
            rest_position=None,
    ) as controller:
        robot.set_arm_mode(speed=JOINT_SAFE_SPEED)
        print(f"current joints: {robot.get_joint_positions()}")

        print(f"moving to zero position: {ZERO_Q}")
        reached_zero_position = controller.move_to_position(
            ZERO_Q,
            threshold=ZERO_THRESHOLD,
            timeout=8.0,
        )
        print(f"reached zero position: {reached_zero_position}")

        if not reached_zero_position:
            print("zero position not reached, skip realtime follow test.")
            return

        processed_frames, zero_confirmed, stop_requested = receive_and_follow_stream(
            robot,
            controller,
            host=host,
            port=port,
        )
        print(f"realtime follow finished, processed frames: {processed_frames}")
        if not zero_confirmed:
            print("sender never reached zero confirmation; follow mode did not start.")

        current_gripper, _gripper_effort = robot.get_gripper_state()
        print(
            f"current state: q={robot.get_joint_positions()}, "
            f"gripper={current_gripper}"
        )

    confirm_and_shutdown(
        robot,
        emergency_stop_triggered=stop_requested,
    )
