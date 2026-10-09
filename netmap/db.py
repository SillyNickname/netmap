"""
NetMap - Network Tree Status Monitor (Database Management)
Developed by: Antigravity (Google DeepMind)
Requested and commissioned by: Andre Kajita <kajita@univap.br>
"""

import os
import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from netmap.config import config

@asynccontextmanager
async def get_hosts_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    os.makedirs(os.path.dirname(config.hosts_db_path), exist_ok=True)
    async with aiosqlite.connect(config.hosts_db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        yield db

@asynccontextmanager
async def get_history_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    os.makedirs(os.path.dirname(config.history_db_path), exist_ok=True)
    async with aiosqlite.connect(config.history_db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        yield db

async def init_databases() -> None:
    # Initialize Hosts DB
    async with get_hosts_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                name TEXT PRIMARY KEY,
                aggregation_mode TEXT DEFAULT 'any' CHECK(aggregation_mode IN ('any', 'all')),
                description TEXT DEFAULT ''
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS hosts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                location TEXT NOT NULL,
                parent_id INTEGER,
                grouping TEXT,
                description TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES hosts(id) ON DELETE SET NULL,
                FOREIGN KEY (grouping) REFERENCES groups(name) ON DELETE SET NULL
            );
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_hosts_location ON hosts(location);
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_hosts_grouping ON hosts(grouping);
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_hosts_parent ON hosts(parent_id);
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'operator')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

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

        # Create default admin and operator if users table is empty
        async with db.execute("SELECT COUNT(*) as count FROM users") as cursor:
            row = await cursor.fetchone()
            if row and row["count"] == 0:
                from netmap.auth import hash_password
                admin_hash = hash_password("admin123")
                operator_hash = hash_password("operator123")
                await db.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    ("admin", admin_hash, "admin")
                )
                await db.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    ("operator", operator_hash, "operator")
                )
                await db.commit()

    # Initialize History DB
    async with get_history_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ping_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_id INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                is_up INTEGER NOT NULL,
                rtt_ms REAL,
                error_msg TEXT
            );
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_host_time 
            ON ping_history(host_id, timestamp DESC);
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_time 
            ON ping_history(timestamp);
        """)
        await db.commit()
