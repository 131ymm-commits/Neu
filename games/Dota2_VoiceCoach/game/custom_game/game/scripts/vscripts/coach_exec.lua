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
-- добивание с упреждением (слова автора 11.10.2026: «нужен ласт хит удар по крипу со слабым здоровьем»): удар начинается,
-- когда к попаданию — дойти, замах, полёт снаряда — у крипа останется не больше LH_MARGIN урона героя (запас на разброс
-- урона) и он ещё жив. Скорость потери здоровья — по окну LH_WINDOW: крипы бьют ступеньками раз в ~1 с, и замер по
-- соседним шагам скакал на каждом ударе — герой бил рано (рецензия 11: на 60 модельных крипах 11 добиваний из 60).
-- Пока идёт подход и замах, удар не сбивается ничем, кроме отхода и вражеской вышки.
X.LH_WINDOW = 1.0       -- с: окно замера скорости — ровно период удара крипа (KV: AttackRate 1), тогда в окне
                        -- каждый бьющий крип по одному разу; пока замеров на окно нет — скорость 0 (бить, только
                        -- когда хватает удара сейчас)
X.LH_MARGIN = 0.85      -- к попаданию у крипа не больше этой доли урона
X.LH_KEEP = 3           -- с: замер крипа, которого столько не видели, — забыть
X.DENY_PCT = 50         -- своего крипа добиваем ниже этой доли здоровья
X.FARM_NEAR = 1500      -- крипы ближе — фармим их, дальше — идём к середине линии
X.CAST_SLACK = 150
X.AFTER_CAST = 0.3      -- с к замаху: не сбивать применение приказом движения
X.REFRESH = { move = 1.0, attack_move = 2.0, attack = 3.0 }   -- частый повтор атаки сбивает замах (research/01)
X.WALK_CAST = 20        -- с: дольше не идём к месту применения (вард у дальней вышки); к герою — не дольше 4 с
X.LEVEL_CHECK = 1.0     -- с: через столько проверяем, выросла ли способность после прокачки
X.LEVEL_SKIP = 30       -- с: способность, которую не удалось вкачать, пропускаем
local TELEPORTS = { item_tpscroll = true, item_travel_boots = true, item_travel_boots_2 = true }
local FREE_ITEMS = { item_ward_observer = true }      -- из запаса магазина бесплатно: цена 0 — не «нет предмета»
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
X.TOWER_KEEP = 900      -- к живой вражеской вышке на фарме ближе не подходить (бьёт примерно на 700 — по памяти)
-- больше действий (живой матч 11.10.2026, слова автора: «то что они ходят это хорошо. просто они очень мало действий
-- делают»): стычка рядом, размен ударом и способностью на линии. Пороги — наше правило, в игре не проверены. Решение
-- вступить в бой надолго — за агентом (ERRORS №102: в руки — моторика); руки вступают сами, только когда повод виден
-- сейчас: раненый враг рядом, враг бьёт героя или союзника дольше секунды, союзник бьёт раненого врага (рецензия 11:
-- стычка от одного удара-размена поддерживала сама себя и гналась без предела)
X.SKIRMISH_PLANS = { farm = true, push = true, defend = true, group = true, follow = true }
X.SKIRMISH_R = 900      -- враг ближе — можно вступить в стычку
X.SKIRMISH_HP = 45      -- у себя меньше — в стычку не вступать (добить раненого — от 30)
X.SKIRMISH_HOLD = 3     -- с: стычка держится после последнего повода
X.SKIRMISH_LEASH = 1500 -- не гнаться дальше этого от места, где стычка началась (дальше теряется и опыт волны)
X.SKIRMISH_BAN = 6      -- с: цель, за которой не погнались дальше поводка, столько не брать снова (иначе поводок
                        -- начинался бы заново с нового места)
