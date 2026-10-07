"""Сухой прогон пробника кастомки (game/probe_addon) под LuaJIT до запуска в игре.

vscripts Dota 2 подменены имитацией — только то, что пробник вызывает (имена сверены с
@moddota/dota-data в test_api_names.py). Сервер тренера — настоящий. Веб-панель клиента
имитирует Python: тот же адрес, что строит probe.js, ответ из <title> («номер|JSON») уходит
серверу кастомки событием vc_probe_title, как в игре.
Проверяется: проход всех стадий без ошибок Lua, строки «[ПРОБНИК] …» и итог, 9 ботов,
приказ «назад» от тренера доходит до ботов, подтверждение «ui_loaded» клиенту.
"""
import html
import json
import re
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
VS = GAME / "probe_addon" / "game" / "scripts" / "vscripts"
sys.path.insert(0, str(GAME.parent / "coach"))

try:
    from lupa import luajit21 as lupa_rt
except ImportError:                      # pragma: no cover
    from lupa import lua51 as lupa_rt

from voicecoach.server import serve  # noqa: E402

MOCK = r"""
DOTA_TEAM_GOODGUYS, DOTA_TEAM_BADGUYS = 2, 3
DOTA_GAMERULES_STATE_HERO_SELECTION, DOTA_GAMERULES_STATE_STRATEGY_TIME = 3, 4
DOTA_GAMERULES_STATE_PRE_GAME, DOTA_GAMERULES_STATE_GAME_IN_PROGRESS = 8, 10
DOTA_UNIT_ORDER_MOVE_TO_POSITION, LUA_MODIFIER_MOTION_NONE = 1, 0
__now, __thinks, __printed, __orders, __said, __sent = 0, {}, {}, {}, {}, {}
print = function(...)
  local t = {}
  for i = 1, select("#", ...) do t[#t + 1] = tostring((select(i, ...))) end
  __printed[#__printed + 1] = table.concat(t, " ")
end

local V = {}
V.__index = V
V.__sub = function(a, b) return Vector(a.x - b.x, a.y - b.y, a.z - b.z) end
function V:Length2D() return math.sqrt(self.x * self.x + self.y * self.y) end
function Vector(x, y, z) return setmetatable({ x = x or 0, y = y or 0, z = z or 0 }, V) end

local gm = {}
function gm:SetContextThink(name, fn, delay) __thinks[#__thinks + 1] = { t = __now + (delay or 0), fn = fn } end
function gm:SetBotThinkingEnabled(on) gm.bots_on = on end
__state = 0
GameRules = {}
function GameRules:GetGameModeEntity() return gm end
function GameRules:State_Get() return __state end
for _, n in ipairs({ "SetCustomGameTeamMaxPlayers", "EnableCustomGameSetupAutoLaunch",
                     "SetCustomGameSetupAutoLaunchDelay", "SetHeroSelectionTime", "SetStrategyTime",
                     "SetShowcaseTime", "SetPreGameTime" }) do
  GameRules[n] = function() end
end
Convars = { SetBool = function() end }

__players = {}
local function make_hero(name, team, pid)
  local h = { name = name, idx = 100 + pid, mods = {},
              pos = (team == 2) and Vector(-6700, -6200, 0) or Vector(6700, 6200, 0) }
  function h:GetAbsOrigin() return self.pos end
  function h:GetUnitName() return self.name end
  function h:GetHealth() return 600 end
  function h:entindex() return self.idx end
  function h:AddNewModifier(caster, ability, mname, data)
    local b = { stack = 0 }
    function b:SetStackCount(n) self.stack = n end
    self.mods[mname] = b
    return b
  end
  return h
end
__players[0] = { team = 2, fake = false, hero = make_hero("npc_dota_hero_pudge", 2, 0) }
PlayerResource = {}
function PlayerResource:IsValidPlayerID(pid) return __players[pid] ~= nil end
function PlayerResource:GetSelectedHeroEntity(pid) return __players[pid] and __players[pid].hero end
function PlayerResource:IsFakeClient(pid) return __players[pid].fake end
function PlayerResource:GetTeam(pid) return __players[pid].team end
function PlayerResource:GetSelectedHeroName(pid) return __players[pid].hero.name end
function PlayerResource:GetPlayer(pid) return __players[pid] and { pid = pid } end
function PlayerResource:GetPlayerCountForTeam(team)
  local n = 0
  for _, p in pairs(__players) do if p.team == team then n = n + 1 end end
  return n
end
Tutorial = { started = false }
function Tutorial:AddBot(hero, lane, difficulty, good)
  local pid = 0
  while __players[pid] do pid = pid + 1 end
  local team = good and 2 or 3
  __players[pid] = { team = team, fake = true, hero = make_hero(hero, team, pid) }
  return true
end
function Tutorial:StartTutorialMode() Tutorial.started = true end
__listeners, __events = {}, {}
CustomGameEventManager = {}
function CustomGameEventManager:RegisterListener(name, fn) __listeners[name] = fn end
function CustomGameEventManager:Send_ServerToPlayer(player, name, data) __sent[#__sent + 1] = { pid = player.pid, name = name } end
function ListenToGameEvent(name, fn, ctx) __events[name] = { fn = fn, ctx = ctx } end
function Dynamic_Wrap(ctx, name) return function(...) return ctx[name](...) end end
function LinkLuaModifier() end
function GetSystemTime() return "12:00:00" end
function GetSystemTimeMS() return __now * 1000 end
function IsInToolsMode() return true end
function IsDedicatedServer() return false end
function ExecuteOrderFromTable(t)
  __orders[#__orders + 1] = t
  for _, p in pairs(__players) do if p.hero.idx == t.UnitIndex then p.hero.pos = t.Position end end
end
function Say(ent, msg, teamOnly) __said[#__said + 1] = msg end
function CreateHTTPRequestScriptVM(method, url)
  local req = { url = url }
  function req:SetHTTPRequestAbsoluteTimeoutMS(ms) self.timeout = ms end
  function req:Send(cb)
    local code, body = __py_get(self.url)
    cb({ StatusCode = code, Body = body })
  end
  return req
end

function __step(dt)
  __now = __now + dt
  local due, rest = {}, {}
  for _, th in ipairs(__thinks) do
    if th.t <= __now then due[#due + 1] = th else rest[#rest + 1] = th end
  end
  __thinks = rest
  for _, th in ipairs(due) do
    local again = th.fn()
    if type(again) == "number" then __thinks[#__thinks + 1] = { t = __now + again, fn = th.fn } end
  end
end
function __set_state(s)
  __state = s
  local e = __events["game_rules_state_change"]
  e.fn(e.ctx, {})
end
"""


