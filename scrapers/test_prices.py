"""Unit tests for scrapers/prices.py.

Run:  python scrapers/test_prices.py
      python -m unittest scrapers.test_prices

Emphasis is deliberately on the NEGATIVE cases. A wrong price is worse than no
price, so most of this file is about strings that must NOT produce a number:
store tokens, free play, premium/VIP tiers, bundles, promotional days and
per-coin unit rates.

The final test class is a live check against data/enrichment.json. It asserts
the thing the whole module exists for: Hong Kong maimai_dx and chunithm come
out at HKD 6.00, tier "measured". It is skipped when the data files are not
present so the parser tests still run standalone.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices  # noqa: E402


def p(text, local=None):
    return prices.parse_price(text, local)


def reason(text, local=None):
    return prices.classify(text, local)["reason"]


class TestAmountParsing(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(prices.to_amount("6.00"), 6.0)
        self.assertEqual(prices.to_amount("1,320.00"), 1320.0)
        self.assertEqual(prices.to_amount("100"), 100.0)

    def test_decimal_comma(self):
        self.assertEqual(prices.to_amount("6,90"), 6.9)
        self.assertEqual(prices.to_amount("0,50"), 0.5)

    def test_thousands_dot_zero_decimal(self):
        # Indonesian and Vietnamese listings write 10,900 as "10.900".
        self.assertEqual(prices.to_amount("10.900", "IDR"), 10900.0)
        self.assertEqual(prices.to_amount("15.000", "VND"), 15000.0)
        # ...but a genuine minor unit in a decimal currency stays a decimal.
        self.assertEqual(prices.to_amount("10.900", "USD"), 10.9)
        self.assertEqual(prices.to_amount("6.00", "HKD"), 6.0)

    def test_european_mixed(self):
        self.assertEqual(prices.to_amount("10.900,00", "IDR"), 10900.0)

    def test_rejects_non_numbers(self):
        self.assertIsNone(prices.to_amount("abc"))
        self.assertIsNone(prices.to_amount("0"))
        self.assertIsNone(prices.to_amount(""))


class TestPositiveParses(unittest.TestCase):
    """The prompt's positive examples, each with the figure it must yield."""

    CASES = [
        ("HK$6.00 for 3 songs", "HKD", "HKD", 6.0, 3),
        ("JP¥100 for 3 songs", "JPY", "JPY", 100.0, 3),
        ("NT$30.00 for 3 songs", "TWD", "TWD", 30.0, 3),
        ("PHP 15.00 for 3 songs", "PHP", "PHP", 15.0, 3),
        ("SGD 1.50 for 3 songs / SGD 1.50 to continue", "SGD", "SGD", 1.5, 3),
        ("$1 / 3 songs", "USD", "USD", 1.0, 3),
        ("¥100 / 3 songs (1 player)", "JPY", "JPY", 100.0, 3),
        ("100Y = 3 songs STANDARD MODE", "JPY", "JPY", 100.0, 3),
        ("GBP 1.00", "GBP", "GBP", 1.0, None),
        ("RM 2.00", "MYR", "MYR", 2.0, None),
        ("€1.00 for 3 songs", "EUR", "EUR", 1.0, 3),
        ("1.00€ / 3 songs", "EUR", "EUR", 1.0, 3),
        ("₩500 for 4 songs", "KRW", "KRW", 500.0, 4),
        ("CN¥4.00 for 3 songs", "CNY", "CNY", 4.0, 3),
        ("Rp10.900 / 3 songs", "IDR", "IDR", 10900.0, 3),
        ("₱60.00 for 3 songs", "PHP", "PHP", 60.0, 3),
        ("A$3.50 for 3 songs", "AUD", "AUD", 3.5, 3),
        ("MOP$8 / 2 songs", "MOP", "MOP", 8.0, 2),
    ]

    def test_cases(self):
        for text, local, cur, amount, songs in self.CASES:
            with self.subTest(text=text):
                got = p(text, local)
                self.assertIsNotNone(got, "expected a price from %r" % text)
                self.assertEqual(got["currency"], cur)
                self.assertAlmostEqual(got["amount"], amount)
                if songs is not None:
                    self.assertEqual(got["songs"], songs)


