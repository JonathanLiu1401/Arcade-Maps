# -*- coding: utf-8 -*-
"""Inject place-panel price/hours keys + short cab badge labels into all locales."""
from __future__ import annotations

import json
import re
from pathlib import Path

I18N = Path(__file__).resolve().parents[1] / "js" / "i18n.js"

# Short badge pills (panel/popup). Filter labels stay in cabs.* long form.
BADGES: dict[str, dict[str, str]] = {
    "en": {
        "badge_maimai_classic": "FiNALE / pre-DX",
        "badge_iidx_lm": "Lightning",
        "badge_sdvx_vm": "Valkyrie",
        "badge_sdvx_nemsys": "NEMSYS",
        "badge_ddr_gold": "Gold cab",
        "badge_ddr_universal": "Universal",
        "badge_ddr_legacy": "Legacy CRT",
        "badge_popn_pikapika": "Pikapika",
        "badge_gitadora_gf_arena": "GF Arena",
        "badge_gitadora_dm_arena": "DM Arena",
        "badge_taiko_asia": "Asia build",
        "badge_taiko_jp": "JP build",
        "badge_taiko_us": "USA build",
        "taiko_asia": "Nijiiro - Asia build",
        "taiko_jp": "Nijiiro - Japan build",
        "taiko_us": "Nijiiro - USA build",
        "gitadora_gf_arena": "GuitarFreaks Arena",
        "gitadora_dm_arena": "DrumMania Arena",
    },
    "zh-Hans": {
        "badge_maimai_classic": "FiNALE / 旧框",
        "badge_iidx_lm": "Lightning",
        "badge_sdvx_vm": "Valkyrie",
        "badge_sdvx_nemsys": "NEMSYS",
        "badge_ddr_gold": "金色机台",
        "badge_ddr_universal": "Universal",
        "badge_ddr_legacy": "旧 CRT",
        "badge_popn_pikapika": "ピカピカ",
        "badge_gitadora_gf_arena": "GF Arena",
        "badge_gitadora_dm_arena": "DM Arena",
        "badge_taiko_asia": "亚版",
        "badge_taiko_jp": "日版",
        "badge_taiko_us": "美版",
        "taiko_asia": "Nijiiro · 亚洲版",
        "taiko_jp": "Nijiiro · 日本版",
        "taiko_us": "Nijiiro · 美国版",
        "gitadora_gf_arena": "GuitarFreaks Arena",
        "gitadora_dm_arena": "DrumMania Arena",
    },
    "zh-Hant": {
        "badge_maimai_classic": "FiNALE / 舊框",
        "badge_iidx_lm": "Lightning",
        "badge_sdvx_vm": "Valkyrie",
        "badge_sdvx_nemsys": "NEMSYS",
        "badge_ddr_gold": "金色機台",
        "badge_ddr_universal": "Universal",
        "badge_ddr_legacy": "舊 CRT",
        "badge_popn_pikapika": "ピカピカ",
        "badge_gitadora_gf_arena": "GF Arena",
        "badge_gitadora_dm_arena": "DM Arena",
        "badge_taiko_asia": "亞版",
        "badge_taiko_jp": "日版",
        "badge_taiko_us": "美版",
        "taiko_asia": "Nijiiro · 亞洲版",
        "taiko_jp": "Nijiiro · 日本版",
        "taiko_us": "Nijiiro · 美國版",
        "gitadora_gf_arena": "GuitarFreaks Arena",
        "gitadora_dm_arena": "DrumMania Arena",
    },
    "ja": {
        "badge_maimai_classic": "FiNALE / 旧筐体",
        "badge_iidx_lm": "Lightning",
        "badge_sdvx_vm": "Valkyrie",
        "badge_sdvx_nemsys": "NEMSYS",
        "badge_ddr_gold": "ゴールド筐体",
        "badge_ddr_universal": "Universal",
        "badge_ddr_legacy": "旧型CRT",
        "badge_popn_pikapika": "ピカピカ",
        "badge_gitadora_gf_arena": "GF アリーナ",
        "badge_gitadora_dm_arena": "DM アリーナ",
        "badge_taiko_asia": "アジア版",
        "badge_taiko_jp": "日本版",
        "badge_taiko_us": "USA版",
        "taiko_asia": "ニジイロ · アジア版",
        "taiko_jp": "ニジイロ · 日本版",
        "taiko_us": "ニジイロ · USA版",
        "gitadora_gf_arena": "GuitarFreaks アリーナ",
        "gitadora_dm_arena": "DrumMania アリーナ",
    },
    "ko": {
        "badge_maimai_classic": "FiNALE / 구기체",
        "badge_iidx_lm": "Lightning",
        "badge_sdvx_vm": "Valkyrie",
        "badge_sdvx_nemsys": "NEMSYS",
        "badge_ddr_gold": "골드 기체",
        "badge_ddr_universal": "Universal",
        "badge_ddr_legacy": "구형 CRT",
        "badge_popn_pikapika": "피카피카",
        "badge_gitadora_gf_arena": "GF Arena",
        "badge_gitadora_dm_arena": "DM Arena",
        "badge_taiko_asia": "아시아판",
        "badge_taiko_jp": "일본판",
        "badge_taiko_us": "미국판",
        "taiko_asia": "니지이로 · 아시아",
        "taiko_jp": "니지이로 · 일본",
        "taiko_us": "니지이로 · 미국",
        "gitadora_gf_arena": "GuitarFreaks Arena",
        "gitadora_dm_arena": "DrumMania Arena",
    },
}

