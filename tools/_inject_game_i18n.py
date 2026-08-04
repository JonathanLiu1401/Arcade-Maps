# -*- coding: utf-8 -*-
"""Inject games.* labels into every locale in js/i18n.js."""
from __future__ import annotations

import json
import re
from pathlib import Path

I18N = Path(__file__).resolve().parents[1] / "js" / "i18n.js"

# Official / market display names. Latin brand marks stay when that is how
# the operator publishes the title in that market.
GAMES: dict[str, dict[str, str]] = {
    "en": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "Taiko no Tatsujin",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "Other",
        "maimai_finale": "maimai (FiNALE / pre-DX)",
    },
    "zh-Hans": {
        "maimai_dx": "舞萌 DX", "chunithm": "中二节奏", "ongeki": "音击",
        "project_diva": "初音未来 歌姬计划", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DanceDanceRevolution", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "太鼓达人",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "其他",
        "maimai_finale": "maimai（FiNALE / 旧框体）",
    },
    "zh-Hant": {
        "maimai_dx": "舞萌 DX", "chunithm": "中二節奏", "ongeki": "音擊",
        "project_diva": "初音未來 歌姬計劃", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DanceDanceRevolution", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "太鼓達人",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "其他",
        "maimai_finale": "maimai（FiNALE / 舊框體）",
    },
    "ja": {
        "maimai_dx": "maimai でらっくす", "chunithm": "CHUNITHM", "ongeki": "オンゲキ",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DanceDanceRevolution", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "ノスタルジア",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "太鼓の達人",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "グルーヴコースター", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "その他",
        "maimai_finale": "maimai（FiNALE / 旧筐体）",
    },
    "ko": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "온게키",
        "project_diva": "Project DIVA", "sdvx": "사운드 볼텍스", "iidx": "비트매니아 IIDX",
        "ddr": "댄스댄스레볼루션", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "팝픈뮤직", "nostalgia": "노스탤지아",
        "drs": "댄서러시", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "태고의 달인",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "그루브 코스터", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "기타",
        "maimai_finale": "maimai (FiNALE / 구기체)",
    },
    "id": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "Taiko no Tatsujin",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "Lainnya",
        "maimai_finale": "maimai (FiNALE / pra-DX)",
    },
    "ms": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "Taiko no Tatsujin",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "Lain-lain",
        "maimai_finale": "maimai (FiNALE / pra-DX)",
    },
    "th": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "ไทโกะ โนะ ทัตสึจิน",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "อื่นๆ",
        "maimai_finale": "maimai (FiNALE / ก่อน DX)",
    },
    "vi": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "Taiko no Tatsujin",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "Khác",
        "maimai_finale": "maimai (FiNALE / trước DX)",
    },
    "fil": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "Taiko no Tatsujin",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "Iba pa",
        "maimai_finale": "maimai (FiNALE / pre-DX)",
    },
    "es": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "Taiko no Tatsujin",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "Otros",
        "maimai_finale": "maimai (FiNALE / pre-DX)",
    },
    "fr": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "Taiko no Tatsujin",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "Autres",
        "maimai_finale": "maimai (FiNALE / pré-DX)",
    },
    "de": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "Taiko no Tatsujin",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "Sonstige",
        "maimai_finale": "maimai (FiNALE / vor-DX)",
    },
    "pt": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "Taiko no Tatsujin",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "Outros",
        "maimai_finale": "maimai (FiNALE / pré-DX)",
    },
    "it": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "Taiko no Tatsujin",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "Altri",
        "maimai_finale": "maimai (FiNALE / pre-DX)",
    },
    "ru": {
        "maimai_dx": "maimai DX", "chunithm": "CHUNITHM", "ongeki": "O.N.G.E.K.I.",
        "project_diva": "Project DIVA", "sdvx": "SOUND VOLTEX", "iidx": "beatmania IIDX",
        "ddr": "DDR", "polaris_chord": "Polaris Chord", "gitadora": "GITADORA",
        "jubeat": "jubeat", "popn": "pop'n music", "nostalgia": "NOSTALGIA",
        "drs": "DANCERUSH", "dance_around": "DANCE aROUND", "dance_evo": "Dance Evolution",
        "museca": "MUSECA", "reflec": "REFLEC BEAT", "taiko": "Taiko no Tatsujin",
        "pump_it_up": "Pump It Up", "stepmaniax": "StepManiaX", "wacca": "WACCA",
        "groove_coaster": "Groove Coaster", "crossbeats": "crossbeats",
        "beatstream": "BeatStream", "other": "Другие",
        "maimai_finale": "maimai (FiNALE / до DX)",
    },
}

LANG_ORDER = [
    "en", "zh-Hans", "zh-Hant", "ja", "ko", "id", "ms", "th",
    "vi", "fil", "es", "fr", "de", "pt", "it", "ru",
]


def games_block(lang: str) -> str:
    d = GAMES[lang]
    lines = ["      games: {"]
    for k, v in d.items():
        lines.append(f"        {k}: {json.dumps(v, ensure_ascii=False)},")
    lines.append("      },")
    return "\n".join(lines)


def main() -> None:
    text = I18N.read_text(encoding="utf-8")
    # Drop any previous games blocks we may have injected
    text = re.sub(
        r"\n[ \t]*games:\s*\{(?:[^{}]|\{[^{}]*\})*\},",
        "",
        text,
    )
    out = []
    pos = 0
    li = 0
    for m in re.finditer(r"\n {6}cabs:\s*\{", text):
        lang = LANG_ORDER[li] if li < len(LANG_ORDER) else "en"
        li += 1
        out.append(text[pos:m.start()])
        out.append("\n")
        out.append(games_block(lang))
        out.append(m.group(0))
        pos = m.end()
    out.append(text[pos:])
    if li != 16:
        raise SystemExit(f"expected 16 cabs blocks, found {li}")
    I18N.write_text("".join(out), encoding="utf-8")
    print(f"OK: injected games for {li} locales")


if __name__ == "__main__":
    main()
