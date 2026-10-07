-- Агенты кастомки: намерение тренера → приказ герою-боту. Чистая логика.
--
-- Всё, что про Доту, приходит через таблицу world (в игре — coach_world.lua, в тестах — имитация):
--   world.fountain(team) · world.lane_front(team, lane) · world.lane_enemy_front(team, lane)
--   world.roshan() · world.enemy_hero(team, hero_name) · world.enemy_by_pos(team, pos)
--   world.ally_hero(team, pos) · world.nearest_enemy(team, point) · world.team_center(team)
--   world.pos(unit) · world.dist(a, b) · world.ult(hero) · world.ability_info(ability)
--   world.item(hero, name) · world.can_buyback(hero) · world.alive(hero)
-- Без намерения агент играет сам (встроенный ИИ ботов Доты). С намерением — получает приказ,
-- который повторяется раз в A.REFRESH секунд: встроенный ИИ может его перебить (это меряет пробник).

local A = {}
A.REFRESH = 1.0       -- с
A.ARRIVE = 700        -- «дошёл» до точки фарма линии — дальше фармит сам

local LANE_RU = { top = "топ", mid = "мид", bot = "бот" }

local function lane_of(p)
  local l = p.lane
  if l == nil or l == "auto" then return "mid" end
  return l
end

local function enemy_target(it, ag, world)
  local p = it.params or {}
  if p.enemy then return world.enemy_hero(ag.team, p.enemy) end
  if p.enemy_pos then return world.enemy_by_pos(ag.team, p.enemy_pos) end
  return nil
end

local function place_point(place, ag, world)
  if place == "base" then return world.fountain(ag.team) end
  if place == "roshan" then
    local r = world.roshan()
    return r and world.pos(r) or nil
  end
  return nil                                   -- руны, лес, аутпосты — точек пока нет
end

-- Приказ для намерения (не мгновенного). nil — играет сам.
-- Приказ: { kind = "move"|"attack_move"|"attack"|"hold", point = …, target = …, why = "для HUD" }
function A.decide(it, ag, world)
  if it == nil or not world.alive(ag.hero) then return nil end
  local act, p = it.action, it.params or {}
  if act == "retreat" then
    return { kind = "move", point = world.fountain(ag.team), why = "назад на базу" }
  elseif act == "move" then
    local point = p.lane and world.lane_front(ag.team, p.lane) or place_point(p.place, ag, world)
    if not point then return nil end
    return { kind = "move", point = point, why = "иди " .. (LANE_RU[p.lane] or p.place or "") }
  elseif act == "push" or act == "split" then
    local lane = lane_of(p)
    return { kind = "attack_move", point = world.lane_enemy_front(ag.team, lane), why = "пуш " .. LANE_RU[lane] }
  elseif act == "defend" then
    if p.place == "base" then
      return { kind = "attack_move", point = world.fountain(ag.team), why = "деф базы" }
    end
    local lane = lane_of(p)
    return { kind = "attack_move", point = world.lane_front(ag.team, lane), why = "деф " .. LANE_RU[lane] }
  elseif act == "gank" or act == "engage" or act == "focus" then
    local target = enemy_target(it, ag, world)
    if target then
      return { kind = "attack", target = target, why = (act == "focus" and "фокус" or act == "gank" and "ганг" or "драка") }
    end
    if act == "focus" then return nil end      -- цели не видно — ждём, играет сам
    if p.lane or act == "gank" then
      local lane = lane_of(p)
      return { kind = "attack_move", point = world.lane_enemy_front(ag.team, lane), why = "ганг " .. LANE_RU[lane] }
    end
    local near = world.nearest_enemy(ag.team, world.pos(ag.hero))
    if near then return { kind = "attack", target = near, why = "драка" } end
    return nil
  elseif act == "group" then
    local point = (p.lane and world.lane_front(ag.team, p.lane)) or place_point(p.place, ag, world)
      or world.team_center(ag.team)
    return { kind = "move", point = point, why = "сбор" }
  elseif act == "roshan" then
    local r = world.roshan()
    if not r then return nil end
    return { kind = "attack", target = r, why = "Рошан" }
  elseif act == "hold" then
    if p.what then return nil end              -- «не X» встроенному ИИ не запретить; ответ — в HUD
    return { kind = "hold", why = "жду" }
  elseif act == "follow" or act == "save" then
    local ally = world.ally_hero(ag.team, p.ally)
    if not ally or ally == ag.hero then return nil end
    return { kind = act == "save" and "attack_move" or "move", point = world.pos(ally),
             why = (act == "save" and "спасать " or "за ") .. tostring(p.ally) }
  elseif act == "farm" then
    if p.area == "lane" and p.lane then
      local point = world.lane_front(ag.team, p.lane)
      if world.dist(world.pos(ag.hero), point) > A.ARRIVE then
        return { kind = "move", point = point, why = "фарм " .. LANE_RU[p.lane] }
      end
    end
    return nil                                 -- лес и «где лучше» — фармит сам
  end
  return nil                                   -- смок, вард, стак — пока не умеем: играет сам
