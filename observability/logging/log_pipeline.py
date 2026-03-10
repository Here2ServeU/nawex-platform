"""Log pipeline placeholder."""


def route_log(record: dict) -> dict:
    return {"status": "routed", "record": record}
