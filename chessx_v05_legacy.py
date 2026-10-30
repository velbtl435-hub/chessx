#!/usr/bin/env python3
"""ChessX v0.5 - Meta-busca agentica no terminal.
Motores: DuckDuckGo (HTML), Brave (API), + mocks. Salva JSON/CSV.
Abre no navegador. Auto-refresh periodico."""
from __future__ import annotations
import os, sys, time, random, textwrap, re, json, csv, urllib.request, urllib.parse, webbrowser
from dataclasses import dataclass, field, asdict

class C:
    RESET=chr(27)+"[0m"; BOLD=chr(27)+"[1m"; DIM=chr(27)+"[2m"
    RED=chr(27)+"[31m"; GREEN=chr(27)+"[32m"; YELLOW=chr(27)+"[33m"
    BLUE=chr(27)+"[34m"; MAGENTA=chr(27)+"[35m"; CYAN=chr(27)+"[36m"; WHITE=chr(27)+"[37m"
    BG_BLUE=chr(27)+"[44m"
if (not sys.stdout.isatty()) or os.environ.get("NO_COLOR"):
    for a in ["RESET","BOLD","DIM","RED","GREEN","YELLOW","BLUE","MAGENTA","CYAN","WHITE","BG_BLUE"]:
        globals()[a] = ""

@dataclass
class SearchResult:
    title: str; url: str; snippet: str; source: str
    score: float = 0.0; kind: str = "web"; extra: dict = field(default_factory=dict)

@dataclass
class EngineReport:
    engine: str; results: list; latency_ms: float; ok: bool; error: str = ""

class BaseEngine:
    name = "base"
    def search(self, query, limit=5):
        raise NotImplementedError

class MockEngine(BaseEngine):
    def __init__(self, name, bias=""):
        self.name, self.bias = name, bias
    def search(self, query, limit=5):
        t0 = time.perf_counter()
        out = []
        for i in range(limit):
            nm = self.name.lower().replace(chr(32), chr(39))
            out.append(SearchResult(
                title="[" + self.name + "] " + query + " - " + str(i+1) + " " + self.bias,
                url="https://" + nm + ".example/" + str(i+1),
                snippet=textwrap.shorten("Simulado: " + query + " via " + self.name + ".", 120),
                source=self.name, score=round(random.uniform(0.4,0.95),3),
                kind=random.choice(["web","web","image","code","video"])))
        out.sort(key=lambda r: r.score, reverse=True)
        return EngineReport(self.name, out, round((time.perf_counter()-t0)*1000,1), True)

class DuckDuckGoEngine(BaseEngine):
    name = "DuckDuckGo"
    HDR = {"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language":"pt-BR,pt;q=0.9"}
    def search(self, query, limit=5):
        t0 = time.perf_counter()
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
        req = urllib.request.Request(url, headers=self.HDR)
        try:
            page = urllib.request.urlopen(req, timeout=12).read().decode("utf-8","ignore")
        except Exception as e:
            return EngineReport(self.name, [], round((time.perf_counter()-t0)*1000,1), False, str(e)[:200])
        out = []
        pat = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
            r'(?:.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>)?', re.S)
        for m in pat.finditer(page):
            href = m.group(1); title = m.group(2); snip = m.group(3) or ""
            title = re.sub(r"<[^>]+>","",title)
            title = title.replace(chr(38)+chr(97)+chr(109)+chr(112)+chr(59), chr(38))
            title = title.replace(chr(38)+chr(108)+chr(116)+chr(59), chr(60))
            title = title.replace(chr(38)+chr(103)+chr(116)+chr(59), chr(62))
            title = title.replace(chr(38)+chr(113)+chr(117)+chr(111)+chr(116)+chr(59), chr(34))
            title = title.replace(chr(38)+chr(35)+chr(51)+chr(57)+chr(59), chr(39))
            title = re.sub(r"\s+"," ",title).strip()
            snip = re.sub(r"<[^>]+>","",snip)
            snip = snip.replace(chr(38)+chr(97)+chr(109)+chr(112)+chr(59), chr(38))
            snip = snip.replace(chr(38)+chr(108)+chr(116)+chr(59), chr(60))
            snip = snip.replace(chr(38)+chr(103)+chr(116)+chr(59), chr(62))
            snip = snip.replace(chr(38)+chr(113)+chr(117)+chr(111)+chr(116)+chr(59), chr(34))
            snip = snip.replace(chr(38)+chr(35)+chr(51)+chr(57)+chr(59), chr(39))
            snip = re.sub(r"\s+"," ",snip).strip()
            if "uddg=" in href:
                try: href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                except Exception: pass
            if href.startswith("http") and title:
                out.append(SearchResult(title[:200], href, snip[:300], self.name, 0.0, "web"))
            if len(out) >= limit: break
        return EngineReport(self.name, out, round((time.perf_counter()-t0)*1000,1), True,
                            "" if out else "nenhum resultado")

