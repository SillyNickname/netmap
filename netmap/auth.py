"""
NetMap - Network Tree Status Monitor (Authentication & Sessions)
Developed by: Antigravity (Google DeepMind)
Requested and commissioned by: Andre Kajita <kajita@univap.br>
"""

import time
import secrets
from typing import Optional, Dict, Any
import bcrypt
from fastapi import Request, HTTPException, status, Depends
from netmap.db import get_hosts_db

SESSION_COOKIE_NAME = "netmap_session"
SESSION_LIFETIME_SECONDS = 7 * 24 * 3600  # 7 days

def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

async def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    now = int(time.time())
    expires_at = now + SESSION_LIFETIME_SECONDS
    async with get_hosts_db() as db:
        await db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        await db.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at)
        )
        await db.commit()
    return token

async def delete_session(token: str) -> None:
    async with get_hosts_db() as db:
        await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        await db.commit()

async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        return None

    now = int(time.time())
    async with get_hosts_db() as db:
        async with db.execute(
            """
            SELECT u.id, u.username, u.role, s.expires_at 
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, now)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "username": row["username"],
                    "role": row["role"]
                }
    return None

async def require_authenticated(request: Request) -> Dict[str, Any]:
    user = await get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to perform this action"
        )
    return user

async def require_admin(request: Request) -> Dict[str, Any]:
    user = await require_authenticated(request)
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required"
        )
    return user
