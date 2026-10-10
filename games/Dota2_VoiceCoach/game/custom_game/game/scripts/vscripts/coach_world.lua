-- Карта и герои через API Доты (vscripts) — для исполнителя (coach_exec.lua) и наблюдения (coach_obs.lua).
--
-- Ничего не захардкожено по координатам: вышки, фонтаны и Рошан находятся по классам сущностей
-- (npc_dota_tower, ent_dota_fountain, npc_dota_roshan — так их ищет и Windy10v10AI, сверено по коду);
-- линия и уровень вышки — из имени юнита («…_tower1_top»). Линия без живых вышек — фонтан.
-- Имена функций Valve сверяет game/tests/test_api_names.py по @moddota/dota-data.

local W = {}
W.towers = {}          -- { unit, team, lane, tier, pos } — pos запомнен: у разрушенной вышки сущности уже нет
W.fountains = {}       -- team → точка
W.agents = {}          -- team → { [pos] = hero }, задаёт coach_game.lua
W.seen = {}            -- team → { [имя героя врага] = { pos, t } } — где враг был виден последний раз
W.LANES = { "top", "mid", "bot" }

function W.other(team)
  if team == DOTA_TEAM_GOODGUYS then return DOTA_TEAM_BADGUYS end
  return DOTA_TEAM_GOODGUYS
end

function W.init()
  W.towers, W.fountains, W.seen = {}, {}, {}
  for _, f in pairs(Entities:FindAllByClassname("ent_dota_fountain")) do
    W.fountains[f:GetTeamNumber()] = f:GetAbsOrigin()
  end
  for _, tower in pairs(Entities:FindAllByClassname("npc_dota_tower")) do
    local name = tower:GetUnitName()
    local lane = (name:find("_top", 1, true) and "top") or (name:find("_mid", 1, true) and "mid")
      or (name:find("_bot", 1, true) and "bot") or nil
    local tier = tonumber(name:match("tower(%d)"))
    if lane and tier then
      W.towers[#W.towers + 1] = { unit = tower, team = tower:GetTeamNumber(), lane = lane, tier = tier,
                                  pos = tower:GetAbsOrigin() }
    end
  end
  return #W.towers, W.fountains[DOTA_TEAM_GOODGUYS] ~= nil and W.fountains[DOTA_TEAM_BADGUYS] ~= nil
end

function W.fountain(team)
  return W.fountains[team]
end

local function tower_alive(t)
  return IsValidEntity(t.unit) and t.unit:IsAlive()
end

W.tower_alive = tower_alive

-- внешняя живая вышка команды на линии (меньший уровень — дальше от базы)
local function outer(team, lane)
  local best = nil
  for _, t in ipairs(W.towers) do
    if t.team == team and t.lane == lane and tower_alive(t) and (best == nil or t.tier < best.tier) then
      best = t
    end
  end
  return best
end

function W.lane_front(team, lane)
  local t = outer(team, lane)
  return t and t.pos or W.fountain(team)
end

function W.lane_enemy_front(team, lane)
  local t = outer(W.other(team), lane)
  return t and t.pos or W.fountain(W.other(team))
end