X.HIT_SUSTAIN = 1.0     -- с: «бьёт» — бьёт столько подряд (один удар-размен — не повод)
X.HELP_R = 700          -- враг ближе к союзнику — союзник в бою
X.HELP_HP = 70          -- союзника выручать и раненого врага добивать вместе — ниже этой доли здоровья
X.NUMBERS_R = 1200      -- своих и врагов считать в этом радиусе: против перевеса не вступать
X.HARASS_HP = 60        -- размен ударом или способностью — когда у себя здоровья не меньше (research/05: удар с руки
                        -- переключает на ударившего вражеских крипов рядом; саппорту — не ниже 60 %)
X.HARASS_REACH = 150    -- за ударом-разменом подойти не дальше досягаемости + столько; керри не подходит (гайды:
                        -- керри на линии не дерётся — бьёт, только когда враг сам подошёл добивать)
X.HARASS_GAP = { ranged = 2.5, melee = 3.5 }   -- с между ударами-разменами
X.HARASS_CAST_GAP = 8   -- с между способностями-разменами
-- размен способностью — только уроном, без оглушений и контроля (рецензия 11: Lion отдавал Earth Spike и хекс, и к гангу
-- всё было в откате). Список — по KV героев списка ботов (сверил рецензент 11)
X.HARASS_SPELLS = { lina_dragon_slave = true, jakiro_dual_breath = true, crystal_maiden_crystal_nova = true,
                    viper_nethertoxin = true, sniper_shrapnel = true, luna_lucent_beam = true,
                    bristleback_viscous_nasal_goo = true }
X.HARASS_MANA = { 80, 70, 70, 50, 50 }          -- размен способностью при мане не меньше (%, по позициям 1–5)
-- площадные способности по врагам, у которых в KV цель не указана (рецензия 10 сверила KV героев списка ботов):
-- без списка рефлекс их не видит
X.ENEMY_AOE = { sniper_shrapnel = true, viper_nethertoxin = true, axe_berserkers_call = true,
                crystal_maiden_crystal_nova = true, lina_light_strike_array = true, witch_doctor_maledict = true }
X.ULT_BY_CAST = { axe_culling_blade = true }   -- убивает только ниже порога — рефлекс не угадает; агент называет сам

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
  if cost <= 0 and not FREE_ITEMS[name] then
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

-- добивание на подходе: рядом вражеский крип, которому хватит двух ударов, — не отвлекаться на размен
local function lasthit_soon(hero, world, creeps)
  local my, range = world.pos(hero), world.attack_range(hero)
  for _, c in ipairs(creeps or world.lane_creeps(hero, range + 300, true)) do
    if world.dist(my, world.pos(c)) <= range + 300 and world.hp(c) <= 2 * world.damage(hero, c) * world.armor_factor(c) then
      return true
    end
  end
  return false
end

