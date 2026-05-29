"""JFact reasoner (replaces Pellet, which was dropped from ROBOT due to licensing)."""
from pathlib import Path
from bench.reasoners.robot_docker import RobotDocker


class JFactReasoner:
    name = "jfact"
    profile = "DL"
    wrapper = "robot-docker"

    def __init__(self):
        self._robot = RobotDocker()

    def materialise(self, source: Path) -> Path:
        out = source.with_suffix(".jfact.owx")
        return self._robot.reason(source, reasoner="JFact", out=out)
