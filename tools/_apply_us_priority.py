import json
from pathlib import Path
from datetime import date

oa_path = Path("data/owner_attested.json")
oa = json.loads(oa_path.read_text(encoding="utf-8"))
venues = oa.setdefault("venues", {})

# OMES must stay exclude (not closed)
omes_key = "allnet|https://location.am-all.net/alm/shop?sid=18325"
venues[omes_key] = {
    "name": "ONE MORE EXTRA STAGE",
    "exclude": True,
    "attested_by": "research-fleet",
    "attested_at": str(date.today()),
    "evidence_url": "https://www.google.com/maps/search/?api=1&query=One+More+Extra+Stage+1313+W+El+Camino+Real+Mountain+View",
    "note": "Exclude. Google temporarily closed; ALL.Net-only ghost. Removed from map.",
}

# SIZIGI exclude
sizigi_key = "allnet|https://location.am-all.net/alm/shop?sid=18326"
venues[sizigi_key] = {
    "name": "SIZIGI 20TH STREET",
    "exclude": True,
    "attested_by": "research-fleet",
    "attested_at": str(date.today()),
    "evidence_url": "https://location.am-all.net/alm/shop?sid=18326",
    "note": "Exclude. 933 20th St San Francisco is commercial/biotech office space, not a walk-in arcade. ALL.Net-only ghost/private install pattern. Prefer silence.",
}

# Rec Room Brentwood country fix via addr key + allnet
rr_key = "allnet|https://location.am-all.net/alm/shop?sid=18365"
venues[rr_key] = {
    "name": "THE REC ROOM BRENTWOOD",
    "attested_by": "research-fleet",
    "attested_at": str(date.today()),
    "evidence_url": "https://www.therecroom.com/brentwood",
    "note": "Country was United States; real venue is Rec Room Brentwood Town Centre, Burnaby BC, Canada. Official chain site therecroom.com/brentwood.",
    "set_country": "Canada",
}
oa_path.write_text(json.dumps(oa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

data = json.loads(Path("data/arcades.json").read_text(encoding="utf-8"))
before = len(data["arcades"])
kept = []
removed = []
for a in data["arcades"]:
    allnet = (a.get("links") or {}).get("allnet")
    name = (a.get("name") or "").upper()
    if allnet in (
        "https://location.am-all.net/alm/shop?sid=18325",
        "https://location.am-all.net/alm/shop?sid=18326",
    ) or name in ("ONE MORE EXTRA STAGE", "SIZIGI 20TH STREET"):
        removed.append((a.get("id"), a.get("sid"), a.get("name")))
        continue
    if allnet == "https://location.am-all.net/alm/shop?sid=18365" or name == "THE REC ROOM BRENTWOOD":
        a["country"] = "Canada"
        print("country fix", a.get("name"), "-> Canada")
    kept.append(a)

data["arcades"] = kept
Path("data/arcades.json").write_text(
    json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

st_path = Path("data/stats.json")
if st_path.exists():
    st = json.loads(st_path.read_text(encoding="utf-8"))
    if isinstance(st.get("counts"), dict):
        st["counts"]["total"] = len(kept)
        bs = st["counts"].get("by_source") or {}
        if "allnet" in bs:
            bs["allnet"] = max(0, bs["allnet"] - len(removed))
        st_path.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

for _, sid, _ in removed:
    if sid:
        p = Path("s") / (sid + ".html")
        if p.exists():
            p.unlink()
            print("deleted share", p)

print("removed", removed)
print("arcades", before, "->", len(kept))
