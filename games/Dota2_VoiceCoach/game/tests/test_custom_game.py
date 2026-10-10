"""Кастомка (game/custom_game): героев ведут агенты Claude (Д11) — сухой прогон матча под LuaJIT до игры.

vscripts Доты подменены имитацией (только то, что кастомка вызывает; имена сверены с @moddota/dota-data
в test_api_names.py): вышки трёх уровней на трёх линиях у обеих команд, фонтаны, Рошан, крипы, герои со
способностями и предметами, магазин у фонтана. HTTP игры к серверу агентов идёт в настоящий сервер тренера
(coach/voicecoach/server.py) с мотором «правила» — путь «наблюдение → агент → решение → приказы героям» тот же,
что с Claude; сам Claude здесь не вызывается. Без сервера — запасной исполнитель приказов тренера.
"""
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
ROOT = GAME.parent
VS = GAME / "custom_game" / "game" / "scripts" / "vscripts"
sys.path.insert(0, str(ROOT / "coach"))

from voicecoach import agents as A  # noqa: E402
from voicecoach.server import serve  # noqa: E402

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
DOTA_UNIT_ORDER_HOLD_POSITION, DOTA_UNIT_ORDER_TRAIN_ABILITY = 10, 11
ABILITY_TYPE_ULTIMATE, ABILITY_CAN_BE_UPGRADED = 1, 0
DOTA_ABILITY_BEHAVIOR_NO_TARGET, DOTA_ABILITY_BEHAVIOR_UNIT_TARGET, DOTA_ABILITY_BEHAVIOR_POINT = 4, 8, 16
DOTA_UNIT_TARGET_TEAM_FRIENDLY, DOTA_UNIT_TARGET_TEAM_ENEMY, DOTA_UNIT_TARGET_BASIC = 1, 2, 18
DOTA_UNIT_TARGET_FLAG_NONE, FIND_CLOSEST, DOTA_SHOP_HOME, DOTA_ModifyGold_PurchaseItem = 0, 1, 0, 15
DOTA_ITEM_TP_SCROLL, DOTA_ITEM_NEUTRAL_ACTIVE_SLOT = 15, 16
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
local function d2(a, b) return math.sqrt((a.x - b.x) ^ 2 + (a.y - b.y) ^ 2) end

__next_idx = 1000
__ents = {}
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
  function e:GetHealth() return self.health or 100 end
  function e:GetMaxHealth() return self.max_health or 100 end
  function e:GetHealthPercent() return math.floor(100 * self:GetHealth() / self:GetMaxHealth()) end
  function e:IsRealHero() return self.is_hero == true end
  function e:IsTower() return self.is_tower == true end
  __ents[e.idx] = e
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
      __towers[#__towers + 1] = ent({ team = team, pos = p, is_tower = true,
                                      name = "npc_dota_" .. side .. "_tower" .. tier .. "_" .. lane })
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