class TestTierSelection(unittest.TestCase):
    """Light / Standard / Premium cost different amounts. Standard wins, and a
    premium figure is never returned as if it were the standard price."""

    def test_standard_beats_premium(self):
        got = p("NT$30 / Standard Start / NT$40 / Premium Start", "TWD")
        self.assertEqual(got["amount"], 30.0)
        self.assertEqual(got["tier"], "base")

    def test_standard_beats_light_and_premium(self):
        # HK$6 LIGHT / HK$8 STANDARD / HK$12 PREMIUM / HK$12 BLASTER.
        # The standard start is 8, not the cheaper light 6.
        got = p("HK$6 / 3 songs LIGHT START / HK$8 / 3 songs STANDARD START / "
                "HK$12 / 3 songs PREMIUM START / HK$12 / 3 songs BLASTER START",
                "HKD")
        self.assertEqual(got["amount"], 8.0)
        self.assertEqual(got["tier"], "base")

    def test_nearest_keyword_wins(self):
        # The 2.70 window names Standard AND Premium; Standard is nearer.
        got = p("$2.70 / Standard / Premium Play / $10.80 / Galaxy Play / "
                "Versus mode requires 2 credits", "USD")
        self.assertEqual(got["amount"], 2.70)
        self.assertEqual(got["tier"], "base")

    def test_galaxy_never_selected(self):
        got = p("NT$40 / Normal Start / NT$50 / Premium Start / "
                "NT$90 / Galaxy Start", "TWD")
        self.assertEqual(got["amount"], 40.0)

    def test_light_only_falls_back_to_light(self):
        got = p("HKD$6 / 2 songs LIGHT MODE", "HKD")
        self.assertIsNotNone(got)
        self.assertEqual(got["tier"], "light")
        self.assertEqual(got["amount"], 6.0)

    def test_premium_only_is_rejected(self):
        self.assertIsNone(p("HK$16 / PREMIUM FREE", "HKD"))
        self.assertEqual(reason("HK$16 / PREMIUM FREE", "HKD"),
                         "all_tiers_rejected")

    def test_vip_price_not_used(self):
        # The VIP figure is a members-only rate, the walk-in price is 3.00.
        got = p("$3.00 / Normal / $2.80 / VIP / 3 songs per credit", "AUD")
        self.assertEqual(got["amount"], 3.00)

    def test_card_tier_in_parentheses_rejected(self):
        got = p("₱60.00 (Yellow card) / ₱57.00 (Blue card) = 1 credit "
                "/ [Standard] / 1 credit / 1 player = 3 songs", "PHP")
        self.assertIsNotNone(got)
        self.assertEqual(got["amount"], 60.0,
                         "the Blue-card rate is a members price, not the "
                         "walk-in price")

    def test_loyalty_card_ladders_take_the_entry_rung(self):
        """The walk-in price, never the members-only discount."""
        cases = [
            ("$3.30 / 3-4 songs (Welcome card) / $3.00 / 3-4 songs "
             "(Blue/Gold card) / $2.80 / 3-4 songs (Platinum card)",
             "NZD", 3.30),
            ("$3.00 / Regular [Red Card] / 3 songs / $2.80 / "
             "VIP [Blue, Gold, Platinum Card] / 3 songs", "AUD", 3.00),
            ("AUD$3.50 / 1 Credit / AUD$3.30 / 1 Credit VIP / "
             "AUD$6.00 / 1 Sega Aime Card", "AUD", 3.50),
            ("Rp14.000 (RED/BLUE) / 3 songs (1P) / Rp13.000 (GOLD/PLATINUM) "
             "/ 3 songs (1P)", "IDR", 14000.0),
        ]
        for text, local, want in cases:
            with self.subTest(text=text):
                self.assertEqual(p(text, local)["amount"], want)

    def test_ladders_that_label_before_the_price(self):
        """'Welcome Card $3.8 / Platinum $3.25' labels first; the same tier
        logic has to run backwards or it picks the members rate."""
        cases = [
            ("Welcome Card $3.8 / Blue&Gold $3.4 / Platinum $3.25",
             "NZD", 3.80),
            ("Welcome: $3.70 / Blue/Gold: $3.50 / Platinum: $3.30",
             "SGD", 3.70),
            ("A$4 / 3 songs VISITOR / A$3.5 / 3 songs MEMBER", "AUD", 4.00),
        ]
        for text, local, want in cases:
            with self.subTest(text=text):
                self.assertEqual(p(text, local)["amount"], want)

    def test_paseli_ladder_standard_start(self):
        # A long SDVX board: many ¥100 light/analyzer lines, one ¥120 standard.
        got = p("CREDIT / ¥100 / LIGHT START / ¥100 / SKILL ANALYZER / "
                "PASELI / ¥100 / LIGHT START / ¥120 / STANDARD START / "
                "¥200 / PREMIUM TIME", "JPY")
        self.assertEqual(got["amount"], 120.0)
        self.assertEqual(got["tier"], "base")

    def test_preamble_prose_does_not_flip_label_orientation(self):
        """A leading sentence that happens to say "Standard" must not switch
        the whole string into label-before-price mode - every price would then
        inherit the label belonging to the price above it, and this row would
        return the $2.80 VIP rate instead of the $3.00 walk-in rate."""
        got = p("Standard/Premium Modes Are The Same Price. Galaxy Mode is "
                "2 Credits. / $3.00 / Regular [Red Card] / 3 songs / $2.80 / "
                "VIP [Blue, Gold, Platinum Card] / 3 songs", "AUD")
        self.assertEqual(got["amount"], 3.00)

    def test_ambiguous_ladder_is_rejected_not_guessed(self):
        # "Red and blue card" names an entry rung AND a members rung in the
        # same breath. Refusing is correct; guessing is what this module is
        # here to stop.
        self.assertIsNone(
            p("Red and blue card : Rp. 15000 / Gold and platinum : Rp. 14000",
              "IDR"))

    def test_continue_price_not_used_alone(self):
        self.assertIsNone(p("¥100 to continue", "JPY"))

    def test_doubles_and_versus_rejected(self):
        got = p("HK$6.00 / 3 songs Single Play / HK$12.00 / 4 songs Multi-Play",
                "HKD")
        self.assertEqual(got["amount"], 6.0)
        got = p("NT$5.00 / 3 songs SINGLE MODE / NT$10.00 / 3 songs "
                "VERSUS/DOUBLE MODE", "TWD")
        self.assertEqual(got["amount"], 5.0)
        got = p("3€ or 45 credits / 3 songs SP or Doubles / 6€ or 90 "
                "credits / 3 songs DP", "EUR")
        # 6 EUR is the DP (doubles) price; it must not be selected. 3 EUR is
        # itself a bundle-ish "or 45 credits" line, so the whole row is dropped.
        self.assertTrue(got is None or got["amount"] != 6.0)


