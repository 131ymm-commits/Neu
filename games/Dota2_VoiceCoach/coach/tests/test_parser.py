"""Тесты разбора фраз тренера. Запуск из папки coach/:  python -m unittest -v

Каждая строка CASES — фраза и ожидаемые команды (действие, позиции, параметры).
Параметры сравниваются только те, что указаны в ожидании.
Фразы придуманы Claude по памяти об игровом сленге; настоящие фразы тренера
из голосовых прогонов добавлять сюда же (с пометкой источника).
"""
import unittest

from voicecoach import Agent, MatchContext, parse, validate, normalize
from voicecoach.lexicon import ITEM_PHRASES, load_item_ids, load_heroes

ALL = [1, 2, 3, 4, 5]


def ctx(team="radiant", last=None):
    return MatchContext(
        team=team,
        agents=[
            Agent(1, "Miracle-", ("миракл", "мирак"), "npc_dota_hero_antimage"),
            Agent(2, "Topson", ("топсон",), "npc_dota_hero_invoker"),
            Agent(3, "Collapse", ("коллапс",), "npc_dota_hero_mars"),
            Agent(4, "Mira", ("мира",), "npc_dota_hero_hoodwink"),
            Agent(5, "Вася", ("вася", "васька"), "npc_dota_hero_crystal_maiden"),
        ],
        enemy_heroes=["npc_dota_hero_pudge", "npc_dota_hero_phantom_assassin",
                      "npc_dota_hero_storm_spirit", "npc_dota_hero_tidehunter",
                      "npc_dota_hero_lion"],
        last_agents=last or [],
    )


