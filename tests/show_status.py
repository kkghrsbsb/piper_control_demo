from piper_control import piper_interface
import time

from piper_control_demo.config import connect_can

if __name__ == "__main__":
    ports = connect_can()

    robot = piper_interface.PiperInterface(can_port=ports[0])
    robot.set_installation_pos(piper_interface.ArmInstallationPos.UPRIGHT)

    # wait for the robot to settle
    time.sleep(0.3)

    robot.show_status()
    while True:
        time.sleep(1)
        print(f"current joints: {robot.get_joint_positions()}")