#!/usr/bin/env python3
"""Aggregate the pre-search records into the invisible-layer report.

Answers, across the whole prompt set:
  - how wide ChatGPT fans out, how much it retrieves, how little it shows
  - the invisible layer: % of retrieved domains that are never cited
  - which domains are retrieved a lot but rarely shown (the invisible influencers)
  - first-party share: how often a target's own domain is retrieved vs shown (needs config.json)

  python3 analyze.py            # -> analysis.json
"""
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "presearch.json").read_text())
prompts = data["prompts"]
cfg_path = HERE / "config.json"
cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
TARGET = set(d.lower() for d in cfg.get("target_domains", []))

n = len(prompts)
# per-domain: how often retrieved vs shown across all prompts
retr = defaultdict(int); shown = defaultdict(int)
for p in prompts:
    for d in p["retrieved_domains"]: retr[d] += 1
    for d in p["shown_domains"]: shown[d] += 1

per_domain = []
for d, rc in retr.items():
    sc = shown.get(d, 0)
    per_domain.append({"domain": d, "retrieved": rc, "shown": sc,
                       "shown_rate": round(100 * sc / rc) if rc else 0})
per_domain.sort(key=lambda z: (-z["retrieved"], z["domain"]))

# invisible influencers: retrieved in >=2 prompts, shown in none
invisible_influencers = [x for x in per_domain if x["retrieved"] >= 2 and x["shown"] == 0][:30]

tot_retr = sum(p["n_retrieved"] for p in prompts)
tot_shown = sum(p["n_shown"] for p in prompts)
tot_fan = sum(p["n_fan_out"] for p in prompts)
uniq_retr = len(retr); uniq_shown = len(shown)
invisible_uniq = sorted(set(retr) - set(shown))

out = {
    "n_prompts": n,
    "fan_out": {"total": tot_fan, "avg_per_prompt": round(tot_fan / max(1, n), 1)},
    "retrieved": {"total": tot_retr, "avg_per_prompt": round(tot_retr / max(1, n), 1), "unique_domains": uniq_retr},
    "shown": {"total": tot_shown, "avg_per_prompt": round(tot_shown / max(1, n), 1), "unique_domains": uniq_shown},
    "invisible_layer": {
        "unique_domains_never_shown": len(invisible_uniq),
        "pct_of_unique_retrieved": round(100 * len(invisible_uniq) / max(1, uniq_retr)),
        "avg_invisible_pct_per_prompt": round(sum(p["invisible_pct"] for p in prompts) / max(1, n)),
    },
    "per_domain": per_domain[:60],
    "invisible_influencers": invisible_influencers,
    "top_shown": sorted(per_domain, key=lambda z: -z["shown"])[:15],
    "spend": round(sum((p.get("cost") or 0) for p in prompts), 2),
}
if TARGET:
    t_retr = sum(1 for p in prompts if any(d in TARGET for d in p["retrieved_domains"]))
    t_shown = sum(1 for p in prompts if any(d in TARGET for d in p["shown_domains"]))
    out["first_party"] = {"target_domains": sorted(TARGET),
                          "prompts_retrieved": t_retr, "prompts_shown": t_shown,
                          "retrieved_pct": round(100 * t_retr / max(1, n)),
                          "shown_pct": round(100 * t_shown / max(1, n))}

(HERE / "analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in out.items() if k not in ("per_domain", "invisible_influencers", "top_shown")}, indent=1))
print("\ntop invisible influencers (retrieved often, never shown):")
for x in invisible_influencers[:12]:
    print(f"  {x['domain']:34} retrieved in {x['retrieved']} prompts, shown 0")
