from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv, set_key


ENV_PATH = Path(".env")


def load_env() -> None:
    load_dotenv(dotenv_path=ENV_PATH, override=False)


def get_openweather_key() -> Optional[str]:
    return os.getenv("OPENWEATHER_API_KEY")


def save_openweather_key(value: str) -> None:
    ENV_PATH.touch(exist_ok=True)
    set_key(str(ENV_PATH), "OPENWEATHER_API_KEY", value)


def get_firebase_db_url() -> Optional[str]:
    """Đọc URL Firebase Realtime Database từ biến môi trường (.env)."""
    return os.getenv("FIREBASE_DB_URL")


def save_firebase_db_url(value: str) -> None:
    """Lưu URL Firebase Realtime Database vào .env (FIREBASE_DB_URL)."""
    ENV_PATH.touch(exist_ok=True)
    set_key(str(ENV_PATH), "FIREBASE_DB_URL", value)


# Firebase Web API key (for Identity Toolkit / user sign-in)
def get_firebase_web_api_key() -> Optional[str]:
    return os.getenv("FIREBASE_WEB_API_KEY")


def save_firebase_web_api_key(value: str) -> None:
    ENV_PATH.touch(exist_ok=True)
    set_key(str(ENV_PATH), "FIREBASE_WEB_API_KEY", value)


# User email/password (optional; avoid committing real password)
def get_firebase_user_email() -> Optional[str]:
    return os.getenv("FIREBASE_USER_EMAIL")


def get_firebase_user_password() -> Optional[str]:
    return os.getenv("FIREBASE_USER_PASSWORD")


def save_firebase_user_email(value: str) -> None:
    ENV_PATH.touch(exist_ok=True)
    set_key(str(ENV_PATH), "FIREBASE_USER_EMAIL", value)


def save_firebase_user_password(value: str) -> None:
    ENV_PATH.touch(exist_ok=True)
    set_key(str(ENV_PATH), "FIREBASE_USER_PASSWORD", value)


# Service account path (.json) - do NOT commit secret file
def get_firebase_service_account_path() -> Optional[str]:
    return os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")


def save_firebase_service_account_path(value: str) -> None:
    ENV_PATH.touch(exist_ok=True)
    set_key(str(ENV_PATH), "FIREBASE_SERVICE_ACCOUNT_PATH", value)
