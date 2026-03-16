import time
from piper_control import piper_connect, piper_init, piper_interface


# 6 个关节的默认碰撞保护等级，按 [j1, j2, j3, j4, j5, j6] 给出
DEFAULT_COLLISION_PROTECTION_LEVELS = [5, 5, 5, 5, 5, 5]
# 写入碰撞保护后，先等待设备反馈刷新
COLLISION_PROTECTION_SETTLE_SECONDS = 0.3
# 反馈采样次数，用于覆盖设备侧可能存在的刷新延迟
COLLISION_PROTECTION_SAMPLE_COUNT = 5
# 相邻两次反馈采样的时间间隔
COLLISION_PROTECTION_SAMPLE_INTERVAL = 0.1

def connect_can():
    """连接到 Piper 的 CAN 接口并返回已激活的 CAN 端口名称列表。

    Returns:
        list[str]: 激活后的 CAN 端口列表（例如 ["can0"]）

    Raises:
        ValueError: 如果未发现任何已激活的 CAN 端口，则抛出异常提示用户检查连接
    """
    ports = piper_connect.find_ports()
    print(f"Piper ports: {ports}")

    piper_connect.activate(ports)
    ports = piper_connect.active_ports()

    if not ports:
        raise ValueError("No ports found. Make sure the Piper is connected and turned on.")

    return ports


def probe_arm_enabled_state(
        robot,
        settle_seconds=0.3,
        sample_count=5,
        sample_interval=0.05,
):
    """通过多次采样状态来探测机械臂是否已使能。

    在重新连接后先短暂等待，然后多次调用 `robot.is_arm_enabled()`
    进行采样，以降低由瞬时状态更新引起的一次性误判为未使能的情况。

    Args:
        robot: 用于查询的 PiperInterface 实例
        settle_seconds (float): 开始采样前的初始等待时间
        sample_count (int): 采集的使能状态样本数量
        sample_interval (float): 相邻两次采样之间的等待时间

    Returns:
        bool: 只要任一采样结果显示为已使能则返回 True，否则返回 False
    """

    # Allow status feedback to settle after reconnect, then sample multiple
    # times to avoid one-shot false negatives.
    time.sleep(settle_seconds)
    enabled_samples = []
    for _ in range(sample_count):
        enabled_samples.append(robot.is_arm_enabled())
        time.sleep(sample_interval)

    is_enabled = any(enabled_samples)
    if is_enabled:
        print(f"arm appears enabled (samples={enabled_samples}), skip reset_arm.")
    else:
        print(f"arm appears disabled (samples={enabled_samples}).")

    return is_enabled


def probe_gripper_enabled_state(
        robot,
        settle_seconds=0.3,
        sample_count=5,
        sample_interval=0.05,
):
    """通过多次采样状态来探测夹爪是否已使能。"""

    time.sleep(settle_seconds)
    enabled_samples = []
    for _ in range(sample_count):
        enabled_samples.append(robot.is_gripper_enabled())
        time.sleep(sample_interval)

    is_enabled = any(enabled_samples)
    if is_enabled:
        print(f"gripper appears enabled (samples={enabled_samples}), skip enable_gripper.")
    else:
        print(f"gripper appears disabled (samples={enabled_samples}).")

    return is_enabled


def ensure_arm_and_gripper_enabled(robot) -> tuple[bool, bool]:
    """确保机械臂与夹爪都处于可控制状态。"""

    is_arm_enabled = probe_arm_enabled_state(robot)
    if not is_arm_enabled:
        print("resetting arm")
        piper_init.reset_arm(
            robot,
            arm_controller=piper_interface.ArmController.POSITION_VELOCITY,
            move_mode=piper_interface.MoveMode.JOINT,
        )
        is_arm_enabled = True

    print("resetting gripper")
    piper_init.reset_gripper(robot)
    is_gripper_enabled = probe_gripper_enabled_state(robot)

    if not is_gripper_enabled:
        print("enabling gripper")
        robot.enable_gripper()
        is_gripper_enabled = probe_gripper_enabled_state(robot)

    print(f"arm enabled: {is_arm_enabled}")
    print(f"gripper enabled: {is_gripper_enabled}")
    print(f"current gripper state: {robot.get_gripper_state()}")

    return is_arm_enabled, is_gripper_enabled


def verify_collision_protection(
        robot,
        expected_levels,
        settle_seconds=COLLISION_PROTECTION_SETTLE_SECONDS,
        sample_count=COLLISION_PROTECTION_SAMPLE_COUNT,
        sample_interval=COLLISION_PROTECTION_SAMPLE_INTERVAL,
):
    """写入碰撞保护后，等待并多次读取反馈进行验证。"""

    print(f"setting collision protection levels: {expected_levels}")
    robot.set_collision_protection(expected_levels)

    time.sleep(settle_seconds)
    sampled_levels = []
    for _ in range(sample_count):
        sampled_levels.append(robot.get_collision_protection())
        time.sleep(sample_interval)

    matched = any(levels == list(expected_levels) for levels in sampled_levels)
    print(f"collision protection expected: {list(expected_levels)}")
    print(f"collision protection samples: {sampled_levels}")
    print(f"collision protection matched: {matched}")

    return matched


def configure_collision_protection(
        robot,
        levels=DEFAULT_COLLISION_PROTECTION_LEVELS,
        *,
        settle_seconds=COLLISION_PROTECTION_SETTLE_SECONDS,
        sample_count=COLLISION_PROTECTION_SAMPLE_COUNT,
        sample_interval=COLLISION_PROTECTION_SAMPLE_INTERVAL,
):
    """统一写入并验证真实机械臂的碰撞保护等级。"""

    return verify_collision_protection(
        robot,
        levels,
        settle_seconds=settle_seconds,
        sample_count=sample_count,
        sample_interval=sample_interval,
    )
