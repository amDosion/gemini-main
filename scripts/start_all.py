#!/usr/bin/env python3
"""
Cross-platform bootstrap + run script.

What it does:
1. Create backend virtual environment if missing
2. Install backend requirements
3. Install frontend npm dependencies
4. Start backend (uvicorn) and frontend (vite) together

Supported: macOS, Linux, Windows
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional


def _print(msg: str) -> None:
    print(msg, flush=True)


def _require_command(name: str) -> None:
    if shutil.which(name):
        return
    raise RuntimeError(f"Required command not found in PATH: {name}")


def _venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _run(cmd: List[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> None:
    _print(f"[run] ({cwd}) {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def _is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _create_venv_if_needed(backend_dir: Path, venv_dir: Path) -> Path:
    venv_python = _venv_python_path(venv_dir)
    if venv_python.exists():
        _print(f"[ok] Virtual env already exists: {venv_dir}")
        return venv_python

    _print(f"[setup] Creating virtual env: {venv_dir}")
    _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=backend_dir)
    if not venv_python.exists():
        raise RuntimeError(f"Virtual env created but python not found: {venv_python}")
    return venv_python


def _install_dependencies(root_dir: Path, backend_dir: Path, venv_python: Path) -> None:
    _print("[setup] Installing backend dependencies...")
    _run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], cwd=backend_dir)
    _run([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"], cwd=backend_dir)

    _print("[setup] Installing frontend dependencies...")
    _run(["npm", "install"], cwd=root_dir)


class ProcessGroup:
    def __init__(self) -> None:
        self._processes: List[subprocess.Popen] = []
        self._lock = threading.Lock()

    def add(self, process: subprocess.Popen) -> None:
        with self._lock:
            self._processes.append(process)

    def terminate_all(self) -> None:
        with self._lock:
            procs = list(self._processes)

        for proc in procs:
            if proc.poll() is not None:
                continue
            self._terminate_process_tree(proc)

    @staticmethod
    def _terminate_process_tree(proc: subprocess.Popen) -> None:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                os.killpg(proc.pid, signal.SIGTERM)
                time.sleep(0.2)
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _spawn(cmd: List[str], cwd: Path, env: Dict[str, str]) -> subprocess.Popen:
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return subprocess.Popen(cmd, cwd=str(cwd), env=env, creationflags=flags)

    return subprocess.Popen(cmd, cwd=str(cwd), env=env, preexec_fn=os.setsid)


def _start_services(
    root_dir: Path,
    backend_dir: Path,
    venv_python: Path,
    host: str,
    backend_port: int,
    frontend_port: int,
    reload_backend: bool,
) -> int:
    if not _is_port_available(backend_port):
        raise RuntimeError(f"Backend port {backend_port} is already in use")
    if not _is_port_available(frontend_port):
        raise RuntimeError(f"Frontend port {frontend_port} is already in use")

    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"

    backend_cmd = [
        str(venv_python),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(backend_port),
        "--log-level",
        "info",
    ]
    if reload_backend:
        backend_cmd.extend(["--reload", "--reload-dir", "app"])

    frontend_cmd = [
        "npx",
        "vite",
        "--host",
        host,
        "--port",
        str(frontend_port),
        "--strictPort",
    ]

    group = ProcessGroup()

    _print("[start] Starting backend...")
    backend_proc = _spawn(backend_cmd, cwd=backend_dir, env=env)
    group.add(backend_proc)

    _print("[start] Starting frontend...")
    frontend_proc = _spawn(frontend_cmd, cwd=root_dir, env=env)
    group.add(frontend_proc)

    _print("[ready] Services launched")
    _print(f"        Backend:  http://{host}:{backend_port}")
    _print(f"        Frontend: http://{host}:{frontend_port}")
    _print("[hint] Press Ctrl+C to stop both services")

    stopping = {"value": False}

    def _handle_stop(_signum: int, _frame) -> None:  # type: ignore[no-untyped-def]
        if stopping["value"]:
            return
        stopping["value"] = True
        _print("\n[stop] Stopping services...")
        group.terminate_all()

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    exit_code = 0
    try:
        while True:
            backend_code = backend_proc.poll()
            frontend_code = frontend_proc.poll()

            if backend_code is not None:
                exit_code = int(backend_code)
                _print(f"[exit] Backend exited with code {backend_code}")
                group.terminate_all()
                break

            if frontend_code is not None:
                exit_code = int(frontend_code)
                _print(f"[exit] Frontend exited with code {frontend_code}")
                group.terminate_all()
                break

            time.sleep(0.4)
    finally:
        group.terminate_all()

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap and start backend + frontend")
    parser.add_argument("--host", default="0.0.0.0", help="Host for backend/frontend")
    parser.add_argument("--backend-port", type=int, default=21574, help="Backend port")
    parser.add_argument("--frontend-port", type=int, default=21573, help="Frontend port")
    parser.add_argument("--skip-install", action="store_true", help="Skip dependency installation")
    parser.add_argument("--no-backend-reload", action="store_true", help="Disable uvicorn --reload")
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parents[1]
    backend_dir = root_dir / "backend"
    venv_dir = backend_dir / ".venv"

    if not backend_dir.exists():
        raise RuntimeError(f"Backend directory not found: {backend_dir}")

    _require_command("npm")
    _require_command("npx")

    venv_python = _create_venv_if_needed(backend_dir=backend_dir, venv_dir=venv_dir)

    if not args.skip_install:
        _install_dependencies(root_dir=root_dir, backend_dir=backend_dir, venv_python=venv_python)

    return _start_services(
        root_dir=root_dir,
        backend_dir=backend_dir,
        venv_python=venv_python,
        host=args.host,
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        reload_backend=not args.no_backend_reload,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        _print(f"[error] Command failed with exit code {exc.returncode}")
        raise SystemExit(exc.returncode)
    except Exception as exc:
        _print(f"[error] {exc}")
        raise SystemExit(1)
