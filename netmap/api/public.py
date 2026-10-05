"""
NetMap - Network Tree Status Monitor (Public API Endpoints)
Developed by: Antigravity (Google DeepMind)
Requested and commissioned by: Andre Kajita <kajita@univap.br>
"""

import time
import asyncio
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Path
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
async def get_tree_data(location_filter: Optional[str] = Query(None, max_length=100)):
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
    sparklines_30m, downtime_6h = await asyncio.gather(
        ping_engine.get_30m_stats(host_ids),
        ping_engine.get_6h_downtime_stats(host_ids)
    )

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
            h_stat = downtime_6h.get(h["id"], {"downtime_pct": 0.0, "total_polls": 0, "down_polls": 0})
            downtime_pct = h_stat["downtime_pct"]

            # Instability thresholds (past 6h downtime):
            # > 50%: red
            # > 30%: yellow
            # > 10%: lime (greenish-yellow)
            instability_level = None
            if downtime_pct > 50.0:
                instability_level = "red"
            elif downtime_pct > 30.0:
                instability_level = "yellow"
            elif downtime_pct > 10.0:
                instability_level = "lime"

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
                "downtime_6h_pct": downtime_pct,
                "instability_level": instability_level,
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
        # Cluster member data points into polling rounds so that there is exactly ONE square per round of polling,
        # with state and color determined by the average availability of members in that round.
        all_member_points = []
        for m in members:
            for pt in sparklines_30m.get(m["id"], []):
                all_member_points.append({
                    "t": pt["t"],
                    "host_id": m["id"],
                    "up": pt["up"],
                    "rtt": pt.get("rtt")
                })
        all_member_points.sort(key=lambda x: x["t"])

        rounds = []
        for pt in all_member_points:
            if rounds and (pt["t"] - rounds[-1]["start_t"] <= 20) and (pt["host_id"] not in rounds[-1]["hosts"]):
                rounds[-1]["hosts"][pt["host_id"]] = pt
                rounds[-1]["t"] = max(rounds[-1]["t"], pt["t"])
            else:
                rounds.append({
                    "start_t": pt["t"],
                    "t": pt["t"],
                    "hosts": {pt["host_id"]: pt}
                })

        combined_sparkline = []
        for r in rounds:
            tot = max(total_count, len(r["hosts"]))
            up_cnt = sum(1 for p in r["hosts"].values() if p["up"])
            avg_up = up_cnt / tot if tot > 0 else 0.0

            # Determine state/color using the average:
            # avg == 1.0 (100% up) -> Green
            # avg == 0.0 (0% up) -> Red
            # 0.0 < avg < 1.0 (partially up) -> Yellow (Degraded)
            if avg_up == 1.0:
                pt_up, pt_deg = True, False
            elif avg_up == 0.0:
                pt_up, pt_deg = False, False
            else:
                pt_up, pt_deg = True, True

            rtts = [p["rtt"] for p in r["hosts"].values() if p.get("rtt") is not None]
            avg_round_rtt = round(sum(rtts) / len(rtts), 1) if rtts else None

            combined_sparkline.append({
                "t": r["t"],
                "up": pt_up,
                "degraded": pt_deg,
                "avg": round(avg_up, 2),
                "hosts_up": up_cnt,
                "hosts_total": tot,
                "rtt": avg_round_rtt
            })

        grp_tot_polls = sum(downtime_6h.get(m["id"], {}).get("total_polls", 0) for m in members)
        grp_down_polls = sum(downtime_6h.get(m["id"], {}).get("down_polls", 0) for m in members)
        grp_downtime_pct = round((grp_down_polls / grp_tot_polls) * 100, 1) if grp_tot_polls > 0 else 0.0

        grp_instability_level = None
        if grp_downtime_pct > 50.0:
            grp_instability_level = "red"
        elif grp_downtime_pct > 30.0:
            grp_instability_level = "yellow"
        elif grp_downtime_pct > 10.0:
            grp_instability_level = "lime"

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
            "downtime_6h_pct": grp_downtime_pct,
            "instability_level": grp_instability_level,
            "sparkline_30m": combined_sparkline,
            "children": []
        }

    # 3. Assemble locations and hierarchical tree
    devices_by_loc: Dict[str, Dict[str, int]] = {}
    for h in hosts_rows:
        loc = h["location"]
        if loc not in devices_by_loc:
            devices_by_loc[loc] = {"total": 0, "up": 0, "down": 0}
        devices_by_loc[loc]["total"] += 1
        st = ping_engine.latest_host_status.get(h["id"])
        if st and st.is_up is True:
            devices_by_loc[loc]["up"] += 1
        elif st and st.is_up is False:
            devices_by_loc[loc]["down"] += 1

    locations_map: Dict[str, Dict[str, Any]] = {}

    for node_id, node in tree_nodes.items():
        loc = node["location"]
        if loc not in locations_map:
            dev_stats = devices_by_loc.get(loc, {"total": 0, "up": 0, "down": 0})
            dev_total = dev_stats["total"]
            dev_down = dev_stats["down"]
            dev_up = dev_stats["up"]
            dev_down_pct = round((dev_down / dev_total) * 100, 1) if dev_total > 0 else 0.0

            # Warning sign thresholds:
            # Red: >= 50% down
            # Yellow: < 50% down (and > 0 devices down)
            alert_level = None
            if dev_total > 0 and dev_down > 0:
                if dev_down_pct >= 50.0:
                    alert_level = "red"
                else:
                    alert_level = "yellow"

            locations_map[loc] = {
                "name": loc,
                "roots": [],
                "total_count": 0,
                "up_count": 0,
                "down_count": 0,
                "degraded_count": 0,
                "device_total": dev_total,
                "device_up": dev_up,
                "device_down": dev_down,
                "device_down_pct": dev_down_pct,
                "alert_level": alert_level,
                "unstable_count": 0,
                "unstable_max_level": None
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

        if node.get("instability_level"):
            loc_data["unstable_count"] += 1
            lvl = node["instability_level"]
            cur_max = loc_data.get("unstable_max_level")
            severity_order = {"lime": 1, "yellow": 2, "red": 3}
            if cur_max is None or severity_order.get(lvl, 0) > severity_order.get(cur_max, 0):
                loc_data["unstable_max_level"] = lvl

        pid = node["parent_id"]
        parent_node_id = host_to_node_id.get(pid) if pid else None
        if parent_node_id and parent_node_id in tree_nodes and tree_nodes[parent_node_id]["location"] == loc:
            tree_nodes[parent_node_id]["children"].append(node)
        else:
            loc_data["roots"].append(node)

    all_dev_total = sum(d["total"] for d in devices_by_loc.values())
    all_dev_down = sum(d["down"] for d in devices_by_loc.values())
    all_dev_up = sum(d["up"] for d in devices_by_loc.values())
    all_down_pct = round((all_dev_down / all_dev_total) * 100, 1) if all_dev_total > 0 else 0.0
    all_alert_level = None
    if all_dev_total > 0 and all_dev_down > 0:
        if all_down_pct >= 50.0 or any(l.get("alert_level") == "red" for l in locations_map.values()):
            all_alert_level = "red"
        else:
            all_alert_level = "yellow"

    all_unstable_count = sum(l.get("unstable_count", 0) for l in locations_map.values())
    all_unstable_max_level = None
    severity_order = {"lime": 1, "yellow": 2, "red": 3}
    for l in locations_map.values():
        lvl = l.get("unstable_max_level")
        if lvl and (all_unstable_max_level is None or severity_order.get(lvl, 0) > severity_order.get(all_unstable_max_level, 0)):
            all_unstable_max_level = lvl

    locations_list = list(locations_map.values())
    return {
        "locations": locations_list,
        "groups": groups,
        "last_poll_time": ping_engine.last_poll_time,
        "device_summary": {
            "total": all_dev_total,
            "up": all_dev_up,
            "down": all_dev_down,
            "down_pct": all_down_pct,
            "alert_level": all_alert_level,
            "unstable_count": all_unstable_count,
            "unstable_max_level": all_unstable_max_level
        }
    }

@router.get("/hosts/{host_id}/timeline")
async def get_host_timeline(
    host_id: int, 
    hours: Optional[int] = Query(48, ge=1, le=48),
    end_time: Optional[int] = Query(None, ge=0)
):
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

    timeline_data = await ping_engine.get_host_history_timeline(host_id, hours=hours, end_time=end_time)
    
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
async def get_group_timeline(
    group_name: str = Path(..., max_length=100),
    hours: Optional[int] = Query(None, ge=1, le=48)
):
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
