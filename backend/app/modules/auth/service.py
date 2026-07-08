import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.modules.auth.schemas import RegisterRequest

_PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,128}$"
)


def _validate_password(password: str) -> None:
    if not _PASSWORD_PATTERN.match(password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "La contraseña debe tener entre 8 y 128 caracteres, "
                "al menos una mayúscula, una minúscula y un dígito."
            ),
        )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Cookies httpOnly (auth)
# ---------------------------------------------------------------------------
# NOTA DE SEGURIDAD (ver docs/11_changelog.md / futuras mejoras):
# - Las cookies son httpOnly => no accesibles vía JS (mitiga XSS robo de token).
# - `secure` debe ser True en producción (HTTPS obligatorio).
# - `samesite="lax"` es un equilibrio; si se requiere máxima protección CSRF,
#   evaluar "strict" o tokens doble-submit / SameSite=None+Secure con CORS estricto.
# - El refresh token en cookie no se invalida en backend al hacer logout
#   (no hay denylist). Mejora futura: almacenar jti en DB y validar en logout.
# - `domain=".astreo.space"` comparte la cookie entre subdominios del mismo padre;
#   no usar en desarrollo (localhost) => dejar cookie_domain=None.

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


def _cookie_domain() -> Optional[str]:
    return settings.cookie_domain or None


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: Optional[str] = None,
) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        domain=_cookie_domain(),
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    if refresh_token is not None:
        response.set_cookie(
            key=REFRESH_COOKIE,
            value=refresh_token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,  # type: ignore[arg-type]
            domain=_cookie_domain(),
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
            path="/",
        )


def clear_auth_cookies(response: Response) -> None:
    for key in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(key=key, path="/", domain=_cookie_domain())


def create_access_token(user_id: str) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return token, settings.access_token_expire_minutes * 60


def create_refresh_token(user_id: str) -> tuple[str, int]:
    expires_delta = timedelta(days=settings.refresh_token_expire_days)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": user_id, "exp": expire, "type": "refresh"}
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return token, settings.refresh_token_expire_days * 24 * 60 * 60


def decode_access_token(token: str) -> str:
    return _decode_token(token, token_type="access")


def decode_refresh_token(token: str) -> str:
    return _decode_token(token, token_type="refresh")


def _decode_token(token: str, token_type: str) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id: str | None = payload.get("sub")
        payload_type: str | None = payload.get("type")
        if user_id is None or payload_type != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )


async def create_user(db: AsyncSession, data: RegisterRequest) -> User:
    _validate_password(data.password)

    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado",
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado",
        )

    return user
