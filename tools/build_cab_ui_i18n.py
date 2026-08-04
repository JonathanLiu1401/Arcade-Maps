# -*- coding: utf-8 -*-
"""Inject cabs.* and ui.* keys into js/i18n.js (brace-safe) and leave panel wiring separate."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "js" / "i18n.js"

LANGS = [
    "en", "zh-Hans", "zh-Hant", "ja", "ko", "id", "ms", "th", "vi",
    "fil", "es", "fr", "de", "pt", "it", "ru",
]

# Official product codenames kept; only descriptive words localized.
CABS = {
    "en": {
        "sdvx_vm": "Valkyrie model",
        "iidx_lm": "Lightning model",
        "ddr_gold": "Gold cab (20th anniv.)",
        "gitadora_arena": "Arena model",
        "popn_pikapika": "Pikapika model",
        "maimai_classic": "maimai FiNALE / pre-DX",
        "sdvx_nemsys": "NEMSYS (standard)",
        "ddr_universal": "Universal Model (EU/NA)",
        "ddr_legacy": "Legacy CRT cabinet",
        "other_game": "Other",
    },
    "ja": {
        "sdvx_vm": "Valkyrie\u30e2\u30c7\u30eb",
        "iidx_lm": "Lightning\u30e2\u30c7\u30eb",
        "ddr_gold": "\u30b4\u30fc\u30eb\u30c9\u7b4b\u4f53\uff0820\u5468\u5e74\uff09",
        "gitadora_arena": "Arena\u30e2\u30c7\u30eb",
        "popn_pikapika": "\u30d4\u30ab\u30d4\u30ab\u30e2\u30c7\u30eb",
        "maimai_classic": "maimai FiNALE / \u65e7\u7b4b\u4f53",
        "sdvx_nemsys": "NEMSYS\uff08\u6a19\u6e96\uff09",
        "ddr_universal": "Universal Model\uff08\u6b27\u7c73\uff09",
        "ddr_legacy": "\u65e7\u578bCRT\u7b4b\u4f53",
        "other_game": "\u305d\u306e\u4ed6",
    },
    "zh-Hans": {
        "sdvx_vm": "Valkyrie \u673a\u578b",
        "iidx_lm": "Lightning \u673a\u578b",
        "ddr_gold": "\u91d1\u8272\u673a\u53f0\uff0820\u5468\u5e74\uff09",
        "gitadora_arena": "Arena \u673a\u578b",
        "popn_pikapika": "\u76ae\u5361\u76ae\u5361\u673a\u578b",
        "maimai_classic": "maimai FiNALE / \u65e7\u673a\u53f0",
        "sdvx_nemsys": "NEMSYS\uff08\u6807\u51c6\uff09",
        "ddr_universal": "Universal Model\uff08\u6b27\u7f8e\uff09",
        "ddr_legacy": "\u65e7\u5f0f CRT \u673a\u53f0",
        "other_game": "\u5176\u4ed6",
    },
    "zh-Hant": {
        "sdvx_vm": "Valkyrie \u6a5f\u578b",
        "iidx_lm": "Lightning \u6a5f\u578b",
        "ddr_gold": "\u91d1\u8272\u6a5f\u53f0\uff0820\u9031\u5e74\uff09",
        "gitadora_arena": "Arena \u6a5f\u578b",
        "popn_pikapika": "\u76ae\u5361\u76ae\u5361\u6a5f\u578b",
        "maimai_classic": "maimai FiNALE / \u820a\u6a5f\u53f0",
        "sdvx_nemsys": "NEMSYS\uff08\u6a19\u6e96\uff09",
        "ddr_universal": "Universal Model\uff08\u6b50\u7f8e\uff09",
        "ddr_legacy": "\u820a\u5f0f CRT \u6a5f\u53f0",
        "other_game": "\u5176\u4ed6",
    },
    "ko": {
        "sdvx_vm": "Valkyrie \ubaa8\ub378",
        "iidx_lm": "Lightning \ubaa8\ub378",
        "ddr_gold": "\uace8\ub4dc \uce90\ube44\ub137(20\uc8fc\ub144)",
        "gitadora_arena": "Arena \ubaa8\ub378",
        "popn_pikapika": "\ud53c\uce74\ud53c\uce74 \ubaa8\ub378",
        "maimai_classic": "maimai FiNALE / \uad6c\uae30\uccb4",
        "sdvx_nemsys": "NEMSYS(\ud45c\uc900)",
        "ddr_universal": "Universal Model(\uc720/\ubbf8)",
        "ddr_legacy": "\ub808\uac70\uc2dc CRT \uce90\ube44\ub137",
        "other_game": "\uae30\ud0c0",
    },
}

for code, d in {
    "id": {
        "sdvx_vm": "Model Valkyrie", "iidx_lm": "Model Lightning",
        "ddr_gold": "Kabinet emas (ultah ke-20)", "gitadora_arena": "Model Arena",
        "popn_pikapika": "Model Pikapika", "maimai_classic": "maimai FiNALE / pra-DX",
        "sdvx_nemsys": "NEMSYS (standar)", "ddr_universal": "Universal Model (EU/NA)",
        "ddr_legacy": "Kabinet CRT lama", "other_game": "Lainnya",
    },
    "ms": {
        "sdvx_vm": "Model Valkyrie", "iidx_lm": "Model Lightning",
        "ddr_gold": "Kabinet emas (ulang tahun ke-20)", "gitadora_arena": "Model Arena",
        "popn_pikapika": "Model Pikapika", "maimai_classic": "maimai FiNALE / pra-DX",
        "sdvx_nemsys": "NEMSYS (standard)", "ddr_universal": "Universal Model (EU/NA)",
        "ddr_legacy": "Kabinet CRT legasi", "other_game": "Lain-lain",
    },
    "es": {
        "sdvx_vm": "Modelo Valkyrie", "iidx_lm": "Modelo Lightning",
        "ddr_gold": "Cabina dorada (20.\u00ba aniv.)", "gitadora_arena": "Modelo Arena",
        "popn_pikapika": "Modelo Pikapika", "maimai_classic": "maimai FiNALE / pre-DX",
        "sdvx_nemsys": "NEMSYS (est\u00e1ndar)", "ddr_universal": "Universal Model (EU/NA)",
        "ddr_legacy": "Cabina CRT antigua", "other_game": "Otros",
    },
    "fr": {
        "sdvx_vm": "Mod\u00e8le Valkyrie", "iidx_lm": "Mod\u00e8le Lightning",
        "ddr_gold": "Borne dor\u00e9e (20e anniv.)", "gitadora_arena": "Mod\u00e8le Arena",
        "popn_pikapika": "Mod\u00e8le Pikapika", "maimai_classic": "maimai FiNALE / pre-DX",
        "sdvx_nemsys": "NEMSYS (standard)", "ddr_universal": "Universal Model (EU/NA)",
        "ddr_legacy": "Borne CRT ancienne", "other_game": "Autre",
    },
    "de": {
        "sdvx_vm": "Valkyrie-Modell", "iidx_lm": "Lightning-Modell",
        "ddr_gold": "Gold-Cab (20. Jubil\u00e4um)", "gitadora_arena": "Arena-Modell",
        "popn_pikapika": "Pikapika-Modell", "maimai_classic": "maimai FiNALE / pre-DX",
        "sdvx_nemsys": "NEMSYS (Standard)", "ddr_universal": "Universal Model (EU/NA)",
        "ddr_legacy": "Legacy-CRT-Geh\u00e4use", "other_game": "Sonstige",
    },
    "pt": {
        "sdvx_vm": "Modelo Valkyrie", "iidx_lm": "Modelo Lightning",
        "ddr_gold": "Cabine dourada (20\u00ba aniv.)", "gitadora_arena": "Modelo Arena",
        "popn_pikapika": "Modelo Pikapika", "maimai_classic": "maimai FiNALE / pre-DX",
        "sdvx_nemsys": "NEMSYS (padr\u00e3o)", "ddr_universal": "Universal Model (EU/NA)",
        "ddr_legacy": "Cabine CRT antiga", "other_game": "Outros",
    },
    "it": {
        "sdvx_vm": "Modello Valkyrie", "iidx_lm": "Modello Lightning",
        "ddr_gold": "Cabinato oro (20\u00ba anniv.)", "gitadora_arena": "Modello Arena",
        "popn_pikapika": "Modello Pikapika", "maimai_classic": "maimai FiNALE / pre-DX",
        "sdvx_nemsys": "NEMSYS (standard)", "ddr_universal": "Universal Model (EU/NA)",
        "ddr_legacy": "Cabinato CRT legacy", "other_game": "Altro",
    },
}.items():
    CABS[code] = d
CABS["th"] = {
    "sdvx_vm": "\u0e23\u0e38\u0e48\u0e19 Valkyrie",
    "iidx_lm": "\u0e23\u0e38\u0e48\u0e19 Lightning",
    "ddr_gold": "\u0e15\u0e39\u0e49\u0e17\u0e2d\u0e07\u0e04\u0e33 (20 \u0e1b\u0e35)",
    "gitadora_arena": "\u0e23\u0e38\u0e48\u0e19 Arena",
    "popn_pikapika": "\u0e23\u0e38\u0e48\u0e19 Pikapika",
    "maimai_classic": "maimai FiNALE / \u0e01\u0e48\u0e2d\u0e19 DX",
    "sdvx_nemsys": "NEMSYS (\u0e21\u0e32\u0e15\u0e23\u0e10\u0e32\u0e19)",
    "ddr_universal": "Universal Model (EU/NA)",
    "ddr_legacy": "\u0e15\u0e39\u0e49 CRT \u0e23\u0e38\u0e48\u0e19\u0e40\u0e01\u0e48\u0e32",
    "other_game": "\u0e2d\u0e37\u0e48\u0e19\u0e46",
}
CABS["vi"] = {
    "sdvx_vm": "Model Valkyrie", "iidx_lm": "Model Lightning",
    "ddr_gold": "Cabinet v\u00e0ng (20 n\u0103m)", "gitadora_arena": "Model Arena",
    "popn_pikapika": "Model Pikapika",
    "maimai_classic": "maimai FiNALE / tr\u01b0\u1edbc DX",
    "sdvx_nemsys": "NEMSYS (ti\u00eau chu\u1ea9n)",
    "ddr_universal": "Universal Model (EU/NA)",
    "ddr_legacy": "Cabinet CRT c\u0169", "other_game": "Kh\u00e1c",
}
CABS["fil"] = dict(CABS["en"], other_game="Iba pa")
CABS["ru"] = {
    "sdvx_vm": "Valkyrie-\u043c\u043e\u0434\u0435\u043b\u044c",
    "iidx_lm": "Lightning-\u043c\u043e\u0434\u0435\u043b\u044c",
    "ddr_gold": "\u0417\u043e\u043b\u043e\u0442\u043e\u0439 cab (20 \u043b\u0435\u0442)",
    "gitadora_arena": "Arena-\u043c\u043e\u0434\u0435\u043b\u044c",
    "popn_pikapika": "Pikapika-\u043c\u043e\u0434\u0435\u043b\u044c",
    "maimai_classic": "maimai FiNALE / pre-DX",
    "sdvx_nemsys": "NEMSYS (\u0441\u0442\u0430\u043d\u0434\u0430\u0440\u0442)",
    "ddr_universal": "Universal Model (EU/NA)",
    "ddr_legacy": "Legacy CRT-\u043a\u0430\u0431\u0438\u043d\u0435\u0442",
    "other_game": "\u041f\u0440\u043e\u0447\u0435\u0435",
}

# UI residual keys (panel/search/css)
UI = {
    "en": {
        "shown": "{n} shown",
        "stores_total": "{n} stores total",
        "per_credit": "per credit",
        "show_more": "Show more",
        "show_less": "Show less",
        "search_wide": "Search games, arcades, places...",
        "search_narrow": "Search...",
        "cab_model_unpublished": "Cabinet model not published",
        "cab_model_unpublished_cap": (
            "No listing says which cabinet this store runs. Official cab data "
            "covers Japan only, and community listings record the model just "
            "when someone noted it - so this is \"unknown\", not \"standard\"."
        ),
        "offline_cab": "offline cabinet",
        "offline_cabs": "offline cabinets",
        "offline_cap": (
            "This cabinet's network has shut down. It can still be played, but "
            "nothing is saved: no score history, no online play, no unlocks."
        ),
        "price_median": (
            "{game}, median of {n} quoted prices in {country}. "
            "Not this store's own price."
        ),
        "price_sparse": (
            "Based on only {n} listing(s) in {country}{for_game}, "
            "so treat it as a rough guide."
        ),
        "for_game": " for {game}",
        "typical_country": "Typical for {country} - not this store's own price",
        "permanently_closed": "Permanently closed.",
        "source": "source",
        "photo_by": "photo: {credit}",
        "unknown_author": "unknown",
        "size_1": "1 to 2 cabinets",
        "size_2": "3 to 9 cabinets",
        "size_3": "10 to 19 cabinets",
        "size_4": "20 to 49 cabinets",
        "size_5": "50 or more cabinets (mega arcade)",
        "size_U": "Count unknown",
    },
    "ja": {
        "shown": "{n} \u4ef6\u8868\u793a",
        "stores_total": "\u5168{n} \u5e97",
        "per_credit": "/\u30af\u30ec\u30b8\u30c3\u30c8",
        "show_more": "\u3082\u3063\u3068\u898b\u308b",
        "show_less": "\u6298\u308a\u305f\u305f\u3080",
        "search_wide": "\u30b2\u30fc\u30e0\u30fb\u5e97\u8217\u30fb\u5834\u6240\u3092\u691c\u7d22...",
        "search_narrow": "\u691c\u7d22...",
        "cab_model_unpublished": "\u7b4b\u4f53\u30e2\u30c7\u30eb\u672a\u516c\u958b",
        "cab_model_unpublished_cap": (
            "\u3069\u306e\u7b4b\u4f53\u304b\u3092\u660e\u8a18\u3057\u305f\u60c5\u5831\u304c\u3042\u308a\u307e\u305b\u3093\u3002"
            "\u516c\u5f0f\u306e\u7b4b\u4f53\u30c7\u30fc\u30bf\u306f\u65e5\u672c\u306e\u307f\u3002"
            "\u30b3\u30df\u30e5\u30cb\u30c6\u30a3\u63b2\u8f09\u306f\u8a18\u9332\u3055\u308c\u305f\u5834\u5408\u3060\u3051\u3067\u3059\u3002"
            "\u300c\u6a19\u6e96\u300d\u3067\u306f\u306a\u304f\u300c\u4e0d\u660e\u300d\u3067\u3059\u3002"
        ),
        "offline_cab": "\u30aa\u30d5\u30e9\u30a4\u30f3\u7b4b\u4f53",
        "offline_cabs": "\u30aa\u30d5\u30e9\u30a4\u30f3\u7b4b\u4f53",
        "offline_cap": (
            "\u3053\u306e\u7b4b\u4f53\u306e\u30cd\u30c3\u30c8\u30ef\u30fc\u30af\u306f\u7d42\u4e86\u3057\u3066\u3044\u307e\u3059\u3002"
            "\u904a\u3079\u307e\u3059\u304c\u30b9\u30b3\u30a2\u4fdd\u5b58\u30fb\u30aa\u30f3\u30e9\u30a4\u30f3\u30fb\u30a2\u30f3\u30ed\u30c3\u30af\u306f\u3067\u304d\u307e\u305b\u3093\u3002"
        ),
        "price_median": (
            "{game}\u3001{country}\u3067\u5f15\u7528{n}\u4ef6\u306e\u4e2d\u592e\u5024\u3002"
            "\u3053\u306e\u5e97\u306e\u5b9f\u969b\u6599\u91d1\u3067\u306f\u3042\u308a\u307e\u305b\u3093\u3002"
        ),
        "price_sparse": (
            "{country}\u3067{n}\u4ef6\u306e\u60c5\u5831\u306e\u307f{for_game}\u3002"
            "\u76ee\u5b89\u3068\u3057\u3066\u53d6\u3063\u3066\u304f\u3060\u3055\u3044\u3002"
        ),
        "for_game": "\uff08{game}\uff09",
        "typical_country": (
            "{country}\u306e\u5178\u578b\u4fa1\u683c - "
            "\u3053\u306e\u5e97\u306e\u5b9f\u969b\u6599\u91d1\u3067\u306f\u3042\u308a\u307e\u305b\u3093"
        ),
        "permanently_closed": "\u9589\u5e97\u6e08\u307f\u3002",
        "source": "\u51fa\u5178",
        "photo_by": "\u5199\u771f: {credit}",
        "unknown_author": "\u4e0d\u660e",
        "size_1": "1\u301c2 \u53f0",
        "size_2": "3\u301c9 \u53f0",
        "size_3": "10\u301c19 \u53f0",
        "size_4": "20\u301c49 \u53f0",
        "size_5": "50 \u53f0\u4ee5\u4e0a\uff08\u5de8\u5927\u5e97\uff09",
        "size_U": "\u53f0\u6570\u4e0d\u660e",
    },
    "zh-Hans": {
        "shown": "{n} \u4e2a\u663e\u793a",
        "stores_total": "\u5171 {n} \u5bb6\u95e8\u5e97",
        "per_credit": "\u6bcf\u6b21\u6295\u5e01",
        "show_more": "\u5c55\u5f00\u66f4\u591a",
        "show_less": "\u6536\u8d77",
        "search_wide": "\u641c\u7d22\u6e38\u620f\u3001\u8857\u673a\u5385\u3001\u5730\u70b9...",
        "search_narrow": "\u641c\u7d22...",
        "cab_model_unpublished": "\u672a\u516c\u5e03\u673a\u53f0\u578b\u53f7",
        "cab_model_unpublished_cap": (
            "\u6ca1\u6709\u6765\u6e90\u8bf4\u660e\u6b64\u5e97\u8fd0\u884c\u54ea\u79cd\u673a\u53f0\u3002"
            "\u5b98\u65b9\u673a\u53f0\u6570\u636e\u4ec5\u8986\u76d6\u65e5\u672c\uff1b"
            "\u793e\u533a\u5217\u8868\u53ea\u5728\u6709\u4eba\u8bb0\u5f55\u65f6\u624d\u6709\u578b\u53f7\u3002"
            "\u56e0\u6b64\u662f\u300c\u672a\u77e5\u300d\u800c\u975e\u300c\u6807\u51c6\u300d\u3002"
        ),
        "offline_cab": "\u79bb\u7ebf\u673a\u53f0",
        "offline_cabs": "\u79bb\u7ebf\u673a\u53f0",
        "offline_cap": (
            "\u6b64\u673a\u53f0\u7f51\u7edc\u5df2\u5173\u95ed\u3002\u4ecd\u53ef\u73a9\uff0c"
            "\u4f46\u4e0d\u4f1a\u4fdd\u5b58\u5206\u6570\u3001\u8054\u673a\u6216\u89e3\u9501\u3002"
        ),
        "price_median": (
            "{game}\uff0c{country} {n} \u6761\u62a5\u4ef7\u7684\u4e2d\u4f4d\u6570\u3002"
            "\u975e\u672c\u5e97\u5b9e\u9645\u4ef7\u683c\u3002"
        ),
        "price_sparse": (
            "\u4ec5\u57fa\u4e8e {country} \u7684 {n} \u6761\u4fe1\u606f{for_game}\uff0c\u4ec5\u4f9b\u53c2\u8003\u3002"
        ),
        "for_game": "\uff08{game}\uff09",
        "typical_country": "{country} \u5178\u578b\u4ef7 - \u975e\u672c\u5e97\u5b9e\u9645\u4ef7\u683c",
        "permanently_closed": "\u5df2\u6c38\u4e45\u5173\u95ed\u3002",
        "source": "\u6765\u6e90",
        "photo_by": "\u7167\u7247: {credit}",
        "unknown_author": "\u672a\u77e5",
        "size_1": "1\u20132 \u53f0\u673a\u53f0",
        "size_2": "3\u20139 \u53f0",
        "size_3": "10\u201319 \u53f0",
        "size_4": "20\u201349 \u53f0",
        "size_5": "50 \u53f0\u4ee5\u4e0a\uff08\u8d85\u5927\u5e97\uff09",
        "size_U": "\u53f0\u6570\u672a\u77e5",
    },
}

# Derive zh-Hant from Hans with key overrides for traditional forms already in place
UI["zh-Hant"] = dict(UI["zh-Hans"])
UI["zh-Hant"].update({
    "shown": "{n} \u500b\u986f\u793a",
    "stores_total": "\u5171 {n} \u5bb6\u5e97",
    "per_credit": "\u6bcf\u6b21\u6295\u5e63",
    "show_more": "\u5c55\u958b\u66f4\u591a",
    "search_wide": "\u641c\u5c0b\u904a\u6232\u3001\u8857\u6a5f\u5ef3\u3001\u5730\u9ede...",
    "cab_model_unpublished": "\u672a\u516c\u4f48\u6a5f\u53f0\u578b\u865f",
    "cab_model_unpublished_cap": (
        "\u6c92\u6709\u4f86\u6e90\u8aaa\u660e\u6b64\u5e97\u904b\u884c\u54ea\u7a2e\u6a5f\u53f0\u3002"
        "\u5b98\u65b9\u6a5f\u53f0\u8cc7\u6599\u50c5\u8986\u84cb\u65e5\u672c\uff1b"
        "\u793e\u7fa4\u5217\u8868\u53ea\u5728\u6709\u4eba\u8a18\u9304\u6642\u624d\u6709\u578b\u865f\u3002"
        "\u56e0\u6b64\u662f\u300c\u672a\u77e5\u300d\u800c\u975e\u300c\u6a19\u6e96\u300d\u3002"
    ),
    "offline_cab": "\u96e2\u7dda\u6a5f\u53f0",
    "offline_cabs": "\u96e2\u7dda\u6a5f\u53f0",
    "offline_cap": (
        "\u6b64\u6a5f\u53f0\u7db2\u7d61\u5df2\u95dc\u9589\u3002\u4ecd\u53ef\u73a9\uff0c"
        "\u4f46\u4e0d\u6703\u4fdd\u5b58\u5206\u6578\u3001\u806f\u6a5f\u6216\u89e3\u9396\u3002"
    ),
    "price_median": (
        "{game}\uff0c{country} {n} \u689d\u5831\u50f9\u7684\u4e2d\u4f4d\u6578\u3002"
        "\u975e\u672c\u5e97\u5be6\u969b\u50f9\u683c\u3002"
    ),
    "price_sparse": (
        "\u50c5\u57fa\u65bc {country} \u7684 {n} \u689d\u8cc7\u8a0a{for_game}\uff0c\u50c5\u4f9b\u53c3\u8003\u3002"
    ),
    "typical_country": "{country} \u5178\u578b\u50f9 - \u975e\u672c\u5e97\u5be6\u969b\u50f9\u683c",
    "permanently_closed": "\u5df2\u6c38\u4e45\u95dc\u9589\u3002",
    "source": "\u4f86\u6e90",
    "photo_by": "\u7167\u7247: {credit}",
    "size_1": "1\u20132 \u53f0\u6a5f\u53f0",
    "size_U": "\u53f0\u6578\u672a\u77e5",
})

UI["ko"] = {
    "shown": "{n}\uac1c \ud45c\uc2dc",
    "stores_total": "\uc804\uccb4 {n}\uac1c \ub9e4\uc7a5",
    "per_credit": "/\ud06c\ub808\ub527",
    "show_more": "\ub354 \ubcf4\uae30",
    "show_less": "\uc811\uae30",
    "search_wide": "\uac8c\uc784\u00b7\uc544\ucf00\uc774\ub4dc\u00b7\uc7a5\uc18c \uac80\uc0c9...",
    "search_narrow": "\uac80\uc0c9...",
    "cab_model_unpublished": "\uae30\uccb4 \ubaa8\ub378 \ubbf8\uacf5\uac1c",
    "cab_model_unpublished_cap": (
        "\uc774 \ub9e4\uc7a5\uc774 \uc5b4\ub5a4 \uae30\uccb4\uc778\uc9c0 \uc801\ud78c \ubaa9\ub85d\uc774 \uc5c6\uc2b5\ub2c8\ub2e4. "
        "\uacf5\uc2dd \uae30\uccb4 \ub370\uc774\ud130\ub294 \uc77c\ubcf8\ub9cc. "
        "\ucee4\ubba4\ub2c8\ud2f0\ub294 \uae30\ub85d\ub41c \uacbd\uc6b0\ub9cc. "
        "\u201c\ud45c\uc900\u201d\uc774 \uc544\ub2c8\ub77c \u201c\ubbf8\uc0c1\u201d\uc785\ub2c8\ub2e4."
    ),
    "offline_cab": "\uc624\ud504\ub77c\uc778 \uae30\uccb4",
    "offline_cabs": "\uc624\ud504\ub77c\uc778 \uae30\uccb4",
    "offline_cap": (
        "\uc774 \uae30\uccb4 \ub124\ud2b8\uc6cc\ud06c\ub294 \uc885\ub8cc\ub418\uc5c8\uc2b5\ub2c8\ub2e4. "
        "\ud50c\ub808\uc774\ub294 \uac00\ub2a5\ud558\uc9c0\ub9cc \uc810\uc218 \uc800\uc7a5\u00b7\uc628\ub77c\uc778\u00b7\uc5b8\ub77d\uc740 \ubd88\uac00\ub2a5\ud569\ub2c8\ub2e4."
    ),
    "price_median": (
        "{game}, {country} {n}\uac1c \uac00\uaca9\uc758 \uc911\uc704\uac12. "
        "\uc774 \ub9e4\uc7a5 \uc2e4\uc81c \uac00\uaca9 \uc544\ub2d8."
    ),
    "price_sparse": "{country} {n}\uac1c \uc815\ubcf4\ub9cc{for_game}. \ucc38\uace0\ub85c\ub9cc.",
    "for_game": " ({game})",
    "typical_country": "{country} \ud45c\uc900\uac00 - \uc774 \ub9e4\uc7a5 \uac00\uaca9 \uc544\ub2d8",
    "permanently_closed": "\uc601\uad6c \ud3d0\uc5c5.",
    "source": "\ucd9c\ucc98",
    "photo_by": "\uc0ac\uc9c4: {credit}",
    "unknown_author": "\ubbf8\uc0c1",
    "size_1": "1\u20132\ub300",
    "size_2": "3\u20139\ub300",
    "size_3": "10\u201319\ub300",
    "size_4": "20\u201349\ub300",
    "size_5": "50\ub300 \uc774\uc0c1(\uba54\uac00)",
    "size_U": "\ub300\uc218 \ubbf8\uc0c1",
}

# Remaining languages: base on English structure with localized short UI bits
for code, shown, total, more, less, wide, narrow, per, closed, source in [
    ("id", "{n} ditampilkan", "{n} toko total", "Tampilkan lebih", "Tampilkan kurang",
     "Cari game, arkade, tempat...", "Cari...", "per kredit", "Tutup permanen.", "sumber"),
    ("ms", "{n} dipaparkan", "{n} kedai jumlah", "Tunjuk lagi", "Tunjuk kurang",
     "Cari game, arked, tempat...", "Cari...", "per kredit", "Ditutup kekal.", "sumber"),
    ("es", "{n} mostrados", "{n} locales en total", "Mostrar m\u00e1s", "Mostrar menos",
     "Buscar juegos, arcades, lugares...", "Buscar...", "por cr\u00e9dito",
     "Cerrado permanentemente.", "fuente"),
    ("fr", "{n} affich\u00e9s", "{n} salons au total", "Voir plus", "Voir moins",
     "Rechercher jeux, salles, lieux...", "Rechercher...", "par cr\u00e9dit",
     "Ferm\u00e9 d\u00e9finitivement.", "source"),
    ("de", "{n} angezeigt", "{n} L\u00e4den gesamt", "Mehr anzeigen", "Weniger anzeigen",
     "Spiele, Arcades, Orte suchen...", "Suchen...", "pro Credit",
     "Dauerhaft geschlossen.", "Quelle"),
    ("pt", "{n} exibidos", "{n} lojas no total", "Mostrar mais", "Mostrar menos",
     "Buscar jogos, arcades, lugares...", "Buscar...", "por cr\u00e9dito",
     "Fechado permanentemente.", "fonte"),
    ("it", "{n} mostrati", "{n} locali in totale", "Mostra di pi\u00f9", "Mostra meno",
     "Cerca giochi, sale, luoghi...", "Cerca...", "per credito",
     "Chiuso definitivamente.", "fonte"),
    ("fil", "{n} ipinapakita", "{n} na tindahan sa kabuuan", "Ipakita pa", "Magpakita ng mas kaunti",
     "Maghanap ng laro, arcade, lugar...", "Maghanap...", "bawat credit",
     "Permanenteng sarado.", "pinagmulan"),
    ("vi", "{n} \u0111ang hi\u1ec7n", "t\u1ed5ng {n} c\u1eeda h\u00e0ng", "Xem th\u00eam", "Thu g\u1ecdn",
     "T\u00ecm game, arcade, \u0111\u1ecba \u0111i\u1ec3m...", "T\u00ecm...", "m\u1ed7i credit",
     "\u0110\u00e3 \u0111\u00f3ng v\u0129nh vi\u1ec5n.", "ngu\u1ed3n"),
    ("th", "\u0e41\u0e2a\u0e14\u0e07 {n}", "\u0e23\u0e49\u0e32\u0e19\u0e17\u0e31\u0e49\u0e07\u0e2b\u0e21\u0e14 {n}",
     "\u0e41\u0e2a\u0e14\u0e07\u0e40\u0e1e\u0e34\u0e48\u0e21", "\u0e41\u0e2a\u0e14\u0e07\u0e19\u0e49\u0e2d\u0e22\u0e25\u0e07",
     "\u0e04\u0e49\u0e19\u0e2b\u0e32\u0e40\u0e01\u0e21 \u0e2d\u0e32\u0e23\u0e4c\u0e40\u0e04\u0e14 \u0e2a\u0e16\u0e32\u0e19\u0e17\u0e35\u0e48...",
     "\u0e04\u0e49\u0e19\u0e2b\u0e32...", "\u0e15\u0e48\u0e2d\u0e04\u0e23\u0e14\u0e34\u0e15",
     "\u0e1b\u0e34\u0e14\u0e16\u0e32\u0e27\u0e23.", "\u0e41\u0e2b\u0e25\u0e48\u0e07"),
    ("ru", "{n} \u043f\u043e\u043a\u0430\u0437\u0430\u043d\u043e", "\u0432\u0441\u0435\u0433\u043e {n} \u0442\u043e\u0447\u0435\u043a",
     "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u0435\u0449\u0451", "\u0421\u0432\u0435\u0440\u043d\u0443\u0442\u044c",
     "\u0418\u0441\u043a\u0430\u0442\u044c \u0438\u0433\u0440\u044b, \u0430\u0440\u043a\u0430\u0434\u044b, \u043c\u0435\u0441\u0442\u0430...",
     "\u041f\u043e\u0438\u0441\u043a...", "\u0437\u0430 \u043a\u0440\u0435\u0434\u0438\u0442",
     "\u0417\u0430\u043a\u0440\u044b\u0442\u043e \u043d\u0430\u0432\u0441\u0435\u0433\u0434\u0430.", "\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a"),
]:
    base = dict(UI["en"])
    base.update({
        "shown": shown, "stores_total": total, "show_more": more, "show_less": less,
        "search_wide": wide, "search_narrow": narrow, "per_credit": per,
        "permanently_closed": closed, "source": source,
    })
    UI[code] = base


def find_lang(text: str, code: str):
    m = re.search(r'["\']' + re.escape(code) + r'["\']\s*:\s*\{', text)
    if not m:
        m = re.search(r"\b" + re.escape(code) + r":\s*\{", text)
    return m


def extract_brace_block(text: str, open_brace_index: int) -> tuple[int, int]:
    depth = 0
    i = open_brace_index
    in_str = False
    esc = False
    quote = ""
    while i < len(text):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
        else:
            if ch in ("'", '"'):
                in_str = True
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return open_brace_index, i + 1
        i += 1
    raise ValueError("unbalanced")


def inject_section(body: str, name: str, keys: dict) -> str:
    """Insert or replace a top-level section object inside a language block body."""
    # Remove existing section if present
    pat = re.compile(r",?\s*" + re.escape(name) + r"\s*:\s*\{", re.S)
    m = pat.search(body)
    if m:
        # find the opening brace of section
        brace = body.find("{", m.start())
        # extract relative to body
        # Need absolute - work on body only with local index
        depth = 0
        i = brace
        in_str = False
        esc = False
        quote = ""
        while i < len(body):
            ch = body[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == quote:
                    in_str = False
            else:
                if ch in ("'", '"'):
                    in_str = True
                    quote = ch
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        # also eat trailing comma
                        j = end
                        while j < len(body) and body[j] in " \t":
                            j += 1
                        if j < len(body) and body[j] == ",":
                            end = j + 1
                        body = body[: m.start()] + body[end:]
                        break
            i += 1
    # Append section before end of language object (body is inside lang, ends before final })
    add = ",\n      %s: {\n" % name
    for k, v in keys.items():
        add += "        %s: %s,\n" % (k, json.dumps(v, ensure_ascii=False))
    add += "      }"
    # add already starts with a leading comma
    body = body.rstrip().rstrip(",")
    return body + add + "\n    "


def main() -> None:
    text = I18N.read_text(encoding="utf-8")
    for code in LANGS:
        lm = find_lang(text, code)
        if not lm:
            print("no lang", code)
            continue
        # language object opens at last {
        open_i = text.rfind("{", lm.start(), lm.end())
        b0, b1 = extract_brace_block(text, open_i)
        body = text[b0 + 1 : b1 - 1]
        # strip prior injects of cabs/ui sections
        body = inject_section(body, "cabs", CABS.get(code, CABS["en"]))
        body = inject_section(body, "ui", UI.get(code, UI["en"]))
        text = text[: b0 + 1] + body + text[b1 - 1 :]
        print("ok", code)
    I18N.write_text(text, encoding="utf-8", newline="\n")
    t2 = I18N.read_text(encoding="utf-8")
    print("ja Valkyrie", "Valkyrie\u30e2\u30c7\u30eb" in t2)
    print("ja shown", "\u4ef6\u8868\u793a" in t2)
    print("syntax: run node --check")


if __name__ == "__main__":
    main()
