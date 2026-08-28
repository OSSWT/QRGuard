r"""Start the QRGuard API on the first free port.

Windows often refuses a port with WinError 10013 -- reserved by Hyper-V/WSL, or simply
still held by a previous run that was not shut down cleanly. This picks the first port
that actually binds instead of failing.

    python scripts\run_server.py
    python scripts\run_server.py --port 8080
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_PORTS = (8001, 8000, 8080, 8888, 5000, 0)  # 0 = let the OS choose


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def pick_port(preferred: int | None) -> int:
    candidates = (preferred, *CANDIDATE_PORTS) if preferred else CANDIDATE_PORTS
    for port in candidates:
        if port == 0:  # OS-assigned; always available
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                return s.getsockname()[1]
        if port_is_free(port):
            return port
        print(f"  port {port} unavailable, trying next...")
    raise SystemExit("No free port found.")


def lan_addresses() -> list[str]:
    """Best-effort list of this machine's LAN IPs, for the phone to connect to."""
    addresses: set[str] = set()
    try:
        # Opening a UDP socket to a public address reveals which local interface
        # the OS would route through, without sending anything.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            addresses.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                addresses.add(ip)
    except OSError:
        pass
    return sorted(addresses)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--no-reload", action="store_true",
                    help="disable auto-reload (slightly faster startup)")
    ap.add_argument("--lan", action="store_true",
                    help="bind 0.0.0.0 so a phone on the same Wi-Fi can reach it")
    args = ap.parse_args()

    port = pick_port(args.port)
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    sys.path.insert(0, str(ROOT / "backend"))

    print("=" * 64)
    print(f"  QRGuard API   ->  http://127.0.0.1:{port}")
    print(f"  Interactive   ->  http://127.0.0.1:{port}/docs")
    if args.lan:
        for ip in lan_addresses():
            print(f"  From a phone  ->  http://{ip}:{port}    (same Wi-Fi)")
        print("  Windows Firewall may prompt on first run — allow private networks.")
    else:
        print("  Localhost only. Use --lan to let a phone connect.")
    print("  Stop with Ctrl+C")
    print("=" * 64)

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=not args.no_reload,
        reload_dirs=[str(ROOT / "backend")],
        app_dir=str(ROOT / "backend"),
    )


if __name__ == "__main__":
    main()
