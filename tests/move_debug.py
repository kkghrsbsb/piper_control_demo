# 运动调试
import time
from piper_control import (
    piper_control,
    piper_init,
    piper_interface,
)
from piper_control_demo.config import connect_can, probe_arm_enabled_state

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

    # 采用Buildin关节位控制器上下文
    with piper_control.BuiltinJointPositionController(
            robot,
            # 为退出时要去的目标关节角，值为None到达目标位不动，此值在Builin模式下库中被定义是 timeout=5
            rest_position=None,
    ) as controller:
        # ⚠ (ModeCtrl speed=5) for safer motion.
        robot.set_arm_mode(speed=5)
        print(f"current joints: {robot.get_joint_positions()}")

        reach_position = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        # [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        # [0.2, 0.2, -0.2, 0.3, -0.2, 0.5]
        print(f"moving to position: {reach_position}")
        success = controller.move_to_position(reach_position, threshold=0.01, timeout=8.0)
        print(f"reached target: {success}")

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
            safe_position = [0.0, 0.0, 0.0, 0.02, 0.5, 0.0]
            print(f"moving to safe position before disable: {safe_position}")
            reached_safe_position = controller.move_to_position(safe_position, threshold=0.01, timeout=8.0)
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