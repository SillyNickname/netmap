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
    """
    Returns hierarchical network tree data grouped by Location.
    When a grouping is set, hosts in that grouping are replaced by the Grouping name.
    If not all hosts in the group are responsive, it is marked as partially up (is_degraded=True).
    """
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

    # Separate standalone hosts and grouped hosts
    # Grouped hosts are merged by (location, parent_id, grouping) into single Group nodes
    tree_nodes: Dict[str, Dict[str, Any]] = {}
    host_to_node_id: Dict[int, str] = {}

    # 1. Bucket hosts by group key or standalone
    grouped_buckets: Dict[str, List[Dict[str, Any]]] = {}
    for h in hosts_rows:
        grp = h.get("grouping")
        if grp:
            key = f"grp:{h['location']}:{h['parent_id']}:{grp}"
            if key not in grouped_buckets:
                grouped_buckets[key] = []
            grouped_buckets[key].append(h)
        else:
            node_id = f"host:{h['id']}"
            status_res = ping_engine.latest_host_status.get(h["id"])
            tree_nodes[node_id] = {
                "id": h["id"],
                "node_id": node_id,
                "is_group": False,
                "name": h["name"],
                "ip_address": h["ip_address"],
                "location": h["location"],
                "parent_id": h["parent_id"],
                "grouping": None,
                "description": h["description"] or "",
                "is_up": status_res.is_up if status_res else None,
                "is_degraded": False,
                "rtt_ms": status_res.rtt_ms if status_res else None,
                "error_msg": status_res.error_msg if status_res else None,
                "last_checked": status_res.timestamp if status_res else None,
                "sparkline_30m": sparklines_30m.get(h["id"], []),
                "children": []
            }
            host_to_node_id[h["id"]] = node_id

    # 2. Build Group nodes replacing grouped hosts
    for key, members in grouped_buckets.items():
        first = members[0]
        grp_name = first["grouping"]
        loc = first["location"]
        pid = first["parent_id"]
        node_id = key

        # Aggregate member status
        member_statuses = []
        up_count = 0
        total_count = len(members)
        rtt_sum = 0.0
        rtt_count = 0

        for m in members:
            hid = m["id"]
            host_to_node_id[hid] = node_id
            st = ping_engine.latest_host_status.get(hid)
            is_m_up = st.is_up if st else None
            rtt = st.rtt_ms if st else None
            if is_m_up is True:
                up_count += 1
                if rtt is not None:
                    rtt_sum += rtt
                    rtt_count += 1
            member_statuses.append({
                "id": hid,
                "name": m["name"],
                "ip_address": m["ip_address"],
                "is_up": is_m_up,
                "rtt_ms": rtt
            })

        avg_rtt = round(rtt_sum / rtt_count, 1) if rtt_count > 0 else None
        
        # Partially up logic: if not all hosts are responsive -> is_degraded = True
        polled_members = sum(1 for m in member_statuses if m["is_up"] is not None)
        if total_count == 0 or polled_members == 0:
            is_grp_up = None
            is_degraded = False
        elif up_count == 0:
            is_grp_up = False
            is_degraded = False
        else:
            is_grp_up = True
            is_degraded = (up_count < total_count)

        mode = groups.get(grp_name, {}).get("aggregation_mode", "any")

        # Combine sparkline of members:
        # Group time records by timestamp
        combined_sparkline_map = {}
        for m in members:
            for pt in sparklines_30m.get(m["id"], []):
                t_val = pt["t"]
                if t_val not in combined_sparkline_map:
                    combined_sparkline_map[t_val] = {"up_count": 0, "total": 0, "rtt_sum": 0.0, "rtt_num": 0}
                entry = combined_sparkline_map[t_val]
                entry["total"] += 1
                if pt["up"]:
                    entry["up_count"] += 1
                    if pt.get("rtt") is not None:
                        entry["rtt_sum"] += pt["rtt"]
                        entry["rtt_num"] += 1

        combined_sparkline = []
        for t_val in sorted(combined_sparkline_map.keys()):
            entry = combined_sparkline_map[t_val]
            t_up = entry["up_count"]
            t_tot = entry["total"]
            pt_deg = (0 < t_up < t_tot)
            pt_up = (t_up > 0)
            pt_rtt = round(entry["rtt_sum"] / entry["rtt_num"], 1) if entry["rtt_num"] > 0 else None
            combined_sparkline.append({
                "t": t_val,
                "up": pt_up,
                "degraded": pt_deg,
                "rtt": pt_rtt
            })

        tree_nodes[node_id] = {
            "id": first["id"],
            "node_id": node_id,
            "is_group": True,
            "name": grp_name,  # Replaced with the Grouping name!
            "ip_address": ", ".join(m["ip_address"] for m in members),
            "location": loc,
            "parent_id": pid,
            "grouping": grp_name,
            "group_mode": mode,
            "hosts_total": total_count,
            "hosts_up": up_count,
            "is_up": is_grp_up,
            "is_degraded": is_degraded,  # True when not all hosts are responsive (Yellow box)
            "rtt_ms": avg_rtt,
            "error_msg": "Timeout" if is_grp_up is False else None,
            "last_checked": ping_engine.last_poll_time,
            "member_hosts": member_statuses,
            "sparkline_30m": combined_sparkline,
            "children": []
        }

    # 3. Assemble locations and hierarchical tree
    locations_map: Dict[str, Dict[str, Any]] = {}

    for node_id, node in tree_nodes.items():
        loc = node["location"]
        if loc not in locations_map:
            locations_map[loc] = {
                "name": loc,
                "roots": [],
                "total_count": 0,
                "up_count": 0,
                "down_count": 0,
                "degraded_count": 0
            }
        loc_data = locations_map[loc]
        loc_data["total_count"] += 1
        if node["is_degraded"]:
            loc_data["degraded_count"] += 1
            loc_data["up_count"] += 1
        elif node["is_up"] is True:
            loc_data["up_count"] += 1
        elif node["is_up"] is False:
            loc_data["down_count"] += 1

        pid = node["parent_id"]
        parent_node_id = host_to_node_id.get(pid) if pid else None
        if parent_node_id and parent_node_id in tree_nodes and tree_nodes[parent_node_id]["location"] == loc:
            tree_nodes[parent_node_id]["children"].append(node)
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

