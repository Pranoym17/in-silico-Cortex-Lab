from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.dependencies import require_admin
from app.core.config import get_settings


def test_admin_access_requires_allowlisted_email(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL_ADDRESSES", "admin@example.com, second@example.com")
    get_settings.cache_clear()
    try:
        assert require_admin(SimpleNamespace(email="admin@example.com")).email == "admin@example.com"
        with pytest.raises(HTTPException) as exc:
            require_admin(SimpleNamespace(email="member@example.com"))
        assert exc.value.status_code == 403
    finally:
        get_settings.cache_clear()
