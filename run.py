#!/usr/bin/env python3
import os
import sys

def _check_and_switch_venv():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(script_dir, ".venv", "bin", "python3")
    if sys.prefix == sys.base_prefix and os.path.isfile(venv_python) and sys.executable != venv_python:
        os.execv(venv_python, [venv_python, os.path.abspath(__file__)] + sys.argv[1:])

if __name__ == "__main__":
    _check_and_switch_venv()

try:
    import uvicorn
    import fastapi
    from netmap.config import config
except ModuleNotFoundError as e:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(script_dir, ".venv", "bin", "python3")
    print(f"\n[ERROR] Missing required Python dependency: '{e.name}'", file=sys.stderr)
    print(f"Current Python interpreter: {sys.executable}", file=sys.stderr)
    if os.path.isfile(venv_python):
        print(f"\nA dedicated virtual environment was found at: {venv_python}", file=sys.stderr)
        print("Please run NetMap using:", file=sys.stderr)
        print(f"  {venv_python} run.py", file=sys.stderr)
        print("Or activate the virtual environment first:", file=sys.stderr)
        print(f"  source {os.path.join(script_dir, '.venv', 'bin', 'activate')} && python3 run.py\n", file=sys.stderr)
    else:
        print("\nPlease install the required dependencies:", file=sys.stderr)
        print("  sudo ./install.sh", file=sys.stderr)
        print("Or manually:", file=sys.stderr)
        print("  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt\n", file=sys.stderr)
    sys.exit(1)

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
