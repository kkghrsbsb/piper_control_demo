import json
from piper_control import piper_interface
import time

from piper_control_demo.config import connect_can


STREAM_HZ = 200.0

if __name__ == "__main__":
    ports = connect_can()

    robot = piper_interface.PiperInterface(can_port=ports[0])
    robot.set_installation_pos(piper_interface.ArmInstallationPos.UPRIGHT)

    # wait for the robot to settle
    time.sleep(0.3)

    robot.show_status()
    time.sleep(2.0)

    start_time = time.perf_counter()
    frame_count = 0
    dt = 1.0 / STREAM_HZ

    while True:
        joints = robot.get_joint_positions()
        gripper_pos, _gripper_effort = robot.get_gripper_state()
        payload = {
            "t": time.perf_counter() - start_time,
            "q": joints,
            "gripper": gripper_pos,
        }
        print(json.dumps(payload), flush=True)

        frame_count += 1
        target_time = start_time + frame_count * dt
        remaining = target_time - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)
