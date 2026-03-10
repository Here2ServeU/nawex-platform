"""Policy evaluator placeholder."""


def is_action_allowed(action: str, context: dict) -> bool:
    return not context.get("blocked", False) and bool(action)