@router.get("/groups/{group_name}/timeline")
async def get_group_timeline(group_name: str, hours: Optional[int] = Query(None)):
    async with get_hosts_db() as db:
        async with db.execute("SELECT name, aggregation_mode, description FROM groups WHERE name = ?", (group_name,)) as cur:
            grp = await cur.fetchone()
        
        grp_data = dict(grp) if grp else {"name": group_name, "aggregation_mode": "any", "description": ""}

        async with db.execute("SELECT id, name, ip_address, location, description FROM hosts WHERE grouping = ? AND is_active = 1", (group_name,)) as cur:
            members = [dict(r) for r in await cur.fetchall()]

    member_data = []
    up_count = 0
    polled_count = 0
    for m in members:
        st = ping_engine.latest_host_status.get(m["id"])
        is_up = st.is_up if st else None
        rtt = st.rtt_ms if st else None
        if is_up is not None:
            polled_count += 1
        if is_up is True:
            up_count += 1
        member_data.append({
            "id": m["id"],
            "name": m["name"],
            "ip_address": m["ip_address"],
            "location": m["location"],
            "description": m["description"],
            "is_up": is_up,
            "rtt_ms": rtt
        })

    total = len(members)
    is_degraded = (0 < up_count < total) if polled_count > 0 else False
    mode = grp_data.get("aggregation_mode", "any")
    if polled_count == 0:
        is_grp_up = None
    elif mode == "any":
        is_grp_up = (up_count > 0)
    else:
        is_grp_up = (up_count == total and total > 0)

    return {
        "group": {
            "name": grp_data["name"],
            "aggregation_mode": mode,
            "description": grp_data.get("description", ""),
            "hosts_total": total,
            "hosts_up": up_count,
            "is_up": is_grp_up,
            "is_degraded": is_degraded,
            "members": member_data
        }
    }