# (фраза, [(action, agents, {params})], настройки контекста)
CASES = [
    # адресация по имени, роли, герою, всем, остальным
    ("Миракл, фарми лес, остальные на Рошана",
     [("farm", [1], {"area": "jungle_own"}), ("roshan", [2, 3, 4, 5], {})]),
    ("все на роша", [("roshan", ALL, {})]),
    ("Миракл и Топсон, на роша", [("roshan", [1, 2], {})]),
    ("керри, фарми их лес", [("farm", [1], {"area": "jungle_enemy"})]),
    ("сапорты, стакните древних", [("stack", [4, 5], {"place": "ancients"})]),
    ("коры, фармите", [("farm", [1, 2, 3], {"area": "auto"})]),
    ("антимаг, фарми лес", [("farm", [1], {"area": "jungle_own"})]),
    ("инвокер иди на мид", [("move", [2], {"lane": "mid"})]),
    ("позиция 3 отходи", [("retreat", [3], {})]),
    ("пятерка, поставь вард на руну", [("ward", [5], {"place": "rune"})]),
    ("Васька, купи сентри", [("buy", [5], {"item": "item_ward_sentry"})]),
    ("Мираклу помоги", [("follow", [3], {"ally": 1})], {"last": [3]}),
    # «мид»: игрок или линия — по глаголу
    ("мид пушим", [("push", ALL, {"lane": "mid", "group": True})]),
    ("мид, пушь", [("push", [2], {"lane": "auto"})]),
    ("мид в лес", [("farm", [2], {"area": "jungle_own"})]),
    ("го мид", [("push", ALL, {"lane": "mid", "group": True})]),
    ("все мид", [("push", ALL, {"lane": "mid", "group": True})]),
    ("помогите миду", [("follow", [1, 3, 4, 5], {"ally": 2})]),
    # линии по стороне
    ("пушим лайт", [("push", ALL, {"lane": "bot"})]),
    ("пушим лайт", [("push", ALL, {"lane": "top"})], {"team": "dire"}),
    ("дефаем хардлейн", [("defend", ALL, {"lane": "top"})]),
    # башни
    ("т2 на топе сносим", [("push", ALL, {"lane": "top", "tier": 2})]),
    ("сносим вторую башню на боте", [("push", ALL, {"lane": "bot", "tier": 2})]),
    ("защищайте базу", [("defend", ALL, {"place": "base"})]),
    # цели и драки
    ("бейте пуджа", [("focus", ALL, {"enemy": "npc_dota_hero_pudge"})]),
    ("фокус фантомку", [("focus", ALL, {"enemy": "npc_dota_hero_phantom_assassin"})]),
    ("все на шторма", [("focus", ALL, {"enemy": "npc_dota_hero_storm_spirit"})]),
    ("убейте их керри", [("focus", ALL, {"enemy_pos": 1})]),
    ("заходим", [("engage", ALL, {})]),
    ("бейте!", [("engage", ALL, {})]),
    ("коллапс, инициируй на тайда", [("engage", [3], {"enemy": "npc_dota_hero_tidehunter"})]),
    ("не начинайте", [("hold", ALL, {"what": "engage"})]),
    ("ждём, не лезьте", [("hold", ALL, {})]),
    ("смок и ганг мид", [("smoke", ALL, {"then": "gank", "lane": "mid"})]),
    ("смокаемся", [("smoke", ALL, {})]),
    ("Мира, гангни топ", [("gank", [4], {"lane": "top"})]),
    # отступление и срочность
    ("отходим отходим", [("retreat", ALL, {})]),
    ("все назад срочно", [("retreat", ALL, {})]),
    ("валим на базу", [("retreat", ALL, {"place": "base"})]),
    ("не отходите", [("hold", ALL, {"what": "retreat"})]),
    # ульты и предметы
    ("держи ульту", [("save_ult", [2], {})], {"last": [2]}),
    ("Топсон, прожми ульту", [("use_ult", [2], {})]),
    ("не ультуй", [("save_ult", [2], {})], {"last": [2]}),
    ("Миракл, купи бкб", [("buy", [1], {"item": "item_black_king_bar"})]),
    ("Миракл, собирай бкб", [("buy", [1], {"item": "item_black_king_bar"})]),
    ("Миракл, прожми бкб", [("use_item", [1], {"item": "item_black_king_bar"})]),
    ("купи смоки", [("buy", [4], {"item": "item_smoke_of_deceit"})], {"last": [4]}),
    ("купи бкб", [("buy", [], {"item": "item_black_king_bar"})]),     # нужно «кому?»
    ("керри, бб", [("buyback", [1], {})]),
    ("Миракл, выкупайся", [("buyback", [1], {})]),
    # перемещение и союзники
    ("Миракл, тп на мид", [("tp", [1], {"lane": "mid"})]),
    ("Миракл иди с Топсоном", [("follow", [1], {"ally": 2})]),
    ("спасите керри", [("save", [2, 3, 4, 5], {"ally": 1})]),
    ("идите на топ", [("push", ALL, {"lane": "top", "group": True})]),
    ("собираемся на миду", [("group", ALL, {"lane": "mid"})]),
    ("собираемся", [("group", ALL, {})]),
    ("торментор", [("tormentor", ALL, {})]),
    # последовательность
    ("Миракл фарми лес, потом пушь топ",
     [("farm", [1], {"area": "jungle_own"}), ("push", [1], {"lane": "top"})]),
    ("Миракл фарми и пушь", [("farm", [1], {}), ("push", [1], {})]),
    ("Миракл фарми лес Топсон пушь мид",
     [("farm", [1], {"area": "jungle_own"}), ("push", [2], {"lane": "mid"})]),
    # управление
    ("отмена", [("cancel", ALL, {})]),
    ("играйте сами", [("free", ALL, {})]),
    ("доклад", [("report", ALL, {})]),
    # падежи и ошибки распознавания
    ("инвокеру помоги", [("follow", [5], {"ally": 2})], {"last": [5]}),
    ("бейте пуджем", [("focus", ALL, {"enemy": "npc_dota_hero_pudge"})]),
    ("миракал фарми лес", [("farm", [1], {"area": "jungle_own"})]),    # ошибка распознавания
]


