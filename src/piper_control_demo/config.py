from piper_control import piper_connect, piper_init
import time

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
