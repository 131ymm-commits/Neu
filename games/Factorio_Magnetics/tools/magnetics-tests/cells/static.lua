--[[ Статические проверки Magnetics по прототипам времени игры (prototypes.*), FINAL_SPEC §11.2:
  S4  числа §2–§5 против expected.lua (сгенерирован spec.py) и против DOC — чисел, набранных здесь вручную из
      FINAL_SPEC §2, §4, §11.2 (независимый второй путь к правде; spec.py и мод могут ошибиться одинаково);
  S5  граф технологий, достижимость (алгоритм design/spec_check.py на загруженных прототипах), research_all;
  S6  связи улучшения;  S8  Space Age (условия поверхности, подогрев, вставки категорий, T13);
  S9  замки качества и набор рецептов переработки (bq, sa);  S10 жидкости без бочек;
  S14 зеркало бонусов;  S15 потолки дальности;  S16 фиксированные рецепты;  G3 витрина (showroom.lua).
Единицы API (PILOT-5, пилот 30.09.2026 в base и sa): мощность и сток — Дж/тик (75 кВт → 1250), буфер и топливо — Дж,
research_unit_energy — тики (time × 60), resistances.percent — доля (20 % → 0.2, float32), heating_energy — Дж/тик.
Выгоняет прочитанные числа в script-output/magnetics-static-export.json (tools/tests.py сверяет их с таблицами FINAL_SPEC). ]]
local EXP = require("expected")
local showroom = require("showroom")     -- require только при разборе control.lua, не в обработчиках

local L                      -- lib стенда (ctx.L), задаётся при запуске ячейки
local SA                     -- включён ли Space Age
local CFG                    -- base / bq / bqe / be / sa
local TOP                    -- "express" без SA, "turbo" с SA (FINAL_SPEC §3.3)

---------------------------------------------------------------------------------------------------------------------
-- Единицы и сравнения

local MULT = { [""] = 1, k = 1e3, M = 1e6, G = 1e9, T = 1e12 }
local function si(s)                         -- "90kW" -> 90000, "1MJ" -> 1e6
  if s == nil then return nil end
  if type(s) == "number" then return s end
  local n, p = string.match(s, "^%s*([%d%.]+)%s*([kMGT]?)[WJ]%s*$")
  assert(n, "не разобрана величина " .. tostring(s))
  return tonumber(n) * MULT[p]
end
local function per_tick(s) return si(s) / 60 end   -- Вт -> Дж/тик (PILOT-5)

local function plain(v, depth)               -- копия без LuaObject (для записи в JSON)
  depth = depth or 0
  local t = type(v)
  if t == "table" then
    if depth > 5 then return "<…>" end
    local o = {}
    for k, x in pairs(v) do o[k] = plain(x, depth + 1) end
    return o
  elseif t == "userdata" then
    local ok, n = pcall(function() return v.name end)
    return ok and n or "<userdata>"
  end
  return v
end

local function chk(id, name, pass, got, exp, note) L.check(id, name, pass, plain(got), plain(exp), note) end
local function eq(id, name, got, exp, rel, note)
  if type(exp) == "number" then
    L.eq(id, name, got, exp, rel or 1e-6, 1e-9, note)
  else
    L.check(id, name, got == exp, plain(got), plain(exp), note)
  end
