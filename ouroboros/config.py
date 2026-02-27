"""
Ouroboros — Shared configuration (single source of truth).

Paths, settings defaults, load/save with file locking.
Does not import anything from ouroboros.* (zero dependency level).
"""

from __future__ import annotations

import json
import importlib
import os
import pathlib
import sys
import time
from types import ModuleType
from typing import Any, IO, Optional, cast

try:
    portalocker: ModuleType | None = importlib.import_module("portalocker")
except ImportError:
    portalocker = None


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HOME = pathlib.Path.home()
APP_ROOT = HOME / "Ouroboros"
REPO_DIR = APP_ROOT / "repo"
DATA_DIR = APP_ROOT / "data"
SETTINGS_PATH = DATA_DIR / "settings.json"
PID_FILE = APP_ROOT / "ouroboros.pid"
PORT_FILE = DATA_DIR / "state" / "server_port"

RESTART_EXIT_CODE = 42
PANIC_EXIT_CODE = 99
AGENT_SERVER_PORT = 8765


# ---------------------------------------------------------------------------
# Settings defaults
# ---------------------------------------------------------------------------
SETTINGS_DEFAULTS = {
    "OPENROUTER_API_KEY": "",
    "OPENAI_API_KEY": "",
    "ANTHROPIC_API_KEY": "",
    "OUROBOROS_MODEL": "anthropic/claude-sonnet-4.6",
    "OUROBOROS_MODEL_CODE": "anthropic/claude-sonnet-4.6",
    "OUROBOROS_MODEL_LIGHT": "google/gemini-3-flash-preview",
    "OUROBOROS_MODEL_FALLBACK": "google/gemini-3-flash-preview",
    "CLAUDE_CODE_MODEL": "sonnet",
    "OUROBOROS_MAX_WORKERS": 5,
    "TOTAL_BUDGET": 10.0,
    "OUROBOROS_SOFT_TIMEOUT_SEC": 600,
    "OUROBOROS_HARD_TIMEOUT_SEC": 1800,
    "OUROBOROS_BG_MAX_ROUNDS": 5,
    "OUROBOROS_BG_WAKEUP_MIN": 30,
    "OUROBOROS_BG_WAKEUP_MAX": 7200,
    "OUROBOROS_EVO_COST_THRESHOLD": 0.10,
    "OUROBOROS_WEBSEARCH_MODEL": "gpt-5.2",
    "GITHUB_TOKEN": "",
    "GITHUB_REPO": "",
    # Local model (llama-cpp-python server)
    "LOCAL_MODEL_SOURCE": "",
    "LOCAL_MODEL_FILENAME": "",
    "LOCAL_MODEL_PORT": 8766,
    "LOCAL_MODEL_N_GPU_LAYERS": 0,
    "LOCAL_MODEL_CONTEXT_LENGTH": 16384,
    "LOCAL_MODEL_CHAT_FORMAT": "chatml-function-calling",
    "USE_LOCAL_MAIN": False,
    "USE_LOCAL_CODE": False,
    "USE_LOCAL_LIGHT": False,
    "USE_LOCAL_FALLBACK": False,
}

SettingsDict = dict[str, Any]


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
def read_version() -> str:
    try:
        if getattr(sys, "frozen", False):
            bundle_root = getattr(sys, "_MEIPASS", pathlib.Path(__file__).parent.parent)
            vp = pathlib.Path(bundle_root) / "VERSION"
        else:
            vp = pathlib.Path(__file__).parent.parent / "VERSION"
        return vp.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"


# ---------------------------------------------------------------------------
# Settings file locking
# ---------------------------------------------------------------------------
_SETTINGS_LOCK = pathlib.Path(str(SETTINGS_PATH) + ".lock")