# Non-CJK locales: mostly English badges, localized only where natural
for lang in ("id", "ms", "th", "vi", "fil", "es", "fr", "de", "pt", "it", "ru"):
    BADGES[lang] = dict(BADGES["en"])
    if lang == "es":
        BADGES[lang]["badge_ddr_gold"] = "Cabina oro"
        BADGES[lang]["badge_taiko_asia"] = "Asia"
        BADGES[lang]["badge_taiko_jp"] = "JP"
        BADGES[lang]["badge_taiko_us"] = "EE.UU."
    elif lang == "fr":
        BADGES[lang]["badge_ddr_gold"] = "Cabine or"
        BADGES[lang]["badge_taiko_jp"] = "JP"
    elif lang == "de":
        BADGES[lang]["badge_ddr_gold"] = "Gold-Cab"
    elif lang == "pt":
        BADGES[lang]["badge_ddr_gold"] = "Cabine ouro"
    elif lang == "ru":
        BADGES[lang]["badge_ddr_gold"] = "Золотой каб"
        BADGES[lang]["badge_taiko_jp"] = "JP"
    elif lang == "th":
        BADGES[lang]["badge_taiko_jp"] = "JP"
        BADGES[lang]["badge_taiko_asia"] = "เอเชีย"
        BADGES[lang]["badge_taiko_us"] = "สหรัฐ"
    elif lang in ("id", "ms"):
        BADGES[lang]["badge_taiko_jp"] = "JP"
    elif lang == "vi":
        BADGES[lang]["badge_ddr_gold"] = "Cab vàng"
    elif lang == "fil":
        BADGES[lang]["badge_ddr_gold"] = "Gold cab"