-- рефлекс «способности в бою»: одно применение за шаг. В драке, обороне, спасении и пуше — по ближайшему видимому
-- врагу (или цели плана), ульта — только в драке, обороне и спасении (и когда враг ранен или их двое рядом). В прочих
-- планах — только добить слабого врага или отбиться, когда сам ранен и враг вплотную; при отходе — без ульты, по
-- догоняющему. Только способности по врагам: не переключатели, не автоатаки, не по союзникам — их называет агент.
-- В стычке (mode "skirmish") — как в драке, по цели стычки; на фарме при запасе маны — размен способностью по цели
-- или в точку, без ульты.
local function auto_cast(st, ag, world, now, mode)
  if now < (st.auto_next or 0) then return nil end
  local hero, team = ag.hero, ag.team
  local plan = st.plan and st.plan.kind or ""
  local my = world.pos(hero)
  local target = nil
  if mode == "skirmish" and st.skirmish then target = st.skirmish.target end
  if target == nil and st.plan and st.plan.target ~= "" then target = world.enemy_hero(team, st.plan.target) end
  target = target or world.nearest_enemy(team, my, 1600)
  if target == nil then return nil end
  if world.magic_immune(target) or world.silenced(hero) then return nil end   -- приказ отклонят — не дёргать
  if plan == "retreat" then mode = "escape" end      -- отход выбрал агент — руки отходят, а не добивают
  local d = world.dist(my, world.pos(target))
  local fight = mode ~= "escape" and (X.AUTO_PLANS[plan] or mode == "skirmish")
  local harass = false
  if not fight then
    local weak = world.hp_pct(target) <= X.KILL_HP
    local pressed = world.hp_pct(hero) < X.DEFEND_HP and d <= X.DEFEND_NEAR
    if mode == "escape" then
      if d > X.DEFEND_NEAR then return nil end
    elseif not weak and not pressed then
      -- размен способностью на фарме: маны с запасом, здоровья хватает, враг не у своей вышки, добивание не на подходе;
      -- не чаще HARASS_CAST_GAP и только уроном (HARASS_SPELLS)
      harass = plan == "farm" and now >= (st.harass_cast_next or 0) and world.hp_pct(hero) >= X.HARASS_HP
          and world.mana_pct(hero) >= (X.HARASS_MANA[ag.pos] or 70)
          and not world.near_enemy_tower(team, world.pos(target), X.TOWER_KEEP)
          and not lasthit_soon(hero, world)
      if not harass then return nil end
    end
  end
  st.auto_tried = st.auto_tried or {}
  -- ульта: в драке, обороне, спасении — по раненому (≤ 70 %) или когда врагов двое; в стычке — только по врагу ниже
  -- половины здоровья (рецензия 11: «двое врагов рядом» на боковой линии есть почти всегда — ульта уходила в первую стычку)
  local ult_ok
  if mode == "skirmish" and not X.ULT_PLANS[plan] then
    ult_ok = world.hp_pct(target) <= 50
  else
    ult_ok = mode ~= "escape" and X.ULT_PLANS[plan]
        and (world.hp_pct(target) <= 70 or #world.enemies_near(team, world.pos(target), 700) >= 2)
  end
  local pick = nil
  for pass = 1, 2 do                                        -- сначала обычные способности, потом ульта
    for _, ab in ipairs(world.abilities(hero)) do
      local i = world.ability_info(ab, hero)
      -- канальные — только через cast (рецензия 10: Mana Drain при отходе держал героя на месте 5 с); при отходе и
      -- «отбиться» — только по цели или в точку: без цели бывают баффы на себя с замедлением (Take Aim)
      local calm = fight or (i.behavior == "target" or i.behavior == "point")
      local usable = i.level > 0 and i.behavior ~= "passive" and i.ready and (i.enemy or X.ENEMY_AOE[i.name])
          and not i.toggle and not i.autocast and not i.channel and calm and not X.ULT_BY_CAST[i.name]
          and (not harass or X.HARASS_SPELLS[i.name])
          and (pass == 2) == i.ult and (not i.ult or ult_ok)
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
  if harass then st.harass_cast_next = now + X.HARASS_CAST_GAP end
  local act = { kind = "cast", ability = pick.ab, behavior = i.behavior, name = i.name, auto = true,
                busy = (i.cast_point or 0) + X.AFTER_CAST }
  if i.behavior == "target" then act.target = target
  elseif i.behavior == "point" then act.point = world.pos(target) end
  return act
end

-- кого враг бьёт и сколько уже подряд (по шагам): один удар-размен — не повод для стычки (рецензия 11)
local function hits(st, world, e, now)
  st.att = st.att or {}
  local id, v = world.id(e), world.attack_target(e)
  local r = st.att[id]
  if r == nil or r.victim ~= v or now - r.seen > 1 then
    r = { victim = v, since = now }
    st.att[id] = r
  end
  r.seen = now
  return v, now - r.since
end

-- рефлекс «стычка»: на фарме, пуше, обороне, сборе и «за» руки сами вступают в бой рядом, когда повод виден сейчас:
-- добить раненого врага (≤ KILL_HP) в досягаемости + 300; ответить врагу, который бьёт героя дольше HIT_SUSTAIN;
-- выручить союзника (< HELP_HP), которого враг бьёт дольше HIT_SUSTAIN; поддержать удар союзника по раненому врагу
-- (≤ HELP_HP). Керри на фарме — только добить и ответить (гайды: керри на линии не дерётся). Не у вражеской вышки, не
-- против перевеса (врагов у цели больше, чем своих рядом; раненого — на одного больше) и не дальше SKIRMISH_LEASH от
-- места начала. Цель держится, пока у неё есть повод (новую берём, только если она раненая, а прежняя — нет), и ещё
-- SKIRMISH_HOLD с после. → { target, why, origin } или nil
local function skirmish(st, ag, world, now)
  local plan = st.plan and st.plan.kind or ""
  if not X.SKIRMISH_PLANS[plan] then
    st.skirmish = nil
    return nil
  end
  local hero, team = ag.hero, ag.team
  local my = world.pos(hero)
  local hp = world.hp_pct(hero)
  local mates = world.allies_near(team, my, X.NUMBERS_R)
  local carry_farm = ag.pos == 1 and plan == "farm"
  local reach = world.attack_range(hero) + 300
  local sk = st.skirmish
  if sk and world.alive(sk.target) and world.dist(sk.origin, world.pos(sk.target)) > X.SKIRMISH_LEASH then
    st.skirmish_ban = { target = sk.target, until_t = now + X.SKIRMISH_BAN }   -- дальше поводка — бросить и не брать
    sk = nil
  end
  local ban = st.skirmish_ban
  if ban and now >= ban.until_t then ban, st.skirmish_ban = nil, nil end
  local function safe(e)
    local ep = world.pos(e)
    return not (ban and ban.target == e) and not world.near_enemy_tower(team, ep, X.TOWER_KEEP)
        and #world.enemies_near(team, ep, X.NUMBERS_R) <= mates + (world.hp_pct(e) <= X.KILL_HP and 1 or 0)
  end
  local why_of, best, best_hp = {}, nil, 1e9
  for _, e in ipairs(world.enemies_near(team, my, X.SKIRMISH_R)) do
    local ehp = world.hp_pct(e)
    local victim, for_s = hits(st, world, e, now)
    local why = nil
    if safe(e) then
      if ehp <= X.KILL_HP and hp >= 30 and world.dist(my, world.pos(e)) <= reach then
        why = "добиваю"
      elseif hp >= X.SKIRMISH_HP then
        if victim == hero and for_s >= X.HIT_SUSTAIN and ehp <= hp + 15 then why = "отвечаю" end
        for pos = 1, 5 do
          if why or carry_farm then break end
          local a = world.ally_hero(team, pos)
          if a and a ~= hero then
            if victim == a and for_s >= X.HIT_SUSTAIN and world.hp_pct(a) < X.HELP_HP
                and world.dist(world.pos(a), world.pos(e)) <= X.HELP_R then
              why = "выручаю " .. pos
            elseif ehp <= X.HELP_HP and world.attack_target(a) == e and world.dist(world.pos(a), my) <= X.SKIRMISH_R then
              why = "вместе с " .. pos
            end
          end
        end
      end
    end
    if why then
      why_of[e] = why
      if ehp < best_hp then best, best_hp = e, ehp end
    end
  end
  for id, r in pairs(st.att or {}) do                       -- врагов, которых давно не видно, — забыть
    if now - r.seen > 3 then st.att[id] = nil end
  end
  if sk and why_of[sk.target] and not (world.hp_pct(best) <= X.KILL_HP and world.hp_pct(sk.target) > X.KILL_HP) then
    sk.why, sk.until_t = why_of[sk.target], now + X.SKIRMISH_HOLD          -- прежняя цель — пока есть повод
  elseif best then
    sk = { target = best, why = why_of[best], until_t = now + X.SKIRMISH_HOLD, origin = my }
  elseif sk then                                    -- повода нет: держим недолго, если цель рядом и по-прежнему можно
    local still = false
    if now <= sk.until_t and hp >= 30 then
      for _, e in ipairs(world.enemies_near(team, my, X.SKIRMISH_R + 300)) do
        if e == sk.target then still = safe(e) end
      end
    end
    if not still then sk = nil end
  end
  st.skirmish = sk
  return sk
end

-- рефлекс «расходники»: как делает каждый игрок — лечилка и кларити, когда ранен и врага рядом нет (их сбивает урон),
-- волшебный огонь и палочка, когда здоровья мало и враг рядом. Раз в секунду, только из инвентаря.
X.FLASK_HP, X.CLARITY_MP, X.PANIC_HP, X.SAFE_R, X.TANGO_HP, X.TREE_R = 55, 35, 25, 900, 75, 400
X.TANGO_RETRY = 20      -- с между попытками съесть танго
local function consume(st, ag, world, now)
  if now < (st.consume_next or 0) then return nil end
  local hero = ag.hero
  local hp = world.hp_pct(hero)
  local danger = world.nearest_enemy(ag.team, world.pos(hero), X.SAFE_R) ~= nil
  local at_fountain = world.in_shop(hero)               -- у фонтана лечит фонтан
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
  if not danger and not at_fountain then
    if hp <= X.FLASK_HP and not world.has_modifier(hero, "modifier_flask_healing") then
      local a = use("item_flask", true)
      if a then return a end
    end
    if world.mana_pct(hero) <= X.CLARITY_MP and not world.has_modifier(hero, "modifier_clarity_potion") then
      local a = use("item_clarity", true)
      if a then return a end
    end
    if hp <= X.TANGO_HP and now >= (st.tango_next or 0) and not world.has_modifier(hero, "modifier_tango_heal") then
      local it = world.main_item(hero, "item_tango_single") or world.main_item(hero, "item_tango")   -- живой матч:
      local tree = it and world.ability_info(it, hero).ready                                        -- 3 пачки не тронуты
          and world.safe_tree(ag.team, world.pos(hero), X.TREE_R, X.TOWER_KEEP)
      if tree then
        st.consume_next = now + 1.0
        st.tango_next = now + X.TANGO_RETRY          -- не съел (дерево не достать) — не замирать на попытках (рецензия 10б)
        return { kind = "cast", ability = it, behavior = "tree", tree = tree, name = world.ability_name(it), auto = true,
                 busy = 1.5 }
      end
    end
  end
  st.consume_next = now + 1.0
  return nil
end

-- --- план → приказ движения/атаки ---

-- скорость, с которой крип теряет здоровье: по замеру окно назад (шаг 0.25 с — ровно LH_WINDOW)
local function creep_rate(st, c, world, now)
  st.creeps = st.creeps or {}
  local id, hp = world.id(c), world.hp(c)
  local r = st.creeps[id]
  if r == nil or now - r.seen > X.LH_KEEP or hp > r.pts[#r.pts].hp then   -- новый крип (или номер занял другой)
    r = { pts = {} }
    st.creeps[id] = r
  end
  r.seen = now
  local pts = r.pts
  if #pts == 0 or now > pts[#pts].t then pts[#pts + 1] = { t = now, hp = hp } end
  while #pts > 1 and now - pts[2].t >= X.LH_WINDOW - 1e-6 do table.remove(pts, 1) end   -- первый — окно назад
  local span = now - pts[1].t
  if span < X.LH_WINDOW - 1e-6 then return 0 end
  return math.max(0, (pts[1].hp - hp) / span)
end

-- замеры крипов, которых давно не видели, — убрать (номер сущности может занять новый крип)
local function forget_creeps(st, now)
  for id, r in pairs(st.creeps or {}) do
    if now - r.seen > X.LH_KEEP then st.creeps[id] = nil end
  end
end

-- удар героя по крипу: → через сколько попадёт (дойти, замах, полёт снаряда) и сколько длится до выстрела (дойти, замах)
local function hit_time(hero, c, world)
  local d = world.dist(world.pos(hero), world.pos(c))
  local range = world.attack_range(hero)
  local walk = math.max(0, d - range) / math.max(100, world.speed(hero))
  local windup = walk + world.attack_point(hero)
  local fly = world.is_ranged(hero) and math.min(d, range) / math.max(300, world.projectile_speed(hero)) or 0
  return windup + fly, windup
end

-- бить ли сейчас: к попаданию у крипа будет не больше LH_MARGIN урона, и он ещё жив. Ближний бой (попадание через
-- ~0.3 с: за это время удара крипа может и не быть) — только когда хватает удара уже сейчас (модель рецензии 11:
-- иначе 9 ранних ударов из 60). → да/нет, здоровье к удару, замах
local function lasthit_now(st, hero, c, world, now)
  local rate = creep_rate(st, c, world, now)
  local t, windup = hit_time(hero, c, world)
  local hp = world.hp(c)
  local pred = hp - rate * t
  local dmg = world.damage(hero, c) * world.armor_factor(c)
  return pred <= dmg * X.LH_MARGIN and pred > 0 and (world.is_ranged(hero) or hp <= dmg), pred, windup
end

-- лучший крип для удара сейчас среди creeps (только в досягаемости + 300); остальных — замерять. → крип, замах
local function pick_lasthit(st, hero, creeps, world, now, filter)
  local my, range = world.pos(hero), world.attack_range(hero)
  local best, best_pred, best_w = nil, 1e18, 0
  for _, c in ipairs(creeps) do
    if (filter == nil or filter(c)) and world.dist(my, world.pos(c)) <= range + 300 then
      local ok, pred, windup = lasthit_now(st, hero, c, world, now)
      if ok and pred < best_pred then best, best_pred, best_w = c, pred, windup end
    else
      creep_rate(st, c, world, now)
    end
  end
  return best, best_w
end

-- кор своей линии рядом с саппортом — добивания ему. Только кор, чья линия — эта (рецензия 10: на старте у фонтана
-- Lion шёл за Sniper на бот), и только когда кор у линии (не провожать его на базу)
local function core_near(ag, world, lane)
  if ag.pos ~= 4 and ag.pos ~= 5 then return nil end
  local my = world.pos(ag.hero)
  for pos = 1, 3 do
    local ally = world.ally_hero(ag.team, pos)
    if ally and ally ~= ag.hero and X.default_lane(ag.team, pos) == lane
        and world.dist(my, world.pos(ally)) <= X.SUPPORT_SHARE and world.lane_dist(ag.team, lane, world.pos(ally)) <= 1500 then
      return ally, pos
    end
  end
  return nil
end

-- размен ударом на линии: враг в досягаемости (подойти — не дальше HARASS_REACH), у себя здоровья не меньше HARASS_HP
-- и не меньше, чем у него, без 10; оба не у вражеской вышки; врагов у него не больше, чем своих рядом; добивание или
-- денай не на подходе (крип из creeps рядом слабее двух ударов); ближнему бою — когда вражеских крипов рядом не больше
-- двух (крипы бьют того, кто бьёт их героя). Один удар — и снова к крипам; следующий — через HARASS_GAP.
local function harass_order(st, ag, world, now, creeps, tag)
  if now < (st.harass_next or 0) then return nil end
  local hero, team = ag.hero, ag.team
  local my = world.pos(hero)
  local range = world.attack_range(hero)
  local e = world.nearest_enemy(team, my, range + (ag.pos == 1 and 0 or X.HARASS_REACH))
  if e == nil then return nil end
  local hp = world.hp_pct(hero)
  if hp < X.HARASS_HP or hp + 10 < world.hp_pct(e) then return nil end
  if world.near_enemy_tower(team, world.pos(e), X.TOWER_KEEP) or world.near_enemy_tower(team, my, X.TOWER_KEEP)
      or #world.enemies_near(team, world.pos(e), X.NUMBERS_R) > world.allies_near(team, my, X.NUMBERS_R) then
    return nil
  end
  if lasthit_soon(hero, world, creeps) then return nil end
  local ranged = world.is_ranged(hero)
  if not ranged and #world.lane_creeps(hero, 500, true) > 2 then return nil end
  st.harass_next = now + (ranged and X.HARASS_GAP.ranged or X.HARASS_GAP.melee)
  local walk = math.max(0, world.dist(my, world.pos(e)) - range) / math.max(100, world.speed(hero))
  return { kind = "attack", target = e, busy = math.min(1.5, walk + world.attack_point(hero) + 0.1),
           why = tag .. ": бью " .. world.short(world.name(e)) }
end

-- свои крипы для денаев: ниже половины здоровья и не у вражеской вышки (рецензия 11: ближний бой шёл под выстрел)
local function deny_ok(team, world)
  return function(c)
    return world.hp_pct(c) < X.DENY_PCT and not world.near_enemy_tower(team, world.pos(c), X.TOWER_KEEP)
  end
end

local function farm_order(st, ag, world, lane, now)
  local hero, team = ag.hero, ag.team
  local my = world.pos(hero)
  local tag = "фарм " .. LANE_RU[lane]
  local core, core_pos = core_near(ag, world, lane)
  if core then                                  -- саппорт на линии с кором: свои крипы — добить, враг — бить, если
    tag = "линия с " .. core_pos                 -- безопасно; вражеских крипов не добивать: опыт идёт и так
    local range = world.attack_range(hero)
    local own = world.lane_creeps(hero, range + 300, false)
    local deny, dt = pick_lasthit(st, hero, own, world, now, deny_ok(team, world))
    if deny then return { kind = "attack", target = deny, busy = math.min(1.5, dt + 0.1), why = tag .. ": добиваю своего" } end
    local h = harass_order(st, ag, world, now, own, tag)          -- бить врага, когда безопасно: ударом — и назад
    if h then return h end
    local cp = world.pos(core)
    local spot = world.keep_from_tower(team, lane, toward(cp, world.lane_enemy_front(team, lane), 200), X.TOWER_KEEP)
                                                     -- впереди кора, к врагу (гайды: research/05), не под их вышкой
    if world.dist(my, spot) > 300 then
      return { kind = "move", point = spot, why = tag .. ": встаю впереди своего" }
    end
    return { kind = "hold", why = tag .. ": стою впереди своего" }
  end
  local enemies = {}
  for _, c in ipairs(world.lane_creeps(hero, X.FARM_NEAR, true)) do   -- под вражеской вышкой не добивать
    if not world.near_enemy_tower(team, world.pos(c), X.TOWER_KEEP) then enemies[#enemies + 1] = c end
  end
  if #enemies == 0 then                         -- вражеских крипов рядом нет: к своей волне, без неё — к середине линии
    local front = world.wave_front(team, lane)
    local base = world.lane_front(team, lane)
    local p = front and world.clear(toward(front, base, 250), base) or world.lane_mid(team, lane)
    p = world.keep_from_tower(team, lane, p, X.TOWER_KEEP)
    local h = harass_order(st, ag, world, now, {}, tag)            -- между волнами враг рядом — размен ударом
    if h then return h end
    if world.dist(my, p) > 300 then
      return { kind = "move", point = p, why = tag .. (front and ": иду к своей волне" or ": иду к линии") }
    end
    return { kind = "hold", why = tag .. ": жду волну" }
  end
  local range = world.attack_range(hero)
  local best, bt = pick_lasthit(st, hero, enemies, world, now)
  if best then return { kind = "attack", target = best, busy = math.min(1.5, bt + 0.1), why = tag .. ": добиваю" } end
  local deny, dt = pick_lasthit(st, hero, world.lane_creeps(hero, range + 300, false), world, now, deny_ok(team, world))
  if deny then return { kind = "attack", target = deny, busy = math.min(1.5, dt + 0.1), why = tag .. ": добиваю своего" } end
  local h = harass_order(st, ag, world, now, enemies, tag)       -- добивание не на подходе — размен ударом с героем
  if h then return h end
  -- где ждать: у крипа, которого скоро добивать (меньше всех здоровья через секунду по замеру), среди ближних к герою —
  -- не дальше ближайшего + 200 (рецензия 11: ближний бой уходил за спины вражеских ближних к их дальнему крипу)
  local near = world.dist(my, world.pos(enemies[1]))           -- enemies — от ближнего к дальнему (FIND_CLOSEST)
  if not world.is_ranged(hero) and near <= range + 250 then      -- ближний бой у волны — стоять, как раньше
    return { kind = "hold", why = tag .. ": жду добивание" }
  end
  local soon, shp = enemies[1], 1e18
  for _, c in ipairs(enemies) do
    if world.dist(my, world.pos(c)) <= near + 200 then
      local h1 = world.hp(c) - creep_rate(st, c, world, now) * 1.0
      if h1 < shp then soon, shp = c, h1 end
    end
  end
  local np = world.pos(soon)
  if world.dist(my, np) > range + 50 then
    return { kind = "move", point = toward(np, my, range - 50), why = tag .. ": к крипам" }
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
    return farm_order(st, ag, world, lane_of(plan, ag) or X.default_lane(team, ag.pos), now)
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
    if order.busy then st.busy_until = math.max(st.busy_until or 0, now + order.busy) end   -- замах не сбивать
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
  local dt = math.max(0, math.min(1, now - (st.step_t or now)))
  st.step_t = now
  if not world.alive(hero) then
    if st.buyback and world.can_buyback(hero) then
      acts[#acts + 1] = { kind = "buyback" }
      st.buyback = false
    end
    local b = buy_step(st, hero, world, now, true)
    if b then acts[#acts + 1] = b end
    st.retreating, st.last, st.busy_until, st.skirmish = false, nil, 0, nil
    st.status = string.format("мёртв, %d с", math.floor((tonumber(world.respawn(hero)) or 0) + 0.5))
    return acts
  end
  if st.last and st.last.kind == "hold" then st.idle = (st.idle or 0) + dt end   -- простой рук (Д20: число для учёбы)
  forget_creeps(st, now)
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
  local hp = world.hp_pct(hero)
  local last = st.last
  if last and last.kind == "attack" and last.target and now < st.busy_until and st.active == nil then
    -- замах удара не ждать: цель умерла раньше попадания; здоровье ниже порога отхода; бьёт вражеская вышка
    -- (рецензия 11: замах до 1.5 с откладывал отход). Применение способности так не прерывается
    if not world.alive(last.target) or (st.retreat_hp > 0 and hp < st.retreat_hp)
        or world.tower_hitting(ag.team, hero, X.TOWER_KEEP) then
      st.busy_until = now
    end
  end
  if world.is_channeling(hero) or now < st.busy_until then return acts end

  local want_acquire = not (st.plan and st.plan.kind == "farm")
  if st.acquire ~= want_acquire then                    -- на фарме руки бьют только добивания и денаи сами
    st.acquire = want_acquire
    acts[#acts + 1] = { kind = "acquire", on = want_acquire }
  end

  local u = consume(st, ag, world, now)
  if u then
    acts[#acts + 1] = u
    st.busy_until = now + u.busy
    st.status = "пью/жму " .. u.name
    return acts
  end

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

  local function cast(c)
    acts[#acts + 1] = c
    st.busy_until = now + (c.busy or X.AFTER_CAST)
    st.last = nil                                            -- после применения приказ движения выдать заново
    st.status = (c.auto and "бью способностью " or "применяю ") .. c.name
    return acts
  end
  local c = cast_step(st, ag, world, now)                    -- применения агента — раньше рефлексов (рецензия 11)
  if c then return cast(c) end

  -- рефлекс «из-под вышки»: вражеская вышка бьёт героя — отойти за её досягаемость, если это не драка с запасом
  -- здоровья (на фарме, пуше, при отходе и прочем — всегда; в драке и спасении — когда здоровья меньше половины)
  local tw = world.tower_hitting(ag.team, hero, X.TOWER_KEEP)
  if tw and (not (st.plan and (st.plan.kind == "fight" or st.plan.kind == "save")) or hp < 50) then
    return issue(st, acts, { kind = "move", point = toward(tw.pos, world.pos(hero), X.TOWER_KEEP + 150),
                             why = "отхожу из-под вышки" }, now, world)
  end

  local sk = skirmish(st, ag, world, now)
  c = auto_cast(st, ag, world, now, sk and "skirmish" or nil)
  if c then return cast(c) end
  if sk then
    return issue(st, acts, { kind = "attack", target = sk.target,
                             why = "стычка: " .. sk.why .. ", бью " .. world.short(world.name(sk.target)) }, now, world)
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
X._creep_rate = creep_rate              -- для тестов: замер скорости потери здоровья

return X
