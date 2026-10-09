"""
NetMap - Network Speedtest API Endpoints
Developed by: Antigravity (Google DeepMind)
Requested and commissioned by: Andre Kajita <kajita@univap.br>
"""

import os
import time
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Request, Response, HTTPException, status, Query, Depends
from fastapi.responses import StreamingResponse

from netmap.config import config
from netmap.db import get_hosts_db
from netmap.auth import get_current_user_optional, require_authenticated, require_admin
from netmap.models import SpeedtestResultCreate

router = APIRouter(prefix="/api/speedtest", tags=["speedtest"])

# Pre-generate uncompressible pseudo-random buffer to minimize CPU consumption
CHUNK_SIZE = 256 * 1024  # 256 KB
_RAW_CHUNK = os.urandom(CHUNK_SIZE)


def get_client_ip(request: Request) -> str:
    """Extract real client IP address respecting reverse proxy headers"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the list is the originating client
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


async def require_operator_or_admin(request: Request) -> Dict[str, Any]:
    """Require user to be logged in with either operator or admin role"""
    user = await require_authenticated(request)
    if user["role"] not in ("admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or Administrative privileges required"
        )
    return user


async def ensure_speedtest_table(db) -> None:
    """Auto-migration helper ensuring speedtest_results exists"""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS speedtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_ip TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            ping_ms REAL,
            jitter_ms REAL,
            download_max_mbps REAL,
            download_avg_mbps REAL,
            upload_max_mbps REAL,
            upload_avg_mbps REAL,
            role TEXT NOT NULL DEFAULT 'visitor',
            user_agent TEXT
        );
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_speedtest_client_ip 
        ON speedtest_results(client_ip, timestamp DESC);
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_speedtest_timestamp 
        ON speedtest_results(timestamp DESC);
    """)
    await db.commit()


