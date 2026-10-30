"""Optional angr helpers (CFG / reachability). Static analysis only (CFGFast never runs the sample)."""
import importlib.util

# Lazy: angr is heavy, so only check presence here; import happens on first use.
HAVE_ANGR = importlib.util.find_spec("angr") is not None


def cfg_summary(path: str, max_functions: int = 50) -> dict:
    if not HAVE_ANGR:
        return {"available": False, "reason": "angr not installed"}
    import angr
    proj = angr.Project(path, auto_load_libs=False)
    cfg = proj.analyses.CFGFast(normalize=True)
    funcs = [{"addr": f.addr, "name": f.name, "blocks": len(list(f.blocks))}
             for f in list(cfg.kb.functions.values())[:max_functions]]
    return {"available": True, "entry": proj.entry, "nodes": sum(1 for _ in cfg.graph.nodes()),
            "edges": sum(1 for _ in cfg.graph.edges()), "function_count": len(cfg.kb.functions), "functions": funcs}


def reachable(path: str, src, dst) -> dict:
    """Is function/address `dst` statically reachable from `src` in the call graph?"""
    if not HAVE_ANGR:
        return {"available": False, "reason": "angr not installed"}
    import angr, networkx as nx
    proj = angr.Project(path, auto_load_libs=False)
    cfg = proj.analyses.CFGFast(normalize=True)
    fns = cfg.kb.functions

    def _addr(x):
        if isinstance(x, int):
            return x
        f = fns.function(name=x)
        return f.addr if f else None
    a, b = _addr(src), _addr(dst)
    if a is None or b is None:
        return {"available": True, "reachable": False, "reason": "symbol not found"}
    cg = fns.callgraph
    ok = a in cg and b in cg and nx.has_path(cg, a, b)
    return {"available": True, "reachable": bool(ok), "src": a, "dst": b}
