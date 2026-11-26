#!/usr/bin/env python3
"""Turn each raw capture into the pre-search record: fan-out queries, the retrieved pool
(pre-search citations), the citations actually shown, and the invisible set (retrieved but
never shown). Writes presearch.json.

  python3 parse.py
"""
import json, re
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
TWO = {"co.uk", "com.au", "co.nz", "org.uk", "ac.uk", "co.in", "com.br"}

def reg(host):
    host = (host or "").replace("www.", "").lower().split("/")[0].split("?")[0]
    p = host.split(".")
    if len(p) >= 3 and ".".join(p[-2:]) in TWO: return ".".join(p[-3:])
    return ".".join(p[-2:]) if len(p) >= 2 else host

def dom(u):
    try: return reg(urlparse(u).netloc)
    except Exception: return ""

def shown_urls(res):
    """Citations actually shown: markdown links in the answer + section annotations."""
    urls = set()
    for it in res.get("items") or []:
        for s in it.get("sections") or []:
            txt = s.get("text") or s.get("markdown") or ""
            for u in re.findall(r"\]\((https?://[^)\s]+)\)", txt):
                urls.add(u)
            for a in (s.get("annotations") or []):
                u = a.get("url") or a.get("href")
                if u: urls.add(u)
    return urls

def run():
    prompts = []
    for f in sorted(RAW.glob("*.json")):
        res = json.loads(f.read_text())
        m = res.get("_meta", {})
        fan = res.get("fan_out_queries") or []
        pool = res.get("search_results") or []
        pool_doms = [dom(r.get("url")) for r in pool if r.get("url")]
        shown = shown_urls(res)
        shown_doms = {dom(u) for u in shown if dom(u)}
        pool_set = {d for d in pool_doms if d}
        invisible = sorted(pool_set - shown_doms)
        prompts.append({
            "slug": m.get("slug"), "topic": m.get("topic"), "location": m.get("location"),
            "prompt": m.get("prompt"),
            "fan_out": fan,
            "n_fan_out": len(fan),
            "retrieved_pool": [{"domain": dom(r.get("url")), "url": r.get("url"),
                                "title": r.get("title"), "date": r.get("date")} for r in pool if r.get("url")],
            "retrieved_domains": sorted(pool_set),
            "shown_domains": sorted(shown_doms),
            "invisible_domains": invisible,
            "n_retrieved": len(pool_set),
            "n_shown": len(shown_doms),
            "n_invisible": len(invisible),
            "invisible_pct": round(100 * len(invisible) / max(1, len(pool_set))),
            "cost": res.get("money_spent"),
            "datetime": res.get("datetime"),
        })
    out = {"n_prompts": len(prompts), "prompts": prompts}
    (HERE / "presearch.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"parsed {len(prompts)} prompts -> presearch.json")
    for p in prompts:
        print(f"  {p['slug']:16} fan-out {p['n_fan_out']:>2} | retrieved {p['n_retrieved']:>2} | shown {p['n_shown']:>2} | invisible {p['invisible_pct']:>3}%")

if __name__ == "__main__":
    run()
