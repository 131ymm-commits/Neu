"""Модуль тренера для ботов OHA (game/prototype_oha/coach/coach_bot.lua) под LuaJIT.

API ботов Valve подменён имитацией (только то, что модуль вызывает; имена функций сверены
по коду OHA, коммит cb814c6). HTTP идёт в настоящий сервер тренера (urllib из Python).
Проверяется: опрос одним ботом команды, сдвиг желаний режимов, ответы в чат и на сервер,
покупка в очередь OHA, байбэк, доклад, работа без сервера.
"""
import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(GAME.parent / "coach"))

try:
    from lupa import luajit21 as lupa_rt
except ImportError:                      # pragma: no cover
    from lupa import lua51 as lupa_rt

from voicecoach.server import serve  # noqa: E402

MOCK_API = r"""
TEAM_RADIANT, TEAM_DIRE = 2, 3
__T = 0
function GameTime() return __T end
function DotaTime() return __T - 90 end
function GetScriptDirectory() return "bots" end
__players = { [TEAM_RADIANT] = {0, 1, 2, 3, 4}, [TEAM_DIRE] = {5, 6, 7, 8, 9} }
__heroes = {}
function GetTeamPlayers(team) return __players[team] end
function GetSelectedHeroName(pid) return __heroes[pid] or "" end
__bots, __cur = {}, nil
function GetBot() return __cur end
function GetTeam() return __cur.team end
__http_calls = 0
function CreateRemoteHTTPRequest(url)
  return { Send = function(self, cb) __http_calls = __http_calls + 1; py_http(url, cb) end }
end
function make_bot(pid, team)
  local b = { pid = pid, team = team, alive = true, gold = 600, buyback = true, chat = {},
              bought_back = false, purchaseListInReverseOrder = {} }
  function b:GetPlayerID() return self.pid end
  function b:GetUnitName() return "npc_dota_hero_test" end
  function b:IsAlive() return self.alive end
  function b:GetGold() return self.gold end
  function b:GetHealth() return 500 end
  function b:GetMaxHealth() return 1000 end
  function b:GetMana() return 100 end
  function b:GetMaxMana() return 400 end
  function b:HasBuyback() return self.buyback end
  function b:ActionImmediate_Buyback() self.bought_back = true end
  function b:ActionImmediate_Chat(text, all) table.insert(self.chat, text) end
  __bots[pid] = b
  return b
end
"""