PLACE_EXTRA: dict[str, dict[str, str]] = {
    "en": {
        "price_for_songs": "for {n} songs",
        "price_n_songs": "{n} songs",
        "price_to_continue": "to continue",
        "price_free_play": "free play",
        "price_per_credit": "per credit",
        "price_n_credits": "{n} credits",
        "price_n_credits_play": "{n} credits/play",
        "price_standard_play": "Standard Play",
        "price_premium_credit": "Premium Credit",
        "price_normal_credit": "Normal Credit",
        "price_tokens": "Tokens",
        "price_token": "Token",
        "price_stage_break_off": "Stage break off",
        "price_stage_break_on": "Stage break on",
        "price_offline": "Offline",
        "hours_mon": "Mon", "hours_tue": "Tue", "hours_wed": "Wed",
        "hours_thu": "Thu", "hours_fri": "Fri", "hours_sat": "Sat", "hours_sun": "Sun",
        "cabinet_suffix": "cabinet",
    },
    "zh-Hans": {
        "price_for_songs": "{n} 曲",
        "price_n_songs": "{n} 曲",
        "price_to_continue": "续关",
        "price_free_play": "免费畅玩",
        "price_per_credit": "/ 次币",
        "price_n_credits": "{n} 次币",
        "price_n_credits_play": "{n} 次币/局",
        "price_standard_play": "标准模式",
        "price_premium_credit": "高级币",
        "price_normal_credit": "普通币",
        "price_tokens": "代币",
        "price_token": "代币",
        "price_stage_break_off": "关闭 stage break",
        "price_stage_break_on": "开启 stage break",
        "price_offline": "离线",
        "hours_mon": "周一", "hours_tue": "周二", "hours_wed": "周三",
        "hours_thu": "周四", "hours_fri": "周五", "hours_sat": "周六", "hours_sun": "周日",
        "cabinet_suffix": "机台",
    },
    "zh-Hant": {
        "price_for_songs": "{n} 曲",
        "price_n_songs": "{n} 曲",
        "price_to_continue": "續關",
        "price_free_play": "免費暢玩",
        "price_per_credit": "/ 次幣",
        "price_n_credits": "{n} 次幣",
        "price_n_credits_play": "{n} 次幣/局",
        "price_standard_play": "標準模式",
        "price_premium_credit": "高級幣",
        "price_normal_credit": "普通幣",
        "price_tokens": "代幣",
        "price_token": "代幣",
        "price_stage_break_off": "關閉 stage break",
        "price_stage_break_on": "開啟 stage break",
        "price_offline": "離線",
        "hours_mon": "週一", "hours_tue": "週二", "hours_wed": "週三",
        "hours_thu": "週四", "hours_fri": "週五", "hours_sat": "週六", "hours_sun": "週日",
        "cabinet_suffix": "機台",
    },
    "ja": {
        "price_for_songs": "{n}曲",
        "price_n_songs": "{n}曲",
        "price_to_continue": "コンティニュー",
        "price_free_play": "フリープレイ",
        "price_per_credit": "/ クレジット",
        "price_n_credits": "{n}クレジット",
        "price_n_credits_play": "{n}クレジット/プレイ",
        "price_standard_play": "スタンダード",
        "price_premium_credit": "プレミアムクレジット",
        "price_normal_credit": "ノーマルクレジット",
        "price_tokens": "トークン",
        "price_token": "トークン",
        "price_stage_break_off": "ステージブレイクOFF",
        "price_stage_break_on": "ステージブレイクON",
        "price_offline": "オフライン",
        "hours_mon": "月", "hours_tue": "火", "hours_wed": "水",
        "hours_thu": "木", "hours_fri": "金", "hours_sat": "土", "hours_sun": "日",
        "cabinet_suffix": "筐体",
    },
    "ko": {
        "price_for_songs": "{n}곡",
        "price_n_songs": "{n}곡",
        "price_to_continue": "이어하기",
        "price_free_play": "프리 플레이",
        "price_per_credit": "/ 크레딧",
        "price_n_credits": "{n} 크레딧",
        "price_n_credits_play": "{n} 크레딧/플레이",
        "price_standard_play": "스탠다드",
        "price_premium_credit": "프리미엄 크레딧",
        "price_normal_credit": "노멀 크레딧",
        "price_tokens": "토큰",
        "price_token": "토큰",
        "price_stage_break_off": "스테이지 브레이크 끔",
        "price_stage_break_on": "스테이지 브레이크 켬",
        "price_offline": "오프라인",
        "hours_mon": "월", "hours_tue": "화", "hours_wed": "수",
        "hours_thu": "목", "hours_fri": "금", "hours_sat": "토", "hours_sun": "일",
        "cabinet_suffix": "기체",
    },
    "id": {
        "price_for_songs": "untuk {n} lagu",
        "price_n_songs": "{n} lagu",
        "price_to_continue": "untuk lanjut",
        "price_free_play": "free play",
        "price_per_credit": "per kredit",
        "price_n_credits": "{n} kredit",
        "price_n_credits_play": "{n} kredit/main",
        "price_standard_play": "Standard Play",
        "price_premium_credit": "Kredit Premium",
        "price_normal_credit": "Kredit Normal",
        "price_tokens": "Token",
        "price_token": "Token",
        "price_stage_break_off": "Stage break mati",
        "price_stage_break_on": "Stage break nyala",
        "price_offline": "Offline",
        "hours_mon": "Sen", "hours_tue": "Sel", "hours_wed": "Rab",
        "hours_thu": "Kam", "hours_fri": "Jum", "hours_sat": "Sab", "hours_sun": "Min",
        "cabinet_suffix": "kabinet",
    },
    "ms": {
        "price_for_songs": "untuk {n} lagu",
        "price_n_songs": "{n} lagu",
        "price_to_continue": "untuk terus",
        "price_free_play": "free play",
        "price_per_credit": "setiap kredit",
        "price_n_credits": "{n} kredit",
        "price_n_credits_play": "{n} kredit/main",
        "price_standard_play": "Standard Play",
        "price_premium_credit": "Kredit Premium",
        "price_normal_credit": "Kredit Biasa",
        "price_tokens": "Token",
        "price_token": "Token",
        "price_stage_break_off": "Stage break off",
        "price_stage_break_on": "Stage break on",
        "price_offline": "Luar talian",
        "hours_mon": "Isn", "hours_tue": "Sel", "hours_wed": "Rab",
        "hours_thu": "Kha", "hours_fri": "Jum", "hours_sat": "Sab", "hours_sun": "Ahd",
        "cabinet_suffix": "kabinet",
    },
    "th": {
        "price_for_songs": "สำหรับ {n} เพลง",
        "price_n_songs": "{n} เพลง",
        "price_to_continue": "เล่นต่อ",
        "price_free_play": "เล่นฟรี",
        "price_per_credit": "ต่อเครดิต",
        "price_n_credits": "{n} เครดิต",
        "price_n_credits_play": "{n} เครดิต/เกม",
        "price_standard_play": "Standard Play",
        "price_premium_credit": "Premium Credit",
        "price_normal_credit": "Normal Credit",
        "price_tokens": "โทเคน",
        "price_token": "โทเคน",
        "price_stage_break_off": "Stage break ปิด",
        "price_stage_break_on": "Stage break เปิด",
        "price_offline": "ออฟไลน์",
        "hours_mon": "จ.", "hours_tue": "อ.", "hours_wed": "พ.",
        "hours_thu": "พฤ.", "hours_fri": "ศ.", "hours_sat": "ส.", "hours_sun": "อา.",
        "cabinet_suffix": "ตู้",
    },
    "vi": {
        "price_for_songs": "cho {n} bài",
        "price_n_songs": "{n} bài",
        "price_to_continue": "để tiếp",
        "price_free_play": "chơi free",
        "price_per_credit": "mỗi credit",
        "price_n_credits": "{n} credit",
        "price_n_credits_play": "{n} credit/ván",
        "price_standard_play": "Standard Play",
        "price_premium_credit": "Premium Credit",
        "price_normal_credit": "Normal Credit",
        "price_tokens": "Token",
        "price_token": "Token",
        "price_stage_break_off": "Stage break tắt",
        "price_stage_break_on": "Stage break bật",
        "price_offline": "Offline",
        "hours_mon": "T2", "hours_tue": "T3", "hours_wed": "T4",
        "hours_thu": "T5", "hours_fri": "T6", "hours_sat": "T7", "hours_sun": "CN",
        "cabinet_suffix": "máy",
    },
    "fil": {
        "price_for_songs": "para sa {n} kanta",
        "price_n_songs": "{n} kanta",
        "price_to_continue": "para magpatuloy",
        "price_free_play": "free play",
        "price_per_credit": "bawat credit",
        "price_n_credits": "{n} credits",
        "price_n_credits_play": "{n} credits/play",
        "price_standard_play": "Standard Play",
        "price_premium_credit": "Premium Credit",
        "price_normal_credit": "Normal Credit",
        "price_tokens": "Tokens",
        "price_token": "Token",
        "price_stage_break_off": "Stage break off",
        "price_stage_break_on": "Stage break on",
        "price_offline": "Offline",
        "hours_mon": "Lun", "hours_tue": "Mar", "hours_wed": "Miy",
        "hours_thu": "Huw", "hours_fri": "Biy", "hours_sat": "Sab", "hours_sun": "Lin",
        "cabinet_suffix": "cabinet",
    },
    "es": {
        "price_for_songs": "por {n} canciones",
        "price_n_songs": "{n} canciones",
        "price_to_continue": "para continuar",
        "price_free_play": "juego libre",
        "price_per_credit": "por crédito",
        "price_n_credits": "{n} créditos",
        "price_n_credits_play": "{n} créditos/partida",
        "price_standard_play": "Juego estándar",
        "price_premium_credit": "Crédito premium",
        "price_normal_credit": "Crédito normal",
        "price_tokens": "Fichas",
        "price_token": "Ficha",
        "price_stage_break_off": "Stage break off",
        "price_stage_break_on": "Stage break on",
        "price_offline": "Sin conexión",
        "hours_mon": "lun", "hours_tue": "mar", "hours_wed": "mié",
        "hours_thu": "jue", "hours_fri": "vie", "hours_sat": "sáb", "hours_sun": "dom",
        "cabinet_suffix": "cabina",
    },
    "fr": {
        "price_for_songs": "pour {n} titres",
        "price_n_songs": "{n} titres",
        "price_to_continue": "pour continuer",
        "price_free_play": "free play",
        "price_per_credit": "par crédit",
        "price_n_credits": "{n} crédits",
        "price_n_credits_play": "{n} crédits/partie",
        "price_standard_play": "Jeu standard",
        "price_premium_credit": "Crédit premium",
        "price_normal_credit": "Crédit normal",
        "price_tokens": "Jetons",
        "price_token": "Jeton",
        "price_stage_break_off": "Stage break off",
        "price_stage_break_on": "Stage break on",
        "price_offline": "Hors ligne",
        "hours_mon": "lun", "hours_tue": "mar", "hours_wed": "mer",
        "hours_thu": "jeu", "hours_fri": "ven", "hours_sat": "sam", "hours_sun": "dim",
        "cabinet_suffix": "borne",
    },
    "de": {
        "price_for_songs": "für {n} Songs",
        "price_n_songs": "{n} Songs",
        "price_to_continue": "zum Weiterspielen",
        "price_free_play": "Free Play",
        "price_per_credit": "pro Credit",
        "price_n_credits": "{n} Credits",
        "price_n_credits_play": "{n} Credits/Spiel",
        "price_standard_play": "Standard Play",
        "price_premium_credit": "Premium-Credit",
        "price_normal_credit": "Normal-Credit",
        "price_tokens": "Tokens",
        "price_token": "Token",
        "price_stage_break_off": "Stage break aus",
        "price_stage_break_on": "Stage break an",
        "price_offline": "Offline",
        "hours_mon": "Mo", "hours_tue": "Di", "hours_wed": "Mi",
        "hours_thu": "Do", "hours_fri": "Fr", "hours_sat": "Sa", "hours_sun": "So",
        "cabinet_suffix": "Cabinet",
    },
    "pt": {
        "price_for_songs": "por {n} músicas",
        "price_n_songs": "{n} músicas",
        "price_to_continue": "para continuar",
        "price_free_play": "free play",
        "price_per_credit": "por crédito",
        "price_n_credits": "{n} créditos",
        "price_n_credits_play": "{n} créditos/partida",
        "price_standard_play": "Standard Play",
        "price_premium_credit": "Crédito premium",
        "price_normal_credit": "Crédito normal",
        "price_tokens": "Fichas",
        "price_token": "Ficha",
        "price_stage_break_off": "Stage break off",
        "price_stage_break_on": "Stage break on",
        "price_offline": "Offline",
        "hours_mon": "seg", "hours_tue": "ter", "hours_wed": "qua",
        "hours_thu": "qui", "hours_fri": "sex", "hours_sat": "sáb", "hours_sun": "dom",
        "cabinet_suffix": "cabinet",
    },
    "it": {
        "price_for_songs": "per {n} brani",
        "price_n_songs": "{n} brani",
        "price_to_continue": "per continuare",
        "price_free_play": "free play",
        "price_per_credit": "per credito",
        "price_n_credits": "{n} crediti",
        "price_n_credits_play": "{n} crediti/partita",
        "price_standard_play": "Standard Play",
        "price_premium_credit": "Credito premium",
        "price_normal_credit": "Credito normal",
        "price_tokens": "Token",
        "price_token": "Token",
        "price_stage_break_off": "Stage break off",
        "price_stage_break_on": "Stage break on",
        "price_offline": "Offline",
        "hours_mon": "lun", "hours_tue": "mar", "hours_wed": "mer",
        "hours_thu": "gio", "hours_fri": "ven", "hours_sat": "sab", "hours_sun": "dom",
        "cabinet_suffix": "cabinet",
    },
    "ru": {
        "price_for_songs": "за {n} треков",
        "price_n_songs": "{n} треков",
        "price_to_continue": "чтобы продолжить",
        "price_free_play": "free play",
        "price_per_credit": "за кредит",
        "price_n_credits": "{n} кредитов",
        "price_n_credits_play": "{n} кредитов/игра",
        "price_standard_play": "Standard Play",
        "price_premium_credit": "Premium Credit",
        "price_normal_credit": "Normal Credit",
        "price_tokens": "токены",
        "price_token": "токен",
        "price_stage_break_off": "Stage break выкл.",
        "price_stage_break_on": "Stage break вкл.",
        "price_offline": "Офлайн",
        "hours_mon": "пн", "hours_tue": "вт", "hours_wed": "ср",
        "hours_thu": "чт", "hours_fri": "пт", "hours_sat": "сб", "hours_sun": "вс",
        "cabinet_suffix": "кабинет",
    },
}

