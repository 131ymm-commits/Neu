-- Ячейки проверки ремонтной катушки (FINAL_SPEC §11.7: R1–R8, R9 в паре прогонов, R10 сравнением двух прогонов,
-- R11), пилоты PILOT-10 (заряд буфера EEI secondary-input при energy_usage = 0), PILOT-24 (семантика фильтров
-- on_entity_damaged), PILOT-19 (прогон с поднятой версией тестового мода), а также: предел линий за цикл (V),
-- очередь длиннее QUEUE_CAP (Q), удаление поверхности с катушкой, клон и script_raised_revive.
-- Прогоны 30.09.2026 на 2.0.77: base, base + SA, повтор base (тот же sha256 results.json), base с поднятой версией —
-- 39 из 39 проверок в каждом.
--
-- ИНТЕРФЕЙС
--   local M = require("mend_tests")        -- модуль тестового мода; control.lua мода magnetics не трогает
--   M.END_TICK                             тик, на котором вызвать M.check (после M.tick того же тика)
--   M.BENCH_TICKS                          сколько тиков дать --benchmark (с запасом над END_TICK)
--   M.setup(ctx)                           один раз из on_init тестового мода (тик 0 сохранения, --create);
--                                          тестовый мод зависит от magnetics, поэтому on_init magnetics уже прошёл
--   M.tick(ctx, tick)                      на каждом on_tick (единый диспетчер тестового мода)
--   M.check(ctx)                           один раз на END_TICK; остальные проверки записаны раньше через ctx.check
-- Поля ctx:
--   surface         LuaSurface с плитками lab; чанки сгенерированы на квадрате [origin, origin + 512) по x и y
--   origin          {x = , y = }: левый верхний угол свободного квадрата 512×512 (ячейки через 128 клеток)
--   data            таблица в storage, принадлежащая модулю (переживает save/load)
--   check           function(group, name, ok, got, expected, note) — запись результата (в storage)
--   source          имя прототипа источника энергии primary-output (например "magnetics-test-source")
--   config_changed  true, если тестовый мод получил on_configuration_changed (прогон R9 с поднятой версией)
-- Нужные прототипы: magnetics-mend-coil, magnetics-magnet-wall (800 HP, без сопротивления poison), substation,
-- radar, assembling-machine-1, small-biter, ctx.source.
-- Побочные действия: на тике 5 (PILOT-24) модуль временно ставит свой обработчик on_entity_damaged ТЕСТОВОГО мода
-- и в том же тике возвращает прежний обработчик с прежним фильтром (в on_init пилот нельзя: пока идёт on_init мода,
-- события этому моду не приходят); на тиках 1200–1201 создаёт и удаляет поверхность "mend-tmp"; на тике 3200
-- уничтожает все катушки на ctx.surface. Проверка "последняя катушка ушла" требует, чтобы других катушек в мире
-- не было (другие ячейки стенда не должны ставить magnetics-mend-coil).
-- R9: в обычном прогоне катушка, созданная без raise_built, не лечит (контроль); в прогоне, где версия тестового
-- мода поднята между --create и --benchmark (ctx.config_changed = true), on_configuration_changed мода magnetics
-- перестраивает список, и та же катушка лечит 100 ± 5 HP за 600 тиков.
-- Время: урон наносится между циклами катушки (циклы на тиках, кратных 30), замеры тоже вне кратных 30,
-- чтобы порядок on_tick и on_nth_tick разных модов не влиял на счёт циклов.

local M = {}
M.END_TICK = 3420
M.BENCH_TICKS = 3500

