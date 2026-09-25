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
            "secret_key": "netmap-secret-key-change-in-production"
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
        self._parser["database"] = {
            "hosts_db": "data/hosts.db",
            "history_db": "data/history.db"
        }

    def _ensure_keys(self) -> None:
        defaults = {
            "server": {"host": "0.0.0.0", "port": "8080", "secret_key": "netmap-secret-key-change-in-production"},
            "poller": {"interval_seconds": "60", "ping_threads": "20", "ping_timeout": "2", "ping_count": "1"},
            "history": {"retention_hours": "48"},
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

    def update_settings(self, updates: Dict[str, Any]) -> None:
        """Update settings and persist to netmap.cfg"""
        if "server_host" in updates:
            self._parser.set("server", "host", str(updates["server_host"]).strip())
        if "server_port" in updates:
            self._parser.set("server", "port", str(int(updates["server_port"])))
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
        self.save()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server_host": self.server_host,
            "server_port": self.server_port,
            "interval_seconds": self.poller_interval_seconds,
            "ping_threads": self.ping_threads,
            "ping_timeout": self.ping_timeout,
            "ping_count": self.ping_count,
            "retention_hours": self.retention_hours,
            "hosts_db_path": self.hosts_db_path,
            "history_db_path": self.history_db_path
        }

config = Config()
