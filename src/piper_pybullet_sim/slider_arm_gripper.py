import os
import time
from dataclasses import dataclass

import pybullet as p
import pybullet_data

from piper_control_demo.core.path import PIPER_DESCRIPTION_DIR


CONTROL_TYPES = {
    p.JOINT_REVOLUTE,
    p.JOINT_PRISMATIC,
}

GRIPPER_JOINT_7 = "joint7"
GRIPPER_JOINT_8 = "joint8"
GRIPPER_SLIDER_NAME = "gripper_position"


@dataclass(frozen=True)
class JointTarget:
    joint_index: int
    joint_name: str
    scale: float = 1.0


@dataclass(frozen=True)
class SliderControl:
    slider_name: str
    slider_id: int
    targets: tuple[JointTarget, ...]


def get_joint_limits(joint_info: tuple) -> tuple[float, float]:
    lower = float(joint_info[8])
    upper = float(joint_info[9])

    # Some URDF joints may not provide valid limits. Fall back to a small symmetric range
    # so the slider can still be created and interacted with.
    if lower > upper:
        return -1.0, 1.0

    return lower, upper


def get_joint_infos(robot_id: int) -> dict[int, tuple]:
    return {
        joint_index: p.getJointInfo(robot_id, joint_index)
        for joint_index in range(p.getNumJoints(robot_id))
    }


def get_gripper_control(robot_id: int, joint_infos: dict[int, tuple]) -> SliderControl | None:
    joint7_info: tuple | None = None
    joint8_info: tuple | None = None
    joint7_index: int | None = None
    joint8_index: int | None = None

    for joint_index, joint_info in joint_infos.items():
        joint_name = joint_info[1].decode("utf-8")
        if joint_name == GRIPPER_JOINT_7:
            joint7_index = joint_index
            joint7_info = joint_info
        elif joint_name == GRIPPER_JOINT_8:
            joint8_index = joint_index
            joint8_info = joint_info

    if joint7_info is None or joint8_info is None or joint7_index is None or joint8_index is None:
        return None

    lower7, upper7 = get_joint_limits(joint7_info)
    start_value = p.getJointState(robot_id, joint7_index)[0]
    slider_id = p.addUserDebugParameter(GRIPPER_SLIDER_NAME, lower7, upper7, start_value)

    return SliderControl(
        slider_name=GRIPPER_SLIDER_NAME,
        slider_id=slider_id,
        targets=(
            JointTarget(joint_index=joint7_index, joint_name=GRIPPER_JOINT_7, scale=1.0),
            JointTarget(joint_index=joint8_index, joint_name=GRIPPER_JOINT_8, scale=-1.0),
        ),
    )


def create_joint_sliders(robot_id: int) -> list[SliderControl]:
    sliders: list[SliderControl] = []
    joint_infos = get_joint_infos(robot_id)
    gripper_control = get_gripper_control(robot_id, joint_infos)
    gripper_joint_names = {GRIPPER_JOINT_7, GRIPPER_JOINT_8}

    for joint_index, joint_info in joint_infos.items():
        joint_type = joint_info[2]
        if joint_type not in CONTROL_TYPES:
            continue

        joint_name = joint_info[1].decode("utf-8")
        if gripper_control is not None and joint_name in gripper_joint_names:
            continue

        lower, upper = get_joint_limits(joint_info)
        start_value = p.getJointState(robot_id, joint_index)[0]
        slider_id = p.addUserDebugParameter(joint_name, lower, upper, start_value)
        sliders.append(
            SliderControl(
                slider_name=joint_name,
                slider_id=slider_id,
                targets=(JointTarget(joint_index=joint_index, joint_name=joint_name),),
            )
        )

    if gripper_control is not None:
        sliders.append(gripper_control)

    return sliders


def main() -> None:
    dt = 1.0 / 200.0
    max_force = 80.0
    max_velocity = 0.7

    p.connect(p.GUI, options="--width=1920 --height=1080")
    p.setGravity(0, 0, -9.8)
    p.setTimeStep(dt)
    p.resetDebugVisualizerCamera(
        cameraDistance=1.8,
        cameraYaw=45,
        cameraPitch=-25,
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
    for control in joint_sliders:
        target_desc = ", ".join(
            f"{target.joint_index}:{target.joint_name} x{target.scale:g}"
            for target in control.targets
        )
        print(f"  - {control.slider_name} -> {target_desc}")

    try:
        while p.isConnected():
            for control in joint_sliders:
                slider_value = p.readUserDebugParameter(control.slider_id)
                for target in control.targets:
                    p.setJointMotorControl2(
                        bodyIndex=robot_id,
                        jointIndex=target.joint_index,
                        controlMode=p.POSITION_CONTROL,
                        targetPosition=slider_value * target.scale,
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
