"""Local file metadata (offline): reuses chessx_libs.detective (hashes, indicators, provenance) and
chessx_libs.media.detect (magic sniffing) read-only via imports. Never touches the network; reverse-search
links are returned as data for the user to open, not fetched."""
import os
from urllib.parse import urlparse
from ..base import Source, SourceError, register
from ..types import Entity, Finding

MAX_RELATED = 50


@register
class FileMetadataSource(Source):
    name = "metadata"
    accepts = frozenset({"file"})
    host = "local"
    rate = (1000, 1.0)
    ttl = 0
    license = "local analysis (chessx_libs.detective / media), no network"

    def lookup(self, e, client=None):
        path = os.path.expanduser(e.value)
        if not os.path.isfile(path):
            raise SourceError("not a file: %s" % e.value)
        from ...detective import investigate as det
        from ...media.detect import detect_type, kind_of
        r = det(path)
        with open(path, "rb") as f:
            head = f.read(64)
        mime, how = detect_type(None, head, path)
        if client is not None and getattr(client, "audit", None):
            client.audit.log("local_file", source=self.name, entity=os.path.basename(path))
        meta = dict(r.get("metadata", {}), mime=mime, mime_source=how, media_kind=kind_of(mime))
        uri = "file://" + os.path.abspath(path)
        out = [Finding(e, self.name, "file.meta", "%s (%s, %d bytes)" % (os.path.basename(path), mime,
                                                                      meta.get("size", 0)), meta, uri, confidence=1.0),
               Finding(e, self.name, "file.hash", "sha256 " + r["hashes"]["sha256"], r["hashes"], "",
                       confidence=1.0, related=[Entity("hash", r["hashes"]["sha256"])])]
        if r.get("provenance") or r.get("origin_hints"):
            out.append(Finding(e, self.name, "file.provenance", "provenance hints (%d)" % len(r.get("provenance") or []),
                               {"provenance": r.get("provenance"), "origin_hints": r.get("origin_hints")}, "",
                               confidence=0.6))
        if r.get("embedded_payloads"):
            out.append(Finding(e, self.name, "file.embedded", "%d embedded payload(s)" % len(r["embedded_payloads"]),
                               {"embedded_payloads": r["embedded_payloads"]}, "", confidence=0.7))
        ind = r.get("indicators") or {}
        rel = []
        for u in ind.get("urls", []):
            h = urlparse(u).hostname
            if h:
                rel.append(Entity("domain", h))
        rel += [Entity("ip", i) for i in ind.get("ips", [])]
        rel += [Entity("email", m) for m in ind.get("emails", [])]   # never auto-pivoted (people)
        uniq = list(dict.fromkeys(rel))[:MAX_RELATED]
        if any(ind.values()):
            out.append(Finding(e, self.name, "file.indicators", "indicators: %d urls, %d ips, %d emails" % (
                len(ind.get("urls", [])), len(ind.get("ips", [])), len(ind.get("emails", []))),
                {k: v[:MAX_RELATED] for k, v in ind.items()}, "", confidence=0.7, related=uniq))
        out.append(Finding(e, self.name, "file.reverse_links", "reverse-search links (not fetched)",
                           r.get("reverse_search", {}), "", confidence=0.3))
        return out
