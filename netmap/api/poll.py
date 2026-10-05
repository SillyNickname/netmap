"""
NetMap - Network Tree Status Monitor (Poll API Endpoints)
Developed by: Antigravity (Google DeepMind)
Requested and commissioned by: Andre Kajita <kajita@univap.br>
"""

from fastapi import APIRouter, Depends
from netmap.auth import require_authenticated
from netmap.ping_engine import ping_engine

router = APIRouter(prefix="/api/poll", tags=["poll"])

@router.post("/force")
async def force_poll(current_user: dict = Depends(require_authenticated)):
    """
    Triggers an immediate parallel poll of all active hosts.
    Protected: Only logged-in users (operator or admin) can execute this.
    """
    if ping_engine.is_polling:
        return {
            "success": True,
            "status": "in_progress",
            "message": "A polling cycle is already actively running."
        }

    result = await ping_engine.execute_poll()
    return {
        "success": True,
        "status": "completed",
        "triggered_by": current_user["username"],
        "result": result
    }

@router.get("/status")
async def poll_status():
    return {
        "is_polling": ping_engine.is_polling,
        "last_poll_time": ping_engine.last_poll_time
    }