class BraveEngine(BaseEngine):
    name = "Brave"
    def search(self, query, limit=5):
        t0 = time.perf_counter()
        key = os.environ.get("BRAVE_API_KEY","")
        if not key:
            return EngineReport(self.name, [], 0.0, False, "BRAVE_API_KEY nao definida")
        url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode({"q":query,"count":limit})
        req = urllib.request.Request(url, headers={"Accept":"application/json","X-Subscription-Token":key})
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=12).read().decode())
        except Exception as e:
            return EngineReport(self.name, [], round((time.perf_counter()-t0)*1000,1), False, str(e)[:200])
        out = []
        for it in data.get("web",{}).get("results",[])[:limit]:
            out.append(SearchResult((it.get("title") or "")[:200], it.get("url") or "",
                                    (it.get("description") or "")[:300], self.name, 0.0, "web"))
        return EngineReport(self.name, out, round((time.perf_counter()-t0)*1000,1), True)

ENGINES = [DuckDuckGoEngine(), BraveEngine(),
           MockEngine("Startpage","🕵️"), MockEngine("Searx","🧩"),
           MockEngine("Bing","🅱️"), MockEngine("Google","🔍")]

def fuse(reports):
    bucket = {}
    for rep in reports:
        if not rep.ok: continue
        for r in rep.results:
            if r.url not in bucket: bucket[r.url] = r
            else:
                bucket[r.url].score = min(1.0, bucket[r.url].score + 0.12)
                bucket[r.url].extra.setdefault("agreed_by", set()).add(rep.engine)
    fused = sorted(bucket.values(), key=lambda r: r.score, reverse=True)
    for r in fused:
        r.extra["agreed_by"] = sorted(r.extra.get("agreed_by", []))
    return fused

