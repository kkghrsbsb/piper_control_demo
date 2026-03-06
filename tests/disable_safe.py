# 请确保机械臂在零位安全
from piper_control import piper_init, piper_interface
from piper_control_demo.config import connect_can, probe_arm_enabled_state


if __name__ == '__main__':
    ports = connect_can()

    robot = piper_interface.PiperInterface(can_port=ports[0])
    robot.set_installation_pos(piper_interface.ArmInstallationPos.UPRIGHT)

    input("WARNING: the robot will be disabled. Press Enter to continue...")
    piper_init.disable_arm(robot)