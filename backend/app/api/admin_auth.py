from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel, EmailStr, Field

from app.config import settings

router = APIRouter(prefix="/auth/admin", tags=["admin-auth"])
bearer = HTTPBearer(auto_error=False)
_TOKEN_ISSUER = "quita-api"
_TOKEN_AUDIENCE = "quita-admin"


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _configured() -> bool:
    return (
        bool(settings.admin_email.strip())
        and len(settings.admin_password) >= 12
        and len(settings.admin_token_secret) >= 32
        and settings.admin_token_ttl_minutes > 0
    )


def issue_admin_token(email: str) -> str:
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.admin_token_ttl_minutes)
    claims = {
        "sub": email,
        "role": "admin",
        "iss": _TOKEN_ISSUER,
        "aud": _TOKEN_AUDIENCE,
        "iat": now,
        "exp": expires,
    }
    return jwt.encode(claims, settings.admin_token_secret, algorithm="HS256")


def verify_admin_token(token: str) -> str | None:
    if not _configured():
        return None
    try:
        claims = jwt.decode(
            token,
            settings.admin_token_secret,
            algorithms=["HS256"],
            issuer=_TOKEN_ISSUER,
            audience=_TOKEN_AUDIENCE,
            options={"require": ["sub", "role", "exp", "iat", "iss", "aud"]},
        )
    except InvalidTokenError:
        return None

    email = claims.get("sub")
    if claims.get("role") != "admin" or not isinstance(email, str):
        return None
    if not hmac.compare_digest(email.casefold(), settings.admin_email.strip().casefold()):
        return None
    return email


async def require_admin_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token administrativo ausente")
    email = verify_admin_token(credentials.credentials)
    if email is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token administrativo inválido ou expirado")
    return email


@router.post("/login", response_model=AdminTokenResponse)
async def admin_login(request: AdminLoginRequest) -> AdminTokenResponse:
    if not _configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login administrativo não configurado. Configure QUITA_ADMIN_PASSWORD e QUITA_ADMIN_TOKEN_SECRET no servidor.",
        )

    expected_email = settings.admin_email.strip().casefold()
    provided_email = str(request.email).strip().casefold()
    valid_email = hmac.compare_digest(provided_email, expected_email)
    valid_password = hmac.compare_digest(request.password, settings.admin_password)
    if not (valid_email and valid_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos",
        )

    return AdminTokenResponse(
        access_token=issue_admin_token(expected_email),
        expires_in=settings.admin_token_ttl_minutes * 60,
    )


@router.get("/me")
async def admin_me(email: str = Depends(require_admin_token)) -> dict[str, str]:
    return {"email": email, "role": "admin"}
