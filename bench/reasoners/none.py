from pathlib import Path


class NoneReasoner:
    name = "none"
    profile = "none"
    wrapper = "in-process"

    def materialise(self, source: Path) -> Path:
        return source