class TestConditionalClausesKept(unittest.TestCase):
    """The single most important negative-of-a-negative: a parenthesised
    'multiplay' aside describes a bonus, not a multiplayer price tier. These
    ARE the Hong Kong maimai_dx rows and losing them breaks everything."""

    def test_multiplay_aside_kept(self):
        got = p("HK$6.00 / 3 songs (4 songs if multiplay)", "HKD")
        self.assertIsNotNone(got)
        self.assertEqual(got["amount"], 6.0)

    def test_multiplayer_aside_kept(self):
        got = p("HK$6.00 / 3 songs (4 songs if multiplayer)", "HKD")
        self.assertEqual(got["amount"], 6.0)

    def test_cab_to_cab_aside_kept(self):
        got = p("HK$6.00 / 3 songs (4 songs if 1 song out of 3 was played "
                "with Cabinet-to-cabinet play)", "HKD")
        self.assertEqual(got["amount"], 6.0)

    def test_two_player_aside_kept(self):
        got = p("Rp16000 / 3 songs (4 songs when two player)", "IDR")
        self.assertEqual(got["amount"], 16000.0)

    def test_versus_requirement_note_kept(self):
        got = p("$2.70 / Standard / Versus mode requires 2 credits", "USD")
        self.assertEqual(got["amount"], 2.70)

    def test_one_player_note_kept(self):
        got = p("¥100 / 3 songs (1 player)", "JPY")
        self.assertEqual(got["amount"], 100.0)


