-- Исполнитель решений агента героя (решение Д11). Чистая логика: всё про Доту — через таблицу world
-- (в игре coach_world.lua, в тестах — имитация).
--
-- Решение агента Claude (раз в несколько секунд):
--   { plan = "farm"|"push"|"defend"|"fight"|"retreat"|"roshan"|"move"|"follow"|"save"|"group"|"hold",
--     where = ""|"top"|"mid"|"bot"|"base"|"roshan", target = "<герой врага>", ally = 0..5,
--     cast = { { ability = "<имя способности или предмета>", target = "<цель>" }, … },
--     buy = { "item_…", … }, level = { "<способность>", … }, retreat_hp = 0..90, buyback = bool, say = "…" }
-- Исполнитель ничего не выбирает сам, кроме рефлексов: добить крипа, применить способность, когда есть
-- цель, отойти по порогу здоровья, купить у фонтана, вложить очко способности. Шаг — раз в 0.25 с.
-- Цель способности: "" (цель плана или ближайший видимый враг), "self", "creeps", номер союзника "1".."5",
-- место "base"/"top"/"mid"/"bot"/"roshan" (для телепорта и точечных способностей), имя героя врага.
-- Имя "#ult" — ульта героя (так запасной исполнитель передаёт «ульт» тренера).

local X = {}
X.CAST_TTL = 8          -- с: сколько способность из решения ждёт цели
X.RETREAT_HYST = 40     -- отход длится, пока здоровье не поднимется на 40 пунктов выше порога
X.LASTHIT = 0.9         -- добиваем, когда у крипа здоровья ≤ 0.9 урона (запас на броню и разброс)
X.DENY_PCT = 50         -- своего крипа добиваем ниже этой доли здоровья
X.FARM_NEAR = 1500      -- крипы ближе — фармим их, дальше — идём к середине линии
X.CAST_SLACK = 150
X.AFTER_CAST = 0.3      -- с к замаху: не сбивать применение приказом движения
X.REFRESH = { move = 1.0, attack_move = 2.0, attack = 3.0 }   -- частый повтор атаки сбивает замах (research/01)
X.WALK_CAST = 20        -- с: дольше не идём к месту применения (вард у дальней вышки); к герою — не дольше 4 с
X.LEVEL_CHECK = 1.0     -- с: через столько проверяем, выросла ли способность после прокачки
X.LEVEL_SKIP = 30       -- с: способность, которую не удалось вкачать, пропускаем
local TELEPORTS = { item_tpscroll = true, item_travel_boots = true, item_travel_boots_2 = true }
-- рефлекс «способности в бою» (живой матч 10.10.2026: «ведут себя очень плохо. только простые действия»: агент
-- решает раз в 15–20 с и о драке заранее не знает, а руки применяли только названное им): руки сами бьют
-- способностями по врагу видимому и в досягаемости
X.AUTO_PLANS = { fight = true, defend = true, save = true, push = true }   -- здесь — всеми, ульта — в драке
X.ULT_PLANS = { fight = true, defend = true, save = true }
X.AUTO_GAP = 0.5        -- с между автоприменениями
X.AUTO_RETRY = 3        -- с: ту же способность, если приказ не прошёл (она всё ещё готова), — не раньше
X.KILL_HP = 40          -- на фарме и в прочих планах: враг слабее этого процента — добить способностями
X.DEFEND_HP = 50        -- на фарме: у себя меньше этого и враг вплотную — отбиваться
X.DEFEND_NEAR = 500
X.SUPPORT_SHARE = 900   -- саппорт (4, 5) на фарме линии: свой кор ближе — вражеских крипов не добивает

local PLANS = { farm = true, push = true, defend = true, fight = true, retreat = true, roshan = true,
                move = true, follow = true, save = true, group = true, hold = true }
local LANES = { top = true, mid = true, bot = true }
local PLACES = { base = true, roshan = true, top = true, mid = true, bot = true }
local LANE_RU = { top = "топ", mid = "мид", bot = "бот" }
local PLAN_RU = { farm = "фарм", push = "пуш", defend = "деф", fight = "бой", retreat = "назад", roshan = "Рошан",
                  move = "иду", follow = "за", save = "спасаю", group = "сбор", hold = "жду" }

