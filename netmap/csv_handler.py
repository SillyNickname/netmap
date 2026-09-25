import csv
import io
from typing import List, Dict, Any, Tuple
from netmap.db import get_hosts_db
from netmap.ping_engine import is_valid_target

CSV_SAMPLE_HEADER = ["name", "ip_address", "location", "parent", "grouping", "group_mode", "description"]

SAMPLE_CSV_CONTENT = """name,ip_address,location,parent,grouping,group_mode,description
Core-Router-HQ,192.168.1.1,HQ Datacenter,,,any,Main Gateway
Dist-Switch-1,192.168.1.2,HQ Datacenter,Core-Router-HQ,,,Distribution Switch 1
Dist-Switch-2,192.168.1.3,HQ Datacenter,Core-Router-HQ,,,Distribution Switch 2
Web-Node-01,192.168.1.10,HQ Datacenter,Dist-Switch-1,Web-Cluster,any,Primary web frontend
Web-Node-02,192.168.1.11,HQ Datacenter,Dist-Switch-1,Web-Cluster,any,Secondary web frontend
DB-Primary,192.168.1.20,HQ Datacenter,Dist-Switch-2,DB-Cluster,all,Database Primary
DB-Replica,192.168.1.21,HQ Datacenter,Dist-Switch-2,DB-Cluster,all,Database Replica
Edge-Router-NY,10.0.0.1,New York Branch,,,any,Branch Gateway
NY-Switch-1,10.0.0.2,New York Branch,Edge-Router-NY,,,Branch Switch
NY-FileServer,10.0.0.15,New York Branch,NY-Switch-1,,,Branch Storage
"""

async def import_hosts_from_csv(csv_text: str) -> Dict[str, Any]:
    f = io.StringIO(csv_text.strip())
    reader = csv.DictReader(f)
    
    if not reader.fieldnames:
        raise ValueError("CSV file is empty or missing headers.")

    normalized_fieldnames = {k.strip().lower(): k for k in reader.fieldnames}
    
    def get_val(row: Dict[str, str], *keys: str, default: str = "") -> str:
        for k in keys:
            if k in normalized_fieldnames:
                orig_key = normalized_fieldnames[k]
                val = row.get(orig_key, "")
                if val:
                    return val.strip()
        return default

    rows = []
    line_num = 1
    errors = []
    for r in reader:
        line_num += 1
        name = get_val(r, "name", "hostname", "host")
        ip = get_val(r, "ip_address", "ip", "address", "host_ip")
        location = get_val(r, "location", "site", "datacenter", default="Default")
        parent = get_val(r, "parent", "parent_id", "parent_name", "hierarchy")
        grouping = get_val(r, "grouping", "group")
        group_mode = get_val(r, "group_mode", "aggregation_mode", default="any").lower()
        desc = get_val(r, "description", "desc", default="")

        if not name:
            errors.append(f"Line {line_num}: Host name is required.")
            continue
        if not ip:
            errors.append(f"Line {line_num}: IP address is required for '{name}'.")
            continue
        if not is_valid_target(ip):
            errors.append(f"Line {line_num}: Invalid IP address or hostname '{ip}' for '{name}'.")
            continue

        if group_mode not in ("any", "all"):
            group_mode = "any"

        rows.append({
            "name": name,
            "ip_address": ip,
            "location": location,
            "parent_raw": parent,
            "grouping": grouping if grouping else None,
            "group_mode": group_mode,
            "description": desc
        })

    if not rows and errors:
        return {"success": False, "imported": 0, "errors": errors}

    imported_count = 0
    async with get_hosts_db() as db:
        for row in rows:
            if row["grouping"]:
                await db.execute(
                    """
                    INSERT INTO groups (name, aggregation_mode)
                    VALUES (?, ?)
                    ON CONFLICT(name) DO UPDATE SET aggregation_mode = excluded.aggregation_mode
                    """,
                    (row["grouping"], row["group_mode"])
                )

        existing_hosts: Dict[str, int] = {}
        async with db.execute("SELECT id, name FROM hosts") as cursor:
            for r in await cursor.fetchall():
                existing_hosts[r["name"].lower()] = r["id"]
                existing_hosts[str(r["id"])] = r["id"]

        row_id_map: Dict[str, int] = {}
        for row in rows:
            cursor = await db.execute(
                """
                INSERT INTO hosts (name, ip_address, location, grouping, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (row["name"], row["ip_address"], row["location"], row["grouping"], row["description"])
            )
            new_id = cursor.lastrowid
            row_id_map[row["name"].lower()] = new_id
            existing_hosts[row["name"].lower()] = new_id
            existing_hosts[str(new_id)] = new_id
            imported_count += 1

        for row in rows:
            parent_raw = row["parent_raw"]
            if parent_raw:
                parent_id = None
                p_key = parent_raw.lower()
                if p_key in existing_hosts:
                    parent_id = existing_hosts[p_key]
                elif parent_raw.isdigit() and parent_raw in existing_hosts:
                    parent_id = int(parent_raw)

                if parent_id is not None:
                    host_id = row_id_map.get(row["name"].lower())
                    if host_id and host_id != parent_id:
                        await db.execute(
                            "UPDATE hosts SET parent_id = ? WHERE id = ?",
                            (parent_id, host_id)
                        )

        await db.commit()

    return {
        "success": True,
        "imported": imported_count,
        "errors": errors
    }

async def export_hosts_to_csv() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_SAMPLE_HEADER)

    async with get_hosts_db() as db:
        query = """
            SELECT h.id, h.name, h.ip_address, h.location, h.parent_id, p.name as parent_name,
                   h.grouping, g.aggregation_mode, h.description
            FROM hosts h
            LEFT JOIN hosts p ON h.parent_id = p.id
            LEFT JOIN groups g ON h.grouping = g.name
            ORDER BY h.location, h.id
        """
        async with db.execute(query) as cursor:
            for row in await cursor.fetchall():
                parent_val = row["parent_name"] if row["parent_name"] else (str(row["parent_id"]) if row["parent_id"] else "")
                group_mode = row["aggregation_mode"] if row["aggregation_mode"] else "any"
                writer.writerow([
                    row["name"],
                    row["ip_address"],
                    row["location"],
                    parent_val,
                    row["grouping"] or "",
                    group_mode,
                    row["description"] or ""
                ])

    return output.getvalue()
