"""
NetMap - Network Tree Status Monitor (Configuration Manager)
Developed by: Antigravity (Google DeepMind)
Requested and commissioned by: Andre Kajita <kajita@univap.br>
"""

import os
import configparser
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG_PATH = Path("netmap.cfg")

class Config:
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self._parser = configparser.ConfigParser()
        self.load()

    def load(self) -> None:
        if not self.config_path.exists():
            self._set_defaults()
            self.save()
        else:
            self._parser.read(self.config_path)
            self._ensure_keys()

    def _set_defaults(self) -> None:
        self._parser["server"] = {
            "host": "0.0.0.0",
            "port": "8080",
            "secret_key": "netmap-secret-key-change-in-production",
            "url_prefix": ""
        }
        self._parser["poller"] = {
            "interval_seconds": "60",
            "ping_threads": "20",
            "ping_timeout": "2",
            "ping_count": "1"
        }
        self._parser["history"] = {
            "retention_hours": "48"
        }
        self._parser["speedtest"] = {
            "enabled": "true",
            "server_url": "",
            "duration_seconds": "5",
            "visitor_cooldown_hours": "2"
        }
        self._parser["database"] = {
            "hosts_db": "data/hosts.db",
            "history_db": "data/history.db"
        }

    def _ensure_keys(self) -> None:
        defaults = {
            "server": {"host": "0.0.0.0", "port": "8080", "secret_key": "netmap-secret-key-change-in-production", "url_prefix": ""},
            "poller": {"interval_seconds": "60", "ping_threads": "20", "ping_timeout": "2", "ping_count": "1"},
            "history": {"retention_hours": "48"},
            "speedtest": {"enabled": "true", "server_url": "", "duration_seconds": "5", "visitor_cooldown_hours": "2"},
            "database": {"hosts_db": "data/hosts.db", "history_db": "data/history.db"}
        }
        changed = False
        for section, keys in defaults.items():
            if not self._parser.has_section(section):
                self._parser.add_section(section)
                changed = True
            for key, val in keys.items():
                if not self._parser.has_option(section, key):
                    self._parser.set(section, key, str(val))
                    changed = True
        if changed:
            self.save()

    def save(self) -> None:
        with open(self.config_path, "w") as f:
            self._parser.write(f)

    # Server settings
    @property
    def server_host(self) -> str:
        return self._parser.get("server", "host", fallback="0.0.0.0")

    @property
    def server_port(self) -> int:
        return self._parser.getint("server", "port", fallback=8080)

    @property
    def secret_key(self) -> str:
        return self._parser.get("server", "secret_key", fallback="netmap-secret-key-change-in-production")

    @property
    def url_prefix(self) -> str:
        prefix = self._parser.get("server", "url_prefix", fallback="").strip()
        if prefix and not prefix.startswith("/"):
            prefix = "/" + prefix
        return prefix.rstrip("/")

    # Poller settings
    @property
    def poller_interval_seconds(self) -> int:
        return max(5, self._parser.getint("poller", "interval_seconds", fallback=60))

    @property
    def ping_threads(self) -> int:
        return max(1, self._parser.getint("poller", "ping_threads", fallback=20))

    @property
    def ping_timeout(self) -> int:
        return max(1, self._parser.getint("poller", "ping_timeout", fallback=2))

    @property
    def ping_count(self) -> int:
        return max(1, self._parser.getint("poller", "ping_count", fallback=1))

    # History settings
    @property
    def retention_hours(self) -> int:
        return max(24, self._parser.getint("history", "retention_hours", fallback=48))

    # Database settings
    @property
    def hosts_db_path(self) -> str:
        return self._parser.get("database", "hosts_db", fallback="data/hosts.db")

    @property
    def history_db_path(self) -> str:
        return self._parser.get("database", "history_db", fallback="data/history.db")

    # Speedtest settings
    @property
    def speedtest_enabled(self) -> bool:
        return self._parser.getboolean("speedtest", "enabled", fallback=True)

    @property
    def speedtest_server_url(self) -> str:
        return self._parser.get("speedtest", "server_url", fallback="").strip()

    @property
    def speedtest_duration_seconds(self) -> int:
        return self._parser.getint("speedtest", "duration_seconds", fallback=5)

    @property
    def speedtest_visitor_cooldown_hours(self) -> int:
        return self._parser.getint("speedtest", "visitor_cooldown_hours", fallback=2)

    def update_settings(self, updates: Dict[str, Any]) -> None:
        """Update settings and persist to netmap.cfg"""
        if "server_host" in updates:
            self._parser.set("server", "host", str(updates["server_host"]).strip())
        if "server_port" in updates:
            self._parser.set("server", "port", str(int(updates["server_port"])))
        if "url_prefix" in updates:
            raw_prefix = str(updates["url_prefix"]).strip()
            if raw_prefix and not raw_prefix.startswith("/"):
                raw_prefix = "/" + raw_prefix
            self._parser.set("server", "url_prefix", raw_prefix.rstrip("/"))
        if "interval_seconds" in updates:
            val = max(5, int(updates["interval_seconds"]))
            self._parser.set("poller", "interval_seconds", str(val))
        if "ping_threads" in updates:
            val = max(1, min(200, int(updates["ping_threads"])))
            self._parser.set("poller", "ping_threads", str(val))
        if "ping_timeout" in updates:
            val = max(1, min(10, int(updates["ping_timeout"])))
            self._parser.set("poller", "ping_timeout", str(val))
        if "ping_count" in updates:
            val = max(1, min(5, int(updates["ping_count"])))
            self._parser.set("poller", "ping_count", str(val))
        if "retention_hours" in updates:
            val = max(24, int(updates["retention_hours"]))
            self._parser.set("history", "retention_hours", str(val))
        if "speedtest_enabled" in updates:
            enabled_val = updates["speedtest_enabled"]
            if isinstance(enabled_val, bool):
                self._parser.set("speedtest", "enabled", "true" if enabled_val else "false")
            else:
                self._parser.set("speedtest", "enabled", "true" if str(enabled_val).lower() in ("true", "1", "yes") else "false")
        if "speedtest_server_url" in updates:
            self._parser.set("speedtest", "server_url", str(updates["speedtest_server_url"]).strip())
        if "speedtest_duration_seconds" in updates:
            dur = max(3, min(30, int(updates["speedtest_duration_seconds"])))
            self._parser.set("speedtest", "duration_seconds", str(dur))
        if "speedtest_visitor_cooldown_hours" in updates:
            cooldown = max(0, min(72, int(updates["speedtest_visitor_cooldown_hours"])))
            self._parser.set("speedtest", "visitor_cooldown_hours", str(cooldown))
        self.save()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server_host": self.server_host,
            "server_port": self.server_port,
            "url_prefix": self.url_prefix,
            "interval_seconds": self.poller_interval_seconds,
            "ping_threads": self.ping_threads,
            "ping_timeout": self.ping_timeout,
            "ping_count": self.ping_count,
            "retention_hours": self.retention_hours,
            "speedtest_enabled": self.speedtest_enabled,
            "speedtest_server_url": self.speedtest_server_url,
            "speedtest_duration_seconds": self.speedtest_duration_seconds,
            "speedtest_visitor_cooldown_hours": self.speedtest_visitor_cooldown_hours,
            "hosts_db_path": self.hosts_db_path,
            "history_db_path": self.history_db_path
        }

config = Config()