LANG_ORDER = [
    "en", "zh-Hans", "zh-Hant", "ja", "ko", "id", "ms", "th",
    "vi", "fil", "es", "fr", "de", "pt", "it", "ru",
]


def inject_into_block(text: str, marker_re: str, entries: dict[str, str], lang_idx_limit: int = 16) -> str:
    """Insert key: value pairs before closing of each matching block.

    marker_re should match the start of a section we append into, e.g.
    place blocks ending with search_gmaps line.
    """
    # Strategy: for each locale's place: { ... }, insert before the closing
    # of place that contains search_gmaps. Simpler: after each search_gmaps line.
    out = []
    pos = 0
    li = 0
    for m in re.finditer(r'(search_gmaps:\s*"[^"]*",)\n', text):
        lang = LANG_ORDER[li] if li < len(LANG_ORDER) else "en"
        li += 1
        extra = entries.get(lang) or entries["en"]
        out.append(text[pos:m.end()])
        for k, v in extra.items():
            out.append(f"        {k}: {json.dumps(v, ensure_ascii=False)},\n")
        pos = m.end()
    out.append(text[pos:])
    if li != 16:
        raise SystemExit(f"place inject: expected 16 search_gmaps, got {li}")
    return "".join(out)


def inject_cabs_badges(text: str) -> str:
    """Append badge_* keys before each cabs block's closing other_game line region.

    Insert after other_game line in each cabs block.
    """
    out = []
    pos = 0
    li = 0
    for m in re.finditer(r'(other_game:\s*"[^"]*",)\n', text):
        lang = LANG_ORDER[li] if li < len(LANG_ORDER) else "en"
        # Only cabs.other_game - place might not have this. Count carefully.
        # other_game appears only in cabs blocks once per locale.
        li += 1
        extra = BADGES.get(lang) or BADGES["en"]
        out.append(text[pos:m.end()])
        for k, v in extra.items():
            # skip if already present later in same cab block - we just inject
            out.append(f"        {k}: {json.dumps(v, ensure_ascii=False)},\n")
        pos = m.end()
    out.append(text[pos:])
    if li != 16:
        raise SystemExit(f"cabs inject: expected 16 other_game, got {li}")
    return "".join(out)


