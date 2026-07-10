from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import HTTPException, Request, Response, status

from app.config import settings

_DEFAULT_RETURN_TO = "/app"


def sanitize_return_to(path: str | None) -> str:
    """Allow only relative app paths (no open redirects)."""
    if not path:
        return _DEFAULT_RETURN_TO
    path = path.strip()
    if not path.startswith("/") or path.startswith("//"):
        return _DEFAULT_RETURN_TO
    if "://" in path or "\\" in path or "\n" in path or "\r" in path:
        return _DEFAULT_RETURN_TO
    path = path.split("?")[0].split("#")[0]
    if not path or not path.startswith("/"):
        return _DEFAULT_RETURN_TO
    return path


def issue_state(user_id: str, return_to: str | None = None) -> str:
    """Generate a signed JWT state token for OAuth CSRF protection."""
    nonce = uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(
        seconds=settings.notion_oauth_state_ttl_seconds
    )
    payload: dict = {
        "sub": user_id,
        "nonce": nonce,
        "exp": expires,
        "type": "notion_oauth",
        "return_to": sanitize_return_to(return_to),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def verify_state(state: str, request: Request) -> tuple[str, str]:
    """Validate the OAuth state JWT and the companion cookie.

    Returns (user_id, return_to).
    """
    cookie_state = request.cookies.get(settings.notion_oauth_state_cookie_name)
    if not cookie_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cookie de estado OAuth ausente. Intenta conectar de nuevo.",
        )
    if state != cookie_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado OAuth inválido (posible ataque CSRF).",
        )
    try:
        payload = jwt.decode(state, settings.secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El estado OAuth ha expirado. Intenta conectar de nuevo.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado OAuth inválido.",
        )
    if payload.get("type") != "notion_oauth":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Estado OAuth con tipo incorrecto.",
        )
    return payload["sub"], sanitize_return_to(payload.get("return_to"))


def set_state_cookie(response: Response, state: str) -> None:
    """Set the ephemeral state cookie for CSRF protection."""
    response.set_cookie(
        key=settings.notion_oauth_state_cookie_name,
        value=state,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        max_age=settings.notion_oauth_state_ttl_seconds,
        path="/",
    )


def clear_state_cookie(response: Response) -> None:
    """Delete the ephemeral state cookie."""
    response.delete_cookie(
        key=settings.notion_oauth_state_cookie_name,
        path="/",
    )
