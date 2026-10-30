"""Self-protection heuristics: anti-debug and sandbox/VM detection (defensive, best-effort)."""
import os, sys, platform


def debugger_attached() -> bool:
    if sys.gettrace() is not None:
        return True
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("TracerPid:"):
                    return int(line.split()[1]) != 0
    except OSError:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            return bool(ctypes.windll.kernel32.IsDebuggerPresent())
        except Exception:
            pass
    return False


def sandbox_indicators() -> list:
    found = []
    if os.path.exists("/.dockerenv") or os.environ.get("container"):
        found.append("container")
    try:
        with open("/proc/1/cgroup") as fh:
            if any(k in fh.read() for k in ("docker", "kubepods", "lxc")):
                found.append("cgroup-container")
    except OSError:
        pass
    for p in ("/sys/class/dmi/id/product_name", "/sys/class/dmi/id/sys_vendor"):
        try:
            v = open(p).read().lower()
            if any(k in v for k in ("virtualbox", "vmware", "qemu", "kvm", "xen", "hyper-v", "bochs")):
                found.append("vm:" + v.strip())
        except OSError:
            pass
    if (os.cpu_count() or 2) < 2:
        found.append("low-cpu")
    if "microsoft" in platform.release().lower():
        found.append("wsl")
    return found


def in_sandbox(threshold: int = 1) -> bool:
    return len(sandbox_indicators()) >= threshold