def main() -> None:
    text = I18N.read_text(encoding="utf-8")
    # strip previous inject markers if re-run (badge_*, place price/hours only)
    strip_keys = (
        "price_for_songs", "price_n_songs", "price_to_continue", "price_free_play",
        "price_per_credit", "price_n_credits", "price_n_credits_play",
        "price_standard_play", "price_premium_credit", "price_normal_credit",
        "price_tokens", "price_token", "price_stage_break_off", "price_stage_break_on",
        "price_offline", "hours_mon", "hours_tue", "hours_wed", "hours_thu",
        "hours_fri", "hours_sat", "hours_sun", "cabinet_suffix",
        "badge_maimai_classic", "badge_iidx_lm", "badge_sdvx_vm", "badge_sdvx_nemsys",
        "badge_ddr_gold", "badge_ddr_universal", "badge_ddr_legacy", "badge_popn_pikapika",
        "badge_gitadora_gf_arena", "badge_gitadora_dm_arena",
        "badge_taiko_asia", "badge_taiko_jp", "badge_taiko_us",
        "taiko_asia", "taiko_jp", "taiko_us", "gitadora_gf_arena", "gitadora_dm_arena",
    )
    for key in strip_keys:
        text = re.sub(rf"\n[ \t]*{re.escape(key)}:\s*\"(?:\\.|[^\"])*\"\s*,", "", text)

    text = inject_into_block(text, "", PLACE_EXTRA)
    text = inject_cabs_badges(text)
    I18N.write_text(text, encoding="utf-8")
    print("OK: place price/hours + cab badges injected for 16 locales")


if __name__ == "__main__":
    main()
