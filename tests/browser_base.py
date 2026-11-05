"""Shared Playwright plumbing for the browser suites: one browser per class, a fresh server and database per test.

Uses Microsoft Edge/Chrome already installed on Windows. Skipped if Playwright or a browser is missing.
Never touches port 8000 (Dreambox), port 8099 or the real Craftbox database.
"""
import os
import socket
import sys
import tempfile
import threading
import time
import unittest

os.environ.setdefault("CRAFTBOX_LOG_LEVEL", "ERROR")
sys.path.insert(0, os.path.dirname(__file__))

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # pragma: no cover
    expect = sync_playwright = None

import uvicorn  # noqa: E402

from app.server import create_app  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipIf(sync_playwright is None, "playwright not installed (pip install -r requirements-dev.txt)")
class BrowserCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = None
        for channel in ("msedge", "chrome", None):
            try:
                cls.browser = cls.pw.chromium.launch(channel=channel) if channel else cls.pw.chromium.launch()
                break
            except Exception:
                continue
        if cls.browser is None:
            cls.pw.stop()
            raise unittest.SkipTest("no Chromium-based browser available")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop()

    def setUp(self):
        # A fresh server and database per test: tests never see each other's experiments.
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        port = free_port()
        self.base = f"http://127.0.0.1:{port}"
        self.server = uvicorn.Server(uvicorn.Config(create_app(self.tmp.name, log_to_file=False),
                                                    host="127.0.0.1", port=port, log_level="error"))
        thread = threading.Thread(target=self.server.run, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(setattr, self.server, "should_exit", True)
        for _ in range(100):
            if self.server.started:
                break
            time.sleep(0.05)
        self.context = self.browser.new_context(accept_downloads=True)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        # HTTP 4xx logged by the browser are expected in negative tests (the UI shows them); JS errors are not.
        self.page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text
                     and self.errors.append(m.text))
        self.page.goto(self.base)
        self.page.wait_for_selector("body[data-ready=true]")  # avoid load races
        self.start()
        self.addCleanup(self.context.close)

    def tearDown(self):
        self.assertEqual(self.errors, [], "browser console/page errors")

    def start(self):
        """Hook: runs after the page is ready. Subclasses may switch tabs here."""

