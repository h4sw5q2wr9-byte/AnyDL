"""Shared fixtures for the AnyDL tests.

anydl.py decides its folders when it is loaded (from $HOME and $ANYDL_DIR),
so every test loads a fresh copy pointed at its own temporary folders.
a-Shell commands (open, view, hideKeyboard) are recorded instead of run.
"""
import functools
import http.server
import importlib.util
import os
import pathlib
import subprocess
import threading

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def anydl(tmp_path, monkeypatch):
    home = tmp_path / "home"
    base = tmp_path / "shortcuts"
    home.mkdir()
    base.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ANYDL_DIR", str(base))
    monkeypatch.setenv("COLUMNS", "40")
    monkeypatch.chdir(base)
    spec = importlib.util.spec_from_file_location("anydl_under_test", ROOT / "anydl.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    commands = []
    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if isinstance(cmd, str):            # a-Shell commands are single strings
            commands.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(module, "_pip", lambda args: True)   # never install anything
    module.commands = commands
    module.home = home
    module.base = base
    module.library = home / "Documents" / "AnyDL"
    return module


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def site(tmp_path_factory):
    """A local web site with a few files and pages to download from."""
    root = tmp_path_factory.mktemp("site")
    (root / "clip.mp4").write_bytes(os.urandom(300_000))
    (root / "big.mp4").write_bytes(b"\0" * (51 * 1024 * 1024 + 10))
    (root / "doc.pdf").write_bytes(os.urandom(50_000))
    (root / "notes.zip").write_bytes(os.urandom(40_000))
    (root / "pic.jpg").write_bytes(os.urandom(2_000))
    (root / "pic2.jpg").write_bytes(os.urandom(3_000))
    (root / "files.html").write_text(
        '<html><body><a href="doc.pdf">A</a><a href="notes.zip">B</a>'
        '<a href="doc.pdf">duplicate</a><img src="pic.jpg"></body></html>')
    (root / "one.html").write_text('<html><body><a href="doc.pdf" download>doc</a></body></html>')
    (root / "pics.html").write_text('<html><body><img src="pic.jpg"><img src="pic2.jpg"></body></html>')
    (root / "empty.html").write_text("<html><body><p>nothing</p></body></html>")
    handler = functools.partial(QuietHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()


def run_job(module, *lines):
    """Write a job like the shortcut does, run the script, return its status."""
    (module.base / "anydl_job.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    module._handed_off = False          # each real run is a fresh process
    with pytest.raises(SystemExit):
        try:
            module.main()
        finally:
            module.back_to_shortcuts()
    return (module.base / "anydl_status.txt").read_text(encoding="utf-8")
