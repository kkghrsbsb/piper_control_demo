# 运动调试
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
from piper_control_demo.control import (
    confirm_and_shutdown,
    move_to_position_with_keyboard_stop,
)

# 目标位姿，前 6 个元素是关节角度，第 7 个元素是夹爪位置
# 控制范围见 https://github.com/Reimagine-Robotics/piper_control/blob/main/src/piper_control/piper_interface.py

# target_pose = [j1, j2, j3, j4, j5, j6, gripper_pos] -> gripper_pos range: [0, 0.1]
TARGET_POSE_7D = [0.2, 0.2, -0.2, 0.3, -0.2, 0.5, 0.0]
# [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

# (内置)位置速度控制模式的速度 range: [0, 100]
# ⚠ 测试安全运动速度范围是 [5, 20], 值越小越安全
JOINT_SAFE_SPEED = 5

# 夹爪夹持时允许施加的力 range: [0, 2]
GRIPPER_EFFORT_NOW = 1

# 6个关节的碰撞保护等级 
COLLISION_PROTECTION_LEVELS = [5, 5, 5, 5, 5, 5]

# 控制循环频率
MOVE_CONTROL_HZ = 200.0
# 单次运动运动最大允许时长，超过时自动停止
MOVE_TIMEOUT_SECONDS = 12.0
# 到位判定阈值
MOVE_THRESHOLD = 0.01
# 到位判定滑动平均窗口大小
MOVE_STEP_ALPHA = 0.2


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

    # 重置或失能机械臂关节与夹爪
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
    
    # 急停侦测
    emergency_stop_triggered = False
    
    # 采用内置默认关节位控制器上下文
    with piper_control.BuiltinJointPositionController(
            robot,
            # 为退出时要去的目标关节角，值为None到达目标位不动，一定不要改动此值
            rest_position=None,
    ) as controller:
        robot.set_arm_mode(speed=JOINT_SAFE_SPEED)
        print(f"current joints: {robot.get_joint_positions()}")

        reach_position = TARGET_POSE_7D[:6]
        gripper_position = TARGET_POSE_7D[6]
        print(f"moving to position: {reach_position}")
        
        # 必要时按下 q 中断运动
        success, emergency_stop_triggered = move_to_position_with_keyboard_stop(
            robot,
            controller,
            reach_position,
            speed_hz=MOVE_CONTROL_HZ,
            threshold=MOVE_THRESHOLD,
            timeout=MOVE_TIMEOUT_SECONDS,
            step_alpha=MOVE_STEP_ALPHA,
        )
        print(f"reached target: {success}")
        if emergency_stop_triggered:
            print("motion interrupted before gripper command.")
        elif not success:
            print("joint target not reached within timeout, skip gripper command.")
        else:
            print(f"moving gripper to position: {gripper_position}")
            robot.command_gripper(gripper_position, GRIPPER_EFFORT_NOW)
            print(f"current gripper state: {robot.get_gripper_state()}")

    # 提醒与安全失能
    confirm_and_shutdown(
        robot,
        emergency_stop_triggered=emergency_stop_triggered,
        threshold=MOVE_THRESHOLD,
        timeout=MOVE_TIMEOUT_SECONDS,
    )


if __name__ == "__main__":
    main()
