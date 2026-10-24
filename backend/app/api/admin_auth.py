from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.admin_sessions import (
    SESSION_TTL_SECONDS,
    create_admin_session,
    delete_admin_session,
    get_admin_session_email,
)
from app.config import settings

router = APIRouter(prefix="/auth/admin", tags=["admin-auth"])
SESSION_COOKIE = "quita_admin_session"


class AdminLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


def _configured() -> bool:
    return bool(settings.admin_email.strip()) and len(settings.admin_password) >= 12


async def require_admin_session(request: Request) -> str:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão administrativa ausente",
        )

    try:
        email = await get_admin_session_email(session_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sessões administrativas indisponíveis",
        )

    if (
        not email
        or not hmac.compare_digest(email.casefold(), settings.admin_email.strip().casefold())
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão administrativa inválida ou expirada",
        )
    return email


@router.post("/login")
async def admin_login(request: AdminLoginRequest, response: Response) -> dict[str, str | int]:
    if not _configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login administrativo não configurado. Configure QUITA_ADMIN_PASSWORD no servidor.",
        )

    expected_email = settings.admin_email.strip().casefold()
    provided_email = request.email.strip().casefold()
    valid_email = hmac.compare_digest(provided_email, expected_email)
    valid_password = hmac.compare_digest(request.password, settings.admin_password)
    if not (valid_email and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos",
        )

    try:
        session_id = await create_admin_session(expected_email)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível iniciar a sessão administrativa",
        )

    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.admin_cookie_secure,
        samesite="lax",
        path="/",
    )
    return {
        "email": expected_email,
        "role": "admin",
        "expires_in": SESSION_TTL_SECONDS,
    }


@router.get("/me")
async def admin_me(email: str = Depends(require_admin_session)) -> dict[str, str]:
    return {"email": email, "role": "admin"}


@router.post("/logout")
async def admin_logout(request: Request, response: Response) -> dict[str, bool]:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        try:
            await delete_admin_session(session_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Não foi possível encerrar a sessão administrativa",
            )
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=settings.admin_cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"logged_out": True}
