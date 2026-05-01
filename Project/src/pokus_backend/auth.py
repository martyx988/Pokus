from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Mapping

from pokus_backend.settings import Settings


@dataclass(frozen=True)
class AuthResult:
    allowed: bool
    status: HTTPStatus


def required_boundary(path: str) -> str | None:
    if path == "/health":
        return None
    if path.startswith("/app/"):
        return "app"
    if path.startswith("/operator/"):
        return "operator"
    if path.startswith("/admin/"):
        return "admin"
    return None


def authorize_path(path: str, headers: Mapping[str, str], settings: Settings) -> AuthResult:
    boundary = required_boundary(path)
    if boundary is None:
        return AuthResult(allowed=True, status=HTTPStatus.OK)

    if boundary == "app":
        return _require_app_token(headers, settings)

    session_token = headers.get("X-Private-Session")
    if not session_token:
        return AuthResult(allowed=False, status=HTTPStatus.UNAUTHORIZED)

    if boundary == "operator":
        if session_token in {settings.operator_session_token, settings.admin_session_token}:
            return AuthResult(allowed=True, status=HTTPStatus.OK)
        return AuthResult(allowed=False, status=HTTPStatus.FORBIDDEN)

    if boundary == "admin":
        if session_token == settings.admin_session_token:
            return AuthResult(allowed=True, status=HTTPStatus.OK)
        return AuthResult(allowed=False, status=HTTPStatus.FORBIDDEN)

    return AuthResult(allowed=False, status=HTTPStatus.NOT_FOUND)


def _require_app_token(headers: Mapping[str, str], settings: Settings) -> AuthResult:
    app_token = headers.get("X-App-Token")
    if not app_token:
        return AuthResult(allowed=False, status=HTTPStatus.UNAUTHORIZED)
    if app_token != settings.app_read_token:
        return AuthResult(allowed=False, status=HTTPStatus.FORBIDDEN)
    return AuthResult(allowed=True, status=HTTPStatus.OK)
