from fastapi import APIRouter, HTTPException, Response, Request, status
from netmap.db import get_hosts_db
from netmap.auth import verify_password, create_session, delete_session, get_current_user_optional, SESSION_COOKIE_NAME, SESSION_LIFETIME_SECONDS
from netmap.models import UserLogin

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
async def login(credentials: UserLogin, response: Response):
    async with get_hosts_db() as db:
        async with db.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (credentials.username.strip(),)
        ) as cursor:
            user = await cursor.fetchone()

    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    token = await create_session(user["id"])
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_LIFETIME_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False
    )
    return {
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"]
        }
    }

@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if token:
        await delete_session(token)

    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"success": True, "message": "Logged out successfully"}

@router.get("/me")
async def get_current_user(request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}
