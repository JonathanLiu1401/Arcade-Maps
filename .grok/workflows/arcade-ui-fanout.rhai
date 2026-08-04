// Parallel fan-out: share-card map pin, size filter, multi-language UI
let meta = #{
  name: "arcade-ui-fanout",
  description: "Parallel: Discord share map pin, cab-size filter, i18n + language button",
};

const REPO = "C:/Users/jonny/Desktop/Arcade Maps";

const COMMON = `
REPO: ${REPO} (branch main). Windows PowerShell.

HARD RULES:
- NEVER use an em dash. Use hyphen, colon, or two sentences.
- Do NOT run git commit, git push, or git mutate commands.
- Do NOT create subagents or spawn further agents.
- Do NOT run the full scrape pipeline.
- Prefer surgical Search/Edit of existing files over rewriting whole files.
- Keep ASCII punctuation (no em dash). UTF-8 is fine for CJK translation strings.
- After JS/CSS edits, run: python tools/stamp_assets.py
- When done, write a short captain report to:
  ${REPO}/data_raw/ui_fanout/<your_slug>_report.json
  with keys: slug, files_changed[], summary, how_to_verify, risks[]

Context: live site https://jonathanliu1401.github.io/Arcade-Maps/
Share pages already exist at s/<sid>.html with OG tags (name, games, venue/cab photo).
Settings gear is injected by js/settings.js buildGear() before #repo-link.
Marker size tiers already exist in js/markers.js TIER_CLASSES (1-2, 3-9, 10-19, 20-49, 50+, U unknown).
`;

let jobs = [];

// ---- 1) Share cards: photo + city-level map pin ----
jobs.push(#{
  label: "ui:share-map",
  subagent_type: "grok",
  prompt: `${COMMON}

YOU ARE: share-map agent. slug = share_map

OWN THESE FILES ONLY (do not edit others):
- scrapers/build_share_pages.py
- (optional) scrapers/test_share_pages.py if you add tests
- Write report: data_raw/ui_fanout/share_map_report.json

GOAL
Discord unfurl already shows venue name/games/photo. Improve share pages so the
card/page also shows a MAP PIN of the arcade at prefecture/city zoom on the RIGHT.

Discord link previews only reliably use ONE og:image. So:
1. HTML body of s/<sid>.html: two-column layout - left venue/cab image, right
   static map with pin at city/prefecture zoom (zoom ~10-12, not street-level 16).
2. og:image strategy:
   - Prefer keeping the venue photo as primary og:image when present (user liked it).
   - ALSO emit a second og:image pointing at the static map URL (some clients show one;
     the HTML card always shows both for humans who open the link).
   - If no coords, skip map column and map og:image.
3. Static map without API keys. Use a free OSM static endpoint, e.g.:
   https://staticmap.openstreetmap.de/staticmap.php?center=LAT,LNG&zoom=11&size=600x400&maptype=mapnik&markers=LAT,LNG,red-pushpin
   Escape properly. Document fallback if the service is down (hide map img onerror).
4. Map column caption: country / pref if available.
5. Do NOT regenerate all 12k HTML files in this agent if too heavy - change the
   generator and run it for at least 2 proof pages:
   - s/z195.html (Quantum SM City Bacolod, no venue photo)
   - s/b4712.html or s/b1.html (China with venue photo under assets/venues)
   Full rebuild is optional if run finishes in <2 min; otherwise generator-only + 2 samples.

6. Browser JS redirect to the map can stay, but delay ~1.5-2s OR only redirect when
   ?go=1 so humans can see the dual card. Prefer: redirect after 2s for normal browsers,
   never for Discordbot/Twitterbot/etc. (already partially implemented).

Deliver working generator + sample pages + report.
`,
});

