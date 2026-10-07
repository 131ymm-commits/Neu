"""Каркас кастомки (game/custom_game) — сухой прогон матча под LuaJIT до запуска в игре.

vscripts Доты подменены имитацией (только то, что каркас вызывает; имена сверены с @moddota/dota-data
в test_api_names.py): вышки трёх уровней на трёх линиях у обеих команд, фонтаны, Рошан, герои со
способностями. Проверяется весь путь: тренер в команде, по 5 ботов, герой тренера спрятан, приказы
из поля HUD и из чата → намерения → приказы героям (и их повтор), ответы агентов, состояние в HUD.
"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
VS = GAME / "custom_game" / "game" / "scripts" / "vscripts"

try:
    from lupa import luajit21 as lupa_rt
except ImportError:                      # pragma: no cover
    from lupa import lua51 as lupa_rt

MOCK = r"""
DOTA_TEAM_GOODGUYS, DOTA_TEAM_BADGUYS = 2, 3
DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP, DOTA_GAMERULES_STATE_HERO_SELECTION = 2, 3
DOTA_GAMERULES_STATE_PRE_GAME, DOTA_GAMERULES_STATE_GAME_IN_PROGRESS = 8, 10
DOTA_UNIT_ORDER_MOVE_TO_POSITION, DOTA_UNIT_ORDER_ATTACK_MOVE, DOTA_UNIT_ORDER_ATTACK_TARGET = 1, 3, 4
DOTA_UNIT_ORDER_CAST_POSITION, DOTA_UNIT_ORDER_CAST_TARGET, DOTA_UNIT_ORDER_CAST_NO_TARGET = 5, 6, 8
DOTA_UNIT_ORDER_HOLD_POSITION = 10
ABILITY_TYPE_ULTIMATE = 1
DOTA_ABILITY_BEHAVIOR_NO_TARGET, DOTA_ABILITY_BEHAVIOR_UNIT_TARGET, DOTA_ABILITY_BEHAVIOR_POINT = 4, 8, 16
LUA_MODIFIER_MOTION_NONE = 0
__now, __thinks, __printed, __orders, __said, __to_player, __to_team, __assign = 0, {}, {}, {}, {}, {}, {}, {}
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

__next_idx = 1000
local function ent(fields)
  __next_idx = __next_idx + 1
  local e = fields or {}
  e.idx = __next_idx
  e.alive = e.alive ~= false
  function e:entindex() return self.idx end
  function e:GetAbsOrigin() return self.pos end
  function e:GetTeamNumber() return self.team end
  function e:GetUnitName() return self.name end
  function e:IsAlive() return self.alive end
  return e
end
function IsValidEntity(e) return e ~= nil end

