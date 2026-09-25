#!/usr/bin/env python3
import sys
import uvicorn
from netmap.config import config

def main():
    print(f"==================================================")
    print(f" NetMap - High Performance Network Status Monitor")
    print(f" Server starting on http://{config.server_host}:{config.server_port}")
    print(f" Polling Interval: {config.poller_interval_seconds}s | Parallel Ping Workers: {config.ping_threads}")
    print(f" History Retention: {config.retention_hours}h")
    print(f"==================================================")
    uvicorn.run(
        "netmap.main:app",
        host=config.server_host,
        port=config.server_port,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
