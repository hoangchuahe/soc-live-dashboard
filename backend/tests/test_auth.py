"""
Authentication + RBAC tests.
"""

from __future__ import annotations

import os

# Force deterministic credentials before importing auth module
os.environ["ADMIN_PASSWORD"] = "admin"
os.environ["VIEWER_PASSWORD"] = "viewer"
os.environ["JWT_SECRET"] = "test-secret-do-not-use-in-prod-this-is-long-enough-for-hs256"

import pytest

from app.auth import authenticate, create_access_token, decode_token


class TestAuthenticate:
    def test_valid_admin_credentials(self):
        assert authenticate("admin", "admin") == "admin"

    def test_valid_viewer_credentials(self):
        assert authenticate("viewer", "viewer") == "viewer"

    def test_invalid_password_returns_none(self):
        assert authenticate("admin", "wrong") is None

    def test_unknown_user_returns_none(self):
        assert authenticate("ghost", "any") is None

    def test_empty_credentials_returns_none(self):
        assert authenticate("", "") is None


class TestJWT:
    def test_token_round_trip(self):
        token, ttl = create_access_token("admin", "admin")
        assert ttl > 0

        payload = decode_token(token)
        assert payload["sub"] == "admin"
        assert payload["role"] == "admin"

    def test_token_carries_role(self):
        token, _ = create_access_token("viewer", "viewer")
        payload = decode_token(token)
        assert payload["role"] == "viewer"

    def test_invalid_token_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            decode_token("not.a.valid.token")