class TestTokenSystemRejections(unittest.TestCase):
    """Store tokens have no public exchange rate. Never coerce to a number."""

    NON_MONEY = [
        ("3 Medals", None),
        ("8 creds", None),
        ("2 Medals / LIGHT / 3 Medals / STANDARD", None),
        ("6.9 credits", None),
        ("4 Tokens / 3 songs", None),
        ("9 Credits", None),
        ("4 tokens", None),
        ("10.0 chips / 3 songs Standard Play", "USD"),
        ("3 quarters / 3 songs joint premium", "USD"),
        ("4 quarters / 4 songs", "USD"),
        ("2 Quarters", "GBP"),
        ("20 Points / 3 songs", "USD"),
        ("6.8 Funcoins / Single", "GBP"),
        ("15 Tizo / 3 songs", "IDR"),
        ("1 token / 2 songs", "SEK"),
        ("100P / Standard Start", "GBP"),
    ]

    def test_all_rejected(self):
        for text, local in self.NON_MONEY:
            with self.subTest(text=text):
                self.assertIsNone(p(text, local),
                                  "%r must not produce a price" % text)

    def test_reason_is_token_system(self):
        self.assertEqual(reason("3 Medals"), "token_system")
        self.assertEqual(reason("8 creds"), "token_system")
        self.assertEqual(reason("2 Medals / LIGHT / 3 Medals / STANDARD"),
                         "token_system")
        self.assertEqual(reason("3 quarters / 3 songs joint premium", "USD"),
                         "token_system")

    def test_token_exchange_rate_definition_rejected(self):
        # The money named is what ONE token costs; a play costs seven of them.
        # Reading it as a play price understates by 7x.
        for text in [
            "1 TOKEN = Rp. 2500,00 / Price to play : 7 TOKEN",
            "1 TOKEN = Rp. 2500,00 / Price to play : 7 TOKEN / "
            "7 Tokens : IDR 17.500,00",
            "5 FUN / LIGHT START / 5 FUN / STANDARD START / 1 FUN = Rp. 1000,00",
            "RED/BLUE : 15 Tizo / GOLD/PLATINUM : 14 Tizo / *1 Tizo = Rp.1.000,-",
            "1 Token = R4 / 1 Player = 2 Tokens",
            "4 Tokens for 1 Credit / (1 Token = 0.25¢)",
        ]:
            with self.subTest(text=text):
                self.assertIsNone(p(text, "IDR"))

    def test_per_coin_rate_rejected(self):
        # A coin is a sub-credit unit: a play swallows several.
        self.assertIsNone(p("3元/币 / 3 yuan/coin", "CNY"))
        self.assertIsNone(p("･1 / coin", "CNY"))

    def test_per_credit_rate_kept_when_one_credit_is_one_play(self):
        got = p("$2.10 Per Credit", "AUD")
        self.assertIsNotNone(got)
        self.assertEqual(got["amount"], 2.10)

    def test_per_credit_rate_rejected_when_play_needs_several(self):
        self.assertIsNone(
            p("Rp1.600/credit / Rp8.000 : 5 credits STANDARD / "
              "Rp9.600 : 6 credits PREMIUM", "IDR"))


class TestFreePlayRejections(unittest.TestCase):
    FREE = [
        "free play",
        "Free play during rental",
        "Free Play / 3 songs",
        "free play",
        "FREE PLAY",
    ]

    def test_rejected(self):
        for text in self.FREE:
            with self.subTest(text=text):
                self.assertIsNone(p(text, "USD"))
                self.assertEqual(reason(text, "USD"), "free_play")

    def test_free_play_never_becomes_zero(self):
        # The failure mode this guards: a 0.00 sneaking into an aggregate and
        # dragging a country's figure down.
        got = prices.classify("free play", "USD")
        self.assertNotIn("amount", got)


class TestTimeAndPromoRejections(unittest.TestCase):
    def test_time_passes_rejected(self):
        self.assertIsNone(p("$5 for 1 Hour / $20 for all day", "USD"))
        self.assertIsNone(p("daily pass / up to 0.80€", "EUR"))
        self.assertIsNone(p("HK$20 / 10 minutes PREMIUM FREE", "HKD"))

    def test_promotional_day_price_rejected(self):
        got = p("$2.20 / Normal / $1.10 / Tuesday Happy Hour", "AUD")
        self.assertEqual(got["amount"], 2.20,
                         "the Tuesday promo rate is not the standard price")
        self.assertIsNone(
            p("Weekdays: S$0.66 / 4 songs / Weekends and holidays: S$1 / "
              "4 songs / Limited period promotion: S$0.33 / 4 songs", "SGD"))

    def test_bundle_pricing_rejected(self):
        for text in [
            "£5: 45 Credits (£1.44 per credit) / "
            "£10: 100 Credits (£1.3 per credit)",
            "£50 worth of arcade credits gives 350 credits",
            "10 credits for €8",
            "28 Credits / 50 Credits for €5",
            "22 Credits ≈ 2.2€",
        ]:
            with self.subTest(text=text):
                self.assertIsNone(p(text, "GBP" if "£" in text else "EUR"))