end

-- Мгновенное намерение (ульта, байбэк, тп, предмет). Возвращает действие для игры
-- { kind = "cast"|"buyback"|"move", ability = …, target = …, point = …, behavior = … }
-- или { kind = "skip", reason = "…" } — что ответить тренеру.
function A.instant(it, ag, world)
  local act, p = it.action, it.params or {}
  if act == "buyback" then
    if world.alive(ag.hero) then return { kind = "skip", reason = "alive" } end
    if not world.can_buyback(ag.hero) then return { kind = "skip", reason = "no_buyback" } end
    return { kind = "buyback" }
  end
  if not world.alive(ag.hero) then return { kind = "skip", reason = "dead" } end
  if act == "use_ult" then
    local ab = world.ult(ag.hero)
    if not ab then return { kind = "skip", reason = "no_ult" } end
    local info = world.ability_info(ab)
    if not info.ready then return { kind = "skip", reason = "ult_cd", value = info.cooldown } end
    local target = enemy_target(it, ag, world) or world.nearest_enemy(ag.team, world.pos(ag.hero))
    if info.behavior == "none" then return { kind = "cast", ability = ab, behavior = "none" } end
    if not target then return { kind = "skip", reason = "no_target" } end
    if info.behavior == "point" then
      return { kind = "cast", ability = ab, behavior = "point", point = world.pos(target) }
    end
    return { kind = "cast", ability = ab, behavior = "target", target = target }
  end
  if act == "tp" then
    local point = p.lane and world.lane_front(ag.team, p.lane) or place_point(p.place, ag, world)
    if not point then return { kind = "skip", reason = "where" } end
    local scroll = world.item(ag.hero, "item_tpscroll")
    if scroll and world.ability_info(scroll).ready then
      return { kind = "cast", ability = scroll, behavior = "point", point = point }
    end
    return { kind = "move", point = point }
  end
  if act == "use_item" then
    local item = world.item(ag.hero, p.item)
    if not item then return { kind = "skip", reason = "no_item" } end
    local info = world.ability_info(item)
    if not info.ready then return { kind = "skip", reason = "item_cd", value = info.cooldown } end
    if info.behavior == "none" then return { kind = "cast", ability = item, behavior = "none" } end
    local target = enemy_target(it, ag, world) or world.nearest_enemy(ag.team, world.pos(ag.hero))
    if not target then return { kind = "skip", reason = "no_target" } end
    if info.behavior == "point" then return { kind = "cast", ability = item, behavior = "point", point = world.pos(target) } end
    return { kind = "cast", ability = item, behavior = "target", target = target }
  end
  return { kind = "skip", reason = "cant" }    -- покупка — пока не умеем
end

-- Повторять ли приказ: новый вид, новая цель или прошло REFRESH секунд.
function A.should_issue(last, order, now, world)
  if order == nil then return false end
  if last == nil or last.kind ~= order.kind or last.target ~= order.target then return true end
  if order.point and last.point and world.dist(order.point, last.point) > 50 then return true end
  return now - (last.t or -1e9) >= A.REFRESH
end

return A
