import json
from pathlib import Path
from datetime import date

oa_path = Path("data/owner_attested.json")
oa = json.loads(oa_path.read_text(encoding="utf-8"))
key = "allnet|https://location.am-all.net/alm/shop?sid=18325"
oa["venues"][key] = {
    "name": "ONE MORE EXTRA STAGE",
    "exclude": True,
    "attested_by": "research-fleet",
    "attested_at": str(date.today()),
    "evidence_url": "https://www.google.com/maps/search/?api=1&query=One+More+Extra+Stage+1313+W+El+Camino+Real+Mountain+View",
    "note": "Remove from map. Google Maps: Temporarily closed at 1313 W El Camino Real A, Mountain View. ALL.Net-only maimai intl registration (sid=18325) with no public hours, no ZIv/community corroboration. Not a useful music-map listing; prefer silence over a closed/open ghost pin.",
}
# drop closed-only fields if we previously set them elsewhere
oa_path.write_text(json.dumps(oa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("owner_attested exclude", key)

data = json.loads(Path("data/arcades.json").read_text(encoding="utf-8"))
before = len(data["arcades"])
kept = []
removed = []
for a in data["arcades"]:
    name = (a.get("name") or "").upper()
    allnet = (a.get("links") or {}).get("allnet")
    if name == "ONE MORE EXTRA STAGE" or allnet == "https://location.am-all.net/alm/shop?sid=18325":
        removed.append((a.get("id"), a.get("sid"), a.get("name")))
        continue
    kept.append(a)
data["arcades"] = kept
# renumber ids? keep existing ids stable for share pages; do not renumber
# update stats if present
if "counts" in data and isinstance(data["counts"], dict):
    data["counts"]["total"] = len(kept)
# also stats.json
stats_path = Path("data/stats.json")
if stats_path.exists():
    st = json.loads(stats_path.read_text(encoding="utf-8"))
    if "counts" in st and isinstance(st["counts"], dict):
        st["counts"]["total"] = len(kept)
        # by_source allnet decrement if present
        bs = st["counts"].get("by_source") or {}
        if "allnet" in bs and bs["allnet"] > 0:
            bs["allnet"] = max(0, bs["allnet"] - len(removed))
        stats_path.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

Path("data/arcades.json").write_text(
    json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print("removed", removed)
print("arcades", before, "->", len(kept))

# drop share page if any for this sid
for sid in [r[1] for r in removed if r[1]]:
    p = Path("s") / (sid + ".html")
    if p.exists():
        p.unlink()
        print("deleted share", p)