class TestCurrencyResolution(unittest.TestCase):
    def test_bare_glyph_needs_compatible_local(self):
        # "$1.00" in the US is a dollar; with no country it is unresolvable.
        self.assertIsNotNone(p("$1.00 for 3 songs", "USD"))
        self.assertIsNone(p("$1.00 for 3 songs", None))

    def test_bare_yen_glyph_rejected_in_a_non_yen_country(self):
        # A real row: a UK arcade whose listing reads "¥100". That is an
        # import cab or a copy-paste, and it is certainly not GBP 100.
        self.assertIsNone(p("¥100 for 3 songs", "GBP"))

    def test_bare_dollar_glyph_rejected_in_a_non_dollar_country(self):
        self.assertIsNone(p("$1.00 for 3 songs", "GBP"))
        self.assertIsNone(p("$1.00 for 3 songs", "JPY"))

    def test_bare_dollar_accepted_in_dollar_countries(self):
        for local in ("USD", "HKD", "TWD", "AUD", "SGD", "NZD", "CAD"):
            with self.subTest(local=local):
                got = p("$2.00 for 3 songs", local)
                self.assertIsNotNone(got)
                self.assertEqual(got["currency"], local)

    def test_explicit_token_beats_local(self):
        got = p("HK$6.00 for 3 songs", "USD")
        self.assertEqual(got["currency"], "HKD")

    def test_guarded_yen_suffix_needs_agreement(self):
        # "100Y" resolves to yen in Japan and nowhere else.
        self.assertEqual(p("100Y = 3 songs STANDARD MODE", "JPY")["amount"],
                         100.0)
        self.assertIsNone(p("100Y = 3 songs STANDARD MODE", "USD"))

    def test_local_currency_preferred_over_an_aside(self):
        got = p("US$1.00 for 3 songs (about HK$8)", "USD")
        self.assertEqual(got["currency"], "USD")

    def test_unknown_currency_rejected(self):
        self.assertIsNone(p("ARS 1,320.00", None))
        self.assertIsNone(p("CZK 40.00 for 1 song", None))
        self.assertEqual(reason("PLN 0.50 for 3 songs", None), "no_currency")


