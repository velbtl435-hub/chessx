"""Detective mode: reverse search of file origins, metadata and provenance chain."""
from .investigate import investigate, metadata, provenance_chain, hashes, reverse_search_links
__all__ = ["investigate", "metadata", "provenance_chain", "hashes", "reverse_search_links"]
