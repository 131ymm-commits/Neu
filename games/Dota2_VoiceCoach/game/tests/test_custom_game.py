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
DOTA_ABILITY_BEHAVIOR_CHANNELLED, DOTA_ABILITY_BEHAVIOR_TOGGLE, DOTA_ABILITY_BEHAVIOR_AUTOCAST = 128, 512, 4096
DOTA_UNIT_TARGET_TEAM_NONE, DOTA_UNIT_TARGET_TEAM_BOTH = 0, 3
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
  function c:GetPhysicalArmorValue(magic) return self.armor or 0 end
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
  function ab:GetAbilityTargetTeam() return self.tt or 0 end      -- по умолчанию NONE: рефлекс боя не трогает
  function ab:GetAOERadius() return self.aoe or 0 end
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
  function h:GetMana() return self.mana or 300 end
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
  function h:GetAttackAnimationPoint() return self.attack_point or 0.3 end
  function h:GetSecondsPerAttack() return self.spa or 1.7 end
  function h:GetBaseAttackTime() return 1.7 end
  function h:IsRangedAttacker() return self.range > 300 end
  function h:GetProjectileSpeed() return 900 end
  function h:IsChanneling() return false end
  function h:HasModifier(n) return self.mods[n] == true end
  function h:IsMagicImmune() return self.immune == true end
  function h:IsSilenced() return self.silenced == true end
  function h:SetIdleAcquire(on) self.idle_acquire = on end
  function h:GetAttackTarget() return self.attack_target end
  function h:Buyback() self.alive = true; self.bought_back = true end
  function h:UpgradeAbility(ab) if self.points > 0 then ab.level = ab.level + 1; self.points = self.points - 1 end end
  return h