class TestAggregation(unittest.TestCase):
    ROWS = [("a%d" % i, "Hong Kong", "maimai_dx", "HK$6.00 for 3 songs")
            for i in range(6)]

    def test_measured_tier(self):
        countries, stats, _ = prices.aggregate(self.ROWS, "2026-07-29")
        cell = countries["Hong Kong"]["games"]["maimai_dx"]
        self.assertEqual(cell["tier"], "measured")
        self.assertEqual(cell["n"], 6)
        self.assertEqual(cell["value"], 6.0)
        self.assertEqual(cell["currency"], "HKD")

    def test_sparse_tier(self):
        countries, _, _ = prices.aggregate(self.ROWS[:3], "2026-07-29")
        self.assertEqual(
            countries["Hong Kong"]["games"]["maimai_dx"]["tier"], "sparse")

    def test_unknown_tier(self):
        countries, _, _ = prices.aggregate(self.ROWS[:1], "2026-07-29")
        self.assertEqual(
            countries["Hong Kong"]["games"]["maimai_dx"]["tier"], "unknown")

    def test_mode_not_mean(self):
        rows = [("a%d" % i, "Hong Kong", "taiko", "HK$8.00 for 3 songs")
                for i in range(5)]
        rows.append(("z", "Hong Kong", "taiko", "HK$30.00 for 3 songs"))
        countries, _, _ = prices.aggregate(rows, "2026-07-29")
        cell = countries["Hong Kong"]["games"]["taiko"]
        self.assertEqual(cell["value"], 8.0, "an outlier must not move the "
                                             "headline figure")
        self.assertEqual(cell["max"], 30.0)

    def test_mode_ties_break_low(self):
        rows = [("a", "Hong Kong", "jubeat", "HK$6.00"),
                ("b", "Hong Kong", "jubeat", "HK$6.00"),
                ("c", "Hong Kong", "jubeat", "HK$8.00"),
                ("d", "Hong Kong", "jubeat", "HK$8.00")]
        countries, _, _ = prices.aggregate(rows, "2026-07-29")
        self.assertEqual(countries["Hong Kong"]["games"]["jubeat"]["value"], 6.0)

    def test_median_never_becomes_the_headline(self):
        # {6, 8} medians to 7.00. Nobody charges 7. The headline must not.
        rows = [("a", "Hong Kong", "sdvx", "HK$6.00"),
                ("b", "Hong Kong", "sdvx", "HK$8.00")]
        countries, _, _ = prices.aggregate(rows, "2026-07-29")
        cell = countries["Hong Kong"]["games"]["sdvx"]
        self.assertEqual(cell["median"], 7.0)
        self.assertIn(cell["value"], (6.0, 8.0))
        self.assertTrue(cell["median_differs"])

    def test_single_arcade_dominance_demoted(self):
        rows = [("same", "Hong Kong", "popn", "HK$6.00 for 3 songs")] * 5
        rows.append(("other", "Hong Kong", "popn", "HK$6.00 for 3 songs"))
        countries, _, _ = prices.aggregate(rows, "2026-07-29")
        cell = countries["Hong Kong"]["games"]["popn"]
        self.assertEqual(cell["tier"], "unknown")
        self.assertEqual(cell.get("rejected_by"), "single_arcade_dominance")

    def test_implausible_value_dropped(self):
        rows = [("a%d" % i, "Japan", "taiko", "JP¥1 for 4 songs")
                for i in range(8)]
        countries, stats, artifacts = prices.aggregate(rows, "2026-07-29")
        self.assertNotIn("Japan", countries)
        self.assertEqual(stats["gate_drops"]["implausible"], 8)
        self.assertTrue(all(a[3] == "implausible" for a in artifacts))

    def test_currency_mismatch_dropped(self):
        rows = [("a%d" % i, "United States", "iidx", "JP¥100 for 3 songs")
                for i in range(8)]
        countries, stats, _ = prices.aggregate(rows, "2026-07-29")
        self.assertNotIn("United States", countries)
        self.assertEqual(stats["gate_drops"]["currency_mismatch"], 8)

    def test_country_overall_is_one_vote_per_arcade(self):
        rows = [("big", "Hong Kong", "g%d" % i, "HK$20.00") for i in range(10)]
        rows += [("s%d" % i, "Hong Kong", "maimai_dx", "HK$6.00")
                 for i in range(4)]
        countries, _, _ = prices.aggregate(rows, "2026-07-29")
        overall = countries["Hong Kong"]["overall"]
        self.assertEqual(overall["n"], 5, "one vote per arcade, not per row")
        self.assertEqual(overall["value"], 6.0,
                         "a single chain must not carry a country")

    def test_dispersed_cell_demoted_out_of_measured(self):
        """A plurality winner that the median disagrees with must not render
        as a definite figure. This is the HK gitadora shape: n=5, 2..10,
        mode 2 on 40%, median 6."""
        texts = ["HK$2.00", "HK$2.00", "HK$6.00", "HK$8.00", "HK$10.00"]
        rows = [("a%d" % i, "Hong Kong", "gitadora", t)
                for i, t in enumerate(texts)]
        countries, _, _ = prices.aggregate(rows, "2026-07-29")
        cell = countries["Hong Kong"]["games"]["gitadora"]
        self.assertEqual(cell["n"], 5)
        self.assertTrue(cell["dispersed"])
        self.assertEqual(cell["tier"], "sparse")
        self.assertEqual(cell["demoted_by"], "dispersed")

    def test_plurality_is_kept_when_the_median_agrees(self):
        """A plurality across many independent arcades whose median lands on
        the same figure is a real price. This is the US ddr shape."""
        texts = (["$1.00"] * 4) + ["$0.50", "$0.50", "$2.00", "$1.50"]
        rows = [("a%d" % i, "United States", "ddr", t)
                for i, t in enumerate(texts)]
        countries, _, _ = prices.aggregate(rows, "2026-07-29")
        cell = countries["United States"]["games"]["ddr"]
        self.assertEqual(cell["value"], 1.0)
        self.assertEqual(cell["median"], 1.0)
        self.assertFalse(cell["dispersed"])
        self.assertEqual(cell["tier"], "measured")

    def test_country_overall_needs_several_games(self):
        """A country figure drawn from one game is that game's price wearing
        a country label. This is the UK shape: 110 of 111 votes are DDR."""
        rows = [("a%d" % i, "United Kingdom", "ddr", "GBP 1.00")
                for i in range(20)]
        countries, _, _ = prices.aggregate(rows, "2026-07-29")
        overall = countries["United Kingdom"]["overall"]
        self.assertEqual(overall["games"], 1)
        self.assertEqual(overall["tier"], "sparse")
        self.assertEqual(overall["demoted_by"], "too_few_games")

    def test_country_overall_measured_across_games(self):
        rows = []
        for game in ("ddr", "maimai_dx", "taiko"):
            for i in range(4):
                rows.append(("%s%d" % (game, i), "Hong Kong", game, "HK$6.00"))
        countries, _, _ = prices.aggregate(rows, "2026-07-29")
        overall = countries["Hong Kong"]["overall"]
        self.assertEqual(overall["games"], 3)
        self.assertEqual(overall["tier"], "measured")
        self.assertEqual(overall["value"], 6.0)

    def test_no_country_row_skipped(self):
        countries, stats, _ = prices.aggregate(
            [("a", None, "maimai_dx", "HK$6.00")], "2026-07-29")
        self.assertEqual(countries, {})
        self.assertEqual(stats["no_country"], 1)

    def test_free_play_never_counted(self):
        rows = [("a%d" % i, "Hong Kong", "ddr", "free play") for i in range(9)]
        countries, stats, _ = prices.aggregate(rows, "2026-07-29")
        self.assertEqual(countries, {})
        self.assertEqual(stats["reject_reasons"]["free_play"], 9)


