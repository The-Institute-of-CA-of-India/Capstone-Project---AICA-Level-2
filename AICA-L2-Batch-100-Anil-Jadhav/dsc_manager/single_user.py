"""This application is single-user: one PC, one person, one open copy at a time.

SQLite is safe for one user. To keep it that way, the app holds a lock on
'<database>.lock' while it is open; a second copy trying to open the same
database is refused. Windows releases the lock by itself if the app is closed
or crashes, so a stale lock never blocks the next start.
"""
import os

try:
    import msvcrt
except ImportError:  # not Windows: no lock, the note still applies
    msvcrt = None

NOTE = "This application is for use on one PC by one user at a time."


def acquire(db_path):
    """Return a lock handle, or None when another copy of the app has this database open."""
    if msvcrt is None:
        return object()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)   # a first start: the database folder is not made yet
    fh = open(db_path + ".lock", "a+")
    try:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        fh.close()
        return None
    return fh


def release(handle, db_path=None):
    if msvcrt is None or handle is None or not hasattr(handle, "fileno"):
        return
    try:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    handle.close()
    if db_path:
        try:
            os.remove(db_path + ".lock")
        except OSError:
            pass
