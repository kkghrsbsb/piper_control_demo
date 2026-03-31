"""PyBullet receiver that mirrors a real robot's state streamed over a socket.

The receiver:
1. Loads the Piper URDF in a PyBullet GUI (no sliders).
2. Listens on a TCP port for ``PoseStreamFrame`` lines from the real-arm sender.
3. On the **first frame**, teleports the sim joints to match the real arm
   (``resetJointState``), so there is no slow drift from the origin.
4. On subsequent frames, drives the sim joints via position control so that
   the physics engine smooths the motion.

When multiple frames accumulate in the receive buffer, only the **latest**
frame is applied — older frames are discarded to avoid lag build-up.
"""

from __future__ import annotations

import os
import select
import socket
import time

import pybullet as p
import pybullet_data

from piper_control_demo.core.path import PIPER_DESCRIPTION_DIR
from piper_pybullet_sim.slider_arm_gripper import (
    CONTROL_TYPES,
    GRIPPER_JOINT_7,
    GRIPPER_JOINT_8,
    GRIPPER_PROTOCOL_TO_SIM_SCALE,
)
from piper_socket_bridge.protocol import PoseStreamFrame


HOST = "127.0.0.1"
PORT = 15002
STREAM_HZ = 200.0
MAX_FORCE = 80.0
MAX_VELOCITY = 5.0
PRINT_HZ = 20.0


# ---------------------------------------------------------------------------
# Joint mapping helpers
# ---------------------------------------------------------------------------

def _build_joint_maps(robot_id: int) -> tuple[list[int], int | None, int | None]:
    """Return ordered arm joint indices and the two gripper joint indices.

    The arm joints are returned in the same order as the URDF (joint1 … joint6),
    matching the ``q`` list in ``PoseStreamFrame``.
    """

    arm_indices: list[int] = []
    gripper7_index: int | None = None
    gripper8_index: int | None = None

    for idx in range(p.getNumJoints(robot_id)):
        info = p.getJointInfo(robot_id, idx)
        joint_type = info[2]
        joint_name = info[1].decode("utf-8")

        if joint_name == GRIPPER_JOINT_7:
            gripper7_index = idx
            continue
        if joint_name == GRIPPER_JOINT_8:
            gripper8_index = idx
            continue

        if joint_type in CONTROL_TYPES:
            arm_indices.append(idx)

    return arm_indices, gripper7_index, gripper8_index


# ---------------------------------------------------------------------------
# Frame application
# ---------------------------------------------------------------------------

def _teleport_to_frame(
    robot_id: int,
    frame: PoseStreamFrame,
    arm_indices: list[int],
    gripper7: int | None,
    gripper8: int | None,
) -> None:
    """Instantly set sim joints to *frame* (no physics transition)."""

    for i, idx in enumerate(arm_indices):
        if i < len(frame.q):
            p.resetJointState(robot_id, idx, frame.q[i])

    if gripper7 is not None:
        p.resetJointState(
            robot_id, gripper7, frame.gripper * GRIPPER_PROTOCOL_TO_SIM_SCALE,
        )
    if gripper8 is not None:
        p.resetJointState(
            robot_id, gripper8, -frame.gripper * GRIPPER_PROTOCOL_TO_SIM_SCALE,
        )


