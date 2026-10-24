from __future__ import annotations

import secrets

from redis.asyncio import Redis

from app.config import settings

SESSION_TTL_SECONDS = 30 * 60
SESSION_PREFIX = "quita:admin:session:"


def _redis_client() -> Redis:
    if not settings.redis_url:
        raise RuntimeError("Redis de sessões administrativas não configurado")
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def create_admin_session(email: str) -> str:
    session_id = secrets.token_urlsafe(32)
    client = _redis_client()
    try:
        await client.set(
            f"{SESSION_PREFIX}{session_id}",
            email,
            ex=SESSION_TTL_SECONDS,
        )
    finally:
        await client.aclose()
    return session_id


async def get_admin_session_email(session_id: str) -> str | None:
    client = _redis_client()
    try:
        value = await client.get(f"{SESSION_PREFIX}{session_id}")
        return value if isinstance(value, str) else None
    finally:
        await client.aclose()


async def delete_admin_session(session_id: str) -> None:
    client = _redis_client()
    try:
        await client.delete(f"{SESSION_PREFIX}{session_id}")
    finally:
        await client.aclose()
