-- Карта и герои для агентов кастомки — через API Доты (vscripts). Интерфейс — как ждёт coach_agents.lua.
--
-- Ничего не захардкожено по координатам: вышки, фонтаны и Рошан находятся по классам сущностей
-- (npc_dota_tower, ent_dota_fountain, npc_dota_roshan — так их ищет и Windy10v10AI, сверено по коду);
-- линия и уровень вышки — из имени юнита («…_tower1_top»). Линия без живых вышек — фонтан.

local W = {}
W.towers = {}          -- { unit, team, lane, tier }
W.fountains = {}       -- team → точка
W.agents = {}          -- team → { [pos] = hero }, задаёт coach_game.lua

local function other(team)
  if team == DOTA_TEAM_GOODGUYS then return DOTA_TEAM_BADGUYS end
  return DOTA_TEAM_GOODGUYS
end

function W.init()
  W.towers, W.fountains = {}, {}
  for _, f in pairs(Entities:FindAllByClassname("ent_dota_fountain")) do
    W.fountains[f:GetTeamNumber()] = f:GetAbsOrigin()
  end
  for _, tower in pairs(Entities:FindAllByClassname("npc_dota_tower")) do
    local name = tower:GetUnitName()
    local lane = (name:find("_top", 1, true) and "top") or (name:find("_mid", 1, true) and "mid")
      or (name:find("_bot", 1, true) and "bot") or nil
    local tier = tonumber(name:match("tower(%d)"))
    if lane and tier then
      W.towers[#W.towers + 1] = { unit = tower, team = tower:GetTeamNumber(), lane = lane, tier = tier }
    end
  end
  return #W.towers, W.fountains[DOTA_TEAM_GOODGUYS] ~= nil and W.fountains[DOTA_TEAM_BADGUYS] ~= nil
end

function W.fountain(team)
  return W.fountains[team]
end

-- внешняя живая вышка команды на линии (меньший уровень — дальше от базы)
local function outer(team, lane)
  local best = nil
  for _, t in ipairs(W.towers) do
    if t.team == team and t.lane == lane and IsValidEntity(t.unit) and t.unit:IsAlive()
      and (best == nil or t.tier < best.tier) then
      best = t
    end
  end
  return best
end

function W.lane_front(team, lane)
  local t = outer(team, lane)
  return t and t.unit:GetAbsOrigin() or W.fountain(team)
end

function W.lane_enemy_front(team, lane)
  local t = outer(other(team), lane)
  return t and t.unit:GetAbsOrigin() or W.fountain(other(team))
end

function W.roshan()
  local unit = Entities:FindByClassname(nil, "npc_dota_roshan")
  if unit and IsValidEntity(unit) and unit:IsAlive() then return unit end
  return nil
end

function W.alive(hero)
  return hero ~= nil and IsValidEntity(hero) and hero:IsAlive()
end

function W.pos(unit)
  return unit:GetAbsOrigin()
end

function W.dist(a, b)
  return (a - b):Length2D()
end

-- виден ли юнит команде: хоть один живой агент команды его видит
local function visible(team, unit)
  for _, hero in pairs(W.agents[team] or {}) do
    if W.alive(hero) and hero:CanEntityBeSeenByMyTeam(unit) then return true end
  end
  return false
end

function W.enemy_by_pos(team, pos)
  local hero = (W.agents[other(team)] or {})[pos]
  if W.alive(hero) and visible(team, hero) then return hero end
  return nil
end

function W.enemy_hero(team, hero_name)
  for _, hero in pairs(W.agents[other(team)] or {}) do
    if W.alive(hero) and hero:GetUnitName() == hero_name and visible(team, hero) then return hero end
  end
  return nil
end

function W.ally_hero(team, pos)
  local hero = (W.agents[team] or {})[pos]
  if W.alive(hero) then return hero end
  return nil
end

function W.nearest_enemy(team, point)
  local best, best_d = nil, 1e18
  for _, hero in pairs(W.agents[other(team)] or {}) do
    if W.alive(hero) and visible(team, hero) then
      local d = W.dist(hero:GetAbsOrigin(), point)
      if d < best_d then best, best_d = hero, d end
    end
  end
  return best
end

function W.team_center(team)
  local sx, sy, n = 0, 0, 0
  for _, hero in pairs(W.agents[team] or {}) do
    if W.alive(hero) then
      local p = hero:GetAbsOrigin()
      sx, sy, n = sx + p.x, sy + p.y, n + 1
    end
  end
  if n == 0 then return W.fountain(team) end
  return Vector(sx / n, sy / n, 0)
end

-- ульта: способность с типом ABILITY_TYPE_ULTIMATE и уровнем ≥ 1
function W.ult(hero)
  for i = 0, hero:GetAbilityCount() - 1 do
    local ab = hero:GetAbilityByIndex(i)
    if ab and ab:GetAbilityType() == ABILITY_TYPE_ULTIMATE and ab:GetLevel() > 0 then return ab end
  end
  return nil
end

local function has_flag(value, flag)
  return math.floor(value / flag) % 2 == 1          -- без библиотеки bit: флаги — степени двойки
end

function W.ability_info(ab)
  local behavior = ab:GetBehaviorInt()
  local kind = "none"
  if has_flag(behavior, DOTA_ABILITY_BEHAVIOR_UNIT_TARGET) then kind = "target"
  elseif has_flag(behavior, DOTA_ABILITY_BEHAVIOR_POINT) then kind = "point" end
  return { ready = ab:IsFullyCastable(), behavior = kind, cooldown = ab:GetCooldownTimeRemaining() }
end

function W.item(hero, name)
  return hero:FindItemInInventory(name)
end

function W.can_buyback(hero)
  return PlayerResource:GetGold(hero:GetPlayerID()) >= hero:GetBuybackCost()
end

return W
