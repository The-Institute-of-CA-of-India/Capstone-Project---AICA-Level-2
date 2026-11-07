"""Entry point: ``python -m mukhota`` (run.bat does this)."""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path


def main() -> int:
    """Start logging, the network guard, the splash screen and the main window."""
    from .core.config import load_config, resolve_path
    from .core.logging_setup import setup_logging

    cfg = load_config()
    setup_logging(resolve_path(cfg, "log_dir"))
    log = logging.getLogger("mukhota")

    from .core import netguard

    netguard.install()

    # onnxruntime (OCR) must load before PyQt6: Qt ships an older MSVC runtime DLL
    # that otherwise makes onnxruntime fail with "DLL initialization routine failed".
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        log.exception("OCR runtime could not be preloaded")

    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QFont, QIcon
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from . import APP_NAME, FULL_TITLE, VERSION
    from .core.models import UserFacingError
    from .gui.dialogs import make_splash
    from .gui.icon import PNG_PATH, ensure_icon
    from .gui.main_window import MainWindow

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Mukhota.NoticeRedactionSuite")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(FULL_TITLE)
    app.setApplicationVersion(VERSION)
    app.setFont(QFont("Segoe UI", 10))

    def excepthook(exc_type, exc, tb) -> None:
        log.critical("Unhandled error", exc_info=(exc_type, exc, tb))
        msg = str(exc) if isinstance(exc, UserFacingError) else (
            "Something unexpected went wrong. Your original file is safe. "
            "The details were saved to logs\\mukhota.log."
        )
        QMessageBox.warning(None, APP_NAME, msg)

    sys.excepthook = excepthook
    threading.excepthook = lambda args: log.critical(
        "Unhandled thread error", exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )

    ico = ensure_icon()
    icon = QIcon(str(ico))
    app.setWindowIcon(icon)
    qss = Path(__file__).resolve().parent / "gui" / "theme.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))

    splash = make_splash(PNG_PATH)
    splash.show()
    app.processEvents()

    window = MainWindow(cfg, icon)

    def show_main() -> None:
        window.show()
        splash.finish(window)
        QTimer.singleShot(1500, window.check_due)

    QTimer.singleShot(1500, show_main)
    log.info("%s %s started", APP_NAME, VERSION)
    code = app.exec()
    log.info("%s closed", APP_NAME)
    return code


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