def _acquire_settings_lock(timeout: float = 2.0) -> Optional[int]:
    start = time.time()
    while time.time() - start < timeout:
        try:
            fd = os.open(str(_SETTINGS_LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            return fd
        except FileExistsError:
            try:
                if time.time() - _SETTINGS_LOCK.stat().st_mtime > 10:
                    _SETTINGS_LOCK.unlink()
                    continue
            except Exception:
                pass
            time.sleep(0.01)
        except Exception:
            break
    return None


def _release_settings_lock(fd: Optional[int]) -> None:
    if fd is not None:
        try:
            os.close(fd)
        except Exception:
            pass
    try:
        _SETTINGS_LOCK.unlink()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------
def load_settings() -> SettingsDict:
    fd = _acquire_settings_lock()
    settings: SettingsDict = dict(SETTINGS_DEFAULTS)
    try:
        if SETTINGS_PATH.exists():
            try:
                loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    settings.update(loaded)
            except Exception:
                pass
        return settings
    finally:
        _release_settings_lock(fd)


def save_settings(settings: SettingsDict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd = _acquire_settings_lock()
    try:
        try:
            tmp = SETTINGS_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(settings, indent=2), encoding="utf-8")
            os.replace(str(tmp), str(SETTINGS_PATH))
        except OSError:
            SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    finally:
        _release_settings_lock(fd)


def apply_settings_to_env(settings: SettingsDict) -> None:
    """Push settings into environment variables for supervisor modules."""
    env_keys = [
        "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "OUROBOROS_MODEL", "OUROBOROS_MODEL_CODE", "OUROBOROS_MODEL_LIGHT",
        "OUROBOROS_MODEL_FALLBACK", "CLAUDE_CODE_MODEL",
        "TOTAL_BUDGET", "GITHUB_TOKEN", "GITHUB_REPO",
        "OUROBOROS_BG_MAX_ROUNDS", "OUROBOROS_BG_WAKEUP_MIN", "OUROBOROS_BG_WAKEUP_MAX",
        "OUROBOROS_EVO_COST_THRESHOLD", "OUROBOROS_WEBSEARCH_MODEL",
        "LOCAL_MODEL_SOURCE", "LOCAL_MODEL_FILENAME",
        "LOCAL_MODEL_PORT", "LOCAL_MODEL_N_GPU_LAYERS", "LOCAL_MODEL_CONTEXT_LENGTH",
        "LOCAL_MODEL_CHAT_FORMAT",
        "USE_LOCAL_MAIN", "USE_LOCAL_CODE", "USE_LOCAL_LIGHT", "USE_LOCAL_FALLBACK",
    ]
    for k in env_keys:
        val = settings.get(k)
        if val is None or val == "":
            os.environ.pop(k, None)
        else:
            os.environ[k] = str(val)


# ---------------------------------------------------------------------------
# PID lock (single instance) — uses portalocker for cross-platform lock.
# The OS releases the lock automatically when the process dies (even SIGKILL),
# so stale lock files can never block future launches.
# ---------------------------------------------------------------------------
_lock_fd: IO[str] | None = None


def acquire_pid_lock() -> bool:
    global _lock_fd
    APP_ROOT.mkdir(parents=True, exist_ok=True)
    portalocker_module = portalocker
    if portalocker_module is None:
        # Fallback if portalocker is not installed
        try:
            _lock_fd = open(str(PID_FILE), "w")
            _lock_fd.write(str(os.getpid()))
            _lock_fd.flush()
            return True
        except (IOError, OSError):
            return False

    try:
        _lock_fd = open(str(PID_FILE), "w")
        lock_ex = cast(int, getattr(portalocker_module, "LOCK_EX"))
        lock_nb = cast(int, getattr(portalocker_module, "LOCK_NB"))
        lock_fn = cast(Any, getattr(portalocker_module, "lock"))
        lock_fn(_lock_fd, lock_ex | lock_nb)
        _lock_fd.write(str(os.getpid()))
        _lock_fd.flush()
        return True
    except Exception as e:
        lock_exception = cast(Any, getattr(portalocker_module, "LockException", None))
        if lock_exception is not None and isinstance(e, lock_exception):
            pass  # normal lock failure
        if _lock_fd:
            try:
                _lock_fd.close()
            except Exception:
                pass
            _lock_fd = None
        return False


def release_pid_lock() -> None:
    global _lock_fd
    if _lock_fd is not None:
        try:
            if portalocker is not None:
                unlock_fn = cast(Any, getattr(portalocker, "unlock"))
                unlock_fn(_lock_fd)
            _lock_fd.close()
        except Exception:
            pass
        _lock_fd = None
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
