import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from netmap.auth import require_admin, hash_password
from netmap.config import config
from netmap.db import get_hosts_db, get_history_db
from netmap.ping_engine import is_valid_target, ping_engine
from netmap.models import (
    HostCreate, HostUpdate,
    GroupCreate, GroupUpdate,
    UserCreate, UserUpdate,
    SettingsUpdate
)
from netmap.csv_handler import import_hosts_from_csv, export_hosts_to_csv, SAMPLE_CSV_CONTENT

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

# ----------------- HOSTS CRUD -----------------

@router.get("/hosts")
async def list_hosts(sort: Optional[str] = None, dir: Optional[str] = "asc"):
    direction = "DESC" if dir and dir.lower() == "desc" else "ASC"
    order_map = {
        "name": f"h.name COLLATE NOCASE {direction}",
        "ip": f"h.ip_address {direction}",
        "location": f"h.location COLLATE NOCASE {direction}, h.name COLLATE NOCASE {direction}",
        "parent": f"parent_name COLLATE NOCASE {direction}, h.name COLLATE NOCASE {direction}",
        "grouping": f"h.grouping COLLATE NOCASE {direction}, h.name COLLATE NOCASE {direction}",
        "status": f"h.is_active {direction}, h.name COLLATE NOCASE {direction}"
    }
    order_clause = order_map.get(sort, "h.location, h.name")
    async with get_hosts_db() as db:
        query = f"""
            SELECT h.id, h.name, h.ip_address, h.location, h.parent_id, p.name as parent_name,
                   h.grouping, g.aggregation_mode as group_mode, h.description, h.is_active,
                   h.created_at, h.updated_at
            FROM hosts h
            LEFT JOIN hosts p ON h.parent_id = p.id
            LEFT JOIN groups g ON h.grouping = g.name
            ORDER BY {order_clause}
        """
        async with db.execute(query) as cursor:
            hosts = [dict(r) for r in await cursor.fetchall()]
    return {"hosts": hosts}

