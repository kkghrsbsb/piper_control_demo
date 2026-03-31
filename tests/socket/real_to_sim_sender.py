"""Entry point: stream the real Piper arm state to the PyBullet receiver."""

from piper_socket_bridge.robot_sender import run_robot_sender


if __name__ == "__main__":
    run_robot_sender()
