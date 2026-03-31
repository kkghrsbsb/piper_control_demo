"""Real-robot state sender for the unified joint-and-gripper stream.

Reads joint positions and gripper state from the physical Piper arm at a fixed
rate and pushes ``PoseStreamFrame`` lines over a TCP connection.
"""

from __future__ import annotations

import socket
import time

from piper_control import piper_interface

from piper_control_demo.config import connect_can
from piper_socket_bridge.protocol import PoseStreamFrame


HOST = "127.0.0.1"
PORT = 15002
STREAM_HZ = 200.0


def connect_receiver(host: str = HOST, port: int = PORT) -> socket.socket:
    """Connect to the sim-side receiver, retrying until it is ready."""

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"[RobotSender] connecting to receiver on {host}:{port} ...")

    while True:
        try:
            client.connect((host, port))
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print("[RobotSender] receiver connected.")
            return client
        except ConnectionRefusedError:
            time.sleep(0.2)


def read_robot_frame(
    robot: piper_interface.PiperInterface,
    *,
    timestamp: float,
) -> PoseStreamFrame:
    """Snapshot the real robot state into a stream frame."""

    joints = robot.get_joint_positions()
    gripper_pos, _gripper_effort = robot.get_gripper_state()
    return PoseStreamFrame(t=timestamp, q=joints, gripper=gripper_pos)


def run_robot_sender(host: str = HOST, port: int = PORT) -> None:
    """Connect to the real arm and stream its state to *host*:*port* at 200 Hz.

    The function blocks until the socket peer disconnects or the process is
    interrupted.
    """

    ports = connect_can()

    robot = piper_interface.PiperInterface(can_port=ports[0])
    robot.set_installation_pos(piper_interface.ArmInstallationPos.UPRIGHT)

    # Let the CAN bus settle so the first few reads are valid.
    time.sleep(0.3)
    robot.show_status()
    time.sleep(2.0)

    client = connect_receiver(host=host, port=port)

    dt = 1.0 / STREAM_HZ
    start_time = time.perf_counter()
    frame_count = 0

    try:
        while True:
            frame = read_robot_frame(
                robot,
                timestamp=time.perf_counter() - start_time,
            )
            client.sendall(frame.to_json_line())

            frame_count += 1
            target_time = start_time + frame_count * dt
            remaining = target_time - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
    except (BrokenPipeError, ConnectionResetError):
        print("[RobotSender] receiver disconnected.")
    except KeyboardInterrupt:
        print("\n[RobotSender] interrupted.")
    finally:
        client.close()
