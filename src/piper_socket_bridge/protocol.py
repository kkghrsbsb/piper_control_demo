"""Protocol helpers for the unified joint-and-gripper socket stream."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class PoseStreamFrame:
    """A single newline-delimited socket frame.

    The stream keeps the 6 arm joints under `q` and the gripper under the
    separate `gripper` field so the protocol matches the robot control surface.
    """

    t: float
    q: list[float]
    gripper: float

    def __post_init__(self) -> None:
        if len(self.q) != 6:
            raise ValueError(f"Expected 6 joint targets, got {len(self.q)}")

    def to_payload(self) -> dict[str, Any]:
        return {
            "t": float(self.t),
            "q": [float(value) for value in self.q],
            "gripper": float(self.gripper),
        }

    def to_json_line(self) -> bytes:
        return (json.dumps(self.to_payload()) + "\n").encode("utf-8")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PoseStreamFrame":
        q = payload.get("q")
        if not isinstance(q, list):
            raise ValueError(f"Frame missing joint list: {payload}")
        if len(q) != 6:
            raise ValueError(f"Expected 6 joint targets, got {len(q)}")

        gripper = payload.get("gripper")
        if not isinstance(gripper, (int, float)):
            raise ValueError(f"Frame missing numeric gripper target: {payload}")

        t_value = payload.get("t", 0.0)
        if not isinstance(t_value, (int, float)):
            raise ValueError(f"Frame missing numeric timestamp: {payload}")

        return cls(
            t=float(t_value),
            q=[float(value) for value in q],
            gripper=float(gripper),
        )

    @classmethod
    def from_json_line(cls, line: str) -> "PoseStreamFrame":
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"Frame payload must be an object: {payload}")
        return cls.from_payload(payload)