end
__make_hero = make_hero
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
__shared = {}
function PlayerResource:SetUnitShareMaskForPlayer(pid, other, flag, state)
  __shared[#__shared + 1] = { pid = pid, other = other, flag = flag, state = state }
end
__precached = {}
function PrecacheUnitByNameAsync(name, cb) __precached[#__precached + 1] = name; cb(1) end
function RandomInt(a, b) return math.random(a, b) end
function Time() return __now end
HeroList = {}
function HeroList:GetAllHeroes()
  local out = {}
  for _, p in pairs(__players) do if p.hero then out[#out + 1] = p.hero end end
  return out
end
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
-- приказ атаки задаёт цель атаки героя, любой другой приказ (кроме прокачки) её снимает — как в Доте (по памяти);
-- без этого стычки «поддерживали» сами себя, а тесты были зелёными (рецензия 11)
function ExecuteOrderFromTable(t)
  __orders[#__orders + 1] = t
  local u = __ents[t.UnitIndex]
  if u and t.OrderType ~= DOTA_UNIT_ORDER_TRAIN_ABILITY then
    u.attack_target = (t.OrderType == DOTA_UNIT_ORDER_ATTACK_TARGET) and __ents[t.TargetIndex] or nil
  end
end
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
        self.assertEqual(self.xy(moves[-1]), (6200, -4500))   # середина бот-линии по самой линии (через угол карты)
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

    def st(self, team, pos):
        return self.G["CoachGame"]["teams"][team]["exec"][pos]

    def status(self, team, pos):
        return str(self.st(team, pos)["status"])

    def test_last_hit_with_lead_and_no_cancel(self):
        """Слова автора: «нужен ласт хит удар по крипу со слабым здоровьем». Крип теряет здоровье от своих крипов —
        удар начинается заранее (к попаданию у крипа будет не больше 0.85 урона), а пока идёт замах, герой не
        переключается и на крипа, которого добить легче."""
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(5000, -4500, 0)")
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        c = self.L.eval("__creep(3, 5540, -4500, 300)")                     # в 540: попадание через 0.3 + 0.6 с
        self.L.eval("__creep(3, 5450, -4300, 550)")
        attack_hp = None
        for _ in range(30):                                                  # теряет 40 здоровья в секунду
            c["health"] = c["health"] - 10
            n = self.n_orders()
            self.L.execute("__step(0.25)")
            if [o for o in self.unit_orders(sniper, n) if o["OrderType"] == ORDER["attack"] and o["TargetIndex"] == c["idx"]]:
                attack_hp = c["health"]
                break
        self.assertIsNotNone(attack_hp)
        # к попаданию (0.9 с) крип потеряет 36: бить при ≤ 87 (0.85 урона + 36); без упреждения было бы ≤ 51, без
        # полёта снаряда — ≤ 63, с запасом 1.0 — ≤ 96
        self.assertEqual(attack_hp, 80)
        # замер сбился (крипа перестали бить, здоровье чуть выросло) — без защиты замаха руки тут же дали бы «стоять»
        # и сбили бы удар; замах (≈0.4 с) не сбивается ничем
        c["health"] = attack_hp + 5
        n1 = self.n_orders()
        self.L.execute("__step(0.25)")
        self.assertEqual(self.unit_orders(sniper, n1), [])
        self.L.execute("__step(0.25)")                                       # замах кончился — руки снова решают
        self.assertTrue(self.unit_orders(sniper, n1))

    def test_last_hit_stepwise_damage(self):
        """Рецензия 11: урон по крипу идёт ступеньками — каждый крип бьёт раз в ~1 с; замер скорости по окну, удар с
        запасом. Модель: три наших крипа бьют вражеского по 21 раз в 1 с с разными фазами; удар героя (60) попадает через
        0.3 + 500/900 с после приказа; добил — если к попаданию у крипа осталось от 1 до 60. Без упреждения удар
        опаздывает почти всегда (≈54 урона за время полёта)."""
        hit = 0.3 + 500 / 900
        phases = [(0.10, 0.43, 0.77), (0.0, 0.33, 0.66), (0.2, 0.25, 0.9), (0.05, 0.5, 0.55), (0.3, 0.6, 0.95),
                  (0.15, 0.4, 0.7), (0.12, 0.13, 0.62), (0.35, 0.8, 0.85)]
        outcomes = []
        for ph in phases:
            self.tearDown()
            self.setUp()
            self.start_match()
            sniper = self.hero(1)
            sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
            self.decide(2, 1, {"plan": "farm", "where": "bot"})
            c = self.L.eval("__creep(3, 2500, -5000, 550)")
            hp_at = lambda t: 550 - 21 * sum(int((t - p) // 1.0) + 1 for p in ph if t >= p)   # noqa: E731
            t, got = 0.0, None
            n0 = self.n_orders()
            while t < 40 and got is None:
                t += 0.25
                if hp_at(t) <= 0:
                    break
                c["health"] = hp_at(t)
                self.L.execute("__step(0.25)")
                if [o for o in self.unit_orders(sniper, n0) if o["OrderType"] == ORDER["attack"]
                        and o["TargetIndex"] == c["idx"]]:
                    got = t
            h = hp_at(got + hit) if got is not None else 0
            outcomes.append("добил" if 0 < h <= 60 else "рано" if h > 60 else "поздно")
        self.assertGreaterEqual(outcomes.count("добил"), 6, outcomes)

    def test_melee_last_hit_only_when_one_hit_kills(self):
        """Ближний бой попадает через ~0.3 с — за это время удара крипа может и не быть: бьёт, только когда хватает
        удара уже сейчас (модель рецензии 11: с упреждением 9 ранних ударов из 60)."""
        self.start_match()
        axe = self.by_name("axe")
        axe["range"] = 150
        axe["pos"] = self.L.eval("Vector(-6200, 2500, 0)")
        self.decide(2, 3, {"plan": "farm", "where": "top"})
        c = self.L.eval("__creep(3, -6200, 2600, 172)")                      # на 62 упреждение уже ударило бы
        attack_hp = None
        for _ in range(16):
            c["health"] = c["health"] - 10                                    # 40 в секунду
            n = self.n_orders()
            self.L.execute("__step(0.25)")
            if [o for o in self.unit_orders(axe, n) if o["OrderType"] == ORDER["attack"] and o["TargetIndex"] == c["idx"]]:
                attack_hp = c["health"]
                break
        self.assertIsNotNone(attack_hp)
        self.assertLessEqual(attack_hp, 60)

    def test_creep_rate_window_is_one_attack_period(self):
        """Скорость потери здоровья — по замеру ровно секунду назад (период удара крипа): второй бьющий крип виден в
        замере через секунду, а не через две."""
        X = self.L.eval('require("coach_exec")')
        W = self.L.eval('require("coach_world")')
        st = self.L.table_from({})
        c = self.L.eval("__creep(3, 0, 0, 550)")
        rates = []
        for k in range(1, 25):                                               # 6 с, шаг 0.25 с
            t = k * 0.25
            hits = int((t - 0.1) // 1 + 1) if t >= 0.1 else 0                # один крип: 21 раз в 1 с
            if t >= 3.05:
                hits += int((t - 3.05) // 1 + 1)                             # с 3.05 с — второй
            c["health"] = 550 - 21 * hits
            rates.append(X._creep_rate(st, c, W, t))
        self.assertEqual(rates[2], 0)                                        # 0.75 с: окна ещё нет
        self.assertAlmostEqual(rates[7], 21)                                 # 2 с: один крип — 21 в секунду
        self.assertAlmostEqual(rates[16], 42)                                # 4.25 с: двое — 42 (окно 2 с дало бы 31.5)

    def test_last_hit_skips_creep_that_dies_before_hit(self):
        """Крип умрёт раньше, чем долетит удар (к попаданию здоровья ≤ 0), — не бить: удар уйдёт в пустоту."""
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(5000, -4500, 0)")
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        c = self.L.eval("__creep(3, 5900, -4500, 200)")                     # в 900: замеряется, но не в досягаемости
        n0 = self.n_orders()
        for _ in range(7):                                                   # 80 в секунду
            c["health"] = c["health"] - 20
            self.L.execute("__step(0.25)")
        c["pos"] = self.L.eval("Vector(5540, -4500, 0)")                     # в досягаемости при 40: к попаданию
        c["health"] = c["health"] - 20                                       # (0.9 с) — минус 32
        self.L.execute("__step(0.25)")
        self.assertFalse([o for o in self.unit_orders(sniper, n0) if o["OrderType"] == ORDER["attack"]
                          and o["TargetIndex"] == c["idx"]])

    def test_windup_released_when_target_dies_or_tower_hits(self):
        """Замах удара не ждать, если цель умерла раньше попадания (бить другого) или бьёт вражеская вышка (уйти)."""
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(5000, -4500, 0)")
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        c = self.L.eval("__creep(3, 5400, -4500, 45)")
        n0 = self.n_orders()
        self.step(0.25)
        self.assertEqual(self.unit_orders(sniper, n0)[-1]["TargetIndex"], c["idx"])
        c["alive"] = False                                                   # добил кто-то другой
        c2 = self.L.eval("__creep(3, 5350, -4400, 40)")
        n1 = self.n_orders()
        self.step(0.25)
        o = self.unit_orders(sniper, n1)
        self.assertTrue(o and o[-1]["TargetIndex"] == c2["idx"], o)
        t1 = next(t for t in self.G["__towers"].values() if t["name"] == "npc_dota_badguys_tower1_bot")   # (6200,-1600)
        sniper["pos"] = self.L.eval("Vector(6000, -2400, 0)")
        self.L.eval("__creep(3, 5800, -2600, 550)")                           # вражеская волна рядом (целая)
        c3 = self.L.eval("__creep(2, 5700, -2700, 40, 550)")                 # свой крип для деная — замах ≈0.4 с
        c2["alive"] = False
        n2 = self.n_orders()
        self.step(0.25)
        o = self.unit_orders(sniper, n2)
        self.assertTrue(o and o[-1]["TargetIndex"] == c3["idx"], o)
        self.L.execute(f"__ents[{t1['idx']}].GetAttackTarget = function() return __players[1].hero end")
        n3 = self.n_orders()
        self.step(0.25)
        o = self.unit_orders(sniper, n3)
        self.assertTrue(o and o[-1]["OrderType"] == ORDER["move"], o)

    def test_harass_needs_health(self):
        """Размен ударом — только когда у себя здоровья не меньше 60 % и не меньше, чем у врага, без 10."""
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
        luna["pos"] = self.L.eval("Vector(2450, -5000, 0)")
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        self.decide(3, 1, {"plan": "hold"})
        for mine, hers in ((420, 600), (330, 300)):                          # 70 % против 100 %; 55 % против 50 %
            sniper["health"], luna["health"] = mine, hers
            n = self.n_orders()
            self.step(3)
            self.assertFalse([o for o in self.unit_orders(sniper, n) if o["OrderType"] == ORDER["attack"]
                              and o["TargetIndex"] == luna["idx"]], (mine, hers))
        sniper["health"] = 600                                               # здоров — размен есть
        n = self.n_orders()
        self.step(3)
        self.assertTrue([o for o in self.unit_orders(sniper, n) if o["OrderType"] == ORDER["attack"]
                         and o["TargetIndex"] == luna["idx"]])

    def test_harass_windup_not_cancelled(self):
        """Замах удара-размена не сбивается, даже если тут же появилось добивание (оно — после удара)."""
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
        luna["pos"] = self.L.eval("Vector(2450, -5000, 0)")
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        self.decide(3, 1, {"plan": "hold"})
        for _ in range(8):
            n = self.n_orders()
            self.L.execute("__step(0.25)")
            if [o for o in self.unit_orders(sniper, n) if o["OrderType"] == ORDER["attack"] and o["TargetIndex"] == luna["idx"]]:
                break
        self.L.eval("__creep(3, 2300, -4900, 40)")                            # добиваемый крип рядом
        n1 = self.n_orders()
        self.L.execute("__step(0.25)")
        self.assertEqual(self.unit_orders(sniper, n1), [])                   # замах (0.4 с) идёт

    def test_last_hit_counts_armor_and_attack_speed(self):
        """Броня крипа уменьшает удар (у крипа с бронёй 10 удар 60 снимает ≈37); скорость атаки ускоряет замах — удар
        начинается позже."""
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(5000, -4500, 0)")
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        c = self.L.eval("__creep(3, 5300, -4500, 45)")
        c["armor"] = 10                                                       # 45 > 0.85 × 37.5 — одного удара мало
        n0 = self.n_orders()
        self.step(1.5)
        self.assertFalse([o for o in self.unit_orders(sniper, n0) if o["OrderType"] == ORDER["attack"]
                          and o["TargetIndex"] == c["idx"]])
        c["alive"] = False
        sniper["spa"] = 0.85                                                  # вдвое быстрее: замах 0.15 с
        c2 = self.L.eval("__creep(3, 5540, -4500, 305)")
        attack_hp = None
        for _ in range(30):
            c2["health"] = c2["health"] - 10
            n = self.n_orders()
            self.L.execute("__step(0.25)")
            if [o for o in self.unit_orders(sniper, n) if o["OrderType"] == ORDER["attack"] and o["TargetIndex"] == c2["idx"]]:
                attack_hp = c2["health"]
                break
        self.assertEqual(attack_hp, 75)                                      # к попаданию 0.75 с: ≤ 51 + 30

    def test_wait_at_creep_that_dies_soonest(self):
        """Где ждать добивания: у крипа, который скоро умрёт (по замеру), а не просто у ближайшего."""
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        self.L.eval("__creep(3, 2700, -5000, 550)")                           # ближний, целый
        b = self.L.eval("__creep(3, 2000, -5750, 400)")                       # чуть дальше, его бьют
        moves = []
        for _ in range(8):
            b["health"] = b["health"] - 15
            n = self.n_orders()
            self.L.execute("__step(0.25)")
            moves += [o for o in self.unit_orders(sniper, n) if o["OrderType"] == ORDER["move"]]
        self.assertTrue(moves)
        x, y = self.xy(moves[-1])
        self.assertLess(y, -5100)                                             # к тому, которого бьют (вниз)

    def test_harass_rules_melee_tower_numbers(self):
        """Размен ударом: ближнему бою — не в толпе вражеских крипов; не от своей позиции у их вышки; не против
        перевеса — даже когда враг в досягаемости и здоровья хватает."""
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        self.decide(3, 1, {"plan": "hold"})
        self.decide(2, 1, {"plan": "farm", "where": "bot"})

        def attacks(seconds=3):
            n = self.n_orders()
            self.step(seconds)
            return [o for o in self.unit_orders(sniper, n) if o["OrderType"] == ORDER["attack"]
                    and o["TargetIndex"] == luna["idx"]]
        # своя позиция в 850 от их Т1 бот (6200, -1600), Luna — в 1300 от неё
        sniper["pos"] = self.L.eval("Vector(6200, -2450, 0)")
        luna["pos"] = self.L.eval("Vector(6200, -2900, 0)")
        self.assertFalse(attacks())
        # перевес: трое у Luna, свой один
        sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
        luna["pos"] = self.L.eval("Vector(2450, -5000, 0)")
        for name, x in (("lina", 2700), ("bristleback", 2800)):
            self.by_name(name)["pos"] = self.L.eval(f"Vector({x}, -5100, 0)")
        self.assertFalse(attacks())
        for name in ("lina", "bristleback"):
            self.by_name(name)["pos"] = self.L.eval("Vector(6700, 6200, 0)")
        self.assertTrue(attacks())                                            # без перевеса — размен есть
        # ближний бой (Axe) и три вражеских крипа рядом — не разменивается; один крип — да
        self.decide(2, 1, {"plan": "hold"})
        axe, bb = self.by_name("axe"), self.by_name("bristleback")
        axe["range"] = 150
        axe["pos"] = self.L.eval("Vector(-6000, 3500, 0)")
        bb["pos"] = self.L.eval("Vector(-6000, 3750, 0)")                     # в 250: дотянуться с подходом
        self.decide(2, 3, {"plan": "farm", "where": "top"})
        self.decide(3, 3, {"plan": "hold"})
        crowd = [self.L.eval(f"__creep(3, {-6100 + 100 * i}, 3900, 550)") for i in range(3)]
        n = self.n_orders()
        self.step(3)
        self.assertFalse([o for o in self.unit_orders(axe, n) if o["OrderType"] == ORDER["attack"]
                          and o["TargetIndex"] == bb["idx"]])
        for c in crowd[1:]:
            c["alive"] = False
        n = self.n_orders()
        self.step(4)
        self.assertTrue([o for o in self.unit_orders(axe, n) if o["OrderType"] == ORDER["attack"]
                         and o["TargetIndex"] == bb["idx"]])

    def test_skirmish_thresholds_and_reset(self):
        """Пороги стычки: раненого у их вышки не добивать; добивать — только в досягаемости + 300 и от 30 % своего
        здоровья; не отвечать врагу намного здоровее; не выручать здорового союзника; самому при < 45 % — не вступать;
        после смерти стычка не продолжается."""
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        self.decide(3, 1, {"plan": "hold"})
        self.decide(2, 1, {"plan": "farm", "where": "bot", "retreat_hp": 0})

        def fighting(seconds=0.5):
            self.step(seconds)
            return self.status(2, 1).startswith("стычка")
        luna["health"] = 180                                                  # 30 %
        sniper["pos"] = self.L.eval("Vector(-500, 0, 0)")                     # Luna у их Т1 мид (500, 650): в 550
        luna["pos"] = self.L.eval("Vector(0, 300, 0)")
        self.assertFalse(fighting())
        sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
        luna["pos"] = self.L.eval("Vector(2880, -5000, 0)")                   # 880 > 550 + 300
        self.assertFalse(fighting())
        luna["pos"] = self.L.eval("Vector(2800, -5000, 0)")                   # 800 — в досягаемости + 300
        sniper["health"] = 150                                                # 25 % — сам слишком ранен
        self.assertFalse(fighting())
        sniper["health"] = 600
        self.assertTrue(fighting())
        sniper["alive"] = False                                               # погиб посреди стычки
        self.step(0.5)
        sniper["alive"] = True
        luna["health"] = 600                                                  # повода больше нет
        self.assertFalse(fighting(0.25))
        # «отвечаю» — не врагу намного здоровее
        sniper["health"] = 300                                                # 50 %
        self.decide(3, 1, {"plan": "fight", "target": "sniper"})
        self.assertFalse(fighting(2))
        # «выручаю» — не здорового союзника; и не при своём здоровье < 45 %
        self.decide(3, 1, {"plan": "hold"})
        lion, axe, bb = self.by_name("lion"), self.by_name("axe"), self.by_name("bristleback")
        lion["pos"] = self.L.eval("Vector(-6000, 3500, 0)")
        axe["pos"] = self.L.eval("Vector(-5800, 3800, 0)")
        bb["pos"] = self.L.eval("Vector(-5600, 4100, 0)")
        self.decide(2, 3, {"plan": "hold"})
        self.decide(2, 4, {"plan": "farm", "where": "top"})
        self.decide(3, 3, {"plan": "fight", "target": "axe"})
        self.step(2)
        self.assertFalse(self.status(2, 4).startswith("стычка"), self.status(2, 4))    # Axe цел
        axe["health"] = 300
        lion["health"] = 240                                                  # 40 % — сам слаб
        self.step(1)
        self.assertFalse(self.status(2, 4).startswith("стычка"), self.status(2, 4))
        lion["health"] = 600
        self.step(0.5)
        self.assertTrue(self.status(2, 4).startswith("стычка: выручаю 3"), self.status(2, 4))
        # повод пропал — стычка держится ещё до 3 с, потом кончается
        self.decide(3, 3, {"plan": "hold"})
        self.step(1)
        self.assertTrue(self.status(2, 4).startswith("стычка"), self.status(2, 4))
        self.step(3)
        self.assertFalse(self.status(2, 4).startswith("стычка"), self.status(2, 4))

    def test_no_deny_under_enemy_tower(self):
        """Свой крип у вражеской вышки не денаить (ближний бой подошёл бы под выстрел)."""
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(6200, -2600, 0)")                  # 1000 от их Т1 бот (6200, -1600)
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        self.L.eval("__creep(3, 5900, -2800, 550)")                           # вражеская волна рядом (не у вышки)
        mine = self.L.eval("__creep(2, 6200, -2200, 40)")                     # в 600 от вышки
        n0 = self.n_orders()
        self.step(1)
        self.assertFalse([o for o in self.unit_orders(sniper, n0) if o["OrderType"] == ORDER["attack"]
                          and o["TargetIndex"] == mine["idx"]])

    def test_leaves_tower_aggro(self):
        """Вражеская вышка бьёт героя на пуше — отходит за её досягаемость; в драке с запасом здоровья — нет."""
        self.start_match()
        sniper = self.hero(1)
        t1 = next(t for t in self.G["__towers"].values() if t["name"] == "npc_dota_badguys_tower1_bot")   # (6200,-1600)
        sniper["pos"] = self.L.eval("Vector(6200, -2100, 0)")
        self.L.execute(f"__ents[{t1['idx']}].GetAttackTarget = function() return __players[1].hero end")
        self.decide(2, 1, {"plan": "push", "where": "bot"})
        n0 = self.n_orders()
        self.step(0.5)
        o = self.unit_orders(sniper, n0)[-1]
        x, y = self.xy(o)
        self.assertEqual(o["OrderType"], ORDER["move"])
        self.assertGreater(((x - 6200) ** 2 + (y + 1600) ** 2) ** 0.5, 900)
        self.assertEqual(self.status(2, 1), "отхожу из-под вышки")
        self.decide(2, 1, {"plan": "fight", "target": "luna"})                # драка, здоровье полное — не бежит
        self.step(0.5)
        self.assertNotEqual(self.status(2, 1), "отхожу из-под вышки")
        self.hero(1)["health"] = 240                                         # 40 %: в драке тоже уходит
        self.step(0.5)
        self.assertEqual(self.status(2, 1), "отхожу из-под вышки")

    def test_agent_cast_before_tower_reflex(self):
        """Рецензия 11: применение агента (телепорт на базу) — раньше рефлекса «из-под вышки»."""
        self.start_match()
        sniper = self.hero(1)
        t1 = next(t for t in self.G["__towers"].values() if t["name"] == "npc_dota_badguys_tower1_bot")
        sniper["pos"] = self.L.eval("Vector(6200, -2100, 0)")
        self.L.execute(f"__ents[{t1['idx']}].GetAttackTarget = function() return __players[1].hero end")
        tp = self.L.eval("__make_ability")("item_tpscroll", False, 16, 1)
        sniper["slots"][15] = tp
        self.decide(2, 1, {"plan": "retreat", "cast": [{"ability": "item_tpscroll", "target": "base"}]})
        n0 = self.n_orders()
        self.step(0.25)
        first = self.unit_orders(sniper, n0)[0]
        self.assertEqual((first["OrderType"], first["AbilityIndex"]), (ORDER["cast_point"], tp["idx"]))

    def test_retreat_interrupts_attack_windup(self):
        """Рецензия 11: замах удара (до 1.5 с) не откладывает отход — здоровье ниже порога, и герой уходит сразу."""
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
        self.decide(2, 1, {"plan": "farm", "where": "bot", "retreat_hp": 30})
        c = self.L.eval("__creep(3, 2600, -5000, 50)")                      # в 600: подойти 50 и замах ≈0.5 с
        n0 = self.n_orders()
        self.step(0.25)
        self.assertEqual(self.unit_orders(sniper, n0)[-1]["TargetIndex"], c["idx"])
        sniper["health"] = 120                                               # 20 %
        n1 = self.n_orders()
        self.step(0.25)
        o = self.unit_orders(sniper, n1)
        self.assertTrue(o and o[-1]["OrderType"] == ORDER["move"], o)
        self.assertTrue(self.status(2, 1).startswith("отхожу"), self.status(2, 1))

    def test_lane_harass_hit_and_back(self):
        """Живой матч 11.10.2026: «очень мало действий делают». На линии вдали от вышек враг в досягаемости, у героя
        здоровья не меньше — один удар по врагу, потом снова к линии (удар больше не идёт: цель атаки снята);
        следующий удар — не раньше чем через 2.5 с (дальний бой). Крип слабее двух ударов рядом — сначала он."""
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
        luna["pos"] = self.L.eval("Vector(2450, -5000, 0)")
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        self.decide(3, 1, {"plan": "hold"})
        times = []
        for k in range(24):                                                   # 6 с
            n = self.n_orders()
            self.L.execute("__step(0.25)")
            if [o for o in self.unit_orders(sniper, n) if o["OrderType"] == ORDER["attack"]
                    and o["TargetIndex"] == luna["idx"]]:
                times.append(k * 0.25)
            elif times and k * 0.25 - times[-1] == 1.0:
                self.assertIsNone(sniper["attack_target"])                   # через секунду после удара — не бьёт
        self.assertGreaterEqual(len(times), 2, times)
        self.assertTrue(all(b - a >= 2.5 - 1e-9 for a, b in zip(times, times[1:])), times)
        self.L.eval("__creep(3, 2300, -4900, 100)")                           # добить с двух ударов — ждать его
        n1 = self.n_orders()
        self.step(3)
        self.assertFalse([o for o in self.unit_orders(sniper, n1) if o["OrderType"] == ORDER["attack"]
                          and o["TargetIndex"] == luna["idx"]])

    def test_trade_does_not_snowball(self):
        """Рецензия 11: у соперника те же руки (Д16). Оба на фарме в досягаемости друг друга — размены по одному удару,
        стычки нет: «отвечаю» — только когда враг бьёт дольше секунды."""
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
        luna["pos"] = self.L.eval("Vector(2450, -5000, 0)")
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        self.decide(3, 1, {"plan": "farm", "where": "top"})
        in_fight, hits = 0, {2: [], 3: []}
        for k in range(48):                                                   # 12 с
            n = self.n_orders()
            self.L.execute("__step(0.25)")
            for team, me, other in ((2, sniper, luna), (3, luna, sniper)):
                if self.status(team, 1).startswith("стычка"):
                    in_fight += 1
                if [o for o in self.unit_orders(me, n) if o["OrderType"] == ORDER["attack"]
                        and o["TargetIndex"] == other["idx"]]:
                    hits[team].append(k * 0.25)
        self.assertEqual(in_fight, 0)
        for team, ts in hits.items():
            self.assertGreaterEqual(len(ts), 2, (team, ts))
            self.assertTrue(all(b - a >= 2.5 - 1e-9 for a, b in zip(ts, ts[1:])), (team, ts))

    def test_skirmish_helps_and_joins_ally(self):
        """Стычка: враг бьёт раненого союзника дольше секунды — выручить; союзник бьёт раненого врага — поддержать, а
        здорового — нет (это решение агента); на «иду» — не отвлекаться."""
        self.start_match()
        lion, axe, bb = self.by_name("lion"), self.by_name("axe"), self.by_name("bristleback")
        lion["pos"] = self.L.eval("Vector(-6000, 3500, 0)")
        axe["pos"] = self.L.eval("Vector(-5800, 3800, 0)")
        bb["pos"] = self.L.eval("Vector(-5600, 4100, 0)")                     # до их Т1 топ ≈ 2100
        axe["health"] = 300                                                   # 50 %
        self.decide(2, 3, {"plan": "hold"})
        self.decide(2, 4, {"plan": "farm", "where": "top"})
        self.decide(3, 3, {"plan": "fight", "target": "axe"})                 # BB бьёт Axe
        self.step(0.5)
        self.assertFalse(self.status(2, 4).startswith("стычка"), self.status(2, 4))   # бьёт меньше секунды
        n0 = self.n_orders()
        self.step(1.0)
        self.assertTrue(self.status(2, 4).startswith("стычка: выручаю 3"), self.status(2, 4))
        att = [o for o in self.unit_orders(lion, n0) if o["OrderType"] == ORDER["attack"]]
        self.assertEqual(att[-1]["TargetIndex"], bb["idx"])
        axe["health"] = 600
        self.decide(3, 3, {"plan": "hold"})
        self.decide(2, 3, {"plan": "fight", "target": "bristleback"})         # Axe сам бьёт BB, у BB полное здоровье
        self.step(4)
        self.assertFalse(self.status(2, 4).startswith("стычка"), self.status(2, 4))
        bb["health"] = 380                                                    # 63 % — раненый: поддержать
        self.step(0.5)
        self.assertTrue(self.status(2, 4).startswith("стычка: вместе с 3"), self.status(2, 4))
        self.decide(2, 4, {"plan": "move", "where": "mid"})                   # агент ведёт в другое место
        n1 = self.n_orders()
        self.step(1.25)
        self.assertFalse([o for o in self.unit_orders(lion, n1) if o["OrderType"] == ORDER["attack"]])

    def test_skirmish_answers_but_not_outnumbered(self):
        """Враг бьёт героя дольше секунды — ответить; врагов рядом с ним трое, а свой один — ни стычки, ни размена,
        хотя враг в досягаемости."""
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
        luna["pos"] = self.L.eval("Vector(2650, -5000, 0)")                   # вне досягаемости: размена нет
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        self.decide(3, 1, {"plan": "fight", "target": "sniper"})
        self.step(1.75)
        self.assertTrue(self.status(2, 1).startswith("стычка: отвечаю"), self.status(2, 1))
        self.assertEqual(sniper["attack_target"]["idx"], luna["idx"])
        luna["pos"] = self.L.eval("Vector(2450, -5000, 0)")                   # в досягаемости
        for name, x in (("lina", 2700), ("bristleback", 2800)):
            self.by_name(name)["pos"] = self.L.eval(f"Vector({x}, -5100, 0)")
        self.step(0.5)
        n1 = self.n_orders()
        self.step(2)
        self.assertFalse([o for o in self.unit_orders(sniper, n1) if o["OrderType"] == ORDER["attack"]
                          and o["TargetIndex"] == luna["idx"]])
        self.assertFalse(self.status(2, 1).startswith("стычка"), self.status(2, 1))

    def test_carry_on_farm_only_finishes_and_answers(self):
        """Рецензия 11: керри на фарме не вступает в стычку союзника (гайды: керри на линии не дерётся), но раненого
        врага в досягаемости + 300 добивает."""
        self.start_match()
        sniper, cm, luna = self.hero(1), self.by_name("crystal_maiden"), self.by_name("luna")
        sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
        cm["pos"] = self.L.eval("Vector(2100, -4900, 0)")
        luna["pos"] = self.L.eval("Vector(2800, -5000, 0)")                   # 800: вне досягаемости 550
        luna["health"] = 380                                                  # 63 %
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        self.decide(2, 5, {"plan": "fight", "target": "luna"})
        self.decide(3, 1, {"plan": "hold"})
        self.step(1.5)
        self.assertFalse(self.status(2, 1).startswith("стычка"), self.status(2, 1))
        luna["health"] = 200                                                  # 33 %
        self.step(0.5)
        self.assertTrue(self.status(2, 1).startswith("стычка: добиваю"), self.status(2, 1))

    def test_skirmish_leash(self):
        """Рецензия 11: стычка не гонится дальше 1500 от места, где началась, и ту же цель сразу снова не берёт."""
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        sniper["pos"] = self.L.eval("Vector(0, -5000, 0)")
        luna["pos"] = self.L.eval("Vector(500, -5000, 0)")
        luna["health"] = 200
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        self.decide(3, 1, {"plan": "hold"})
        self.step(0.5)
        self.assertTrue(self.status(2, 1).startswith("стычка: добиваю"), self.status(2, 1))
        for x in (500, 1000):                                                 # бегут оба, Luna впереди на 500
            sniper["pos"] = self.L.eval(f"Vector({x}, -5000, 0)")
            luna["pos"] = self.L.eval(f"Vector({x + 500}, -5000, 0)")
            self.step(0.5)
        self.assertTrue(self.status(2, 1).startswith("стычка"), self.status(2, 1))   # Luna в 1500 — ещё можно
        sniper["pos"] = self.L.eval("Vector(1400, -5000, 0)")
        luna["pos"] = self.L.eval("Vector(1900, -5000, 0)")                   # в 1900 от начала
        self.step(0.5)
        self.assertFalse(self.status(2, 1).startswith("стычка"), self.status(2, 1))
        self.step(3)
        self.assertFalse(self.status(2, 1).startswith("стычка"), self.status(2, 1))   # снова не берёт

    def test_skirmish_ult_only_below_half(self):
        """Рецензия 11: в стычке ульта — только по врагу ниже половины здоровья, даже когда врагов рядом двое."""
        self.start_match()
        lion, axe, bb, wd = (self.by_name(n) for n in ("lion", "axe", "bristleback", "witch_doctor"))
        lion["pos"] = self.L.eval("Vector(-5900, 3700, 0)")                   # до BB 500: способности достают
        axe["pos"] = self.L.eval("Vector(-5800, 3800, 0)")
        bb["pos"] = self.L.eval("Vector(-5600, 4100, 0)")
        wd["pos"] = self.L.eval("Vector(-5500, 4300, 0)")
        for ab in list(lion["abilities"].values()):
            ab["tt"] = 2
        lion["abilities"][4]["level"] = 1
        ult = lion["abilities"][4]["idx"]
        bb["health"] = 390                                                    # 65 %
        self.decide(2, 3, {"plan": "fight", "target": "bristleback"})
        self.decide(2, 4, {"plan": "farm", "where": "top"})
        self.decide(3, 3, {"plan": "hold"})
        self.decide(3, 4, {"plan": "hold"})
        n0 = self.n_orders()
        self.step(3)
        self.assertTrue(self.status(2, 4).startswith(("стычка", "бью способностью")), self.status(2, 4))
        got = {o["AbilityIndex"] for o in self.casts(lion, n0)}
        self.assertTrue(got)
        self.assertNotIn(ult, got)
        bb["health"] = 270                                                    # 45 %
        n1 = self.n_orders()
        self.step(3)
        self.assertIn(ult, {o["AbilityIndex"] for o in self.casts(lion, n1)})

    def test_melee_waits_at_front_creeps(self):
        """Рецензия 11: ближний бой ждёт добивания у передних крипов волны, а не уходит за спины вражеских ближних к их
        дальнему крипу (у него меньше здоровья по KV)."""
        self.start_match()
        axe = self.by_name("axe")
        axe["range"] = 150                                                    # ближний бой
        axe["pos"] = self.L.eval("Vector(-6200, 2500, 0)")
        self.decide(2, 3, {"plan": "farm", "where": "top"})
        for dy in (300, 330, 360):
            self.L.eval(f"__creep(3, -6200, {2500 + dy}, 550)")
        self.L.eval("__creep(3, -6200, 3150, 300, 300)")                       # дальний за ними
        n0 = self.n_orders()
        self.step(1)
        moves = [o for o in self.unit_orders(axe, n0) if o["OrderType"] == ORDER["move"]]
        self.assertFalse(moves, moves)                                        # у волны (300 ≤ 150 + 250) — стоит

    def test_support_harass_hit_and_back(self):
        """Саппорт рядом со своим кором бьёт врага, когда безопасно: один удар — и назад к своему."""
        self.start_match()
        axe, lion, bb = self.by_name("axe"), self.by_name("lion"), self.by_name("bristleback")
        axe["pos"] = self.L.eval("Vector(-6200, 3000, 0)")
        lion["pos"] = self.L.eval("Vector(-6150, 3200, 0)")
        bb["pos"] = self.L.eval("Vector(-6100, 3650, 0)")                      # в 455 от Lion
        self.decide(2, 3, {"plan": "hold"})
        self.decide(2, 4, {"plan": "farm", "where": "top"})
        self.decide(3, 3, {"plan": "hold"})
        hits = []
        for k in range(20):                                                   # 5 с
            n = self.n_orders()
            self.L.execute("__step(0.25)")
            if [o for o in self.unit_orders(lion, n) if o["OrderType"] == ORDER["attack"] and o["TargetIndex"] == bb["idx"]]:
                hits.append(k)
        self.assertGreaterEqual(len(hits), 2, hits)
        self.assertTrue(all(b - a >= 10 for a, b in zip(hits, hits[1:])), hits)    # раз в 2.5 с

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

    def fight_setup(self, plan, luna_hp=600, sniper_hp=600, dist=500, at=(0, 0)):
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        sniper["pos"] = self.L.eval(f"Vector({at[0]}, {at[1]}, 0)")
        luna["pos"] = self.L.eval(f"Vector({at[0] + dist}, {at[1]}, 0)")
        luna["health"], sniper["health"] = luna_hp, sniper_hp
        for ab in list(sniper["abilities"].values()):
            ab["tt"] = 2                                                      # все — по врагам
        sniper["abilities"][4]["level"] = 1                                   # ульта изучена
        self.decide(2, 1, plan)
        return sniper, luna

    def casts(self, hero, since):
        return [o for o in self.unit_orders(hero, since)
                if o["OrderType"] in (ORDER["cast_point"], ORDER["cast_target"], ORDER["cast_none"])]

    def test_auto_spells_in_fight(self):
        """Живой матч: «только простые действия» — агент не называл способности заранее, руки их не применяли.
        Теперь в драке руки сами бьют способностями по врагу в досягаемости; ульта — когда враг ранен."""
        sniper, luna = self.fight_setup({"plan": "fight", "target": "luna"})
        n0 = self.n_orders()
        self.step(2)
        names = {o["AbilityIndex"] for o in self.casts(sniper, n0)}
        q, w, e, r = (sniper["abilities"][i]["idx"] for i in (1, 2, 3, 4))
        self.assertIn(q, names)                                               # точечная — в точку врага
        self.assertIn(w, names)                                               # по цели — во врага
        self.assertNotIn(e, names)                                            # без цели: враг дальше 300
        self.assertNotIn(r, names)                                            # враг цел — ульту бережём
        luna["health"] = 300                                                  # 50 %
        n1 = self.n_orders()
        self.step(4)
        self.assertIn(r, {o["AbilityIndex"] for o in self.casts(sniper, n1)})
        _, rows = self.hud_rows()
        self.assertTrue(any("способност" in r_["status"] or r_["status"].startswith("бой") for r_ in rows[:1]))

    def test_lane_spells_harass_with_mana_and_kill_with_ult(self):
        """Живой матч 11.10.2026: «очень мало действий делают». На фарме вдали от вышек: маны мало — способности
        бережёт; маны с запасом — размен способностью только из списка урона (рецензия 11: не оглушения), одной за 8 с,
        без ульты и не когда на подходе добивание; враг ранен — стычка: способности как в драке, ульта — по раненому
        до половины. У их вышки (центр карты в имитации — их Т1 мид) — без размена и без стычки."""
        sniper, luna = self.fight_setup({"plan": "farm", "where": "bot"}, dist=400, at=(2000, -5000))
        self.decide(3, 1, {"plan": "hold"})
        q, w, r = (sniper["abilities"][i] for i in (1, 2, 4))
        w["name"] = "sniper_shrapnel"                                         # из списка размена — вторая по счёту;
        q["name"] = "sniper_stun"                                             # первая (не из списка) — не тратить
        sniper["mana"] = 120                                                  # 40 % — у керри порог 80 %
        n0 = self.n_orders()
        self.step(1.5)
        self.assertEqual(self.casts(sniper, n0), [])
        sniper["mana"] = 300
        n1 = self.n_orders()
        self.step(1.5)
        got = [o["AbilityIndex"] for o in self.casts(sniper, n1)]
        self.assertEqual(got, [w["idx"]])                                     # один размен, и только уроном
        n2 = self.n_orders()
        self.step(5)
        self.assertEqual(self.casts(sniper, n2), [])                          # следующий — не раньше чем через 8 с
        weak = self.L.eval("__creep(3, 2300, -4900, 100)")                     # добивание на подходе — не до размена
        n3 = self.n_orders()
        self.step(4)
        self.assertEqual(self.casts(sniper, n3), [])
        weak["alive"] = False
        n4 = self.n_orders()
        self.step(1)
        self.assertEqual([o["AbilityIndex"] for o in self.casts(sniper, n4)], [w["idx"]])
        luna["health"] = 200                                                  # 33 % — добить
        n5 = self.n_orders()
        self.step(3)
        got = {o["AbilityIndex"] for o in self.casts(sniper, n5)}
        self.assertIn(r["idx"], got)
        self.assertIn(q["idx"], got)                                          # в стычке — все способности по врагу
        self.assertTrue(self.status(2, 1).startswith(("стычка: добиваю", "бью способностью")), self.status(2, 1))
        # у вражеской вышки (их Т1 мид в (500, 650)): ни размена, ни стычки
        sniper["pos"] = self.L.eval("Vector(0, 0, 0)")
        luna["pos"] = self.L.eval("Vector(400, 0, 0)")
        luna["health"] = 600
        self.step(9)                                                          # пауза размена прошла
        n6 = self.n_orders()
        self.step(2)
        self.assertEqual(self.casts(sniper, n6), [])
        self.assertFalse([o for o in self.unit_orders(sniper, n6) if o["OrderType"] == ORDER["attack"]
                          and o["TargetIndex"] == luna["idx"]])

    def test_auto_spells_skip_toggles_and_friendly(self):
        sniper, luna = self.fight_setup({"plan": "fight", "target": "luna"})
        sniper["abilities"][1]["tt"] = 1                                      # по союзникам
        sniper["abilities"][2]["behavior"] = 8 + 512                          # переключатель
        n0 = self.n_orders()
        self.step(1.5)
        idx = {o["AbilityIndex"] for o in self.casts(sniper, n0)}
        self.assertNotIn(sniper["abilities"][1]["idx"], idx)
        self.assertNotIn(sniper["abilities"][2]["idx"], idx)

    def test_escape_hits_chaser_without_ult(self):
        sniper, luna = self.fight_setup({"plan": "farm", "where": "bot", "retreat_hp": 40}, sniper_hp=120, dist=350,
                                        luna_hp=200)
        n0 = self.n_orders()
        self.step(1)
        got = self.casts(sniper, n0)
        self.assertTrue(got)                                                  # отходя — бьёт догоняющего
        self.assertNotIn(sniper["abilities"][4]["idx"], {o["AbilityIndex"] for o in got})

    def test_support_keeps_own_lane_core(self):
        """Рецензия 10: на старте у фонтана саппорт сложной линии (Lion, 4) не уходит за керри (Sniper) на бот."""
        self.start_match()
        lion = self.by_name("lion")
        for name in ("sniper", "lion", "axe"):
            self.by_name(name)["pos"] = self.L.eval("Vector(-6700, -6200, 0)")
        self.decide(2, 4, {"plan": "farm", "where": "top"})
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        n0 = self.n_orders()
        self.step(1)
        o = self.unit_orders(lion, n0)[-1]
        x, y = self.xy(o)
        self.assertLess(x, -5000)                                            # идёт на верх (левый край), не на бот
        self.assertGreater(y, 0)
        # керри зашёл на верхнюю линию к саппорту — это не кор его линии: саппорт фармит сам, а не встаёт к нему
        lion["pos"] = self.L.eval("Vector(-6200, 3000, 0)")
        self.by_name("sniper")["pos"] = self.L.eval("Vector(-6250, 3100, 0)")
        self.step(1)
        _, rows = self.hud_rows()
        self.assertFalse(rows[3]["status"].startswith("линия с 1"), rows[3])

    def test_support_does_not_steal_last_hits(self):
        """Д18: саппорт на линии рядом со своим кором вражеских крипов не добивает, своих — добивает, бьёт врага,
        когда безопасно, иначе стоит у своего."""
        self.start_match()
        axe, lion = self.by_name("axe"), self.by_name("lion")                 # 3 и 4 — сложная линия Света
        axe["pos"] = self.L.eval("Vector(-6200, 3000, 0)")
        lion["pos"] = self.L.eval("Vector(-6250, 2900, 0)")
        self.decide(2, 4, {"plan": "farm", "where": "top"})
        self.decide(2, 3, {"plan": "hold"})
        weak = self.L.eval("__creep(3, -6150, 3200, 30)")                     # вражеский — добил бы с удара
        n0 = self.n_orders()
        self.step(1)
        att = [o for o in self.unit_orders(lion, n0) if o["OrderType"] == ORDER["attack"]]
        self.assertFalse([o for o in att if o["TargetIndex"] == weak["idx"]])  # добивание — керри/оффлейнеру
        mine = self.L.eval("__creep(2, -6230, 2950, 40)")                     # свой, ниже половины — добить
        n1 = self.n_orders()
        self.step(0.5)
        last = self.unit_orders(lion, n1)[-1]
        self.assertEqual((last["OrderType"], last["TargetIndex"]), (ORDER["attack"], mine["idx"]))
        mine["alive"] = False
        weak["alive"] = False
        axe["pos"] = self.L.eval("Vector(-6200, 3500, 0)")                    # кор отошёл на 600 — саппорт к нему
        n2 = self.n_orders()
        self.step(1)
        o = self.unit_orders(lion, n2)[-1]
        self.assertEqual(o["OrderType"], ORDER["move"])
        x, y = self.xy(o)
        self.assertLess(((x + 6200) ** 2 + (y - 3500) ** 2) ** 0.5, 300)       # встаёт за своим, ближе к базе

    def test_review10_spell_rules(self):
        """Рецензия 10: канальные — только через cast; при отходе — только по цели/в точку; площадные из списка — да;
        по невосприимчивому к магии — нет; отход, выбранный агентом, — режим отхода."""
        sniper, luna = self.fight_setup({"plan": "fight", "target": "luna"}, dist=250)
        q, w, e, r = (sniper["abilities"][i] for i in (1, 2, 3, 4))
        w["behavior"] = 8 + 128                                              # канальная по цели
        q["name"], q["tt"] = "sniper_shrapnel", 0                            # площадная без цели в KV — из списка
        n0 = self.n_orders()
        self.step(1.5)
        idx = {o["AbilityIndex"] for o in self.casts(sniper, n0)}
        self.assertIn(q["idx"], idx)
        self.assertNotIn(w["idx"], idx)
        luna["immune"] = True                                                # BKB — приказ отклонят
        n1 = self.n_orders()
        self.step(4)
        self.assertEqual(self.casts(sniper, n1), [])
        luna["immune"] = False
        luna["health"] = 200                                                 # слаб — на farm добили бы, но план retreat
        self.decide(2, 1, {"plan": "retreat"})
        e["behavior"] = 4                                                    # без цели — при отходе нельзя
        q["ready"] = False
        n2 = self.n_orders()
        self.step(4)
        got = {o["AbilityIndex"] for o in self.casts(sniper, n2)}
        self.assertNotIn(e["idx"], got)
        self.assertNotIn(r["idx"], got)

    def test_farm_acquire_off_tango_and_free_ward(self):
        """Д18 по гайдам: на фарме крипов бьют только добиванием (без атаки ближайшего); танго — у дерева; вард из
        запаса магазина (цена 0) покупается."""
        self.L.execute("""
          __trees = {}
          GridNav = {}
          function GridNav:IsNearbyTree() return false end
          function GridNav:IsTraversable() return true end
          function GridNav:GetAllTreesAroundPoint(p, r, full)
            local out = {}
            for _, t in ipairs(__trees) do
              if math.sqrt((t.pos.x - p.x) ^ 2 + (t.pos.y - p.y) ^ 2) <= r then out[#out + 1] = t end
            end
            return out
          end
          function GetTreeIdForEntityIndex(i) return 9000 + i end
          DOTA_UNIT_ORDER_CAST_TARGET_TREE = 7""")
        self.start_match()
        sniper = self.hero(1)
        self.decide(2, 1, {"plan": "farm", "where": "bot"})
        self.step(0.5)
        self.assertIs(sniper["idle_acquire"], False)                          # на фарме — только добивания
        self.decide(2, 1, {"plan": "push", "where": "bot"})
        self.step(0.5)
        self.assertIs(sniper["idle_acquire"], True)
        sniper["pos"] = self.L.eval("Vector(0, -3000, 0)")
        tree = self.L.eval("(function() local t = { pos = Vector(150, -3000, 0) }; t.idx = 777; "
                           "function t:GetAbsOrigin() return self.pos end; function t:entindex() return self.idx end; "
                           "__trees[1] = t; return t end)()")
        tango = self.L.eval('__players[1].hero:AddItemByName("item_tango")')
        sniper["health"] = 400                                                 # 66 %
        self.decide(2, 1, {"plan": "hold"})
        n0 = self.n_orders()
        self.step(0.5)
        eat = [o for o in self.unit_orders(sniper, n0) if o["OrderType"] == 7]
        self.assertEqual((eat[0]["AbilityIndex"], eat[0]["TargetIndex"]), (tango["idx"], 9000 + 777))
        n_try = self.n_orders()                                              # не съел (здоровье то же) — не замирает:
        self.step(6)                                                          # следующая попытка не раньше чем через 20 с
        self.assertEqual(len([o for o in self.unit_orders(sniper, n_try) if o["OrderType"] == 7]), 0)
        # дерево у вражеской вышки не годится: Т1 Тьмы на боте (6200, -1600)
        self.assertIsNone(self.L.eval('require("coach_world").safe_tree(2, Vector(6200, -2200, 0), 400, 900)'))
        sniper["pos"] = self.L.eval("Vector(-6800, -6300, 0)")                # у фонтана
        self.decide(2, 1, {"plan": "hold", "buy": ["item_ward_observer"]})
        self.step(0.5)
        self.assertTrue(any(it and it["name"] == "item_ward_observer" for it in sniper["slots"].values()))

    def test_consumables_reflex(self):
        """Лечилка и кларити — когда ранен и врага рядом нет; палочка и волшебный огонь — когда здоровья мало и враг
        рядом. Из рюкзака — нет."""
        self.start_match()
        sniper, luna = self.hero(1), self.by_name("luna")
        sniper["pos"] = self.L.eval("Vector(0, 0, 0)")
        luna["pos"] = self.L.eval("Vector(5000, 5000, 0)")                   # врага рядом нет
        flask = self.L.eval('__players[1].hero:AddItemByName("item_flask")')
        self.decide(2, 1, {"plan": "hold"})
        sniper["health"] = 300                                                # 50 %
        n0 = self.n_orders()
        self.step(0.5)
        got = [o for o in self.unit_orders(sniper, n0) if o["OrderType"] == ORDER["cast_target"]]
        self.assertEqual((got[0]["AbilityIndex"], got[0]["TargetIndex"]), (flask["idx"], sniper["idx"]))
        sniper["mods"]["modifier_flask_healing"] = True                       # уже лечится — второй не пьёт
        n1 = self.n_orders()
        self.step(1.5)
        self.assertFalse([o for o in self.unit_orders(sniper, n1) if o.get("AbilityIndex") == flask["idx"]])
        ff = self.L.eval('__players[1].hero:AddItemByName("item_faerie_fire")')
        ff["behavior"] = 4
        luna["pos"] = self.L.eval("Vector(300, 0, 0)")                        # враг вплотную
        sniper["health"] = 120                                                # 20 %
        n2 = self.n_orders()
        self.step(1.5)
        self.assertTrue([o for o in self.unit_orders(sniper, n2)
                         if o["OrderType"] == ORDER["cast_none"] and o["AbilityIndex"] == ff["idx"]])

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


class Learning(Game):
    """Д20: игра даёт агентам то, на чём они учатся: «запомни …» тренера дословно, вражеских крипов, умерших рядом с
    героем (пропущенные добивания), простой рук и конец матча с победителем."""
    decide = Executor.decide
    lua = Executor.lua

    def test_remember_parse(self):
        rp = self.G["CoachGame"]["remember_parse"]
        who, lesson = rp("1 запомни: стой дальше от вышки")
        self.assertEqual((list(who.values()), lesson), ([1], "стой дальше от вышки"))
        who, lesson = rp("Запомни Не ходи под вышку без союзников")
        self.assertEqual((list(who.values()), lesson), ([1, 2, 3, 4, 5], "Не ходи под вышку без союзников"))
        who, _ = rp("все-1 запомни — денай дальнего крипа")
        self.assertEqual(list(who.values()), [2, 3, 4, 5])
        who, _ = rp("23 запомни бей керри врага")
        self.assertEqual(list(who.values()), [2, 3])
        self.assertIsNone(rp("1 фарм бот"))
        self.assertIsNone(rp("запомни"))
        self.assertIsNone(rp("снайпер, пожалуйста, запомни это"))             # не наш формат — дальше парсер

    def test_remember_from_chat_reaches_agents(self):
        self.start_match()
        self.G["CoachGame"]["OnChat"](self.G["CoachGame"], self.L.table_from(
            {"playerid": 0, "text": "1 запомни: стой у своей волны"}))
        self.step(1.5)
        sent = self.payloads()[-1]
        mine = next(h for h in sent["heroes"] if h["team"] == "radiant" and h["pos"] == 1)
        self.assertEqual(mine["coach"][-1]["remember"], "стой у своей волны")
        other = next(h for h in sent["heroes"] if h["team"] == "radiant" and h["pos"] == 2)
        self.assertFalse([c for c in other["coach"] if c.get("remember")])

    def test_seen_idle_and_match_end(self):
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(2000, -5000, 0)")
        self.decide(2, 1, {"plan": "hold"})                                   # стоит — простой рук
        near = self.L.eval("__creep(3, 2300, -5000, 0)")
        far = self.L.eval("__creep(3, 4000, -5000, 0)")
        mine = self.L.eval("__creep(2, 2100, -5000, 0)")
        for c in (near, far, mine):
            c["alive"] = False
            self.L.execute(f"__fire('entity_killed', {{ entindex_killed = {c['idx']} }})")
        self.step(3)
        sent = self.payloads()[-1]
        me = next(h for h in sent["heroes"] if h["team"] == "radiant" and h["pos"] == 1)
        self.assertEqual(me["stats"]["seen"], 1)                              # только вражеский и рядом
        self.assertGreaterEqual(me["stats"]["idle"], 2)
        self.L.execute("__fire('dota_match_done', { winningteam = 3 })")
        G = self.G["CoachGame"]
        payload = G["TickPayload"](G, self.G["__now"])
        self.assertEqual(payload["ended"]["winner"], "dire")


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
        self.assertEqual((o["OrderType"], self.xy(o)), (ORDER["move"], (6200, -4500)))   # «сам» без агента — фарм своей линии

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


class FindBotHeroes(Game):
    """Игра на связи, а героев агентам не досталось (первый живой матч): находим героев ботов не одним путём."""

    def agents(self, team=2):
        T = self.G["CoachGame"]["teams"][team]
        return [T["agents"][p]["name"].replace("npc_dota_hero_", "") for p in range(1, 6) if T["agents"][p]]

    def test_selected_hero_nil_for_bots(self):
        self.L.execute("""
          local sel = PlayerResource.GetSelectedHeroEntity
          function PlayerResource:GetSelectedHeroEntity(pid)
            if __players[pid] and __players[pid].fake then return nil end   -- для ботов Дота не отдаёт героя
            return sel(self, pid)
          end""")
        self.start_match()
        self.assertEqual(self.agents(2), ["sniper", "viper", "axe", "lion", "crystal_maiden"])   # из списка героев
        self.assertEqual(len(self.agents(3)), 5)
        n0 = self.n_orders()
        self.step(1)
        self.assertTrue(self.unit_orders(self.hero(1), n0))

    def test_only_hero_list_knows_them(self):
        """Ни выбранного героя у ботов, ни события появления — герои есть только в списке всех героев."""
        self.L.execute("""
          local sel = PlayerResource.GetSelectedHeroEntity
          function PlayerResource:GetSelectedHeroEntity(pid)
            if __players[pid] and __players[pid].fake then return nil end
            return sel(self, pid)
          end""")
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP)")
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_HERO_SELECTION)")
        self.step(2.5)
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_PRE_GAME)")
        self.step(1.5)
        self.assertEqual(len(self.agents(2)), 5)
        self.assertEqual(len(self.agents(3)), 5)

    def test_bot_heroes_without_owner(self):
        self.L.execute("""
          local add = Tutorial.AddBot
          function Tutorial:AddBot(hero, lane, difficulty, good)
            local ok = add(self, hero, lane, difficulty, good)
            for pid, p in pairs(__players) do
              if p.fake then function p.hero:GetPlayerOwnerID() return -1 end end   -- владелец не указан
            end
            return ok
          end""")
        self.start_match()
        self.assertEqual(len(self.agents(2)), 5)
        self.assertEqual(len(self.agents(3)), 5)
        self.assertTrue(self.hero(0)["nodraw"])                              # тренер — по-прежнему не агент

    def test_hero_after_setup_goes_to_agent(self):
        self.L.execute(LATE_HEROES)
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP)")
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_HERO_SELECTION)")
        self.step(2.5)
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_PRE_GAME)")
        self.step(32)                                                         # не дождались: раздали, что есть
        self.assertEqual(self.agents(2), [])
        self.L.execute("__reveal()")
        for pid in range(1, 11):
            self.L.execute(f"__fire('npc_spawned', {{ entindex = __players[{pid}].hero.idx, is_respawn = 0 }})")
        self.assertEqual(self.agents(2), ["sniper", "viper", "axe", "lion", "crystal_maiden"])
        late = [line for line in self.G["__printed"].values() if "появился позже" in line]
        self.assertEqual(len(late), 10)
        self.L.execute("__fire('npc_spawned', { entindex = __players[1].hero.idx, is_respawn = 1 })")
        self.assertEqual(len(self.agents(2)), 5)                              # возрождение — не новый агент
        n0 = self.n_orders()
        self.step(1)
        self.assertTrue(self.unit_orders(self.hero(1), n0))

    def test_bot_heroes_owned_by_human(self):
        """Повторная проверка: если Дота назовёт владельцем героев ботов человека (он ими управляет — живой матч),
        героев всё равно получают агенты; прячется только выбранный герой человека."""
        self.L.execute("""
          local add = Tutorial.AddBot
          function Tutorial:AddBot(hero, lane, difficulty, good)
            local ok = add(self, hero, lane, difficulty, good)
            for pid, p in pairs(__players) do
              if p.fake then function p.hero:GetPlayerOwnerID() return 0 end end   -- «владелец» — человек 0
            end
            return ok
          end""")
        self.start_match()
        self.assertEqual(self.agents(2), ["sniper", "viper", "axe", "lion", "crystal_maiden"])
        self.assertEqual(len(self.agents(3)), 5)
        self.assertTrue(self.hero(0)["nodraw"])                               # герой тренера спрятан
        self.assertFalse(any(self.hero(p)["nodraw"] for p in range(1, 11)))   # герои ботов — нет
        line = [x for x in self.G["__printed"].values() if "герои агентов:" in x][0]
        self.assertIn("по номеру бота 10", line)

    def test_bot_hero_spawning_before_coach_hero_not_hidden(self):
        """Повторная проверка (узкий случай): владелец героев ботов — человек, и герой бота появился раньше, чем у
        человека назначен выбранный герой — прятать его как героя тренера нельзя."""
        self.L.execute("""
          local add = Tutorial.AddBot
          function Tutorial:AddBot(hero, lane, difficulty, good)
            local ok = add(self, hero, lane, difficulty, good)
            for pid, p in pairs(__players) do
              if p.fake then function p.hero:GetPlayerOwnerID() return 0 end end
            end
            return ok
          end
          local sel = PlayerResource.GetSelectedHeroEntity
          __coach_ready = false
          function PlayerResource:GetSelectedHeroEntity(pid)
            if pid == 0 and not __coach_ready then return nil end      -- выбранный герой человека ещё не назначен
            return sel(self, pid)
          end""")
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP)")
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_HERO_SELECTION)")
        self.step(2.5)
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_PRE_GAME)")
        self.L.execute("__fire('npc_spawned', { entindex = __players[1].hero.idx, is_respawn = 0 })")   # бот — первым
        self.L.execute("__coach_ready = true")
        for pid in [0] + list(range(2, 11)):
            self.L.execute(f"__fire('npc_spawned', {{ entindex = __players[{pid}].hero.idx, is_respawn = 0 }})")
        self.step(1.5)
        self.assertFalse(self.hero(1)["nodraw"])                              # sniper не спрятан
        self.assertTrue(self.hero(0)["nodraw"])                               # спрятан герой человека
        self.assertEqual(self.agents(2), ["sniper", "viper", "axe", "lion", "crystal_maiden"])

    def test_coach_hero_before_selection_hidden_by_name(self):
        """Повторная проверка: герой человека появился раньше, чем назначен выбранный, — прячется по имени выбранного."""
        self.L.execute("""
          local sel = PlayerResource.GetSelectedHeroEntity
          __coach_ready = false
          function PlayerResource:GetSelectedHeroEntity(pid)
            if pid == 0 and not __coach_ready then return nil end
            return sel(self, pid)
          end""")
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP)")
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_HERO_SELECTION)")
        self.step(2.5)
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_PRE_GAME)")
        self.L.execute("__fire('npc_spawned', { entindex = __players[0].hero.idx, is_respawn = 0 })")
        self.assertTrue(self.hero(0)["nodraw"])
        self.L.execute("__coach_ready = true")
        self.step(1.5)
        self.assertNotIn("pudge", self.agents(2))

    def test_coach_hero_without_owner_is_not_agent(self):
        self.L.execute("__players[0].hero.GetPlayerOwnerID = function() return -1 end")   # у героя тренера нет владельца
        self.start_match()
        self.assertEqual(self.agents(2), ["sniper", "viper", "axe", "lion", "crystal_maiden"])
        self.assertNotIn("pudge", self.agents(2) + self.agents(3))
        self.assertTrue(self.hero(0)["nodraw"])                               # и спрятан — по самому герою

    def test_setup_error_still_gives_heroes(self):
        self.L.execute("function CoachGame:TrySetup() error('сломалось ожидание') end")
        self.start_match()
        self.assertTrue(self.G["CoachGame"]["ready"])
        self.assertTrue(any("ошибка при ожидании героев ботов" in line for line in self.G["__printed"].values()))
        self.assertEqual(len(self.agents(2)), 5)