class ParserCases(unittest.TestCase):
    def test_cases(self):
        failures = []
        for case in CASES:
            text, expected = case[0], case[1]
            opts = case[2] if len(case) > 2 else {}
            res = parse(text, ctx(**opts))
            got = [(c.action, c.agents, c.params) for c in res.commands]
            ok = len(got) == len(expected)
            if ok:
                for (ga, gag, gp), (ea, eag, ep) in zip(got, expected):
                    if ga != ea or (eag and gag != eag) or any(gp.get(k) != v for k, v in ep.items()):
                        ok = False
                    if not eag and gag:   # ожидали «кому?», а адресат выбран
                        ok = ok and False
            if not ok:
                failures.append(f"{text!r}\n    ждали {expected}\n    вышло {got} unknown={res.unknown}")
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_follow_without_address_uses_last_agents(self):
        res = parse("Мираклу помоги", ctx(last=[3]))
        self.assertEqual(res.commands[0].agents, [3])

    def test_personal_without_address_asks(self):
        res = parse("купи бкб", ctx())
        self.assertEqual(res.commands[0].clarify, "кому?")

    def test_sequence_flag(self):
        res = parse("Миракл фарми лес, потом пушь топ", ctx())
        self.assertFalse(res.commands[0].after_prev)
        self.assertTrue(res.commands[1].after_prev)

    def test_urgent_flag(self):
        res = parse("все назад срочно", ctx())
        self.assertTrue(res.commands[0].urgent)

    def test_unknown_lowers_confidence(self):
        res = parse("Миракл, сделай что-нибудь умное", ctx())
        self.assertLess(res.confidence, 0.5)

    def test_fuzzy_lowers_confidence(self):
        res = parse("миракал фарми лес", ctx())
        self.assertLess(res.confidence, 1.0)

    def test_short_hero_alias_needs_hero_in_match(self):
        # «та» — частица, а не Templar Assassin, если её нет в матче
        res = parse("бейте та", ctx())
        self.assertNotIn("npc_dota_hero_templar_assassin",
                         [c.params.get("enemy") for c in res.commands])

    def test_all_commands_valid(self):
        for case in CASES:
            opts = case[2] if len(case) > 2 else {}
            for c in parse(case[0], ctx(**opts)).commands:
                errs = validate(c)
                self.assertEqual(errs, [], f"{case[0]!r}: {c} → {errs}")

    def test_normalize(self):
        self.assertEqual(normalize("Т-2, на ТОПЕ!!"), ["т2", "|", "на", "топе"])
        self.assertEqual(normalize("ёлки"), ["елки"])


class LexiconData(unittest.TestCase):
    def test_item_ids_exist_in_patch_list(self):
        ids = load_item_ids()
        missing = sorted({v for v in ITEM_PHRASES.values() if v not in ids})
        self.assertEqual(missing, [], "предметы не найдены в списке имён из OHA (патч 7.41)")

    def test_heroes_complete(self):
        heroes = load_heroes()
        self.assertEqual(len(heroes), 127)
        for k, v in heroes.items():
            self.assertTrue(k.startswith("npc_dota_hero_"))
            self.assertTrue(v["aliases"], k)


if __name__ == "__main__":
    unittest.main()


class RegressionParse01(unittest.TestCase):
    """Бывший отложенный набор PARSE-01. После правок по его ошибкам (06.10.2026) он уже не мера
    точности, а регрессия: следит, чтобы выученное не сломалось. Честная мера — новые наборы."""

    def test_parse01_still_learned(self):
        from pathlib import Path
        from tests.eval_heldout import evaluate
        summary, _ = evaluate(Path(__file__).resolve().parent / "heldout_phrases.jsonl", "parse01")
        self.assertGreaterEqual(summary["phrase_ok_share"], 0.95, summary)
