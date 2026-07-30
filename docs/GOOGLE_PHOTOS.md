# Google Places photos (optional)

Most arcades on this map have no photo. Coverage is about 7.5% overall, 3% in
Japan and effectively 0% in China, and the photos we do have come from
community uploads that are often years old. This is the optional path that
fills the gap using Google's own photo of the venue.

It is **off by default and costs nothing until you turn it on.** With no API
key configured the site behaves exactly as it does today: no Google request is
made, nothing appears in the console, and every fallback works as before.

---

## The rule that shapes the whole design

Google's terms treat place IDs and photos completely differently, and this is
worth understanding before you enable anything, because it explains why the
setup has two halves.

**Place IDs may be stored.** Google states they are "exempt from the caching
restrictions stated in Section 3.2.3(b) of the Google Maps Platform Terms of
Service" and that "you can therefore store place ID values indefinitely". They
recommend refreshing IDs older than 12 months, which is free.

**Photos may not be stored.** The Place Photos documentation is blunt: *"You
cannot cache a photo name. Also, the name can expire."*

So the design is:

| What | Where | Stored? |
| --- | --- | --- |
| place ID | `data/place_ids.json`, committed | yes, permitted explicitly |
| photo name | fetched live, used once, discarded | never |
| photo bytes | loaded by the browser from Google's URL | never |

No photo is ever written into this repo, into any data file, into
localStorage, or into sessionStorage. The only cache is a plain JavaScript
object that dies when the tab closes, and it exists only so that reopening the
same panel does not bill you twice.

---

## What it costs

Verified against Google's published pricing list on 2026-07-30. Check it again
before you enable billing, because these numbers move.

Free tier since 2025-03-01 is **per-SKU free calls per month**: 10,000 for
Essentials SKUs, 5,000 for Pro, 1,000 for Enterprise. The old $200 monthly
credit is gone.

### One-off: resolving place IDs

`scrapers/place_ids.py` uses **Text Search Pro** at **$32.00 per 1,000**, with
**5,000 free per month**.

It has to be Pro. There is a free "Text Search Essentials (IDs Only)" SKU, but
it returns nothing except the ID, which means nothing to verify the match
against. Using it would mean storing IDs we have not checked, and a wrong ID
puts a photo of the wrong building on an arcade. The Pro fields (name, address,
coordinates) are what make the verification possible, so they are the honest
cost of not being wrong.

| Scope | Calls | Cost if done in one month |
| --- | --- | --- |
| Japan only (~1,400) | 1,400 | **$0** (inside the free 5,000) |
| Japan + Korea + Taiwan + SE Asia | ~2,700 | **$0** |
| Everything (13,534 arcades) | 13,534 | ~**$273** |
| Everything, spread over 3 months | 4,500/month | **$0** |

The script defaults to 200 arcades per run and refuses `--all` unless you also
pass `--yes`, so it cannot spend hundreds of dollars because you typed the
wrong thing. It prints the estimate before it does anything.

Refreshing IDs later (`--refresh`) uses the free **Place Details Essentials
IDs Only** SKU and costs nothing.

### Ongoing: showing photos

Each panel a visitor opens for an arcade with no photo of its own costs:

1. **Place Details, `fields=photos`** - free (Essentials IDs Only SKU), gets
   the photo name and its attributions. This has to happen every session
   because the name may not be cached.
2. **Place Details Photos** - **Enterprise SKU, 1,000 free per month, then
   $7.00 per 1,000**. This is the one that costs money.

So the practical budget is **about 1,000 free photo views a month**, and after
that roughly **$0.007 per photo**.

A photo is only fetched when someone actually opens a place panel for an
arcade that has no photo of its own. Never on map load, never for a marker,
never for the 13,534 stores nobody clicked. Reopening the same panel in the
same session is free.

### If the map gets popular

At more than ~1,000 opened panels a month you will exceed the free photo pool.
Two honest options:

- **Do nothing.** Google returns HTTP 403 once you are over quota, this code
  detects that, stops asking for the rest of the session, and every panel
  falls back to the existing photo chain. Visitors see the site as it is
  today. Nothing breaks and you are not billed.
