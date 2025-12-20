# pianos/automation/utils.py
from django.conf import settings

def is_allowed_customer(name: str) -> bool:
    if not getattr(settings, "AUTOMATION_SAFE_MODE", True):
        return True
    allowed = set(getattr(settings, "AUTOMATION_ALLOWED_CUSTOMER_NAMES", []))
    return (name or "").strip() in allowed
