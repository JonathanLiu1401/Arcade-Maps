# Venue photo attribution

The images in `assets/venues/` are **not** covered by this repository's MIT
license. They are third-party photographs mirrored here with attribution, a
deep link back to the source page for every file, and the takedown path below.

## `assets/venues/cn/` - BemaniCN community map

| | |
| --- | --- |
| Source | [BemaniCN arcade map](https://map.bemanicn.com) (map.bemanicn.com) |
| Credit line shown in the UI | `Photo: BemaniCN community map` |
| Per-shop source page | `https://map.bemanicn.com/s/<shop_id>` |
| File naming | `assets/venues/cn/<shop_id>.jpg` - the filename **is** the BemaniCN shop id |
| Authoritative per-file record | [`data_raw/bemanicn_photos.json`](../../data_raw/bemanicn_photos.json) |
| Harvested by | [`scrapers/bemanicn_photos.py`](../../scrapers/bemanicn_photos.py) |

Every mirrored file has a row in `data_raw/bemanicn_photos.json` carrying its
`source_url` (the shop page it came from), `sha256`, byte size, real pixel
dimensions, and fetch timestamp. That index is the attribution record; it is
not duplicated as a table here because it runs to thousands of rows.

Bytes are stored exactly as served. Nothing is re-encoded, cropped, or resized.

### Licence position (please read before reusing these files)

This is an honest statement of an unclear situation, not a claim of a licence:

- BemaniCN publishes **no** public terms of service, no copyright page, and no
  Creative Commons grant. `/terms`, `/privacy`, `/tos` and `/agreement` all
  return HTTP 404. The site meta carries `(c) BEMANICN`.
- The photos are **community uploads** contributed by players to identify
  venues on a public map. They are not a freely-licensed corpus.
- We therefore do **not** relicense them. They are not MIT. Downstream reuse of
  an individual photo is between the reuser and its uploader.

### Why these are mirrored rather than linked

BemaniCN serves each thumbnail from a **signed** OSS URL: the link carries an
expiry and a token scoped to one exact path, and it stops working within the
hour. Stripping the token, stripping the `-thumbnail` suffix, or requesting any
other size returns HTTP 401. A stored link would be dead before anyone loaded
the page, so mirroring the bytes is the only way this source yields a working
photo at all.

We mirror on the narrow basis that the source already publishes this exact
thumbnail publicly for venue identification, which is the same purpose it
serves here, and that every copy carries attribution and a link home. That is
community courtesy, not a written grant.

### What these files are (and are not)

These are **thumbnails**: roughly 150-200 px on the long edge and 7-10 KB each.
The full-size original and the multi-photo gallery are behind a login and are
not publicly reachable. Use the `w` and `h` fields in the index and render
these at their native size. Do not upscale a 200 px thumbnail into a hero slot.

A minority of shops upload a notice poster, a price-list screenshot, or a
promotional graphic instead of a photo of the venue. Treat these as "the picture
the venue's community posted", not as a guaranteed photograph of the premises.
The index flags the most obvious cases with `extreme_aspect` (a long sliver is
almost always a screenshot); `dup_count` marks a cover reused across several
branches of a chain, which is a brand image rather than that branch.

## Takedown

If you uploaded one of these photos, or you hold rights in one, and you want it
removed, we will remove it. No justification needed and no argument from us.

1. Open an issue on this repository titled `takedown: <shop_id>` (the shop id is
   the filename), **or** contact the repository owner through the address on the
   GitHub profile that owns this repo.
2. Say which file or shop id is affected. "All of them" is a valid answer.
3. The file is deleted from `assets/venues/`, its row is removed from
   `data_raw/bemanicn_photos.json`, and the site falls back to a no-photo state
   for that venue.

If BemaniCN as a site asks us to stop mirroring, the entire `assets/venues/cn/`
tree is deleted and the map degrades to linking out to
`https://map.bemanicn.com/s/<shop_id>` instead.

## Related

Representative cabinet photos (stock images of a game's cabinet, never used as
a venue photo) live in [`assets/cabs/`](../cabs/ATTRIBUTION.md) and are
separately licensed from Wikimedia Commons.
