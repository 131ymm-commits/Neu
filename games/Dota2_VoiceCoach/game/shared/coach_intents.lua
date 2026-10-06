-- Намерения тренера → желания режимов бота.
--
-- Чистый Lua 5.1 / LuaJIT без API Доты: один и тот же модуль работает в ботах (bot scripts)
-- и в vscripts кастомки, а проверяется вне игры (game/tests, LuaJIT через lupa).
--
-- Модель: тренер даёт команду (протокол v1, docs/COMMANDS.md) → у каждого адресата появляется
-- текущее намерение с временем жизни; «потом …» ставит намерение в очередь. Бот на каждом
-- шаге спрашивает желание режима (как GetDesire в режимах ботов Valve): базовое желание
-- самого бота сдвигается характером игрока (persona) и поднимается до пола / срезается
-- до потолка намерением. Решает по-прежнему бот: намерение — сильный совет, не приказ на каждый шаг.

local M = {}

M.VERSION = 1

-- Время жизни намерений, с; копия ACTIONS[*].ttl_s из coach/voicecoach/protocol.py
-- (совпадение проверяет game/tests/test_intents.py).
M.TTL = {
  farm = 120, push = 60, defend = 60, gank = 60, group = 60, roshan = 90, tormentor = 60,
  smoke = 60, retreat = 20, focus = 20, engage = 20, hold = 30, split = 120, ward = 60,
  stack = 60, buy = 300, use_item = 10, buyback = 15, use_ult = 10, save_ult = 60, save = 10,
  follow = 60, tp = 15, move = 45, free = 0, cancel = 0, report = 0,
}

-- Режимы — по именам файлов режимов ботов (mode_<имя>_generic.lua).
M.MODES = {
  "laning", "attack", "roam", "retreat", "farm", "team_roam", "roshan", "ward", "rune",
  "push_tower_top", "push_tower_mid", "push_tower_bot",
  "defend_tower_top", "defend_tower_mid", "defend_tower_bot",
  "defend_ally", "assemble", "outpost", "secret_shop", "side_shop", "item", "evasive_maneuvers",
}

local LANES = { top = true, mid = true, bot = true }

-- К какому классу относится режим (для добавок характера).
local MODE_CLASS = {
  attack = "fight", roam = "fight", team_roam = "teamfight_join", defend_ally = "teamfight_join",
  farm = "farm", laning = "farm", ward = "ward",
}

local function clamp(x, lo, hi)
  if x < lo then return lo end
  if x > hi then return hi end
  return x
end

local function lane_of(mode)
  return mode:match("_(%a+)$")
end

-- Правила: что делает намерение с режимом. Возвращают (пол, потолок) или nil, nil.
-- Пол — желание не ниже; потолок — не выше.
local RULES = {}

RULES.farm = function(mode, it)
  if mode == "farm" then return 0.75, nil end
  if mode == "laning" then
    local area = it.params.area
    if area == "lane" then return 0.6, nil end
    return nil, 0.1
  end
  if mode:find("^push_tower_") or mode == "team_roam" or mode == "roam" then return nil, 0.3 end
  return nil, nil
end

RULES.push = function(mode, it)
  local lane = it.params.lane
  if mode:find("^push_tower_") then
    if lane == nil or lane == "auto" or not LANES[lane] then return 0.6, nil end
    if lane_of(mode) == lane then return 0.85, nil end
    return nil, 0.2
  end
  if mode == "farm" or mode == "laning" then return nil, 0.3 end
  return nil, nil
end
RULES.split = RULES.push

RULES.defend = function(mode, it)
  local lane = it.params.lane
  if mode:find("^defend_tower_") then
    if it.params.place == "base" or lane == nil or lane == "auto" then return 0.7, nil end
    if lane_of(mode) == lane then return 0.85, nil end
    return nil, nil
  end
  if mode == "farm" or mode:find("^push_tower_") then return nil, 0.3 end
  return nil, nil
end

RULES.gank = function(mode, it)
  if mode == "roam" then return 0.8, nil end
  if mode == "farm" or mode == "laning" then return nil, 0.3 end
  return nil, nil
end

RULES.group = function(mode, it)
  if mode == "assemble" or mode == "team_roam" then return 0.7, nil end
  if mode == "farm" then return nil, 0.3 end
  return nil, nil
end
RULES.follow = RULES.group
RULES.move = function(mode, it)
  if mode == "assemble" then return 0.75, nil end
  if mode == "farm" or mode == "laning" then return nil, 0.3 end
  return nil, nil
end

RULES.roshan = function(mode, it)
  if mode == "roshan" then return 0.9, nil end
  if mode == "farm" or mode == "laning" or mode:find("^push_tower_") then return nil, 0.25 end
  return nil, nil
end

RULES.tormentor = function(mode, it)
  if mode == "assemble" then return 0.8, nil end
  if mode == "farm" or mode == "laning" then return nil, 0.25 end
  return nil, nil
end

RULES.smoke = function(mode, it)
  if mode == "team_roam" or mode == "roam" then return 0.8, nil end
  if mode == "farm" or mode == "laning" then return nil, 0.25 end
  return nil, nil
end

RULES.retreat = function(mode, it)
  if mode == "retreat" then return 0.95, nil end
  if mode == "attack" or mode == "roam" or mode == "team_roam" or mode:find("^push_tower_")
    or mode == "roshan" then
    return nil, 0.1
  end
  return nil, nil
