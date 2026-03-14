import json
import os
import socket
import time

import pybullet as p
import pybullet_data

from piper_control_demo.core.path import PIPER_DESCRIPTION_DIR


HOST = "127.0.0.1"
PORT = 15001
STREAM_HZ = 200.0
MAX_FORCE = 80.0
MAX_VELOCITY = 0.7
CONTROL_TYPES = {
    p.JOINT_REVOLUTE,
    p.JOINT_PRISMATIC,
}


def get_joint_limits(joint_info: tuple) -> tuple[float, float]:
    lower = float(joint_info[8])
    upper = float(joint_info[9])

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


def connect_receiver(host: str = HOST, port: int = PORT) -> socket.socket:
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


def main() -> None:
    dt = 1.0 / STREAM_HZ

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
    if len(joint_sliders) < 6:
        raise RuntimeError("Less than 6 controllable joints found for slider UI.")

    streamed_joints = joint_sliders[:6]
    print("[Sender] Streaming the first 6 controllable joints:")
    for joint_index, joint_name, _slider_id in streamed_joints:
        print(f"  - {joint_index}: {joint_name}")

    client = connect_receiver()
    start_time = time.perf_counter()
    frame_count = 0

    try:
        while p.isConnected():
            q = []
            for joint_index, _joint_name, slider_id in joint_sliders:
                target = p.readUserDebugParameter(slider_id)
                p.setJointMotorControl2(
                    bodyIndex=robot_id,
                    jointIndex=joint_index,
                    controlMode=p.POSITION_CONTROL,
                    targetPosition=target,
                    force=MAX_FORCE,
                    maxVelocity=MAX_VELOCITY,
                )
                if len(q) < 6:
                    q.append(target)

            payload = {
                "t": time.perf_counter() - start_time,
                "q": q,
            }
            client.sendall((json.dumps(payload) + "\n").encode("utf-8"))

            p.stepSimulation()
            frame_count += 1
            target_time = start_time + frame_count * dt
            remaining = target_time - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
    finally:
        client.close()
        if p.isConnected():
            p.disconnect()


if __name__ == "__main__":
    main()