-- точка на ломаной pts, пройдя долю frac её длины
function W.along(pts, frac)
  local total = 0
  for i = 2, #pts do total = total + W.dist(pts[i - 1], pts[i]) end
  local left = total * frac
  for i = 2, #pts do
    local seg = W.dist(pts[i - 1], pts[i])
    if seg > 0 and left <= seg then
      local t = left / seg
      return Vector(pts[i - 1].x + (pts[i].x - pts[i - 1].x) * t, pts[i - 1].y + (pts[i].y - pts[i - 1].y) * t, 0)
    end
    left = left - seg
  end
  return Vector(pts[#pts].x, pts[#pts].y, 0)
end

W.CLEAR_STEP, W.CLEAR_STEPS, W.TREE_R = 200, 15, 150

-- точка в деревьях или непроходима — шагами по CLEAR_STEP к toward (по линии к своей вышке); нет навигации — как есть
function W.clear(p, toward)
  if GridNav == nil then return p end
  local function bad(q)
    local ok, res = pcall(function() return GridNav:IsNearbyTree(q, W.TREE_R, true) or not GridNav:IsTraversable(q) end)
    return ok and res
  end
  local q = p
  for _ = 1, W.CLEAR_STEPS do
    if not bad(q) then return q end
    local d = W.dist(q, toward)
    if d <= W.CLEAR_STEP then return toward end
    local t = W.CLEAR_STEP / d
    q = Vector(q.x + (toward.x - q.x) * t, q.y + (toward.y - q.y) * t, 0)
  end
  return p
end

-- середина линии — там встречаются волны, пока вышки стоят. Считается по самой линии: верхняя и нижняя линии идут
-- углом вдоль края карты, и середина отрезка между вышками попадала в лес (живой матч 10.10.2026: «акс и леон
-- застряли в деревьях»). Путь: своя вышка → угол → их вышка; угол — тот из двух вариантов, что дальше от центра
-- карты (линии огибают карту по краю); точка в деревьях — сдвигается к своей вышке.
function W.lane_mid(team, lane)
  local a, b = W.lane_front(team, lane), W.lane_enemy_front(team, lane)
  local pts = { a, b }
  if lane ~= "mid" then
    local c1, c2 = Vector(a.x, b.y, 0), Vector(b.x, a.y, 0)
    pts = { a, (c1.x * c1.x + c1.y * c1.y >= c2.x * c2.x + c2.y * c2.y) and c1 or c2, b }
  end
  return W.clear(W.along(pts, 0.5), a)
end

-- уровень внешней живой вышки на каждой линии (0 — на линии вышек не осталось)
function W.tower_tiers(team)
  local out = {}
  for _, lane in ipairs(W.LANES) do
    local t = outer(team, lane)
    out[lane] = t and t.tier or 0
  end
  return out
end

function W.roshan()
  local unit = Entities:FindByClassname(nil, "npc_dota_roshan")
  if unit and IsValidEntity(unit) and unit:IsAlive() then return unit end
  return nil
end

function W.alive(unit)
  return unit ~= nil and IsValidEntity(unit) and unit:IsAlive()
end

function W.pos(unit)
  return unit:GetAbsOrigin()
end

function W.dist(a, b)
  return (a - b):Length2D()
end

function W.name(unit)
  return unit:GetUnitName()
end

function W.short(name)
  return (tostring(name or ""):gsub("^npc_dota_hero_", ""))
end

function W.hp(unit) return unit:GetHealth() end
function W.max_hp(unit) return unit:GetMaxHealth() end
function W.hp_pct(unit) return unit:GetHealthPercent() end

-- «где» словами для агента: линия и ближайшая вышка (своя или их) с расстоянием; у фонтана — база
function W.zone(team, point)
  local own, enemy = W.fountain(team), W.fountain(W.other(team))
  if own and W.dist(point, own) < 2500 then return "своя база" end
  if enemy and W.dist(point, enemy) < 2500 then return "их база" end
  local best, bd = nil, 1e18
  for _, t in ipairs(W.towers) do
    local d = W.dist(t.pos, point)
    if d < bd then best, bd = t, d end
  end
  if best == nil then return "?" end
  local whose = best.team == team and "своя" or "их"
  if bd > 2200 then
    local side = (own and enemy and W.dist(point, own) < W.dist(point, enemy)) and "наша половина" or "их половина"
    return string.format("%s, между линиями (ближе всего %s Т%d %s)", side, whose, best.tier, best.lane)
  end
  return string.format("%s, %s Т%d%s, %d", best.lane, whose, best.tier, tower_alive(best) and "" or " (снесена)",
    math.floor(bd + 0.5))
end

-- виден ли юнит команде: хоть один живой агент команды его видит
function W.visible(team, unit)
  for _, hero in pairs(W.agents[team] or {}) do
    if W.alive(hero) and hero:CanEntityBeSeenByMyTeam(unit) then return true end
  end
  return false
end

function W.enemy_heroes(team)
  local out = {}
  for _, hero in pairs(W.agents[W.other(team)] or {}) do out[#out + 1] = hero end
  return out
end

function W.enemy_by_pos(team, pos)
  local hero = (W.agents[W.other(team)] or {})[pos]
  if W.alive(hero) and W.visible(team, hero) then return hero end
  return nil
end

-- герой врага по имени (полному или короткому), только если его видно
function W.enemy_hero(team, name)
  local short = W.short(name)
  for _, hero in pairs(W.agents[W.other(team)] or {}) do
    if W.alive(hero) and W.short(hero:GetUnitName()) == short and W.visible(team, hero) then return hero end
  end
  return nil
end

function W.ally_hero(team, pos)
  local hero = (W.agents[team] or {})[pos]
  if W.alive(hero) then return hero end
  return nil
end

function W.nearest_enemy(team, point, max_dist)
  local best, best_d = nil, max_dist or 1e18
  for _, hero in pairs(W.agents[W.other(team)] or {}) do
    if W.alive(hero) and W.visible(team, hero) then
      local d = W.dist(hero:GetAbsOrigin(), point)
      if d < best_d then best, best_d = hero, d end
    end
  end
  return best
end

-- видимые живые враги не дальше radius от точки
function W.enemies_near(team, point, radius)
  local out = {}
  for _, hero in pairs(W.agents[W.other(team)] or {}) do
    if W.alive(hero) and W.visible(team, hero) and W.dist(hero:GetAbsOrigin(), point) <= radius then
      out[#out + 1] = hero
    end
  end
  return out
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

-- запомнить, где враги видны сейчас (для «давно не видно»)
function W.update_seen(team, now)
  W.seen[team] = W.seen[team] or {}
  for _, hero in pairs(W.agents[W.other(team)] or {}) do
    if W.alive(hero) and W.visible(team, hero) then
      W.seen[team][W.short(hero:GetUnitName())] = { pos = hero:GetAbsOrigin(), t = now }
    end
  end
end

function W.last_seen(team, name)
  return (W.seen[team] or {})[W.short(name)]
end

-- крипы линий рядом с героем, которых видно: enemy = true — вражеские, false — свои; нейтралы не входят
function W.lane_creeps(hero, radius, enemy)
  local team = hero:GetTeamNumber()
  local filter = enemy and DOTA_UNIT_TARGET_TEAM_ENEMY or DOTA_UNIT_TARGET_TEAM_FRIENDLY
  local units = FindUnitsInRadius(team, hero:GetAbsOrigin(), nil, radius, filter, DOTA_UNIT_TARGET_BASIC,
    DOTA_UNIT_TARGET_FLAG_NONE, FIND_CLOSEST, false)
  local out = {}
  for _, u in pairs(units) do
    if u:IsAlive() and u:IsCreep() and not u:IsNeutralUnitType() and (not enemy or hero:CanEntityBeSeenByMyTeam(u)) then
      out[#out + 1] = u
    end
  end
  return out
end

function W.damage(hero, target)
  return hero:GetAverageTrueAttackDamage(target)
end

function W.attack_damage(hero)
  return hero:GetAttackDamage()
end

function W.attack_range(hero)
  return hero:Script_GetAttackRange()
end

function W.speed(hero)
  return hero:GetIdealSpeed()
end

-- --- герой: уровень, золото, способности, предметы ---

function W.level(hero) return hero:GetLevel() end
function W.mana(hero) return hero:GetMana() end
function W.max_mana(hero) return hero:GetMaxMana() end
function W.gold(hero) return PlayerResource:GetGold(hero:GetPlayerID()) end
function W.buyback_cost(hero) return hero:GetBuybackCost() end
function W.respawn(hero) return hero:GetTimeUntilRespawn() end
function W.is_channeling(hero) return hero:IsChanneling() end
function W.in_shop(hero) return hero:IsInRangeOfShop(DOTA_SHOP_HOME, true) end
function W.item_cost(name) return GetItemCost(name) end
function W.ability_points(hero) return hero:GetAbilityPoints() end

function W.can_buyback(hero)
  return W.gold(hero) >= hero:GetBuybackCost() and hero:GetBuybackCooldownTime() <= 0
end

function W.stats(hero)
  return { lh = hero:GetLastHits(), dn = hero:GetDenies(), k = hero:GetKills(), d = hero:GetDeaths(),
           a = hero:GetAssists() }
end

local function has_flag(value, flag)
  if flag == nil or value == nil then return false end   -- константы нет — флага нет (наблюдение не ломается)
  return math.floor(value / flag) % 2 == 1          -- без библиотеки bit: флаги — степени двойки
end

local function is_talent(ab)
  return ab:GetAbilityName():find("special_bonus", 1, true) ~= nil
end

-- способности героя, которые видит игрок (без талантов и скрытых)
function W.abilities(hero)
  local out = {}
  for i = 0, hero:GetAbilityCount() - 1 do
    local ab = hero:GetAbilityByIndex(i)
    if ab and not ab:IsHidden() and not is_talent(ab) then out[#out + 1] = ab end
  end
  return out
end

-- ульта: способность с типом ABILITY_TYPE_ULTIMATE и уровнем ≥ 1
function W.ult(hero)
  for i = 0, hero:GetAbilityCount() - 1 do
    local ab = hero:GetAbilityByIndex(i)
    if ab and ab:GetAbilityType() == ABILITY_TYPE_ULTIMATE and ab:GetLevel() > 0 then return ab end
  end
  return nil
end

-- слоты предметов: 0–5 — инвентарь, 6–8 — рюкзак, отдельный слот телепорта и нейтральный (dota-data, перечисление
-- DOTAScriptInventorySlot_t); тайник (9–14) не смотрим — из него предметом не воспользоваться
local function item_slots()
  local out = {}
  for slot = 0, 8 do out[#out + 1] = slot end
  out[#out + 1] = DOTA_ITEM_TP_SCROLL
  out[#out + 1] = DOTA_ITEM_NEUTRAL_ACTIVE_SLOT
  return out
end

-- способность или предмет по внутреннему имени («sniper_shrapnel», «item_blink»); предмет ищем по слотам сами:
-- ищет ли FindItemInInventory в слоте телепорта, по описанию API не ясно
function W.ability(hero, name)
  if type(name) ~= "string" or name == "" then return nil end
  if name:sub(1, 5) == "item_" then
    for _, slot in ipairs(item_slots()) do
      local it = hero:GetItemInSlot(slot)
      if it and it:GetAbilityName() == name then return it end
    end
    return nil
  end
  return hero:FindAbilityByName(name)
end

function W.ability_info(ab, hero)
  local behavior = ab:GetBehaviorInt()
  local kind = "none"
  if ab:IsPassive() then kind = "passive"
  elseif has_flag(behavior, DOTA_ABILITY_BEHAVIOR_UNIT_TARGET) then kind = "target"
  elseif has_flag(behavior, DOTA_ABILITY_BEHAVIOR_POINT) then kind = "point" end
  -- по кому способность (для рефлекса «способности в бою»): враги — ENEMY или BOTH; нет ответа — не по врагу
  local okt, tt = pcall(function() return ab:GetAbilityTargetTeam() end)
  tt = okt and tonumber(tt) or DOTA_UNIT_TARGET_TEAM_NONE
  local oka, aoe = pcall(function() return ab:GetAOERadius() end)
  return { name = ab:GetAbilityName(), level = ab:GetLevel(), max = ab:GetMaxLevel(),
           ready = ab:IsFullyCastable(), behavior = kind, cooldown = ab:GetCooldownTimeRemaining(),
           mana = ab:GetManaCost(-1), range = ab:GetCastRange(hero and hero:GetAbsOrigin() or nil, nil),
           cast_point = ab:GetCastPoint(), ult = ab:GetAbilityType() == ABILITY_TYPE_ULTIMATE,
           enemy = tt == DOTA_UNIT_TARGET_TEAM_ENEMY or tt == DOTA_UNIT_TARGET_TEAM_BOTH,
           aoe = oka and tonumber(aoe) or 0,
           toggle = has_flag(behavior, DOTA_ABILITY_BEHAVIOR_TOGGLE),
           autocast = has_flag(behavior, DOTA_ABILITY_BEHAVIOR_AUTOCAST) }
end

-- предметы: инвентарь, рюкзак, слот телепорта, нейтральный
function W.items(hero)
  local out = {}
  for _, slot in ipairs(item_slots()) do
    local it = hero:GetItemInSlot(slot)
    if it then out[#out + 1] = { item = it, slot = slot, charges = it:GetCurrentCharges() } end
  end
  return out
end

function W.is_backpack(slot) return slot >= 6 and slot <= 8 end
function W.is_tp_slot(slot) return slot == DOTA_ITEM_TP_SCROLL end

local function free_in(hero, from, to)
  local n = 0
  for slot = from, to do
    if hero:GetItemInSlot(slot) == nil then n = n + 1 end
  end
  return n
end

-- свободные места: всего (инвентарь и рюкзак) и только в инвентаре — предмет из рюкзака не работает
function W.free_slots(hero) return free_in(hero, 0, 8) end
function W.free_main(hero) return free_in(hero, 0, 5) end

-- CanAbilityBeUpgraded: в @moddota/dota-data 0.47.2 возвращает bool, а константы ABILITY_CAN_BE_UPGRADED…
-- там же описаны как перечисление — что вернёт игра, не проверено, поэтому принимаем оба ответа
local function upgradable(ab)
  local r = ab:CanAbilityBeUpgraded()
  return (r == true or r == ABILITY_CAN_BE_UPGRADED) and ab:GetLevel() < ab:GetMaxLevel()
end

-- что можно качать сейчас (с талантами): только при свободных очках
function W.can_level(hero)
  local out = {}
  if hero:GetAbilityPoints() <= 0 then return out end
  for i = 0, hero:GetAbilityCount() - 1 do
    local ab = hero:GetAbilityByIndex(i)
    if ab and upgradable(ab) and (is_talent(ab) or not ab:IsHidden()) then
      out[#out + 1] = ab
    end
  end
  return out
end

W.is_talent = is_talent
function W.upgrade(hero, ab) hero:UpgradeAbility(ab) end
function W.ability_name(ab) return ab:GetAbilityName() end
function W.ability_level(ab) return ab:GetLevel() end
function W.is_ult(ab) return ab:GetAbilityType() == ABILITY_TYPE_ULTIMATE end

return W
