// Full-map deep research fleet: 128 agents comb every arcade.
// Broad scope: closed/open, exclude ghosts, games, addr, hours, website, remove noise.
// Agents write reports only; apply_deep_research_reports.py merges certain findings.
let meta = #{
  name: "arcade-deep-research",
  description: "128 agents research every arcade: correct/add/remove/close/exclude",
};

const REPO = "C:/Users/jonny/Desktop/Arcade Maps";

let shard_list = [];
if (type_of(args) == "map" && args.contains("shards")) {
  shard_list = args.shards;
} else {
  let i = 0;
  while i < 128 {
    shard_list.push(i);
    i += 1;
  }
}

let jobs = [];
for i in shard_list {
  let n = i;
  let pad = if n < 10 {
    `00${n}`
  } else if n < 100 {
    `0${n}`
  } else {
    `${n}`
  };
  let shard_path = `${REPO}/data_raw/deep_research/shards/deep_${pad}.json`;
  let out_path = `${REPO}/data_raw/deep_research/reports/deep_${pad}.json`;
  let prompt = `
REPO: ${REPO} (branch main). Windows PowerShell.

HARD RULES:
- NEVER use an em dash. Hyphen, colon, or two sentences.
- Python stdlib-only when scripting. Set PYTHONIOENCODING=utf-8 for CJK.
- Do NOT run git mutate commands. Do NOT create subagents.
- Do NOT edit data/, js/, scrapers/, or index.html.
- Your ONLY deliverable is writing the report file with Write tool. Actually write it.

YOU ARE DEEP RESEARCHER ${n}.
Shard: ${shard_path}
Report: ${out_path}

The shard has ~100 venues covering the FULL map (not just Other-only).
risk field: 0=ALL.Net-only outside Japan (highest ghost risk), 1=insert_coin-only,
2=other-only games, 3=single-source, 4=multi-source baseline.
Spend more time on risk 0-2. Still check risk 3-4 for closed/wrong/addr issues.

PER VENUE research (think outside the box; use local language):
1. Is it a real PUBLIC music-game venue, private home install, wrong business, or ghost?
2. Open / temporarily closed / permanently closed / never existed?
3. Address + coords correct? Google Maps business card, official chain finder, mall directory.
4. Games present or missing from our list? Counts only with hard evidence.
5. Hours, website, social, chain name.
6. Duplicate of another pin?
7. Should the listing be REMOVED (exclude) vs kept as closed?

WHERE TO LOOK:
- Google Maps business listing + reviews + "Temporarily closed" / "Permanently closed"
- ALL.Net location.am-all.net (gm=98 maimai intl, 104 chuni intl, 96/109 JP, 88 ongeki)
- e-amusement Japan facility search; WAHLAP China; BemaniCN; ZIv; nearcade; Insert Coin
- Chain sites: Round1, GiGO, Taito, Namco, Timezone, etc.
- Regional: hkarcade.fandom, MGM Taiwan, Musecat KR, otogesetchi wiki
- Social: Reddit, FB groups, Bilibili/XHS, PTT/Dcard, DCInside, Instagram venue tags
- News / city licenses / mall tenant lists

SUPREME RULES:
- Never invent games, hours, or open status.
- Prefer silence over a wrong open pin (owner policy: prefer nothing over closed/expired).
- ALL.Net alone outside Japan is weak: require independent public evidence before leaving open.
- Google Maps "Temporarily closed" or "Permanently closed" with matching name+address is strong closed evidence.
- Do not declare confirmed_none just because you found nothing (use unknown).
- Prefer newest sources; date everything.

WRITE: ${out_path} as JSON:

{
  "shard": ${n},
  "checked": <number researched this run>,
  "sources_used": ["url", ...],
  "findings": [
    {
      "sid": "<from shard KEY>",
      "id": <from shard>,
      "name": "<as in shard>",
      "verdict": "ok|closed|exclude|add_games|remove_games|fix_addr|unknown",
      "games": ["maimai_dx"],
      "closed_reason": "...",
      "confidence": "certain|likely|unverified",
      "evidence_url": "https://...",
      "evidence_quote": "short quote",
      "evidence_date": "YYYY-MM-DD or null",
      "checked_at": "2026-08-04",
      "note": "what was wrong and what to do"
    }
  ],
  "skipped_ok": <approx count that looked fine with multi-source>,
  "notes": "..."
}

Only include findings that change something or flag risk. Pure "ok" multi-source venues need not list every row if time is short - put count in skipped_ok.
MUST research ALL risk 0-1 venues in the shard thoroughly.
MUST write the file even if findings is empty.
`;

  jobs.push(#{
    prompt: prompt,
    description: `deep research shard ${pad}`,
    subagent_type: "general-purpose",
  });
}

// Fan out all shards (host may schedule). Budget must cover 128 agents.
let results = parallel(jobs);
let wrote = 0;
let failed = 0;
for r in results {
  if r == () {
    failed += 1;
  } else {
    wrote += 1;
  }
}

#{
  note: "reports under data_raw/deep_research/reports/deep_*.json; apply with tools/apply_deep_research_reports.py",
  requested: shard_list.len(),
  returned: results.len(),
  wrote: wrote,
  failed: failed,
}
