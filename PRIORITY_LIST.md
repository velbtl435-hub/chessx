# ChessX - Priority List
# Ranked queue, one by one, most important first | 10/30/2026

Work top to bottom. Finish and test each item before starting the next.

---

## S+ (do now)

1. Install real deps (pyttsx3, vosk, ddgs, cryptography) and validate voice/STT end to end
2. Fix the ddgs merged-titles bug (result #2 returns several page titles glued together)
3. Solve the DuckDuckGo anti-bot page (try rotating headers, or fall back to ddgs/another engine)

## S

4. ASCII browser mode with colored square tiles (ChessX's unique feature)
5. Real integration of all packages in the main chessx.py with a unified menu
23. C in WASI/WebAssembly: port C cores (search core, capstone for reversing, audio DSP) to wasm32-wasi, run in the browser, native fallback on desktop, dual-target build pipeline (see CHESSX_MASTER_LIST.md section 25)

## A

6. Agents package (see CHESSX_MASTER_LIST.md section 22)
7. Deploy on Vercel Hobby
8. E2E test with real network on all 6 engines (DuckDuckGo, Brave, ddgs, webserp, SearXNG, mock)
22. Procedural audio system: 8-bit chiptune mixed with synthwave, plus synthesized retro-hardware sounds (HDD, fans, floppy, mechanical keyboard, CRT hum), no external samples; numpy + scipy; integrates with chessx_libs/sounds/ and TamagóX (see CHESSX_MASTER_LIST.md section 24)
24. Program reversal (MASTER §14.2): reversal_summary in detective.investigate(): toolchain/linker/language, packer verdict, import/export history, CFG highlights; static only | owner: Reversing Engineer | status: In progress

## B

9. Sounds beyond the basic set
10. Animated pixel art with little creatures
11. Expanded detective mode
12. Base conversion with more formats (octal, base32, base58, base64)

## C

13. Text and spreadsheet generation/analysis
14. Math generation with symbol drawing in the terminal
15. Multidisciplinary PhD professor mode

## D

16. Continuous scheduler beyond the basic scheduler
17. Periodic automatic audit

## E

18. Desktop version with Tauri/Electron
19. pip installer
20. Global terminal command

## F

21. Speculative ideas from the master list that still have no spec
