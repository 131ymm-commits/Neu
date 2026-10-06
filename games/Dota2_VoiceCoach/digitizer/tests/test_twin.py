"""Тесты оцифровки на настоящем матче OpenDota (tests/fixtures/SOURCE.md).
Запуск из папки digitizer/:  python -m unittest -v
Ожидаемые значения считаются вторым способом прямо из сырых полей матча."""
import copy
import json
import unittest
from pathlib import Path

from twin import agent_params, build_profile, estimate_positions, match_features, translit
from twin.opendota import OpenDota, collect_matches, is_parsed

HERE = Path(__file__).resolve().parent
MATCH = json.loads((HERE / "fixtures" / "match_1781962623.json").read_text(encoding="utf-8"))
ACC = 120269134            # слот 0, Tusk


def raw(acc=ACC):
    return next(p for p in MATCH["players"] if p["account_id"] == acc)


class Features(unittest.TestCase):
    def test_player_found_and_basic(self):
        f = match_features(MATCH, ACC)
        p = raw()
        self.assertEqual(f["hero"], "npc_dota_hero_tusk")
        self.assertEqual(f["kills"], p["kills"])
        self.assertEqual(f["apm"], p["actions_per_min"])
        self.assertTrue(f["is_radiant"])

    def test_minute_10(self):
        f, p = match_features(MATCH, ACC), raw()
        i = p["times"].index(600)
        self.assertEqual(f["lh10"], p["lh_t"][i])
        self.assertEqual(f["gold10"], p["gold_t"][i])

    def test_early_kills(self):
        f, p = match_features(MATCH, ACC), raw()
        self.assertEqual(f["early_kills"], len([k for k in p["kills_log"] if k["time"] < 600]))

    def test_unknown_player(self):
        self.assertIsNone(match_features(MATCH, 1))

    def test_action_mix_sums_to_one(self):
        f = match_features(MATCH, ACC)
        self.assertAlmostEqual(sum(f["action_mix"].values()), 1.0, places=3)

    def test_components_not_in_build(self):
        # mystic_staff куплен в ту же секунду, что и sheepstick (компонент рецепта)
        f = match_features(MATCH, ACC)
        self.assertIn("sheepstick", f["core_build"])
        self.assertNotIn("mystic_staff", f["core_build"])

    def test_missing_fields_are_none_not_zero(self):
        m = copy.deepcopy(MATCH)
        p = next(q for q in m["players"] if q["account_id"] == ACC)
        for k in ("purchase_log", "lane_pos", "obs_log", "sen_log", "actions", "kills_log"):
            p.pop(k, None)
        f = match_features(m, ACC)
        self.assertIsNone(f["core_build"])
        self.assertIsNone(f["obs_placed"])
        self.assertIsNone(f["early_kills"])


class Positions(unittest.TestCase):
    def test_radiant_positions(self):
        pos = estimate_positions(MATCH)
        # посчитано вручную по gold_t/lh_t на 10–12-й минуте (алгоритм odota/core):
        # ранги фарма 1:1, 3:3, 2:3, 0:5, 4:8 → коры 1 (лёгкая→1), 3 (мид→2), 2 (лес→3);
        # саппорты: 0 (сложная→4), 4 (лёгкая→5)
        self.assertEqual([pos[s] for s in (0, 1, 2, 3, 4)], [4, 1, 3, 2, 5])

    def test_dire_positions(self):
        pos = estimate_positions(MATCH)
        # ранги фарма 130:0, 132:2, 131:4, 128:6, 129:8 → коры 130 (мид→2), 132 (лёгкая→1),
        # 131 (лёгкая занята → 3); саппорты 128 (сложная→4), 129 (мид→4 занято → 5)
        self.assertEqual([pos[s] for s in (128, 129, 130, 131, 132)], [4, 5, 2, 3, 1])

    def test_position_est_from_api_wins(self):
        m = copy.deepcopy(MATCH)
        for p, est in zip([q for q in m["players"] if q["player_slot"] < 128], [5, 4, 3, 2, 1]):
            p["position_est"] = est
        pos = estimate_positions(m)
        self.assertEqual([pos[s] for s in (0, 1, 2, 3, 4)], [5, 4, 3, 2, 1])

    def test_each_team_has_positions_1_to_5(self):
        pos = estimate_positions(MATCH)
        self.assertEqual(sorted(pos[s] for s in (0, 1, 2, 3, 4)), [1, 2, 3, 4, 5])
        self.assertEqual(sorted(pos[s] for s in (128, 129, 130, 131, 132)), [1, 2, 3, 4, 5])


class Profile(unittest.TestCase):
    def test_profile_from_one_match_warns(self):
        prof = build_profile([MATCH], ACC)
        self.assertEqual(prof["matches_used"], 1)
        self.assertTrue(any("мало матчей" in w for w in prof["warnings"]))
        self.assertEqual(prof["hero_pool"][0]["hero"], "npc_dota_hero_tusk")
        for k, v in prof["style"].items():
            self.assertTrue(v is None or 0.0 <= v <= 1.0, (k, v))

    def test_profile_not_found(self):
        prof = build_profile([MATCH], 1)
        self.assertEqual(prof["matches_used"], 0)

    def test_profile_is_json_serializable(self):
        json.dumps(build_profile([MATCH, MATCH], ACC), ensure_ascii=False)


class AgentParams(unittest.TestCase):
    def test_ranges(self):
        a = agent_params(build_profile([MATCH], ACC))
        b = a["behavior"]
        self.assertTrue(0.2 <= b["retreat_hp"] <= 0.45)
        for v in b["desire_bonus"].values():
            self.assertTrue(-0.2 <= v <= 0.2)
        self.assertTrue(150 <= b["reaction_ms"] <= 350)
        self.assertEqual(a["hero"], "npc_dota_hero_tusk")

    def test_translit(self):
        self.assertEqual(translit("Topson"), "топсон")
        self.assertEqual(translit("Miracle-"), "миракл")
        self.assertEqual(translit("Collapse"), "коллапс")


class Client(unittest.TestCase):
    def test_collect_with_fake_fetch(self):
        unparsed = {"match_id": 2, "players": [{"account_id": ACC, "hero_id": 1}]}

        def fetch(method, url):
            if url.endswith(f"/players/{ACC}/matches?limit=2"):
                return [{"match_id": 1781962623}, {"match_id": 2}]
            if "/matches/1781962623" in url:
                return MATCH
            if "/matches/2" in url:
                return unparsed
            if "/request/2" in url and method == "POST":
                return {"job": {"jobId": 1}}
            raise AssertionError(url)

        logs = []
        api = OpenDota(cache_dir=None, fetch=fetch)
        ms = collect_matches(api, ACC, limit=2, request_missing=True, log=logs.append)
        self.assertEqual(len(ms), 2)
        self.assertTrue(is_parsed(ms[0]))
        self.assertFalse(is_parsed(ms[1]))
        self.assertTrue(any("разобрано: 1" in l for l in logs))


class TablesAgree(unittest.TestCase):
    def test_hero_names_match_voice_lexicon(self):
        here = Path(__file__).resolve().parents[2]
        coach = json.loads((here / "coach" / "data" / "heroes.json").read_text(encoding="utf-8"))
        twin = json.loads((here / "digitizer" / "data" / "heroes_by_id.json").read_text(encoding="utf-8"))
        self.assertEqual(set(coach), {v["name"] for v in twin.values()})


if __name__ == "__main__":
    unittest.main()
