"""Shared helpers for API-centric tests."""


def assert_ok(response, expected_status=200):
    """Validate expected status and JSON content type for Flask test responses."""
    assert response.status_code == expected_status
    assert response.is_json


def assert_has_keys(payload, required_keys):
    """Validate all required keys are present in a response payload."""
    missing = [key for key in required_keys if key not in payload]
    assert not missing, f"Missing keys: {missing}"