class TestBuildPriceTable(unittest.TestCase):
    def test_shape_and_local_currency_only(self):
        enrichment = {str(i): {"machine_prices": {"maimai_dx": "HK$6.00"}}
                      for i in range(6)}
        countries = {str(i): "Hong Kong" for i in range(6)}
        table = prices.build_price_table(enrichment, countries,
                                         as_of="2026-07-29")
        cell = table["countries"]["Hong Kong"]["games"]["maimai_dx"]
        self.assertEqual(cell["value"], 6.0)
        self.assertEqual(cell["currency"], "HKD")
        self.assertEqual(cell["as_of"], "2026-07-29")
        self.assertEqual(table["coverage"]["measured"], 1)
        # Nothing converted: no USD/JPY/CNY keys anywhere in the payload.
        blob = json.dumps(table)
        for key in ("usd", "converted", "fx"):
            self.assertNotIn('"%s"' % key, blob.lower())

    def test_json_serializable(self):
        enrichment = {"1": {"machine_prices": {"ddr": "$1.00 for 3 songs"}}}
        table = prices.build_price_table(enrichment, {"1": "United States"})
        json.dumps(table)

    def test_tolerates_junk_records(self):
        enrichment = {
            "1": None,
            "2": {"machine_prices": None},
            "3": {"machine_prices": "not a dict"},
            "4": {"machine_prices": {"ddr": None}},
            "5": {"machine_prices": {"ddr": "   "}},
            "6": {},
        }
        table = prices.build_price_table(enrichment, {"1": "Japan"})
        self.assertEqual(table["countries"], {})


# ------------------------------------------------------------- live data ----

def _load_live():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    enr = os.path.join(root, "data", "enrichment.json")
    arc = os.path.join(root, "data", "arcades.json")
    if not (os.path.exists(enr) and os.path.exists(arc)):
        return None
    return prices.build_from_disk(root)


