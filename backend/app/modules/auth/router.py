from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.modules.auth.service import (
    authenticate_user,
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    create_user,
    decode_refresh_token,
    set_auth_cookies,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await create_user(db, data)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await authenticate_user(db, data.email, data.password)
    access_token, access_expires = create_access_token(user.id)
    refresh_token, _ = create_refresh_token(user.id)
    set_auth_cookies(response, access_token, refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": access_expires,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Prioriza refresh token de cookie (flujo frontend con credentials: include).
    refresh_token = request.cookies.get("refresh_token")
    # Fallback a body (clientes no-browser / compatibilidad hacia atrás).
    if not refresh_token and body is not None:
        refresh_token = body.refresh_token

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token no encontrado",
        )

    user_id = decode_refresh_token(refresh_token)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o desactivado",
        )
    access_token, access_expires = create_access_token(user.id)
    new_refresh_token, _ = create_refresh_token(user.id)
    set_auth_cookies(response, access_token, new_refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": access_expires,
    }


@router.post("/logout")
async def logout(response: Response) -> dict:
    clear_auth_cookies(response)
    return {"detail": "Sesión cerrada"}


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user
