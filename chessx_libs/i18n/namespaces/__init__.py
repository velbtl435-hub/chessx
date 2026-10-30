"""Namespaced string tables (keys like ``menu.title``), kept apart from the base STRINGS.

Each namespace module defines ``STRINGS = {"en": {...}, "pt": {...}, "ja": {...}}`` and every
key must start with ``<namespace>.``. ``NS_STRINGS`` merges all namespaces per language;
the Translator looks there after the base table. Add a namespace with ``register()``.
"""
from . import menu

NAMESPACES = {"menu": menu.STRINGS}
NS_STRINGS = {"en": {}, "pt": {}, "ja": {}}


def register(name: str, table: dict) -> None:
    for lang, entries in table.items():
        bad = [k for k in entries if not k.startswith(name + ".")]
        if bad:
            raise ValueError(f"namespace {name!r}: keys must start with '{name}.': {bad}")
        NS_STRINGS.setdefault(lang, {}).update(entries)
    NAMESPACES[name] = table


for _name, _table in list(NAMESPACES.items()):
    register(_name, _table)