- **Enable billing** and accept ~$7 per additional 1,000 photo views.

There is a subtlety worth knowing: an over-quota request returns 403 *along
with a "quota exceeded" notification image*. A plain `<img>` tag would render
that image as though it were the arcade. That is why this code requests
`skipHttpRedirect=true` and reads the JSON response, so a failure is a status
code it can check rather than a misleading picture it would display.

---

## Setup

### 1. Create the key

1. Go to the [Google Cloud console](https://console.cloud.google.com/), create
   a project (or pick one).
2. Enable billing on it. The free monthly calls still apply, but Google will
   not issue a usable Maps key without a billing account attached.
3. **APIs and services** -> **Library** -> enable **Places API (New)**. Enable
   only this one. Do not enable the legacy Places API; nothing here uses it.
4. **APIs and services** -> **Credentials** -> **Create credentials** ->
   **API key**.

### 2. Restrict the key. Do not skip this.

The browser key is public by design: anyone can read it in the page source.
That is expected and it is how every client-side Maps integration works. The
security boundary is **not secrecy**, it is the two restrictions below. An
unrestricted key found in your page source can be used by anyone, on any site,
billed to you.

On the key's settings page:

**Application restrictions** -> **Websites**, and add exactly:

```
https://jonathanliu1401.github.io/*
http://localhost:*
http://127.0.0.1:*
```

The first is the live site. The two local entries are for development
(`python3 -m http.server`); drop them if you never test locally.

**API restrictions** -> **Restrict key** -> select **Places API (New)** only.

With both set, a key lifted from your page source is useless anywhere except
your own origins, and it can only call the one API.

A caution the referrer restriction does not solve: someone can still open your
real site and open panels in a loop to burn your quota. There is no fix for
that without a backend, which this site does not have. The exposure is capped
by your billing limits, so set a **budget alert** in Google Cloud Billing.

### 3. Resolve place IDs

Set the key in your shell (this is used only by the offline script; it is not
the value you put in the page):

```bash
export GOOGLE_MAPS_API_KEY="AIza..."          # bash
$env:GOOGLE_MAPS_API_KEY = "AIza..."          # PowerShell
```

Then, from the repo root:

```bash
# See what it would do. Requests nothing, costs nothing.
python scrapers/place_ids.py --dry-run

# Start with Japan: about 1,400 arcades, inside the free monthly pool.
python scrapers/place_ids.py --country Japan --all --yes

# Or a small test run first (200 arcades, the default).
python scrapers/place_ids.py --limit 50
```

This writes `data/place_ids.json`. Commit it: those IDs are the durable,
permitted artifact, and having them means you never pay to resolve them twice.

The run is resumable and incremental. It writes every 25 arcades, skips
anything already resolved, and records explicit misses so a re-run does not
re-pay for arcades Google has no good answer for.

**Every match is verified before it is stored.** An answer is accepted only
when Google's location is within 300 m of our pin *and* the names agree, with
both a similarity score and a brand-head check (see below). Each record keeps
its distance, score and a confidence grade, and rejections are written to the
file with the reason, so a questionable match can be audited rather than
guessed at.

### 4. Turn it on in the page

In `index.html`, near the bottom, fill in the key:

```html
<script>
window.AM_CONFIG = {
  googleMapsApiKey: "AIza...",
  googlePhotoMinConfidence: "high"
};
</script>
```

That is the whole frontend change. Leave the key as `""` and everything stays
off.

`googlePhotoMinConfidence` controls which stored IDs are trusted enough to
show a photo for:

- `"high"` (default) - the match was confirmed by both distance and name.
- `"medium"` - also allows weaker matches, including China rows that are
  placed at a district centroid rather than a real coordinate. More photos,
  and a real chance one of them is the building next door.

`"high"` is the default deliberately. On a map whose entire value is being
right about where something is, a missing photo is much cheaper than a
confident photo of the wrong place.

### 5. Refresh, about once a year

Google recommends refreshing place IDs older than 12 months. It is free:

```bash
python scrapers/place_ids.py --refresh --all
```

This re-checks stored IDs, updates any that Google has reissued, and drops any
that have become obsolete (a closed or moved business) so the site never points
at a dead ID.

---

## How the matching avoids wrong photos

This is the part worth scrutinising, because the failure mode is a photo of a
building that is not the arcade.

A Text Search answer is accepted only if **both** tests pass:

**Distance.** Google's coordinate must be within 300 m of ours. That is
generous enough for a large mall whose registered point sits away from the
arcade inside it, and tight enough that another arcade rarely qualifies.

**Name.** Two checks, because one is not enough. The similarity score alone is
actively misleading here: venue names in Japan usually end in their location,
so unrelated businesses in the same district score *higher* than the same
arcade written in two scripts. Measured on real name shapes:

```
GiGO Shinjuku           vs  Namco Shinjuku          0.696   different venues
Taito Station Ikebukuro vs  Round1 Ikebukuro        0.581   different venues
GiGO Akihabara 1        vs  GiGO                    0.375   same venue
GiGO Akihabara 3        vs  ギーゴ秋葉原3号館          0.273   same venue
```

No threshold separates those, so the *front* of the name is checked too: two
different arcades in one district share the suffix and differ at the front,
while one arcade written two ways shares the front. Both signals must agree.

Rows placed at a district or city centroid (mostly China) are skipped by
default, because a distance test against an administrative centroid means
nothing. With `--include-approx` they are resolved under a much stricter name
requirement and capped at `medium` confidence, so the default `high` gate still
refuses them.

**Known blind spot, stated plainly:** the name comparer romanizes kana but not
kanji, so a venue we hold in romaji that Google names in kanji ("ラウンドワン
スタジアム 町田店" vs "Round1 Stadium Machida") usually will not match. Those
land in the `misses` map and simply get no Google photo. That is the intended
trade: a miss costs nothing, a wrong photo costs the map's credibility.

`scrapers/test_place_ids.py` asserts all of this, including a table of 13
adversarial pairs (neighbouring arcades, unrelated tenants, chain branches in
other cities) that must never be accepted. Run it with:

```bash
python scrapers/test_place_ids.py
```

---

## Attribution

Google requires it and it is not optional. From the Place Photos docs: *"if the
returned photo element includes a value in the authorAttributions field, you
must include the additional attribution in your application wherever you
display the image."* The policy page adds that you *"must always credit the
author when displaying photos or reviews"* and must let users reach the
original on Google Maps.

Every Google photo therefore renders a credit line naming the photo's author
and Google Maps, linked to the place's Google Maps page. This happens per
photo, from the attributions returned with that photo. There is no way to turn
it off, which is intentional.

---

## Where our own photos fit

A real venue photo we already have always wins. Ours is licence-clean and free,
so Google is only ever asked when we have nothing. The order is:

1. our own photo(s) of the venue, from enrichment
2. a Google photo of the venue *(this feature)*
3. a stock photo of a cabinet the store has, from `assets/cabs`
4. the game-tinted gradient banner

Google sits above the cab photo on purpose: a cab shot is a stock picture of a
*machine*, not of this venue, and a real photo of the actual building tells the
reader more. If you would rather keep cab photos ahead of Google's, that is one
line in `js/panel.js` (the `AM.gphotos.records(a)` call in `heroHtml`).

---

## Files

| File | Role |
| --- | --- |
| `scrapers/place_ids.py` | offline place-ID resolution and verification |
| `scrapers/test_place_ids.py` | unit tests, including the rejection cases |
| `data/place_ids.json` | the resolved IDs (commit this) |
| `js/gphotos.js` | runtime photo fetch, session-only cache |
| `index.html` | `AM_CONFIG` - where the key goes |

The weekly GitHub Action has no key and never will: `place_ids.py` is not part
of `run_all.py`, and with no `GOOGLE_MAPS_API_KEY` it makes no request and
exits 0.