X.PLANS = PLANS

-- линия по умолчанию по позиции: лёгкая у 1 и 5, мид у 2, сложная у 3 и 4 (у Света лёгкая — бот, у Тьмы — топ)
function X.default_lane(team, pos)
  local radiant = team == DOTA_TEAM_GOODGUYS
  if pos == 2 then return "mid" end
  if pos == 1 or pos == 5 then return radiant and "bot" or "top" end
  return radiant and "top" or "bot"
end

function X.new()
  return { plan = nil, casts = {}, buy = {}, level = {}, retreat_hp = 25, buyback = false, retreating = false,
           last = nil, notes = {}, busy_until = 0, level_wait = 0, buy_wait = 0, source = nil, set_t = nil,
           active = nil, level_try = nil, level_bad = {}, status = "ждёт решения агента" }
end

local function note(st, text)
  if st.notes[#st.notes] == text then return end
  st.notes[#st.notes + 1] = text
  while #st.notes > 5 do table.remove(st.notes, 1) end
end

local function copy(list)
  local out = {}
  for i, v in ipairs(list or {}) do out[i] = v end
  return out
end

local function clamp(v, lo, hi)
  if v < lo then return lo end
  if v > hi then return hi end
  return v
end

-- новое решение (агента или запасного исполнителя)
function X.set(st, d, now, source)
  local plan = PLANS[d.plan] and d.plan or (st.plan and st.plan.kind) or "hold"
  st.plan = { kind = plan, where = tostring(d.where or ""), target = tostring(d.target or ""),
              ally = tonumber(d.ally) or 0 }
  st.casts = {}
  for _, c in ipairs(d.cast or {}) do
    if #st.casts >= 4 then break end
    if type(c) == "table" and type(c.ability) == "string" and c.ability ~= "" then
      st.casts[#st.casts + 1] = { ability = c.ability, target = tostring(c.target or ""), until_t = now + X.CAST_TTL }
    end
  end
  if type(d.buy) == "table" and #d.buy > 0 then st.buy = copy(d.buy) end
  if type(d.level) == "table" and #d.level > 0 then st.level = copy(d.level) end
  if tonumber(d.retreat_hp) then st.retreat_hp = clamp(tonumber(d.retreat_hp), 0, 90) end
  st.buyback = d.buyback == true
  st.source, st.set_t, st.notes = source, now, {}
  -- новое решение заменяет ждущие применения. Начатое (герой идёт ставить вард) продолжается, только если агент
  -- его повторил; иначе подход отменяется, а замах, который уже идёт, доигрывается
  local a = st.active
  if a and now < (st.busy_until or 0) then
    for i, c in ipairs(st.casts) do
      if c.ability == a.name and c.target == a.target then
        table.remove(st.casts, i)
        return
      end
    end
  end
  st.active = nil
  st.busy_until = math.min(st.busy_until or 0, now + X.AFTER_CAST)
end

-- --- рефлексы ---

local function level_step(st, hero, world, now)
  local try = st.level_try
  if try and now - try.t >= X.LEVEL_CHECK then
    local ab = world.ability(hero, try.name)
    st.level_try = nil
    if ab and world.ability_level(ab) <= try.before then
      if try.method == "order" then                  -- приказ не сработал — вкачать напрямую
        st.level_try = { name = try.name, before = try.before, t = now, method = "upgrade" }
        return { kind = "level", ability = ab, name = try.name, method = "upgrade", by = "повтор" }
      end
      st.level_bad[try.name] = now + X.LEVEL_SKIP
      note(st, "не удалось вкачать " .. try.name)
    end
  end
  if st.level_try or now < st.level_wait or world.ability_points(hero) <= 0 then return nil end
  local can = {}
  for _, ab in ipairs(world.can_level(hero)) do
    if now >= (st.level_bad[world.ability_name(ab)] or 0) then can[#can + 1] = ab end
  end
  if #can == 0 then return nil end
  local by_name = {}
  for _, ab in ipairs(can) do by_name[world.ability_name(ab)] = ab end
  local pick, why = nil, nil
  for i, name in ipairs(st.level) do
    if by_name[name] then
      pick, why = by_name[name], "агент"
      table.remove(st.level, i)
      break
    end
  end
  if pick == nil then                       -- очередь пуста или в ней нечего качать: ульта, потом младшая способность
    local best = nil
    for _, ab in ipairs(can) do
      if world.is_ult(ab) then best = ab break end
      if not world.is_talent(ab) and (best == nil or world.ability_level(ab) < world.ability_level(best)) then best = ab end
    end
    pick, why = best or can[1], "сам"
  end
  st.level_wait = now + 1.0
  local name = world.ability_name(pick)
  st.level_try = { name = name, before = world.ability_level(pick), t = now, method = "order" }
  return { kind = "level", ability = pick, name = name, method = "order", by = why }
end

local function buy_step(st, hero, world, now, dead)
  if #st.buy == 0 or now < st.buy_wait then return nil end
  if not dead and not world.in_shop(hero) then return nil end
  local name = st.buy[1]
  local cost = tonumber(world.item_cost(name)) or 0
  if cost <= 0 then
    table.remove(st.buy, 1)
    note(st, "нет такого предмета: " .. tostring(name))
    return nil
  end
  if world.free_slots(hero) <= 0 then
    note(st, "нет места для " .. name)
    st.buy_wait = now + 5
    return nil
  end
  if world.free_main(hero) <= 0 then note(st, name .. " ляжет в рюкзак: инвентарь полон") end
  if world.gold(hero) < cost then
    st.saving = name
    return nil
  end
  table.remove(st.buy, 1)
  st.saving, st.buy_wait = nil, now + 0.5
  return { kind = "buy", item = name, cost = cost }
end

local function toward(from, to, dist)        -- точка на расстоянии dist от from в сторону to
  local dx, dy = to.x - from.x, to.y - from.y
  local len = math.sqrt(dx * dx + dy * dy)
  if len < 1 then return from end
  return Vector(from.x + dx / len * dist, from.y + dy / len * dist, 0)
end

local function place_point(place, team, world)
  if place == "base" then return world.fountain(team) end
  if LANES[place] then return world.lane_front(team, place) end
  if place == "roshan" then
    local r = world.roshan()
    return r and world.pos(r) or nil
  end
  return nil
end

local function creep_center(creeps, world, n)
  local sx, sy, k = 0, 0, 0
  for i, c in ipairs(creeps) do
    if i > n then break end
    local p = world.pos(c)
    sx, sy, k = sx + p.x, sy + p.y, k + 1
  end
  if k == 0 then return nil end
  return Vector(sx / k, sy / k, 0)
end

-- цель способности: { unit = … } | { point = …, global = bool } | { none = true } | nil (цели нет)
local function resolve(target, info, st, ag, world)
  local hero, team = ag.hero, ag.team
  local t = target or ""
  if t == "self" then return { unit = hero } end
  if PLACES[t] then
    local p = place_point(t, team, world)
    return p and { point = p, place = true } or nil
  end
  local n = tonumber(t)
  if n and n >= 1 and n <= 5 then
    local ally = world.ally_hero(team, n)
    return ally and { unit = ally } or nil
  end
  local range = (info.range and info.range > 0) and info.range or 600
  if t == "creeps" then
    local creeps = world.lane_creeps(hero, range + 200, true)
    if #creeps == 0 then return nil end
    if info.behavior == "none" then return #creeps >= 2 and { none = true } or nil end
    if info.behavior == "point" then return { point = creep_center(creeps, world, 4) } end
    return { unit = creeps[1] }
  end
  if t == "" then                                 -- цель плана или ближайший видимый враг; «сразу» — это "self"
    local plan = st.plan
    if plan and plan.target ~= "" then
      local e = world.enemy_hero(team, plan.target)
      if e then return { unit = e } end
    end
    local reach = (info.behavior == "none") and math.max(range, 400) or range
    local near = world.nearest_enemy(team, world.pos(hero), reach + 300)
    return near and { unit = near } or nil
  end
  local e = world.enemy_hero(team, t)
  return e and { unit = e } or nil
end

local function cast_step(st, ag, world, now)
  local hero, team = ag.hero, ag.team
  local my = world.pos(hero)
  local keep = {}
  local act = nil
  for _, c in ipairs(st.casts) do
    if act ~= nil then
      keep[#keep + 1] = c                                      -- за шаг — одно применение
    elseif now > c.until_t then
      note(st, "не применил " .. c.ability .. ": за " .. X.CAST_TTL .. " с не было цели или отката")
    else
      local ab = c.ability == "#ult" and world.ult(hero) or world.ability(hero, c.ability)
      if ab == nil then
        note(st, "нет способности " .. c.ability)
      else
        local info = world.ability_info(ab, hero)
        if info.level <= 0 then
          note(st, c.ability .. " не изучена")
        elseif info.behavior == "passive" then
          note(st, c.ability .. " — пассивная")
        elseif not info.ready then
          keep[#keep + 1] = c                                  -- откат или нет маны: ждём до срока
        else
          local tg = resolve(c.target, info, st, ag, world)
          local range = (info.range and info.range > 0) and info.range or 600
          if tg == nil then
            keep[#keep + 1] = c
          elseif info.behavior == "target" and tg.unit then
            local d = world.dist(my, world.pos(tg.unit))
            local walk = math.max(0, d - range) / math.max(100, world.speed(hero))
            act = { kind = "cast", ability = ab, behavior = "target", target = tg.unit, name = c.ability, src = c,
                    busy = math.min(4, walk + (info.cast_point or 0) + X.AFTER_CAST) }
          elseif info.behavior == "point" and (tg.point or tg.unit) then
            local p = tg.point or world.pos(tg.unit)
            local d = world.dist(my, p)
            local teleport = TELEPORTS[c.ability]
            local walk = teleport and 0 or math.max(0, d - range) / math.max(100, world.speed(hero))
            local cap = (tg.place and not teleport) and X.WALK_CAST or 4
            act = { kind = "cast", ability = ab, behavior = "point", point = p, name = c.ability, src = c,
                    busy = math.min(cap, walk + (info.cast_point or 0) + X.AFTER_CAST) }
          elseif info.behavior == "none" then
            -- без цели: применяем, когда цель (если есть) рядом — радиус не знаем, берём дальность или 400
            if tg.unit and tg.unit ~= hero and world.dist(my, world.pos(tg.unit)) > math.max(range, 400) + X.CAST_SLACK then
              keep[#keep + 1] = c
            else
              act = { kind = "cast", ability = ab, behavior = "none", name = c.ability, src = c,
                      busy = (info.cast_point or 0) + X.AFTER_CAST }
            end
          else
            keep[#keep + 1] = c                                -- цель не того вида (точка для способности по юниту)
          end
        end
      end
    end
  end
  st.casts = keep
  if act then st.active = { name = act.src.ability, target = act.src.target, t = now } end
  return act
end

-- рефлекс «способности в бою»: одно применение за шаг. В драке, обороне, спасении и пуше — по ближайшему видимому
-- врагу (или цели плана), ульта — только в драке, обороне и спасении (и когда враг ранен или их двое рядом). В прочих
-- планах — только добить слабого врага или отбиться, когда сам ранен и враг вплотную; при отходе — без ульты, по
-- догоняющему. Только способности по врагам: не переключатели, не автоатаки, не по союзникам — их называет агент.
local function auto_cast(st, ag, world, now, mode)
  if now < (st.auto_next or 0) then return nil end
  local hero, team = ag.hero, ag.team
  local plan = st.plan and st.plan.kind or ""
  local my = world.pos(hero)
  local target = nil
  if st.plan and st.plan.target ~= "" then target = world.enemy_hero(team, st.plan.target) end
  target = target or world.nearest_enemy(team, my, 1600)
  if target == nil then return nil end
  local d = world.dist(my, world.pos(target))
  local fight = mode ~= "escape" and X.AUTO_PLANS[plan]
  if not fight then
    local weak = world.hp_pct(target) <= X.KILL_HP
    local pressed = world.hp_pct(hero) < X.DEFEND_HP and d <= X.DEFEND_NEAR
    if mode == "escape" then
      if d > X.DEFEND_NEAR then return nil end
    elseif not weak and not pressed then
      return nil
    end
  end
  st.auto_tried = st.auto_tried or {}
  local ult_ok = mode ~= "escape" and X.ULT_PLANS[plan]
      and (world.hp_pct(target) <= 70 or #world.enemies_near(team, world.pos(target), 700) >= 2)
  local pick = nil
  for pass = 1, 2 do                                        -- сначала обычные способности, потом ульта
    for _, ab in ipairs(world.abilities(hero)) do
      local i = world.ability_info(ab, hero)
      local usable = i.level > 0 and i.behavior ~= "passive" and i.ready and i.enemy and not i.toggle
          and not i.autocast and (pass == 2) == i.ult and (not i.ult or ult_ok)
          and now - (st.auto_tried[i.name] or -1e9) >= X.AUTO_RETRY
      if usable then
        local range = (i.range and i.range > 0) and i.range or 600
        if i.behavior == "none" then
          if d <= ((i.aoe and i.aoe > 0) and i.aoe or 300) then pick = { ab = ab, i = i } end
        elseif d <= range + 50 then
          pick = { ab = ab, i = i }
        end
      end
      if pick then break end
    end
    if pick then break end
  end
  if pick == nil then return nil end
  local i = pick.i
  st.auto_next, st.auto_tried[i.name] = now + X.AUTO_GAP, now
  local act = { kind = "cast", ability = pick.ab, behavior = i.behavior, name = i.name, auto = true,
                busy = (i.cast_point or 0) + X.AFTER_CAST }
  if i.behavior == "target" then act.target = target
  elseif i.behavior == "point" then act.point = world.pos(target) end
  return act
end

-- рефлекс «расходники»: как делает каждый игрок — лечилка и кларити, когда ранен и врага рядом нет (их сбивает урон),
-- волшебный огонь и палочка, когда здоровья мало и враг рядом. Раз в секунду, только из инвентаря.
X.FLASK_HP, X.CLARITY_MP, X.PANIC_HP, X.SAFE_R = 55, 35, 25, 900
local function consume(st, ag, world, now)
  if now < (st.consume_next or 0) then return nil end
  local hero = ag.hero
  local hp = world.hp_pct(hero)
  local danger = world.nearest_enemy(ag.team, world.pos(hero), X.SAFE_R) ~= nil
  local function use(name, self_target)
    local it = world.main_item(hero, name)
    if it == nil or not world.ability_info(it, hero).ready then return nil end
    st.consume_next = now + 1.0
    if self_target then return { kind = "cast", ability = it, behavior = "target", target = hero, name = name, auto = true, busy = 0.1 } end
    return { kind = "cast", ability = it, behavior = "none", name = name, auto = true, busy = 0.1 }
  end
  if danger and hp <= X.PANIC_HP then
    local wand = world.main_item(hero, "item_magic_wand") or world.main_item(hero, "item_magic_stick")
    if wand and world.charges(wand) >= 3 then
      local a = use(world.ability_name(wand), false)
      if a then return a end
    end
    local a = use("item_faerie_fire", false)
    if a then return a end
  end
  if not danger then
    if hp <= X.FLASK_HP and not world.has_modifier(hero, "modifier_flask_healing") then
      local a = use("item_flask", true)
      if a then return a end
    end
    if world.mana_pct(hero) <= X.CLARITY_MP and not world.has_modifier(hero, "modifier_clarity_potion") then
      local a = use("item_clarity", true)
      if a then return a end
    end
  end
  st.consume_next = now + 1.0
  return nil
end

-- --- план → приказ движения/атаки ---

-- кор (позиции 1–3) рядом с саппортом — добивания ему
local function core_near(ag, world)
  if ag.pos ~= 4 and ag.pos ~= 5 then return nil end
  local my = world.pos(ag.hero)
  for pos = 1, 3 do
    local ally = world.ally_hero(ag.team, pos)
    if ally and ally ~= ag.hero and world.dist(my, world.pos(ally)) <= X.SUPPORT_SHARE then return ally, pos end
  end
  return nil
end

local function farm_order(st, ag, world, lane)
  local hero, team = ag.hero, ag.team
  local my = world.pos(hero)
  local tag = "фарм " .. LANE_RU[lane]
  local core, core_pos = core_near(ag, world)
  if core then                                  -- саппорт на линии с кором: свои крипы — добить, враг — бить, если
    tag = "линия с " .. core_pos                 -- безопасно; вражеских крипов не добивать: опыт идёт и так
    local range = world.attack_range(hero)
    for _, c in ipairs(world.lane_creeps(hero, range + 300, false)) do
      if world.hp_pct(c) < X.DENY_PCT and world.hp(c) <= world.damage(hero, c) * X.LASTHIT then
        return { kind = "attack", target = c, why = tag .. ": добиваю своего" }
      end
    end
    local e = world.nearest_enemy(team, my, range + 100)
    if e and world.hp_pct(hero) >= 60 and world.hp_pct(e) <= world.hp_pct(hero) then
      return { kind = "attack", target = e, why = tag .. ": бью врага" }
    end
    local cp = world.pos(core)
    if world.dist(my, cp) > 350 then
      return { kind = "move", point = toward(cp, world.fountain(team) or my, 250), why = tag .. ": иду к своему" }
    end
    return { kind = "hold", why = tag .. ": стою у своего" }
  end
  local enemies = world.lane_creeps(hero, X.FARM_NEAR, true)
  if #enemies == 0 then                         -- вражеских крипов рядом нет: к своей волне, без неё — к середине линии
    local front = world.wave_front(team, lane)
    local base = world.lane_front(team, lane)
    local p = front and world.clear(toward(front, base, 250), base) or world.lane_mid(team, lane)
    if world.dist(my, p) > 300 then
      return { kind = "move", point = p, why = tag .. (front and ": иду к своей волне" or ": иду к линии") }
    end
    return { kind = "hold", why = tag .. ": жду волну" }
  end
  local range = world.attack_range(hero)
  local best, best_hp = nil, 1e18
  for _, c in ipairs(enemies) do
    local hp = world.hp(c)
    if hp <= world.damage(hero, c) * X.LASTHIT and world.dist(my, world.pos(c)) <= range + 300 and hp < best_hp then
      best, best_hp = c, hp
    end
  end
  if best then return { kind = "attack", target = best, why = tag .. ": добиваю" } end
  for _, c in ipairs(world.lane_creeps(hero, range + 300, false)) do
    if world.hp_pct(c) < X.DENY_PCT and world.hp(c) <= world.damage(hero, c) * X.LASTHIT then
      return { kind = "attack", target = c, why = tag .. ": добиваю своего" }
    end
  end
  local near = enemies[1]                                    -- ближайший (FIND_CLOSEST)
  local np = world.pos(near)
  if world.dist(my, np) > range + 250 then
    return { kind = "move", point = toward(np, my, range), why = tag .. ": к крипам" }
  end
  return { kind = "hold", why = tag .. ": жду добивание" }
end

local function lane_of(plan, ag)
  if LANES[plan.where] then return plan.where end
  return nil
end

local function plan_order(st, ag, world, now)
  local plan = st.plan
  if plan == nil then return nil end
  local hero, team = ag.hero, ag.team
  local k = plan.kind
  if k == "farm" then
    return farm_order(st, ag, world, lane_of(plan, ag) or X.default_lane(team, ag.pos))
  elseif k == "push" then
    local lane = lane_of(plan, ag) or "mid"
    return { kind = "attack_move", point = world.lane_enemy_front(team, lane), why = "пуш " .. LANE_RU[lane] }
  elseif k == "defend" then
    if plan.where == "base" then return { kind = "attack_move", point = world.fountain(team), why = "деф базы" } end
    local lane = lane_of(plan, ag) or "mid"
    return { kind = "attack_move", point = world.lane_front(team, lane), why = "деф " .. LANE_RU[lane] }
  elseif k == "fight" then
    if plan.target ~= "" then
      local e = world.enemy_hero(team, plan.target)
      if e then return { kind = "attack", target = e, why = "бью " .. plan.target } end
      local seen = world.last_seen(team, plan.target)
      if seen and now - seen.t <= 20 then
        return { kind = "attack_move", point = seen.pos, why = "ищу " .. plan.target }
      end
    end
    local lane = lane_of(plan, ag)
    if lane then return { kind = "attack_move", point = world.lane_mid(team, lane), why = "бой на " .. LANE_RU[lane] } end
    local near = world.nearest_enemy(team, world.pos(hero), 1500)
    if near then return { kind = "attack", target = near, why = "бой" } end
    return { kind = "hold", why = "бой: не вижу врага" }
  elseif k == "retreat" then
    return { kind = "move", point = world.fountain(team), why = "назад на базу" }
  elseif k == "roshan" then
    local r = world.roshan()
    if r then return { kind = "attack", target = r, why = "Рошан" } end
    return { kind = "hold", why = "Рошана нет" }
  elseif k == "move" or k == "group" then
    local p = place_point(plan.where, team, world)
    if p == nil and k == "group" then p = world.team_center(team) end
    if p == nil then return { kind = "hold", why = "не знаю, куда" } end
    local tag = k == "group" and "сбор" or "иду"
    return { kind = "move", point = p, why = tag .. (plan.where ~= "" and (" " .. (LANE_RU[plan.where] or plan.where)) or "") }
  elseif k == "follow" or k == "save" then
    local ally = world.ally_hero(team, plan.ally)
    if ally == nil or ally == hero then return { kind = "hold", why = "нет союзника " .. tostring(plan.ally) } end
    return { kind = k == "save" and "attack_move" or "move", point = world.pos(ally),
             why = (k == "save" and "спасаю " or "за ") .. tostring(plan.ally) }
  end
  return { kind = "hold", why = "жду" }
end

-- Повторять ли приказ: новый вид, новая цель, точка сдвинулась или вышел срок повтора.
function X.should_issue(last, order, now, world)
  if order == nil then return false end
  if last == nil or last.kind ~= order.kind or last.target ~= order.target then return true end
  if order.point and last.point and world.dist(order.point, last.point) > 100 then return true end
  local every = X.REFRESH[order.kind]
  if every == nil then return false end                     -- «стоять» не повторяем
  return now - (last.t or -1e9) >= every
end

local function issue(st, acts, order, now, world)
  if X.should_issue(st.last, order, now, world) then
    order.t = now
    st.last = order
    acts[#acts + 1] = { kind = "order", order = order }
  end
  st.status = order.why
  return acts
end

-- Один шаг: список действий для игры
--   { kind = "order", order = { kind = "move"|"attack_move"|"attack"|"hold", point, target, why } }
--   { kind = "cast", ability, behavior, target, point } · { kind = "level", ability } · { kind = "buy", item, cost }
--   { kind = "buyback" }
function X.step(st, ag, world, now)
  local hero = ag.hero
  local acts = {}
  if not world.alive(hero) then
    if st.buyback and world.can_buyback(hero) then
      acts[#acts + 1] = { kind = "buyback" }
      st.buyback = false
    end
    local b = buy_step(st, hero, world, now, true)
    if b then acts[#acts + 1] = b end
    st.retreating, st.last, st.busy_until = false, nil, 0
    st.status = string.format("мёртв, %d с", math.floor((tonumber(world.respawn(hero)) or 0) + 0.5))
    return acts
  end
  local lv = level_step(st, hero, world, now)
  if lv then acts[#acts + 1] = lv end
  local b = buy_step(st, hero, world, now, false)
  if b then acts[#acts + 1] = b end
  local a = st.active
  if a and now < st.busy_until and now - (a.t or now) >= X.AFTER_CAST then
    local ab = a.name == "#ult" and world.ult(hero) or world.ability(hero, a.name)
    if ab == nil or not world.ability_info(ab, hero).ready then
      st.busy_until, st.active = now, nil              -- применено: пошёл откат или предмет израсходован
    end
  end
  if world.is_channeling(hero) or now < st.busy_until then return acts end

  local u = consume(st, ag, world, now)
  if u then
    acts[#acts + 1] = u
    st.busy_until = now + u.busy
    st.status = "пью/жму " .. u.name
    return acts
  end

  local hp = world.hp_pct(hero)
  if st.retreat_hp > 0 and hp < st.retreat_hp then st.retreating = true end
  if st.retreating and hp >= math.min(95, st.retreat_hp + X.RETREAT_HYST) then st.retreating = false end
  if st.retreating then
    local esc = auto_cast(st, ag, world, now, "escape")
    if esc then
      acts[#acts + 1] = esc
      st.busy_until, st.last = now + esc.busy, nil
      st.status = "отхожу, бью догоняющего: " .. esc.name
      return acts
    end
    return issue(st, acts, { kind = "move", point = world.fountain(ag.team),
                             why = string.format("отхожу, здоровья %d%%", math.floor(hp + 0.5)) }, now, world)
  end

  local c = cast_step(st, ag, world, now) or auto_cast(st, ag, world, now)
  if c then
    acts[#acts + 1] = c
    st.busy_until = now + (c.busy or X.AFTER_CAST)
    st.last = nil                                            -- после применения приказ движения выдать заново
    st.status = (c.auto and "бью способностью " or "применяю ") .. c.name
    return acts
  end

  local order = plan_order(st, ag, world, now)
  if order then return issue(st, acts, order, now, world) end
  st.status = "ждёт решения агента"
  return acts
end

-- --- запасной исполнитель: приказ тренера без агента (нет связи с сервером агентов) ---

local FROM_INTENT = { retreat = "retreat", move = "move", push = "push", split = "push", defend = "defend",
                      gank = "fight", engage = "fight", focus = "fight", group = "group", roshan = "roshan",
                      hold = "hold", follow = "follow", save = "save", farm = "farm" }

local function short(name)
  return (tostring(name or ""):gsub("^npc_dota_hero_", ""))
end

-- намерение тренера (vc_intents) → решение для исполнителя; enemy_name(pos) — имя врага по позиции
function X.from_intent(it, team, pos, enemy_name)
  local lane = X.default_lane(team, pos)
  if it == nil then return { plan = "farm", where = lane } end
  local p = it.params or {}
  local plan = FROM_INTENT[it.action]
  if plan == nil then return { plan = "farm", where = lane } end            -- смок, вард, стак — пока не умеем
  if plan == "hold" and p.what then return { plan = "farm", where = lane } end  -- «не рош»: запрет, а не «стой»
  local where = p.lane or ((p.place == "base" or p.place == "roshan") and p.place) or ""
  if plan == "farm" and not LANES[where] then where = lane end
  if (plan == "push" or plan == "defend") and where == "" then where = "mid" end
  local target = p.enemy and short(p.enemy) or (p.enemy_pos and enemy_name and enemy_name(p.enemy_pos)) or ""
  return { plan = plan, where = where, target = target or "", ally = p.ally or 0 }
end

-- мгновенное намерение тренера (ульт, тп, предмет, бб) → добавка к решению; nil — не умеем
function X.from_instant(it, enemy_name)
  local p = it.params or {}
  local target = p.enemy and short(p.enemy) or (p.enemy_pos and enemy_name and enemy_name(p.enemy_pos)) or ""
  if it.action == "buyback" then return { buyback = true } end
  if it.action == "buy" and p.item then return { buy = { p.item } } end
  if it.action == "use_ult" then return { cast = { { ability = "#ult", target = target or "" } } } end
  if it.action == "use_item" and p.item then return { cast = { { ability = p.item, target = target or "" } } } end
  if it.action == "tp" then
    local where = p.lane or p.place
    if PLACES[where] then return { cast = { { ability = "item_tpscroll", target = where } } } end
  end
  return nil
end

X.PLAN_RU = PLAN_RU
X.LANE_RU = LANE_RU

return X
