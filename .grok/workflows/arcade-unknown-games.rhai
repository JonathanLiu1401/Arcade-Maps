// Resume of Claude session workflow arcade-unknown-games
// (was wf_b640b09f-328, wf_2ab1ae2e-27b, wf_301396c9-519, wf_aad16fd4-c3a;
//  60 shards, agents died before writing reports)
let meta = #{
  name: "arcade-unknown-games",
  description: "Research Other-only arcades: has_games / confirmed_none / unknown / closed",
};

const REPO = "C:/Users/jonny/Desktop/Arcade Maps";

// Optional args.shards = array of shard ints; default all 0..59
let shard_list = [];
if (type_of(args) == "map" && args.contains("shards")) {
  shard_list = args.shards;
} else {
  let i = 0;
  while i < 60 {
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
  // pad for 0-59 as 000-059
  if n < 10 {
    pad = `00${n}`;
  } else {
    pad = `0${n}`;
  }
  let shard_path = `${REPO}/data_raw/unknown/shards/unk_${pad}.json`;
  let out_path = `${REPO}/data_raw/unknown/reports/unk_${pad}.json`;
  let prompt = `
REPO: ${REPO} (branch main). Windows PowerShell.

HARD RULES:
- NEVER use an em dash. Hyphen, colon, or two sentences.
- Python stdlib-only. Set PYTHONIOENCODING=utf-8 for CJK.
- Do NOT run git mutate commands. Do NOT create subagents.
- Do NOT edit data/, js/, scrapers/, or index.html.
- Your ONLY deliverable is writing the report file. Actually Write it.

YOU ARE RESEARCHER ${n}. Shard file: ${shard_path}

It holds ~39 venues with NO game list (shown as Other / No music game available).
Fields: id, sid, name, addr, country, pref, lat, lng, src, links, website, hours_text, n_images.
Grouped by country/region - do shared regional lookups FIRST, then stragglers.

Valid game slugs ONLY:
  maimai_dx chunithm ongeki project_diva sdvx iidx ddr polaris_chord gitadora
  jubeat popn nostalgia drs dance_around dance_evo museca reflec taiko wacca
  groove_coaster crossbeats beatstream pump_it_up stepmaniax other

WHY: ~19% of the map has empty game lists. ZIv silence is not "no games".
Per venue decide:
  (a) has_games - prove which, with evidence
  (b) confirmed_none - POSITIVE evidence of no rhythm games (bowling only, crane only, etc.)
  (c) unknown - nothing findable (honest, useful)
  (d) closed - shut down

WHERE TO LOOK (local language!):
  - Regional arcade wikis (hkarcade.fandom.com for HK; find local equivalents)
  - Official locators: ALL.Net location.am-all.net (gm 98 maimai intl, 104 chuni intl, 88 ongeki, 34 diva);
    e-amusement Japan; WAHLAP China; chain store finders
  - Venue own website/social
  - Player communities: Reddit, Facebook groups, Bilibili/小红书, X, PTT/Dcard, DCInside/Naver
  - Google Maps REVIEW TEXT ok for evidence; Google Maps PHOTOS are not usable

SUPREME RULE: never more confident than the source. Do not invent games. Do not declare empty just because you found nothing (that is unknown, not confirmed_none).

DATING: prefer newest sources. Old-only = note date and mark unverified.

WRITE: ${out_path}

{
  "shard": ${n},
  "checked": <number actually researched>,
  "sources_used": ["..."],
  "findings": [
    {
      "sid": "<from shard - KEY, never use id>",
      "name": "<as in shard>",
      "verdict": "has_games|confirmed_none|unknown|closed",
      "games": ["ddr", "maimai_dx"],
      "game_counts": {"ddr": 2},
      "confidence": "certain|likely|unverified",
      "evidence_url": "...",
      "evidence_quote": "...",
      "evidence_date": "YYYY-MM-DD or null",
      "checked_at": "2026-08-04",
      "note": "..."
    }
  ]
}

RULES:
- Key findings by sid, never id (ids reassign every build).
- Every finding needs evidence_url AND evidence_quote.
- game_counts ONLY when a source states a NUMBER. Presence without count: omit game_counts.
- confirmed_none needs positive evidence of no rhythm games.
- Ambiguous branch/name: unknown + note. Do not attach another venue's list.

Research as many of the ~39 as you can. Report honestly. Write the file before finishing.
Final message: path + counts of has_games / confirmed_none / unknown / closed.
`;
  jobs.push(#{
    label: `unk:shard${n}`,
    prompt: prompt,
    subagent_type: "grok",
  });
}

print(`unknown-games: launching ${jobs.len()} shard researchers`);
let results = parallel(jobs);
let ok = 0;
for r in results {
  if r != () {
    ok += 1;
  }
}
print(`unknown-games done: ${ok}/${jobs.len()} agents returned`);
#{
  returned: ok,
  requested: jobs.len(),
  note: "reports under data_raw/unknown/reports/unk_*.json",
}
