# chessx_libs.chess_ai
Rule-based ("good old fashioned AI") intent classifier for the ChessX prompt.

- **Origin:** written for ChessX; replaces the inline command parsing of chessx.py v0.5.
- **License:** same as the ChessX repository.
- **Adapted:** fixed commands followed by numbers (`open 3`, `o 3`, `go #3`) and multi-term phrases
  (`convert hex to binary`, `convert ff hex to bin`), plus a loose fallback that finds base names anywhere in a sentence.
- **API:** `classify(text) -> Intent(name, confidence, args)`, `INTENTS`.
- Dependencies: Python 3 stdlib only.
