from __future__ import annotations

import time
from typing import Optional, Dict, Any

import requests

from .env import (
    get_firebase_web_api_key,
    get_firebase_user_email,
    get_firebase_user_password,
)

IDENTITY_ENDPOINT = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
REFRESH_ENDPOINT = "https://securetoken.googleapis.com/v1/token"


class FirebaseUserAuth:
    """Simple helper to obtain and cache Firebase ID token for email/password user.

    Not used if service account (firebase_admin) is initialized.
    """

    def __init__(self):
        self._id_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._expiry_ts: float = 0.0  # unix timestamp of expiry

    def _sign_in(self) -> None:
        api_key = get_firebase_web_api_key()
        email = get_firebase_user_email()
        password = get_firebase_user_password()
        if not api_key or not email or not password:
            return
        try:
            resp = requests.post(
                f"{IDENTITY_ENDPOINT}?key={api_key}",
                json={"email": email, "password": password, "returnSecureToken": True},
                timeout=10,
            )
            resp.raise_for_status()
            j = resp.json()
            self._id_token = j.get("idToken")
            self._refresh_token = j.get("refreshToken")
            expires_in = float(j.get("expiresIn", 3600))
            self._expiry_ts = time.time() + expires_in - 30  # subtract small buffer
        except Exception:
            # leave tokens None on failure
            self._id_token = None
            self._refresh_token = None
            self._expiry_ts = 0.0

    def _refresh(self) -> None:
        api_key = get_firebase_web_api_key()
        if not api_key or not self._refresh_token:
            self._sign_in()
            return
        try:
            resp = requests.post(
                f"{REFRESH_ENDPOINT}?key={api_key}",
                data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
                timeout=10,
            )
            resp.raise_for_status()
            j = resp.json()
            self._id_token = j.get("id_token")
            self._refresh_token = j.get("refresh_token", self._refresh_token)
            expires_in = float(j.get("expires_in", 3600))
            self._expiry_ts = time.time() + expires_in - 30
        except Exception:
            # fallback to sign-in if refresh fails
            self._sign_in()

    def get_id_token(self) -> Optional[str]:
        # Refresh or sign in if missing/expired
        if not self._id_token or time.time() >= self._expiry_ts:
            self._sign_in()
        return self._id_token

    def ensure_valid(self) -> Optional[str]:
        if not self._id_token or time.time() >= self._expiry_ts:
            self._refresh()
        return self._id_token


def get_firebase_id_token() -> Optional[str]:
    """Convenience function that returns a (possibly cached) idToken."""
    global _AUTH
    try:
        _AUTH  # type: ignore[name-defined]
    except NameError:
        _AUTH = FirebaseUserAuth()  # type: ignore[assignment]
    return _AUTH.ensure_valid()  # type: ignore[name-defined]
