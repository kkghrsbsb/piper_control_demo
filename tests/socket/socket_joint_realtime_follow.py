"""Real robot receiver entry point for the unified q+gripper stream."""

from piper_socket_bridge.receiver.robot_follow import run_socket_realtime_follow


if __name__ == "__main__":
    run_socket_realtime_follow()
