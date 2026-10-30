"""ChessX forensic geolocation (master list section 33, image part). Offline, deterministic.
Ethics: only analyze files you have the right to analyze; locations are estimates, never proof."""
from .exif import read_metadata, parse_tiff, parse_xmp, gps_info, time_info, Metadata
__all__ = ["read_metadata", "parse_tiff", "parse_xmp", "gps_info", "time_info", "Metadata"]