end
local function sorted(a) local o = {} for i, x in ipairs(a or {}) do o[i] = x end table.sort(o) return o end
local function keys(t, skip) local o = {} for k in pairs(t or {}) do if not (skip and skip[k]) then o[#o + 1] = k end end table.sort(o) return o end
local function join(a) return table.concat(a, ",") end
local function seteq(id, name, got, exp) local g, e = join(sorted(got)), join(sorted(exp)); chk(id, name, g == e, g, e) end
local function listeq(id, name, got, exp) local g, e = join(got), join(exp); chk(id, name, g == e, g, e) end
local function resolve(n) if n:sub(1, 4) == "TOP-" then return TOP .. n:sub(4) end return n end

-- Каждая секция — под pcall: ошибка Lua в одной не останавливает остальные (и видна как провал).
local function section(id, name, f, ...)
  local ok, err = pcall(f, ...)
  if not ok then L.check(id, name .. ": ошибка Lua", false, nil, nil, tostring(err)) end
end

local function color3(c)                     -- Color API {r,g,b,a} или массив -> {r,g,b}
  if not c then return nil end
  return { c.r or c[1], c.g or c[2], c.b or c[3] }
end
local function color_eq(id, name, got, exp)
  local g = color3(got)
  local pass = g ~= nil
  for i = 1, 3 do pass = pass and math.abs(g[i] - exp[i]) <= 1e-6 end
  chk(id, name, pass, g, exp)
end
local function bbox(b)                       -- BoundingBox -> {x1,y1,x2,y2}
  local lt, rb = b.left_top or b[1], b.right_bottom or b[2]
  return { lt.x or lt[1], lt.y or lt[2], rb.x or rb[1], rb.y or rb[2] }
end
-- Движок хранит координаты рамок с шагом 1/256 (пилот: -0.4 читается как -0.3984375), поэтому допуск 1/256.
local function bbox_eq(a, b)
  for i = 1, 4 do if math.abs(a[i] - b[i]) > 1 / 256 + 1e-9 then return false end end
  return true
end
local function flat_box(b) return { b[1][1], b[1][2], b[2][1], b[2][2] } end
-- usage_priority аккумулятора: в данных "tertiary", в API читается "managed-accumulator" (пилот: у ванильного аккумулятора
-- так же). Ожидание для API берём с ванильного аккумулятора; буквальное "tertiary" в данных проверяет tests.py по выгрузке.
local function api_priority(ptype, data_priority)
  if ptype == "accumulator" and data_priority == "tertiary" then
    return prototypes.entity["accumulator"].electric_energy_source_prototype.usage_priority
  end
  return data_priority
end
-- Действие attack_reaction в API — массив TriggerItem (в описании API — одиночный); берём первый.
local function first_damage(trigger)
  if not trigger then return nil end
  if trigger[1] then trigger = trigger[1] end
  local dl = trigger.action_delivery and trigger.action_delivery[1]
  local te = dl and dl.target_effects and dl.target_effects[1]
  return te and te.damage
end

-- Загрязнение в минуту из emissions_per_joule (PILOT-5, калибровка S4 cal: каменная печь 2, AM2 3,
-- ванильный burner-generator 10 в минуту): потребители — от energy_usage, генераторы на топливе — от max_power_output.
local function pollution_per_min(epj, joules_per_tick) return (epj and epj.pollution or 0) * joules_per_tick * 3600 end

---------------------------------------------------------------------------------------------------------------------
-- DOC: числа, набранные вручную из FINAL_SPEC (§2.1, §2.3, §4.2–§4.7, §11.2 S4, §5.3). Не из spec.py.

local DOC = {}
-- постройки: тип, основа, клетки, HP, группа быстрой замены, ключевые числа
DOC.entities = {
  ["magnetics-sintering-kiln"] = { type = "assembling-machine", w = 2, h = 2, hp = 200, frg = "magnetics-sintering-kiln",
    speed = 1, kw = 90, burner = { "chemical", 1, 1, 0 }, pollution = 2, fixed = "magnetics-ferrite", cats = { "magnetics-sintering" }, modules = 0,
    er = { false, false, true } },
  ["magnetics-induction-furnace"] = { type = "assembling-machine", w = 3, h = 3, hp = 350, frg = "magnetics-induction-furnace",
    speed = 2, kw = 240, drain_kw = 8, pollution = 1, cats = { "magnetics-sintering", "magnetics-induction" }, modules = 2 },
  ["magnetics-coil-winder"] = { type = "assembling-machine", w = 3, h = 3, hp = 350, frg = "magnetics-coil-winder",
    speed = 1, kw = 150, drain_kw = 5, pollution = 3, cats = { "magnetics-winding" }, modules = 2 },
  ["magnetics-cryo-chamber"] = { type = "assembling-machine", w = 3, h = 3, hp = 350, frg = "magnetics-cryo-chamber",
    speed = 1, kw = 300, drain_kw = 10, pollution = 3, cats = { "magnetics-cryogenics" }, modules = 3 },
  ["magnetics-flux-resonator"] = { type = "assembling-machine", w = 3, h = 3, hp = 350, frg = "magnetics-flux-resonator",
    speed = 1, kw = 5000, drain_kw = 10, pollution = 0, cats = { "magnetics-resonance" }, modules = 0,
    fixed = "magnetics-flux-crystal-charging", er = { false, false, false } },
  ["magnetics-magnetic-separator"] = { type = "assembling-machine", w = 3, h = 3, hp = 400, frg = "magnetics-magnetic-separator",
    speed = 1, kw = 250, drain_kw = 8.33, pollution = 4, cats = { "magnetics-separation" }, modules = 2 },
  ["magnetics-magnetic-drill"] = { type = "mining-drill", w = 3, h = 3, hp = 400, frg = "mining-drill",
    mining_speed = 0.75, kw = 150, pollution = 15, radius = 2.49, res_cats = { "basic-solid" }, modules = 3 },
  ["magnetics-maglev-transport-belt"] = { type = "transport-belt", w = 1, h = 1, hp = 180, frg = "transport-belt", belt_speed = 0.15625 },
  ["magnetics-maglev-underground-belt"] = { type = "underground-belt", w = 1, h = 1, hp = 180, frg = "transport-belt",
    belt_speed = 0.15625, ug = 13 },
  ["magnetics-maglev-splitter"] = { type = "splitter", w = 2, h = 1, hp = 200, belt_speed = 0.15625 },
  ["magnetics-coil-capacitor"] = { type = "accumulator", w = 1, h = 1, hp = 100, frg = "magnetics-coil-capacitor",
    buffer_mj = 1, flow_mw = 1, priority = "tertiary", cbox = { -0.4, -0.4, 0.4, 0.4 }, sbox = { -0.5, -0.5, 0.5, 0.5 } },
  ["magnetics-superconducting-accumulator"] = { type = "accumulator", w = 2, h = 2, hp = 250, frg = "accumulator",
    buffer_mj = 20, flow_mw = 1.2, priority = "tertiary" },
  ["magnetics-superconducting-pylon"] = { type = "electric-pole", w = 2, h = 2, hp = 250, frg = "big-electric-pole", wire = 48, supply = 2 },
  ["magnetics-mhd-generator"] = { type = "burner-generator", w = 3, h = 5, hp = 400, frg = "magnetics-mhd-generator",
    power_mw = 5.4, burner = { "chemical", 0.9, 2, 0 }, gen_pollution = 100, priority = "secondary-output" },
  ["magnetics-flux-dynamo"] = { type = "burner-generator", w = 3, h = 5, hp = 500, frg = "magnetics-flux-dynamo",
    power_mw = 10, burner = { "magnetics-flux", 1, 1, 1 }, gen_pollution = 0, priority = "secondary-output" },
  ["magnetics-geomagnetic-coil"] = { type = "solar-panel", w = 3, h = 3, hp = 200, frg = "magnetics-geomagnetic-coil",
    solar_kw = 20, solar_property = "magnetic-field", day = 1, night = 1 },
  ["magnetics-ferrite-wall"] = { type = "wall", w = 1, h = 1, hp = 500, frg = "wall", res = "ferrite" },
  ["magnetics-magnet-wall"] = { type = "wall", w = 1, h = 1, hp = 800, frg = "wall", res = "magnet", thorns = 5 },
  ["magnetics-superconducting-wall"] = { type = "wall", w = 1, h = 1, hp = 1500, frg = "wall", res = "sc", thorns = 10 },
  ["magnetics-magnet-gate"] = { type = "gate", w = 1, h = 1, hp = 800, frg = "wall", res = "magnet", thorns = 5 },
  ["magnetics-superconducting-gate"] = { type = "gate", w = 1, h = 1, hp = 1500, frg = "wall", res = "sc", thorns = 10 },
  ["magnetics-mend-coil"] = { type = "electric-energy-interface", w = 2, h = 2, hp = 300, frg = "magnetics-mend-coil",
    buffer_mj = 1, in_kw = 200, out_kw = 0, priority = "secondary-input" },
  ["magnetics-coilgun-turret"] = { type = "ammo-turret", w = 2, h = 2, hp = 500, frg = "magnetics-coilgun-turret",
    ammo = "magnetics-slug", cooldown = 24, range = 20, buffer_kj = 200, in_kw = 250, priority = "primary-input", inv = 1, aac = 10 },
  ["magnetics-gauss-turret"] = { type = "ammo-turret", w = 2, h = 2, hp = 800, frg = "magnetics-gauss-turret",
    ammo = "magnetics-gauss", cooldown = 60, range = 30, buffer_kj = 1000, in_kw = 1000, priority = "primary-input", aac = 8 },
  ["magnetics-arc-emitter"] = { type = "electric-turret", w = 2, h = 2, hp = 1000, frg = "magnetics-arc-emitter",
    ammo = "laser", cooldown = 120, range = 20,  -- §15: 60 → 120 (PILOT-15)
    buffer_kj = 2000, in_kw = 3000, drain_kw = 24, priority = "primary-input",
    shot_mj = 1, damage = 45 },
  ["magnetics-rail-cannon"] = { type = "ammo-turret", w = 2, h = 2, hp = 2000, frg = "magnetics-rail-cannon",
    ammo = "magnetics-rail", cooldown = 150, range = 36, min_range = 4, health_penalty = -1, buffer_kj = 8000, in_kw = 2000,
    priority = "primary-input", aac = 5 },
}
-- сопротивления §4.5: {decrease, percent}
DOC.res = {
  ferrite = { physical = { 3, 25 }, impact = { 45, 60 }, explosion = { 10, 30 }, fire = { 0, 100 }, acid = { 0, 80 }, laser = { 0, 70 }, electric = { 0, 30 } },
  magnet = { physical = { 5, 30 }, impact = { 50, 65 }, explosion = { 15, 35 }, fire = { 0, 100 }, acid = { 0, 85 }, laser = { 0, 75 }, electric = { 0, 50 } },
  sc = { physical = { 8, 35 }, impact = { 60, 70 }, explosion = { 20, 40 }, fire = { 0, 100 }, acid = { 0, 90 }, laser = { 0, 100 }, electric = { 0, 100 } },
}
-- стаки: §2.1 и §2.3
DOC.stacks = {
  ["magnetics-ferrite"] = 100, ["magnetics-coil"] = 200, ["magnetics-magnet-alloy"] = 100, ["magnetics-superconducting-cable"] = 200,
  ["magnetics-flux-crystal-uncharged"] = 20, ["magnetics-flux-crystal"] = 20, ["magnetics-ferrite-slug"] = 100,
  ["magnetics-magnet-slug"] = 100, ["magnetics-gauss-slug"] = 50, ["magnetics-rail-slug"] = 20, ["magnetics-flux-rail-slug"] = 10,
  ["magnetics-sintering-kiln"] = 50, ["magnetics-induction-furnace"] = 50, ["magnetics-coil-winder"] = 50, ["magnetics-cryo-chamber"] = 10,
  ["magnetics-flux-resonator"] = 20, ["magnetics-magnetic-separator"] = 50, ["magnetics-magnetic-drill"] = 50,
  ["magnetics-maglev-transport-belt"] = 100, ["magnetics-maglev-underground-belt"] = 50, ["magnetics-maglev-splitter"] = 50,
  ["magnetics-coil-capacitor"] = 50, ["magnetics-superconducting-accumulator"] = 50, ["magnetics-superconducting-pylon"] = 50,
  ["magnetics-mhd-generator"] = 10, ["magnetics-flux-dynamo"] = 10, ["magnetics-geomagnetic-coil"] = 50,
  ["magnetics-ferrite-wall"] = 100, ["magnetics-magnet-wall"] = 100, ["magnetics-superconducting-wall"] = 100,
  ["magnetics-magnet-gate"] = 50, ["magnetics-superconducting-gate"] = 50, ["magnetics-mend-coil"] = 20,
  ["magnetics-coilgun-turret"] = 50, ["magnetics-gauss-turret"] = 50, ["magnetics-arc-emitter"] = 50, ["magnetics-rail-cannon"] = 10,
}
-- боеприпасы §2.1, §4.7: категория, магазин, урон/пробитие/скорость/дальность снаряда или линия
DOC.ammo = {
  ["magnetics-ferrite-slug"] = { cat = "magnetics-slug", mag = 10, speed = 1, max_range = 24 },
  ["magnetics-magnet-slug"] = { cat = "magnetics-slug", mag = 10, speed = 1, max_range = 24 },
  ["magnetics-gauss-slug"] = { cat = "magnetics-gauss", mag = 4, speed = 1.5, max_range = 34 },
  ["magnetics-rail-slug"] = { cat = "magnetics-rail", mag = 1, line = { range = 34.60625,  -- §15: 36 от центра (PILOT-8)
    width = 1.5, dmg = { { 1200, "physical" } } } },
  ["magnetics-flux-rail-slug"] = { cat = "magnetics-rail", mag = 3, line = { range = 34.60625, width = 2, dmg = { { 1800, "physical" }, { 600, "electric" } } } },
}
DOC.chain = { max_jumps = 4, max_range_per_jump = 6, jump_delay_ticks = 3, fork_chance = 0, max_forks = 2 }
-- §7.4 подогрев (кВт; нет в списке — 0)
DOC.heat = {
  ["magnetics-induction-furnace"] = 100, ["magnetics-coil-winder"] = 100, ["magnetics-cryo-chamber"] = 100,
  ["magnetics-flux-resonator"] = 100, ["magnetics-magnetic-separator"] = 100, ["magnetics-magnetic-drill"] = 100,
  ["magnetics-maglev-transport-belt"] = 10, ["magnetics-maglev-underground-belt"] = 250, ["magnetics-maglev-splitter"] = 40,
  ["magnetics-mhd-generator"] = 50, ["magnetics-flux-dynamo"] = 50, ["magnetics-coilgun-turret"] = 50,
  ["magnetics-gauss-turret"] = 50, ["magnetics-rail-cannon"] = 50, ["magnetics-arc-emitter"] = 50,
}
-- §7.3: к magnetic-field ≥ 10 у всех 26 — ещё pressure ≥ 10 у печи и МГД
DOC.pressure = { ["magnetics-sintering-kiln"] = true, ["magnetics-mhd-generator"] = true }
-- §5.1: технологии (предпосылки, число × время, пакеты, открываемые рецепты) — для S5 и S8
local A, Lg, C, Mi, P, U = "automation-science-pack", "logistic-science-pack", "chemical-science-pack", "military-science-pack",
  "production-science-pack", "utility-science-pack"
local function m(x) return "magnetics-" .. x end
DOC.techs = {
  [m "ferrite-sintering"] = { pre = { A, "stone-wall" }, n = 30, t = 10, packs = { A }, un = { m "sintering-kiln", m "ferrite", m "ferrite-wall" } },
  [m "electromagnetic-coils"] = { pre = { m "ferrite-sintering", "automation-2" }, n = 75, t = 15, packs = { A, Lg }, un = { m "coil-winder", m "coil" } },
  [m "coilgun"] = { pre = { m "electromagnetic-coils", "gun-turret", "military-2" }, n = 100, t = 15, packs = { A, Lg }, un = { m "coilgun-turret", m "ferrite-slug" } },
  [m "induction-smelting"] = { pre = { m "electromagnetic-coils", "advanced-material-processing-2" }, n = 250, t = 30, packs = { A, Lg, C }, un = { m "induction-furnace", m "magnet-alloy" } },
  [m "magnetic-mining"] = { pre = { m "induction-smelting", "electric-mining-drill" }, n = 250, t = 30, packs = { A, Lg, C }, un = { m "magnetic-drill" } },
  [m "magnetic-power"] = { pre = { m "induction-smelting", "solar-energy", "electric-energy-accumulators" }, n = 250, t = 30, packs = { A, Lg, C }, un = { m "mhd-generator", m "coil-capacitor", m "geomagnetic-coil" } },
  [m "magnetic-separation"] = { pre = { m "induction-smelting", "advanced-oil-processing" }, n = 150, t = 30, packs = { A, Lg, C }, un = { m "ferrofluid", m "magnetic-separator", m "stone-separation" } },
  [m "magnetic-fortifications"] = { pre = { m "coilgun", m "induction-smelting", "military-3", "gate", "repair-pack" }, n = 250, t = 30, packs = { A, Lg, C, Mi },
    un = { m "magnet-wall", m "magnet-gate", m "magnet-slug", m "gauss-turret", m "gauss-slug", m "mend-coil" } },
  [m "arc-emitter"] = { pre = { m "induction-smelting", "laser-turret" }, n = 200, t = 30, packs = { A, Lg, C, Mi }, un = { m "arc-emitter" } },
  [m "superconductivity"] = { pre = { m "induction-smelting", "production-science-pack" }, n = 300, t = 30, packs = { A, Lg, C, P }, un = { m "cryo-chamber", m "liquid-nitrogen", m "superconducting-cable" } },
  [m "superconducting-power"] = { pre = { m "superconductivity", "electric-energy-distribution-2", "electric-energy-accumulators" }, n = 300, t = 30, packs = { A, Lg, C, P }, un = { m "superconducting-accumulator", m "superconducting-pylon" } },
  [m "flux-energy"] = { pre = { m "superconducting-power", m "magnetic-separation", "utility-science-pack", "uranium-processing" }, n = 500, t = 30, packs = { A, Lg, C, P, U },
    un = { m "flux-resonator", m "flux-dynamo", m "flux-crystal-growth", m "flux-crystal-charging" } },
  [m "maglev-logistics"] = { pre = { "logistics-3", m "superconductivity", m "magnetic-separation", "utility-science-pack" }, n = 600, t = 30, packs = { A, Lg, C, P, U },
    un = { m "maglev-transport-belt", m "maglev-underground-belt", m "maglev-splitter" },
    sa = { pre_add = { "turbo-transport-belt", "electromagnetic-science-pack" }, n = 1000, t = 60,
           packs = { A, Lg, C, P, U, "space-science-pack", "metallurgic-science-pack", "electromagnetic-science-pack" } } },
  [m "superconducting-defense"] = { pre = { m "magnetic-fortifications", m "flux-energy", "military-4", "concrete" }, n = 500, t = 45, packs = { A, Lg, C, Mi, P, U },
    un = { m "superconducting-wall", m "superconducting-gate", m "rail-cannon", m "rail-slug", m "flux-rail-slug" } },
}
-- §5.3 / S14: бонусы, которые переносятся (по уровням)
DOC.ppd_bullet = { 0.1, 0.1, 0.2, 0.2, 0.2, 0.4, 0.4 }
DOC.ppd_turret = { 0.1, 0.1, 0.2, 0.2, 0.2, 0.4, 0.7 }
DOC.ppd_sa_67 = 0.2                         -- под SA уровни 6 и 7: 0.2 и для пуль, и для турели [W §14.3]
DOC.wss = { 0.1, 0.2, 0.2, 0.3, 0.3, 0.4 }
DOC.cats = { "magnetics-slug", "magnetics-gauss", "magnetics-rail" }
DOC.turrets = { "magnetics-coilgun-turret", "magnetics-gauss-turret", "magnetics-rail-cannon" }
-- §7.2 / S6: связи улучшения
DOC.links_internal = {
  { "magnetics-ferrite-wall", "magnetics-magnet-wall" }, { "magnetics-magnet-wall", "magnetics-superconducting-wall" },
  { "magnetics-magnet-gate", "magnetics-superconducting-gate" },
}
local function vanilla_links()
  local top = SA and "turbo" or "express"
  return {
    { "stone-wall", "magnetics-ferrite-wall" }, { "gate", "magnetics-magnet-gate" },
    { "electric-mining-drill", "magnetics-magnetic-drill" }, { "accumulator", "magnetics-superconducting-accumulator" },
    { "big-electric-pole", "magnetics-superconducting-pylon" },
    { top .. "-transport-belt", "magnetics-maglev-transport-belt" }, { top .. "-underground-belt", "magnetics-maglev-underground-belt" },
    { top .. "-splitter", "magnetics-maglev-splitter" },
  }
end
DOC.chain_ends = { "magnetics-superconducting-wall", "magnetics-superconducting-gate", "magnetics-magnetic-drill",
  "magnetics-superconducting-accumulator", "magnetics-superconducting-pylon", "magnetics-maglev-transport-belt",
  "magnetics-maglev-underground-belt", "magnetics-maglev-splitter" }
-- §7.5 / S9: рецепты с auto_recycle = false и предметы с auto_recycle = false
DOC.no_recycle_recipes = { m "ferrite", m "magnet-alloy", m "ferrofluid", m "liquid-nitrogen", m "superconducting-cable",
  m "stone-separation", m "flux-crystal-growth", m "flux-crystal-charging", m "flux-rail-slug" }
DOC.no_recycle_items = { m "superconducting-cable", m "flux-crystal-uncharged", m "flux-crystal" }

---------------------------------------------------------------------------------------------------------------------
-- Выгрузка прочитанного (для tools/tests.py: сверка с таблицами FINAL_SPEC.md)

local EXPORT = { recipes = {}, techs = {}, items = {}, entities = {} }

---------------------------------------------------------------------------------------------------------------------
-- S4 калибровка метрик (ванильные числа из FINAL_SPEC и recon: AM1 75 кВт, AM2 150 кВт/5 кВт/3 в мин,
-- каменная печь 90 кВт/2 в мин, burner-generator 1 МВт/10 в мин [D:base/prototypes/entity/entities.lua:9956-9973])

local function s4_calibration()
  local E = prototypes.entity
  eq("S4", "cal AM1 energy_usage = 75 kW (J/tick)", E["assembling-machine-1"].energy_usage, 75e3 / 60)
  eq("S4", "cal AM2 drain = 5 kW (J/tick)", E["assembling-machine-2"].electric_energy_source_prototype.drain, 5e3 / 60)
  eq("S4", "cal AM2 pollution 3/min",
    pollution_per_min(E["assembling-machine-2"].electric_energy_source_prototype.emissions_per_joule, E["assembling-machine-2"].energy_usage), 3)
  eq("S4", "cal stone-furnace pollution 2/min",
    pollution_per_min(E["stone-furnace"].burner_prototype.emissions_per_joule, E["stone-furnace"].energy_usage), 2)
  eq("S4", "cal burner-generator pollution 10/min (per max_power_output)",
    pollution_per_min(E["burner-generator"].burner_prototype.emissions_per_joule, E["burner-generator"].get_max_power_output()), 10)
  eq("S4", "cal stone-wall physical percent 20 % -> 0.2", E["stone-wall"].resistances.physical.percent, 0.2, 1e-6)
  eq("S4", "cal automation research_unit_energy = 10 s x 60", prototypes.technology["automation"].research_unit_energy, 600)
  eq("S4", "cal accumulator: data tertiary reads managed-accumulator", E["accumulator"].electric_energy_source_prototype.usage_priority, "managed-accumulator")
end

---------------------------------------------------------------------------------------------------------------------
-- S4 постройки против expected.lua (EXP.entities)

local function s4_energy_source(name, p, es_exp, eu)
  local id = "S4"
  if es_exp.type == "burner" then
    local b = p.burner_prototype
    chk(id, name .. " burner present", b ~= nil, b ~= nil, true)
    if not b then return end
    seteq(id, name .. " burner fuel_categories", keys(b.fuel_categories), es_exp.fuel_categories or { "chemical" })
    eq(id, name .. " burner effectivity", b.effectivity, es_exp.effectivity or 1)
    eq(id, name .. " burner fuel_inventory_size", b.fuel_inventory_size, es_exp.fuel_inventory_size or 0)
    eq(id, name .. " burner burnt_inventory_size", b.burnt_inventory_size, es_exp.burnt_inventory_size or 0)
    if es_exp.emissions_per_minute then
      eq(id, name .. " burner pollution/min", pollution_per_min(b.emissions_per_joule, eu), es_exp.emissions_per_minute.pollution, 1e-4)
    end
    return
  end
  local es = p.electric_energy_source_prototype
  chk(id, name .. " electric energy source present", es ~= nil, es ~= nil, true)
  if not es then return end
  if es_exp.usage_priority then eq(id, name .. " usage_priority (API)", es.usage_priority, api_priority(p.type, es_exp.usage_priority)) end
  if es_exp.drain then eq(id, name .. " drain (J/tick)", es.drain, per_tick(es_exp.drain), 1e-6) end
  if es_exp.buffer_capacity then eq(id, name .. " buffer_capacity (J)", es.buffer_capacity, si(es_exp.buffer_capacity)) end
  if es_exp.input_flow_limit then eq(id, name .. " input_flow_limit (J/tick)", es.get_input_flow_limit(), per_tick(es_exp.input_flow_limit)) end
  if es_exp.output_flow_limit then eq(id, name .. " output_flow_limit (J/tick)", es.get_output_flow_limit(), per_tick(es_exp.output_flow_limit)) end
  if es_exp.emissions_per_minute and eu then
    eq(id, name .. " pollution/min", pollution_per_min(es.emissions_per_joule, eu), es_exp.emissions_per_minute.pollution, 1e-4)
  end
end

local function s4_entity(name, d)
  local id = "S4"
  local p = prototypes.entity[name]
  chk(id, name .. " exists", p ~= nil, p ~= nil, true)
  if not p then return end
  local ex = { type = p.type, hp = p.get_max_health(), frg = p.fast_replaceable_group, w = p.tile_width, h = p.tile_height }
  EXPORT.entities[name] = ex
  eq(id, name .. " type", p.type, d.type)
  eq(id, name .. " max_health", p.get_max_health(), d.hp)
  eq(id, name .. " fast_replaceable_group", p.fast_replaceable_group, d.frg)
  local s = d.set or {}
  if s.crafting_speed then eq(id, name .. " crafting_speed", p.get_crafting_speed(), s.crafting_speed) end
  if s.energy_usage and d.type ~= "electric-energy-interface" then
    eq(id, name .. " energy_usage (J/tick)", p.energy_usage, per_tick(s.energy_usage))
    ex.energy_usage_w = p.energy_usage * 60
  end
  if s.crafting_categories then seteq(id, name .. " crafting_categories (без parameters)", keys(p.crafting_categories, { parameters = true }), s.crafting_categories) end
  if s.fixed_recipe then eq(id, name .. " fixed_recipe", p.fixed_recipe, s.fixed_recipe) end
  if s.module_slots then eq(id, name .. " module slots", p.module_inventory_size or 0, s.module_slots) end
  if s.allowed_effects then
    local on = {}
    for k, v in pairs(p.allowed_effects or {}) do if v then on[#on + 1] = k end end
    seteq(id, name .. " allowed_effects", on, s.allowed_effects)
  end
  if s.effect_receiver then
    local er = p.effect_receiver or {}
    for _, k in ipairs({ "uses_module_effects", "uses_beacon_effects", "uses_surface_effects" }) do
      eq(id, name .. " effect_receiver." .. k, er[k], s.effect_receiver[k])
    end
  end
  if s.energy_source then
    local eu = p.energy_usage
    if d.type == "burner-generator" then eu = p.get_max_power_output() end
    s4_energy_source(name, p, s.energy_source, eu)
  end
  if s.burner then s4_energy_source(name, p, s.burner, p.get_max_power_output()) end
  if s.mining_speed then eq(id, name .. " mining_speed", p.mining_speed, s.mining_speed) end
  if s.resource_searching_radius then eq(id, name .. " mining radius", p.get_mining_drill_radius(), s.resource_searching_radius) end
  if s.resource_categories then seteq(id, name .. " resource_categories", keys(p.resource_categories), s.resource_categories) end
  if s.speed then eq(id, name .. " belt_speed", p.belt_speed, s.speed) end
  if s.max_distance then eq(id, name .. " max_underground_distance", p.max_underground_distance, s.max_distance) end
  if s.maximum_wire_distance then eq(id, name .. " wire distance", p.get_max_wire_distance(), s.maximum_wire_distance) end
  if s.supply_area_distance then eq(id, name .. " supply area distance", p.get_supply_area_distance(), s.supply_area_distance) end
  if s.max_power_output then eq(id, name .. " max_power_output (J/tick)", p.get_max_power_output(), per_tick(s.max_power_output)) end
  if s.production then eq(id, name .. " solar production (J/tick)", p.get_max_energy_production(), per_tick(s.production)) end
  if s.solar_coefficient_property then
    eq(id, name .. " solar_coefficient_property", p.solar_panel_solar_coefficient_property and p.solar_panel_solar_coefficient_property.name, s.solar_coefficient_property)
  end
  if s.performance_at_day then eq(id, name .. " performance_at_day", p.solar_panel_performance_at_day, s.performance_at_day) end
  if s.performance_at_night then eq(id, name .. " performance_at_night", p.solar_panel_performance_at_night, s.performance_at_night) end
  if s.resistances then
    local want = {}
    for _, r in ipairs(s.resistances) do
      want[#want + 1] = r.type
      local g = (p.resistances or {})[r.type] or {}
      eq(id, name .. " resistance " .. r.type .. " decrease", g.decrease, r.decrease)
      eq(id, name .. " resistance " .. r.type .. " percent", g.percent, r.percent / 100, 1e-6)
    end
    seteq(id, name .. " resistance types", keys(p.resistances), want)
  end
  if s.collision_box then chk(id, name .. " collision_box (±1/256)", bbox_eq(bbox(p.collision_box), flat_box(s.collision_box)), bbox(p.collision_box), flat_box(s.collision_box)) end
  if s.selection_box then chk(id, name .. " selection_box (±1/256)", bbox_eq(bbox(p.selection_box), flat_box(s.selection_box)), bbox(p.selection_box), flat_box(s.selection_box)) end
  if s.allow_copy_paste ~= nil then eq(id, name .. " allow_copy_paste", p.allow_copy_paste, s.allow_copy_paste) end
  if s.energy_production then eq(id, name .. " energy_production (J/tick)", p.get_max_energy_production(), per_tick(s.energy_production)) end
  if d.type == "electric-energy-interface" and s.energy_usage then eq(id, name .. " energy_usage (J/tick)", p.energy_usage or 0, per_tick(s.energy_usage)) end
  if s.inventory_size then eq(id, name .. " ammo inventory size", p.get_inventory_size(defines.inventory.turret_ammo), s.inventory_size) end
  if s.automated_ammo_count then eq(id, name .. " automated_ammo_count", p.automated_ammo_count, s.automated_ammo_count) end
  if d.attack then
    local a = p.attack_parameters or {}
    listeq(id, name .. " ammo_categories", a.ammo_categories or {}, { d.attack.ammo_category })
    eq(id, name .. " cooldown", a.cooldown, d.attack.cooldown)
    eq(id, name .. " attack range", a.range, d.attack.range)
    eq(id, name .. " turret_range", p.turret_range, d.attack.range)
    eq(id, name .. " min_range", a.min_range, d.attack.min_range or 0)
    if d.attack.health_penalty then eq(id, name .. " health_penalty", a.health_penalty, d.attack.health_penalty) end
    ex.range = a.range; ex.cooldown = a.cooldown
    if d.attack.energy then
      eq(id, name .. " energy per shot (J)", a.ammo_type and a.ammo_type.energy_consumption, si(d.attack.energy))
    end
  end
  if d.thorns then
    local ar = p.attack_reaction or {}
    chk(id, name .. " attack_reaction count", #ar == 1, #ar, 1)
    local r1 = ar[1] or {}
    eq(id, name .. " attack_reaction range", r1.range, 3)   -- §15: 2 → 3 (большие жуки кусают с 2,07–2,16)
    eq(id, name .. " attack_reaction reaction_modifier", r1.reaction_modifier, 0)
    eq(id, name .. " attack_reaction damage_type", r1.damage_type and r1.damage_type.name, "physical")
    local dmg = first_damage(r1.action)
    eq(id, name .. " thorns damage", dmg and dmg.amount, d.thorns)
    eq(id, name .. " thorns damage type", dmg and dmg.type, "electric")
  elseif d.type == "wall" or d.type == "gate" then
    local ar = p.attack_reaction or {}
    chk(id, name .. " no attack_reaction", #ar == 0, #ar, 0)
  end
  -- предмет постройки
  local it = prototypes.item[name]
  chk(id, name .. " item exists", it ~= nil, it ~= nil, true)
  if it then
    eq(id, name .. " item stack_size", it.stack_size, d.item.stack)
    eq(id, name .. " item subgroup", it.subgroup and it.subgroup.name, d.item.subgroup)
    eq(id, name .. " item order", it.order, d.item.order)
    eq(id, name .. " item place_result", it.place_result and it.place_result.name, name)
    ex.stack = it.stack_size
  end
end

-- S4 постройки против DOC (набрано из FINAL_SPEC)
local function s4_doc_entity(name, d)
  local id = "S4"
  local n = "doc " .. name
  local p = prototypes.entity[name]
  if not p then chk(id, n .. " exists", false, nil, true); return end
  eq(id, n .. " type", p.type, d.type)
  eq(id, n .. " size", p.tile_width .. "x" .. p.tile_height, d.w .. "x" .. d.h)
  eq(id, n .. " max_health", p.get_max_health(), d.hp)
  if d.frg then eq(id, n .. " fast_replaceable_group", p.fast_replaceable_group, d.frg) end
  if d.speed then eq(id, n .. " crafting speed", p.get_crafting_speed(), d.speed) end
  if d.kw then eq(id, n .. " energy_usage kW", p.energy_usage * 60 / 1e3, d.kw, 1e-6) end
  local es = p.electric_energy_source_prototype
  if d.drain_kw then eq(id, n .. " drain kW", es and es.drain * 60 / 1e3, d.drain_kw, 0.005) end
  if d.pollution and es and d.kw then eq(id, n .. " pollution/min", pollution_per_min(es.emissions_per_joule, p.energy_usage), d.pollution, 1e-4) end
  if d.burner then
    local b = p.burner_prototype
    chk(id, n .. " burner", b ~= nil, b ~= nil, true)
    if b then
      seteq(id, n .. " burner fuel", keys(b.fuel_categories), { d.burner[1] })
      eq(id, n .. " burner effectivity", b.effectivity, d.burner[2])
      eq(id, n .. " burner fuel slots", b.fuel_inventory_size, d.burner[3])
      eq(id, n .. " burner burnt slots", b.burnt_inventory_size, d.burner[4])
      if d.pollution then eq(id, n .. " burner pollution/min", pollution_per_min(b.emissions_per_joule, p.energy_usage), d.pollution, 1e-4) end
      if d.gen_pollution then eq(id, n .. " generator pollution/min (per max output)", pollution_per_min(b.emissions_per_joule, p.get_max_power_output()), d.gen_pollution, 1e-4) end
    end
  end
  if d.fixed then eq(id, n .. " fixed_recipe", p.fixed_recipe, d.fixed) end
  if d.cats then seteq(id, n .. " crafting categories", keys(p.crafting_categories, { parameters = true }), d.cats) end
  if d.modules then eq(id, n .. " module slots", p.module_inventory_size or 0, d.modules) end
  if d.er then
    local er = p.effect_receiver or {}
    eq(id, n .. " effect_receiver modules/beacons/surface", join({ tostring(er.uses_module_effects), tostring(er.uses_beacon_effects), tostring(er.uses_surface_effects) }),
      join({ tostring(d.er[1]), tostring(d.er[2]), tostring(d.er[3]) }))
  end
  if d.mining_speed then eq(id, n .. " mining_speed", p.mining_speed, d.mining_speed) end
  if d.radius then eq(id, n .. " mining radius", p.get_mining_drill_radius(), d.radius) end
  if d.res_cats then seteq(id, n .. " resource categories", keys(p.resource_categories), d.res_cats) end
  if d.belt_speed then
    eq(id, n .. " belt_speed", p.belt_speed, d.belt_speed)
    eq(id, n .. " items/s (speed x 480)", p.belt_speed * 480, 75)
  end
  if d.ug then eq(id, n .. " underground distance", p.max_underground_distance, d.ug) end
  if d.buffer_mj then eq(id, n .. " buffer MJ", es and es.buffer_capacity / 1e6, d.buffer_mj) end
  if d.flow_mw then
    eq(id, n .. " input MW", es and es.get_input_flow_limit() * 60 / 1e6, d.flow_mw)
    eq(id, n .. " output MW", es and es.get_output_flow_limit() * 60 / 1e6, d.flow_mw)
  end
  if d.in_kw then eq(id, n .. " input kW", es and es.get_input_flow_limit() * 60 / 1e3, d.in_kw) end
  if d.out_kw then eq(id, n .. " output kW", es and es.get_output_flow_limit() * 60 / 1e3, d.out_kw) end
  if d.buffer_kj then eq(id, n .. " buffer kJ", es and es.buffer_capacity / 1e3, d.buffer_kj) end
  if d.priority then eq(id, n .. " usage_priority (API)", es and es.usage_priority, api_priority(p.type, d.priority)) end
  if d.cbox then chk(id, n .. " collision_box (±1/256)", bbox_eq(bbox(p.collision_box), d.cbox), bbox(p.collision_box), d.cbox) end
  if d.sbox then chk(id, n .. " selection_box (±1/256)", bbox_eq(bbox(p.selection_box), d.sbox), bbox(p.selection_box), d.sbox) end
  if d.wire then eq(id, n .. " wire reach", p.get_max_wire_distance(), d.wire) end
  if d.supply then eq(id, n .. " supply distance", p.get_supply_area_distance(), d.supply) end
  if d.power_mw then eq(id, n .. " max power MW", p.get_max_power_output() * 60 / 1e6, d.power_mw) end
  if d.solar_kw then eq(id, n .. " production kW", p.get_max_energy_production() * 60 / 1e3, d.solar_kw) end
  if d.solar_property then eq(id, n .. " coefficient property", p.solar_panel_solar_coefficient_property and p.solar_panel_solar_coefficient_property.name, d.solar_property) end
  if d.day then eq(id, n .. " performance day", p.solar_panel_performance_at_day, d.day) end
  if d.night then eq(id, n .. " performance night", p.solar_panel_performance_at_night, d.night) end
  if d.res then
    local want = {}
    for t, dp in pairs(DOC.res[d.res]) do
      want[#want + 1] = t
      local g = (p.resistances or {})[t] or {}
      eq(id, n .. " " .. t .. " decrease", g.decrease, dp[1])
      eq(id, n .. " " .. t .. " percent", g.percent, dp[2] / 100, 1e-6)
    end
    seteq(id, n .. " resistance types", keys(p.resistances), want)
  end
  if d.ammo then
    local a = p.attack_parameters or {}
    if d.type == "ammo-turret" then eq(id, n .. " attack type (kept from gun-turret)", a.type, "projectile") end
    listeq(id, n .. " ammo category", a.ammo_categories or {}, { d.ammo })
    eq(id, n .. " cooldown", a.cooldown, d.cooldown)
    eq(id, n .. " range", a.range, d.range)
    if d.min_range then eq(id, n .. " min_range", a.min_range, d.min_range) end
    if d.health_penalty then eq(id, n .. " health_penalty", a.health_penalty, d.health_penalty) end
    if d.shot_mj then eq(id, n .. " energy per shot MJ", a.ammo_type and a.ammo_type.energy_consumption / 1e6, d.shot_mj) end
    if d.inv then eq(id, n .. " ammo slots", p.get_inventory_size(defines.inventory.turret_ammo), d.inv) end
    if d.aac then eq(id, n .. " automated_ammo_count", p.automated_ammo_count, d.aac) end
  end
  if d.damage then
    -- разрядник: мгновенный урон 45 electric, стикер, цепь magnetics-arc-chain первым действием (§4.6)
    local a = p.attack_parameters or {}
    eq(id, n .. " attack type", a.type, "beam")
    eq(id, n .. " range_mode", a.range_mode, "center-to-bounding-box")
    local act = a.ammo_type and a.ammo_type.action and a.ammo_type.action[1]
    local te = act and act.action_delivery and act.action_delivery[1] and act.action_delivery[1].target_effects or {}
    local kinds, dmg, dtype, sticker, chain, beam_len = {}, nil, nil, nil, nil, nil
    for i, e in ipairs(te) do
      kinds[i] = e.type or (e.action and "nested-result") or "?"   -- у nested-result в API нет поля type (пилот)
      if e.type == "damage" then dmg = e.damage and e.damage.amount; dtype = e.damage and e.damage.type end
      if e.type == "create-sticker" then sticker = e.sticker end
      if kinds[i] == "nested-result" and e.action and e.action[1] and e.action[1].action_delivery then
        local dl = e.action[1].action_delivery[1] or {}
        if dl.type == "chain" then chain = dl.chain end
        if dl.type == "beam" then beam_len = dl.max_length end
      end
    end
    listeq(id, n .. " arc action order", kinds, { "nested-result", "damage", "create-sticker", "nested-result" })
    eq(id, n .. " arc damage", dmg, d.damage)
    eq(id, n .. " arc damage type", dtype, "electric")
    eq(id, n .. " arc sticker", sticker, "electric-mini-stun")
    eq(id, n .. " arc chain", chain, "magnetics-arc-chain")
    eq(id, n .. " arc beam max_length", beam_len, 22)
    if d.drain_kw then eq(id, n .. " drain kW", es and es.drain * 60 / 1e3, d.drain_kw) end
  end
  if d.thorns then
    local r1 = (p.attack_reaction or {})[1] or {}
    local dmg = first_damage(r1.action)
    eq(id, n .. " thorns", dmg and dmg.amount, d.thorns)
  end
  local it = prototypes.item[name]
  eq(id, n .. " item stack", it and it.stack_size, DOC.stacks[name])
end

-- S4 предметы, боеприпасы, категории, жидкости, рецепты, технологии против expected.lua
local function s4_items()
  local id = "S4"
  for name, d in pairs(EXP.items) do
    local it = prototypes.item[name]
    chk(id, name .. " exists", it ~= nil, it ~= nil, true)
    if it then
      eq(id, name .. " stack_size", it.stack_size, d.stack)
      eq(id, name .. " order", it.order, d.order)
      eq(id, name .. " subgroup", it.subgroup and it.subgroup.name, "magnetics-intermediate")
      if d.fuel_category then
        eq(id, name .. " fuel_category", it.fuel_category, d.fuel_category)
        eq(id, name .. " fuel_value (J)", it.fuel_value, si(d.fuel_value))
        eq(id, name .. " burnt_result", it.burnt_result and it.burnt_result.name, d.burnt_result)
      end
      EXPORT.items[name] = { stack = it.stack_size, fuel_value = it.fuel_value }
    end
  end
  for name, d in pairs(EXP.ammo) do
    local it = prototypes.item[name]
    chk(id, name .. " exists", it ~= nil, it ~= nil, true)
    if it then
      eq(id, name .. " type", it.type, "ammo")
      eq(id, name .. " ammo_category", it.ammo_category and it.ammo_category.name, d.category)
      eq(id, name .. " magazine_size", it.magazine_size, d.magazine)
      eq(id, name .. " stack_size", it.stack_size, d.stack)
      eq(id, name .. " order", it.order, d.order)
      eq(id, name .. " subgroup", it.subgroup and it.subgroup.name, "ammo")
      EXPORT.items[name] = { stack = it.stack_size, magazine = it.magazine_size, category = it.ammo_category and it.ammo_category.name }
      local at = it.get_ammo_type() or {}
      eq(id, name .. " target_type", at.target_type, "direction")
      local act = at.action and at.action[1] or {}
      if d.projectile then
        local dl = act.action_delivery and act.action_delivery[1] or {}
        eq(id, name .. " delivery", dl.type, "projectile")
        eq(id, name .. " projectile", dl.projectile, d.projectile)
        eq(id, name .. " starting_speed", dl.starting_speed, d.speed, 1e-6)
        eq(id, name .. " max_range", dl.max_range, d.max_range)
        eq(id, name .. " direction_deviation", dl.direction_deviation, 0.02, 1e-6)
        eq(id, name .. " range_deviation", dl.range_deviation, 0.02, 1e-6)
        local pp = prototypes.entity[d.projectile]
        eq(id, name .. " projectile prototype type", pp and pp.type, "projectile")
      else
        eq(id, name .. " action type", act.type, "line")
        eq(id, name .. " line range", act.range, d.line.range)
        eq(id, name .. " line width", act.width, d.line.width)
        eq(id, name .. " line force", act.force, "enemy")
        eq(id, name .. " clamp_position", at.clamp_position, true)
        local dl = act.action_delivery and act.action_delivery[1] or {}
        eq(id, name .. " line delivery", dl.type, "instant")
        local got = {}
        for _, e in ipairs(dl.target_effects or {}) do
          if e.type == "damage" then got[#got + 1] = tostring(e.damage.amount) .. " " .. e.damage.type end
        end
        local want = {}
        for _, dm in ipairs(d.line.damage) do want[#want + 1] = tostring(dm[1]) .. " " .. dm[2] end
        listeq(id, name .. " line damage", got, want)
      end
    end
  end
  for name, d in pairs(EXP.ammo_categories) do
    local c = prototypes.ammo_category[name]
    chk(id, "ammo-category " .. name .. " exists", c ~= nil, c ~= nil, true)
    if c then eq(id, "ammo-category " .. name .. " bonus_gui_order", c.bonus_gui_order, d.bonus_gui_order) end
  end
  for _, name in ipairs(EXP.fuel_categories) do
    chk(id, "fuel-category " .. name .. " exists", prototypes.fuel_category[name] ~= nil, prototypes.fuel_category[name] ~= nil, true)
  end
  for _, name in ipairs(EXP.recipe_categories) do
    chk(id, "recipe-category " .. name .. " exists", prototypes.recipe_category[name] ~= nil, prototypes.recipe_category[name] ~= nil, true)
  end
  local sg = prototypes.item_subgroup["magnetics-intermediate"]
  chk(id, "subgroup magnetics-intermediate exists", sg ~= nil, sg ~= nil, true)
  if sg then
    eq(id, "subgroup magnetics-intermediate group", sg.group and sg.group.name, "intermediate-products")
    eq(id, "subgroup magnetics-intermediate order", sg.order, "gm")
  end
  for name, d in pairs(EXP.fluids) do
    local f = prototypes.fluid[name]
    chk(id, name .. " exists", f ~= nil, f ~= nil, true)
    if f then
      eq(id, name .. " default_temperature", f.default_temperature, d.default_temperature)
      color_eq(id, name .. " base_color", f.base_color, d.base_color)
      color_eq(id, name .. " flow_color", f.flow_color, d.flow_color)
      eq(id, name .. " order", f.order, d.order)
      eq(id, name .. " subgroup", f.subgroup and f.subgroup.name, "fluid")
    end
  end
  -- DOC: стаки непостроечных предметов и боеприпасы
  for name, d in pairs(DOC.ammo) do
    local it = prototypes.item[name]
    eq(id, "doc " .. name .. " stack", it and it.stack_size, DOC.stacks[name])
    eq(id, "doc " .. name .. " magazine", it and it.magazine_size, d.mag)
    eq(id, "doc " .. name .. " category", it and it.ammo_category and it.ammo_category.name, d.cat)
    local act = it and it.get_ammo_type().action[1] or {}
    if d.line then
      eq(id, "doc " .. name .. " line range", act.range, d.line.range)
      eq(id, "doc " .. name .. " line width", act.width, d.line.width)
    else
      local dl = act.action_delivery and act.action_delivery[1] or {}
      eq(id, "doc " .. name .. " speed", dl.starting_speed, d.speed, 1e-6)
      eq(id, "doc " .. name .. " max_range", dl.max_range, d.max_range)
    end
  end
  for _, name in ipairs({ "magnetics-ferrite", "magnetics-coil", "magnetics-magnet-alloy", "magnetics-superconducting-cable",
                          "magnetics-flux-crystal-uncharged", "magnetics-flux-crystal" }) do
    local it = prototypes.item[name]
    eq(id, "doc " .. name .. " stack", it and it.stack_size, DOC.stacks[name])
  end
  local fc = prototypes.item["magnetics-flux-crystal"]
  eq(id, "doc flux crystal fuel MJ", fc and fc.fuel_value / 1e6, 100)
  eq(id, "doc flux crystal fuel category", fc and fc.fuel_category, "magnetics-flux")
  eq(id, "doc flux crystal burnt_result", fc and fc.burnt_result and fc.burnt_result.name, "magnetics-flux-crystal-uncharged")
  eq(id, "doc ferrofluid temperature", prototypes.fluid["magnetics-ferrofluid"].default_temperature, 25)
  eq(id, "doc liquid nitrogen temperature (PILOT-13: loads)", prototypes.fluid["magnetics-liquid-nitrogen"].default_temperature, -196)
  local ch = prototypes.active_trigger["magnetics-arc-chain"]
  chk(id, "doc arc chain exists", ch ~= nil, ch ~= nil, true)
  if ch then
    for k, v in pairs(DOC.chain) do eq(id, "doc arc chain " .. k, ch[k], v) end
  end
end

local function s4_recipes()
  local id = "S4"
  for name, d in pairs(EXP.recipes) do
    local r = prototypes.recipe[name]
    chk(id, "recipe " .. name .. " exists", r ~= nil, r ~= nil, true)
    if r then
      local n = "recipe " .. name
      eq(id, n .. " category", r.category, d.category)
      eq(id, n .. " energy", r.energy, d.energy)
      eq(id, n .. " enabled at start", r.enabled, false)
      local gi, wi = {}, {}
      for i, x in ipairs(r.ingredients) do gi[i] = x.type .. ":" .. x.name .. "*" .. tostring(x.amount) end
      for i, x in ipairs(d.ing) do wi[i] = x.type .. ":" .. resolve(x.name) .. "*" .. tostring(x.amount) end
      seteq(id, n .. " ingredients (set; движок сортирует)", gi, wi)
      local gp, wp = {}, {}
      for i, x in ipairs(r.products) do gp[i] = x.type .. ":" .. x.name .. "*" .. tostring(x.amount) .. "@" .. tostring(x.probability) end
      for i, x in ipairs(d.res) do wp[i] = x.type .. ":" .. resolve(x.name) .. "*" .. tostring(x.amount) .. "@" .. tostring(x.probability or 1) end
      seteq(id, n .. " products (set)", gp, wp)
      local ae = r.allowed_effects or {}
      eq(id, n .. " allow_productivity", ae.productivity == true, d.prod)
      eq(id, n .. " allow_quality", ae.quality == true, d.allow_quality ~= false)
      if d.subgroup then eq(id, n .. " subgroup", r.subgroup and r.subgroup.name, d.subgroup) end
      if d.order then eq(id, n .. " order", r.order, d.order) end
      if d.tint then
        local t = r.crafting_machine_tints or {}
        for i, k in ipairs({ "primary", "secondary", "tertiary", "quaternary" }) do color_eq(id, n .. " tint " .. k, t[i], d.tint[k]) end
      end
      EXPORT.recipes[name] = { category = r.category, energy = r.energy, ing = gi, res = gp, prod = ae.productivity == true,
                               quality = ae.quality == true, enabled = r.enabled }
    end
  end
end

local function s4_techs()
  local id = "S4"
  for name, d in pairs(EXP.techs) do
    local t = prototypes.technology[name]
    chk(id, "tech " .. name .. " exists", t ~= nil, t ~= nil, true)
    if t then
      local n = "tech " .. name
      local pre, count, time, packs = d.prereq, d.count, d.time, d.packs
      if SA and d.sa then
        pre = sorted(pre)
        for _, x in ipairs(d.sa.extra_prereq) do pre[#pre + 1] = x end
        count, time, packs = d.sa.count, d.sa.time, d.sa.packs
      end
      seteq(id, n .. " prerequisites", keys(t.prerequisites), pre)
      eq(id, n .. " count", t.research_unit_count, count)
      eq(id, n .. " time (s)", t.research_unit_energy / 60, time)
      local gp, ga = {}, true
      for i, x in ipairs(t.research_unit_ingredients) do gp[i] = x.name; ga = ga and x.amount == 1 end
      seteq(id, n .. " packs (set; движок сортирует)", gp, packs)
      chk(id, n .. " pack amounts all 1", ga, ga, true)
      local ge = {}
      for i, e in ipairs(t.effects) do ge[i] = e.type .. ":" .. tostring(e.recipe) end
      local we = {}
      for i, r in ipairs(d.unlocks) do we[i] = "unlock-recipe:" .. r end
      listeq(id, n .. " effects", ge, we)
      EXPORT.techs[name] = { pre = keys(t.prerequisites), count = t.research_unit_count, time = t.research_unit_energy / 60,
                             packs = gp, unlocks = ge }
    end
  end
end

---------------------------------------------------------------------------------------------------------------------
-- S5 граф технологий и достижимость

local function is_magnetics(n) return n:sub(1, 10) == "magnetics-" end
local function magnetics_recipes()
  local out = {}
  for n, r in pairs(prototypes.recipe) do
    if is_magnetics(n) and r.category ~= "recycling" then out[#out + 1] = n end
  end
  table.sort(out)
  return out
end

-- Природные ресурсы (как design/spec_check.py): продукты добычи ресурсов, деревьев, растений, камней, рыбы, астероидов,
-- жидкости плиток, вода, порча; без урановой руды и нефти (их открывают технологии/насосная вышка).
local function natural_set()
  local out = { water = true }
  if prototypes.item["spoilage"] then out.spoilage = true end
  local types = { "resource", "tree", "plant", "simple-entity", "fish", "asteroid-chunk" }
  for _, p in pairs(prototypes.get_entity_filtered({ { filter = "type", type = types } })) do
    local mp = p.mineable_properties
    if mp and mp.products then for _, x in ipairs(mp.products) do out[x.name] = true end end
  end
  for n, _ in pairs(prototypes.asteroid_chunk) do out[n] = true end
  for _, tp in pairs(prototypes.tile) do
    local f = tp.fluid
    if f then out[f.name] = true end
  end
  out["uranium-ore"] = nil
  out["crude-oil"] = nil
  return out
end

local function closure(tname, seen)
  seen = seen or {}
  if seen[tname] then return seen end
  seen[tname] = true
  local t = prototypes.technology[tname]
  if t then for p, _ in pairs(t.prerequisites) do closure(p, seen) end end
  return seen
end

local function s5()
  local id = "S5"
  local T = prototypes.technology
  -- 14 технологий, имена по §5.1
  local have = {}
  for n, _ in pairs(T) do if is_magnetics(n) then have[#have + 1] = n end end
  seteq(id, "Magnetics technologies (14)", have, keys(DOC.techs))
  -- предпосылки существуют и совпадают с §5.1 (SA-форма T13 проверяется в S8)
  for n, d in pairs(DOC.techs) do
    local t = T[n]
    if t then
      for _, p in ipairs(d.pre) do chk(id, n .. " prerequisite " .. p .. " exists", T[p] ~= nil, T[p] ~= nil, true) end
      local pre = sorted(d.pre)
      if SA and d.sa then for _, x in ipairs(d.sa.pre_add) do pre[#pre + 1] = x end end
      seteq(id, n .. " prerequisites = §5.1", keys(t.prerequisites), pre)
      local un = {}
      for _, e in ipairs(t.effects) do if e.type == "unlock-recipe" then un[#un + 1] = e.recipe end end
      listeq(id, n .. " unlocks = §5.1", un, d.un)
    end
  end
  -- ацикличность (обход всех технологий)
  local state, cyc = {}, {}
  local function dfs(n, stack)
    if state[n] == 2 then return end
    if state[n] == 1 then cyc[#cyc + 1] = n; return end
    state[n] = 1
    for p, _ in pairs(T[n].prerequisites) do dfs(p) end
    state[n] = 2
  end
  for n, _ in pairs(T) do dfs(n) end
  chk(id, "technology graph acyclic", #cyc == 0, cyc, {})
  -- рецепты: enabled = false и открываются ровно одной технологией Magnetics
  local unlocked_by = {}
  for tn, t in pairs(T) do
    for _, e in ipairs(t.effects) do
      if e.type == "unlock-recipe" and is_magnetics(e.recipe) then
        unlocked_by[e.recipe] = unlocked_by[e.recipe] or {}
        table.insert(unlocked_by[e.recipe], tn)
      end
    end
  end
  local recs = magnetics_recipes()
  chk(id, "Magnetics recipes (без переработки) = 40", #recs == 40, #recs, 40)
  for _, rn in ipairs(recs) do
    local by = unlocked_by[rn] or {}
    chk(id, rn .. " enabled = false", prototypes.recipe[rn].enabled == false, prototypes.recipe[rn].enabled, false)
    chk(id, rn .. " unlocked by exactly one Magnetics tech", #by == 1 and is_magnetics(by[1]), by, "1 magnetics-*")
  end
  -- никакая ванильная технология не требует технологии Magnetics
  local bad = {}
  for tn, t in pairs(T) do
    if not is_magnetics(tn) then
      for p, _ in pairs(t.prerequisites) do if is_magnetics(p) then bad[#bad + 1] = tn .. "<-" .. p end end
    end
  end
  chk(id, "no vanilla tech has a Magnetics prerequisite", #bad == 0, bad, {})
  -- достижимость: алгоритм design/spec_check.py
  local natural = natural_set()
  local start = {}
  for rn, r in pairs(prototypes.recipe) do
    if r.enabled and not r.hidden and not r.is_parameter and r.category ~= "recycling" then start[#start + 1] = rn end
  end
  local problems = {}
  for tn, _ in pairs(DOC.techs) do
    if T[tn] then
      local C = closure(tn)
      local recipes = {}
      for _, rn in ipairs(start) do recipes[#recipes + 1] = rn end
      for cn, _ in pairs(C) do
        for _, e in ipairs(T[cn].effects) do if e.type == "unlock-recipe" then recipes[#recipes + 1] = e.recipe end end
      end
      local avail = {}
      for k, _ in pairs(natural) do avail[k] = true end
      if C["uranium-mining"] then avail["uranium-ore"] = true end
      local changed = true
      while changed do
        changed = false
        if avail["pumpjack"] and not avail["crude-oil"] then avail["crude-oil"] = true; changed = true end
        for _, rn in ipairs(recipes) do
          local r = prototypes.recipe[rn]
          if r and r.category ~= "recycling" then
            local okr = true
            for _, x in ipairs(r.ingredients) do if not avail[x.name] then okr = false; break end end
            if okr then
              for _, x in ipairs(r.products) do
                if not avail[x.name] then avail[x.name] = true; changed = true end
              end
            end
          end
        end
      end
      for _, e in ipairs(T[tn].effects) do
        if e.type == "unlock-recipe" then
          for _, x in ipairs(prototypes.recipe[e.recipe].ingredients) do
            if not avail[x.name] then problems[#problems + 1] = tn .. ": " .. e.recipe .. " <- " .. x.name end
          end
        end
      end
    end
  end
  chk(id, "reachability problems = 0", #problems == 0, problems, {})
  -- research_all_technologies на отдельной силе (не трогает силу player других ячеек)
  local fname = "magnetics-static-s5"
  local f = game.forces[fname] or game.create_force(fname)
  local ok, err = pcall(function() f.research_all_technologies() end)
  chk(id, "research_all_technologies() raises no error", ok, ok and "ok" or tostring(err), "ok")
  if ok then
    local not_done = {}
    for tn, _ in pairs(DOC.techs) do if not (f.technologies[tn] and f.technologies[tn].researched) then not_done[#not_done + 1] = tn end end
    chk(id, "all Magnetics techs researched after research_all", #not_done == 0, not_done, {})
    local off = {}
    for _, rn in ipairs(recs) do if not f.recipes[rn].enabled then off[#off + 1] = rn end end
    chk(id, "all Magnetics recipes enabled after research_all", #off == 0, off, {})
  end
end

---------------------------------------------------------------------------------------------------------------------
-- S6 связи улучшения

local function mask_str(p)
  local cm = p.collision_mask or {}
  local parts = keys(cm.layers)
  if cm.not_colliding_with_itself then parts[#parts + 1] = "!self" end
  if cm.colliding_with_tiles_only then parts[#parts + 1] = "tiles-only" end
  if cm.consider_tile_transitions then parts[#parts + 1] = "transitions" end
  return join(parts)
end

local function s6()
  local id = "S6"
  local E = prototypes.entity
  local want = {}
  for _, l in ipairs(vanilla_links()) do want[#want + 1] = l end
  for _, l in ipairs(DOC.links_internal) do want[#want + 1] = l end
  for _, l in ipairs(want) do
    local a, b = E[l[1]], E[l[2]]
    local n = l[1] .. " -> " .. l[2]
    chk(id, n .. " both exist", a ~= nil and b ~= nil, { a ~= nil, b ~= nil }, { true, true })
    if a and b then
      eq(id, n .. " next_upgrade", a.next_upgrade and a.next_upgrade.name, l[2])
      chk(id, n .. " same collision_box", join(bbox(a.collision_box)) == join(bbox(b.collision_box)), bbox(b.collision_box), bbox(a.collision_box))
      eq(id, n .. " same collision_mask", mask_str(b), mask_str(a))
      eq(id, n .. " same fast_replaceable_group", b.fast_replaceable_group, a.fast_replaceable_group)
      local itp = b.items_to_place_this and b.items_to_place_this[1]
      local it = itp and prototypes.item[itp.name]
      chk(id, n .. " target item exists and not hidden", it ~= nil and not it.hidden, it and it.hidden, false)
    end
  end
  if SA then
    for _, k in ipairs({ "transport-belt", "underground-belt", "splitter" }) do
      local a = E["express-" .. k]
      eq(id, "SA express-" .. k .. " -> turbo-" .. k .. " unchanged", a and a.next_upgrade and a.next_upgrade.name, "turbo-" .. k)
    end
  end
  -- концы цепочек и остальные постройки Magnetics — без next_upgrade
  local has_link = {}
  for _, l in ipairs(DOC.links_internal) do has_link[l[1]] = true end
  for name, _ in pairs(DOC.entities) do
    local p = E[name]
    if p and not has_link[name] then
      eq(id, name .. " next_upgrade = nil", p.next_upgrade and p.next_upgrade.name, nil)
    end
  end
  for _, name in ipairs(DOC.chain_ends) do chk(id, "chain end " .. name .. " listed", DOC.entities[name] ~= nil, true, true) end
  -- ровно эти ванильные связи ведут в Magnetics
  local allowed = {}
  for _, l in ipairs(want) do allowed[l[1] .. ">" .. l[2]] = true end
  local extra = {}
  for n, p in pairs(E) do
    local nu = p.next_upgrade
    if nu and is_magnetics(nu.name) and not allowed[n .. ">" .. nu.name] then extra[#extra + 1] = n .. ">" .. nu.name end
  end
  chk(id, "no other entity upgrades into Magnetics", #extra == 0, extra, {})
  -- группа быстрой замены каждой копии — §4 (DOC.frg)
  for name, d in pairs(DOC.entities) do
    local p = E[name]
    if p and d.frg then eq(id, name .. " FRG per §4", p.fast_replaceable_group, d.frg) end
  end
  local sp, eb = E["magnetics-maglev-splitter"], E[TOP .. "-splitter"]
  if sp and eb then eq(id, "maglev splitter FRG = " .. TOP .. "-splitter FRG", sp.fast_replaceable_group, eb.fast_replaceable_group) end
end

---------------------------------------------------------------------------------------------------------------------
-- S8 Space Age

local function cond_str(conds)
  local o = {}
  for _, c in ipairs(conds or {}) do
    local mx = (c.max == nil or c.max >= 1e300) and "max" or tostring(c.max)
    o[#o + 1] = c.property .. ">=" .. tostring(c.min) .. "<=" .. mx
  end
  table.sort(o)
  return join(o)
end

local function s8()
  local id = "S8"
  local E = prototypes.entity
  local mag_entities = keys(DOC.entities)
  if SA then
    for _, name in ipairs(mag_entities) do
      local p = E[name]
      if p then
        local want = { { property = "magnetic-field", min = 10 } }
        if DOC.pressure[name] then want[2] = { property = "pressure", min = 10 } end
        eq(id, name .. " surface_conditions", cond_str(p.surface_conditions), cond_str(want))
        eq(id, name .. " heating_energy kW", p.heating_energy * 60 / 1e3, DOC.heat[name] or 0, 1e-6)
      end
    end
    for _, rn in ipairs(magnetics_recipes()) do
      local r = prototypes.recipe[rn]
      local want = rn == "magnetics-stone-separation" and { { property = "magnetic-field", min = 50 } } or {}
      eq(id, "recipe " .. rn .. " surface_conditions", cond_str(r.surface_conditions), cond_str(want))
    end
    local ins = { ["electromagnetic-plant"] = { "magnetics-winding" }, ["cryogenic-plant"] = { "magnetics-cryogenics" },
                  ["foundry"] = { "magnetics-sintering", "magnetics-induction" } }
    for mn, cats in pairs(ins) do
      local p = E[mn]
      for _, c in ipairs(cats) do
        chk(id, mn .. " has category " .. c, p and p.crafting_categories and p.crafting_categories[c] == true, p and p.crafting_categories and p.crafting_categories[c], true)
      end
    end
    local t = prototypes.technology["magnetics-maglev-logistics"]
    local d = DOC.techs["magnetics-maglev-logistics"]
    if t then
      local pre = sorted(d.pre)
      for _, x in ipairs(d.sa.pre_add) do pre[#pre + 1] = x end
      seteq(id, "T13 SA prerequisites", keys(t.prerequisites), pre)
      eq(id, "T13 SA count", t.research_unit_count, d.sa.n)
      eq(id, "T13 SA time", t.research_unit_energy / 60, d.sa.t)
      local gp = {}
      for i, x in ipairs(t.research_unit_ingredients) do gp[i] = x.name end
      seteq(id, "T13 SA packs", gp, d.sa.packs)
    end
  else
    local bad_c, bad_h = {}, {}
    for n, p in pairs(E) do
      if is_magnetics(n) then
        if p.surface_conditions and #p.surface_conditions > 0 then bad_c[#bad_c + 1] = n end
        if (p.heating_energy or 0) ~= 0 then bad_h[#bad_h + 1] = n end
      end
    end
    for n, r in pairs(prototypes.recipe) do
      if is_magnetics(n) and r.surface_conditions and #r.surface_conditions > 0 then bad_c[#bad_c + 1] = n end
    end
    chk(id, "no Magnetics prototype has surface_conditions (no SA)", #bad_c == 0, bad_c, {})
    chk(id, "no Magnetics prototype has heating_energy (no SA)", #bad_h == 0, bad_h, {})
    local t = prototypes.technology["magnetics-maglev-logistics"]
    local d = DOC.techs["magnetics-maglev-logistics"]
    if t then
      seteq(id, "T13 base prerequisites", keys(t.prerequisites), d.pre)
      eq(id, "T13 base count", t.research_unit_count, d.n)
      eq(id, "T13 base time", t.research_unit_energy / 60, d.t)
      local gp = {}
      for i, x in ipairs(t.research_unit_ingredients) do gp[i] = x.name end
      seteq(id, "T13 base packs", gp, d.packs)
    end
  end
  -- §3: кроме машин Magnetics (и SA-вставок) категории Magnetics нет ни у одной машины и ни у персонажа
  local allowed = { ["electromagnetic-plant"] = SA, ["cryogenic-plant"] = SA, ["foundry"] = SA }
  local extra = {}
  for n, p in pairs(E) do
    if not is_magnetics(n) and not allowed[n] and p.crafting_categories then
      for c, _ in pairs(p.crafting_categories) do if is_magnetics(c) then extra[#extra + 1] = n .. ":" .. c end end
    end
  end
  chk(id, "no other vanilla machine or character has a Magnetics category", #extra == 0, extra, {})
end

---------------------------------------------------------------------------------------------------------------------
-- S9 качество и переработка (bq, sa)

local function expected_recycling()
  -- правила quality/prototypes/recycling.lua (FINAL_SPEC [C §11.3]) + §7.5: рецепт перерабатывается, если auto_recycle не
  -- false, категория не smelting/chemistry/…, и у него ровно один предметный продукт с постоянным количеством; предмет
  -- без собственной переработки и без item.auto_recycle = false получает самопереработку <имя>-recycling.
  local no_rec = {}
  for _, n in ipairs(DOC.no_recycle_recipes) do no_rec[n] = true end
  local no_item = {}
  for _, n in ipairs(DOC.no_recycle_items) do no_item[n] = true end
  local out, has = {}, {}
  for _, rn in ipairs(magnetics_recipes()) do
    local r = prototypes.recipe[rn]
    local item_products, item_ingredients = 0, 0
    local single
    for _, x in ipairs(r.products) do if x.type == "item" then item_products = item_products + 1; single = x.name end end
    for _, x in ipairs(r.ingredients) do if x.type == "item" then item_ingredients = item_ingredients + 1 end end
    -- recycling.lua:155 `return next(structure.results)`: без предметных ингредиентов рецепт переработки не создаётся
    if not no_rec[rn] and r.category ~= "chemistry" and r.category ~= "smelting" and item_products == 1 and item_ingredients > 0 then
      out[#out + 1] = single .. "-recycling"; has[single] = true
    end
  end
  for n, it in pairs(prototypes.item) do
    if is_magnetics(n) and not has[n] and not no_item[n] and not string.find(n, "-barrel", 1, true) then out[#out + 1] = n .. "-recycling" end
  end
  table.sort(out)
  return out
end

local function s9()
  local id = "S9"
  local res = prototypes.entity["magnetics-flux-resonator"]
  for q, qp in pairs(prototypes.quality) do
    if q ~= "quality-unknown" then
      eq(id, "resonator crafting speed at " .. q, res.get_crafting_speed(q), 1.0)
    end
  end
  eq(id, "resonator module slots", res.module_inventory_size or 0, 0)
  local er = res.effect_receiver or {}
  eq(id, "resonator uses_module_effects", er.uses_module_effects, false)
  eq(id, "resonator uses_beacon_effects", er.uses_beacon_effects, false)
  eq(id, "resonator uses_surface_effects", er.uses_surface_effects, false)
  eq(id, "resonator quality_affects_energy_usage", res.quality_affects_energy_usage, false)
  local ch = prototypes.recipe["magnetics-flux-crystal-charging"]
  eq(id, "charging allow_productivity", (ch.allowed_effects or {}).productivity == true, false)
  eq(id, "charging allow_quality", (ch.allowed_effects or {}).quality == true, false)
  local gr = prototypes.recipe["magnetics-flux-crystal-growth"]
  eq(id, "growth allow_quality", (gr.allowed_effects or {}).quality == true, false)
  local bad, got = {}, {}
  local crystal = { ["magnetics-flux-crystal"] = true, ["magnetics-flux-crystal-uncharged"] = true }
  for rn, r in pairs(prototypes.recipe) do
    if r.category == "recycling" then
      for _, x in ipairs(r.ingredients) do if crystal[x.name] then bad[#bad + 1] = rn end end
      for _, x in ipairs(r.products) do if crystal[x.name] then bad[#bad + 1] = rn end end
      if is_magnetics(rn) then got[#got + 1] = rn end
    end
  end
  chk(id, "no recycling recipe has a flux crystal", #bad == 0, bad, {})
  local want = expected_recycling()
  seteq(id, "magnetics-*-recycling set (" .. #want .. ")", got, want)
end

---------------------------------------------------------------------------------------------------------------------
-- S10 жидкости: нет бочек (auto_barrel = false проверяет tools/tests.py по выгрузке data.raw — в API игры его нет)

local function s10()
  local id = "S10"
  for name, _ in pairs(EXP.fluids) do chk(id, name .. " exists", prototypes.fluid[name] ~= nil, prototypes.fluid[name] ~= nil, true) end
  local bad = {}
  for n, _ in pairs(prototypes.item) do if string.find(n, "magnetics", 1, true) and string.find(n, "barrel", 1, true) then bad[#bad + 1] = "item " .. n end end
  for n, r in pairs(prototypes.recipe) do
    local mentions = string.find(n, "magnetics", 1, true) ~= nil
    for _, x in ipairs(r.ingredients) do if EXP.fluids[x.name] then mentions = true end end
    for _, x in ipairs(r.products) do if EXP.fluids[x.name] then mentions = true end end
    if mentions and string.find(n, "barrel", 1, true) then bad[#bad + 1] = "recipe " .. n end
  end
  chk(id, "no barrel item/recipe for Magnetics fluids", #bad == 0, bad, {})
end

---------------------------------------------------------------------------------------------------------------------
-- S14 зеркало бонусов (статически)

local function s14()
  local id = "S14"
  local T = prototypes.technology
  local mcat, mtur = {}, {}
  for _, c in ipairs(DOC.cats) do mcat[c] = true end
  for _, t in ipairs(DOC.turrets) do mtur[t] = true end
  local function is_mirror(e) return (e.ammo_category and mcat[e.ammo_category]) or (e.turret_id and mtur[e.turret_id]) end
  for tn, t in pairs(T) do
    local orig, app, order_ok, seen_app = {}, {}, true, false
    for _, e in ipairs(t.effects) do
      if is_mirror(e) then seen_app = true; app[#app + 1] = e
      else
        if seen_app then order_ok = false end
        orig[#orig + 1] = e
      end
    end
    local want = {}
    for _, e in ipairs(orig) do
      if (e.type == "ammo-damage" or e.type == "gun-speed") and e.ammo_category == "bullet" then
        for _, c in ipairs(DOC.cats) do want[#want + 1] = e.type .. ":" .. c .. ":" .. e.modifier end
      elseif e.type == "turret-attack" and e.turret_id == "gun-turret" then
        for _, x in ipairs(DOC.turrets) do want[#want + 1] = e.type .. ":" .. x .. ":" .. e.modifier end
      end
    end
    local got = {}
    for _, e in ipairs(app) do got[#got + 1] = e.type .. ":" .. (e.ammo_category or e.turret_id) .. ":" .. e.modifier end
    if #want > 0 or #got > 0 then
      listeq(id, tn .. " appended copies = source modifiers", got, want)
      chk(id, tn .. " copies appended after vanilla effects", order_ok, order_ok, true)
    end
  end
  -- числа §5.3 / S14
  for lvl = 1, 7 do
    local t = T["physical-projectile-damage-" .. lvl]
    local b, tu = DOC.ppd_bullet[lvl], DOC.ppd_turret[lvl]
    if SA and lvl >= 6 then b, tu = DOC.ppd_sa_67, DOC.ppd_sa_67 end
    if t then
      for _, c in ipairs(DOC.cats) do
        local v
        for _, e in ipairs(t.effects) do if e.type == "ammo-damage" and e.ammo_category == c then v = e.modifier end end
        eq(id, "PPD-" .. lvl .. " ammo-damage " .. c, v, b, 1e-6)
      end
      for _, x in ipairs(DOC.turrets) do
        local v
        for _, e in ipairs(t.effects) do if e.type == "turret-attack" and e.turret_id == x then v = e.modifier end end
        eq(id, "PPD-" .. lvl .. " turret-attack " .. x, v, tu, 1e-6)
      end
    else
      chk(id, "PPD-" .. lvl .. " exists", false, nil, true)
    end
  end
  for lvl = 1, 6 do
    local t = T["weapon-shooting-speed-" .. lvl]
    if t then
      for _, c in ipairs(DOC.cats) do
        local v
        for _, e in ipairs(t.effects) do if e.type == "gun-speed" and e.ammo_category == c then v = e.modifier end end
        eq(id, "WSS-" .. lvl .. " gun-speed " .. c, v, DOC.wss[lvl], 1e-6)
      end
    else
      chk(id, "WSS-" .. lvl .. " exists", false, nil, true)
    end
  end
end

---------------------------------------------------------------------------------------------------------------------
-- S15 потолки дальности, S16 фиксированные рецепты

local function s15()
  local id = "S15"
  for name, d in pairs(DOC.entities) do
    if d.range then
      local p = prototypes.entity[name]
      local a = p.attack_parameters or {}
      chk(id, name .. " attack range <= 36", (a.range or 1e9) <= 36, a.range, "<= 36")
      chk(id, name .. " turret_range <= 36", (p.turret_range or 1e9) <= 36, p.turret_range, "<= 36")
    end
  end
  eq(id, "gauss range = 30", prototypes.entity["magnetics-gauss-turret"].attack_parameters.range, 30)
  for name, d in pairs(DOC.ammo) do
    local at = prototypes.item[name].get_ammo_type()
    chk(id, name .. " no range_modifier", at.range_modifier == nil or at.range_modifier == 1, at.range_modifier, "nil or 1")
    local act = at.action and at.action[1] or {}
    if d.line then
      chk(id, name .. " line range <= 36", (act.range or 1e9) <= 36, act.range, "<= 36")
    else
      local dl = act.action_delivery and act.action_delivery[1] or {}
      chk(id, name .. " projectile max_range <= 36", (dl.max_range or 1e9) <= 36, dl.max_range, "<= 36")
    end
  end
end

local function s16()
  local id = "S16"
  eq(id, "kiln fixed_recipe", prototypes.entity["magnetics-sintering-kiln"].fixed_recipe, "magnetics-ferrite")
  eq(id, "resonator fixed_recipe", prototypes.entity["magnetics-flux-resonator"].fixed_recipe, "magnetics-flux-crystal-charging")
end

---------------------------------------------------------------------------------------------------------------------
-- Ячейки

local function begin(ctx)
  L = ctx.L
  SA = ctx.sa
  CFG = ctx.cfg
  TOP = SA and "turbo" or "express"
end

return {
  { id = "S4", slots = 0, check_at = 1,
    check = function(ctx)
      begin(ctx)
      section("S4", "calibration", s4_calibration)
      for name, d in pairs(EXP.entities) do section("S4", name, s4_entity, name, d) end
      for name, d in pairs(DOC.entities) do section("S4", "doc " .. name, s4_doc_entity, name, d) end
      chk("S4", "entity count (expected.lua) = 26", #keys(EXP.entities) == 26, #keys(EXP.entities), 26)
      section("S4", "items", s4_items)
      section("S4", "recipes", s4_recipes)
      section("S4", "techs", s4_techs)
      EXPORT.cfg = CFG
      helpers.write_file("magnetics-static-export.json", helpers.table_to_json(EXPORT), false)
    end },
  { id = "S5", slots = 0, check_at = 1, check = function(ctx) begin(ctx); section("S5", "S5", s5) end },
  { id = "S6", slots = 0, check_at = 1, check = function(ctx) begin(ctx); section("S6", "S6", s6) end },
  -- S6, часть времени игры (PILOT-25 для стен, ворот, бура, аккумулятора, опоры и лент): планировщик улучшений с
  -- отображениями «откуда → куда» для каждой связи §7.2 помечает постройку к улучшению именно в цель.
  -- Отрицательный контроль: AM2 → намоточный станок (связи нет) не помечается.
  { id = "S6R", slots = 1, check_at = 2,
    setup = function(ctx)
      begin(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      local all = {}
      for _, l in ipairs(vanilla_links()) do all[#all + 1] = l end
      for _, l in ipairs(DOC.links_internal) do all[#all + 1] = l end
      s.links, s.ents = all, {}
      local inv = game.create_inventory(2)
      inv.insert { name = "upgrade-planner", count = 2 }
      local good, bad = inv[1], inv[2]
      s.set_errors = {}
      for i, l in ipairs(all) do
        local proto = prototypes.entity[l[1]]
        local cx, cy = o.x + 4 + (i - 1) * 6, o.y + 8
        local pos = { x = cx + ((proto.tile_width % 2 == 1) and 0.5 or 0), y = cy + ((proto.tile_height % 2 == 1) and 0.5 or 0) }
        local params = { name = l[1], position = pos, force = "player" }
        if proto.type == "underground-belt" then params.type = "input" end
        s.ents[i] = S.create_entity(params)
        local ok, err = pcall(function()
          good.set_mapper(i, "from", { type = "entity", name = l[1] })
          good.set_mapper(i, "to", { type = "entity", name = l[2] })
        end)
        if not ok then s.set_errors[#s.set_errors + 1] = l[1] .. ": " .. tostring(err) end
      end
      s.neg = S.create_entity { name = "assembling-machine-2", position = { o.x + 10.5, o.y + 20.5 }, force = "player" }
      s.neg_set_ok = pcall(function()
        bad.set_mapper(1, "from", { type = "entity", name = "assembling-machine-2" })
        bad.set_mapper(1, "to", { type = "entity", name = "magnetics-coil-winder" })
      end)
      local ok1, e1 = pcall(function() S.upgrade_area { area = { { o.x, o.y + 4 }, { o.x + 127, o.y + 12 } }, force = "player", item = good } end)
      local ok2, e2 = pcall(function() S.upgrade_area { area = { { o.x + 7, o.y + 17 }, { o.x + 14, o.y + 24 } }, force = "player", item = bad } end)
      s.area_ok = { ok1, ok1 and "" or tostring(e1), ok2, ok2 and "" or tostring(e2) }
      inv.destroy()
    end,
    check = function(ctx)
      begin(ctx)
      local s = ctx.state
      chk("S6", "runtime: upgrade planner mappers accepted", #s.set_errors == 0, s.set_errors, {})
      chk("S6", "runtime: upgrade_area ran", s.area_ok[1], s.area_ok[2], "")
      for i, l in ipairs(s.links) do
        local e = s.ents[i]
        local tg = e and e.valid and e.get_upgrade_target()
        local got = { marked = e and e.valid and e.to_be_upgraded() or false, target = tg and tg.name or "nil" }
        chk("S6", "runtime (PILOT-25): upgrade planner " .. l[1] .. " -> " .. l[2], got.marked and got.target == l[2], got,
            { marked = true, target = l[2] })
      end
      local marked = s.neg and s.neg.valid and s.neg.to_be_upgraded() or false
      chk("S6", "runtime negative control: AM2 -> coil winder not marked", not marked,
          { marked = marked, set_ok = s.neg_set_ok, area_ok = s.area_ok[3] }, { marked = false })
    end },
  { id = "S8", slots = 0, check_at = 1, check = function(ctx) begin(ctx); section("S8", "S8", s8) end },
  { id = "S9", slots = 0, check_at = 1, configs = { "bq", "sa" }, check = function(ctx) begin(ctx); section("S9", "S9", s9) end },
  { id = "S10", slots = 0, check_at = 1, check = function(ctx) begin(ctx); section("S10", "S10", s10) end },
  { id = "S14", slots = 0, check_at = 1, check = function(ctx) begin(ctx); section("S14", "S14", s14) end },
  { id = "S15", slots = 0, check_at = 1, check = function(ctx) begin(ctx); section("S15", "S15", s15) end },
  { id = "S16", slots = 0, check_at = 1, check = function(ctx) begin(ctx); section("S16", "S16", s16) end },
  { id = "G3", slots = 0, check_at = 600,
    setup = function(ctx)
      begin(ctx)
      local ok, r = pcall(showroom.build, { force = "magnetics-showroom-test" })
      if not ok then
        L.check("G3", "showroom.build: ошибка Lua", false, nil, nil, tostring(r))
        return
      end
      local s = ctx.state
      s.count, s.base_count, s.errors, s.screenshots = r.count, r.base_count, r.errors, r.screenshots
      s.entities = {}
      for _, rec in ipairs(r.placed) do s.entities[#s.entities + 1] = { name = rec.name, e = rec.entity, base = rec.base, b = rec.base_entity } end
    end,
    -- справочно (не ворота G3): состояния построек витрины через 120 тиков — пишутся в note
    check = function(ctx)
      begin(ctx)
      local s = ctx.state
      if not s.entities then return end
      chk("G3", "26 Magnetics entities placed", s.count == 26, s.count, 26)
      chk("G3", "26 vanilla bases placed", s.base_count == 26, s.base_count, 26)
      chk("G3", "0 errors while furnishing", #s.errors == 0, s.errors, {})
      chk("G3", "headless: 0 screenshots", s.screenshots == 0, s.screenshots, 0)
      local names, invalid = {}, {}
      for _, x in ipairs(s.entities) do
        names[#names + 1] = x.name
        if not (x.e and x.e.valid) then invalid[#invalid + 1] = x.name end
        if not (x.b and x.b.valid) then invalid[#invalid + 1] = x.base .. " (base of " .. x.name .. ")" end
      end
      seteq("G3", "every Magnetics entity once", names, keys(DOC.entities))
      chk("G3", "all placed entities still valid after 600 ticks", #invalid == 0, invalid, {})
      local names_of = {}
      for k, v in pairs(defines.entity_status) do names_of[v] = k end
      local st = {}
      for _, x in ipairs(s.entities) do
        if x.e and x.e.valid then st[#st + 1] = x.name .. "=" .. tostring(x.e.status and names_of[x.e.status] or "-") end
      end
      L.check("G3", "statuses (справочно)", true, nil, nil, table.concat(st, "; "))
      -- PILOT-2 (часть «один крафт»): печь и индукционная печь — сборочные машины на графике печей — крафтят
      -- (витрина: печь на угле, ferrite; индукционная печь на magnet-alloy; 600 тиков = 10 с; крафт 3.2 с каждый)
      for _, x in ipairs(s.entities) do
        if x.name == "magnetics-sintering-kiln" or x.name == "magnetics-induction-furnace" then
          local n = x.e and x.e.valid and x.e.products_finished or 0
          chk("PILOT-2", x.name .. " finished >= 1 craft in the showroom (600 ticks)", n >= 1, n, ">= 1")
        end
      end
      local S = game.surfaces["magnetics-showroom"]
      local n = S and S.count_entities_filtered { name = keys(DOC.entities) } or 0
      chk("G3", "surface magnetics-showroom holds 26 Magnetics entities", n == 26, n, 26)
    end },
}
