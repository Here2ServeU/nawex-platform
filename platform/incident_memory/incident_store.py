"""Incident memory storage stub."""


class IncidentStore:
    def __init__(self) -> None:
        self._items: list[dict] = []

    def add(self, incident: dict) -> None:
        self._items.append(incident)

    def all(self) -> list[dict]:
        return list(self._items)