def _drive_to_frame(
    robot_id: int,
    frame: PoseStreamFrame,
    arm_indices: list[int],
    gripper7: int | None,
    gripper8: int | None,
) -> None:
    """Apply position-control targets so the sim smoothly follows *frame*."""

    for i, idx in enumerate(arm_indices):
        if i < len(frame.q):
            p.setJointMotorControl2(
                bodyIndex=robot_id,
                jointIndex=idx,
                controlMode=p.POSITION_CONTROL,
                targetPosition=frame.q[i],
                force=MAX_FORCE,
                maxVelocity=MAX_VELOCITY,
            )

    gripper_sim = frame.gripper * GRIPPER_PROTOCOL_TO_SIM_SCALE
    if gripper7 is not None:
        p.setJointMotorControl2(
            bodyIndex=robot_id,
            jointIndex=gripper7,
            controlMode=p.POSITION_CONTROL,
            targetPosition=gripper_sim,
            force=MAX_FORCE,
            maxVelocity=MAX_VELOCITY,
        )
    if gripper8 is not None:
        p.setJointMotorControl2(
            bodyIndex=robot_id,
            jointIndex=gripper8,
            controlMode=p.POSITION_CONTROL,
            targetPosition=-gripper_sim,
            force=MAX_FORCE,
            maxVelocity=MAX_VELOCITY,
        )


# ---------------------------------------------------------------------------
# Buffer → latest frame
# ---------------------------------------------------------------------------

def _extract_latest_frame(buffer: str) -> tuple[PoseStreamFrame | None, str]:
    """Parse all complete lines in *buffer* and return only the latest frame.

    Returns ``(latest_frame, remaining_buffer)``.  Intermediate frames are
    silently discarded to avoid lag accumulation.
    """

    latest: PoseStreamFrame | None = None
    remainder = buffer

    while "\n" in remainder:
        line, remainder = remainder.split("\n", 1)
        line = line.strip()
        if not line:
            continue
        try:
            latest = PoseStreamFrame.from_json_line(line)
        except (ValueError, Exception):
            # Skip malformed lines without crashing.
            pass

    return latest, remainder


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_pybullet_receiver(host: str = HOST, port: int = PORT) -> None:
    """Start a PyBullet visualiser and mirror the real robot streamed to *port*."""

    dt = 1.0 / STREAM_HZ

    # ---- PyBullet setup (no sliders) ----
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

    arm_indices, gripper7, gripper8 = _build_joint_maps(robot_id)
    print(f"[SimReceiver] arm joints: {arm_indices}, "
          f"gripper7={gripper7}, gripper8={gripper8}")

    # ---- TCP server ----
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)
    print(f"[SimReceiver] listening on {host}:{port} ...")

    conn, addr = server.accept()
    conn.setblocking(False)
    print(f"[SimReceiver] sender connected from {addr}")

    buffer = ""
    first_frame_applied = False
    next_print_time = time.perf_counter()
    frame_count = 0
    start_time = time.perf_counter()

    try:
        while p.isConnected():
            # ---- non-blocking recv ----
            try:
                readable = select.select([conn], [], [], 0)[0]
                if readable:
                    chunk = conn.recv(8192)
                    if not chunk:
                        print("[SimReceiver] sender disconnected.")
                        break
                    buffer += chunk.decode("utf-8")
            except (ConnectionResetError, OSError):
                print("[SimReceiver] connection lost.")
                break

            # ---- parse & apply latest frame ----
            frame, buffer = _extract_latest_frame(buffer)

            if frame is not None:
                if not first_frame_applied:
                    _teleport_to_frame(
                        robot_id, frame, arm_indices, gripper7, gripper8,
                    )
                    first_frame_applied = True
                    print(f"[SimReceiver] initial pose aligned: q={frame.q}, "
                          f"gripper={frame.gripper}")
                else:
                    _drive_to_frame(
                        robot_id, frame, arm_indices, gripper7, gripper8,
                    )

                now = time.perf_counter()
                if now >= next_print_time:
                    print(f"[SimReceiver] t={frame.t:.2f}  q={frame.q}  "
                          f"gripper={frame.gripper:.4f}")
                    next_print_time = now + 1.0 / PRINT_HZ

            p.stepSimulation()

            # ---- rate-limit to match STREAM_HZ ----
            frame_count += 1
            target_time = start_time + frame_count * dt
            remaining = target_time - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)

    except KeyboardInterrupt:
        print("\n[SimReceiver] interrupted.")
    finally:
        conn.close()
        server.close()
        if p.isConnected():
            p.disconnect()
