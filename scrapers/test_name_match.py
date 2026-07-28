"""Unit tests for scrapers/name_match.py (fabricated + real-world names).

Run: python scrapers/test_name_match.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge
import name_match as nm

# Chinese/Japanese labels in test output die on the cp1252 Windows console.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):   # pragma: no cover
    pass

FAILED = []
RAN = []


def check(label, cond, detail=""):
    print("%s  %s%s" % ("PASS" if cond else "FAIL", label,
                        ("  <- " + detail) if detail else ""))
    RAN.append(label)
    if not cond:
        FAILED.append(label)


# ------------------------------------------------------------- romanization -
print("--- kana -> romaji ---")
for kana, want in [
        ("アミパラ", "amipara"),
        ("ラウンドワン", "raundowan"),
        ("ここじゃ", "kokoja"),                 # hiragana
        ("がいな", "gaina"),
        ("タイトーステーション", "taitoosuteeshon"),   # ー doubles the vowel
        ("ゲーセン", "geesen"),
        ("キャッツアイ", "kyattsuai"),           # digraph + sokuon
        ("ジャンボ", "janbo"),
        ("ファミリー", "famirii"),
        ("モーリーファンタジー", "mooriifantajii"),
        ("ソユー", "soyuu"),
        ("シルクハット", "shirukuhatto"),        # シ is Hepburn "shi"
        ("フジグラン", "fujiguran")]:
    got = nm.romanize(kana)
    check("romanize %s -> %s" % (kana, want), got == want, "got %r" % got)

# kanji / latin / digits pass through, kana around them still converts
check("mixed script passes non-kana through",
      nm.romanize("アミパラ下関店") == "amipara下関店",
      nm.romanize("アミパラ下関店"))
check("latin untouched", nm.romanize("GiGO 1") == "GiGO 1")

print("\n--- long vowels (both directions) ---")
for a, b in [("toukyou", "tokyo"), ("tookyoo", "tokyo"), ("geesen", "gesen"),
             ("taitoosuteeshon", "taitosuteshon"), ("moori", "mori")]:
    check("fold_long %s == %s" % (a, b), nm.fold_long(a) == b,
          "got %r" % nm.fold_long(a))
check("オオ and オウ meet at one form",
      nm.fold_long(nm.romanize("オオサカ")) == nm.fold_long(nm.romanize("オウサカ")),
      "%r vs %r" % (nm.fold_long(nm.romanize("オオサカ")),
                    nm.fold_long(nm.romanize("オウサカ"))))

print("\n--- romanizer robustness (must not raise) ---")
for s in ["ッ", "ー", "っ", "ーー", "アッ", "ッア", "", "  ", "1-2-3",
          "ヶ", "ｱﾐﾊﾟﾗ", "!!", "アーッ"]:
    try:
        nm.romanize(s)
        ok = True
    except Exception as exc:                      # noqa: BLE001
        ok, s = False, "%s (%s)" % (s, exc)
    check("romanize(%r) survives" % s, ok)
check("trailing sokuon does not crash", nm.romanize("アミッ") == "amitsu",
      nm.romanize("アミッ"))
check("leading chouon does not crash", nm.romanize("ーアミ") == "ami",
      nm.romanize("ーアミ"))
check("halfwidth kana normalizes via NFKC in norm_text",
      nm.romanize(nm.norm_text("ｱﾐﾊﾟﾗ")) == "amipara",
      nm.romanize(nm.norm_text("ｱﾐﾊﾟﾗ")))

# ------------------------------------------------------------ drift guard --
print("\n--- norm_text agrees with merge._norm_text (drift guard) ---")
for s in ["AmiPara Kokoja (アミパラ ここじゃ店)", "ＧｉＧＯ赤羽", "  Round1  ",
          "12345 星际传奇", "Taito F-Station!!", "짱구게임장(ZZANG GU)", ""]:
    check("norm_text %r" % s[:24], nm.norm_text(s) == merge._norm_text(s),
          "%r vs %r" % (nm.norm_text(s), merge._norm_text(s)))
    check("norm_name %r" % s[:24], nm.norm_name(s) == merge.norm_name(s),
          "%r vs %r" % (nm.norm_name(s), merge.norm_name(s)))

# ------------------------------------------------------------- similarity --
print("\n--- matcher POSITIVES (same venue, romanized vs kana) ---")
POS = [
    # the reported bug: ziv romaji vs official kana, 0.9 m apart
    ("AmiPara Kokoja (アミパラ ここじゃ店)", "アミパラここじゃ店"),
    ("GiGO Akabane (GiGO 赤羽)", "ＧｉＧＯ赤羽"),
    ("Taito Station Osaka Nipponbashi (タイトーステーション 大阪日本橋店)",
     "タイトーステーション大阪日本橋店"),
    ("PALO Kitakata (PALO喜多方店)", "ＰＡＬＯ喜多方"),
    ("ROUND1 Stadium Morioka (ラウンドワンスタジアム盛岡店)", "ラウンドワン盛岡店"),
    ("Cat's Eye Sakaedori (キャッツアイ 栄通店)", "キャッツアイ栄通店"),
    ("Molly Fantasy Yodobashi Sendai", "モーリーファンタジーヨドバシ仙台"),
]
for a, b in POS:
    s = nm.similarity(a, b)
    check("sim>=0.5  %s || %s" % (a[:30], b[:18]), s >= nm.SIM_THRESHOLD,
          "sim=%.3f" % s)
check("romanization actually helps (Kokoja beats the old matcher)",
      nm.similarity(*POS[0]) > merge.name_similarity(*POS[0]),
      "new %.3f vs old %.3f" % (nm.similarity(*POS[0]),
                                merge.name_similarity(*POS[0])))
check("similarity is symmetric",
      all(abs(nm.similarity(a, b) - nm.similarity(b, a)) < 1e-9
          for a, b in POS))
check("similarity never below merge.name_similarity",
      all(nm.similarity(a, b) >= merge.name_similarity(a, b) - 1e-9
          for a, b in POS))

print("\n--- matcher NEGATIVES (different neighbours, must stay apart) ---")
NEG = [
    ("GiGO Akabane (GiGO 赤羽)", "タイトーステーション赤羽"),      # rival chains
    ("Taito Station Ikebukuro", "GiGO 池袋"),
    ("ROUND1 Stadium Sapporo", "ラウンドワン池袋店"),               # diff city
    ("namco AEON MALL Natori", "モーリーファンタジー名取"),          # one mall
    ("BE-COME Narisawa (ビーカム成沢店)", "あそビレッジ山形店"),
    ("Kids Park AEON Chitose (キッズ・パーク イオン千歳店)",
     "タイトーＦステーションイオン千歳店"),
    ("Archie Brothers CCW", "Village Cinema Century City"),
    ("Ppokkippokki / P2 Zone", "BBOGGIBBOGGI GAMELAND"),
]
for a, b in NEG:
    s = nm.similarity(a, b)
    check("sim<0.5   %s || %s" % (a[:30], b[:18]), s < nm.SIM_THRESHOLD,
          "sim=%.3f" % s)

print("\n--- shared-mall-name false positives (regression) ---")
# Three unrelated arcades share the Bugis+ mall entrance in Singapore.
# Before the min-2-token guard each pair scored a perfect 1.0 off the
# single shared token "bugis" and fused into one pin.
MALL = [
    ("PACO FUNWORLD(BUGIS PLUS)", "TOG - Toy Or Game (Bugis+)"),
    ("VIRTUALAND BUGIS+", "Paco FunWorld Prize Station (Bugis+)"),
    ("VIRTUALAND BUGIS+", "TOG - Toy Or Game (Bugis+)"),
]
for a, b in MALL:
    s = nm.similarity(a, b)
    check("shared mall token alone is not a match: %s || %s"
          % (a[:24], b[:24]), s < 1.0, "sim=%.3f" % s)
check("a single shared token can never score 1.0",
      nm._pair_score("bugis plus", "bugis") < 1.0,
      "got %.3f" % nm._pair_score("bugis plus", "bugis"))
check("two shared tokens still score normally",
      nm._pair_score("round1 stadium morioka", "round1 morioka") >= 0.5)

print("\n--- substring rule ---")
check("truncated official name is a substring hit",
      nm.substring_match("アミパラ", "アミパラここじゃ店"))
check("substring floor rejects short fragments",
      not nm.substring_match("MG", "Amusement Park MG Fuji GRAND Anan"),
      "2-char fragment must not match")
check("substring floor rejects 4-char fragment",
      not nm.substring_match("gigo", "GiGO Akabane"))
check("unrelated names are not substrings",
      not nm.substring_match("Taito Station Ueno", "GiGO 秋葉原"))

# ------------------------------------------------------ proximity_decision -
print("\n--- proximity_decision ---")
KOKOJA = ("AmiPara Kokoja (アミパラ ここじゃ店)", "アミパラここじゃ店")
ok, rule, sim, conf = nm.proximity_decision(KOKOJA[0], KOKOJA[1], 0.9, 3)
check("flagship Kokoja merges on the similarity rule",
      ok and rule == "proximity_romaji_sim" and conf == "high",
      "%s %s sim=%.3f" % (ok, rule, sim))

ok, rule, _s, _c = nm.proximity_decision(KOKOJA[0], KOKOJA[1], 31.0, 2)
check("nothing merges beyond 30 m", not ok and rule is None)

# coincident-isolated: no textual evidence, decided purely on geometry
NOEV = ("BBOGGIBBOGGI GAMELAND", "Ppokkippokki / P2 Zone")
ok, rule, _s, conf = nm.proximity_decision(NOEV[0], NOEV[1], 0.9, 2)
check("isolated coincident pair merges (low confidence)",
      ok and rule == "coincident_isolated" and conf == "low",
      "%s %s" % (ok, rule))
ok, rule, _s, _c = nm.proximity_decision(NOEV[0], NOEV[1], 0.9, 3)
check("a third cluster within 60 m blocks the isolation rule",
      not ok, "rule=%s" % rule)
ok, rule, _s, _c = nm.proximity_decision(NOEV[0], NOEV[1], 15.0, 2)
check("isolation rule refuses 10-30 m (mall tenants share a geocode)",
      not ok, "rule=%s" % rule)
ok, rule, _s, _c = nm.proximity_decision(
    "Kids Park AEON Chitose (キッズ・パーク イオン千歳店)",
    "タイトーＦステーションイオン千歳店", 12.4, 2)
check("two different arcades in one AEON stay separate", not ok,
      "rule=%s" % rule)

# an evidence-bearing rule is NOT subject to the 10 m isolation gate
ok, rule, _s, _c = nm.proximity_decision(
    "ROUND1 Stadium Morioka (ラウンドワンスタジアム盛岡店)", "ラウンドワン盛岡店",
    25.0, 9)
check("name evidence still merges at 25 m in a crowded area",
      ok and rule == "proximity_romaji_sim", "%s %s" % (ok, rule))

check("every rule id has a documented confidence",
      set(nm.RULE_CONFIDENCE) == {"proximity_romaji_sim",
                                  "proximity_substring",
                                  "coincident_isolated"})

print("\n%d checks, %d failed" % (len(RAN), len(FAILED)))
if FAILED:
    print("FAILURES:")
    for f in FAILED:
        print("  - " + f)
    sys.exit(1)
print("ALL PASS")