-- карта: фонтаны, вышки (3 линии × 3 уровня × 2 команды), Рошан
__fountains = { ent({ team = 2, pos = Vector(-7000, -6500, 0) }), ent({ team = 3, pos = Vector(7000, 6400, 0) }) }
__towers = {}
local LANE_POS = {
  [2] = { top = { Vector(-6200, 1800, 0), Vector(-6100, -800, 0), Vector(-6600, -3400, 0) },
          mid = { Vector(-1500, -1400, 0), Vector(-3500, -2800, 0), Vector(-4600, -4100, 0) },
          bot = { Vector(4900, -6100, 0), Vector(-400, -6200, 0), Vector(-3900, -6100, 0) } },
  [3] = { top = { Vector(-4700, 6000, 0), Vector(0, 6000, 0), Vector(3500, 5800, 0) },
          mid = { Vector(500, 650, 0), Vector(2500, 2100, 0), Vector(4200, 3700, 0) },
          bot = { Vector(6200, -1600, 0), Vector(6300, 400, 0), Vector(6300, 3000, 0) } },
}
for team, lanes in pairs(LANE_POS) do
  for lane, list in pairs(lanes) do
    for tier, p in ipairs(list) do
      local side = team == 2 and "goodguys" or "badguys"
      __towers[#__towers + 1] = ent({ team = team, pos = p, name = "npc_dota_" .. side .. "_tower" .. tier .. "_" .. lane })
    end
  end
end
__roshan = ent({ team = 4, pos = Vector(-2800, 2300, 0), name = "npc_dota_roshan" })
Entities = {}
function Entities:FindAllByClassname(cls)
  if cls == "ent_dota_fountain" then return __fountains end
  if cls == "npc_dota_tower" then return __towers end
  return {}
end
function Entities:FindByClassname(prev, cls)
  if cls == "npc_dota_roshan" and prev == nil then return __roshan end
  return nil
end

-- герои
__players = {}
local function make_ability(ult)
  local ab = ent({ ult = ult, level = 1, ready = true, behavior = 8 })
  function ab:GetAbilityType() return self.ult and ABILITY_TYPE_ULTIMATE or 0 end
  function ab:GetLevel() return self.level end
  function ab:GetBehaviorInt() return self.behavior end
  function ab:IsFullyCastable() return self.ready end
  function ab:GetCooldownTimeRemaining() return self.ready and 0 or 42 end
  return ab
end
local function make_hero(name, team, pid)
  local h = ent({ team = team, name = name, pid = pid, mods = {}, items = {}, gold = 900, hp = 100,
                  pos = (team == 2) and Vector(-6700, -6200, 0) or Vector(6700, 6200, 0) })
  h.abilities = { make_ability(false), make_ability(false), make_ability(false), make_ability(false),
                  make_ability(false), make_ability(true) }
  function h:IsRealHero() return true end
  function h:GetPlayerOwnerID() return self.pid end
  function h:GetPlayerID() return self.pid end
  function h:AddNoDraw() self.nodraw = true end
  function h:AddNewModifier(caster, ability, mname, data) self.mods[mname] = true return {} end
  function h:GetHealthPercent() return self.hp end
  function h:GetBuybackCost() return 500 end
  function h:GetTimeUntilRespawn() return 17 end
  function h:CanEntityBeSeenByMyTeam(unit) return true end
  function h:GetAbilityCount() return #self.abilities end
  function h:GetAbilityByIndex(i) return self.abilities[i + 1] end
  function h:FindItemInInventory(n) return self.items[n] end
  function h:Buyback() self.alive = true; self.bought_back = true end
  return h
end
__players[0] = { team = 2, fake = false, hero = make_hero("npc_dota_hero_pudge", 2, 0) }
PlayerResource = {}
function PlayerResource:IsValidPlayerID(pid) return __players[pid] ~= nil end
function PlayerResource:IsFakeClient(pid) return __players[pid].fake end
function PlayerResource:GetTeam(pid) return __players[pid].team end
function PlayerResource:GetSelectedHeroName(pid) return __players[pid].hero.name end
function PlayerResource:GetSelectedHeroEntity(pid) return __players[pid] and __players[pid].hero end
function PlayerResource:GetPlayer(pid) return __players[pid] and { pid = pid } end
function PlayerResource:GetGold(pid) return __players[pid].hero.gold end
function PlayerResource:SetCustomTeamAssignment(pid, team) __assign[pid] = team; __players[pid].team = team end
Tutorial = { started = false }
function Tutorial:AddBot(hero, lane, difficulty, good)
  local pid = 0
  while __players[pid] do pid = pid + 1 end
  local team = good and 2 or 3
  __players[pid] = { team = team, fake = true, hero = make_hero(hero, team, pid) }
  return true
end
function Tutorial:StartTutorialMode() Tutorial.started = true end

local gm = {}
function gm:SetContextThink(name, fn, delay) __thinks[#__thinks + 1] = { t = __now + (delay or 0), fn = fn } end
function gm:SetBotThinkingEnabled(on) gm.bots_on = on end
function gm:SetCameraDistanceOverride(d) gm.camera = d end
__gm = gm
__state = 0
GameRules = {}
function GameRules:GetGameModeEntity() return gm end
function GameRules:State_Get() return __state end
function GameRules:GetGameTime() return __now end
for _, n in ipairs({ "SetCustomGameTeamMaxPlayers", "EnableCustomGameSetupAutoLaunch", "SetCustomGameSetupAutoLaunchDelay",
                     "SetHeroSelectionTime", "SetStrategyTime", "SetShowcaseTime", "SetPreGameTime" }) do
  GameRules[n] = function() end
end
Convars = { SetBool = function() end }
__listeners, __events = {}, {}
CustomGameEventManager = {}
function CustomGameEventManager:RegisterListener(name, fn) __listeners[name] = fn end
function CustomGameEventManager:Send_ServerToPlayer(player, name, data) __to_player[#__to_player + 1] = { pid = player.pid, name = name, data = data } end
function CustomGameEventManager:Send_ServerToTeam(team, name, data) __to_team[#__to_team + 1] = { team = team, name = name, data = data } end
function ListenToGameEvent(name, fn, ctx) __events[name] = { fn = fn, ctx = ctx } end
function Dynamic_Wrap(ctx, name) return function(...) return ctx[name](...) end end
function LinkLuaModifier() end
function EntIndexToHScript(idx)
  for _, p in pairs(__players) do if p.hero.idx == idx then return p.hero end end
  return nil
end
function FindClearSpaceForUnit(unit, pos, grid) unit.pos = pos end
function ExecuteOrderFromTable(t) __orders[#__orders + 1] = t end
function Say(ent, msg, teamOnly) __said[#__said + 1] = msg end

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
function __fire(name, data)
  local e = __events[name]
  e.fn(e.ctx, data)
end
"""

ORDER = {"move": 1, "attack_move": 3, "attack": 4, "cast_target": 6, "hold": 10}


class CustomGame(unittest.TestCase):
    def setUp(self):
        L = self.L = lupa_rt.LuaRuntime(unpack_returned_tuples=True)
        L.execute(MOCK)
        L.execute(f'package.path = "{VS.as_posix()}/?.lua;" .. package.path')
        for mod, src in {"vc_intents": "coach_intents.lua", "vc_voice": "coach_voice.lua",
                         "vc_text": "coach_text.lua", "vc_text_data": "coach_text_data.lua"}.items():
            L.execute(f'package.preload["{mod}"] = function() return dofile("{(GAME / "shared" / src).as_posix()}") end')
        L.execute(f'dofile("{(VS / "addon_game_mode.lua").as_posix()}")')
        L.execute("Activate()")
        self.G = L.globals()

    def step(self, seconds):
        for _ in range(int(round(seconds / 0.25))):
            self.L.execute("__step(0.25)")

    def start_match(self):
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP)")
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_HERO_SELECTION)")
        self.step(2.5)
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_PRE_GAME)")
        for pid in list(self.G["__players"].keys()):
            self.L.execute(f"__fire('npc_spawned', {{ entindex = __players[{pid}].hero.idx, is_respawn = 0 }})")
        self.step(1.5)

    def hud(self, text, pid=0):
        self.G["__listeners"]["vc_command"](0, self.L.table_from({"PlayerID": pid, "text": text}))

    def orders(self, since=0):
        return list(self.G["__orders"].values())[since:]

    def n_orders(self):
        return len(self.G["__orders"])

    def hero(self, pid):
        return self.G["__players"][pid]["hero"]

    def replies(self):
        return [dict(e["data"]) for e in self.G["__to_player"].values() if e["name"] == "vc_reply"]

    def test_setup(self):
        self.start_match()
        self.assertEqual(dict(self.G["__assign"]), {0: 2})                     # тренер — за Свет
        bots = [p for p in self.G["__players"].values() if p["fake"]]
        self.assertEqual(len(bots), 10)
        self.assertTrue(self.G["Tutorial"]["started"])
        human = self.hero(0)
        self.assertTrue(human["nodraw"])
        self.assertIn("modifier_voicecoach_commander", list(human["mods"].keys()))
        self.assertEqual(self.G["__gm"]["camera"], 1600)
        log = [l for l in self.G["__printed"].values() if "карта:" in l]
        self.assertTrue(log and "вышек 18" in log[0] and "Свет 5, Тьма 5" in log[0], log)
        agents = [e for e in self.G["__to_team"].values() if e["name"] == "vc_agents" and e["team"] == 2]
        self.assertTrue(agents)
        rows = list(agents[-1]["data"]["agents"].values())
        self.assertEqual([r["pos"] for r in rows], [1, 2, 3, 4, 5])
        self.assertEqual(rows[0]["hero"], "sniper")
        self.assertEqual(rows[0]["status"], "играет сам")

    def test_retreat_all_and_refresh(self):
        self.start_match()
        n0 = self.n_orders()
        self.hud("все назад")
        self.step(0.5)
        first = self.orders(n0)
        self.assertEqual(len(first), 5)
        self.assertTrue(all(o["OrderType"] == ORDER["move"] for o in first))
        self.assertTrue(all((o["Position"]["x"], o["Position"]["y"]) == (-7000, -6500) for o in first))
        n1 = self.n_orders()
        self.step(1.0)
        self.assertEqual(len(self.orders(n1)), 5)                              # приказ повторяется
        acks = [r for r in self.replies() if r["kind"] == "ack"]
        self.assertEqual(len(acks), 5)
        self.assertTrue(all(r["text"] for r in acks))

    def test_push_defend_roshan_ult(self):
        self.start_match()
        n0 = self.n_orders()
        self.hud("1 пуш топ. 23 деф мид. 45 рош")
        self.step(0.5)
        by_unit = {o["UnitIndex"]: o for o in self.orders(n0)}
        a = {pos: self.hero(pos)["idx"] for pos in range(1, 6)}               # боты Света — pid 1..5
        self.assertEqual(by_unit[a[1]]["OrderType"], ORDER["attack_move"])
        self.assertEqual((by_unit[a[1]]["Position"]["x"], by_unit[a[1]]["Position"]["y"]), (-4700, 6000))  # Т1 топ Тьмы
        for pos in (2, 3):
            self.assertEqual((by_unit[a[pos]]["Position"]["x"], by_unit[a[pos]]["Position"]["y"]), (-1500, -1400))
        for pos in (4, 5):
            self.assertEqual(by_unit[a[pos]]["OrderType"], ORDER["attack"])
            self.assertEqual(by_unit[a[pos]]["TargetIndex"], self.G["__roshan"]["idx"])
        n1 = self.n_orders()
        self.hud("3 ульт луна !")
        self.step(0.5)
        casts = [o for o in self.orders(n1) if o["OrderType"] == ORDER["cast_target"]]
        self.assertEqual(len(casts), 1)
        luna = next(p["hero"] for p in self.G["__players"].values() if p["hero"]["name"] == "npc_dota_hero_luna")
        self.assertEqual(casts[0]["TargetIndex"], luna["idx"])
        self.assertEqual(casts[0]["AbilityIndex"], self.hero(3)["abilities"][6]["idx"])

    def test_tower_falls_front_moves(self):
        self.start_match()
        t1 = next(t for t in self.G["__towers"].values() if t["name"] == "npc_dota_badguys_tower1_top")
        t1["alive"] = False
        n0 = self.n_orders()
        self.hud("1 пуш топ")
        self.step(0.5)
        o = self.orders(n0)[0]
        self.assertEqual((o["Position"]["x"], o["Position"]["y"]), (0, 6000))  # следующая — Т2

    def test_free_releases_agents(self):
        self.start_match()
        self.hud("все назад")
        self.step(0.5)
        self.hud("сам")
        self.step(0.5)
        n0 = self.n_orders()
        self.step(3.0)
        self.assertEqual(self.orders(n0), [])

    def test_errors_and_chat(self):
        self.start_match()
        self.hud("2 летай")
        errs = [r for r in self.replies() if r["kind"] == "error"]
        self.assertEqual(len(errs), 1)
        self.assertIn("летай", errs[0]["text"])
        n0 = self.n_orders()
        self.L.execute("__fire('player_chat', { playerid = 0, text = 'все рош', teamonly = 1 })")
        self.L.execute("__fire('player_chat', { playerid = 0, text = 'gg', teamonly = 1 })")
        self.step(0.5)
        self.assertEqual(len([o for o in self.orders(n0) if o["OrderType"] == ORDER["attack"]]), 5)
        self.assertEqual(len([r for r in self.replies() if r["kind"] == "error"]), 1)   # «gg» — молча

    def test_enemy_team_without_commander_untouched(self):
        self.start_match()
        n0 = self.n_orders()
        self.hud("все назад")
        self.step(1.0)
        dire = {self.hero(pid)["idx"] for pid in range(6, 11)}
        self.assertFalse([o for o in self.orders(n0) if o["UnitIndex"] in dire])

    def test_report_and_status_in_hud(self):
        self.start_match()
        self.hud("2 пуш бот")
        self.step(1.5)
        self.hud("все доклад")
        reports = [r for r in self.replies() if r["kind"] == "report"]
        self.assertEqual(len(reports), 5)
        self.assertTrue(any("пуш бот" in r["text"] for r in reports), reports)
        agents = [e for e in self.G["__to_team"].values() if e["name"] == "vc_agents" and e["team"] == 2]
        row2 = [r for r in agents[-1]["data"]["agents"].values() if r["pos"] == 2][0]
        self.assertEqual(row2["status"], "пуш бот")

    def test_ready_handshake(self):
        self.start_match()
        self.G["__listeners"]["vc_ready"](0, self.L.table_from({"PlayerID": 0}))
        acks = [e for e in self.G["__to_player"].values() if e["name"] == "vc_ack"]
        self.assertEqual(len(acks), 1)
        self.assertEqual(acks[0]["data"]["camera"], 1600)


if __name__ == "__main__":
    unittest.main()
