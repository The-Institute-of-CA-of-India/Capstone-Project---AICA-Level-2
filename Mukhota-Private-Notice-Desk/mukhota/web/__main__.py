"""Entry point for the browser front end: ``python -m mukhota.web`` (run.bat does this)."""
from __future__ import annotations

import logging
import sys
import threading


def main() -> int:
    """Start logging and the network guard, then serve the page on 127.0.0.1 and open the browser."""
    from ..core.config import load_config, resolve_path
    from ..core.logging_setup import setup_logging

    cfg = load_config()
    setup_logging(resolve_path(cfg, "log_dir"))
    log = logging.getLogger("mukhota")

    from ..core import netguard

    netguard.install()
    threading.excepthook = lambda args: log.critical(
        "Unhandled thread error", exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )

    from .server import App

    App(cfg).serve()
    log.info("Mukhota web front end closed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # last resort: never show a traceback to the user
        logging.getLogger("mukhota").critical("Mukhota failed to start", exc_info=True)
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0, "Mukhota could not start. The details were saved to logs\\mukhota.log.", "Mukhota", 0x30
            )
        except Exception:
            pass
        sys.exit(1)
