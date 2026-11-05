"""Environment check: ``python scripts/check_env.py``. Read-only; changes nothing and contacts no one."""
import importlib
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.run import port_in_use  # noqa: E402

problems = []


def report(ok, label, detail=""):
    print(f"[{'ok' if ok else 'FAIL'}] {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        problems.append(label)


report(sys.version_info >= (3, 10), "Python >= 3.10", sys.version.split()[0])
report(sys.prefix != sys.base_prefix, "running inside a virtual environment", sys.prefix)
for module in ("fastapi", "uvicorn", "sqlite3"):
    try:
        mod = importlib.import_module(module)
        report(True, f"import {module}", getattr(mod, "__version__", ""))
    except ImportError as exc:
        report(False, f"import {module}", str(exc))
try:
    host, port = config.host(), config.port()
    report(True, "configuration", f"{host}:{port}")
    busy = port_in_use(host, port)
    print(f"[info] port {port} is {'IN USE (Craftbox may already be running, or another program owns it)' if busy else 'free'}")
except config.ConfigError as exc:
    report(False, "configuration", str(exc))
try:
    data = config.data_dir()
    data.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=data):
        pass
    report(True, "data directory writable", str(data))
except OSError as exc:
    report(False, "data directory writable", str(exc))
print(f"[info] Dreambox port {config.DREAMBOX_PORT} is {'in use (expected if Dreambox is running)' if port_in_use('127.0.0.1', config.DREAMBOX_PORT) else 'free'}; Craftbox never uses it")
try:
    importlib.import_module("playwright")
    print("[info] playwright installed: browser tests enabled")
except ImportError:
    print("[info] playwright not installed: browser tests will be skipped (pip install -r requirements-dev.txt)")
sys.exit(1 if problems else 0)
