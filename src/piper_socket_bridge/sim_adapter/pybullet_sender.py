"""PyBullet slider sender for the unified joint-and-gripper stream."""

from __future__ import annotations

import os
import socket
import time

import pybullet as p
import pybullet_data

from piper_control_demo.core.path import PIPER_DESCRIPTION_DIR
from piper_pybullet_sim.slider_arm_gripper import (
    GRIPPER_SLIDER_NAME,
    SliderControl,
    create_joint_sliders,
)
from piper_socket_bridge.protocol import PoseStreamFrame


HOST = "127.0.0.1"
PORT = 15001
STREAM_HZ = 200.0
MAX_FORCE = 80.0
MAX_VELOCITY = 0.3


def connect_receiver(host: str = HOST, port: int = PORT) -> socket.socket:
    """Connect to the robot-side receiver, retrying until it is ready."""

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"[Sender] connecting to receiver on {host}:{port} ...")

    while True:
        try:
            client.connect((host, port))
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print("[Sender] receiver connected.")
            return client
        except ConnectionRefusedError:
            time.sleep(0.2)


def apply_slider_targets(robot_id: int, joint_sliders: list[SliderControl]) -> None:
    """Apply the current UI slider targets to the simulated robot.

    This step only writes command targets into the PyBullet position controllers.
    It does not mean the simulated joints have already reached those targets.
    """

    for control in joint_sliders:
        slider_value = float(p.readUserDebugParameter(control.slider_id))
        for target in control.targets:
            p.setJointMotorControl2(
                bodyIndex=robot_id,
                jointIndex=target.joint_index,
                controlMode=p.POSITION_CONTROL,
                targetPosition=slider_value * target.scale,
                force=MAX_FORCE,
                maxVelocity=MAX_VELOCITY,
            )


def read_control_state(robot_id: int, control: SliderControl) -> float:
    """Recover the current simulated state represented by one slider control.

    For ordinary arm joints, one slider maps to one joint, so we can directly
    read that joint's current angle. For the gripper slider, one control maps to
    two mirrored joints; we therefore project both joint states back into the
    single-slider semantic and average them.
    """

    recovered_values: list[float] = []
    for target in control.targets:
        joint_position = float(p.getJointState(robot_id, target.joint_index)[0])
        recovered_values.append(joint_position / target.scale)

    return sum(recovered_values) / len(recovered_values)


def read_robot_state_frame(
        robot_id: int,
        joint_sliders: list[SliderControl],
        *,
        timestamp: float,
) -> PoseStreamFrame:
    """Read the current simulated robot state and convert it into a stream frame."""

    q: list[float] = []
    gripper = 0.0

    for control in joint_sliders:
        current_value = read_control_state(robot_id, control)
        if control.slider_name == GRIPPER_SLIDER_NAME:
            gripper = current_value
        else:
            q.append(current_value)

    return PoseStreamFrame(t=timestamp, q=q[:6], gripper=gripper)


def run_pybullet_slider_sender(host: str = HOST, port: int = PORT) -> None:
    """Start the PyBullet slider UI and stream the simulated robot's true state.

    The sliders still act as command targets for the simulation, but the socket
    payload is sent only after `stepSimulation()` and is built from the current
    simulated joint/gripper state, not from the raw slider values.
    """

    dt = 1.0 / STREAM_HZ

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

    print("[Sender] Created sliders:")
    for control in joint_sliders:
        print(f"  - {control.slider_name}")

    client = connect_receiver(host=host, port=port)
    start_time = time.perf_counter()
    frame_count = 0

    try:
        while p.isConnected():
            apply_slider_targets(robot_id, joint_sliders)
            p.stepSimulation()

            payload = read_robot_state_frame(
                robot_id,
                joint_sliders,
                timestamp=time.perf_counter() - start_time,
            )
            client.sendall(payload.to_json_line())

            frame_count += 1
            target_time = start_time + frame_count * dt
            remaining = target_time - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
    finally:
        client.close()
        if p.isConnected():
            p.disconnect()