class CoachBot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = serve("127.0.0.1", 0)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        # раскладка как в Доте: vscripts/bots/coach/*.lua
        self.tmp = Path(tempfile.mkdtemp())
        coach = self.tmp / "bots" / "coach"
        coach.mkdir(parents=True)
        shutil.copy(GAME / "prototype_oha" / "coach" / "coach_bot.lua", coach)
        shutil.copy(GAME / "shared" / "coach_intents.lua", coach)
        shutil.copy(GAME / "shared" / "json.lua", coach)
        self.room = f"bot{id(self)}"
        self.base = f"http://127.0.0.1:{self.port}"
        (coach / "coach_config.lua").write_text(
            f'return {{ base_url = "{self.base}", room = "{self.room}", poll_interval = 0.5,\n'
            '  personas = { [2] = { [1] = { obedience = 1, desire_bonus = { fight = 0.1 } } } } }\n',
            encoding="utf-8")
        self.L = lupa_rt.LuaRuntime(unpack_returned_tuples=True)
        self.L.globals().py_http = self.py_http
        self.L.execute(MOCK_API)
        self.L.execute(f'package.path = "{self.tmp.as_posix()}/?.lua;" .. package.path')
        self.bots = {pid: self.L.eval(f"make_bot({pid}, {2 if pid < 5 else 3})") for pid in range(10)}
        self.M = self.L.eval('require("bots/coach/coach_bot")')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def py_http(self, url, cb):
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                cb(r.read().decode("utf-8"))      # в API ботов ответ — строка (как читает OHA)
        except (urllib.error.URLError, OSError):
            cb(None)

    def say(self, text, team="radiant"):
        req = urllib.request.Request(f"{self.base}/api/{self.room}/say", method="POST",
                                     data=json.dumps({"team": team, "text": text}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    def at(self, t):
        self.L.globals()["__T"] = t

    def desire(self, pid, mode, base):
        self.L.globals()["__cur"] = self.bots[pid]
        return self.M.desire(mode, base)

    def tick_all(self, mode="farm", base=0.2):
        out = {}
        for pid in range(10):
            out[pid] = self.desire(pid, mode, base)
        return out

    def events(self, team="radiant"):
        with urllib.request.urlopen(f"{self.base}/api/{self.room}/events?team={team}&after=0", timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))["events"]

    def test_roshan_order_raises_desire_of_addressed_only(self):
        self.at(100)
        self.tick_all()                                    # первый опрос: команд нет
        self.say("все на роша")
        self.at(101)
        self.tick_all()                                    # опрос забирает команду
        self.at(101.1)
        d = self.tick_all("roshan", 0.1)
        for pid in range(5):
            self.assertGreaterEqual(d[pid], 0.9, pid)
        for pid in range(5, 10):
            self.assertAlmostEqual(d[pid], 0.1, msg=pid)   # чужая команда не тронута

    def test_one_poller_per_team(self):
        self.at(100)
        before = self.L.globals()["__http_calls"]
        self.tick_all()
        polls = self.L.globals()["__http_calls"] - before
        # по одному опросу на команду (+ одна отправка состава от каждой команды)
        self.assertLessEqual(polls, 4)

    def test_ack_in_chat_and_on_server(self):
        self.at(100)
        self.tick_all()
        self.say("все на роша")
        self.at(101)
        self.tick_all()
        self.at(101.2)
        self.tick_all()
        chat = list(self.bots[0].chat.values())
        self.assertIn("Иду на Рошана", chat)
        texts = [e["text"] for e in self.events()]
        self.assertIn("Иду на Рошана", texts)

    def test_buy_goes_to_oha_purchase_stack(self):
        self.at(100)
        self.tick_all()
        self.say("позиция 1 купи бкб")
        self.at(101)
        self.tick_all()
        self.at(101.2)
        self.tick_all()
        stack = list(self.bots[0].purchaseListInReverseOrder.values())
        self.assertEqual(stack[-1], "item_black_king_bar")

    def test_buyback_when_dead(self):
        self.bots[1].alive = False
        self.at(100)
        self.tick_all()
        self.say("позиция 2 бб")
        self.at(101)
        self.tick_all()
        self.at(101.2)
        self.tick_all()
        self.assertTrue(self.bots[1].bought_back)

    def test_report_answers_with_status(self):
        self.at(100)
        self.tick_all()
        self.say("доклад")
        self.at(101)
        self.tick_all()
        self.at(101.2)
        self.tick_all()
        texts = [e["text"] for e in self.events()]
        self.assertTrue(any("Здоровье 50%" in t for t in texts), texts)

    def test_persona_bonus_applies_without_orders(self):
        self.at(100)
        self.assertAlmostEqual(self.desire(0, "attack", 0.4), 0.5)

    def test_server_down_returns_base(self):
        coach = self.tmp / "bots" / "coach"
        (coach / "coach_config.lua").write_text('return { base_url = "http://127.0.0.1:9", room = "x" }\n',
                                                encoding="utf-8")
        self.L.execute('package.loaded["bots/coach/coach_bot"] = nil; package.loaded["bots/coach/coach_config"] = nil')
        self.M = self.L.eval('require("bots/coach/coach_bot")')
        self.at(100)
        d = self.tick_all("roshan", 0.3)
        self.assertTrue(all(abs(v - 0.3) < 1e-9 for v in d.values()))


if __name__ == "__main__":
    unittest.main()
