"""Dataset registry placeholder."""


class DatasetRegistry:
    def __init__(self) -> None:
        self._datasets: dict[str, str] = {}

    def register(self, name: str, path: str) -> None:
        self._datasets[name] = path
