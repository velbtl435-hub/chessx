"""`strings`-like extractor + URL / email extraction.

Rule: regexes that need a double quote are built by CONCATENATION with chr(34)
outside any quotes -- never chr() inside an f-string.
"""
import re

_DQ = chr(34).encode()   # b'"'
_SQ = chr(39).encode()   # b"'"


def _printable_re(min_len: int):
    return re.compile(rb"[\x20-\x7e]{" + str(int(min_len)).encode() + rb",}")


def _utf16_re(min_len: int):
    return re.compile(rb"(?:[\x20-\x7e]\x00){" + str(int(min_len)).encode() + rb",}")


QUOTED_RE = re.compile(_DQ + rb"((?:[^" + _DQ + rb"\\\n]|\\.)*)" + _DQ)
SQUOTED_RE = re.compile(_SQ + rb"((?:[^" + _SQ + rb"\\\n]|\\.)*)" + _SQ)
# URL stops at whitespace, quotes and angle brackets
URL_RE = re.compile(rb"(?:https?|ftp)://[^\s<>" + _DQ + _SQ + rb"]+")
EMAIL_RE = re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IPV4_RE = re.compile(rb"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")


def _b(data):
    return data.encode() if isinstance(data, str) else data


def extract_strings(data, min_len: int = 4, utf16: bool = False):
    data = _b(data)
    out = [m.group().decode("ascii") for m in _printable_re(min_len).finditer(data)]
    if utf16:
        out += [m.group().decode("utf-16-le") for m in _utf16_re(min_len).finditer(data)]
    return out


def extract_quoted(data):
    data = _b(data)
    return [m.group(1).decode("utf-8", "replace") for rx in (QUOTED_RE, SQUOTED_RE) for m in rx.finditer(data)]


def extract_urls(data):
    return sorted({m.group().decode("ascii", "replace").rstrip(".,;)") for m in URL_RE.finditer(_b(data))})


def extract_emails(data):
    return sorted({m.group().decode("ascii", "replace") for m in EMAIL_RE.finditer(_b(data))})


def extract_ips(data):
    return sorted({m.group().decode() for m in IPV4_RE.finditer(_b(data))})


def indicators(data) -> dict:
    return {"urls": extract_urls(data), "emails": extract_emails(data), "ips": extract_ips(data)}


def strings_from_file(path: str, min_len: int = 4):
    with open(path, "rb") as fh:
        return extract_strings(fh.read(), min_len)


def strings_with_offsets(data, min_len: int = 4, utf16: bool = True, limit: int = 0):
    """Like `strings -t x`: list of {offset, encoding, value}, sorted by offset."""
    data = _b(data)
    out = [{"offset": m.start(), "encoding": "ascii", "value": m.group().decode("ascii")}
           for m in _printable_re(min_len).finditer(data)]
    if utf16:
        out += [{"offset": m.start(), "encoding": "utf-16le", "value": m.group().decode("utf-16-le")}
                for m in _utf16_re(min_len).finditer(data)]
    out.sort(key=lambda d: d["offset"])
    return out[:limit] if limit else out
