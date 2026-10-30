import sys
from . import animate, list_sprites
for n in (sys.argv[1:] or list_sprites()):
    animate(n)
