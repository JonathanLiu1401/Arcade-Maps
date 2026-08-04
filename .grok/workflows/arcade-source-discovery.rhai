// Resume of Claude session workflow arcade-source-discovery
// (was wf_a40f3c9b-b93 + wf_d7334a62-108; agents died before writing reports)
let meta = #{
  name: "arcade-source-discovery",
  description: "Find regional arcade databases, wikis and locators this project does not yet use",
};

const REPO = "C:/Users/jonny/Desktop/Arcade Maps";

let regions = [
  #{ slug: "hk_tw_mo", name: "Hong Kong / Taiwan / Macau", countries: "Hong Kong, Taiwan, Macau", venues: "272 (10 other-only)" },
  #{ slug: "cn", name: "Mainland China", countries: "China", venues: "4863 (280 other-only)" },
  #{ slug: "jp", name: "Japan", countries: "Japan", venues: "1397 (122 other-only)" },
  #{ slug: "kr", name: "South Korea", countries: "South Korea", venues: "117 (8 other-only)" },
  #{ slug: "sea", name: "Southeast Asia", countries: "Philippines, Indonesia, Malaysia, Singapore, Thailand, Vietnam, Cambodia, Brunei, Myanmar, Laos", venues: "1122 (368 other-only)" },
  #{ slug: "us", name: "United States", countries: "United States", venues: "1473 (236 other-only)" },
  #{ slug: "ca_mx", name: "Canada and Mexico", countries: "Canada, Mexico", venues: "463 (244 other-only)" },
  #{ slug: "uk_ie", name: "United Kingdom and Ireland", countries: "United Kingdom, Ireland", venues: "747 (428 other-only)" },
  #{ slug: "eu_west", name: "Western Europe", countries: "France, Germany, Netherlands, Belgium, Spain, Portugal, Italy, Switzerland, Austria, Luxembourg", venues: "460 (198 other-only)" },
  #{ slug: "eu_nordic_east", name: "Nordics and Eastern Europe", countries: "Sweden, Norway, Finland, Denmark, Iceland, Poland, Czechia, Czech Republic, Hungary, Romania, Bulgaria, Ukraine, Russia, Baltics, Balkans, Greece", venues: "171 (81 other-only)" },
  #{ slug: "oceania", name: "Australia and New Zealand", countries: "Australia, New Zealand", venues: "276 (91 other-only)" },
  #{ slug: "latam", name: "Latin America", countries: "Brazil, Mexico, Argentina, Chile, Colombia, Peru, Uruguay, Costa Rica, Guatemala, Venezuela, Ecuador, Bolivia, Paraguay, Panama", venues: "478 (157 other-only)" },
  #{ slug: "me_af_sa", name: "Middle East, Africa, South Asia", countries: "UAE, Saudi Arabia, Israel, Turkey, Egypt, South Africa, Ghana, Morocco, India, and neighbors", venues: "144 (68 other-only)" },
];

let jobs = [];
for r in regions {
  let slug = r.slug;
  let name = r.name;
  let countries = r.countries;
  let venues = r.venues;
  let out_path = `${REPO}/data_raw/sources/found_${slug}.json`;
  let prompt = `
REPO: ${REPO} (branch main). Windows PowerShell.

HARD RULES:
- NEVER use an em dash. Hyphen, colon, or two sentences.
- Python stdlib-only. Set PYTHONIOENCODING=utf-8 for CJK.
- Do NOT run git mutate commands. Do NOT create subagents.
- Do NOT edit data/, js/, scrapers/, or index.html.
- Your ONLY deliverable is writing the JSON report file below. Actually write it with the Write/file tool.

YOU ARE SOURCE SCOUT for: ${name}
Countries: ${countries}
Venues the map currently has here: ${venues}

WHY: The map has ~12k rhythm arcades from ALL.Net, e-amusement, WAHLAP, BemaniCN, Round1 USA, ZIv only.
2,312 venues show Other / no music games because ZIv has no machine list. HK had hkarcade.fandom.com with full cab lists nobody had wired up. Find equivalents for your region.

GOOD FINDS (priority order):
1. Structured per-venue database/wiki/map with games or cabinets (like hkarcade.fandom.com)
2. Official operator/chain locator not already used
3. Community map/spreadsheet with venue-level detail
4. Forum/subreddit with a maintained pinned venue list
5. Enthusiast blog that systematically covers a region

NOT a find: the six sources above; one-off blog posts; Google Maps/Yelp/TripAdvisor as data sources (reference only ok); dead sites.

SUPREME RULE: never claim more than evidence supports. Unopenable site = unverified. Three real tested sources beat thirty plausible URLs.

Search in the LOCAL language (機舖 / 게임장 / ゲーセン / 机厅 / fliperama / etc).

For every candidate you report, you MUST open it (WebFetch/open) and confirm: responds today; lists MULTIPLE venues; per-venue detail (games/cabs/address/hours/prices); rough venue count; machine_readable api|url_pattern|html_scrape|manual_only.

Compare 3 example venues against ${REPO}/data/arcades.json - does the source add games we lack?

WRITE this exact file (create parent dirs if needed): ${out_path}

{
  "region": "${name}",
  "sources": [
    {
      "name": "...",
      "url": "...",
      "kind": "wiki|community_map|official_locator|forum|spreadsheet|blog|other",
      "languages": ["..."],
      "countries_covered": ["..."],
      "venues_estimated": null,
      "per_venue_detail": ["games", "cab_counts", "prices", "hours", "address"],
      "machine_readable": "api|url_pattern|html_scrape|manual_only",
      "example_venue_url": "...",
      "example_data_quote": "...",
      "adds_over_current": "...",
      "still_live": true,
      "checked_at": "2026-08-04",
      "note": "..."
    }
  ],
  "summary": "what you searched, found, and empty dead-ends",
  "dead_ends": "sites checked that failed"
}

If the region has no dedicated source, write sources:[] and say so. That is a useful result.
After writing the file, briefly confirm path + n_sources in your final message.
`;
  jobs.push(#{
    label: `sources:${slug}`,
    prompt: prompt,
    subagent_type: "grok",
  });
}

print(`source discovery: launching ${jobs.len()} region scouts`);
let results = parallel(jobs);
let ok = 0;
for r in results {
  if r != () {
    ok += 1;
  }
}
print(`source discovery done: ${ok}/${jobs.len()} agents returned`);
#{
  returned: ok,
  requested: jobs.len(),
  note: "reports under data_raw/sources/found_*.json",
}
