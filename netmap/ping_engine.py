import asyncio
import re
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from netmap.config import config
from netmap.db import get_hosts_db, get_history_db

logger = logging.getLogger("netmap.poller")

import ipaddress

HOSTNAME_REGEX = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$')
RTT_REGEX = re.compile(r'time=([\d.]+)\s*ms')
RTT_SUMMARY_REGEX = re.compile(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)/')

def is_valid_target(target: str) -> bool:
    if not target or target.startswith("-") or len(target) > 253:
        return False
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        pass
    return bool(HOSTNAME_REGEX.match(target))

class PingResult:
    def __init__(self, host_id: int, is_up: bool, rtt_ms: Optional[float] = None, error_msg: Optional[str] = None):
        self.host_id = host_id
        self.is_up = is_up
        self.rtt_ms = rtt_ms
        self.error_msg = error_msg
        self.timestamp = int(time.time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host_id": self.host_id,
            "is_up": self.is_up,
            "rtt_ms": self.rtt_ms,
            "error_msg": self.error_msg,
            "timestamp": self.timestamp
        }

class PingEngine:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._poll_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self.last_poll_time: Optional[int] = None
        self.is_polling: bool = False
        
        self.latest_host_status: Dict[int, PingResult] = {}
        self.latest_group_status: Dict[str, Dict[str, Any]] = {}

    async def ping_host(self, host_id: int, ip_or_host: str, semaphore: asyncio.Semaphore) -> PingResult:
        if not is_valid_target(ip_or_host):
            return PingResult(host_id=host_id, is_up=False, error_msg=f"Invalid IP or target: '{ip_or_host}'")

        timeout_sec = config.ping_timeout
        count = config.ping_count
        cmd = ["ping", "-c", str(count), "-W", str(timeout_sec), ip_or_host]

        async with semaphore:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout_data, stderr_data = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_sec + 2.0
                )
                stdout = stdout_data.decode("utf-8", errors="ignore")
                
                if proc.returncode == 0:
                    rtt = None
                    m = RTT_REGEX.search(stdout)
                    if m:
                        rtt = float(m.group(1))
                    else:
                        m2 = RTT_SUMMARY_REGEX.search(stdout)
                        if m2:
                            rtt = float(m2.group(1))
                    return PingResult(host_id=host_id, is_up=True, rtt_ms=rtt)
                else:
                    return PingResult(host_id=host_id, is_up=False, error_msg="Host unreachable or timed out")
            except asyncio.TimeoutError:
                return PingResult(host_id=host_id, is_up=False, error_msg="Ping subprocess execution timed out")
            except Exception as e:
                return PingResult(host_id=host_id, is_up=False, error_msg=str(e))

    async def execute_poll(self) -> Dict[str, Any]:
        async with self._lock:
            self.is_polling = True
            start_time = time.time()
            try:
                hosts = []
                groups = {}
                async with get_hosts_db() as db:
                    async with db.execute("SELECT name, aggregation_mode FROM groups") as cursor:
                        for row in await cursor.fetchall():
                            groups[row["name"]] = row["aggregation_mode"]

                    async with db.execute(
                        "SELECT id, name, ip_address, grouping, location, parent_id FROM hosts WHERE is_active = 1"
                    ) as cursor:
                        hosts = [dict(r) for r in await cursor.fetchall()]

                if not hosts:
                    self.last_poll_time = int(time.time())
                    self.is_polling = False
                    return {"polled_count": 0, "duration": round(time.time() - start_time, 2)}

                semaphore = asyncio.Semaphore(config.ping_threads)
                tasks = [
                    self.ping_host(h["id"], h["ip_address"].strip(), semaphore)
                    for h in hosts
                ]
                results: List[PingResult] = await asyncio.gather(*tasks)

                now_ts = int(time.time())
                history_rows = [
                    (res.host_id, res.timestamp, 1 if res.is_up else 0, res.rtt_ms, res.error_msg)
                    for res in results
                ]
                async with get_history_db() as hist_db:
                    await hist_db.executemany(
                        """
                        INSERT INTO ping_history (host_id, timestamp, is_up, rtt_ms, error_msg)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        history_rows
                    )
                    await hist_db.commit()

                for res in results:
                    self.latest_host_status[res.host_id] = res

                group_members: Dict[str, List[PingResult]] = {}
                for h in hosts:
                    grp = h.get("grouping")
                    if grp:
                        if grp not in group_members:
                            group_members[grp] = []
                        if h["id"] in self.latest_host_status:
                            group_members[grp].append(self.latest_host_status[h["id"]])

                new_group_status = {}
                for grp_name, members in group_members.items():
                    mode = groups.get(grp_name, "any")
                    total = len(members)
                    up_count = sum(1 for m in members if m.is_up)
                    if mode == "all":
                        is_grp_up = (up_count == total and total > 0)
                    else:
                        is_grp_up = (up_count > 0)

                    new_group_status[grp_name] = {
                        "is_up": is_grp_up,
                        "aggregation_mode": mode,
                        "hosts_total": total,
                        "hosts_up": up_count,
                        "is_degraded": (0 < up_count < total)
                    }
                self.latest_group_status = new_group_status

                await self.prune_history()

                self.last_poll_time = now_ts
                duration = round(time.time() - start_time, 2)
                logger.info(f"Poll completed: {len(results)} hosts checked in {duration}s")
                return {
                    "polled_count": len(results),
                    "duration": duration,
                    "timestamp": now_ts
                }
            finally:
                self.is_polling = False

    async def prune_history(self) -> int:
        retention_secs = config.retention_hours * 3600
        cutoff = int(time.time()) - retention_secs
        try:
            async with get_history_db() as db:
                cursor = await db.execute("DELETE FROM ping_history WHERE timestamp < ?", (cutoff,))
                pruned = cursor.rowcount
                await db.commit()
                return pruned
        except Exception as e:
            logger.error(f"Failed to prune history: {e}")
            return 0

    async def _poller_loop(self) -> None:
        logger.info("Starting background poller loop")
        await asyncio.sleep(1)
        try:
            await self.execute_poll()
        except Exception as e:
            logger.error(f"Initial poll failed: {e}")

        while not self._stop_event.is_set():
            interval = config.poller_interval_seconds
            try:
                for _ in range(interval):
                    if self._stop_event.is_set():
                        break
                    await asyncio.sleep(1)

                if not self._stop_event.is_set():
                    await self.execute_poll()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in poller loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    def start(self) -> None:
        self._stop_event.clear()
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self._poller_loop())

    def stop(self) -> None:
        self._stop_event.set()
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()

    async def get_30m_stats(self, host_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        if not host_ids:
            return {}
        
        thirty_mins_ago = int(time.time()) - 1800
        placeholders = ",".join("?" for _ in host_ids)
        query = f"""
            SELECT host_id, timestamp, is_up, rtt_ms
            FROM ping_history
            WHERE host_id IN ({placeholders}) AND timestamp >= ?
            ORDER BY timestamp ASC
        """
        params = list(host_ids) + [thirty_mins_ago]
        
        result_map: Dict[int, List[Dict[str, Any]]] = {hid: [] for hid in host_ids}
        async with get_history_db() as db:
            async with db.execute(query, params) as cursor:
                for row in await cursor.fetchall():
                    hid = row["host_id"]
                    if hid in result_map:
                        result_map[hid].append({
                            "t": row["timestamp"],
                            "up": row["is_up"] == 1,
                            "rtt": row["rtt_ms"]
                        })
        return result_map

    async def get_host_history_timeline(self, host_id: int, hours: Optional[int] = None) -> Dict[str, Any]:
        if hours is None:
            hours = config.retention_hours
        cutoff = int(time.time()) - (hours * 3600)

        async with get_history_db() as db:
            query = """
                SELECT timestamp, is_up, rtt_ms, error_msg
                FROM ping_history
                WHERE host_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """
            async with db.execute(query, (host_id, cutoff)) as cursor:
                records = [
                    {
                        "timestamp": row["timestamp"],
                        "is_up": row["is_up"] == 1,
                        "rtt_ms": row["rtt_ms"],
                        "error_msg": row["error_msg"]
                    }
                    for row in await cursor.fetchall()
                ]

        total_checks = len(records)
        up_checks = sum(1 for r in records if r["is_up"])
        uptime_pct = round((up_checks / total_checks) * 100, 2) if total_checks > 0 else 100.0

        incidents = []
        in_outage = False
        outage_start = None
        for r in records:
            if not r["is_up"] and not in_outage:
                in_outage = True
                outage_start = r["timestamp"]
            elif r["is_up"] and in_outage:
                in_outage = False
                incidents.append({
                    "start": outage_start,
                    "end": r["timestamp"],
                    "duration_seconds": r["timestamp"] - outage_start
                })
        if in_outage and outage_start:
            incidents.append({
                "start": outage_start,
                "end": None,
                "duration_seconds": int(time.time()) - outage_start
            })

        return {
            "host_id": host_id,
            "period_hours": hours,
            "total_checks": total_checks,
            "up_checks": up_checks,
            "uptime_pct": uptime_pct,
            "records": records,
            "incidents": incidents
        }

ping_engine = PingEngine()