class TestLiveData(unittest.TestCase):
    """The owner's own report, asserted against the shipped data."""

    @classmethod
    def setUpClass(cls):
        cls.table = _load_live()
        if cls.table is None:
            raise unittest.SkipTest("data/enrichment.json not available")

    def test_hong_kong_maimai_is_six_measured(self):
        cell = self.table["countries"]["Hong Kong"]["games"]["maimai_dx"]
        self.assertEqual(cell["currency"], "HKD")
        self.assertEqual(cell["value"], 6.0)
        self.assertEqual(cell["median"], 6.0)
        self.assertEqual(cell["tier"], "measured")
        self.assertGreaterEqual(cell["n"], 5)

    def test_hong_kong_chunithm_is_six_measured(self):
        cell = self.table["countries"]["Hong Kong"]["games"]["chunithm"]
        self.assertEqual(cell["currency"], "HKD")
        self.assertEqual(cell["value"], 6.0)
        self.assertEqual(cell["median"], 6.0)
        self.assertEqual(cell["tier"], "measured")
        self.assertGreaterEqual(cell["n"], 5)

    def test_hong_kong_never_shows_the_guessed_range(self):
        # The bug: "HKD 8-15/play typical". No HK cell may sit in 8-15 for the
        # two games the owner named, and the country figure must be 6.
        overall = self.table["countries"]["Hong Kong"]["overall"]
        self.assertEqual(overall["value"], 6.0)

    def test_japan_is_one_hundred_yen(self):
        games = self.table["countries"]["Japan"]["games"]
        for game in ("maimai_dx", "chunithm", "iidx", "sdvx", "taiko"):
            with self.subTest(game=game):
                self.assertEqual(games[game]["value"], 100.0)
                self.assertEqual(games[game]["tier"], "measured")

    def test_japan_one_yen_artifact_excluded(self):
        # Two ZIv rows quote "JP¥1", which is a placeholder, not a price.
        for cell in self.table["countries"]["Japan"]["games"].values():
            self.assertGreaterEqual(cell["min"], 50.0)
        gates = [a for a in self.table["artifacts"]
                 if a["country"] == "Japan" and a["gate"] == "implausible"]
        self.assertTrue(gates, "the JP¥1 rows must be recorded as "
                               "rejected artifacts")

    def test_taiwan_maimai(self):
        cell = self.table["countries"]["Taiwan"]["games"]["maimai_dx"]
        self.assertEqual(cell["currency"], "TWD")
        self.assertEqual(cell["value"], 30.0)
        self.assertEqual(cell["tier"], "measured")

    def test_united_states_ddr_is_a_dollar(self):
        cell = self.table["countries"]["United States"]["games"]["ddr"]
        self.assertEqual(cell["currency"], "USD")
        self.assertEqual(cell["value"], 1.0)
        self.assertEqual(cell["tier"], "measured")

    def test_every_cell_is_in_its_country_currency(self):
        for country, node in self.table["countries"].items():
            expected = prices.COUNTRY_CURRENCY[country]
            for game, cell in node["games"].items():
                with self.subTest(country=country, game=game):
                    self.assertEqual(cell["currency"], expected)

    def test_every_value_is_inside_its_plausibility_band(self):
        for country, node in self.table["countries"].items():
            for game, cell in node["games"].items():
                lo, hi = prices.PLAUSIBLE[cell["currency"]]
                with self.subTest(country=country, game=game):
                    self.assertGreaterEqual(cell["min"], lo)
                    self.assertLessEqual(cell["max"], hi)

    def test_unknown_cells_carry_no_guess(self):
        # tier unknown must never be dressed up as a country default.
        for node in self.table["countries"].values():
            for cell in node["games"].values():
                if cell["tier"] == "unknown":
                    self.assertLess(cell["n"], prices.MEASURED_MIN)

    def test_fx_round_trip_matches_the_owners_numbers(self):
        """HKD 6 must convert to ~USD 0.77 / JPY 125 / CNY 5.2."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "data", "fx_rates.json")
        if not os.path.exists(path):
            self.skipTest("no fx_rates.json")
        with open(path, encoding="utf-8") as fh:
            rates = json.load(fh)["rates"]
        hkd = self.table["countries"]["Hong Kong"]["games"]["maimai_dx"]["value"]
        usd = hkd / rates["HKD"]
        self.assertAlmostEqual(usd, 0.77, places=2)
        self.assertAlmostEqual(usd * rates["JPY"], 125.2, delta=1.0)
        self.assertAlmostEqual(usd * rates["CNY"], 5.18, delta=0.1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