// ---- 2) Size filter by cabinet count ----
jobs.push(#{
  label: "ui:size-filter",
  subagent_type: "grok",
  prompt: `${COMMON}

YOU ARE: size-filter agent. slug = size_filter

OWN THESE FILES ONLY:
- js/state.js  (add selectedSizeTiers Set + toggleSizeTier + init defaults)
- js/markers.js (isVisible must AND size tier match via tierFor)
- js/panel.js (build size tier chips UI, sync, all/none)
- index.html (only the filter pane: add Arcade size section markup after cab variants)
- style.css (only styles for size chips; append near existing .chip styles)
- Write report: data_raw/ui_fanout/size_filter_report.json

GOAL
Add a filter for arcade SIZE (cabinet count), reusing the same bands as marker tiers:

  T1 1-2, T2 3-9, T3 10-19, T4 20-49, T5 50+, TU unknown (no trusted count)

Behavior:
- Default: ALL size tiers selected (map looks unchanged).
- Chips in Filters drawer under a "Arcade size" heading with all/none shortcuts.
- Counts on chips = plottable arcades in that tier (like game chips).
- isVisible(a) requires tierFor(a).id in selectedSizeTiers.
- Do NOT change tier geometry or TRUSTED_COUNTS policy.
- Wire AM.state.on("selectedSizeTiers", ...) so markers rebuild (same pattern as selectedGames).
- Hash URL: optional size=1,2,U segment is NICE but not required if it risks mapcore conflicts; skip hash if unsure.
- Persist size filter? Prefer session-only (not localStorage) unless easy.

Read markers.js tierFor/showableCabs/isVisible and panel.js buildChips first.
After edits: python tools/stamp_assets.py

Deliver working size filter + report.
`,
});

// ---- 3) i18n + language button next to settings ----
jobs.push(#{
  label: "ui:i18n",
  subagent_type: "grok",
  prompt: `${COMMON}

YOU ARE: i18n agent. slug = i18n

OWN THESE FILES ONLY:
- js/i18n.js  (CREATE - full module)
- js/settings.js (insert language button LEFT of settings gear; do not break settings modal)
- js/app-init.js (call AM.i18n.init() early after DOM ready / with build)
- index.html (add data-i18n keys on static chrome strings; load i18n.js before settings.js)
- style.css (styles for .am-lang-btn and language menu; match .sd-gear sizing)
- Write report: data_raw/ui_fanout/i18n_report.json

GOAL
1) Top-right language button next to the settings gear (Google Translate style:
   simple "A" + latin/character glyph or globe/translate icon SVG).
   settings.js buildGear() inserts gear before #repo-link. Insert language control
   BEFORE the gear so order is: ... search | lang | gear | github.

2) Click opens a compact popover/menu of languages (not a full settings page).
   Selecting a language applies immediately, closes menu, persists in localStorage
   key e.g. am_lang.

3) Languages (native names in menu). Cover countries with many arcades:
   - en English
   - zh-Hans 简体中文
   - zh-Hant 繁體中文
   - ja 日本語
   - ko 한국어
   - id Bahasa Indonesia
   - ms Bahasa Melayu
   - th ไทย
   - vi Tiếng Việt
   - fil Filipino
   - es Español
   - fr Français
   - de Deutsch
   - pt Português
   - it Italiano
   - ru Русский
   Detect browser language on first visit (navigator.languages), fallback en.

4) AM.i18n.t(key) / data-i18n="key" / data-i18n-placeholder / data-i18n-title / data-i18n-aria
   Translate UI chrome: header, filter titles, buttons (all/none), drawer tabs,
   search placeholder, settings modal titles/labels/descriptions, legend, nearby,
   empty states, share toast strings if easy.
   Do NOT translate game brand names (maimai DX, CHUNITHM, etc.) - keep official names.
   Country names in data can stay as stored English for now.

5) Keep i18n.js self-contained with nested dicts. Missing keys fall back to en then key.
   apply() re-walks [data-i18n] and updates dynamic bits settings rebuilds if needed.

6) After edits: python tools/stamp_assets.py
   Ensure script order in index.html: state.js ... i18n.js before settings.js and panel if needed.

Deliver working language button + translations for all listed langs for core chrome
(at least en fully; other langs complete for main UI strings) + report.
`,
});

print(`arcade-ui-fanout: launching ${jobs.len()} parallel agents`);
let results = parallel(jobs);
let ok = 0;
for r in results {
  if r != () {
    ok += 1;
  }
}
print(`arcade-ui-fanout done: ${ok}/${jobs.len()} agents returned`);
#{
  returned: ok,
  requested: jobs.len(),
  note: "reports under data_raw/ui_fanout/*_report.json",
}