@router.get("/config")
async def get_speedtest_config(request: Request):
    """Returns configuration and visitor cooldown status for the requesting client IP"""
    if not config.speedtest_enabled:
        return {"enabled": False}

    client_ip = get_client_ip(request)
    user = await get_current_user_optional(request)
    now = int(time.time())
    cooldown_seconds = config.speedtest_visitor_cooldown_hours * 3600

    can_test = True
    cooldown_remaining = 0
    role = user["role"] if user else "visitor"

    async with get_hosts_db() as db:
        await ensure_speedtest_table(db)
        # Visitors are subject to cooldown
        if not user and cooldown_seconds > 0:
            async with db.execute(
                """
                SELECT timestamp FROM speedtest_results 
                WHERE client_ip = ? AND role = 'visitor'
                ORDER BY timestamp DESC LIMIT 1
                """,
                (client_ip,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    elapsed = now - row["timestamp"]
                    if elapsed < cooldown_seconds:
                        can_test = False
                        cooldown_remaining = int(cooldown_seconds - elapsed)

    return {
        "enabled": True,
        "client_ip": client_ip,
        "user_role": role,
        "duration_seconds": config.speedtest_duration_seconds,
        "server_url": config.speedtest_server_url,
        "can_test": can_test,
        "cooldown_remaining_seconds": cooldown_remaining,
        "visitor_cooldown_hours": config.speedtest_visitor_cooldown_hours
    }


@router.get("/ping")
async def speedtest_ping(response: Response):
    """Instant ping endpoint for latency measurement"""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Content-Encoding"] = "identity"
    return {"status": "ok", "timestamp": time.time()}


@router.get("/download")
async def speedtest_download(
    request: Request,
    bytes_count: int = Query(25 * 1024 * 1024, alias="bytes", ge=64 * 1024, le=100 * 1024 * 1024)
):
    """
    Streams raw uncompressible data chunks for download throughput testing.
    Explicitly forces no compression (identity) and disables caching.
    """
    async def chunk_generator():
        sent = 0
        while sent < bytes_count:
            if await request.is_disconnected():
                break
            to_send = min(CHUNK_SIZE, bytes_count - sent)
            chunk = _RAW_CHUNK if to_send == CHUNK_SIZE else _RAW_CHUNK[:to_send]
            yield chunk
            sent += to_send
            # Yield event loop
            await asyncio.sleep(0.001)

    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Length": str(bytes_count),
        "Content-Encoding": "identity",
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return StreamingResponse(chunk_generator(), headers=headers)


@router.post("/upload")
async def speedtest_upload(request: Request):
    """
    Receives raw binary payload stream for upload throughput testing.
    Discards bytes immediately in memory without disk I/O.
    """
    start_time = time.time()
    total_bytes = 0

    async for chunk in request.stream():
        total_bytes += len(chunk)

    duration = max(0.0001, time.time() - start_time)
    mbps = (total_bytes * 8) / (duration * 1_000_000)

    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache"
    }
    return Response(
        content=f'{{"status":"ok","received_bytes":{total_bytes},"duration_seconds":{duration:.4f},"speed_mbps":{mbps:.2f}}}',
        media_type="application/json",
        headers=headers
    )


@router.post("/results")
async def record_speedtest_result(payload: SpeedtestResultCreate, request: Request):
    """Records a completed speed test result with client IP and validation"""
    if not config.speedtest_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Speedtest module is disabled")

    client_ip = get_client_ip(request)
    user = await get_current_user_optional(request)
    now = int(time.time())
    cooldown_seconds = config.speedtest_visitor_cooldown_hours * 3600
    role = user["role"] if user else "visitor"

    user_agent = request.headers.get("User-Agent", "")[:255]

    async with get_hosts_db() as db:
        await ensure_speedtest_table(db)

        # Enforce visitor cooldown on submission
        if not user and cooldown_seconds > 0:
            async with db.execute(
                """
                SELECT timestamp FROM speedtest_results 
                WHERE client_ip = ? AND role = 'visitor'
                ORDER BY timestamp DESC LIMIT 1
                """,
                (client_ip,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    elapsed = now - row["timestamp"]
                    if elapsed < cooldown_seconds:
                        remaining = int(cooldown_seconds - elapsed)
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail=f"Visitor cooldown active. Please wait {remaining} seconds."
                        )

        cursor = await db.execute(
            """
            INSERT INTO speedtest_results 
            (client_ip, timestamp, ping_ms, jitter_ms, download_max_mbps, download_avg_mbps, upload_max_mbps, upload_avg_mbps, role, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_ip,
                now,
                payload.ping_ms,
                payload.jitter_ms,
                payload.download_max_mbps,
                payload.download_avg_mbps,
                payload.upload_max_mbps,
                payload.upload_avg_mbps,
                role,
                user_agent
            )
        )
        await db.commit()
        result_id = cursor.lastrowid

    return {
        "status": "ok",
        "id": result_id,
        "client_ip": client_ip,
        "role": role,
        "timestamp": now
    }


@router.get("/results")
async def list_speedtest_results(
    request: Request,
    search_ip: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: Dict[str, Any] = Depends(require_operator_or_admin)
):
    """
    Search and list speedtest results.
    Accessible to both Operator and Admin users.
    """
    async with get_hosts_db() as db:
        await ensure_speedtest_table(db)
        if search_ip and search_ip.strip():
            query_ip = f"%{search_ip.strip()}%"
            async with db.execute(
                "SELECT COUNT(*) as count FROM speedtest_results WHERE client_ip LIKE ?",
                (query_ip,)
            ) as cursor:
                total_row = await cursor.fetchone()
                total = total_row["count"] if total_row else 0

            async with db.execute(
                """
                SELECT id, client_ip, timestamp, ping_ms, jitter_ms, 
                       download_max_mbps, download_avg_mbps, upload_max_mbps, upload_avg_mbps, 
                       role, user_agent
                FROM speedtest_results
                WHERE client_ip LIKE ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (query_ip, limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute("SELECT COUNT(*) as count FROM speedtest_results") as cursor:
                total_row = await cursor.fetchone()
                total = total_row["count"] if total_row else 0

            async with db.execute(
                """
                SELECT id, client_ip, timestamp, ping_ms, jitter_ms, 
                       download_max_mbps, download_avg_mbps, upload_max_mbps, upload_avg_mbps, 
                       role, user_agent
                FROM speedtest_results
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "client_ip": r["client_ip"],
            "timestamp": r["timestamp"],
            "ping_ms": r["ping_ms"],
            "jitter_ms": r["jitter_ms"],
            "download_max_mbps": r["download_max_mbps"],
            "download_avg_mbps": r["download_avg_mbps"],
            "upload_max_mbps": r["upload_max_mbps"],
            "upload_avg_mbps": r["upload_avg_mbps"],
            "role": r["role"],
            "user_agent": r["user_agent"]
        })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": results
    }


@router.delete("/results/{result_id}")
async def delete_speedtest_result(
    result_id: int,
    user: Dict[str, Any] = Depends(require_admin)
):
    """Delete an individual speedtest record (Admin only)"""
    async with get_hosts_db() as db:
        await db.execute("DELETE FROM speedtest_results WHERE id = ?", (result_id,))
        await db.commit()
    return {"status": "ok", "deleted_id": result_id}