def http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode("utf-8")
    except Exception as e:                       # noqa: BLE001
        return 0, str(e)


class ProbeDryRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = serve("127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def setUp(self):
        L = self.L = lupa_rt.LuaRuntime(unpack_returned_tuples=True)
        L.globals()["__py_get"] = http_get
        L.execute(MOCK)
        L.execute(f'package.path = "{VS.as_posix()}/?.lua;" .. package.path')
        L.execute(f'package.preload["vc_json"] = function() return dofile("{(GAME / "shared" / "json.lua").as_posix()}") end')
        L.execute(f'dofile("{(VS / "addon_game_mode.lua").as_posix()}")')
        # адрес сервера тренера — на тестовый порт
        L.execute(f'VoiceCoachProbe.SERVER = "http://127.0.0.1:{self.port}"')
        L.execute("Activate()")

    def step(self, seconds):
        for _ in range(int(seconds * 2)):
            self.L.execute("__step(0.5)")

    def printed(self):
        return list(self.L.globals()["__printed"].values())

    def line(self, name):
        rows = [l for l in self.printed() if re.match(rf"\[ПРОБНИК\] {name}\s", l)]
        self.assertTrue(rows, f"нет строки {name}: {self.printed()}")
        return rows[-1]

    def client_title(self, rid):
        """Что делает probe.js: адрес с fmt=title и rid, ответ из <title> → событие серверу кастомки."""
        url = (f"http://127.0.0.1:{self.port}/api/probe/commands?team=radiant&after=0&fmt=title&rid={rid}")
        code, page = http_get(url)
        self.assertEqual(code, 200)
        title = html.unescape(re.search(r"<title>(.*)</title>", page, re.S).group(1))
        got_rid, data = title.split("|", 1)
        self.assertEqual(got_rid, rid)
        ev = self.L.table_from({"rid": rid, "data": data, "ms": 140})
        self.L.globals()["__listeners"]["vc_probe_title"](0, ev)

    def run_match(self):
        S = self.L.globals()
        self.step(1.5)                                   # проверка HTTP при старте
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_HERO_SELECTION)")
        self.step(4)
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_STRATEGY_TIME)")
        self.step(2)
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_PRE_GAME)")
        self.step(10)
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_GAME_IN_PROGRESS)")
        self.step(95)
        return S

    def test_full_run(self):
        S = self.run_match()
        self.assertIn(" OK ", self.line("lua"))
        self.assertIn(" OK ", self.line("json"))
        self.assertRegex(self.line("server_http"), r" OK .*код 200")
        self.assertRegex(self.line("bots_added"), r" OK .*добавлено 9, всего 9")
        self.assertTrue(S["Tutorial"]["started"])
        self.assertRegex(self.line("heroes"), r" OK\s+10 героев, ботов 9")
        self.assertIn(" OK ", self.line("modifier_on_bots"))
        self.assertIn("#vc проба чата", list(S["__said"].values()))
        self.assertIn(" OK ", self.line("order_vs_native_ai"))       # имитация: приказ исполняется
        self.assertIn(" OK ", self.line("think_cost_ms"))
        self.line("bots_think")
        summary = [l for l in self.printed() if "ИТОГ" in l]
        self.assertGreater(len(summary), 8)
        self.assertTrue(any("html_panel_channel" in l and "НЕТ ответов" in l for l in summary))
        self.assertFalse([l for l in self.printed() if "ошибка в проверке" in l], self.printed())

    def test_retry_bots_only_when_needed(self):
        self.run_match()
        self.assertFalse([l for l in self.printed() if "bots_added_retry" in l])

    def test_voice_command_reaches_bots_through_title(self):
        self.run_match()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/probe/say",
                                     data=json.dumps({"team": "radiant", "text": "все назад"}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            cmds = json.loads(r.read())["commands"]
        self.assertEqual(cmds[0]["action"], "retreat")
        n0 = len(self.L.globals()["__orders"])
        self.client_title("7_123")
        self.assertRegex(self.line("html_panel_channel"), r" OK .*140 мс")
        orders = list(self.L.globals()["__orders"].values())[n0:]
        self.assertEqual(len(orders), 4)                   # 4 бота Света (пятый — человек)
        for o in orders:
            self.assertEqual((o["Position"]["x"], o["Position"]["y"]), (-7000, -6500))
        self.assertTrue(any("retreat → позиции 1,2,3,4,5" in l for l in self.printed()))

    def test_ui_loaded_ack(self):
        lst = self.L.globals()["__listeners"]
        lst["vc_probe_report"](0, self.L.table_from({"key": "ui_loaded", "ok": 1, "detail": "x", "PlayerID": -1}))
        self.assertEqual(len(self.L.globals()["__sent"]), 0)          # слот ещё не назначен — молчим
        lst["vc_probe_report"](0, self.L.table_from({"key": "ui_loaded", "ok": 1, "detail": "x", "PlayerID": 0}))
        sent = list(self.L.globals()["__sent"].values())
        self.assertEqual([(s["pid"], s["name"]) for s in sent], [(0, "vc_probe_ack")])
        self.assertIn(" OK ", self.line("client_ui_loaded"))

    def test_without_server(self):
        self.L.execute('VoiceCoachProbe.SERVER = "http://127.0.0.1:9"')
        self.L.execute("VoiceCoachProbe:CheckHttp()")
        self.assertIn(" НЕТ ", self.line("server_http"))


if __name__ == "__main__":
    unittest.main()
