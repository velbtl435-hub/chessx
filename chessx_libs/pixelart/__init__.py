"""Animated pixel-art critters (PRIORITY #10).

API: list_sprites() -> [names]; get_sprite(name) -> Sprite
     render_frame(sprite_or_name, i=0, color=True) -> str   (half-block ANSI, pure)
     animate(name, frames=None, fps=8, walk=True, out=None, sleep=time.sleep) -> int frames drawn
"""
from .sprites import Sprite, SPRITES, list_sprites, get_sprite
from .render import render_frame, animate
from .legacy import render_sprite, retro_text, FONT

__all__ = ["Sprite", "SPRITES", "list_sprites", "get_sprite", "render_frame", "animate",
           "render_sprite", "retro_text", "FONT"]
