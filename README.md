# ChatGPT Pre-Search Extractor

Extracts ChatGPT's **pre-search layer** — the sub-queries it fans a prompt into and the pool of
pages it retrieves *before* it writes an answer — at scale, and measures the **invisible layer**:
the pages it reads but never shows as a citation.

With web search on, ChatGPT does not answer from the first link. It expands the prompt into several
search queries, pulls back a pool of pages, and then cites only a few of them. The pages it does not
cite still shape the answer. This tool pulls that whole pool through an API, so you can see which
domains influence answers without ever being credited.

## What it found on the demo set

8 consumer VPN prompts, one run, **$0.29**:

| | value |
|---|---|
| Fan-out queries | 18 (2.2 per prompt) |
| Pages retrieved (pre-search pool) | 128, across **80 unique domains** |
| Citations shown | 18, across 16 domains |
| **Invisible layer** | **64 of 80 domains (80%) never shown** — 74% invisible per prompt |
| Invisible influencers | youtube.com (read in 6 prompts, cited 0), wikipedia.org (5/0), rtings.com (4/0), top10vpn.com (3/0) |

The shown citations are the tip; four fifths of what ChatGPT actually read stays hidden.

---

## Why this method scales

The extraction uses DataForSEO's AI Optimization endpoint
(`/v3/ai_optimization/chat_gpt/llm_responses/live`), which returns three things per prompt:

- `fan_out_queries` — the sub-queries ChatGPT generated,
- `search_results` — the pages it retrieved (the pre-search pool),
- `items` — the answer, whose inline links are the citations actually shown.

No browser, no captcha, no session to keep alive. `extract.py` runs prompts in parallel and is
resumable, so a set of thousands is just a bigger input file. A browser/HAR capture gets the same
pool from the live UI but does not scale (captchas, logged-out limits, session-bound tokens); use it
only to spot-check a handful (see *Cross-check* below).

---

## Quick start

```bash
# Python 3.9+ and the system `curl`. No pip packages needed.
cp .env.example .env            # fill DFS_AUTH = base64("login:password")
./run_all.sh                    # extract -> parse -> analyze (default 4 workers)
./run_all.sh --workers 8 --prompts prompts.tsv
```

Outputs:
- `pipeline/presearch.json` — per prompt: fan-out, retrieved pool, shown citations, invisible set.
- `pipeline/analysis.json` — the rollup: fan-out breadth, retrieved vs shown, invisible %, invisible influencers, top shown.

Make `DFS_AUTH`: `printf '%s' 'you@example.com:APIPASS' | base64`.
Cost is roughly $0.03–0.05 per prompt.

---

## Pipeline

| # | Script | Does | Output |
|---|---|---|---|
| 1 | `extract.py --workers N --prompts F` | Runs each prompt through ChatGPT, keeps the raw fan-out + pool + answer. Parallel, resumable. | `pipeline/raw/<slug>.json` |
| 2 | `parse.py` | Per prompt: fan-out, retrieved pool (domain/url/title/date), shown citations, invisible domains. | `pipeline/presearch.json` |
| 3 | `analyze.py` | Rollup across prompts: the invisible-layer metrics, per-domain retrieved-vs-shown, invisible influencers, first-party share. | `pipeline/analysis.json` |

Stages 2–3 need no credentials and re-run offline on whatever is in `raw/`.

### The metrics (`analysis.json`)
- **fan_out** — how wide ChatGPT searches per prompt.
- **retrieved** — total and unique domains in the pre-search pool.
- **shown** — the citations that made it into the answer.
- **invisible_layer** — unique domains never shown, as a share of retrieved, plus the average per-prompt invisible %.
- **per_domain** — every domain with times retrieved vs times shown and a shown-rate; ranked by how often it is retrieved.
- **invisible_influencers** — domains retrieved in 2+ prompts and shown in none. These are the pages steering answers off-screen.
- **first_party** (needs `config.json`) — how often a target brand's own domains are retrieved vs shown.

---

## Prompts

`pipeline/prompts.tsv`, tab-separated, one prompt per line:

```
slug   <TAB>   topic   <TAB>   location   <TAB>   prompt
```

`location` may be blank (defaults to US) or a country name (`United Kingdom`, `Australia`, `Germany`…)
to pull the pool as a local would see it. `topic` is a free label for grouping (awareness / decision / …).
Lines starting with `#` are ignored. Keep a set stage-balanced so the pool is not all decision-stage.

## First-party analysis (optional)

```bash
cp pipeline/config.example.json pipeline/config.json
# edit target_domains to the brand's own domains
```

`analyze.py` then reports how often the brand's own pages are retrieved into the pool versus actually
shown — the gap between "ChatGPT read our site" and "ChatGPT cited our site."

---

## Cross-check (optional, not at scale)

To confirm the API pool matches the live UI, capture one conversation with a DevTools/HAR recording
of `backend-api/conversation` and compare its `safe_urls` / search-source groups to `search_results`
here. Use it on a few prompts only; it needs a logged-in browser and does not batch.

---

## Credentials and safety
- `DFS_AUTH` lives in `.env` (git-ignored), never in code. `raw/` and `config.json` are git-ignored too.
- Read-only measurement of public answer behaviour. It does not evade bot protection or automate logins.
- The demo numbers are one run on 8 prompts; ChatGPT's retrieval changes over time, so re-run for current figures.
