#!/usr/bin/env python3
"""Extract ChatGPT's PRE-SEARCH layer at scale, through the DataForSEO AI Optimization API.

For every prompt, ChatGPT (with web search on) first fans the prompt out into sub-queries and
retrieves a pool of pages BEFORE it writes the answer. Most of that pool is never shown as a
citation. This is the "pre-search" / invisible layer. The DataForSEO endpoint returns it directly:
  - fan_out_queries : the sub-queries ChatGPT generated
  - search_results  : the pages it retrieved (the pre-search citation pool)
  - items           : the answer, whose inline links are the citations actually SHOWN

No browser, no captcha, resumable, and parallel so it runs over thousands of prompts.

  cp .env.example .env         # fill DFS_AUTH
  python3 -I extract.py                      # all prompts, 4 workers
  python3 -I extract.py --workers 8 --prompts prompts.tsv

prompts.tsv columns (tab-separated):  slug  <TAB>  topic  <TAB>  location  <TAB>  prompt
(location may be blank for the default US; e.g. "Australia", "United Kingdom".)
"""
import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"; RAW.mkdir(exist_ok=True)
AUTH = os.environ.get("DFS_AUTH", "")
if not AUTH:
    sys.exit("set DFS_AUTH (base64 of DataForSEO login:password) in the environment or .env")
URL = "https://api.dataforseo.com/v3/ai_optimization/chat_gpt/llm_responses/live"
MODEL = os.environ.get("PRESEARCH_MODEL", "gpt-6.1-sol")


def call(prompt, location):
    item = {"user_prompt": prompt, "model_name": MODEL, "web_search": True, "include_links": True}
    if location:
        item["location_name"] = location
    body = json.dumps([item])
    for _ in range(3):
        r = subprocess.run(
            ["curl", "-s", "--max-time", "180", "-H", f"Authorization: Basic {AUTH}",
             "-H", "Content-Type: application/json", "-X", "POST", URL, "-d", body],
            capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            try:
                d = json.loads(r.stdout)
                t = (d.get("tasks") or [{}])[0]
                if t.get("status_code") == 20000 and t.get("result"):
                    return d.get("cost", 0), t["result"][0]
            except Exception:
                pass
        time.sleep(2)
    return 0, None


def rows_from(path):
    out = []
    for line in (HERE / path).read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        p = line.split("\t")
        if len(p) >= 4:
            out.append({"slug": p[0], "topic": p[1], "location": p[2].strip(), "prompt": p[3]})
        elif len(p) == 2:  # minimal: slug <tab> prompt
            out.append({"slug": p[0], "topic": "", "location": "", "prompt": p[1]})
    return out


def one(row):
    out = RAW / f"{row['slug']}.json"
    if out.exists() and out.stat().st_size > 500:
        return row["slug"], "skip", 0
    cost, res = call(row["prompt"], row["location"])
    if not res:
        return row["slug"], "FAIL", 0
    res["_meta"] = row
    out.write_text(json.dumps(res, ensure_ascii=False))
    return row["slug"], f"fan={len(res.get('fan_out_queries') or [])} pool={len(res.get('search_results') or [])}", cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default="prompts.tsv")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    rows = rows_from(a.prompts)
    print(f"{len(rows)} prompts, {a.workers} workers, model {MODEL}")
    total, done = 0.0, 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(one, r): r for r in rows}
        for f in as_completed(futs):
            slug, msg, cost = f.result()
            total += cost; done += 1
            print(f"  [{done}/{len(rows)}] {slug:16} {msg}  (${cost:.3f})", flush=True)
    print(f"\n=== done; spend ${total:.2f} — raw/ has {len(list(RAW.glob('*.json')))} captures ===")


if __name__ == "__main__":
    main()
