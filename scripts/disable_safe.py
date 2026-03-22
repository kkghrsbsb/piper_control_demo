# ！如果碰过link5上面的按键，在这个程序启动的时候就会失能！

import time

from piper_control import piper_interface

from piper_control_demo.config import connect_can, ensure_arm_and_gripper_enabled

if __name__ == "__main__":
    ports = connect_can()

    robot = piper_interface.PiperInterface(can_port=ports[0])
    robot.set_installation_pos(piper_interface.ArmInstallationPos.UPRIGHT)

    time.sleep(1)

    ensure_arm_and_gripper_enabled(robot)

    input("WARNING: the robot will be disabled. Press Enter to continue...")
    robot.disable_arm()
    robot.disable_gripper()
