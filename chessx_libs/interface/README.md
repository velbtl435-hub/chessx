# chessx_libs.interface
Terminal UI: ANSI colors, boot animation, the result board, widgets and pixel-art sprites.

- **Origin:** split out of chessx.py v0.5 (boot screen and board) and extended.
- **License:** same as the ChessX repository.
- **Adapted:** `str.maketrans` tables now use strings of equal length; colors switch off when NO_COLOR is set or the output is not a TTY;
  the board supports expand/collapse navigation.
- **API:** `Color`, `paint`, `boot_sequence`, `Board`, `Cell`, `panel`, `tabs`, `sidebar`, `render_sprite`, `retro_text`.
- Dependencies: Python 3 stdlib only.
