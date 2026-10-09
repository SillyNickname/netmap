"""
NetMap - Core Test Suite
Developed by: Antigravity (Google DeepMind)
Requested and commissioned by: Andre Kajita <kajita@univap.br>
"""

import asyncio
import os
import pytest
import pytest_asyncio
from pathlib import Path
from netmap.config import Config
from netmap.auth import hash_password, verify_password
from netmap.ping_engine import PingEngine, PingResult, is_valid_target
from netmap.csv_handler import import_hosts_from_csv, SAMPLE_CSV_CONTENT
from netmap.db import init_databases, get_hosts_db, get_history_db

@pytest_asyncio.fixture(autouse=True)
async def setup_test_env(tmp_path, monkeypatch):
    test_cfg_path = tmp_path / "test_netmap.cfg"
    hosts_db_path = str(tmp_path / "test_hosts.db")
    history_db_path = str(tmp_path / "test_history.db")

    with open(test_cfg_path, "w") as f:
        f.write(f"""[server]
host = 127.0.0.1
port = 8888
secret_key = test-secret

[poller]
interval_seconds = 10
ping_threads = 5
ping_timeout = 1
ping_count = 1

[history]
retention_hours = 24

[database]
hosts_db = {hosts_db_path}
history_db = {history_db_path}
""")

    test_config = Config(config_path=test_cfg_path)
    monkeypatch.setattr("netmap.config.config", test_config)
    monkeypatch.setattr("netmap.db.config", test_config)
    monkeypatch.setattr("netmap.ping_engine.config", test_config)
    monkeypatch.setattr("netmap.api.admin.config", test_config)

    # Initialize databases for this test run
    await init_databases()
    return test_config

@pytest.mark.asyncio
async def test_config_load_and_update(setup_test_env):
    cfg = setup_test_env
    assert cfg.poller_interval_seconds == 10
    assert cfg.ping_threads == 5

    cfg.update_settings({"interval_seconds": 30, "ping_threads": 15})
    assert cfg.poller_interval_seconds == 30
    assert cfg.ping_threads == 15

    # Reload from disk
    cfg2 = Config(config_path=cfg.config_path)
    assert cfg2.poller_interval_seconds == 30
    assert cfg2.ping_threads == 15

def test_auth_password_hash():
    pw = "supersecret123"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("wrong", hashed) is False

def test_target_validation():
    assert is_valid_target("127.0.0.1") is True
    assert is_valid_target("::1") is True
    assert is_valid_target("gateway.lan") is True
    assert is_valid_target("-c 1 127.0.0.1") is False
    assert is_valid_target("; rm -rf /") is False
    assert is_valid_target("") is False
    assert is_valid_target("127.0.0.1\n") is False
    assert is_valid_target("127.0.0.1 8.8.8.8") is False
    assert is_valid_target("a" * 254) is False
    assert is_valid_target(None) is False

@pytest.mark.asyncio
async def test_csv_import_and_hierarchy():
    res = await import_hosts_from_csv(SAMPLE_CSV_CONTENT)
    assert res["success"] is True
    assert res["imported"] > 0

    async with get_hosts_db() as db:
        async with db.execute("SELECT COUNT(*) as c FROM hosts") as cur:
            count = (await cur.fetchone())["c"]
            assert count >= 10

        # Verify parent-child hierarchy link
        async with db.execute(
            """
            SELECT c.name as child, p.name as parent 
            FROM hosts c 
            JOIN hosts p ON c.parent_id = p.id 
            WHERE c.name = 'Dist-Switch-1'
            """
        ) as cur:
            row = await cur.fetchone()
            assert row is not None
            assert row["parent"] == "Core-Router-HQ"

        # Verify group created
        async with db.execute("SELECT aggregation_mode FROM groups WHERE name = 'DB-Cluster'") as cur:
            row = await cur.fetchone()
            assert row is not None
            assert row["aggregation_mode"] == "all"

@pytest.mark.asyncio
async def test_ping_engine_execution(monkeypatch):
    # Insert a test host pointing to 127.0.0.1
    async with get_hosts_db() as db:
        await db.execute(
            "INSERT INTO hosts (name, ip_address, location) VALUES (?, ?, ?)",
            ("LocalHost", "127.0.0.1", "Test-Site")
        )
        await db.commit()

    engine = PingEngine()
    async def mock_ping(host_id, ip_or_host, semaphore):
        return PingResult(host_id=host_id, is_up=True, rtt_ms=1.2)
    monkeypatch.setattr(engine, "ping_host", mock_ping)

    poll_res = await engine.execute_poll()
    assert poll_res["polled_count"] >= 1

    # Verify latest state
    assert len(engine.latest_host_status) >= 1
    local_res = next(iter(engine.latest_host_status.values()))
    assert local_res.is_up is True
    assert local_res.rtt_ms is not None

    # Verify history database wrote record
    async with get_history_db() as db:
        async with db.execute("SELECT COUNT(*) as c FROM ping_history") as cur:
            hist_count = (await cur.fetchone())["c"]
            assert hist_count >= 1

@pytest.mark.asyncio
async def test_csv_import_with_purge():
    # 1. Initial import of 10 sample hosts
    res1 = await import_hosts_from_csv(SAMPLE_CSV_CONTENT, purge_existing=False)
    assert res1["success"] is True
    assert res1["imported"] == 10

    # Poll to generate history
    engine = PingEngine()
    await engine.execute_poll()

    async with get_hosts_db() as db:
        async with db.execute("SELECT COUNT(*) as c FROM hosts") as cur:
            assert (await cur.fetchone())["c"] == 10
        async with db.execute("SELECT COUNT(*) as c FROM users") as cur:
            user_count = (await cur.fetchone())["c"]
            assert user_count >= 1

    async with get_history_db() as hdb:
        async with hdb.execute("SELECT COUNT(*) as c FROM ping_history") as cur:
            assert (await cur.fetchone())["c"] >= 10

    # 2. Import replacement CSV with purge_existing=True
    replacement_csv = """name,ip_address,location,parent,grouping,group_mode,description
New-Core-Router,127.0.0.1,New-DC,,,any,Only device after purge
"""
    res2 = await import_hosts_from_csv(replacement_csv, purge_existing=True)
    assert res2["success"] is True
    assert res2["imported"] == 1

    # 3. Verify old hosts and old history purged, only new host exists
    async with get_hosts_db() as db:
        async with db.execute("SELECT COUNT(*) as c FROM hosts") as cur:
            assert (await cur.fetchone())["c"] == 1
        async with db.execute("SELECT name FROM hosts") as cur:
            assert (await cur.fetchone())["name"] == "New-Core-Router"
        # Verify users table was preserved!
        async with db.execute("SELECT COUNT(*) as c FROM users") as cur:
            assert (await cur.fetchone())["c"] == user_count

    # Verify history was wiped
    async with get_history_db() as hdb:
        async with hdb.execute("SELECT COUNT(*) as c FROM ping_history") as cur:
            assert (await cur.fetchone())["c"] == 0