NAMED_BOTS = """
__named = {}
function GameRules:AddBotPlayerWithEntityScript(hero, name, team, script, flag)
  if __named_fail then return nil end
  local pid = 0
  while __players[pid] do pid = pid + 1 end
  local p = { team = team, fake = true, name = name, hero = __make_hero(hero, team, pid) }
  p.hero.pos = Vector(0, 0, 0)                                  -- такой бот появляется в центре карты
  __players[pid] = p
  __named[#__named + 1] = name
  return p.hero
end
local tut = Tutorial.AddBot
__tutorial = 0
function Tutorial:AddBot(...) __tutorial = __tutorial + 1; return tut(self, ...) end
"""


class NamedAgentBots(Game):
    """Д17: агенты — отдельные игроки под своими именами («Claude N · Герой»), мышью тренер тоже может."""

    def agents(self, team=2):
        T = self.G["CoachGame"]["teams"][team]
        return [T["agents"][p]["name"].replace("npc_dota_hero_", "") for p in range(1, 6) if T["agents"][p]]

    def test_names_off_by_default(self):
        """Рецензия 9: до проверочного выпуска — прежние боты Tutorial:AddBot, хоть функция в Доте и есть."""
        self.L.execute(NAMED_BOTS)
        self.start_match()
        self.assertEqual(list(self.G["__named"].values()), [])
        self.assertEqual(self.G["__tutorial"], 10)
        self.assertEqual(len(self.agents(2)), 5)

    def test_names_in_order_when_precache_finishes_backwards(self):
        """Рецензия 9: предзагрузки кончились в обратном порядке — боты всё равно создаются по порядку позиций."""
        self.L.execute(NAMED_BOTS)
        self.L.execute("""
          CoachGame.NAMED_BOTS = true
          __pending = {}
          function PrecacheUnitByNameAsync(name, cb) __pending[#__pending + 1] = cb end""")
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_CUSTOM_GAME_SETUP)")
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_HERO_SELECTION)")
        self.step(2.5)
        self.L.execute("for i = #__pending, 1, -1 do __pending[i](1) end")
        self.assertEqual(list(self.G["__named"].values())[:5],
                         ["Claude 1 · Sniper", "Claude 2 · Viper", "Claude 3 · Axe", "Claude 4 · Lion",
                          "Claude 5 · Crystal Maiden"])
        self.L.execute("__set_state(DOTA_GAMERULES_STATE_PRE_GAME)")
        self.step(1.5)
        self.assertEqual(self.agents(2), ["sniper", "viper", "axe", "lion", "crystal_maiden"])

    def test_seated_without_hero_no_second_bot(self):
        """Рецензия 9: Дота посадила бота, но героя не вернула (создаст позже) — запасного бота не добавлять."""
        self.L.execute(NAMED_BOTS)
        self.L.execute("""
          CoachGame.NAMED_BOTS = true
          local named = GameRules.AddBotPlayerWithEntityScript
          function GameRules:AddBotPlayerWithEntityScript(...)
            named(self, ...)
            return nil                                                    -- игрок есть, героя «пока нет»
          end""")
        self.start_match()
        self.assertEqual(self.G["__tutorial"], 0)
        bots = [p for p in self.G["__players"].values() if p["fake"]]
        self.assertEqual(len(bots), 10)

    def test_bots_named_at_fountain_and_shared_with_coach(self):
        self.L.execute(NAMED_BOTS)
        self.L.execute("CoachGame.NAMED_BOTS = true")
        self.start_match()
        self.assertEqual(list(self.G["__named"].values()),
                         ["Claude 1 · Sniper", "Claude 2 · Viper", "Claude 3 · Axe", "Claude 4 · Lion",
                          "Claude 5 · Crystal Maiden", "Claude 1 · Luna", "Claude 2 · Lina", "Claude 3 · Bristleback",
                          "Claude 4 · Witch Doctor", "Claude 5 · Jakiro"])
        self.assertEqual(self.G["__tutorial"], 0)                                 # обычных ботов не понадобилось
        self.assertEqual(len(list(self.G["__precached"].values())), 10)          # герои — заранее в память
        for pid in range(1, 11):                                                   # не в центре карты — у фонтана
            pos = self.hero(pid)["pos"]
            self.assertGreater(abs(pos["x"]) + abs(pos["y"]), 10000, pid)
        self.assertEqual(len(self.agents(2)), 5)
        self.assertEqual(len(self.agents(3)), 5)
        shared = [(e["pid"], e["other"], e["flag"]) for e in self.G["__shared"].values()]
        self.assertEqual(sorted(shared), sorted([(p, 0, f) for p in range(1, 6) for f in (1, 2)]))   # только Свет
        n0 = self.n_orders()
        self.step(1)
        self.assertTrue(self.unit_orders(self.hero(1), n0))

    def test_named_bots_refused_fall_back_to_tutorial(self):
        self.L.execute(NAMED_BOTS)
        self.L.execute("CoachGame.NAMED_BOTS = true; __named_fail = true")
        self.start_match()
        self.assertEqual(self.G["__tutorial"], 10)
        refused = [x for x in self.G["__printed"].values() if "под именем агента не создался" in x]
        self.assertEqual(len(refused), 1)                                         # один раз, не на каждого бота
        self.assertEqual(len(self.agents(2)), 5)
        self.assertEqual(len(self.agents(3)), 5)


