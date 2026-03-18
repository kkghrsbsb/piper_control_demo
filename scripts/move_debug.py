# 运动调试
from piper_control import (
    piper_control,
    piper_interface,
)
from piper_control_demo.config import (
    DEFAULT_COLLISION_PROTECTION_LEVELS,
    configure_collision_protection,
    connect_can,
    ensure_arm_and_gripper_enabled,
)
from piper_control_demo.control import (
    confirm_and_shutdown,
    move_to_position_with_keyboard_stop,
)
'''
    |joint_name|     limit(rad)       |    limit(angle)    |
    |----------|     ----------       |     ----------     |
    |joint1    |   [-2.6179, 2.6179]  |    [-150.0, 150.0] |
    |joint2    |   [0, 3.14]          |    [0, 180.0]      |
    |joint3    |   [-2.967, 0]        |    [-170, 0]       |
    |joint4    |   [-1.745, 1.745]    |    [-100.0, 100.0] |
    |joint5    |   [-1.22, 1.22]      |    [-70.0, 70.0]   |
    |joint6    |   [-2.09439, 2.09439]|    [-120.0, 120.0] |
'''

# 目标位姿：`q` 只表示 6 个关节，夹爪位置单独定义
# 一些运动重要参数的范围见 .src/piper_control_demo/control.py
# target_q = [j1, j2, j3, j4, j5, j6]  type: rad
TARGET_Q = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
# target_gripper range: [0, 0.1]
TARGET_GRIPPER = 0.0

# (内置)位置速度控制模式的速度 range: [0, 100]
# ⚠ 测试安全运动速度范围是 [5, 20], 值越小越安全
JOINT_SAFE_SPEED = 10

# 夹爪夹持时允许施加的力 range: [0, 2]
GRIPPER_EFFORT_NOW = 0.5

# 6 个关节的碰撞保护等级，一些验证参数见 .src/piper_control_demo/config.py
COLLISION_PROTECTION_LEVELS = DEFAULT_COLLISION_PROTECTION_LEVELS


def main():
    # 连接机械臂并失能/重置机械臂
    ports = connect_can()

    input("WARNING: the robot will move. Press Enter to continue...")

    robot = piper_interface.PiperInterface(can_port=ports[0])
    robot.set_installation_pos(piper_interface.ArmInstallationPos.UPRIGHT)


    # 重置或使能机械臂关节与夹爪
    ensure_arm_and_gripper_enabled(robot)

    configure_collision_protection(robot, COLLISION_PROTECTION_LEVELS)

    robot.show_status()
    
    # 记录本次运动是否被人工急停，用于后续收尾提示
    emergency_stop_triggered = False
    
    # 采用内置默认关节位控制器上下文
    with piper_control.BuiltinJointPositionController(
            robot,
            # 为退出时要去的目标关节角，值为None到达目标位不动，一定不要改动此值
            rest_position=None,
    ) as controller:
        robot.set_arm_mode(speed=JOINT_SAFE_SPEED)
        print(f"current joints: {robot.get_joint_positions()}")

        reach_position = TARGET_Q
        gripper_position = TARGET_GRIPPER
        print(f"moving to position: {reach_position}")
        
        # 必要时按下按键 "q" 进行急停；函数内部也会做程序层运动异常守护
        motion_result = move_to_position_with_keyboard_stop(
            robot,
            controller,
            reach_position,
        )
        emergency_stop_triggered = motion_result.keyboard_stop_triggered
        print(f"reached target: {motion_result.motion_completed}")
        
        if emergency_stop_triggered:
            print("motion interrupted before gripper command.")
        elif motion_result.motion_guard_triggered:
            print(
                "motion interrupted by software motion guard before gripper "
                "command."
            )
        elif motion_result.timeout_triggered:
            print("joint target not reached within timeout, skip gripper command.")
        elif not motion_result.motion_completed:
            print("joint motion did not complete, skip gripper command.")
        else:
            print(f"moving gripper to position: {gripper_position}")
            robot.command_gripper(gripper_position, GRIPPER_EFFORT_NOW)
            print(f"current gripper state: {robot.get_gripper_state()}")

    # 提醒与安全失能机械臂与夹爪
    confirm_and_shutdown(
        robot,
        emergency_stop_triggered=emergency_stop_triggered,
    )


if __name__ == "__main__":
    main()
