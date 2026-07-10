from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import HTTPException, Request, Response, status

from app.config import settings


def issue_state(user_id: str) -> str:
    """Generate a signed JWT state token for OAuth CSRF protection."""
    nonce = uuid4().hex
    expires = datetime.now(timezone.utc) + timedelta(
        seconds=settings.notion_oauth_state_ttl_seconds
    )
    payload = {
        "sub": user_id,
        "nonce": nonce,
        "exp": expires,
        "type": "notion_oauth",
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def verify_state(state: str, request: Request) -> str:
    """Validate the OAuth state JWT and the companion cookie.

    Returns the user_id embedded in the state token.
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
    return payload["sub"]


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
