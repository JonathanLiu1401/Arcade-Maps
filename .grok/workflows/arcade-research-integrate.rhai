// Integrate unknown-games fleet + source-discovery catalog into the map pipeline
let meta = #{
  name: "arcade-research-integrate",
  description: "Parallel integrate unknown-games findings and new regional sources",
};

const REPO = "C:/Users/jonny/Desktop/Arcade Maps";

const COMMON = `
REPO: ${REPO} (branch main). Windows PowerShell.

HARD RULES:
- NEVER use an em dash. Hyphen, colon, or two sentences.
- Do NOT git commit or git push.
- Do NOT create subagents.
- Prefer stdlib-only Python for scrapers (urllib, json, re, html).
- PYTHONIOENCODING=utf-8 for CJK.
- Politeness: sleep >= 0.4s between requests; sequential fetch; 3+ retries;
  catch http.client.HTTPException (IncompleteRead) like scrapers/common.py and bemanicn.
- Key venues by source URL or sid, NEVER by row-number id.
- Write captain report JSON to ${REPO}/data_raw/integrate/<slug>_report.json
  with: slug, files_changed[], summary, how_to_verify[], risks[], metrics{}

Existing research already on disk:
- data_raw/unknown/reports/unk_000.json .. unk_059.json  (2312 findings)
- data_raw/unknown/harvest_summary.json, apply_plan.json
- data/owner_attested.json already has ~310 venues from a first safe pass
  (185 add_games, 21 closed, 101 exclude)
- data_raw/sources/found_*.json + catalog.json (73 sources, 13 regions)

Goal of THIS fan-out: deepen integration so more research becomes map data or
wired scrapers - not just sitting in report JSON.
`;

let jobs = [];

// ---- 1) Deeper apply of unknown-games findings ----
jobs.push(#{
  label: "int:apply-unknown",
  subagent_type: "grok",
  prompt: `${COMMON}

YOU ARE: apply-unknown agent. slug = apply_unknown

OWN:
- scrapers/apply_unknown_reports.py  (CREATE - idempotent apply tool)
- data/owner_attested.json  (extend carefully)
- data_raw/unknown/apply_plan_v2.json (write plan metrics)
- data_raw/integrate/apply_unknown_report.json

DO NOT edit js/, index.html, or scrapers/merge.py beyond what apply tool needs.
You MAY run: python scrapers/apply_unknown_reports.py then
  python -m scrapers.run_all --skip-scrape
to rebuild data/arcades.json (long but OK if <10 min).

GOAL
First pass only applied certain/likely has_games with non-other slugs (185).
There are still 836 has_games, 651 confirmed_none, 34 closed, 791 unknown.

Build apply_unknown_reports.py that:
1. Reads all data_raw/unknown/reports/unk_*.json
2. Joins findings to current data/arcades.json by sid
3. Applies into owner_attested.json with attested_by research-fleet:
   - has_games: confidence certain|likely, evidence_url+quote required,
     games intersect GAME_SLUGS minus pure-other-only unless note is strong.
     Merge add_games with existing owner_attested entries; never wipe exclude
     on a venue already excluded unless has_games certain with real games.
   - closed: confidence certain, evidence required -> closed:true
   - confirmed_none: confidence certain, evidence NOT circular ZIv-empty only,
     only if current games are subset of {other} -> exclude:true
4. Print metrics: applied/skipped by reason
5. Rebuild with --skip-scrape if apply changed owner_attested
6. Report before/after: other-only count, total arcades, n owner_attested

Safety > coverage. Wrong game list is worse than missing.
`,
});

// ---- 2) HK / TW / MO source scrapers ----
jobs.push(#{
  label: "int:scrape-hk-tw",
  subagent_type: "grok",
  prompt: `${COMMON}

YOU ARE: scrape-hk-tw agent. slug = scrape_hk_tw

OWN:
- scrapers/hkrgm2.py and/or scrapers/hkarcade.py and/or scrapers/mgm_tw.py
  (implement the best 1-2 sources that are actually fetchable)
- data_raw/hkrgm2.json and/or data_raw/hkarcade.json (scrape output)
- docs note snippet only if you create scrapers/README fragment in report
- data_raw/integrate/scrape_hk_tw_report.json

Read data_raw/sources/found_hk_tw_mo.json for URLs and machine_readable hints.
Priority order:
1. HKRGM2 https://whitenightawa.github.io/hkrgm2/ (api - gold for HK cab lists)
2. Music Game Map Taiwan https://mgm.wind-chime.info/
3. maimaidx.tw / chunithm.tw store lists
4. hkarcade.fandom (html_scrape - heavier)

Output rows compatible with merge units: name, address, lat/lng if any,
games[], source, source_url, country (Hong Kong / Taiwan / Macau), notes.
Do NOT wire into merge.py in this agent (wire agent does that) - but design
output so merge can load it later as a new source family.
Run your scraper once and write data_raw/*.json with real rows.
Smoke mode --smoke recommended.
`,
});

