"""Demo configuration, scenario dates, identities, and password policy."""
import os
from datetime import datetime, timezone

DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "BridgeDemo2026!")
SCENARIO_DATE = os.getenv("SCENARIO_DATE", "2026-10-14")

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 200

def validate_password_strength(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must not exceed {PASSWORD_MAX_LENGTH} characters.")

def get_scenario_date() -> str:
    return SCENARIO_DATE
