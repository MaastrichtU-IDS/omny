from pathlib import Path
from bench.reasoners.robot_docker import RobotDocker


class ElkReasoner:
    name = "elk"
    profile = "EL"
    wrapper = "robot-docker"

    def __init__(self):
        self._robot = RobotDocker()

    def materialise(self, source: Path) -> Path:
        out = source.with_suffix(".elk.owx")
        return self._robot.reason(source, reasoner="ELK", out=out)
