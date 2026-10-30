"""Tiny cross-process advisory file lock (fcntl on POSIX, msvcrt on Windows). Used by keystore and
otp.JSONFileStore (CRY-04/CRY-05). Advisory: only cooperating ChessX processes honour it; same host only."""
import contextlib, os

try:
    import fcntl as _fcntl
except ImportError:  # Windows
    _fcntl = None
    import msvcrt as _msvcrt


@contextlib.contextmanager
def locked(path: str):
    """Exclusive lock on `path + '.lock'` for the duration of the with-block (blocking)."""
    fd = os.open(path + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if _fcntl:
            _fcntl.flock(fd, _fcntl.LOCK_EX)
        else:
            os.lseek(fd, 0, 0)
            _msvcrt.locking(fd, _msvcrt.LK_LOCK, 1)
        yield
    finally:
        try:
            if _fcntl:
                _fcntl.flock(fd, _fcntl.LOCK_UN)
            else:
                os.lseek(fd, 0, 0)
                _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
        finally:
            os.close(fd)
