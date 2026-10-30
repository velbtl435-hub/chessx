from .base import Result, Engine, http_get
from .engines import (DuckDuckGoEngine, BraveEngine, DDGSEngine, WebSerpEngine,
                      SearXNGEngine, MockEngine, ENGINES)
from .fusion import fuse, multi_search
__all__ = ["Result", "Engine", "http_get", "DuckDuckGoEngine", "BraveEngine", "DDGSEngine",
           "WebSerpEngine", "SearXNGEngine", "MockEngine", "ENGINES", "fuse", "multi_search"]