end

RULES.focus = function(mode, it)
  if mode == "attack" or mode == "team_roam" then return 0.8, nil end
  if mode == "farm" or mode == "laning" then return nil, 0.2 end
  return nil, nil
end
RULES.engage = RULES.focus

RULES.hold = function(mode, it)
  local what = it.params.what
  if what == "retreat" then
    if mode == "retreat" then return nil, 0.3 end
    return nil, nil
  end
  if what and what ~= "engage" and what ~= "focus" then
    -- «не пушьте», «не фармите лес»: срезаем режимы этого действия
    local rule = RULES[what]
    if rule then
      local floor = rule(mode, it)
      if floor then return nil, 0.15 end
    end
    return nil, nil
  end
  if mode == "attack" or mode == "roam" or mode == "team_roam" then return nil, 0.2 end
  return nil, nil
end

RULES.ward = function(mode, it)
  if mode == "ward" then return 0.8, nil end
  return nil, nil
end

RULES.stack = function(mode, it)
  if mode == "farm" then return 0.7, nil end
  return nil, nil
end

RULES.save = function(mode, it)
  if mode == "defend_ally" then return 0.85, nil end
  return nil, nil
end

-- Мгновенные действия (купить, выкупиться, ульта, предмет, тп) режимы не трогают:
-- их исполняют хуки покупки/способностей через M.pending_instant().
local INSTANT = { buy = true, buyback = true, use_ult = true, save_ult = false, use_item = true, tp = true }

function M.new(persona_by_pos)
  local st = { agents = {}, last_seq = 0, persona = persona_by_pos or {} }
  for pos = 1, 5 do st.agents[pos] = { current = nil, queue = {}, instant = {}, save_ult_until = 0 } end
  return st
end

local function make_intent(cmd, now)
  local ttl = cmd.ttl_s or M.TTL[cmd.action] or 30
  return {
    action = cmd.action, params = cmd.params or {}, seq = cmd.seq or 0, t0 = now,
    ttl = ttl, urgent = cmd.urgent and true or false, text = cmd.text,
  }
end

-- Применить команду. Возвращает список позиций, которым она дошла.
function M.apply(st, cmd, now)
  if cmd.seq and cmd.seq <= st.last_seq then return {} end
  if cmd.seq then st.last_seq = cmd.seq end
  local got = {}
  for _, pos in ipairs(cmd.agents or {}) do
    local a = st.agents[pos]
    if a then
      got[#got + 1] = pos
      if cmd.action == "cancel" or cmd.action == "free" then
        a.current, a.queue, a.instant, a.save_ult_until = nil, {}, {}, 0
      elseif cmd.action == "report" then
        -- доклад не меняет намерений
      elseif cmd.action == "save_ult" then
        a.save_ult_until = now + (M.TTL.save_ult or 60)
      elseif INSTANT[cmd.action] then
        a.instant[#a.instant + 1] = make_intent(cmd, now)
      else
        local it = make_intent(cmd, now)
        if cmd.after_prev and a.current then
          a.queue[#a.queue + 1] = it
        else
          a.current, a.queue = it, {}
        end
      end
    end
  end
  return got
end

-- Текущее намерение агента (с истечением и очередью).
function M.current(st, pos, now)
  local a = st.agents[pos]
  if not a then return nil end
  while a.current and now - a.current.t0 > a.current.ttl do
    a.current = table.remove(a.queue, 1)
    if a.current then a.current.t0 = now end
  end
  return a.current
end

-- Мгновенные намерения (купить, тп, ульта…), ещё не исполненные и не просроченные.
function M.pending_instant(st, pos, now)
  local a = st.agents[pos]
  if not a then return {} end
  local keep = {}
  for _, it in ipairs(a.instant) do
    if now - it.t0 <= it.ttl then keep[#keep + 1] = it end
  end
  a.instant = keep
  return keep
end

function M.done_instant(st, pos, seq)
  local a = st.agents[pos]
  if not a then return end
  for i, it in ipairs(a.instant) do
    if it.seq == seq then table.remove(a.instant, i) return end
  end
end

function M.ult_held(st, pos, now)
  local a = st.agents[pos]
  return a ~= nil and now < a.save_ult_until
end

-- Добавка характера к режиму: persona.desire_bonus[класс] (−0.2..+0.2, см. digitizer/twin/agent_params.py).
function M.persona_bonus(st, pos, mode)
  local p = st.persona[pos]
  if not p or not p.desire_bonus then return 0 end
  local cls = MODE_CLASS[mode]
  if not cls then return 0 end
  return p.desire_bonus[cls] or 0
end

-- Главное: итоговое желание режима для агента.
function M.desire(st, pos, mode, base, now)
  local d = (base or 0) + M.persona_bonus(st, pos, mode)
  local it = M.current(st, pos, now)
  if it then
    local rule = RULES[it.action]
    if rule then
      local floor, cap = rule(mode, it)
      local obedience = 1
      local p = st.persona[pos]
      if p and p.obedience then obedience = p.obedience end
      if floor then
        -- непослушный агент поднимает желание не до пола, а частично
        local target = floor + (it.urgent and 0.05 or 0)
        if target > d then d = d + (target - d) * obedience end
      end
      if cap and d > cap then
        d = d - (d - cap) * obedience
      end
    end
  end
  return clamp(d, 0, 1)
end

return M
