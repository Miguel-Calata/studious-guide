from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.modules.auth.service import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token: str | None = None

    # 1) Cookie httpOnly (flujo frontend con credentials: include)
    token = request.cookies.get("access_token")

    # 2) Fallback a header Bearer (clientes no-browser / Swagger)
    if not token and credentials is not None:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
        )

    user_id = decode_access_token(token)

    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado",
        )

    return user