// ---- 3) China nearcade + WAHLAP extras ----
jobs.push(#{
  label: "int:scrape-cn",
  subagent_type: "grok",
  prompt: `${COMMON}

YOU ARE: scrape-cn agent. slug = scrape_cn

OWN:
- scrapers/nearcade.py (primary)
- data_raw/nearcade.json
- optional scrapers/wahlap_gc.py only if quick (Groove Coaster China)
- data_raw/integrate/scrape_cn_report.json

Read data_raw/sources/found_cn.json.
nearcade.phizone.cn was reported as ~3941 CN shops with public paginated JSON
and per-cab lineups that can exceed BemaniCN.

Implement a polite scraper:
- discover API endpoints by fetching the site (WebFetch/open) first
- map title ids to our GAME_SLUGS (maimai_dx, chunithm, sdvx, taiko, etc.)
- write data_raw/nearcade.json
- --smoke for 1 page/city

Do not break existing bemanicn/wahlap scrapers.
Do not wire merge in this agent.
`,
});

// ---- 4) Korea Musecat + JP otoge wiki ----
jobs.push(#{
  label: "int:scrape-kr-jp",
  subagent_type: "grok",
  prompt: `${COMMON}

YOU ARE: scrape-kr-jp agent. slug = scrape_kr_jp

OWN:
- scrapers/musecat.py and/or scrapers/otogesetchi.py (best 1-2 that work)
- data_raw/musecat.json and/or data_raw/otogesetchi.json
- data_raw/integrate/scrape_kr_jp_report.json

Sources:
- KR: https://musecat.app/kr (api preferred)
- JP: https://w.atwiki.jp/otogesetchi/ (html) or https://otomap.net/

Focus on rhythm games only. Output merge-friendly JSON rows.
Polite crawl; --smoke supported.
`,
});

// ---- 5) SEA / AU Timezone + Insert Coin ----
jobs.push(#{
  label: "int:scrape-sea-au",
  subagent_type: "grok",
  prompt: `${COMMON}

YOU ARE: scrape-sea-au agent. slug = scrape_sea_au

OWN:
- scrapers/timezone.py and/or scrapers/insert_coin.py (best that work)
- data_raw/timezone.json and/or data_raw/insert_coin.json
- data_raw/integrate/scrape_sea_au_report.json

Priority:
1. Insert Coin https://www.insert-coin.app/ (api - multi-country rhythm locator)
2. Timezone locators (AU/NZ/SG/PH/ID) if patterns are consistent
   https://www.timezonegames.com/en-au/venues/ etc.

Rhythm-relevant fields only. Merge-friendly rows. --smoke.
`,
});

// ---- 6) Pipeline wire: merge + run_all for new sources ----
jobs.push(#{
  label: "int:pipeline-wire",
  subagent_type: "grok",
  prompt: `${COMMON}

YOU ARE: pipeline-wire agent. slug = pipeline_wire

OWN:
- scrapers/merge.py (loader hooks for new source files if present)
- scrapers/run_all.py (register new scrapers if modules exist)
- scrapers/common.py only if a tiny shared helper is needed
- docs/DATA_SOURCES.md (append short entries for wired sources)
- data_raw/integrate/pipeline_wire_report.json

Other agents create scrapers/* and data_raw/*.json in parallel. You must:
1. Inventory which of these exist after ~waiting is not possible - instead
   write DEFENSIVE loaders: if data_raw/nearcade.json exists, load it; else skip.
   Same for hkrgm2, hkarcade, mgm_tw, musecat, otogesetchi, timezone, insert_coin.
2. Assign each a source slug (nearcade, hkrgm2, musecat, ...) and include in
   SRC_ORDER / labels if those tables exist in merge or state.
3. Dedupe against existing ALL.Net/eagate/ziv/bemanicn by name+proximity or URL
   using existing merge patterns - do not invent loose 5km merges.
4. Do NOT require a full scrape of new sources in run_all default if slow;
   loading existing data_raw JSON on --skip-scrape is enough.
5. If no new raw files exist yet, still land the defensive hooks + docs stubs
   so the next scrape fills them.

Read merge.py source loading path carefully before editing.
Do not run multi-hour scrapes.
`,
});

print(`research-integrate: launching ${jobs.len()} parallel agents`);
let results = parallel(jobs);
let ok = 0;
for r in results {
  if r != () { ok += 1; }
}
print(`research-integrate done: ${ok}/${jobs.len()} returned`);
#{
  returned: ok,
  requested: jobs.len(),
  note: "reports under data_raw/integrate/*_report.json",
}
