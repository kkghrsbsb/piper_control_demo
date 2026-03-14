# socket 关节流跟随测试
import json
import socket
import threading
import time

from piper_control import (
    piper_control,
    piper_init,
    piper_interface,
)
from piper_control_demo.config import connect_can, probe_arm_enabled_state

HOST = "127.0.0.1"
PORT = 15000
STREAM_HZ = 200.0
STREAM_DURATION = 2.0
ZERO_POSITION = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
TARGET_POSITION = [0.2, 0.2, -0.2, 0.3, -0.2, 0.5]
SAFE_DISABLE_POSITION = [0.0, 0.0, 0.0, 0.02, 0.5, 0.0]


def generate_interpolated_q(alpha: float) -> list[float]:
    return [
        (1.0 - alpha) * start + alpha * target
        for start, target in zip(ZERO_POSITION, TARGET_POSITION)
    ]


def simulate_joint_stream(
        start_event: threading.Event,
        stop_event: threading.Event,
        host: str = HOST,
        port: int = PORT,
        hz: float = STREAM_HZ,
        duration: float = STREAM_DURATION,
) -> None:
    """等待主线程就绪后，向本机 socket 发送 200Hz 关节角数据流。"""

    start_event.wait()
    if stop_event.is_set():
        return

    total_frames = max(2, int(duration * hz))
    frame_interval = 1.0 / hz

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        for _ in range(100):
            try:
                client.connect((host, port))
                break
            except ConnectionRefusedError:
                if stop_event.is_set():
                    return
                time.sleep(0.01)
        else:
            raise RuntimeError("socket sender could not connect to receiver")

        start_time = time.perf_counter()
        for frame_idx in range(total_frames):
            if stop_event.is_set():
                break

            alpha = frame_idx / (total_frames - 1)
            payload = {
                "t": frame_idx / hz,
                "q": generate_interpolated_q(alpha),
            }
            client.sendall((json.dumps(payload) + "\n").encode("utf-8"))

            target_time = start_time + (frame_idx + 1) * frame_interval
            remaining = target_time - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)


def receive_and_follow_stream(
        controller: piper_control.BuiltinJointPositionController,
        host: str = HOST,
        port: int = PORT,
) -> int:
    """接收 socket JSON 行流，并逐帧下发关节角命令。"""

    processed_frames = 0

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        print(f"listening for joint stream on {host}:{port}")

        conn, addr = server.accept()
        with conn:
            print(f"sender connected from {addr}")
            reader = conn.makefile("r", encoding="utf-8")
            for line in reader:
                line = line.strip()
                if not line:
                    continue

                frame = json.loads(line)
                q = frame.get("q")
                if not isinstance(q, list) or len(q) != 6:
                    raise ValueError(f"invalid joint frame: {frame}")

                controller.command_joints(q)
                processed_frames += 1

    return processed_frames


def main():
    # 连接机械臂并失能/重置机械臂
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

    start_event = threading.Event()
    stop_event = threading.Event()
    sender_thread = threading.Thread(
        target=simulate_joint_stream,
        args=(start_event, stop_event),
        daemon=True,
    )

    reached_zero_position = False
    reached_safe_position = False

    try:
        # 采用 Builtin 关节位控制器上下文
        with piper_control.BuiltinJointPositionController(
                robot,
                rest_position=None,
        ) as controller:
            # ⚠ (ModeCtrl speed=5) for safer motion.
            robot.set_arm_mode(speed=5)
            print(f"current joints: {robot.get_joint_positions()}")

            print(f"moving to zero position: {ZERO_POSITION}")
            reached_zero_position = controller.move_to_position(
                ZERO_POSITION, threshold=0.01, timeout=8.0
            )
            print(f"reached zero position: {reached_zero_position}")

            if not reached_zero_position:
                print("zero position not reached, skip socket stream test.")
                return

            sender_thread.start()
            start_event.set()

            processed_frames = receive_and_follow_stream(controller)
            print(f"socket stream finished, processed frames: {processed_frames}")
            print(f"current joints: {robot.get_joint_positions()}")
    finally:
        stop_event.set()
        if sender_thread.is_alive():
            sender_thread.join(timeout=1.0)

    # 结束后是否失能（默认不失能，避免误操作）
    disable_confirm = input(
        "Move complete. Disable arm at safe position now? [y/N]: "
    ).strip().lower()

    if disable_confirm in {"y", "yes", "Y"}:
        print("finished, disabling arm.")
        print("WARNING: the arm will power off and drop.")

        with piper_control.BuiltinJointPositionController(
                robot,
                rest_position=None,
        ) as controller:
            robot.set_arm_mode(speed=5)
            print(f"moving to safe position before disable: {SAFE_DISABLE_POSITION}")
            reached_safe_position = controller.move_to_position(
                SAFE_DISABLE_POSITION, threshold=0.01, timeout=8.0
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