@router.post("/hosts")
async def create_host(host_in: HostCreate):
    target = host_in.ip_address.strip()
    if not is_valid_target(target):
        raise HTTPException(status_code=400, detail=f"Invalid IP address or hostname target: '{target}'")

    async with get_hosts_db() as db:
        if host_in.parent_id:
            async with db.execute("SELECT id FROM hosts WHERE id = ?", (host_in.parent_id,)) as cursor:
                if not await cursor.fetchone():
                    raise HTTPException(status_code=400, detail=f"Parent host ID {host_in.parent_id} does not exist")

        if host_in.grouping:
            grp_name = host_in.grouping.strip()
            async with db.execute("SELECT name FROM groups WHERE name = ?", (grp_name,)) as cursor:
                if not await cursor.fetchone():
                    await db.execute("INSERT INTO groups (name, aggregation_mode) VALUES (?, 'any')", (grp_name,))

        cursor = await db.execute(
            """
            INSERT INTO hosts (name, ip_address, location, parent_id, grouping, description, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                host_in.name.strip(),
                target,
                host_in.location.strip(),
                host_in.parent_id,
                host_in.grouping.strip() if host_in.grouping else None,
                host_in.description.strip() if host_in.description else "",
                1 if host_in.is_active else 0
            )
        )
        await db.commit()
        new_id = cursor.lastrowid

    return {"success": True, "id": new_id, "message": "Host created successfully"}

@router.put("/hosts/{host_id}")
async def update_host(host_id: int, host_in: HostUpdate):
    async with get_hosts_db() as db:
        async with db.execute("SELECT id FROM hosts WHERE id = ?", (host_id,)) as cursor:
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="Host not found")

        updates = []
        params = []
        if host_in.name is not None:
            updates.append("name = ?")
            params.append(host_in.name.strip())
        if host_in.ip_address is not None:
            target = host_in.ip_address.strip()
            if not is_valid_target(target):
                raise HTTPException(status_code=400, detail=f"Invalid IP address or hostname: '{target}'")
            updates.append("ip_address = ?")
            params.append(target)
        if host_in.location is not None:
            updates.append("location = ?")
            params.append(host_in.location.strip())
        if host_in.parent_id is not None:
            if host_in.parent_id == host_id:
                raise HTTPException(status_code=400, detail="A host cannot be its own parent")
            if host_in.parent_id > 0:
                async with db.execute("SELECT id FROM hosts WHERE id = ?", (host_in.parent_id,)) as cursor:
                    if not await cursor.fetchone():
                        raise HTTPException(status_code=400, detail=f"Parent host ID {host_in.parent_id} does not exist")
                updates.append("parent_id = ?")
                params.append(host_in.parent_id)
            else:
                updates.append("parent_id = NULL")
        elif "parent_id" in host_in.model_fields_set and host_in.parent_id is None:
            updates.append("parent_id = NULL")

        if host_in.grouping is not None:
            grp_name = host_in.grouping.strip()
            if grp_name:
                async with db.execute("SELECT name FROM groups WHERE name = ?", (grp_name,)) as cursor:
                    if not await cursor.fetchone():
                        await db.execute("INSERT INTO groups (name, aggregation_mode) VALUES (?, 'any')", (grp_name,))
                updates.append("grouping = ?")
                params.append(grp_name)
            else:
                updates.append("grouping = NULL")
        elif "grouping" in host_in.model_fields_set and host_in.grouping is None:
            updates.append("grouping = NULL")

        if host_in.description is not None:
            updates.append("description = ?")
            params.append(host_in.description.strip())
        if host_in.is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if host_in.is_active else 0)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            sql = f"UPDATE hosts SET {', '.join(updates)} WHERE id = ?"
            params.append(host_id)
            await db.execute(sql, params)
            await db.commit()

    return {"success": True, "message": "Host updated successfully"}

@router.delete("/hosts/{host_id}")
async def delete_host(host_id: int):
    async with get_hosts_db() as db:
        await db.execute("DELETE FROM hosts WHERE id = ?", (host_id,))
        await db.commit()
    ping_engine.latest_host_status.pop(host_id, None)
    return {"success": True, "message": "Host deleted successfully"}

# ----------------- GROUPS CRUD -----------------

@router.get("/groups")
async def list_groups(sort: Optional[str] = None, dir: Optional[str] = "asc"):
    direction = "DESC" if dir and dir.lower() == "desc" else "ASC"
    order_map = {
        "name": f"g.name COLLATE NOCASE {direction}",
        "mode": f"g.aggregation_mode {direction}",
        "hosts": f"host_count {direction}",
        "description": f"g.description COLLATE NOCASE {direction}"
    }
    order_clause = order_map.get(sort, "g.name")
    async with get_hosts_db() as db:
        query = f"""
            SELECT g.name, g.aggregation_mode, g.description, COUNT(h.id) as host_count
            FROM groups g
            LEFT JOIN hosts h ON h.grouping = g.name AND h.is_active = 1
            GROUP BY g.name
            ORDER BY {order_clause}
        """
        async with db.execute(query) as cursor:
            groups = [dict(r) for r in await cursor.fetchall()]
    return {"groups": groups}

@router.post("/groups")
async def create_group(group_in: GroupCreate):
    async with get_hosts_db() as db:
        try:
            await db.execute(
                "INSERT INTO groups (name, aggregation_mode, description) VALUES (?, ?, ?)",
                (group_in.name.strip(), group_in.aggregation_mode, group_in.description or "")
            )
            await db.commit()
        except Exception:
            raise HTTPException(status_code=400, detail=f"Group '{group_in.name}' already exists")
    return {"success": True, "message": "Group created successfully"}

@router.put("/groups/{group_name}")
async def update_group(group_name: str, group_in: GroupUpdate):
    async with get_hosts_db() as db:
        updates = []
        params = []
        if group_in.aggregation_mode:
            updates.append("aggregation_mode = ?")
            params.append(group_in.aggregation_mode)
        if group_in.description is not None:
            updates.append("description = ?")
            params.append(group_in.description.strip())
        if updates:
            sql = f"UPDATE groups SET {', '.join(updates)} WHERE name = ?"
            params.append(group_name)
            await db.execute(sql, params)
            await db.commit()
    return {"success": True, "message": "Group updated successfully"}

@router.delete("/groups/{group_name}")
async def delete_group(group_name: str):
    async with get_hosts_db() as db:
        await db.execute("UPDATE hosts SET grouping = NULL WHERE grouping = ?", (group_name,))
        await db.execute("DELETE FROM groups WHERE name = ?", (group_name,))
        await db.commit()
    ping_engine.latest_group_status.pop(group_name, None)
    return {"success": True, "message": "Group deleted successfully"}

# ----------------- SETTINGS -----------------

@router.get("/settings")
async def get_settings():
    return config.to_dict()

@router.put("/settings")
async def update_settings(settings: SettingsUpdate):
    updates = {k: v for k, v in settings.model_dump().items() if v is not None}
    if updates:
        config.update_settings(updates)
    return {"success": True, "settings": config.to_dict(), "message": "Settings updated and saved to netmap.cfg"}

# ----------------- USERS -----------------

@router.get("/users")
async def list_users():
    async with get_hosts_db() as db:
        async with db.execute("SELECT id, username, role, created_at FROM users ORDER BY id") as cursor:
            users = [dict(r) for r in await cursor.fetchall()]
    return {"users": users}

@router.post("/users")
async def create_user(user_in: UserCreate):
    async with get_hosts_db() as db:
        pwd_hash = hash_password(user_in.password)
        try:
            await db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (user_in.username.strip(), pwd_hash, user_in.role)
            )
            await db.commit()
        except Exception:
            raise HTTPException(status_code=400, detail=f"Username '{user_in.username}' already exists")
    return {"success": True, "message": "User created successfully"}

@router.put("/users/{user_id}")
async def update_user(user_id: int, user_in: UserUpdate):
    async with get_hosts_db() as db:
        async with db.execute("SELECT id, role FROM users WHERE id = ?", (user_id,)) as cursor:
            target_user = await cursor.fetchone()
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")

        if target_user["role"] == "admin" and user_in.role == "operator":
            async with db.execute("SELECT COUNT(*) as c FROM users WHERE role = 'admin'") as cursor:
                admin_count = (await cursor.fetchone())["c"]
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot demote the last administrator account")

        updates = []
        params = []
        if user_in.password:
            updates.append("password_hash = ?")
            params.append(hash_password(user_in.password))
        if user_in.role:
            updates.append("role = ?")
            params.append(user_in.role)
        if updates:
            sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            params.append(user_id)
            await db.execute(sql, params)
            await db.commit()
    return {"success": True, "message": "User updated successfully"}

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin_user: dict = Depends(require_admin)):
    if admin_user["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own user account")
    async with get_hosts_db() as db:
        async with db.execute("SELECT id, role FROM users WHERE id = ?", (user_id,)) as cursor:
            target_user = await cursor.fetchone()
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        if target_user["role"] == "admin":
            async with db.execute("SELECT COUNT(*) as c FROM users WHERE role = 'admin'") as cursor:
                admin_count = (await cursor.fetchone())["c"]
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot delete the last administrator account")
        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
    return {"success": True, "message": "User deleted successfully"}

# ----------------- CSV IMPORT & EXPORT -----------------

MAX_CSV_SIZE = 10 * 1024 * 1024  # 10 MB maximum

@router.post("/csv/import")
async def import_csv_file(
    file: Optional[UploadFile] = File(None),
    csv_text: Optional[str] = Form(None),
    purge_existing: bool = Form(False)
):
    content = ""
    if file:
        content_bytes = await file.read(MAX_CSV_SIZE + 1)
        if len(content_bytes) > MAX_CSV_SIZE:
            raise HTTPException(status_code=413, detail="CSV file too large (maximum size 10 MB)")
        content = content_bytes.decode("utf-8", errors="ignore")
    elif csv_text:
        if len(csv_text.encode("utf-8")) > MAX_CSV_SIZE:
            raise HTTPException(status_code=413, detail="CSV content too large (maximum size 10 MB)")
        content = csv_text
    else:
        raise HTTPException(status_code=400, detail="No CSV file or text provided")

    try:
        result = await import_hosts_from_csv(content, purge_existing=purge_existing)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

@router.get("/csv/export")
async def export_csv():
    csv_content = await export_hosts_to_csv()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=netmap_hosts.csv"}
    )

@router.get("/csv/template")
async def get_csv_template():
    return Response(
        content=SAMPLE_CSV_CONTENT,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=netmap_template.csv"}
    )

# ----------------- MAINTENANCE & STATS -----------------

@router.get("/maintenance/stats")
async def get_system_stats():
    hosts_db_size = os.path.getsize(config.hosts_db_path) if os.path.exists(config.hosts_db_path) else 0
    hist_db_size = os.path.getsize(config.history_db_path) if os.path.exists(config.history_db_path) else 0

    async with get_hosts_db() as db:
        async with db.execute("SELECT COUNT(*) as c FROM hosts") as cur:
            hosts_count = (await cur.fetchone())["c"]
        async with db.execute("SELECT COUNT(*) as c FROM groups") as cur:
            groups_count = (await cur.fetchone())["c"]
        async with db.execute("SELECT COUNT(*) as c FROM users") as cur:
            users_count = (await cur.fetchone())["c"]

    async with get_history_db() as db:
        async with db.execute("SELECT COUNT(*) as c FROM ping_history") as cur:
            history_rows_count = (await cur.fetchone())["c"]

    return {
        "hosts_count": hosts_count,
        "groups_count": groups_count,
        "users_count": users_count,
        "history_rows_count": history_rows_count,
        "hosts_db_size_mb": round(hosts_db_size / (1024 * 1024), 2),
        "history_db_size_mb": round(hist_db_size / (1024 * 1024), 2)
    }

@router.post("/maintenance/prune")
async def manual_prune():
    pruned = await ping_engine.prune_history()
    return {"success": True, "pruned_rows": pruned, "message": f"Pruned {pruned} old history records"}
