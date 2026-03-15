# 运动调试
import time
from piper_control import (
    piper_control,
    piper_init,
    piper_interface,
)
from piper_control_demo.config import (
    connect_can,
    probe_arm_enabled_state,
    probe_gripper_enabled_state,
)

# 目标位姿，前 6 个元素是关节角度，第 7 个元素是夹爪位置
# 控制范围见 https://github.com/Reimagine-Robotics/piper_control/blob/main/src/piper_control/piper_interface.py

# target_pose = [j1, j2, j3, j4, j5, j6, gripper_pos] -> gripper_pos range: [0, 0.1]
TARGET_POSE_7D = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


# (内置)位置速度控制模式的速度 range: [0, 100]
# ⚠ 测试安全运动速度范围是 [5, 20], 值越小越安全
JOINT_SAFE_SPEED = 5

# 夹爪夹持时允许施加的力 range: [0, 2]
GRIPPER_EFFORT_NOW = 0.3

# 6个关节的碰撞保护等级
COLLISION_PROTECTION_LEVELS = [5, 5, 5, 5, 5, 5]


def main():
    # 连接机械臂并失能/重置机械臂
    ports = connect_can()

    input("WARNING: the robot will move. Press Enter to continue...")

    robot = piper_interface.PiperInterface(can_port=ports[0])
    robot.set_installation_pos(piper_interface.ArmInstallationPos.UPRIGHT)
    robot.set_collision_protection(COLLISION_PROTECTION_LEVELS)
    print(
        "collision protection levels:",
        robot.get_collision_protection(),
    )

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
    is_gripper_enabled = probe_gripper_enabled_state(robot)
    
    if not is_gripper_enabled:
        print("enabling gripper")
        robot.enable_gripper()
        is_gripper_enabled = probe_gripper_enabled_state(robot)
    print(f"gripper enabled: {is_gripper_enabled}")
    print(f"current gripper state: {robot.get_gripper_state()}")

    robot.show_status()

    # 采用Buildin关节位控制器上下文
    with piper_control.BuiltinJointPositionController(
            robot,
            # 为退出时要去的目标关节角，值为None到达目标位不动，此值在Builin模式下库中被定义是 timeout=5
            rest_position=None,
    ) as controller:
        robot.set_arm_mode(speed=JOINT_SAFE_SPEED)
        print(f"current joints: {robot.get_joint_positions()}")

        reach_position = TARGET_POSE_7D[:6]
        gripper_position = TARGET_POSE_7D[6]
        print(f"moving to position: {reach_position}")
        success = controller.move_to_position(reach_position, threshold=0.01, timeout=12.0)
        print(f"reached target: {success}")
        print(f"moving gripper to position: {gripper_position}")
        robot.command_gripper(gripper_position, GRIPPER_EFFORT_NOW)
        print(f"current gripper state: {robot.get_gripper_state()}")

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
            robot.set_arm_mode(speed=10)
            safe_position = [0.0, 0.0, 0.0, 0.02, 0.5, 0.0]
            print(f"moving to safe position before disable: {safe_position}")
            reached_safe_position = controller.move_to_position(safe_position, threshold=0.01, timeout=12.0)
            print(f"reached safe position: {reached_safe_position}")

        if reached_safe_position:
            time.sleep(1)
            robot.disable_gripper()
            piper_init.disable_arm(robot)
        else:
            print("safe position not reached, skip disabling arm.")
            print(f"current joints: {robot.get_joint_positions()}")
    else:
        print("skip disabling arm.")


if __name__ == "__main__":
    main()
