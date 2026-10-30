"""Optional dependencies: numpy required for procedural audio, scipy optional (numpy fallback)."""


class MissingDependency(ImportError):
    pass


def need_numpy():
    try:
        import numpy
        return numpy
    except ImportError as e:
        raise MissingDependency("chessx_libs.sounds procedural audio needs numpy: pip install numpy") from e


def scipy_signal():
    """Return scipy.signal or None (callers fall back to numpy filters)."""
    try:
        from scipy import signal
        return signal
    except ImportError:
        return None


def need_scipy():
    s = scipy_signal()
    if s is None:
        raise MissingDependency("this feature needs scipy: pip install scipy")
    return s
