import json
from pathlib import Path
from datetime import date

oa_path = Path("data/owner_attested.json")
oa = json.loads(oa_path.read_text(encoding="utf-8"))
venues = oa.setdefault("venues", {})

# Exclude SF JAPAN CENTER ALL.Net duplicate
excl_key = "allnet|https://location.am-all.net/alm/shop?sid=18524"
venues[excl_key] = {
    "name": "SF JAPAN CENTER",
    "exclude": True,
    "attested_by": "research-fleet",
    "attested_at": str(date.today()),
    "evidence_url": "https://zenius-i-vanisher.com/v5.2/arcade.php?id=9174",
    "note": "Duplicate of Kiddleton Japantown (z9174) at Japan Center SF. ALL.Net used Webster St #225 mall address; ZIv/IC/public use 1737 Post St. Same venue ~23m apart. Merge allnet into Kiddleton; exclude this pin.",
}

# Record merge on keep side via ziv key
keep_key = "ziv|https://zenius-i-vanisher.com/v5.2/arcade.php?id=9174"
rec = dict(venues.get(keep_key) or {})
rec.update({
    "name": "Kiddleton Japantown",
    "attested_by": "research-fleet",
    "attested_at": str(date.today()),
    "evidence_url": "https://location.am-all.net/alm/shop?sid=18524",
    "note": "Merged SF JAPAN CENTER ALL.Net shop sid=18524 (1581 Webster St #225) into this pin. Same Japan Center Kiddleton; Post St is the public entrance address.",
})
venues[keep_key] = rec
oa_path.write_text(json.dumps(oa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("owner_attested ok")

data = json.loads(Path("data/arcades.json").read_text(encoding="utf-8"))
before = len(data["arcades"])
kept = []
removed = []
allnet_url = "https://location.am-all.net/alm/shop?sid=18524"
for a in data["arcades"]:
    sid = a.get("sid")
    name = (a.get("name") or "").upper()
    links = dict(a.get("links") or {})
    # drop duplicate
    if sid == "hf905d8010f" or name == "SF JAPAN CENTER" or links.get("allnet") == allnet_url:
        # only drop if it's the allnet-only japan center row, not if somehow same url on kiddleton
        if sid != "z9174" and "kiddleton" not in (a.get("name") or "").lower():
            removed.append((a.get("id"), sid, a.get("name")))
            continue
    # merge allnet onto kiddleton
    if sid == "z9174" or (a.get("name") or "") == "Kiddleton Japantown":
        src = list(a.get("src") or [])
        if "allnet" not in src:
            src.append("allnet")
            # keep roughly priority order
            order = ["allnet", "eagate", "wahlap", "bemanicn", "ziv", "round1usa", "community",
                     "nearcade", "hkrgm2", "insert_coin", "musecat", "maimaidx_tw", "otogesetchi",
                     "timezone", "wahlap_gc"]
            src = sorted(set(src), key=lambda s: order.index(s) if s in order else 99)
            a["src"] = src
        links["allnet"] = allnet_url
        a["links"] = links
        print("merged allnet onto", a.get("sid"), a.get("name"), "src=", a["src"])
    kept.append(a)

data["arcades"] = kept
Path("data/arcades.json").write_text(
    json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

st_path = Path("data/stats.json")
if st_path.exists():
    st = json.loads(st_path.read_text(encoding="utf-8"))
    if isinstance(st.get("counts"), dict):
        st["counts"]["total"] = len(kept)
        bs = st["counts"].setdefault("by_source", {})
        if "allnet" in bs and removed:
            # allnet count stays: one pin still has allnet
            pass
        st_path.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

for _, sid, _ in removed:
    if sid:
        p = Path("s") / (f"{sid}.html")
        if p.exists():
            p.unlink()
            print("deleted share", p)

print("removed", removed)
print("arcades", before, "->", len(kept))

# verify single pin near japantown
from math import radians, cos, sin, asin, sqrt
def hav(a,b):
    lat1,lon1=a; lat2,lon2=b
    r=6371
    dlat=radians(lat2-lat1); dlon=radians(lon2-lon1)
    x=sin(dlat/2)**2+cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2*r*asin(sqrt(x))*1000
near=[]
for a in kept:
    if a.get("lat") is None or a.get("country")!="United States": continue
    d=hav((37.7855,-122.4305),(a["lat"],a["lng"]))
    if d<200: near.append((d,a.get("name"),a.get("sid"),a.get("src")))
near.sort()
print("within 200m:", near)