-- крипы линий
__creeps = {}
function __creep(team, x, y, health, max_health)
  local c = ent({ team = team, pos = Vector(x, y, 0), health = health, max_health = max_health or 550,
                  name = team == 2 and "npc_dota_creep_goodguys_melee" or "npc_dota_creep_badguys_melee" })
  function c:IsCreep() return true end
  function c:IsNeutralUnitType() return false end
  __creeps[#__creeps + 1] = c
  return c
end
function FindUnitsInRadius(team, pos, cache, radius, team_filter, type_filter, flags, order, grow)
  local out = {}
  for _, c in ipairs(__creeps) do
    local enemy = c.team ~= team
    if c.alive and d2(c.pos, pos) <= radius and ((team_filter == DOTA_UNIT_TARGET_TEAM_ENEMY) == enemy) then
      out[#out + 1] = c
    end
  end
  table.sort(out, function(a, b) return d2(a.pos, pos) < d2(b.pos, pos) end)
  return out
end

-- способности и предметы
__costs = { item_tango = 90, item_branches = 50, item_quelling_blade = 100, item_slippers = 140, item_circlet = 155,
            item_faerie_fire = 65, item_gauntlets = 140, item_magic_stick = 200, item_boots = 500, item_bottle = 675,
            item_tpscroll = 100 }
function GetItemCost(name) return __costs[name] or 0 end
local function make_ability(name, ult, behavior, level)
  local ab = ent({ name = name, ult = ult, level = level or 1, ready = true, behavior = behavior or 16,
                   max = ult and 3 or 4, range = 600 })
  function ab:GetAbilityName() return self.name end
  function ab:GetAbilityType() return self.ult and ABILITY_TYPE_ULTIMATE or 0 end
  function ab:GetLevel() return self.level end
  function ab:GetMaxLevel() return self.max end
  function ab:GetBehaviorInt() return self.behavior end
  function ab:IsFullyCastable() return self.ready end
  function ab:IsHidden() return false end
  function ab:IsPassive() return false end
  function ab:GetCooldownTimeRemaining() return self.ready and 0 or 42 end
  function ab:GetManaCost(level) return 50 end
  function ab:GetCastRange(loc, target) return self.range end
  function ab:GetCastPoint() return 0.3 end
  function ab:CanAbilityBeUpgraded() return self.level < self.max end     -- в dota-data — bool
  function ab:GetCurrentCharges() return self.charges or 0 end
  return ab
end
__make_ability = make_ability

-- герои
__players = {}
local function make_hero(name, team, pid)
  local h = ent({ team = team, name = name, pid = pid, mods = {}, slots = {}, gold = 600, health = 600,
                  max_health = 600, points = 0, lvl = 1, is_hero = true, range = 550,
                  pos = (team == 2) and Vector(-6700, -6200, 0) or Vector(6700, 6200, 0) })
  local short = name:gsub("npc_dota_hero_", "")
  h.abilities = { make_ability(short .. "_q", false, 16), make_ability(short .. "_w", false, 8),
                  make_ability(short .. "_e", false, 4), make_ability(short .. "_r", true, 8, 0) }
  function h:GetPlayerOwnerID() return self.pid end
  function h:GetPlayerID() return self.pid end
  function h:AddNoDraw() self.nodraw = true end
  function h:AddNewModifier(caster, ability, mname, data) self.mods[mname] = true return {} end
  function h:GetBuybackCost() return 500 end
  function h:GetBuybackCooldownTime() return 0 end
  function h:GetTimeUntilRespawn() return 17 end
  function h:CanEntityBeSeenByMyTeam(unit) return unit.hidden ~= true end
  function h:GetAbilityCount() return #self.abilities end
  function h:GetAbilityByIndex(i) return self.abilities[i + 1] end
  function h:FindAbilityByName(n)
    for _, ab in ipairs(self.abilities) do if ab.name == n then return ab end end
    return nil
  end
  function h:FindItemInInventory(n)
    for slot = 0, 8 do local it = self.slots[slot]; if it and it.name == n then return it end end
    return nil
  end
  function h:GetItemInSlot(slot) return self.slots[slot] end
  function h:AddItemByName(n)
    for slot = 0, 8 do
      if self.slots[slot] == nil then
        local it = make_ability(n, false, 8, 1)
        self.slots[slot] = it
        return it
      end
    end
    return nil
  end
  function h:IsInRangeOfShop(shop, physical) return d2(self.pos, __fountains[self.team - 1].pos) < 1200 end
  function h:GetAbilityPoints() return self.points end
  function h:GetLevel() return self.lvl end
  function h:GetMana() return 300 end
  function h:GetMaxMana() return 300 end
  function h:GetLastHits() return 0 end
  function h:GetDenies() return 0 end
  function h:GetKills() return 0 end
  function h:GetDeaths() return 0 end
  function h:GetAssists() return 0 end
  function h:GetAttackDamage() return 60 end
  function h:GetAverageTrueAttackDamage(target) return 60 end
  function h:Script_GetAttackRange() return self.range end
  function h:GetIdealSpeed() return 300 end
  function h:IsChanneling() return false end
  function h:Buyback() self.alive = true; self.bought_back = true end
  function h:UpgradeAbility(ab) if self.points > 0 then ab.level = ab.level + 1; self.points = self.points - 1 end end
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
function PlayerResource:SpendGold(pid, cost, reason) __players[pid].hero.gold = __players[pid].hero.gold - cost end
function PlayerResource:SetCustomTeamAssignment(pid, team) __assign[pid] = team; __players[pid].team = team end
function PlayerResource:GetTeamKills(team) return team == 2 and 3 or 5 end
function RandomInt(a, b) return math.random(a, b) end
function Time() return __now end
function GetWorldMinX() return -8288 end
function GetWorldMinY() return -8288 end
function GetWorldMaxX() return 8288 end
function GetWorldMaxY() return 8288 end
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
function GameRules:GetDOTATime(pre, neg) return __now - 90 end
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
function EntIndexToHScript(idx) return __ents[idx] end
function FindClearSpaceForUnit(unit, pos, grid) unit.pos = pos end
function ExecuteOrderFromTable(t) __orders[#__orders + 1] = t end
function Say(ent, msg, teamOnly) __said[#__said + 1] = msg end

-- HTTP: запрос уходит в Python (__py_http — настоящий сервер тренера); без него — «нет связи»
__http_log = {}
function CreateHTTPRequestScriptVM(method, url)
  local req = { method = method, url = url }
  function req:SetHTTPRequestAbsoluteTimeoutMS(ms) self.timeout = ms end
  function req:SetHTTPRequestRawPostBody(ctype, body) self.ctype, self.body = ctype, body end
  function req:Send(cb)
    __http_log[#__http_log + 1] = self.body
    if __py_http == nil then cb({ StatusCode = 0 }) return end
    local code, body = __py_http(self.method, self.url, self.body)
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
function __fire(name, data)
  local e = __events[name]
  e.fn(e.ctx, data)
end
"""

ORDER = {"move": 1, "attack_move": 3, "attack": 4, "cast_point": 5, "cast_target": 6, "cast_none": 8, "hold": 10,
         "train": 11}


class Game(unittest.TestCase):
    """Общая часть: Lua с имитацией Доты, кастомка, по желанию — сервер тренера с агентами-правилами."""
    server = False
    backends = None

    def setUp(self):
        L = self.L = lupa_rt.LuaRuntime(unpack_returned_tuples=True)
        L.execute(MOCK)
        L.execute(f'package.path = "{VS.as_posix()}/?.lua;" .. package.path')
        for mod, src in {"vc_intents": "coach_intents.lua", "vc_text": "coach_text.lua",
                         "vc_text_data": "coach_text_data.lua", "vc_json": "json.lua"}.items():
            L.execute(f'package.preload["{mod}"] = function() return dofile("{(GAME / "shared" / src).as_posix()}") end')
        self.srv = None
        if self.server:
            backends = self.backends or {"radiant": A.RulesBackend(), "dire": A.RulesBackend()}
            self.srv = serve("127.0.0.1", 0, lambda name: A.AgentHub(dict(backends), sync=True))
            threading.Thread(target=self.srv.serve_forever, daemon=True).start()
            port = self.srv.server_address[1]

            self.http_fail = 0                                 # сколько следующих запросов «сорвать»

            def py_http(method, url, body):
                if self.http_fail > 0:
                    self.http_fail -= 1
                    return 0, None
                url = url.replace("http://127.0.0.1:8787", f"http://127.0.0.1:{port}")
                req = urllib.request.Request(url, data=body.encode("utf-8") if body else None, method=method,
                                             headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=5) as r:
                        return r.status, r.read().decode("utf-8")
                except urllib.error.HTTPError as e:
                    return e.code, e.read().decode("utf-8")
            L.globals()["__py_http"] = py_http
        L.execute(f'dofile("{(VS / "addon_game_mode.lua").as_posix()}")')
        L.execute("Activate()")
        self.G = L.globals()

    def tearDown(self):
        if self.srv:
            self.srv.shutdown()
            self.srv.server_close()

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

    def by_name(self, short):
        return next(p["hero"] for p in self.G["__players"].values() if p["hero"]["name"] == "npc_dota_hero_" + short)

    def unit_orders(self, hero, since=0):
        return [o for o in self.orders(since) if o["UnitIndex"] == hero["idx"]]

    def replies(self, kind=None):
        out = [dict(e["data"]) for e in self.G["__to_player"].values() if e["name"] == "vc_reply"]
        return [r for r in out if kind is None or r["kind"] == kind]

    def payloads(self):
        return [json.loads(b) for b in self.G["__http_log"].values() if b]

    def hud_rows(self, team=2):
        ev = [e for e in self.G["__to_team"].values() if e["name"] == "vc_agents" and e["team"] == team][-1]
        return ev["data"]["mode"], [dict(r) for r in ev["data"]["agents"].values()]

    @staticmethod
    def xy(order):
        return (order["Position"]["x"], order["Position"]["y"])


class WithAgents(Game):
    """Сервер тренера с агентами («правила» вместо Claude) — путь тот же, что с Claude."""
    server = True

    def test_setup_without_native_ai(self):
        self.start_match()
        self.assertEqual(dict(self.G["__assign"]), {0: 2})
        self.assertEqual(len([p for p in self.G["__players"].values() if p["fake"]]), 10)
        self.assertIs(self.G["__gm"]["bots_on"], False)                      # встроенный ИИ ботов выключен
        self.assertTrue(self.hero(0)["nodraw"])
        self.assertEqual(self.G["__gm"]["camera"], 1600)
        log = [l for l in self.G["__printed"].values() if "карта:" in l]
        self.assertTrue(log and "вышек 18" in log[0] and "Свет 5, Тьма 5" in log[0], log)

    def test_agents_buy_and_go_to_lanes(self):
        self.start_match()
        self.step(3)
        sent = self.payloads()
        self.assertTrue(sent)
        heroes = sent[-1]["heroes"]
        self.assertEqual(len(heroes), 10)
        o = next(h for h in heroes if h["team"] == "radiant" and h["pos"] == 1)
        for key in ("clock", "hp", "abilities", "items", "enemy_team", "towers", "allies", "missing", "where"):
            self.assertIn(key, o)
        self.assertEqual(o["towers"]["own"], {"top": 1, "mid": 1, "bot": 1})
        self.assertEqual(o["where"], "своя база")
        mode, rows = self.hud_rows()
        self.assertTrue(mode.startswith("агенты на связи"), mode)
        self.assertIn("правила (не Claude)", mode)
        sniper = self.hero(1)
        names = [sniper["slots"][i]["name"] for i in range(9) if sniper["slots"][i] is not None]
        self.assertEqual(names[:2], ["item_tango", "item_quelling_blade"])   # стартовые предметы куплены у фонтана
        self.assertLess(sniper["gold"], 600)
        moves = [o for o in self.unit_orders(sniper) if o["OrderType"] == ORDER["move"]]
        self.assertTrue(moves)
        self.assertEqual(self.xy(moves[-1]), (5550, -3850))                  # середина бот-линии (лёгкая у Света)
        self.assertTrue(all(r["source"] == "agent" for r in rows))

    def test_coach_order_goes_through_agent(self):
        self.start_match()
        self.step(2)
        n0 = self.n_orders()
        self.hud("1 пуш бот")
        echo = self.replies("order")
        self.assertEqual(echo[-1]["text"], "→ 1: 1 пуш бот")
        self.step(2)
        coach = [h for h in self.payloads()[-1]["heroes"] if h["team"] == "radiant" and h["pos"] == 1][0]["coach"]
        self.assertEqual(coach[-1]["text"], "1 пуш бот")
        am = [o for o in self.unit_orders(self.hero(1), n0) if o["OrderType"] == ORDER["attack_move"]]
        self.assertTrue(am)
        self.assertEqual(self.xy(am[-1]), (6200, -1600))                     # Т1 бот Тьмы
        says = self.replies("say")
        self.assertTrue(any(r["pos"] == 1 and "пуш бот" in r["text"] for r in says), says)

    def test_events_reach_agents(self):
        self.start_match()
        self.step(1)
        sniper, luna = self.hero(1), self.by_name("luna")
        sniper["alive"] = False
        self.L.execute(f"__fire('entity_killed', {{ entindex_killed = {sniper['idx']}, entindex_attacker = {luna['idx']} }})")
        self.step(2)
        heroes = self.payloads()[-1]["heroes"]
        get = {(h["team"], h["pos"]): h for h in heroes}
        self.assertIn("тебя убил luna", get[("radiant", 1)]["events"][-1])
        self.assertIn("у нас погиб sniper", get[("radiant", 2)]["events"][-1])
        luna_pos = next(h["pos"] for h in heroes if h["hero"] == "luna")
        self.assertIn("ты убил sniper", get[("dire", luna_pos)]["events"][-1])
        self.assertFalse(get[("radiant", 1)]["alive"])
        self.assertEqual(get[("radiant", 1)]["respawn"], 17)

    def test_agents_talk_to_coach_page(self):
        self.start_match()
        self.step(2)
        self.hud("1 пуш бот")
        self.step(2)
        port = self.srv.server_address[1]
        evs = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/local/events?team=radiant&after=0", timeout=5).read())["events"]
        voice = [e for e in evs if e["kind"] == "voice"]
        self.assertTrue(any(e["pos"] == 1 and "пуш бот" in e["text"] and e["hero_ru"] == "Снайпер" for e in voice), voice)

    def test_applied_reported_and_xy_for_map(self):
        self.start_match()
        self.step(3)
        sent = self.payloads()
        applied = [a for p in sent for a in p.get("applied") or []]
        self.assertTrue(any(a["team"] == "radiant" and a["pos"] == 1 for a in applied))
        self.assertTrue(all(isinstance(a["clock"], (int, float)) for a in applied))
        # сервер считает возраст решения: от наблюдения, по которому агент решал, до начала выполнения
        ages = self.srv.hub.room("local").agents.summary()["teams"]["radiant"]["decision_age_p50_s"]
        self.assertIsNotNone(ages)
        self.assertGreaterEqual(ages, 0)
        o = next(h for h in sent[-1]["heroes"] if h["team"] == "radiant" and h["pos"] == 1)
        self.assertEqual(len(o["xy"]), 2)
        self.assertIn("backpack_free", o)

    def test_console_order_reaches_dire_once(self):
        """Приказ второго тренера с пульта (Д13): через ответ сервера — агентам Тьмы, ровно один раз."""
        self.start_match()
        self.step(2)
        room = self.srv.hub.room("local")
        res = room.remote_order("dire", "все назад")
        self.assertEqual(res["errors"], [])
        self.step(4)
        logs = [l for l in self.G["__printed"].values() if "приказ с пульта" in l]
        self.assertEqual(len(logs), 1, logs)                                # сервер слал, пока игра не подтвердила
        last = self.payloads()[-1]
        self.assertEqual(last["cmd_ack"], res["queued"])
        dire = [h for h in last["heroes"] if h["team"] == "dire"]
        self.assertEqual(len(dire), 5)
        self.assertTrue(all(any(c["text"] == "все назад" for c in h["coach"]) for h in dire))
        self.assertFalse(any(h["coach"] for h in last["heroes"] if h["team"] == "radiant"))
        self.assertEqual(room.agents.agents[("dire", 1)].decision["plan"], "retreat")
        evs = room.events_after("dire", 0, 0)                               # ответ игры — на пульт Тьмы
        self.assertTrue(any(e["kind"] == "order" and "все назад" in e["text"] for e in evs), evs)
        self.assertFalse(any("все назад" in e["text"] for e in room.events_after("radiant", 0, 0)))
        m = last["map"]
        self.assertEqual(len(m["towers"]), 18)
        self.assertEqual((m["fountains"]["dire"], m["bounds"], m["score"]),
                         ([7000, 6400], [-8288, -8288, 8288, 8288], {"radiant": 3, "dire": 5}))
        self.assertTrue(all(t["alive"] for t in m["towers"]))
        bad = room.remote_order("dire", "1 летать")                          # не понял — в игру не уходит
        self.assertTrue(bad["errors"])
        self.assertNotIn("queued", bad)

    def test_console_link_survives_failures_and_new_match(self):
        """Ответы игры для пульта не теряются при сорванном обмене; сбой схемы карты не срывает обмен;
        приказ с пульта из прошлого матча в новый не уходит (номер матча game_id)."""
        self.start_match()
        self.step(2)
        room = self.srv.hub.room("local")
        game = self.payloads()[-1]["game_id"]
        self.assertTrue(game)
        self.L.execute('CoachGame:Reply(CoachGame.teams[DOTA_TEAM_BADGUYS], 0, "order", "проверка связи", "")')
        self.http_fail = 1
        self.step(1.25)
        self.assertFalse(any(e["text"] == "проверка связи" for e in room.events_after("dire", 0, 0)))
        self.step(12)                                                       # повтор после паузы связи
        got = [e for e in room.events_after("dire", 0, 0) if e["text"] == "проверка связи"]
        self.assertEqual(len(got), 1)
        self.L.execute('CoachGame.MapInfo = function() error("сломалась схема") end')
        n = len(self.payloads())
        self.step(2)
        self.assertGreater(len(self.payloads()), n)
        self.assertNotIn("map", self.payloads()[-1])
        res = room.remote_order("dire", "все назад")
        self.assertEqual(res["errors"], [])
        self.assertEqual(room.remote[-1]["game"], game)
        fresh = dict(self.payloads()[-1], game_id="другой матч", cmd_run=None, cmd_ack=0)
        self.assertEqual(room.remote_for_game(fresh, None), [])               # новый матч приказ не получит

    def test_lua_observation_passes_python_checks(self):
        self.start_match()
        self.step(2)
        for o in self.payloads()[-1]["heroes"]:
            d, notes = A.parse_decision(A.rules_decision(o), o)
            self.assertIsNotNone(d)
            self.assertEqual(notes, [], (o["hero"], notes))


class Broken(A.RulesBackend):
    label = "сломанный мотор"
    free = False

    def decide(self, *a, **k):
        raise A.BackendError("HTTP 401: нет ключа")


class AgentsFailing(Game):
    """Сервер на связи, но мотор отвечает ошибкой: герои не стоят, приказы тренера выполняет запасной."""
    server = True
    backends = {"radiant": Broken(), "dire": A.RulesBackend()}

    def test_fallback_when_no_decisions(self):
        self.start_match()
        self.step(2)
        mode, rows = self.hud_rows()
        self.assertIn("без решений агента: 5", mode)
        n0 = self.n_orders()
        self.hud("все назад !")
        self.step(0.5)
        for pos in range(1, 6):
            o = self.unit_orders(self.hero(pos), n0)[-1]
            self.assertEqual((o["OrderType"], self.xy(o)), (ORDER["move"], (-7000, -6500)))
        self.assertIn("без агента: 1,2,3,4,5", self.replies("order")[-1]["text"])
        self.assertTrue(all(r["source"] == "fallback" for r in rows))
        self.assertTrue(rows[0]["agent"].startswith("ошибка"), rows[0])


class Executor(Game):
    """Исполнитель решений: рефлексы на имитации, решения подаются прямо (как из ответа сервера)."""

    def decide(self, team, pos, decision, seq=None):
        T = self.G["CoachGame"]["teams"][team]
        seq = seq or (T["dec_seq"][pos] + 1)
        data = {"decisions": [{"team": "radiant" if team == 2 else "dire", "pos": pos, "seq": seq,
                               "decision": decision}]}
        self.G["CoachGame"]["OnAgents"](self.G["CoachGame"], self.lua(data))
        self.G["CoachGame"]["link"]["last_ok"] = self.G["__now"]          # связь «есть»: запасной не вмешивается
        self.G["CoachGame"]["link"]["stale"] = 1e9

    def lua(self, v):
        if isinstance(v, dict):
            return self.L.table_from({k: self.lua(x) for k, x in v.items()})
        if isinstance(v, list):
            return self.L.table_from([self.lua(x) for x in v])
        return v

    def test_decision_kept_as_long_as_server_says(self):
        """По подписке (Д15) решения реже: сервер сообщает, сколько держать решение, — иначе через 20 с героем
        зря правил бы запасной исполнитель."""
        self.start_match()
        G = self.G["CoachGame"]
        T = G["teams"][2]
        alive = lambda dt: G["AgentAlive"](G, T, 1, T["dec_t"][1] + dt, True)   # noqa: E731
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        self.assertTrue(alive(19))
        self.assertFalse(alive(21))                                            # по умолчанию — 20 с
        G["OnAgents"](G, self.lua({"stale": 30, "decisions": []}))
        self.assertTrue(alive(29))
        self.assertFalse(alive(31))
        G["OnAgents"](G, self.lua({"stale": 1e6, "decisions": []}))            # нелепое значение — не берём
        self.assertFalse(alive(31))

    def test_last_hit_deny_and_wait(self):
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(5000, -4500, 0)")
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        weak = self.L.eval("__creep(3, 5300, -4300, 50)")                   # вражеский, добивается с одного удара
        self.L.eval("__creep(3, 5350, -4250, 500)")
        n0 = self.n_orders()
        self.step(0.5)
        last = self.unit_orders(sniper, n0)[-1]
        self.assertEqual((last["OrderType"], last["TargetIndex"]), (ORDER["attack"], weak["idx"]))
        weak["alive"] = False
        mine = self.L.eval("__creep(2, 4950, -4450, 40)")                    # свой, меньше половины — добить
        n1 = self.n_orders()
        self.step(0.5)
        last = self.unit_orders(sniper, n1)[-1]
        self.assertEqual((last["OrderType"], last["TargetIndex"]), (ORDER["attack"], mine["idx"]))
        mine["alive"] = False
        n2 = self.n_orders()
        self.step(0.5)
        self.assertEqual(self.unit_orders(sniper, n2)[-1]["OrderType"], ORDER["hold"])  # рядом крип с полным здоровьем

    def test_retreat_reflex_and_resume(self):
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(0, -6000, 0)")
        self.decide(2, 1, {"plan": "push", "where": "bot", "retreat_hp": 30})
        sniper["health"] = 120                                               # 20 %
        n0 = self.n_orders()
        self.step(0.5)
        o = self.unit_orders(sniper, n0)[-1]
        self.assertEqual((o["OrderType"], self.xy(o)), (ORDER["move"], (-7000, -6500)))
        self.step(0.75)
        _, rows = self.hud_rows()
        self.assertTrue(rows[0]["status"].startswith("отхожу"), rows[0])
        sniper["health"] = 600
        n1 = self.n_orders()
        self.step(0.5)
        o = self.unit_orders(sniper, n1)[-1]
        self.assertEqual((o["OrderType"], self.xy(o)), (ORDER["attack_move"], (6200, -1600)))

    def test_cast_level_buy(self):
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        sniper["pos"] = self.L.eval("Vector(0, 0, 0)")
        luna["pos"] = self.L.eval("Vector(400, 0, 0)")
        sniper["points"], sniper["lvl"] = 1, 6
        self.decide(2, 1, {"plan": "fight", "target": "luna",
                           "cast": [{"ability": "sniper_q", "target": "luna"}], "level": ["sniper_w"],
                           "buy": ["item_boots"]})
        n0 = self.n_orders()
        self.step(0.25)
        mine = self.unit_orders(sniper, n0)
        train = [o for o in mine if o["OrderType"] == ORDER["train"]]
        self.assertEqual(train[0]["AbilityIndex"], sniper["abilities"][2]["idx"])   # sniper_w — по очереди агента
        cast = [o for o in mine if o["OrderType"] == ORDER["cast_point"]]
        self.assertEqual((cast[0]["AbilityIndex"], self.xy(cast[0])), (sniper["abilities"][1]["idx"], (400, 0)))
        self.assertIsNone(sniper["slots"][0])                                # не у фонтана — не покупает
        sniper["pos"] = self.L.eval("Vector(-6800, -6300, 0)")
        sniper["gold"] = 700
        self.step(0.5)
        self.assertEqual(sniper["slots"][0]["name"], "item_boots")
        self.assertEqual(sniper["gold"], 200)
        n1 = self.n_orders()
        sniper["pos"] = self.L.eval("Vector(0, 0, 0)")
        self.step(1.25)
        att = [o for o in self.unit_orders(sniper, n1) if o["OrderType"] == ORDER["attack"]]
        self.assertEqual(att[-1]["TargetIndex"], luna["idx"])               # после применения — бой с целью плана

    def test_default_level_ult_first_and_unknown_names(self):
        self.start_match()
        sniper = self.hero(1)
        sniper["points"], sniper["lvl"] = 1, 6
        self.decide(2, 1, {"plan": "hold", "cast": [{"ability": "no_such_spell", "target": ""}],
                           "buy": ["item_nonexistent"]})
        n0 = self.n_orders()
        self.step(0.5)
        train = [o for o in self.unit_orders(sniper, n0) if o["OrderType"] == ORDER["train"]]
        self.assertEqual(train[0]["AbilityIndex"], sniper["abilities"][4]["idx"])   # ульта
        notes = list(self.G["CoachGame"]["teams"][2]["exec"][1]["notes"].values())
        self.assertIn("нет способности no_such_spell", notes)
        self.assertIn("нет такого предмета: item_nonexistent", notes)

    def test_voice_chat_line_in_hud_and_team_chat(self):
        self.start_match()
        self.decide(2, 1, {"plan": "farm", "where": "bot", "say": "Вайпер, Луна идёт к тебе", "to": [2]})
        r = self.replies("say")[-1]
        self.assertEqual((r["pos"], r["hero"], r["to"], r["text"]), (1, "sniper", "2", "Вайпер, Луна идёт к тебе"))
        self.assertEqual(list(self.G["__said"].values())[-1], "→2 Вайпер, Луна идёт к тебе")
        self.decide(2, 2, {"plan": "save", "ally": 1, "say": "Иду", "to": []})
        r = self.replies("say")[-1]
        self.assertEqual((r["pos"], r["to"], r["text"]), (2, "", "Иду"))
        self.assertEqual(list(self.G["__said"].values())[-1], "Иду")

    def test_tp_slot_and_teleport_to_base(self):
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(5000, -4500, 0)")
        tp = self.L.eval("__make_ability")("item_tpscroll", False, 16, 1)
        sniper["slots"][15] = tp                                             # отдельный слот телепорта
        self.decide(2, 1, {"plan": "retreat", "cast": [{"ability": "item_tpscroll", "target": "base"}]})
        n0 = self.n_orders()
        self.step(0.25)
        cast = [o for o in self.unit_orders(sniper, n0) if o["OrderType"] == ORDER["cast_point"]]
        self.assertEqual((cast[0]["AbilityIndex"], self.xy(cast[0])), (tp["idx"], (-7000, -6500)))

    def test_ward_walk_survives_repeated_decision(self):
        self.start_match()
        cm = self.hero(5)
        cm["pos"] = self.L.eval("Vector(5000, -4500, 0)")
        ward = self.L.eval("__make_ability")("item_ward_observer", False, 16, 1)
        cm["slots"][0] = ward
        d = {"plan": "farm", "where": "bot", "cast": [{"ability": "item_ward_observer", "target": "top"}]}
        self.decide(2, 5, d)
        n0 = self.n_orders()
        self.step(0.25)
        cast = [o for o in self.unit_orders(cm, n0) if o["OrderType"] == ORDER["cast_point"]]
        self.assertEqual(self.xy(cast[0]), (-6200, 1800))                    # своя Т1 топ — далеко, идёт ставить
        n1 = self.n_orders()
        self.step(4.0)
        self.assertEqual(self.unit_orders(cm, n1), [])                       # фарм не сбивает подход к варду
        self.decide(2, 5, d)                                                 # агент повторил — продолжает
        self.step(1.0)
        self.assertEqual(self.unit_orders(cm, n1), [])
        ward["ready"] = False                                                # вард поставлен
        self.step(0.5)
        self.assertTrue(self.unit_orders(cm, n1))                            # дальше — по плану

    def test_no_target_ability_waits_for_enemy(self):
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        sniper["pos"] = self.L.eval("Vector(0, 0, 0)")
        luna["pos"] = self.L.eval("Vector(7000, 0, 0)")
        self.decide(2, 1, {"plan": "hold", "cast": [{"ability": "sniper_e", "target": ""}]})   # без цели
        n0 = self.n_orders()
        self.step(0.5)
        self.assertFalse([o for o in self.unit_orders(sniper, n0) if o["OrderType"] == ORDER["cast_none"]])
        luna["pos"] = self.L.eval("Vector(500, 0, 0)")
        self.step(0.5)
        self.assertTrue([o for o in self.unit_orders(sniper, n0) if o["OrderType"] == ORDER["cast_none"]])

    def test_level_falls_back_to_upgrade(self):
        self.start_match()
        sniper = self.hero(1)
        sniper["points"], sniper["lvl"] = 1, 2
        self.decide(2, 1, {"plan": "hold", "level": ["sniper_q"]})
        n0 = self.n_orders()
        self.step(0.25)
        self.assertEqual(len([o for o in self.unit_orders(sniper, n0) if o["OrderType"] == ORDER["train"]]), 1)
        self.assertEqual(sniper["abilities"][1]["level"], 1)                 # приказ в имитации не качает
        self.step(1.25)
        self.assertEqual(sniper["abilities"][1]["level"], 2)                 # вкачано напрямую
        self.assertEqual(sniper["points"], 0)
        n1 = self.n_orders()
        self.step(3)
        self.assertFalse([o for o in self.unit_orders(sniper, n1) if o["OrderType"] == ORDER["train"]])

    def test_loop_survives_errors(self):
        self.start_match()
        self.L.execute("CustomGameEventManager.Send_ServerToTeam = function() error('сломалось') end")
        self.hero(3)["GetMana"] = self.L.eval("function() error('нет маны') end")
        self.step(2)
        self.assertTrue(any("ошибка цикла" in l for l in self.G["__printed"].values()))
        self.assertTrue(any(th["fn"] for th in self.G["__thinks"].values()))   # думание продолжается
        sent = self.payloads()
        self.assertEqual(len(sent[-1]["heroes"]), 9)                         # сломанный герой — только он
        self.assertTrue(any("наблюдение героя 3" in l for l in self.G["__printed"].values()))

    def test_old_decision_ignored_and_server_restart(self):
        self.start_match()
        self.decide(2, 1, {"plan": "retreat"}, seq=5)
        self.decide(2, 1, {"plan": "push", "where": "top"}, seq=4)
        plan = lambda: self.G["CoachGame"]["teams"][2]["exec"][1]["plan"]["kind"]
        self.assertEqual(plan(), "retreat")
        restart = {"run": "второй", "decisions": [{"team": "radiant", "pos": 1, "seq": 1, "decision": {"plan": "hold"}}]}
        self.G["CoachGame"]["OnAgents"](self.G["CoachGame"], self.lua(restart))
        self.assertEqual(plan(), "hold")                                     # новый запуск сервера — номера с 1


class Fallback(Game):
    """Нет сервера агентов: запасной исполнитель выполняет приказы тренера сам, HUD пишет об этом."""

    def test_orders_without_agents(self):
        self.start_match()
        self.step(1)
        mode, rows = self.hud_rows()
        self.assertTrue(mode.startswith("нет связи"), mode)
        self.assertTrue(all(r["source"] == "fallback" for r in rows))
        n0 = self.n_orders()
        self.hud("все назад")
        self.step(0.5)
        radiant = [self.hero(p) for p in range(1, 6)]
        for h in radiant:
            o = self.unit_orders(h, n0)[-1]
            self.assertEqual((o["OrderType"], self.xy(o)), (ORDER["move"], (-7000, -6500)))
        self.assertIn("запасной исполнитель", self.replies("order")[-1]["text"])
        n1 = self.n_orders()
        self.hud("3 ульт луна !")
        self.hero(3)["abilities"][4]["level"] = 1
        self.step(0.5)
        casts = [o for o in self.orders(n1) if o["OrderType"] == ORDER["cast_target"]]
        self.assertEqual(len(casts), 1)
        self.assertEqual(casts[0]["TargetIndex"], self.by_name("luna")["idx"])
        self.assertEqual(casts[0]["AbilityIndex"], self.hero(3)["abilities"][4]["idx"])
        n2 = self.n_orders()
        self.hud("1 пуш топ. 23 деф мид. 45 рош")
        self.step(1.0)
        last = {pos: self.unit_orders(self.hero(pos), n2)[-1] for pos in range(1, 6)}
        self.assertEqual((last[1]["OrderType"], self.xy(last[1])), (ORDER["attack_move"], (-4700, 6000)))
        for pos in (2, 3):
            self.assertEqual(self.xy(last[pos]), (-1500, -1400))
        for pos in (4, 5):
            self.assertEqual((last[pos]["OrderType"], last[pos]["TargetIndex"]), (ORDER["attack"], self.G["__roshan"]["idx"]))
        self.hud("сам")
        n3 = self.n_orders()
        self.step(1.0)
        o = self.unit_orders(self.hero(1), n3)[-1]
        self.assertEqual((o["OrderType"], self.xy(o)), (ORDER["move"], (5550, -3850)))   # «сам» без агента — фарм своей линии

    def test_tower_falls_front_moves(self):
        self.start_match()
        t1 = next(t for t in self.G["__towers"].values() if t["name"] == "npc_dota_badguys_tower1_top")
        t1["alive"] = False
        n0 = self.n_orders()
        self.hud("1 пуш топ")
        self.step(0.5)
        o = self.unit_orders(self.hero(1), n0)[-1]
        self.assertEqual(self.xy(o), (0, 6000))                              # следующая — Т2

    def test_errors_chat_report_ready(self):
        self.start_match()
        self.hud("2 летай")
        errs = self.replies("error")
        self.assertEqual(len(errs), 1)
        self.assertIn("летай", errs[0]["text"])
        n0 = self.n_orders()
        self.L.execute("__fire('player_chat', { playerid = 0, text = 'все рош', teamonly = 1 })")
        self.L.execute("__fire('player_chat', { playerid = 0, text = 'gg', teamonly = 1 })")
        self.step(0.5)
        self.assertEqual(len([o for o in self.orders(n0) if o["OrderType"] == ORDER["attack"]]), 5)
        self.assertEqual(len(self.replies("error")), 1)                      # «gg» — молча
        self.hud("все доклад")
        self.assertEqual(len(self.replies("report")), 5)
        self.G["__listeners"]["vc_ready"](0, self.L.table_from({"PlayerID": 0}))
        acks = [e for e in self.G["__to_player"].values() if e["name"] == "vc_ack"]
        self.assertEqual(acks[0]["data"]["camera"], 1600)


LATE_HEROES = """
__late = {}
local add = Tutorial.AddBot
function Tutorial:AddBot(hero, lane, difficulty, good)        -- бот есть, а его героя Дота ещё не создала
  local ok = add(self, hero, lane, difficulty, good)
  for pid, p in pairs(__players) do
    if p.fake and p.hero then __late[pid] = p.hero; p.hero = nil end
  end
  return ok
end
function PlayerResource:GetSelectedHeroName(pid)
  local p = __players[pid]
  return (p.hero or __late[pid] or {}).name
end
function __reveal()
  for pid, h in pairs(__late) do __players[pid].hero = h end
  __late = {}
end
"""


class Diagnostics(Game):
    """Первый живой матч (10.10.2026, «агентов нет»): консоль Доты (лаунчер показывает её хосту) говорит, кого ведут
    агенты, есть ли связь и почему нет, загрузился ли интерфейс; герои ботов, созданные не сразу, достаются агентам."""

    def printed(self, part):
        return [line for line in self.G["__printed"].values() if part in line]

    def pre_game(self):
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP)")
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_HERO_SELECTION)")
        self.step(2.5)
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_PRE_GAME)")

    def test_late_bot_heroes_still_go_to_agents(self):
        self.L.execute(LATE_HEROES)
        self.pre_game()
        self.step(3)
        self.assertFalse(self.G["CoachGame"]["ready"])                      # раздать сейчас — агентам некого вести
        self.assertEqual(len(self.printed("жду героев ботов: без героя 10 из 10")), 1)
        self.L.execute("__reveal()")
        self.step(1.5)
        self.assertTrue(self.G["CoachGame"]["ready"])
        self.assertTrue(self.printed("Свет 5, Тьма 5"))
        self.assertEqual(self.printed("Свет: агенты ведут"),
                         ["[ТРЕНЕР] Свет: агенты ведут 1 sniper, 2 viper, 3 axe, 4 lion, 5 crystal_maiden; "
                          "тренеров-людей 1"])
        self.assertIn("тренеров-людей 0", self.printed("Тьма: агенты ведут")[0])
        n0 = self.n_orders()
        self.step(1)
        self.assertTrue(self.unit_orders(self.hero(1), n0))                 # и герои пошли (запасной — нет сервера)

    def test_heroes_never_come_says_so(self):
        self.L.execute(LATE_HEROES)
        self.pre_game()
        self.step(32)
        self.assertTrue(self.G["CoachGame"]["ready"])                       # ждать вечно нельзя: игра идёт
        self.assertTrue(self.printed("не дождался героев ботов: без героя 10 из 10"))
        self.assertEqual(self.printed("Свет: агенты ведут")[0], "[ТРЕНЕР] Свет: агенты ведут никого; тренеров-людей 1")

    def test_pulse_link_reason_and_hud_ready(self):
        self.start_match()
        self.assertTrue(self.printed("агенты: нет связи с сервером (HTTP 0: сервер тренера не ответил)"))
        pulse = self.printed("пульс:")
        self.assertEqual(len(pulse), 1)
        self.assertIn("связь с сервером нет", pulse[0])
        self.assertIn("героев 10, из них ведут агенты 0", pulse[0])
        self.step(60)
        self.assertEqual(len(self.printed("пульс:")), 2)                      # раз в минуту
        for _ in range(2):                                                    # интерфейс шлёт «готов», пока не ответят
            self.G["__listeners"]["vc_ready"](0, self.L.table_from({"PlayerID": 0}))
        self.assertEqual(self.printed("интерфейс тренера"), ["[ТРЕНЕР] интерфейс тренера загрузился (игрок 0)"])

    def test_no_http_in_game_named(self):
        self.L.execute("CreateHTTPRequestScriptVM = function() return nil end")   # так в лобби из аркады (research/01)
        self.start_match()
        self.assertTrue(self.printed("игра не дала создать HTTP-запрос"))
        n0 = self.n_orders()
        self.step(1)
        self.assertTrue(self.unit_orders(self.hero(1), n0))                 # героев ведёт запасной исполнитель


class PulseWithAgents(Game):
    server = True

    def test_pulse_counts_agent_led_heroes(self):
        self.start_match()
        self.step(61)
        last = [line for line in self.G["__printed"].values() if "пульс:" in line][-1]
        self.assertIn("связь с сервером есть", last)
        self.assertIn("героев 10, из них ведут агенты 10", last)


class SameRules(Game):
    """Lua и Python договорены об одном: планы, места, линии по позиции."""

    def test_plans_and_lanes_match(self):
        X = self.L.eval('require("coach_exec")')
        self.assertEqual(sorted(X["PLANS"].keys()), sorted(A.PLANS))
        lanes = [X["default_lane"](t, p) for t in (2, 3) for p in range(1, 6)]
        self.assertEqual(lanes, [A.default_lane(t, p) for t in ("radiant", "dire") for p in range(1, 6)])


if __name__ == "__main__":
    unittest.main()
