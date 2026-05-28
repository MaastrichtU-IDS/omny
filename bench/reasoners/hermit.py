from pathlib import Path
from bench.reasoners.robot_docker import RobotDocker


class HermitReasoner:
    name = "hermit"
    profile = "DL"
    wrapper = "robot-docker"

    def __init__(self):
        self._robot = RobotDocker()

    def materialise(self, source: Path) -> Path:
        out = source.with_suffix(".hermit.owx")
        return self._robot.reason(source, reasoner="HermiT", out=out)
