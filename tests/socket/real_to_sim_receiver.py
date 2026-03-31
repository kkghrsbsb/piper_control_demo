"""Entry point: mirror the real Piper arm in a PyBullet visualiser."""

from piper_socket_bridge.sim_adapter.pybullet_receiver import run_pybullet_receiver


if __name__ == "__main__":
    run_pybullet_receiver()