class LaneMiddle(Game):
    """Живой матч 10.10.2026: «акс и леон застряли в деревьях». Середина отрезка между вышками изогнутой линии лежит
    в лесу; теперь — середина пути по линии через угол карты, а точка в деревьях сдвигается к своей вышке."""

    def lane_mid(self, team, lane):
        p = self.L.eval(f'CoachGame and require("coach_world").lane_mid({team}, "{lane}")')
        return (round(p["x"]), round(p["y"]))

    def test_mid_along_lane_not_in_forest(self):
        self.start_match()
        self.assertEqual(self.lane_mid(2, "bot"), (6200, -4500))     # Свет: вдоль низа, потом вверх по правому краю
        self.assertEqual(self.lane_mid(2, "top"), (-6200, 4650))     # Свет: вверх по левому краю
        self.assertEqual(self.lane_mid(3, "top"), (-6200, 4650))     # та же точка с другой стороны — встреча волн
        self.assertEqual(self.lane_mid(2, "mid"), (-500, -375))      # мид прямой — середина отрезка
        n0 = self.n_orders()
        self.step(1)
        axe = self.unit_orders(self.by_name("axe"), n0)[-1]           # Axe (3) — на сложной линии Света (верх)
        self.assertEqual(self.xy(axe), (-6200, 4650))

    def test_farm_follows_own_wave(self):
        """Живой матч: на 15-й минуте 4–5 уровень — герои ждали волну в расчётной точке. Теперь — к своей волне."""
        self.start_match()
        sniper = self.hero(1)                                        # керри Света — бот
        sniper["pos"] = self.L.eval("Vector(5000, -6000, 0)")
        self.L.eval("__creep(2, 6150, -3600, 550)")                  # свои крипы на боте, дальше по линии
        self.L.eval("__creep(2, 6200, -3000, 550)")                  # передовой
        self.L.eval("__creep(2, 1000, -2000, 550)")                  # в лесу, далеко от линии — не в счёт
        n0 = self.n_orders()
        self.step(1)
        o = self.unit_orders(sniper, n0)[-1]
        x, y = self.xy(o)
        self.assertEqual(o["OrderType"], ORDER["move"])
        self.assertLess(((x - 6200) ** 2 + (y + 3000) ** 2) ** 0.5, 300)   # чуть позади передового крипа
        _, rows = self.hud_rows()
        self.assertIn("к своей волне", rows[0]["status"])

    def test_wave_at_enemy_tower_stays_out_of_range(self):
        """Рецензия 10: своя волна у вражеской вышки — герой не встаёт под неё."""
        self.start_match()
        sniper = self.hero(1)
        sniper["pos"] = self.L.eval("Vector(6000, -4000, 0)")
        self.L.eval("__creep(2, 6200, -2100, 550)")                  # своя волна у их Т1 боте (6200, -1600)
        n0 = self.n_orders()
        self.step(1)
        x, y = self.xy(self.unit_orders(sniper, n0)[-1])
        self.assertGreaterEqual(((x - 6200) ** 2 + (y + 1600) ** 2) ** 0.5, 890)

    def test_corner_by_lane_name_when_towers_fall(self):
        self.start_match()
        for t in self.G["__towers"].values():
            if t["name"].endswith("_top"):
                t["alive"] = False                                   # пали все вышки топа
        x, y = self.lane_mid(2, "top")
        self.assertLess(x, 0)                                        # точка на верхней линии (слева вверху),
        self.assertGreater(y, 0)                                     # а не в углу нижней

    def test_point_in_trees_moves_toward_own_tower(self):
        self.L.execute("""
          GridNav = {}
          function GridNav:IsNearbyTree(p, r, full) return p.y > 3500 and p.y < 5000 and p.x < -5800 end   -- рощица
          function GridNav:IsTraversable(p) return true end""")
        self.start_match()
        x, y = self.lane_mid(2, "top")
        self.assertEqual(x, -6200)
        self.assertLessEqual(y, 3500)                                 # вышла из деревьев — к своей вышке (-6200, 1800)
        self.assertGreater(y, 1800)


class GameMovesHidden(Game):
    """Рецензия 7: приказы соперника (ИИ-тренер Тьмы, Д16: «его приказы в окно не пишутся») и реплики — ходы игры;
    в окно хоста из консоли Доты они не попадают."""
    server = True

    def test_launcher_filter_hides_moves(self):
        from voicecoach import play as P
        self.start_match()
        room = self.srv.hub.room("local")
        self.step(2)
        room.remote_order("dire", "все назад")
        self.step(2)
        room.remote_order("dire", "летай куда хочешь")
        self.hud("1 фарм лес")
        self.hud("2 летай")
        self.step(5)
        lines = list(self.G["__printed"].values())
        self.assertTrue(any("приказ с пульта: все назад" in line for line in lines))   # в консоли есть
        shown = [line for line in lines if P.DotaLog.wanted(line)]
        for word in ("все назад", "летай", "фарм лес"):
            self.assertFalse([line for line in shown if word in line], word)
        self.assertTrue(any("пульс:" in line for line in shown))
        modes = [line for line in lines if "агенты на связи" in line]
        self.assertEqual(len(modes), 1, modes)                                 # «без решений: N» в консоль не скачет


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
