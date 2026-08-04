import json
from pathlib import Path
from datetime import date

oa_path = Path("data/owner_attested.json")
oa = json.loads(oa_path.read_text(encoding="utf-8"))
key = "allnet|https://location.am-all.net/alm/shop?sid=18325"
oa["venues"][key] = {
    "name": "ONE MORE EXTRA STAGE",
    "closed": True,
    "closed_reason": "Google Maps lists the venue as Temporarily closed (Mountain View). ALL.Net-only maimai intl pin with no ZIv/community corroboration.",
    "attested_by": "research-fleet",
    "attested_at": str(date.today()),
    "evidence_url": "https://www.google.com/maps/search/?api=1&query=One+More+Extra+Stage+1313+W+El+Camino+Real+Mountain+View",
    "note": "User report 2026-08-04: Google Maps shows Temporarily closed at 1313 W El Camino Real A, Mountain View CA 94040. ALL.Net sid=18325 still lists maimai DX International (network-auth list, not public hours proof). Keep pin as closed so searchers are warned.",
}
oa_path.write_text(json.dumps(oa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("owner_attested", key)

data = json.loads(Path("data/arcades.json").read_text(encoding="utf-8"))
n = 0
for a in data["arcades"]:
    name = (a.get("name") or "").upper()
    allnet = (a.get("links") or {}).get("allnet")
    if name == "ONE MORE EXTRA STAGE" or allnet == "https://location.am-all.net/alm/shop?sid=18325":
        a["closed"] = True
        a["closed_reason"] = "Google Maps: Temporarily closed (Mountain View). ALL.Net-only, no independent open confirmation."
        a["closed_source"] = "https://www.google.com/maps/search/?api=1&query=One+More+Extra+Stage+1313+W+El+Camino+Real+Mountain+View"
        n += 1
        print("patched", a.get("id"), a.get("sid"))
Path("data/arcades.json").write_text(
    json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print("patched", n)
