# chessx_libs.sounds
Origin: written for ChessX (2026). License: MIT. Sounds are synthesized at runtime (sine tones, stdlib `wave`)
-- no audio assets, no licensing issues. Playback: winsound (Windows) / aplay / paplay / afplay / ffplay;
silent noop if none found or env CHESSX_MUTE=1.
