"""Detective mode: basic provenance info for a local file."""
import hashlib, os, time

MAGIC = {b"\x7fELF": "ELF", b"MZ": "PE/DOS", b"%PDF": "PDF", b"\x89PNG": "PNG",
         b"PK\x03\x04": "ZIP", b"\xff\xd8\xff": "JPEG", b"#!": "script", b"\xca\xfe\xba\xbe": "Mach-O/Java"}


def file_info(path: str) -> dict:
    with open(path, "rb") as fh:
        data = fh.read()
    st = os.stat(path)
    kind = next((v for k, v in MAGIC.items() if data.startswith(k)), "unknown")
    return {"path": path, "size": st.st_size, "type": kind,
            "sha256": hashlib.sha256(data).hexdigest(), "md5": hashlib.md5(data).hexdigest(),
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))}
