#!/usr/bin/env python3
"""Freeze ../chessx.py into a standalone binary with PyInstaller and place it where
Tauri expects the sidecar: src-tauri/binaries/chessx-engine-<rust target triple>[.exe].

Usage: python scripts/build_sidecar.py [--target <triple>]
"""
import argparse, os, platform, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESKTOP = os.path.dirname(HERE)
REPO = os.path.dirname(DESKTOP)
BIN_DIR = os.path.join(DESKTOP, "src-tauri", "binaries")
WORK = os.path.join(DESKTOP, "build", "pyinstaller")


def host_triple():
    try:
        out = subprocess.check_output(["rustc", "-vV"], text=True)
        for line in out.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    sys.exit("rustc not found: pass --target <triple>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=os.environ.get("TAURI_TARGET") or None)
    a = ap.parse_args()
    triple = a.target or host_triple()
    ext = ".exe" if "windows" in triple else ""
    cmd = [sys.executable, "-m", "PyInstaller", "--onefile", "--console", "--noconfirm", "--clean",
           "--name", "chessx-engine",
           "--paths", REPO,
           "--collect-submodules", "chessx_libs",
           "--distpath", os.path.join(WORK, "dist"),
           "--workpath", os.path.join(WORK, "work"),
           "--specpath", WORK,
           os.path.join(REPO, "chessx.py")]
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=REPO)
    os.makedirs(BIN_DIR, exist_ok=True)
    src = os.path.join(WORK, "dist", "chessx-engine" + ext)
    dst = os.path.join(BIN_DIR, "chessx-engine-" + triple + ext)
    shutil.copy2(src, dst)
    print("sidecar ->", dst, "(%.1f MB)" % (os.path.getsize(dst) / 1e6))


if __name__ == "__main__":
    main()
