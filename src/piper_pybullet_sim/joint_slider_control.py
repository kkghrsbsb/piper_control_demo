import os
import time

import pybullet as p
import pybullet_data

from piper_control_demo.core.path import PIPER_DESCRIPTION_DIR


CONTROL_TYPES = {
    p.JOINT_REVOLUTE,
    p.JOINT_PRISMATIC,
}


def get_joint_limits(joint_info: tuple) -> tuple[float, float]:
    lower = float(joint_info[8])
    upper = float(joint_info[9])

    # Some URDF joints may not provide valid limits. Fall back to a small symmetric range
    # so the slider can still be created and interacted with.
    if lower > upper:
        return -1.0, 1.0

    return lower, upper


def create_joint_sliders(robot_id: int) -> list[tuple[int, str, int]]:
    sliders: list[tuple[int, str, int]] = []

    for joint_index in range(p.getNumJoints(robot_id)):
        joint_info = p.getJointInfo(robot_id, joint_index)
        joint_type = joint_info[2]
        if joint_type not in CONTROL_TYPES:
            continue

        joint_name = joint_info[1].decode("utf-8")
        lower, upper = get_joint_limits(joint_info)
        start_value = p.getJointState(robot_id, joint_index)[0]
        slider_id = p.addUserDebugParameter(joint_name, lower, upper, start_value)
        sliders.append((joint_index, joint_name, slider_id))

    return sliders


def main() -> None:
    dt = 1.0 / 200.0
    max_force = 80.0
    max_velocity = 0.7

    p.connect(p.GUI, options="--width=1920 --height=1080")
    p.setGravity(0, 0, -9.8)
    p.setTimeStep(dt)
    p.resetDebugVisualizerCamera(
        cameraDistance=3,
        cameraYaw=180,
        cameraPitch=0,
        cameraTargetPosition=[0, 0, 0.3],
    )

    plane_path = os.path.join(pybullet_data.getDataPath(), "plane.urdf")
    p.loadURDF(plane_path)

    robot_path = os.path.join(PIPER_DESCRIPTION_DIR, "urdf", "piper_description.urdf")
    robot_id = p.loadURDF(robot_path, [0, 0, 0], useFixedBase=True, globalScaling=5)

    joint_sliders = create_joint_sliders(robot_id)
    if not joint_sliders:
        raise RuntimeError("No controllable joints found for slider UI.")

    print("[Slider Control] Created sliders for joints:")
    for joint_index, joint_name, _slider_id in joint_sliders:
        print(f"  - {joint_index}: {joint_name}")

    try:
        while p.isConnected():
            for joint_index, _joint_name, slider_id in joint_sliders:
                target = p.readUserDebugParameter(slider_id)
                p.setJointMotorControl2(
                    bodyIndex=robot_id,
                    jointIndex=joint_index,
                    controlMode=p.POSITION_CONTROL,
                    targetPosition=target,
                    force=max_force,
                    maxVelocity=max_velocity,
                )

            p.stepSimulation()
            time.sleep(dt)
    finally:
        if p.isConnected():
            p.disconnect()


if __name__ == "__main__":
    main()
