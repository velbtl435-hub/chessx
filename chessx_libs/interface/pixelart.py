"""DEPRECATED: use chessx_libs.pixelart (legacy names live in chessx_libs.pixelart.legacy)."""
import warnings

warnings.warn("chessx_libs.interface.pixelart is deprecated; use chessx_libs.pixelart "
              "(render_sprite/retro_text: chessx_libs.pixelart.legacy)", DeprecationWarning, stacklevel=2)

from chessx_libs.pixelart.legacy import (  # noqa: E402
    Color, paint, PIXEL_FROM, PIXEL_TO, PIXEL_TABLE, SPRITES, FONT, render_sprite, retro_text)

__all__ = ["Color", "paint", "PIXEL_FROM", "PIXEL_TO", "PIXEL_TABLE", "SPRITES", "FONT",
           "render_sprite", "retro_text"]
