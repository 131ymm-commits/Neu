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
    ctx.check(G, "PILOT-24 " .. name, ok, counts[name], expect[name], "handler calls per target; and binds tighter than or")
  end
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
    for _, e in ipairs(ctx.surface.find_entities_filtered{name = COIL}) do e.destroy() end
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
end

return M
