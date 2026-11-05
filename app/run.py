"""Launcher: ``python -m app.run``. Validates configuration and refuses to start if the port is taken.

It never kills, restarts or contacts any other process (including Dreambox on port 8000).
"""
import os
import socket
import sys
import threading
import time
import webbrowser

from app import config


def port_in_use(host, port):
    """True if something is already listening. Probes with a connect; never touches the owner."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((host, port)) == 0


def _open_browser_when_ready(host, port, url):
    for _ in range(100):  # up to ~20 s
        if port_in_use(host, port):
            webbrowser.open(url)
            return
        time.sleep(0.2)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        host, port = config.host(), config.port()
    except config.ConfigError as exc:
        print(f"Craftbox configuration error: {exc}", file=sys.stderr)
        return 2
    if port_in_use(host, port):
        print(f"Craftbox cannot start: {host}:{port} is already in use by another program.\n"
              "Craftbox will not stop it. Close that program, or choose another port, e.g.\n"
              "    set CRAFTBOX_PORT=8100   (cmd)      $env:CRAFTBOX_PORT = 8100   (PowerShell)",
              file=sys.stderr)
        return 3
    import uvicorn
    url = f"http://{host}:{port}"
    print(f"Craftbox {config.VERSION} starting on {url}  (data: {config.data_dir()})")
    print(f"Ready when you see the 'app.started' line below. Open {url} in your browser. Press Ctrl+C to stop.")
    if os.environ.get("CRAFTBOX_NO_BROWSER") != "1":
        threading.Thread(target=_open_browser_when_ready, args=(host, port, url), daemon=True).start()
    uvicorn.run("app.server:app", host=host, port=port, reload="--reload" in argv, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
