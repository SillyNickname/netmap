import time
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from netmap.db import get_hosts_db
from netmap.config import config
from netmap.ping_engine import ping_engine

router = APIRouter(prefix="/api", tags=["public"])

@router.get("/status")
async def get_system_status():
    async with get_hosts_db() as db:
        async with db.execute("SELECT COUNT(*) as count FROM hosts WHERE is_active = 1") as cursor:
            row = await cursor.fetchone()
            total_hosts = row["count"] if row else 0

    latest_states = ping_engine.latest_host_status
    up_count = sum(1 for res in latest_states.values() if res.is_up)
    down_count = sum(1 for res in latest_states.values() if not res.is_up)
    unpolled_count = max(0, total_hosts - len(latest_states))

    next_poll_in = None
    if ping_engine.last_poll_time:
        elapsed = int(time.time()) - ping_engine.last_poll_time
        next_poll_in = max(0, config.poller_interval_seconds - elapsed)

    return {
        "total_hosts": total_hosts,
        "hosts_up": up_count,
        "hosts_down": down_count,
        "hosts_unpolled": unpolled_count,
        "last_poll_time": ping_engine.last_poll_time,
        "next_poll_in_seconds": next_poll_in,
        "poll_interval_seconds": config.poller_interval_seconds,
        "is_polling": ping_engine.is_polling
    }

@router.get("/tree")
async def get_tree_data(location_filter: Optional[str] = Query(None)):
    async with get_hosts_db() as db:
        groups = {}
        async with db.execute("SELECT name, aggregation_mode, description FROM groups") as cursor:
            for r in await cursor.fetchall():
                groups[r["name"]] = {
                    "name": r["name"],
                    "aggregation_mode": r["aggregation_mode"],
                    "description": r["description"]
                }

        query = "SELECT id, name, ip_address, location, parent_id, grouping, description FROM hosts WHERE is_active = 1"
        params = []
        if location_filter:
            query += " AND location = ?"
            params.append(location_filter)
        query += " ORDER BY location, parent_id IS NOT NULL, id"

        async with db.execute(query, params) as cursor:
            hosts_rows = [dict(r) for r in await cursor.fetchall()]

    if not hosts_rows:
        return {"locations": [], "groups": groups}

    host_ids = [h["id"] for h in hosts_rows]
    sparklines_30m = await ping_engine.get_30m_stats(host_ids)

    hosts_by_id: Dict[int, Dict[str, Any]] = {}
    for h in hosts_rows:
        hid = h["id"]
        status_res = ping_engine.latest_host_status.get(hid)
        
        grp_name = h.get("grouping")
        grp_status = ping_engine.latest_group_status.get(grp_name) if grp_name else None

        node = {
            "id": hid,
            "name": h["name"],
            "ip_address": h["ip_address"],
            "location": h["location"],
            "parent_id": h["parent_id"],
            "grouping": grp_name,
            "group_mode": groups.get(grp_name, {}).get("aggregation_mode", "any") if grp_name else None,
            "group_status": grp_status,
            "description": h["description"] or "",
            "is_up": status_res.is_up if status_res else None,
            "rtt_ms": status_res.rtt_ms if status_res else None,
            "error_msg": status_res.error_msg if status_res else None,
            "last_checked": status_res.timestamp if status_res else None,
            "sparkline_30m": sparklines_30m.get(hid, []),
            "children": []
        }
        hosts_by_id[hid] = node

    locations_map: Dict[str, Dict[str, Any]] = {}
    
    for hid, node in hosts_by_id.items():
        loc = node["location"]
        if loc not in locations_map:
            locations_map[loc] = {
                "name": loc,
                "roots": [],
                "total_count": 0,
                "up_count": 0,
                "down_count": 0
            }
        loc_data = locations_map[loc]
        loc_data["total_count"] += 1
        if node["is_up"] is True:
            loc_data["up_count"] += 1
        elif node["is_up"] is False:
            loc_data["down_count"] += 1

        pid = node["parent_id"]
        if pid and pid in hosts_by_id and hosts_by_id[pid]["location"] == loc:
            hosts_by_id[pid]["children"].append(node)
        else:
            loc_data["roots"].append(node)

    locations_list = list(locations_map.values())
    return {
        "locations": locations_list,
        "groups": groups,
        "last_poll_time": ping_engine.last_poll_time
    }

@router.get("/hosts/{host_id}/timeline")
async def get_host_timeline(host_id: int, hours: Optional[int] = Query(None)):
    async with get_hosts_db() as db:
        query = """
            SELECT h.id, h.name, h.ip_address, h.location, h.parent_id, p.name as parent_name,
                   h.grouping, h.description
            FROM hosts h
            LEFT JOIN hosts p ON h.parent_id = p.id
            WHERE h.id = ?
        """
        async with db.execute(query, (host_id,)) as cursor:
            host_row = await cursor.fetchone()

    if not host_row:
        raise HTTPException(status_code=404, detail="Host not found")

    timeline_data = await ping_engine.get_host_history_timeline(host_id, hours=hours)
    
    latest = ping_engine.latest_host_status.get(host_id)
    return {
        "host": {
            "id": host_row["id"],
            "name": host_row["name"],
            "ip_address": host_row["ip_address"],
            "location": host_row["location"],
            "parent_id": host_row["parent_id"],
            "parent_name": host_row["parent_name"],
            "grouping": host_row["grouping"],
            "description": host_row["description"],
            "current_is_up": latest.is_up if latest else None,
            "current_rtt_ms": latest.rtt_ms if latest else None
        },
        "timeline": timeline_data
    }