def save_results(fused, query, fmt="json"):
    base = "chessx_" + re.sub(r"[^a-zA-Z0-9]+","_", query)[:40]
    if fmt == "csv":
        path = base + ".csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["title","url","snippet","source","score","kind","agreed_by"])
            for r in fused:
                w.writerow([r.title, r.url, r.snippet, r.source, r.score, r.kind,
                           "|".join(r.extra.get("agreed_by", []))])
    else:
        path = base + ".json"
        data = {"query": query, "count": len(fused),
                "results": [asdict(r) for r in fused]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return path

def open_url(url):
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False

BW, BH = 3, 2
def draw_header(q):
    print(f"{C.CYAN}{C.BOLD}╔{"═"*64}╗{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}║  ♟  ChessX  v0.5{C.RESET}{" "*44}║")
    print(f"{C.CYAN}{C.BOLD}╚{"═"*64}╝{C.RESET}")
    print(f"{C.DIM}Consulta:{C.RESET} {C.BOLD}{q}{C.RESET}\n")

def draw_stats(reps, fused):
    print(f"{C.BOLD}Estatisticas da rodada{C.RESET}")
    print(f"  Motores: {sum(1 for r in reps if r.ok)}/{len(reps)} ok | "
          f"Latencia: {sum(r.latency_ms for r in reps):.0f} ms | "
          f"Brutos: {sum(len(r.results) for r in reps)} | Fundidos: {len(fused)}")
    if fused:
        kinds = {}
        for r in fused: kinds[r.kind] = kinds.get(r.kind,0)+1
        print(f"  Tipos: {', '.join(f'{k}:{v}' for k,v in kinds.items())} | "
              f"Score medio: {sum(r.score for r in fused)/len(fused):.2f}")
    print()

def draw_board(fused, page=0, sel=0):
    pp = BW*BH; start = page*pp; chunk = fused[start:start+pp]
    print(f"{C.BOLD}Tabuleiro{C.RESET} (pag {page+1}, {start+1}-{start+len(chunk)} de {len(fused)})\n")
    print("      " + "   ".join(f" {chr(65+c)} " for c in range(BW)))
    for row in range(BH):
        print("     " + "┌" + "─┬".join(["─"*16 for _ in range(BW)]) + "─┐")
        cells = []
        for col in range(BW):
            i = row*BW+col
            if i < len(chunk):
                r = chunk[i]
                cells.append(("▶" if i==sel else " ", r.kind[:3].upper(), r.title[:14], r.score, r.source[:6]))
            else:
                cells.append((" ","   ","",0.0,""))
        print("     " + "│".join(f" {m}{C.BOLD}{t}{C.RESET} {ti:<14} " for m,t,ti,_,_ in cells) + "│")
        print("     " + "│".join(f"   {s:>4.02f} {src:<6} " for _,_,_,s,src in cells) + "│")
        print("     " + "└" + "─┴".join(["─"*16 for _ in range(BW)]) + "─┘")
        if row < BH-1:
            print("     " + "├" + "─┼".join(["─"*16 for _ in range(BW)]) + "─┤")
    print(f"\n  {C.DIM}[Enter]=abrir nav [d]=detalhe [Tab]=prox [Shift+Tab]=ant "
          f"[n]=prox pag [p]=ant pag [s]=salvar [r]=refresh [a]=auto [q]=sair{C.RESET}")

def draw_detail(r):
    print(f"\n{C.BG_BLUE}{C.BOLD} DETALHE {C.RESET}")
    print(f"  Titulo: {C.BOLD}{r.title}{C.RESET}")
    print(f"  URL: {C.CYAN}{r.url}{C.RESET}")
    print(f"  Fonte: {r.source} | Tipo: {r.kind} | Score: {r.score:.3f}")
    if r.extra.get("agreed_by"):
        print(f"  Concordou com: {', '.join(r.extra['agreed_by'])}")
    print(f"  Snippet: {C.DIM}{r.snippet}{C.RESET}\n")

def run_search(q):
    draw_header(q)
    print(f"{C.DIM}Consultando {len(ENGINES)} motores...{C.RESET}")
    reps = [e.search(q) for e in ENGINES]
    for r in reps:
        st = f"{C.GREEN}ok{C.RESET}" if r.ok else f"{C.RED}erro{C.RESET}"
        print(f"  {r.engine:<12} {st} {r.latency_ms:>6.1f} ms ({len(r.results)} res)"
              + (f"  {C.DIM}{r.error}{C.RESET}" if r.error else ""))
    fused = fuse(reps); print(); draw_stats(reps, fused); return fused

def main():
    banner = [
        "   ____  _                     __  __",
        "  / ___|| |__   ___  ___ ___  \\ \/ /",
        " | |    | '_ \\ / _ \\/ __/ __|  \\  /",
        " | |___ | | | |  __/\\__ \\__ \\  /  \\",
        "  \\____||_| |_|\\___||___/___/ /_/\\_\\",
    ]
    print(f"{C.MAGENTA}{C.BOLD}")
    for b in banner:
        print(b)
    msg = "Meta-busca agentica v0.5. " + chr(39) + "sair" + chr(39) + " encerra."
    print(f"{C.RESET}{C.DIM}{msg}{C.RESET}\n")
    while True:
        try: q = input(f"{C.CYAN}chessx>{C.RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAte mais."); break
        if not q: continue
        if q.lower() in ("sair","exit","quit"):
            print("Ate mais."); break
        fused = run_search(q)
        if not fused:
            print(f"{C.RED}Nenhum resultado.{C.RESET}"); continue
        page, sel, pp = 0, 0, BW*BH
        auto_sec = 0
        while True:
            draw_board(fused, page, sel)
            if auto_sec > 0:
                print(f"  {C.DIM}Auto-refresh a cada {auto_sec}s. Ctrl+C pra parar o loop.{C.RESET}")
            try:
                if auto_sec > 0:
                    import select
                    ready, _, _ = select.select([sys.stdin], [], [], auto_sec)
                    if not ready:
                        fused = run_search(q); page, sel = 0, 0; continue
                    cmd = sys.stdin.readline().strip().lower()
                else:
                    cmd = input(f"\n{C.YELLOW}chessx/{page+1}>{C.RESET} ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nAte mais."); return
            if cmd in ("q","sair"): break
            elif cmd in ("","enter","o","open"):
                i = page*pp+sel
                if i < len(fused):
                    r = fused[i]
                    if open_url(r.url):
                        print(f"  {C.GREEN}Aberto:{C.RESET} {r.url}")
                    else:
                        print(f"  {C.RED}Falhou ao abrir.{C.RESET}")
                    draw_detail(r)
            elif cmd == "d":
                i = page*pp+sel
                if i < len(fused): draw_detail(fused[i])
            elif cmd in ("tab","n","next"):
                sel = (sel+1) % min(pp, len(fused)-page*pp)
            elif cmd in ("shift+tab","p","prev"):
                sel = (sel-1) % min(pp, len(fused)-page*pp)
            elif cmd == "np" and (page+1)*pp < len(fused):
                page += 1; sel = 0
            elif cmd == "pp" and page > 0:
                page -= 1; sel = 0
            elif cmd in ("s","save"):
                fmt = "csv" if input("  Formato [json/csv]: ").strip().lower()=="csv" else "json"
                path = save_results(fused, q, fmt)
                print(f"  {C.GREEN}Salvo:{C.RESET} {path}")
            elif cmd in ("r","refresh"):
                fused = run_search(q); page, sel = 0, 0
            elif cmd in ("a","auto"):
                try: auto_sec = max(5, int(input("  Segundos entre buscas [min 5]: ").strip()))
                except ValueError: auto_sec = 30
                print(f"  {C.GREEN}Auto-refresh ativado: {auto_sec}s{C.RESET}")
            elif cmd == "aa":
                auto_sec = 0
                print(f"  {C.YELLOW}Auto-refresh desativado.{C.RESET}")
            else:
                print(f"{C.DIM}Desconhecido: {cmd}{C.RESET}")

if __name__ == "__main__":
    main()
