from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from types import TracebackType


_LOGGER_ROOT = "qq_data_cli"
_SESSION_LOG_PATH: Path | None = None
_LATEST_LOG_PATH: Path | None = None
_INITIALIZED = False


def setup_cli_logging(state_dir: Path) -> Path:
    global _SESSION_LOG_PATH, _LATEST_LOG_PATH, _INITIALIZED
    if _INITIALIZED and _SESSION_LOG_PATH is not None:
        return _SESSION_LOG_PATH

    logs_dir = state_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_path = logs_dir / f"cli_{stamp}.log"
    latest_path = logs_dir / "cli_latest.log"

    logger = logging.getLogger(_LOGGER_ROOT)
    _clear_handlers(logger)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for path, mode in [(session_path, "a"), (latest_path, "w")]:
        handler = logging.FileHandler(path, mode=mode, encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _SESSION_LOG_PATH = session_path
    _LATEST_LOG_PATH = latest_path
    _INITIALIZED = True

    _install_exception_hooks()
    logger.info("cli_logging_ready session_log=%s latest_log=%s", session_path, latest_path)
    return session_path


def get_cli_logger(name: str | None = None) -> logging.Logger:
    if name:
        return logging.getLogger(f"{_LOGGER_ROOT}.{name}")
    return logging.getLogger(_LOGGER_ROOT)


def get_cli_log_path() -> Path | None:
    return _SESSION_LOG_PATH


def _install_exception_hooks() -> None:
    def _sys_excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        get_cli_logger("uncaught").exception(
            "uncaught_exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
        get_cli_logger("thread").exception(
            "thread_exception thread=%s",
            getattr(args.thread, "name", "<unknown>"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        threading.__excepthook__(args)

    sys.excepthook = _sys_excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_excepthook


def reset_cli_logging_for_tests() -> None:
    global _SESSION_LOG_PATH, _LATEST_LOG_PATH, _INITIALIZED
    logger = logging.getLogger(_LOGGER_ROOT)
    _clear_handlers(logger)
    _SESSION_LOG_PATH = None
    _LATEST_LOG_PATH = None
    _INITIALIZED = False


def _clear_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