local COIL = "magnetics-mend-coil"
local WALL = "magnetics-magnet-wall"
local G = "mend"
local CELLS = {"P10", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R11", "V", "P24", "Q"}

local function state() return remote.call("magnetics", "state") end
local function near(got, exp, tol) return type(got) == "number" and math.abs(got - exp) <= tol end

local function center(ctx, name)
  for k = 1, #CELLS do
    if CELLS[k] == name then
      return {x = ctx.origin.x + 64 + ((k - 1) % 4) * 128, y = ctx.origin.y + 64 + math.floor((k - 1) / 4) * 128}
    end
  end
  error("unknown cell " .. name)
end

local function create(ctx, name, pos, extra)
  local t = {name = name, position = pos, force = "player"}
  if extra then for k, v in pairs(extra) do t[k] = v end end
  local e = ctx.surface.create_entity(t)
  assert(e, "cannot create " .. name .. " at " .. pos.x .. "," .. pos.y)
  return e
end

local function at(c, dx, dy) return {x = c.x + dx, y = c.y + dy} end

-- Подстанция и источник к западу от катушки в (c.x, c.y): площадь снабжения подстанции 18×18 покрывает катушку.
local function power(ctx, c)
  create(ctx, "substation", at(c, -3, -3))
  create(ctx, ctx.source, at(c, -6, -3))
end

local function coil(ctx, c, dx, dy, raise)
  return create(ctx, COIL, at(c, dx or 0, dy or 0), {raise_built = raise ~= false})
end

local function wall(ctx, c, dx, dy, force)
  return create(ctx, WALL, at(c, dx, dy), force and {force = force} or nil)
end

local function hp(e) return e.valid and e.health or -1 end
local function sum_hp(list) local s = 0; for i = 1, #list do s = s + hp(list[i]) end; return s end

---------------------------------------------------------------------------------------------------------------------
-- PILOT-24: сколько раз обработчик с фильтром вызывается для каждой цели при трёх записях фильтра.
local TYPES = {"wall", "gate", "ammo-turret", "electric-turret", "fluid-turret", "artillery-turret", "radar"}
local function variants()
  local A, B, C = {}, {}, {}
  for i = 1, #TYPES do
    A[#A + 1] = {filter = "type", type = TYPES[i]}
    B[#B + 1] = {filter = "type", type = TYPES[i]}
    B[#B + 1] = {filter = "final-health", comparison = ">", value = 0, mode = "and"}
    C[#C + 1] = {filter = "type", type = TYPES[i]}
  end
  A[#A + 1] = {filter = "final-health", comparison = ">", value = 0, mode = "and"}   -- запись §6.1 буквально
  return {{"A_types_or_then_fh_and", A}, {"B_type_and_fh_pairs", B}, {"C_types_only", C}}
end

local function pilot24(ctx)
  local c = center(ctx, "P24")
  local counts, label_of, current = {}, {}, nil
  local targets = {
    {"wall_ok", WALL, 0.5, 10, "poison"}, {"wall_kill", WALL, 2.5, 1e5, "poison"},
    {"radar_ok", "radar", 6.5, 10, "poison"}, {"radar_kill", "radar", 10.5, 1e6, "poison"},
    {"assembler_ok", "assembling-machine-1", 14.5, 10, "poison"},
    {"biter_ok", "small-biter", 18.5, 1, "poison"}, {"biter_kill", "small-biter", 21.5, 1000, "poison"},
  }
  local vs = variants()
  local prev_handler = script.get_event_handler(defines.events.on_entity_damaged)
  local prev_filter = script.get_event_filter(defines.events.on_entity_damaged)
  for v = 1, #vs do
    current = vs[v][1]
    counts[current] = {}
    script.on_event(defines.events.on_entity_damaged, function(ev)
      local l = label_of[ev.entity.unit_number]
      if l then counts[current][l] = (counts[current][l] or 0) + 1 end
    end, vs[v][2])
    local made = {}
    for t = 1, #targets do
      local tg = targets[t]
      local force = tg[2] == "small-biter" and "enemy" or "player"
      local e = create(ctx, tg[2], at(c, tg[3], v * 10 + 0.5), {force = force})
      label_of[e.unit_number] = tg[1]
      counts[current][tg[1]] = 0
      made[#made + 1] = e
    end
    for t = 1, #targets do
      local tg = targets[t]
      local e = made[t]
      e.damage(tg[4], tg[2] == "small-biter" and "player" or "enemy", tg[5])
    end
    for t = 1, #made do if made[t].valid then made[t].destroy() end end
  end
  script.on_event(defines.events.on_entity_damaged, prev_handler, prev_filter)   -- вернуть обработчик стенда
  ctx.data.p24 = counts
  local expect = {  -- по документации: "and" связывает сильнее "or"
    A_types_or_then_fh_and = {wall_ok = 1, wall_kill = 1, radar_ok = 1, radar_kill = 0, assembler_ok = 0, biter_ok = 0, biter_kill = 0},
    B_type_and_fh_pairs    = {wall_ok = 1, wall_kill = 0, radar_ok = 1, radar_kill = 0, assembler_ok = 0, biter_ok = 0, biter_kill = 0},
    C_types_only           = {wall_ok = 1, wall_kill = 1, radar_ok = 1, radar_kill = 1, assembler_ok = 0, biter_ok = 0, biter_kill = 0},
  }
  for v = 1, #vs do
    local name = vs[v][1]
    local ok = true
    for l, n in pairs(expect[name]) do if counts[name][l] ~= n then ok = false end end
    -- пилот движка (семантика записи фильтра на обработчике тестового мода), не проверка мода: фильтр, который
    -- зарегистрировал сам мод, сверяет REG (ревью 01.10.2026, находка 20)
    ctx.check(G, "PILOT-24 " .. name, ok, counts[name], expect[name],
      "engine pilot on the test mod's own handler (not a check of the mod; the mod's filter is checked by REG); and binds tighter than or",
      "harness")
  end
end

---------------------------------------------------------------------------------------------------------------------
-- Ячейки ревью 01.10.2026 (находки 6, 10, 11, 12, 20; находка 9 — отдельный прогон tests.py: сохранение создаётся
-- с control.lua сборки fc2e2d8, бенчмарк идёт с текущим, ожидания те же). Всё, кроме роботопорта RB, ставится
-- в тиках бенчмарка 1300–1952: после R8 и удаления поверхности (их счёт катушек), до R3 на 3045 (к тому времени
-- записи очереди этих ячеек ушли или стоят неизменно). Ячейки стоят на своей поверхности "mend-review" (RS);
-- её катушки снимает общий снос на тике 3200.
--   HT  типы целей §6.1 (каменная стена, ворота, пулемётная, лазерная, огнемётная, артиллерийская турели, радар), каждая
--       у своей запитанной катушки, урон 100 physical на 1301: в очередь встают все 7, за 4 цикла лечится
--       min(недостача, 20). Сборочный автомат 1 (тип не из §6.1) — отрицательный контроль: не в очереди, 0.
--   RB  катушку строят роботы: роботопорт с 10 строительными роботами и сундук хранения с катушками (с настройки),
--       призрак из чертежа с power_production 1 ГВт и buffer_size 1 ГДж (1300). Ожидание: on_robot_built_entity
--       учтён (+1 катушка), настройки EEI сброшены, стена, повреждённая до постройки, долечена к 2900.
--       on_built_entity без игрока на сервере не вызвать (raise_event его не поднимает): его регистрацию сверяет REG.
--   BP  тот же чертёж без сети, оживление raise_revive: power_production 0, power_usage 0, буфер 1 МДж (§4.5);
--       за 300 тиков энергия 0 и стена рядом не лечится. Клон катушки, которой скрипт после учёта выставил 1 ГВт,
--       буфер 1 ГДж и 500 МДж энергии: настройки клона сброшены (путь on_entity_cloned), энергия срезана до 1 МДж.
--   DB  цели, построенные уже повреждёнными рядом с запитанной катушкой (1400): магнитная стена из предмета со
--       здоровьем 0,95, пулемётная турель из предмета 0,9 (script_raised_built), клон стены с 760 HP
--       (on_entity_cloned) — встают в очередь сразу и лечатся (3 цикла = бюджет 30 HP); целая стена в очередь не встаёт.
--   TF  четыре стены в очереди у одной катушки (урон 1501); на 1502 A сменила силу (катушек той силы рядом нет),
--       B телепортирована на 40 клеток, D телепортирована в радиус из-за его края. За 4 цикла: A и B — 0, C и D — по 20
--       (A и B не отнимают бюджет; D лечится по новой позиции).
--   CF  сила катушек K1 и K2 сменена скриптом на 1651 (события нет). K1 до смены лечила стену своей силы W1, после —
--       нет; стены новой силы W2 (у K1), W4 и W5 (у K2) повреждены на 1652, их урон отсекает on_damaged — в очередь их
--       ставит check_forces. За 10 циклов каждая получает не меньше 5 × (10 − L + 1), L = ceil(катушек / FORCE_CHECKS).
--   KW  смертельный урон по 5 стенам у катушки (1700) не ставит их в очередь; несмертельный по контрольной — ставит.
--       Перевод фильтра урона в запись §6.1 этим не ловится (страховка final_health <= 0 в on_damaged): его ловит REG.
--   REG фактические регистрации мода (remote "registrations", 1300, катушки есть): фильтр урона — ровно пары
--       (type = t, final-health > 0 c "and") по списку типов §6.1 (TYPES выше); каждое событие постройки §6.1 имеет
--       обработчик с фильтром «name = катушка или type из списка §6.1»; HEAL_TYPES мода — тот же список.

local F2 = "mend-f2"
-- Своя поверхность: участок модуля (ORIGIN 1024 в cells/mend.lua) лежит за краем карты лаборатории 2048×2048
-- (плитки out-of-map; create_entity их не проверяет, а чертёж, роботы и телепорт — проверяют).
local RS = "mend-review"
local REVIEW_CELLS = {"HT", "RB", "BP", "DB", "TF", "CF", "KW"}
local function rcenter(name)
  for k = 1, #REVIEW_CELLS do
    if REVIEW_CELLS[k] == name then return {x = -192 + ((k - 1) % 4) * 128, y = -64 + math.floor((k - 1) / 4) * 128} end
  end
  error("unknown review cell " .. name)
end
local function rctx(ctx)
  return {surface = game.surfaces[RS], source = ctx.source, data = ctx.data, check = ctx.check}
end
local SPEC_BUFFER = 1e6          -- §4.5: buffer_capacity = "1MJ"
local HT_TARGETS = {             -- {прототип, тип по §6.1 или nil}
  {"stone-wall", "wall"}, {"gate", "gate"}, {"gun-turret", "ammo-turret"}, {"laser-turret", "electric-turret"},
  {"flamethrower-turret", "fluid-turret"}, {"artillery-turret", "artillery-turret"}, {"radar", "radar"},
  {"assembling-machine-1", nil},
}
local HT_SPOTS = {{-45, -30}, {-15, -30}, {15, -30}, {45, -30}, {-45, 30}, {-15, 30}, {15, 30}, {45, 30}}
local BUILD_EVENTS_SPEC = {"on_built_entity", "on_robot_built_entity", "script_raised_built", "script_raised_revive",
                           "on_entity_cloned"}   -- §6.1; плюс on_space_platform_built_entity, если событие есть

-- Призрак катушки из чертежа с настройками EEI «энергия из ничего» (power_production 1 ГВт, buffer_size 1 ГДж).
local function blueprint_ghost(ctx, pos)
  local inv = game.create_inventory(1)
  local st = inv[1]
  st.set_stack{name = "blueprint"}
  st.set_blueprint_entities{{entity_number = 1, name = COIL, position = {0, 0}, buffer_size = 1e9,
                             power_production = 1e9 / 60, power_usage = 0}}
  local ghosts = st.build_blueprint{surface = ctx.surface, force = "player", position = pos,
                                    build_mode = defines.build_mode.forced}
  inv.destroy()
  for _, g in ipairs(ghosts) do
    if g.valid and g.name == "entity-ghost" and g.ghost_name == COIL then return g end
  end
  error("blueprint ghost not built at " .. pos.x .. "," .. pos.y)
end

local function from_item(ctx, name, pos, health)   -- постройка из предмета с неполным здоровьем
  local inv = game.create_inventory(1)
  inv.insert{name = name, count = 1, health = health}
  local e = ctx.surface.create_entity{name = name, position = pos, force = "player", item = inv[1], raise_built = true}
  inv.destroy()
  assert(e, "cannot create " .. name .. " from item")
  return e
end

local function eei_state(e)
  if not (e and e.valid) then return nil end
  return {pp = e.power_production, pu = e.power_usage, buffer = e.electric_buffer_size, energy = e.energy}
end
local function eei_reset(s)
  return s ~= nil and s.pp == 0 and s.pu == 0 and s.buffer == SPEC_BUFFER and s.energy <= SPEC_BUFFER
end

local function set_of(list) local s = {}; for _, v in ipairs(list) do s[v] = (s[v] or 0) + 1 end; return s end
local function same_set(a, b)
  if type(a) ~= "table" or type(b) ~= "table" or #a ~= #b then return false end
  local sa, sb = set_of(a), set_of(b)
  for k, n in pairs(sa) do if sb[k] ~= n then return false end end
  return true
end

-- Фильтр урона §15.1: ровно пары (type = t [or], final-health > 0 [and]) по списку §6.1, без invert.
local function damage_filter_ok(f)
  if type(f) ~= "table" or #f ~= 2 * #TYPES then return false end
  local types = {}
  for i = 1, #f, 2 do
    local a, b = f[i], f[i + 1]
    if a.filter ~= "type" or (a.mode or "or") ~= "or" or a.invert then return false end
    if b.filter ~= "final-health" or b.comparison ~= ">" or b.value ~= 0 or b.mode ~= "and" or b.invert then return false end
    types[#types + 1] = a.type
  end
  return same_set(types, TYPES)
end

-- Фильтр постройки: ровно "name = катушка" и "type = t" по списку §6.1, все через or, без invert.
local function build_filter_ok(f)
  if type(f) ~= "table" or #f ~= 1 + #TYPES then return false end
  local types, names = {}, {}
  for i = 1, #f do
    local a = f[i]
    if (a.mode or "or") ~= "or" or a.invert then return false end
    if a.filter == "type" then types[#types + 1] = a.type
    elseif a.filter == "name" then names[#names + 1] = a.name
    else return false end
  end
  return same_set(types, TYPES) and #names == 1 and names[1] == COIL
end

local function review_setup(ctx)
  local d = ctx.data
  if not game.forces[F2] then game.create_force(F2) end
  local S = game.create_surface(RS, {width = 1024, height = 1024})
  S.generate_with_lab_tiles = true
  S.always_day = true
  S.request_to_generate_chunks({0, 0}, 9)
  S.force_generate_chunk_requests()
  local rc = rctx(ctx)
  local c = rcenter("RB"); power(rc, c)
  local rp = create(rc, "roboport", at(c, -9, -10))
  rp.get_inventory(defines.inventory.roboport_robot).insert{name = "construction-robot", count = 10}
  create(rc, "storage-chest", at(c, 2.5, -8.5)).insert{name = COIL, count = 3}
  d.rb_wall = wall(rc, c, 5.5, 0.5)
end

local function review_tick(ctx, tick)
  local d = ctx.data
  local rc = rctx(ctx)
  if d.rb_ghost and not d.rb_built_tick and tick > 1300 and tick <= 2900 then
    -- счёт катушек сверяется с предыдущим тиком: в тике постройки другие ячейки катушек не ставят и не снимают
    local coils = state().coils
    if not d.rb_ghost.valid then
      local found = rc.surface.find_entities_filtered{name = COIL, position = rcenter("RB"), radius = 2}
      d.rb_built_tick = tick
      d.rb_found = #found
      d.rb_state = eei_state(found[1])
      d.rb_coils_delta = d.rb_coils_prev and coils - d.rb_coils_prev
    end
    d.rb_coils_prev = coils
  end
  if tick == 1300 then
    d.reg = remote.call("magnetics", "registrations")
    d.consts = remote.call("magnetics", "constants")
    local c = rcenter("HT")
    d.ht = {}
    for i, t in ipairs(HT_TARGETS) do
      local p = at(c, HT_SPOTS[i][1], HT_SPOTS[i][2])
      power(rc, p); coil(rc, p)
      d.ht[i] = create(rc, t[1], at(p, 5.5, 4.5))
    end
    c = rcenter("RB")
    d.rb_ghost = blueprint_ghost(rc, c)
    d.rb_wall.damage(50, "enemy", "poison"); d.rb_hp1300 = hp(d.rb_wall)
    c = rcenter("BP")
    local _, e = blueprint_ghost(rc, c).revive{raise_revive = true}
    d.bp_coil = e
    d.bp_after_revive = eei_state(e)
    d.bp_wall = wall(rc, c, 5.5, 0.5)
    local src = coil(rc, c, 40, 0)
    src.power_production = 1e9 / 60; src.electric_buffer_size = 1e9; src.energy = 5e8
    d.bp_src_state = eei_state(src)
    d.bp_clone = src.clone{position = at(c, 40, 20)}
    d.bp_clone_state = eei_state(d.bp_clone)
    src.destroy()
    c = rcenter("DB"); power(rc, c); coil(rc, c)
    d.db_far = wall(rc, c, 40.5, 0.5); d.db_far.health = 760   -- запись здоровья события не вызывает
    c = rcenter("TF"); power(rc, c); coil(rc, c)
    d.tf = {A = wall(rc, c, 5.5, 0.5), B = wall(rc, c, 0.5, 6.5), C = wall(rc, c, -5.5, 0.5), D = wall(rc, c, 50.5, 0.5)}
    c = rcenter("CF"); power(rc, c); power(rc, at(c, 40, 0))
    d.cf_k1 = coil(rc, c); d.cf_k2 = coil(rc, c, 40, 0)
    d.cf_w1 = wall(rc, c, 5.5, 0.5); d.cf_w2 = wall(rc, c, 0.5, 5.5, F2)
    d.cf_w4 = wall(rc, c, 45.5, 0.5, F2); d.cf_w5 = wall(rc, c, 40.5, 5.5, F2)
    c = rcenter("KW"); power(rc, c); coil(rc, c)
    d.kw = {}
    for k = 0, 4 do d.kw[#d.kw + 1] = create(rc, "stone-wall", at(c, 3.5 + k, 3.5)) end
    d.kw_ctrl = create(rc, "stone-wall", at(c, -4.5, 0.5))
  elseif tick == 1301 then
    local q0 = state().queue
    d.ht_hp0, d.ht_max = {}, {}
    for i = 1, 7 do
      d.ht[i].damage(100, "enemy", "physical")
      d.ht_hp0[i], d.ht_max[i] = d.ht[i].health, d.ht[i].max_health
    end
    local q1 = state().queue
    d.ht[8].damage(100, "enemy", "physical")
    d.ht_hp0[8], d.ht_max[8] = d.ht[8].health, d.ht[8].max_health
    d.ht_q = {heal_types = q1 - q0, control = state().queue - q1}
  elseif tick == 1305 then
    d.bp_wall.damage(100, "enemy", "poison"); d.bp_hp1305 = hp(d.bp_wall)
  elseif tick == 1400 then
    local c = rcenter("DB")
    local q0 = state().queue
    d.db = {from_item(rc, WALL, at(c, 5.5, 0.5), 0.95), from_item(rc, "gun-turret", at(c, -4, 5), 0.9),
            d.db_far.clone{position = at(c, -5.5, 0.5)}}
    d.db_q = state().queue - q0
    d.db_hp0 = {hp(d.db[1]), hp(d.db[2]), hp(d.db[3])}
    d.db_far.destroy()
    local q1 = state().queue
    d.db_whole = create(rc, WALL, at(c, 0.5, -5.5), {raise_built = true})
    d.db_q_whole = state().queue - q1
  elseif tick == 1411 then
    d.ht_hp1 = {}
    for i = 1, 8 do d.ht_hp1[i] = hp(d.ht[i]) end
  elseif tick == 1491 then
    d.db_hp1 = {hp(d.db[1]), hp(d.db[2]), hp(d.db[3])}
  elseif tick == 1501 then
    for _, k in ipairs({"A", "B", "C", "D"}) do d.tf[k].damage(100, "enemy", "poison") end
    d.tf_hp0 = {A = hp(d.tf.A), B = hp(d.tf.B), C = hp(d.tf.C), D = hp(d.tf.D)}
  elseif tick == 1502 then
    local c = rcenter("TF")
    d.tf.A.force = F2
    d.tf_moved = {B = d.tf.B.teleport(at(c, 40.5, 6.5)), D = d.tf.D.teleport(at(c, 0.5, -5.5)), A_force = d.tf.A.force.name}
  elseif tick == 1601 then
    d.cf_w1.damage(300, "enemy", "poison"); d.cf_w1_hp1601 = hp(d.cf_w1)
  elseif tick == 1605 then
    d.bp_hp1605 = hp(d.bp_wall); d.bp_energy1605 = d.bp_coil.valid and d.bp_coil.energy or -1
  elseif tick == 1621 then
    d.tf_hp1 = {A = hp(d.tf.A), B = hp(d.tf.B), C = hp(d.tf.C), D = hp(d.tf.D)}
  elseif tick == 1651 then
    d.cf_w1_hp1651 = hp(d.cf_w1)
    d.cf_k1.force = F2; d.cf_k2.force = F2
  elseif tick == 1652 then
    for _, w in ipairs({d.cf_w2, d.cf_w4, d.cf_w5}) do w.damage(100, "enemy", "poison") end
    d.cf_hp0 = {w1 = hp(d.cf_w1), w2 = hp(d.cf_w2), w4 = hp(d.cf_w4), w5 = hp(d.cf_w5)}
    d.cf_coils = state().coils
  elseif tick == 1700 then
    local q0 = state().queue
    for _, w in ipairs(d.kw) do w.damage(1e6, "enemy", "physical") end
    local q1 = state().queue
    local dead = 0
    for _, w in ipairs(d.kw) do if not w.valid then dead = dead + 1 end end
    d.kw_ctrl.damage(50, "enemy", "physical")
    d.kw_res = {lethal_q_delta = q1 - q0, dead = dead, control_q_delta = state().queue - q1}
  elseif tick == 1952 then
    d.cf_hp1 = {w1 = hp(d.cf_w1), w2 = hp(d.cf_w2), w4 = hp(d.cf_w4), w5 = hp(d.cf_w5)}
  elseif tick == 2900 then
    d.rb_hp2900 = hp(d.rb_wall)
  end
end

local function review_check(ctx)
  local d = ctx.data
  local chk = ctx.check
  -- REG
  local reg = d.reg or {}
  chk(G, "REG HEAL_TYPES of the mod = §6.1 list", same_set(d.consts and d.consts.HEAL_TYPES, TYPES),
    d.consts and d.consts.HEAL_TYPES, TYPES)
  chk(G, "REG on_entity_damaged: handler and filter = pairs (type and final-health > 0) over the §6.1 types (§15.1)",
    reg.damage and reg.damage.handler == true and damage_filter_ok(reg.damage.filter), reg.damage, "pairs over " .. table.concat(TYPES, ","))
  local names = {}
  for _, n in ipairs(BUILD_EVENTS_SPEC) do names[#names + 1] = n end
  if defines.events.on_space_platform_built_entity ~= nil then names[#names + 1] = "on_space_platform_built_entity" end
  for _, n in ipairs(names) do
    local rec
    for _, b in ipairs(reg.build or {}) do if b.event == n then rec = b end end
    chk(G, "REG " .. n .. ": handler with filter name = coil or type in §6.1 list",
      rec ~= nil and rec.handler == true and build_filter_ok(rec.filter), rec, "coil + " .. table.concat(TYPES, ","))
  end
  -- HT
  for i, t in ipairs(HT_TARGETS) do
    local healed = d.ht_hp1[i] - d.ht_hp0[i]
    local deficit = d.ht_max[i] - d.ht_hp0[i]
    if t[2] then
      local exp = math.min(deficit, 20)
      chk(G, "HT " .. t[1] .. " (" .. t[2] .. ") near a powered coil: healed min(deficit, 20) in 4 cycles",
        deficit > 0 and near(healed, exp, 1e-3), {healed = healed, deficit = deficit}, exp, "+-1e-3")
    else
      chk(G, "HT " .. t[1] .. " (not a §6.1 type): 0 healed", deficit > 0 and healed == 0, {healed = healed, deficit = deficit}, 0)
    end
  end
  chk(G, "HT damage queues the 7 targets, not the assembling machine", d.ht_q.heal_types == 7 and d.ht_q.control == 0,
    d.ht_q, {heal_types = 7, control = 0})
  -- RB
  chk(G, "RB robots built the coil from the ghost (on_robot_built_entity counted)",
    d.rb_built_tick ~= nil and d.rb_found == 1 and d.rb_coils_delta == 1,
    {tick = d.rb_built_tick, found = d.rb_found, coils_delta = d.rb_coils_delta}, {found = 1, coils_delta = 1})
  chk(G, "RB robot-built coil from an edited blueprint: EEI settings reset (pp 0, pu 0, buffer 1 MJ)", eei_reset(d.rb_state),
    d.rb_state, {pp = 0, pu = 0, buffer = SPEC_BUFFER})
  chk(G, "RB wall damaged before the robot build: fully healed by tick 2900", near(d.rb_hp2900, 800, 1e-3),
    {hp1300 = d.rb_hp1300, hp2900 = d.rb_hp2900, built = d.rb_built_tick}, 800)
  -- BP
  chk(G, "BP edited blueprint (1 GW, 1 GJ), revived: EEI settings reset", eei_reset(d.bp_after_revive),
    d.bp_after_revive, {pp = 0, pu = 0, buffer = SPEC_BUFFER})
  chk(G, "BP edited-blueprint coil without a grid: energy 0 and wall not healed in 300 ticks",
    d.bp_energy1605 == 0 and d.bp_hp1605 == d.bp_hp1305, {energy = d.bp_energy1605, hp1305 = d.bp_hp1305, hp1605 = d.bp_hp1605},
    {energy = 0, healed = 0})
  chk(G, "BP clone source carries edited settings (bench self-check)",
    d.bp_src_state ~= nil and d.bp_src_state.pp > 0 and d.bp_src_state.buffer == 1e9 and d.bp_src_state.energy > SPEC_BUFFER,
    d.bp_src_state, "pp > 0, buffer 1e9, energy > 1 MJ", nil, "harness")
  chk(G, "BP clone (on_entity_cloned): EEI settings reset, energy clamped to 1 MJ", eei_reset(d.bp_clone_state),
    d.bp_clone_state, {pp = 0, pu = 0, buffer = SPEC_BUFFER, energy = "<= 1e6"})
  -- DB
  chk(G, "DB built damaged (item health 0.95 wall, 0.9 turret, cloned 760 HP wall): queued at once", d.db_q == 3,
    {queued = d.db_q, hp = d.db_hp0}, 3)
  chk(G, "DB full-health wall built near the coil: not queued", d.db_q_whole == 0, d.db_q_whole, 0)
  local db_heal, db_each = 0, true
  for k = 1, 3 do
    local h = d.db_hp1[k] - d.db_hp0[k]
    db_heal = db_heal + h
    if not (h > 0) then db_each = false end
  end
  chk(G, "DB built-damaged targets healed in 3 cycles: each > 0, total = coil budget 30", db_each and near(db_heal, 30, 1e-3),
    {hp0 = d.db_hp0, hp1 = d.db_hp1, total = db_heal}, 30, "+-1e-3")
  -- TF
  chk(G, "TF bench: A switched force, B and D teleported", d.tf_moved.B == true and d.tf_moved.D == true and d.tf_moved.A_force == F2,
    d.tf_moved, {B = true, D = true, A_force = F2}, nil, "harness")
  local tfh = {}
  for _, k in ipairs({"A", "B", "C", "D"}) do tfh[k] = d.tf_hp1[k] - d.tf_hp0[k] end
  chk(G, "TF queued wall that changed force: 0 healed", tfh.A == 0, tfh.A, 0)
  chk(G, "TF queued wall teleported out of range: 0 healed", tfh.B == 0, tfh.B, 0)
  chk(G, "TF control wall keeps 5 HP per cycle (stale entries take no budget)", near(tfh.C, 20, 1e-3), tfh.C, 20)
  chk(G, "TF queued wall teleported into range: healed 5 HP per cycle", near(tfh.D, 20, 1e-3), tfh.D, 20)
  -- CF
  local L = math.ceil(d.cf_coils / d.consts.FORCE_CHECKS)
  local min_heal = 5 * (10 - L + 1)
  chk(G, "CF before the force change the coil heals its force's wall (10 in 2 cycles)",
    near(d.cf_w1_hp1651 - d.cf_w1_hp1601, 10, 1e-3), d.cf_w1_hp1651 - d.cf_w1_hp1601, 10)
  chk(G, "CF after coil.force = f2: the old force's wall gets 0", d.cf_hp1.w1 == d.cf_hp0.w1, d.cf_hp1.w1 - d.cf_hp0.w1, 0)
  for _, k in ipairs({"w2", "w4", "w5"}) do
    local h = d.cf_hp1[k] - d.cf_hp0[k]
    chk(G, "CF new force's wall " .. k .. " damaged after the change: healed >= 5 x (10 - L + 1) in 10 cycles",
      h >= min_heal - 1e-3, {healed = h, coils = d.cf_coils, L = L}, ">= " .. min_heal)
  end
  -- KW
  chk(G, "KW lethal damage to 5 walls next to a coil: queue unchanged", d.kw_res.dead == 5 and d.kw_res.lethal_q_delta == 0,
    d.kw_res, {dead = 5, lethal_q_delta = 0})
  chk(G, "KW non-lethal damage (control): queued", d.kw_res.control_q_delta == 1, d.kw_res.control_q_delta, 1)
end

---------------------------------------------------------------------------------------------------------------------
function M.setup(ctx)
  local d = ctx.data
  local st0 = state()
  d.state_at_setup_start = st0

  local c = center(ctx, "P10"); power(ctx, c); d.p10 = coil(ctx, c); d.p10_trace = {}

  c = center(ctx, "R1"); power(ctx, c); d.r1_coil = coil(ctx, c); d.r1 = wall(ctx, c, 5.5, 0.5)

  c = center(ctx, "R2"); power(ctx, c); coil(ctx, c)
  d.r2 = {wall(ctx, c, 5.5, 0.5), wall(ctx, c, 0.5, 5.5), wall(ctx, c, 4.5, 4.5)}

  c = center(ctx, "R3"); power(ctx, c); coil(ctx, c)
  d.r3_far = wall(ctx, c, 10.5, 0.5)     -- 10.51 клетки
  d.r3_near = wall(ctx, c, -0.5, 9.5)    -- 9.51 клетки, контроль

  c = center(ctx, "R4"); d.r4_coil = coil(ctx, c); d.r4 = wall(ctx, c, 5.5, 0.5)

  c = center(ctx, "R5"); d.r5_coil = coil(ctx, c); d.r5_coil.energy = 1e6
  d.r5_energy0 = d.r5_coil.energy
  d.r5 = {wall(ctx, c, 5.5, 0.5), wall(ctx, c, 0.5, 5.5), wall(ctx, c, 4.5, 4.5)}

  c = center(ctx, "R6"); power(ctx, c); d.r6_a = coil(ctx, c, 0, 0); d.r6_b = coil(ctx, c, 4, 0)
  d.r6 = wall(ctx, c, 2.5, 4.5)

  c = center(ctx, "R7"); power(ctx, c); coil(ctx, c); d.r7 = wall(ctx, c, 5.5, 0.5, "enemy")

  c = center(ctx, "R8"); power(ctx, c); d.r8_wall = wall(ctx, c, 5.5, 0.5)
  d.r8_hidden = coil(ctx, c, 0, -20, false)        -- для script_raised_revive на тике 1010

  c = center(ctx, "R9"); power(ctx, c); d.r9_coil = coil(ctx, c, 0, 0, false); d.r9 = wall(ctx, c, 5.5, 0.5)

  c = center(ctx, "R11"); power(ctx, c); coil(ctx, c)
  d.r11_a = wall(ctx, c, 5.5, 0.5); d.r11_b = wall(ctx, c, 0.5, 5.5)
  d.r11_a.damage(300, "enemy", "poison")           -- очередь не пуста в момент сохранения
  d.r11_a_hp0 = d.r11_a.health

  -- V: 6 катушек и 12 стен, больше 10 лечений за цикл (проверка предела линий).
  c = center(ctx, "V")
  create(ctx, "substation", at(c, 3, 9)); create(ctx, ctx.source, at(c, 7, 9))
  d.v_coils = {}
  for _, p in ipairs({{0, 0}, {3, 0}, {6, 0}, {0, 3}, {3, 3}, {6, 3}}) do d.v_coils[#d.v_coils + 1] = coil(ctx, c, p[1], p[2]) end
  d.v = {}
  for k = 0, 11 do d.v[#d.v + 1] = wall(ctx, c, -2.5 + k, -3.5) end

  review_setup(ctx)
  d.state_after_setup = state()
  ctx.check(G, "setup: handler registered while coils exist (create)", d.state_after_setup.handler_registered == true,
    d.state_after_setup, {handler_registered = true})
  ctx.check(G, "setup: coils known (raise_built ones only)", d.state_after_setup.coils == 16, d.state_after_setup.coils, 16,
    "P10 1, R1 1, R2 1, R3 1, R4 1, R5 1, R6 2, R7 1, R9 0, R11 1, V 6")

end

---------------------------------------------------------------------------------------------------------------------
local P10_TICKS = {[1] = true, [15] = true, [30] = true, [60] = true, [90] = true, [150] = true, [240] = true,
                   [270] = true, [285] = true, [290] = true, [295] = true, [299] = true, [300] = true, [301] = true,
                   [302] = true, [305] = true, [310] = true, [330] = true, [600] = true, [3100] = true}

function M.tick(ctx, tick)
  local d = ctx.data
  review_tick(ctx, tick)
  if P10_TICKS[tick] and d.p10.valid then
    d.p10_trace[#d.p10_trace + 1] = {tick = tick, energy = d.p10.energy}
  end
  if not d.first_tick then                          -- первый тик после загрузки сохранения (R11)
    d.first_tick = tick
    d.state_first_tick = state()
    d.r11_a_hp_first = hp(d.r11_a)
  end
  if tick == 5 then
    -- PILOT-24 идёт в тике, а не в on_init: пока идёт on_init мода, события этому моду не приходят
    -- ("No other events will be raised for the mod until it has finished this step", LuaBootstrap.on_init).
    d.state_before_p24 = state()
    pilot24(ctx)
    d.state_after_p24 = state()
  elseif tick == 45 then
    d.r1.damage(300, "enemy", "poison"); d.r1_hp45 = hp(d.r1)
    for _, w in ipairs(d.r2) do w.damage(300, "enemy", "poison") end; d.r2_hp45 = sum_hp(d.r2)
    d.r3_far.damage(300, "enemy", "poison"); d.r3_near.damage(300, "enemy", "poison")
    d.r3_hp45 = {hp(d.r3_far), hp(d.r3_near)}
    d.r4.damage(300, "enemy", "poison"); d.r4_hp45 = hp(d.r4)
    for _, w in ipairs(d.r5) do w.damage(300, "enemy", "poison") end; d.r5_hp45 = sum_hp(d.r5)
    d.r5_energy45 = d.r5_coil.energy
    d.r6.damage(300, "enemy", "poison"); d.r6_hp45 = hp(d.r6)
    d.r7.damage(300, "player", "poison"); d.r7_hp45 = hp(d.r7)
    d.r8_wall.damage(20, "enemy", "poison"); d.r8_hp45 = hp(d.r8_wall)
    d.r9.damage(300, "enemy", "poison"); d.r9_hp45 = hp(d.r9)
    for _, w in ipairs(d.v) do w.damage(300, "enemy", "poison") end
    d.state45 = state()
  elseif tick == 61 then
    d.lines61 = #rendering.get_all_objects("magnetics")
    d.v_hp61 = sum_hp(d.v)
  elseif tick == 75 then
    d.r1_hp75 = hp(d.r1)
  elseif tick == 100 then
    d.r11_b.damage(300, "enemy", "poison"); d.r11_b_hp100 = hp(d.r11_b)
    d.state100 = state()
  elseif tick == 345 then
    d.r5_hp345 = sum_hp(d.r5); d.r5_energy345 = d.r5_coil.energy
  elseif tick == 645 then
    d.r1_hp645 = hp(d.r1); d.r2_hp645 = sum_hp(d.r2); d.r3_hp645 = {hp(d.r3_far), hp(d.r3_near)}
    d.r4_hp645 = hp(d.r4); d.r4_energy645 = d.r4_coil.energy; d.r6_hp645 = hp(d.r6); d.r7_hp645 = hp(d.r7)
    d.r9_hp645 = hp(d.r9)
  elseif tick == 700 then
    d.r11_b_hp700 = hp(d.r11_b); d.r11_a_hp700 = hp(d.r11_a)
  elseif tick == 1000 then
    local c = center(ctx, "R8")
    d.r8_before = state().coils
    d.r8_hp1000 = hp(d.r8_wall)
    d.r8_coil = coil(ctx, c)
    d.r8_after_build = state().coils
  elseif tick == 1005 then
    local c = center(ctx, "R8")
    d.r8_clone = d.r8_coil.clone{position = at(c, 0, 20)}
    d.r8_after_clone = state().coils
  elseif tick == 1010 then
    local before = state().coils
    script.raise_script_revive{entity = d.r8_hidden}
    d.r8_revive_delta = state().coils - before
  elseif tick == 1060 then
    d.r8_hp1060 = hp(d.r8_wall)
  elseif tick == 1100 then
    d.r8_before_destroy = state().coils
    d.r8_coil.destroy(); d.r8_clone.destroy(); d.r8_hidden.destroy()
  elseif tick == 1102 then
    d.r8_after_destroy = state().coils
  elseif tick == 1200 then
    -- удаление поверхности с катушкой
    local tmp = game.create_surface("mend-tmp", {width = 64, height = 64})
    tmp.generate_with_lab_tiles = true
    tmp.request_to_generate_chunks({0, 0}, 1)
    tmp.force_generate_chunk_requests()
    local before = state().coils
    tmp.create_entity{name = COIL, position = {0, 0}, force = "player", raise_built = true}
    d.surf_delta_add = state().coils - before
    d.surf_before_delete = before
  elseif tick == 1201 then
    game.delete_surface("mend-tmp")
  elseif tick == 1215 then
    d.surf_after_delete = state().coils
  elseif tick == 3044 then
    d.damaged_3044 = {}                          -- диагностика: какие стены ещё повреждены (остаток очереди)
    for _, w in ipairs(ctx.surface.find_entities_filtered{name = WALL}) do
      if w.health < w.max_health then
        d.damaged_3044[#d.damaged_3044 + 1] = {x = w.position.x - ctx.origin.x, y = w.position.y - ctx.origin.y,
                                              force = w.force.name, hp = w.health}
      end
    end
  elseif tick == 3045 then
    d.r3_q0 = state().queue
    d.r3_hp3045 = hp(d.r3_far)
    d.r3_far.damage(10, "enemy", "poison")
    d.r3_q1 = state().queue
  elseif tick == 3075 then
    d.r3_q2 = state().queue
    d.r3_hp3075 = hp(d.r3_far)
  elseif tick == 3200 then
    d.state3200 = state()
    for _, surface in ipairs({ctx.surface, game.surfaces[RS]}) do   -- и катушки ячеек ревью
      for _, e in ipairs(surface.find_entities_filtered{name = COIL}) do e.destroy() end
    end
  elseif tick == 3202 then
    d.state3202 = state()
    local q = state().queue
    d.r1.damage(10, "enemy", "poison")
    d.r8_q_delta_after_last_coil = state().queue - q
  elseif tick == 3260 then
    d.state3260 = state()
  elseif tick == 3300 then
    -- Q: очередь длиннее QUEUE_CAP (очередь в этот момент пуста). 15 групп по 6 катушек с энергией 1 МДж (без сети)
    -- и 10 стен рядом; группы в 25 клетках друг от друга не делят стены, бюджет группы 60 HP > 10 стен × 5 HP,
    -- поэтому за цикл лечатся ровно все обработанные записи.
    local c = center(ctx, "Q")
    d.q_coils, d.q_walls = {}, {}
    for g = 0, 14 do
      local gx, gy = c.x - 50 + (g % 5) * 25, c.y - 25 + math.floor(g / 5) * 25
      for _, p in ipairs({{0, 0}, {2, 0}, {4, 0}, {0, 2}, {2, 2}, {4, 2}}) do
        local k = create(ctx, COIL, {x = gx + p[1], y = gy + p[2]}, {raise_built = true}); k.energy = 1e6
        d.q_coils[#d.q_coils + 1] = k
      end
      for w = 0, 9 do d.q_walls[#d.q_walls + 1] = create(ctx, WALL, {x = gx - 3.5 + w, y = gy - 2.5}) end
    end
    d.q_state_coils = state()
  elseif tick == 3305 then
    for _, w in ipairs(d.q_walls) do w.damage(300, "enemy", "poison") end
    d.q_state_damaged = state()
    d.q_hp0 = {}
    for k, w in ipairs(d.q_walls) do d.q_hp0[k] = w.health end
  elseif tick == 3335 or tick == 3365 or tick == 3395 then
    local total = 0
    for k, w in ipairs(d.q_walls) do total = total + (w.health - d.q_hp0[k]) end
    d.q_total = d.q_total or {}
    d.q_total[#d.q_total + 1] = math.floor(total + 0.5)
    if tick == 3395 then
      local hist = {}
      for k, w in ipairs(d.q_walls) do
        local inc = tostring(math.floor(w.health - d.q_hp0[k] + 0.5))
        hist[inc] = (hist[inc] or 0) + 1
      end
      d.q_hist = hist
      d.q_state_end = state()
    end
  end
end

---------------------------------------------------------------------------------------------------------------------
function M.check(ctx)
  local d = ctx.data
  local chk = ctx.check

  -- PILOT-10
  local full_tick
  for _, s in ipairs(d.p10_trace) do if not full_tick and s.energy >= 1e6 - 1 then full_tick = s.tick end end
  chk(G, "PILOT-10 secondary-input EEI with energy_usage 0 charges", d.p10_trace[#d.p10_trace].energy >= 1e6 - 1,
    d.p10_trace, "energy reaches 1 MJ; 200 kW -> 3333.3 J/tick -> full after ~300 ticks")
  d.p10_full_tick = full_tick

  chk(G, "R11 handler_registered after load (first benchmark tick)", d.state_first_tick.handler_registered == true,
    {first_tick = d.first_tick, state = d.state_first_tick}, {handler_registered = true})
  chk(G, "R11 queue non-empty after load", d.state_first_tick.queue >= 1, d.state_first_tick.queue, ">= 1")
  chk(G, "R11 wall damaged at tick 100 after load: healed in 600 ticks", near(d.r11_b_hp700 - d.r11_b_hp100, 100, 5),
    d.r11_b_hp700 - d.r11_b_hp100, 100, "+-5")
  chk(G, "R11 wall damaged in on_init: healed during ticks 0..700", d.r11_a_hp700 > d.r11_a_hp0,
    {hp0 = d.r11_a_hp0, hp_first = d.r11_a_hp_first, hp700 = d.r11_a_hp700}, "> hp0 (report)")

  chk(G, "R1 one cycle heals 5", near(d.r1_hp75 - d.r1_hp45, 5, 1e-3), d.r1_hp75 - d.r1_hp45, 5,
    "health is stored with float32 rounding (505 reads back as 505.0000305), tolerance 1e-3")
  chk(G, "R1 healed in 600 ticks", near(d.r1_hp645 - d.r1_hp45, 100, 5), d.r1_hp645 - d.r1_hp45, 100, "+-5")
  chk(G, "R2 total healed in 600 ticks (3 walls)", near(d.r2_hp645 - d.r2_hp45, 200, 10), d.r2_hp645 - d.r2_hp45, 200, "+-10")
  chk(G, "R3 wall at 10.51 tiles: 0 healed", d.r3_hp645[1] - d.r3_hp45[1] == 0, d.r3_hp645[1] - d.r3_hp45[1], 0)
  chk(G, "R3 control wall at 9.51 tiles: healed 100", near(d.r3_hp645[2] - d.r3_hp45[2], 100, 5), d.r3_hp645[2] - d.r3_hp45[2], 100, "+-5")
  chk(G, "R3 out-of-range wall enqueued by damage", d.r3_q1 == d.r3_q0 + 1, {q0 = d.r3_q0, q1 = d.r3_q1}, "q1 = q0 + 1")
  chk(G, "R3 out-of-range wall dequeued after one cycle, not healed", d.r3_q2 == d.r3_q0 and d.r3_hp3075 == d.r3_hp3045 - 10,
    {q0 = d.r3_q0, q2 = d.r3_q2, hp3045 = d.r3_hp3045, hp3075 = d.r3_hp3075}, "q2 = q0; hp unchanged after the damage")
  chk(G, "R4 no pole, buffer 0: 0 healed", d.r4_hp645 - d.r4_hp45 == 0 and d.r4_energy645 == 0,
    {healed = d.r4_hp645 - d.r4_hp45, energy = d.r4_energy645}, {healed = 0, energy = 0})
  local r5_healed = d.r5_hp345 - d.r5_hp45
  chk(G, "R5 preset 1 MJ, 3 walls, 300 ticks: healed", near(r5_healed, 100, 5), r5_healed, 100, "+-5")
  chk(G, "R5 coil energy after 300 ticks", near(d.r5_energy345, 5e5, 5e3), d.r5_energy345, 5e5, "+-1%")
  chk(G, "R5 joules per HP", r5_healed > 0 and near((d.r5_energy45 - d.r5_energy345) / r5_healed, 5000, 0.05),
    r5_healed > 0 and (d.r5_energy45 - d.r5_energy345) / r5_healed or nil, 5000)
  chk(G, "R6 two overlapping coils: no stacking", near(d.r6_hp645 - d.r6_hp45, 100, 5), d.r6_hp645 - d.r6_hp45, 100, "+-5")
  chk(G, "R7 enemy-force wall: 0 healed", d.r7_hp645 - d.r7_hp45 == 0, d.r7_hp645 - d.r7_hp45, 0)
  chk(G, "R8 raise_built coil counted", d.r8_after_build == d.r8_before + 1, {before = d.r8_before, after = d.r8_after_build}, "+1")
  chk(G, "R8 raise_built coil heals a wall damaged before it existed, within 60 ticks", d.r8_hp1060 > d.r8_hp1000,
    {hp1000 = d.r8_hp1000, hp1060 = d.r8_hp1060}, "hp1060 > hp1000")
  chk(G, "R8 on_entity_cloned coil counted", d.r8_after_clone == d.r8_after_build + 1, d.r8_after_clone, d.r8_after_build + 1)
  local revive_exp = ctx.config_changed and 0 or 1   -- при перестройке (R9) скрытая катушка уже найдена
  chk(G, "R8 script_raised_revive coil counted", d.r8_revive_delta == revive_exp, d.r8_revive_delta, revive_exp)
  chk(G, "R8 destroyed coils removed (on_object_destroyed), no error", d.r8_after_destroy == d.r8_before_destroy - 3,
    {before = d.r8_before_destroy, after = d.r8_after_destroy}, "-3")
  chk(G, "surface deleted: its coil removed", d.surf_delta_add == 1 and d.surf_after_delete == d.surf_before_delete,
    {added = d.surf_delta_add, before = d.surf_before_delete, after = d.surf_after_delete}, "added 1, after = before")
  chk(G, "R8 last coil gone: coils 0, handler unregistered", d.state3202.coils == 0 and d.state3202.handler_registered == false,
    d.state3202, {coils = 0, handler_registered = false})
  chk(G, "R8 no coils: damage does not reach the queue", d.r8_q_delta_after_last_coil == 0, d.r8_q_delta_after_last_coil, 0)
  chk(G, "R8 no coils: stale queue drains", d.state3260.queue == 0, d.state3260.queue, 0)
  if ctx.config_changed then
    chk(G, "R9 bump run: rebuilt coil (raise_built=false) heals", near(d.r9_hp645 - d.r9_hp45, 100, 5), d.r9_hp645 - d.r9_hp45, 100, "+-5")
  else
    chk(G, "R9 control run: coil built without raise_built unknown, 0 healed", d.r9_hp645 - d.r9_hp45 == 0, d.r9_hp645 - d.r9_hp45, 0)
  end
  chk(G, "Q coils return: handler registered again", d.q_state_coils.handler_registered == true and d.q_state_coils.coils == 90,
    d.q_state_coils, {coils = 90, handler_registered = true})
  chk(G, "Q 150 damaged walls queued", d.q_state_damaged.queue == 150, d.q_state_damaged.queue, 150)
  chk(G, "Q at most QUEUE_CAP entries per cycle: cumulative HP after 1, 2, 3 cycles",
    d.q_total[1] == 500 and d.q_total[2] == 1000 and d.q_total[3] == 1500, d.q_total, {500, 1000, 1500})
  chk(G, "Q round-robin: every wall healed exactly twice in 3 cycles (no double processing)", d.q_hist["10"] == 150,
    d.q_hist, {["10"] = 150})
  chk(G, "lines: at most 10 per cycle (>= 12 heals at tick 60)", d.lines61 == 10, d.lines61, 10)
  chk(G, "V: 6 coils x budget 10 heal 12 walls x 5 in one cycle", near(d.v_hp61, 12 * 500 + 60, 1e-2), d.v_hp61, 12 * 500 + 60)
  review_check(ctx)
end

return M
