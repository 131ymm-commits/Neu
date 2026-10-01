--[[ Walls and combat cells W1–W4, K1–K12 and the T-W wave scenario (FINAL_SPEC §11.6).
Expected values are typed here from the spec text (§11.6, §4.5–§4.7, §8.4), not read from spec.py / expected.lua.
Pilot facts used by the method (design/pilots_combat.md; pilots ran on a scratch copy, never in these cells):
  * damage is measured by POLLING health (the harness owns event registration; one handler per event per mod):
    a target's health is read every tick and, where noted, written back to max (a health write raises no event);
  * targets are made formula-free or exact:
      - `magnetics-test-target` (§11.1) when the test mod defines it; otherwise the stand-in is an enemy-force,
        unpowered vanilla `laser-turret`: no resistances, no healing, immobile, a military target; PILOT-14 showed that
        every turret here (gun, coilgun, gauss, laser, arc, rail) engages it and reads the raw per-hit damage;
      - biters are pinned (stop + distraction none, both ai_settings flags off) AND `disabled_by_script`:
        PILOT-14 showed disabled units are still targeted and do not heal, so health deltas are exact
        (a pinned, enabled behemoth heals 0.1 in the same tick as the hit);
  * resistance formula H_res `(D − decrease) × (1 − percent/100)` is pinned by PILOT-3 (stone wall 100 phys → 77.6;
    behemoth 1200 → 1069.2, 1800 → 1609.2 exactly);
  * shots of ammo turrets = rounds consumed (Σ (count − 1) × magazine + ammo in the ammo slot); one exact shot =
    one item inserted with `ammo = 1`; one arc shot = no network and a pre-charged 1.2 MJ buffer (PILOT-9);
  * energy = buffer delta of a vanilla EEI meter (tertiary, 10 GJ) on an isolated substation (`auto_connect = false`)
    minus the turret's own buffer change (and, for the arc, its 24 kW drain);
  * research only on separate forces (`magnetics-k11`): research is force-wide and would change other cells.
Status names come from defines.entity_status. ]]
local G = "combat"
local L -- set in each check

local SN = {}
for k, v in pairs(defines.entity_status) do SN[v] = k end
local function status(e) return (e and e.valid and e.status) and SN[e.status] or "nil" end

local function eq(name, got, exp, rel, abs, note) L.eq(G, name, got, exp, rel, abs, note) end
local function range(name, got, lo, hi, note) L.check(G, name, type(got) == "number" and got >= lo and got <= hi, got, { lo, hi }, note) end
local function is(name, got, exp, note) L.check(G, name, got == exp, got, exp, note) end

-------------------------------------------------------------------------------------------------- helpers
local function new(S, name, pos, force)
  local e = S.create_entity { name = name, position = pos, force = force or "player" }
  assert(e, "create_entity failed: " .. name)
  return e
end
-- pinned enemy unit; mode "disabled" also sets disabled_by_script (no healing, still targeted: PILOT-14)
local function unit(S, name, pos, mode)
  local u = new(S, name, pos, "enemy")
  u.commandable.set_command { type = defines.command.stop, distraction = defines.distraction.none }
  u.ai_settings.allow_destroy_when_commands_fail = false
  u.ai_settings.allow_try_return_to_spawner = false
  if mode == "disabled" then u.disabled_by_script = true end
  return u
end
-- formula-free target: magnetics-test-target if the test mod has it, else an unpowered enemy laser-turret
local function tt_name() return prototypes.entity["magnetics-test-target"] and "magnetics-test-target" or "laser-turret" end
local function target(S, pos) return new(S, tt_name(), pos, "enemy") end
local function tt_note() return "target " .. tt_name() .. " (enemy, no resistances, no healing)" end
-- isolated electric island: substation (auto_connect = false) + vanilla EEI as an energy meter
local function island(S, x, y, force, mx, my)
  local pole = S.create_entity { name = "substation", position = { x, y }, force = force or "player", auto_connect = false }
  assert(pole, "create_entity failed: substation")
  local m = new(S, "electric-energy-interface", { mx or (x - 4), my or y }, force)
  m.power_production = 0; m.power_usage = 0; m.electric_buffer_size = 1e10; m.energy = 1e10
  return pole, m
end
local function turret(S, name, pos, force)
  local t = new(S, name, pos, force)
  t.destructible = false
  return t
end
local function rounds(t)
  local inv = t.valid and t.get_inventory(defines.inventory.turret_ammo)
  local n = 0
  if inv then
    for i = 1, #inv do
      local st = inv[i]
      if st.valid_for_read then n = n + (st.count - 1) * st.prototype.magazine_size + st.ammo end
    end
  end
  return n
end
-- polled target record {e, max, h, hits = {{t, d}}}; reset = write health back to max every tick
local function rec(e) return { e = e, max = e.max_health, h = e.health, hits = {} } end
local function poll(r, t, reset, thr)
  local e = r.e
  if not (e and e.valid) then
    if not r.dead then r.dead = t end
    return
  end
  local h = e.health
  local d = r.h - h
  if d > (thr or 1e-4) then r.hits[#r.hits + 1] = { t, d } end
  if reset then e.health = r.max; r.h = r.max else r.h = h end
end
local function hits_in(r, t0, t1)
  local n, sum, lo, hi, first = 0, 0, nil, nil, nil
  for _, h in ipairs(r.hits) do
    if h[1] > t0 and h[1] <= t1 then
      n = n + 1; sum = sum + h[2]
      lo = lo and math.min(lo, h[2]) or h[2]; hi = hi and math.max(hi, h[2]) or h[2]
      first = first or h[2]
    end
  end
  return n, sum, lo, hi, first
end
local function damaged(r) return (not r.e.valid) or r.e.health < r.max - 1e-4 end

local cells = {}

-------------------------------------------------------------------------------------------------- W1 resistances
-- LuaEntity.damage(100, "enemy", type) returns the damage applied after resistances (H_res, PILOT-3).
local DT = { "physical", "impact", "explosion", "fire", "acid", "laser", "electric", "poison" }
local W1 = {
  { "stone-wall", { 77.6, 22, 63, 0, 20, 30, 100, 100 } },
  { "magnetics-ferrite-wall", { 72.75, 22, 63, 0, 20, 30, 70, 100 } },
  { "magnetics-magnet-wall", { 66.5, 17.5, 55.25, 0, 15, 25, 50, 100 } },
  { "magnetics-magnet-gate", { 66.5, 17.5, 55.25, 0, 15, 25, 50, 100 } },
  { "magnetics-superconducting-wall", { 59.8, 12, 48, 0, 10, 0, 0, 100 } },
  { "magnetics-superconducting-gate", { 59.8, 12, 48, 0, 10, 0, 0, 100 } },
}
cells[#cells + 1] = { id = "W1", configs = { "base", "sa" }, check_at = 2,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    s.r = {}
    for i, w in ipairs(W1) do
      for j, dt in ipairs(DT) do
        local e = new(S, w[1], { o.x + 10 + 3 * j + 0.5, o.y + 10 + 3 * i + 0.5 })
        local h0 = e.health
        local ret = e.damage(100, "enemy", dt)
        s.r[#s.r + 1] = { w = w[1], dt = dt, exp = w[2][j], ret = ret, dh = h0 - (e.valid and e.health or 0) }
      end
    end
  end,
  check = function(ctx)
    L = ctx.L
    for _, r in ipairs(ctx.state.r) do
      eq("W1 " .. r.w .. " damage(100, " .. r.dt .. ") applied", r.ret, r.exp, 0, 0.01,
         "return value of LuaEntity.damage; health delta " .. string.format("%.4f", r.dh))
    end
  end }

-------------------------------------------------------------------------------------------------- W2 max health
cells[#cells + 1] = { id = "W2", configs = { "base", "sa" }, slots = 0, check_at = 1,
  check = function(ctx)
    L = ctx.L
    for _, w in ipairs { { "magnetics-ferrite-wall", 500 }, { "magnetics-magnet-wall", 800 }, { "magnetics-superconducting-wall", 1500 },
                         { "magnetics-magnet-gate", 800 }, { "magnetics-superconducting-gate", 1500 } } do
      local p = prototypes.entity[w[1]]
      eq("W2 " .. w[1] .. " max health", p and p.get_max_health() or "missing", w[2], 0, 0)
    end
  end }

-------------------------------------------------------------------------------------------------- W3 thorns
-- One medium biter commanded to attack each wall for 20 s. Bites = ticks where the wall's health drops (walls do not
-- heal). Thorns = ticks where the biter's health drops by > 0.5 (it heals 0.01/tick), plus its death on a bite tick.
-- Thorn amount = drop + one tick of healing (PILOT-11 events: one electric event per bite, same tick, cause = wall).
local W3 = {
  { "magnetics-magnet-wall", 5 }, { "magnetics-superconducting-wall", 10 }, { "magnetics-magnet-gate", 5 },
  { "magnetics-superconducting-gate", 10 }, { "stone-wall", 0 },
  -- большие и гигантские жуки кусают с 2,07–2,16 клетки: шипам нужен range 3 (§15)
  { "magnetics-magnet-wall", 5, "big-biter" }, { "magnetics-superconducting-wall", 10, "big-biter" },
  { "magnetics-superconducting-wall", 10, "behemoth-biter" }, { "stone-wall", 0, "big-biter" },
}
local function attacker(S, name, wall, pos)
  local b = new(S, name, pos, "enemy")
  b.ai_settings.allow_destroy_when_commands_fail = false
  b.ai_settings.allow_try_return_to_spawner = false
  b.commandable.set_command { type = defines.command.attack, target = wall, distraction = defines.distraction.none }
  return b
end
local function bite_tick(p, t)
  local w, b = p.w, p.b
  local bite = false
  if w.e.valid then
    local h = w.e.health
    if p.wh - h > 1e-4 then p.bites[#p.bites + 1] = { t, p.wh - h }; bite = true end
    p.wh = h
  end
  if b.e.valid then
    local h = b.e.health
    if p.bh - h > 0.5 then p.thorns[#p.thorns + 1] = { t, p.bh - h + p.heal, bite } end
    p.bh = h
  elseif not p.died then
    p.died = t
    p.died_on_bite = bite
  end
end
-- Подсчёт по событиям урона (крючок L.on_damaged): укус = урон стене с cause = её жук; шип = урон жуку с cause = его стена.
-- Опрос здоровья путал посторонний урон соседних ячеек и лечение больших жуков с шипами (отладка w3dbg, 01.10.2026).
local LIB = require("lib")
LIB.on_damaged[#LIB.on_damaged + 1] = function(e)
  local s = storage.cells and storage.cells["W3"]
  if not (s and s.map) then return end
  local ent = e.entity
  if not ent.valid or not ent.unit_number then return end
  local m = s.map[ent.unit_number]
  if not m then return end
  local p = s.p[m.i]
  local c = e.cause
  -- смертельный укус: шип убил жука в тот же тик, и в событии урона стене его cause уже недействителен или nil
  if m.role == "wall" and (c == nil or not c.valid) then
    p.bites[#p.bites + 1] = { game.tick, e.final_damage_amount, "fatal" }
    return
  end
  if not (c and c.valid) then return end
  if m.role == "wall" and c == p.b.e then
    p.bites[#p.bites + 1] = { game.tick, e.final_damage_amount }
  elseif m.role == "biter" and c == p.w.e then
    p.thorns[#p.thorns + 1] = { game.tick, e.final_damage_amount, e.damage_type.name }
  end
end
cells[#cells + 1] = { id = "W3", configs = { "base", "sa" }, check_at = 1200,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    s.p, s.map = {}, {}
    for i, w in ipairs(W3) do
      local y = o.y + 10 + 22 * ((i - 1) % 5)
      local x = o.x + 20.5 + 60 * math.floor((i - 1) / 5)
      local wall = new(S, w[1], { x, y + 0.5 })
      local b = attacker(S, w[3] or "medium-biter", wall, { x + 3, y + 0.5 })
      s.p[i] = { name = w[1] .. (w[3] and (" vs " .. w[3]) or ""), thorn = w[2], w = { e = wall }, b = { e = b }, bites = {}, thorns = {} }
      s.map[wall.unit_number] = { i = i, role = "wall" }
      s.map[b.unit_number] = { i = i, role = "biter" }
    end
  end,
  check = function(ctx)
    L = ctx.L
    for _, p in ipairs(ctx.state.p) do
      local nb, nt = #p.bites, #p.thorns
      local off, same_tick = 0, 0
      local bite_ticks = {}
      for _, bt in ipairs(p.bites) do bite_ticks[bt[1]] = true end
      for _, th in ipairs(p.thorns) do
        if math.abs(th[2] - p.thorn) > 1e-3 or th[3] ~= "electric" then off = off + 1 end
        if bite_ticks[th[1]] then same_tick = same_tick + 1 end
      end
      local lt, lb = p.thorns[nt] and p.thorns[nt][1], p.bites[nb] and p.bites[nb][1]
      local note = string.format("bites %d, thorn events %d (on bite ticks %d); last thorn t%s, last bite t%s, biter %s",
        nb, nt, same_tick, tostring(lt), tostring(lb), p.b.e.valid and "alive" or "dead")
      range("W3 " .. p.name .. " bites in 20 s (set-up sanity)", nb, 5, 1e9, note)
      if p.thorn > 0 then
        eq("W3 " .. p.name .. " thorn damage per bite (electric)", p.thorns[1] and p.thorns[1][2] or 0, p.thorn, 0, 1e-3, note)
        is("W3 " .. p.name .. " thorn events off the expected amount/type", off, 0, note)
        eq("W3 " .. p.name .. " thorn events = bites ± 1", nt, nb, 0, 1, note)
        eq("W3 " .. p.name .. " thorn events not on a bite tick", nt - same_tick, 0, 0, 0, note)
      else
        is("W3 " .. p.name .. " thorn events (control)", nt, 0, note)
      end
    end
  end }

-------------------------------------------------------------------------------------------------- W4 small biters
cells[#cells + 1] = { id = "W4", configs = { "base", "sa" }, check_at = 600,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    s.p = {}
    for i, w in ipairs { { "magnetics-magnet-wall", 4 }, { "magnetics-superconducting-wall", 2 } } do
      local y = o.y + 20 + 40 * (i - 1)
      local wall = new(S, w[1], { o.x + 20.5, y + 0.5 })
      local b = attacker(S, "small-biter", wall, { o.x + 23.5, y + 0.5 })
      s.p[i] = { name = w[1], exp = w[2], w = { e = wall }, b = { e = b }, wh = wall.health, bh = b.health,
                 heal = b.prototype.healing_per_tick, bites = {}, thorns = {} }
    end
  end,
  tick = function(ctx, t) for _, p in ipairs(ctx.state.p) do bite_tick(p, t) end end,
  check = function(ctx)
    L = ctx.L
    for _, p in ipairs(ctx.state.p) do
      local n = 0
      for _, bt in ipairs(p.bites) do if not p.died or bt[1] <= p.died then n = n + 1 end end
      local note = string.format("died at tick %s, on a bite tick %s; bites %d", tostring(p.died), tostring(p.died_on_bite), #p.bites)
      is("W4 small biter dies on bite no. (" .. p.name .. ")", (p.died and p.died_on_bite) and n or ("alive/" .. n), p.exp, note)
    end
  end }

-------------------------------------------------------------------------------------------------- K1 coilgun per hit and rate
local WARM, WIN = 600, 3600
cells[#cells + 1] = { id = "K1", configs = { "base", "sa" }, check_at = WARM + WIN,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    s.p = {}
    for i, a in ipairs { { "magnetics-ferrite-slug", 20 }, { "magnetics-magnet-slug", 32 } } do
      local x, y = o.x + 20, o.y + 20 + 64 * (i - 1)
      island(S, x - 3, y + 3)
      local tu = turret(S, "magnetics-coilgun-turret", { x, y })
      tu.insert { name = a[1], count = 30 }
      s.p[i] = { ammo = a[1], exp = a[2], tu = tu, r = rec(target(S, { x + 12, y })) }
    end
  end,
  tick = function(ctx, t)
    for _, p in ipairs(ctx.state.p) do
      poll(p.r, t, true)
      if t == WARM then p.r0 = rounds(p.tu); p.i0 = p.tu.get_item_count(p.ammo) end
      if t == WARM + WIN then p.r1 = rounds(p.tu); p.i1 = p.tu.get_item_count(p.ammo) end
    end
  end,
  check = function(ctx)
    L = ctx.L
    for _, p in ipairs(ctx.state.p) do
      local n, sum, lo, hi = hits_in(p.r, WARM, WARM + WIN)
      local shots = p.r0 - p.r1
      local note = string.format("%s; hits in window %d, rounds %d -> %d, items %d -> %d", tt_note(), n, p.r0, p.r1, p.i0, p.i1)
      eq("K1 coilgun " .. p.ammo .. " damage per hit (min)", lo, p.exp, 0, 0.01, note)
      eq("K1 coilgun " .. p.ammo .. " damage per hit (max)", hi, p.exp, 0, 0.01, note)
      eq("K1 coilgun " .. p.ammo .. " shots/s (rounds consumed / 60 s)", shots / (WIN / 60), 2.5, 0, 0.05, note)
      eq("K1 coilgun " .. p.ammo .. " hits = shots ± 1", n, shots, 0, 1, note)
      eq("K1 " .. p.ammo .. " magazine size", prototypes.item[p.ammo].magazine_size, 10, 0, 0)
      eq("K1 " .. p.ammo .. " items consumed = shots / 10 ± 1", p.i0 - p.i1, shots / 10, 0, 1, note)
    end
  end }

-------------------------------------------------------------------------------------------------- K2 coilgun vs medium biter
cells[#cells + 1] = { id = "K2", configs = { "base", "sa" }, check_at = 600,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    s.p = {}
    for i, a in ipairs { { "magnetics-ferrite-slug", 14.4 }, { "magnetics-magnet-slug", 25.2 } } do
      local x, y = o.x + 20, o.y + 20 + 64 * (i - 1)
      island(S, x - 3, y + 3)
      local tu = turret(S, "magnetics-coilgun-turret", { x, y })
      tu.insert { name = a[1], count = 5 }
      s.p[i] = { ammo = a[1], exp = a[2], r = rec(unit(S, "medium-biter", { x + 12, y }, "disabled")) }
    end
  end,
  tick = function(ctx, t) for _, p in ipairs(ctx.state.p) do poll(p.r, t, true) end end,
  check = function(ctx)
    L = ctx.L
    for _, p in ipairs(ctx.state.p) do
      local n, sum, lo, hi = hits_in(p.r, 0, 600)
      local note = "pinned + disabled medium biter (physical 4/10 %), health reset each tick; hits " .. n
      range("K2 coilgun " .. p.ammo .. " hits on the medium biter", n, 5, 1e9, note)
      eq("K2 coilgun " .. p.ammo .. " vs medium biter per hit (min)", lo, p.exp, 0, 0.01, note)
      eq("K2 coilgun " .. p.ammo .. " vs medium biter per hit (max)", hi, p.exp, 0, 0.01, note)
    end
  end }

-------------------------------------------------------------------------------------------------- K3 pierce
-- one shot (one item with ammo = 1) at 5 pinned biters on the line of fire, 8..12 tiles out, 1 tile apart.
cells[#cells + 1] = { id = "K3", configs = { "base", "sa" }, check_at = 300,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    s.p = {}
    for i, a in ipairs { { "magnetics-ferrite-slug", "small-biter", 3 }, { "magnetics-magnet-slug", "medium-biter", 1 } } do  -- магнитная: 1 (PILOT-7, §15)
      local x, y = o.x + 20, o.y + 20 + 64 * (i - 1)
      island(S, x - 3, y + 3)
      local tu = turret(S, "magnetics-coilgun-turret", { x, y })
      tu.insert { name = a[1], count = 1, ammo = 1 }
      local bs = {}
      for k = 1, 5 do bs[k] = rec(unit(S, a[2], { x + 7 + k, y }, "disabled")) end
      s.p[i] = { ammo = a[1], biter = a[2], exp = a[3], tu = tu, bs = bs }
    end
  end,
  check = function(ctx)
    L = ctx.L
    for _, p in ipairs(ctx.state.p) do
      local n, which = 0, {}
      for k, r in ipairs(p.bs) do if damaged(r) then n = n + 1; which[#which + 1] = k end end
      local note = "damaged biters (1 = nearest): " .. table.concat(which, ",") .. "; rounds left " .. rounds(p.tu) ..
        ". PILOT-7: a slug continues only through entities its hit destroys; it stops in the first survivor"
      is("K3 " .. p.ammo .. " one shot fired", rounds(p.tu), 0, note)
      is("K3 " .. p.ammo .. " distinct " .. p.biter .. "s damaged by one slug", n, p.exp, note)
    end
  end }

-------------------------------------------------------------------------------------------------- K4 friendly fire
cells[#cells + 1] = { id = "K4", configs = { "base", "sa" }, check_at = 1800,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    s.p = {}
    for i, a in ipairs { { "magnetics-coilgun-turret", "magnetics-ferrite-slug" }, { "magnetics-gauss-turret", "magnetics-gauss-slug" } } do
      local x, y = o.x + 20, o.y + 24 + 72 * (i - 1)
      island(S, x - 3, y + 3)
      local tu = turret(S, a[1], { x, y })
      tu.insert { name = a[2], count = 20 }
      local walls = {}
      for dx = 1, 3 do for dy = -2, 1 do walls[#walls + 1] = new(S, "stone-wall", { x + 2 + dx + 0.5, y + dy + 0.5 }) end end
      local bs = {}
      for k, ang in ipairs { -12, -6, 0, 6, 12 } do
        local r = math.rad(ang)
        bs[k] = rec(unit(S, "medium-biter", { x + 12 * math.cos(r), y + 12 * math.sin(r) }, "disabled"))
      end
      s.p[i] = { name = a[1], tu = tu, r0 = rounds(tu), walls = walls, bs = bs }
    end
  end,
  check = function(ctx)
    L = ctx.L
    for _, p in ipairs(ctx.state.p) do
      local lost, gone = 0, 0
      for _, w in ipairs(p.walls) do if w.valid then lost = lost + (w.max_health - w.health) else gone = gone + 1 end end
      local hit = 0
      for _, r in ipairs(p.bs) do if damaged(r) then hit = hit + 1 end end
      local note = string.format("%d own stone walls (3 deep) between turret and 5 medium biters; shots %d, biters hit %d, walls gone %d",
        #p.walls, p.r0 - rounds(p.tu), hit, gone)
      range("K4 " .. p.name .. " shots fired over the walls (set-up sanity)", p.r0 - rounds(p.tu), 3, 1e9, note)
      eq("K4 " .. p.name .. " own wall health lost", lost + gone * 350, 0, 0, 0, note)
    end
  end }

-------------------------------------------------------------------------------------------------- K5 gauss
cells[#cells + 1] = { id = "K5", configs = { "base", "sa" }, check_at = WARM + WIN,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    local function g(row)
      local x, y = o.x + 10, o.y + 10 + 32 * row
      island(S, x - 3, y + 3)
      local tu = turret(S, "magnetics-gauss-turret", { x, y })
      tu.insert { name = "magnetics-gauss-slug", count = 30 }
      return tu, x, y
    end
    local tu0, x, y = g(0)
    s.tu = tu0
    s.tt = rec(target(S, { x + 12, y }))
    local tu1, x1, y1 = g(1)
    s.big = rec(unit(S, "big-biter", { x1 + 12, y1 }, "disabled"))
    -- range: the test target is 1×1 and snaps to the tile centre (y + 0.5): distances 29.504 / 30.504
    local far = prototypes.entity["magnetics-test-target"] and "magnetics-test-target" or "behemoth-biter"
    s.far = far
    local tu2, x2, y2 = g(2)
    s.near = rec(far == "behemoth-biter" and unit(S, far, { x2 + 29.5, y2 }, "disabled") or new(S, far, { x2 + 29.5, y2 }, "enemy"))
    local tu3, x3, y3 = g(3)
    s.out = rec(far == "behemoth-biter" and unit(S, far, { x3 + 30.5, y3 }, "disabled") or new(S, far, { x3 + 30.5, y3 }, "enemy"))
    s.dn = math.sqrt((s.near.e.position.x - tu2.position.x) ^ 2 + (s.near.e.position.y - tu2.position.y) ^ 2)
    s.do_ = math.sqrt((s.out.e.position.x - tu3.position.x) ^ 2 + (s.out.e.position.y - tu3.position.y) ^ 2)
  end,
  tick = function(ctx, t)
    local s = ctx.state
    poll(s.tt, t, true); poll(s.big, t, true); poll(s.near, t, true); poll(s.out, t, true)
    if t == WARM then s.r0 = rounds(s.tu) end
    if t == WARM + WIN then s.r1 = rounds(s.tu) end
  end,
  check = function(ctx)
    L = ctx.L
    local s = ctx.state
    local n, _, lo, hi = hits_in(s.tt, WARM, WARM + WIN)
    local note = tt_note() .. "; hits " .. n .. ", rounds " .. s.r0 .. " -> " .. s.r1
    eq("K5 gauss per hit on test target (min)", lo, 90, 0, 0.01, note)
    eq("K5 gauss per hit on test target (max)", hi, 90, 0, 0.01, note)
    eq("K5 gauss shots/s (rounds consumed / 60 s)", (s.r0 - s.r1) / (WIN / 60), 1.0, 0, 0.02, note)
    local nb, _, blo, bhi = hits_in(s.big, 0, WARM + WIN)
    eq("K5 gauss vs big biter per hit (min)", blo, 73.8, 0, 0.01, "pinned + disabled big biter (physical 8/10 %); hits " .. nb)
    eq("K5 gauss vs big biter per hit (max)", bhi, 73.8, 0, 0.01, "H_res")
    local first = s.near.hits[1] and s.near.hits[1][1] or "never"
    local fnote = string.format("%s at centre distance %.3f; PILOT-17: gun-turret copies engage units out to range + unit collision radius (behemoth 0.4)", s.far, s.dn)
    range("K5 gauss engages a target at 29.5 within 5 s (first hit tick)", first, 1, 300, fnote)
    is("K5 gauss never engages a target at 30.5 (hits in 70 s)", #s.out.hits,  0,
       string.format("%s at centre distance %.3f", s.far, s.do_))
  end }

-------------------------------------------------------------------------------------------------- K6 energy per shot
local K6 = {
  { n = "magnetics-coilgun-turret", ammo = "magnetics-ferrite-slug", count = 40, exp = 40e3, row = 0, x = 10 },
  { n = "magnetics-gauss-turret", ammo = "magnetics-gauss-slug", count = 30, exp = 250e3, row = 1, x = 10 },
  { n = "magnetics-arc-emitter", exp = 1e6, row = 2, x = 10 },
  { n = "magnetics-rail-cannon", ammo = "magnetics-rail-slug", count = 20, exp = 4e6, row = 3, x = 70, beh = true },
}
local K6_T0, K6_T1, K6_CUT, K6_END = 600, 2400, 3000, 3600
cells[#cells + 1] = { id = "K6", configs = { "base", "sa" }, check_at = K6_END,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    s.p = {}
    for i, d in ipairs(K6) do
      local x, y = o.x + d.x, o.y + 10 + 32 * d.row
      local pole, m = island(S, x - 3, y + 3)
      local tu = turret(S, d.n, { x, y })
      if d.ammo then tu.insert { name = d.ammo, count = d.count } end
      local tg = (d.beh and not prototypes.entity["magnetics-test-target"]) and unit(S, "behemoth-biter", { x + 10, y }, "disabled") or target(S, { x + 10, y })
      s.p[i] = { d = i, tu = tu, pole = pole, m = m, r = rec(tg),
                 drain = d.ammo and 0 or (prototypes.entity[d.n].electric_energy_source_prototype.drain or 0) }
    end
    -- a coilgun that never had a pole (ammo loaded, target in range)
    local x, y = o.x + 70, o.y + 10
    s.np = turret(S, "magnetics-coilgun-turret", { x, y })
    s.np.insert { name = "magnetics-ferrite-slug", count = 5 }
    s.np_r0 = rounds(s.np)
    s.np_t = rec(target(S, { x + 10, y }))
  end,
  tick = function(ctx, t)
    local s = ctx.state
    poll(s.np_t, t, true)
    if t == K6_END then s.np_st = status(s.np); s.np_e = s.np.energy end
    for _, p in ipairs(s.p) do
      poll(p.r, t, true)
      if t == K6_T0 or t == K6_T1 then
        p[t] = { m = 1e10 - p.m.energy, b = p.tu.energy, r = rounds(p.tu) }
      end
      if t == K6_T1 and p.pole.valid then p.pole.destroy() end
      if t == K6_CUT then p.rcut = rounds(p.tu) end
      if t == K6_END then p.rend = rounds(p.tu); p.st = status(p.tu) end
    end
  end,
  check = function(ctx)
    L = ctx.L
    for _, p in ipairs(ctx.state.p) do
      local d = K6[p.d]
      local a, b = p[K6_T0], p[K6_T1]
      local shots, after, late
      if d.ammo then
        shots = a.r - b.r
        after = b.r - p.rcut
        late = p.rcut - p.rend
      else
        shots = hits_in(p.r, K6_T0, K6_T1)
        after = hits_in(p.r, K6_T1, K6_CUT)
        late = hits_in(p.r, K6_CUT, K6_END)
      end
      local drain = p.drain * (K6_T1 - K6_T0)
      local e = (b.m - a.m) - (b.b - a.b) - drain
      local note = string.format("meter %.0f J, turret buffer %.0f -> %.0f J, drain %.0f J, shots %d", b.m - a.m, a.b, b.b, drain, shots)
      range("K6 " .. d.n .. " shots in the 30 s window", shots, 2, 1e9, note)
      eq("K6 " .. d.n .. " energy per shot (J)", shots > 0 and e / shots or 0, d.exp, 0.02, 0, note)
      local cnote = "pole removed at tick " .. K6_T1 .. "; shots from the turret's own buffer in the first 600 ticks: " .. after ..
        ", turret energy at the end " .. string.format("%.0f J", p.tu.energy) ..
        ". Engine: the status reads low_power while a sub-shot remainder stays in the buffer, no_power only at 0 J"
      is("K6 " .. d.n .. " shots after the buffer is spent (pole removed)", late, 0, cnote)
      L.check(G, "K6 " .. d.n .. " status after the pole is removed (no_power or low_power, §15)", p.st == "no_power" or p.st == "low_power", p.st, "no_power|low_power", cnote)
    end
    local s = ctx.state
    local nnote = string.format("ammo loaded, target in range, no pole ever; turret energy %.0f J", s.np_e)
    is("K6 coilgun without a pole: shots", s.np_r0 - rounds(s.np), 0, nnote)
    is("K6 coilgun without a pole: hits on the target", #s.np_t.hits, 0, nnote)
    is("K6 coilgun without a pole: status", s.np_st, "no_power", nnote)
  end }

-------------------------------------------------------------------------------------------------- K7 arc chain
cells[#cells + 1] = { id = "K7", configs = { "base", "sa" }, check_at = 120,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    local x, y = o.x + 20, o.y + 64
    local tu = turret(S, "magnetics-arc-emitter", { x, y })
    tu.energy = 1.2e6 -- one shot: no network, buffer for exactly one 1 MJ shot (PILOT-9)
    s.bs = {}
    for k = 0, 4 do s.bs[k + 1] = rec(unit(S, "medium-biter", { x + 10 + 4 * k, y }, "disabled")) end
    s.wall = new(S, "stone-wall", { x + 18.5, y + 2.5 })
    s.stk = {}
  end,
  tick = function(ctx, t)
    local s = ctx.state
    for k, r in ipairs(s.bs) do
      poll(r, t, false)
      local e = r.e
      if e.valid and e.stickers then
        for _, st in ipairs(e.stickers) do if st.name == "electric-mini-stun" then s.stk[k] = s.stk[k] or t end end
      end
    end
  end,
  check = function(ctx)
    L = ctx.L
    local s = ctx.state
    local total, distinct, first, firstk, bounces = 0, 0, nil, nil, {}
    for k, r in ipairs(s.bs) do
      if #r.hits > 0 then
        distinct = distinct + 1
        for _, h in ipairs(r.hits) do
          total = total + h[2]
          if not first or h[1] < first[1] then first = h; firstk = k end
        end
      end
    end
    for k, r in ipairs(s.bs) do for _, h in ipairs(r.hits) do if not (k == firstk and h == first) then bounces[#bounces + 1] = h[2] end end end
    local stuck = 0
    for k = 1, 5 do if s.stk[k] then stuck = stuck + 1 end end
    local note = "5 pinned+disabled medium biters 4 tiles apart; bounces " .. table.concat(bounces, ", ")
    eq("K7 arc primary hit", first and first[2] or 0, 45, 0, 0.01, note)
    is("K7 arc bounces", #bounces, 4, note)
    local bad = 0
    for _, b in ipairs(bounces) do if math.abs(b - 30) > 0.01 then bad = bad + 1 end end
    is("K7 arc bounces not equal to 30", bad, 0, note)
    eq("K7 arc total damage of one shot", total, 165, 0, 0.01, note)
    is("K7 arc distinct entities damaged", distinct, 5, note)
    is("K7 arc electric-mini-stun stickers on distinct biters", stuck, 5, note)
    eq("K7 own stone wall 2 tiles from the chain keeps full health", s.wall.valid and s.wall.health or 0, 350, 0, 0)
  end }

-------------------------------------------------------------------------------------------------- K8 arc vs laser
cells[#cells + 1] = { id = "K8", configs = { "base", "sa" }, check_at = WARM + WIN,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    s.p = {}
    for i, n in ipairs { "laser-turret", "magnetics-arc-emitter" } do
      local x, y = o.x + 20, o.y + 20 + 64 * (i - 1)
      island(S, x - 3, y + 3)
      turret(S, n, { x, y })
      s.p[i] = { n = n, r = rec(target(S, { x + 12, y })) }
    end
  end,
  tick = function(ctx, t) for _, p in ipairs(ctx.state.p) do poll(p.r, t, true) end end,
  check = function(ctx)
    L = ctx.L
    local s = ctx.state
    local nl, sl, ll = hits_in(s.p[1].r, WARM, WARM + WIN)
    local na, sa_, la = hits_in(s.p[2].r, WARM, WARM + WIN)
    local Ld, Ad = sl / (WIN / 60), sa_ / (WIN / 60)
    local note = string.format("%s; laser %d hits of %s (DPS %.2f), arc %d hits of %s (DPS %.2f). " ..
      "PILOT-15: the laser beam hits once per shot (20 = 10 × damage_modifier 2, 1.5 shots/s)", tt_note(), nl, tostring(ll), Ld, na, tostring(la), Ad)
    eq("K8 arc single-target DPS (45 per shot, cooldown 120; §15)", Ad, 22.5, 0.02, 0, note)
    range("K8 arc DPS / laser DPS", Ld > 0 and Ad / Ld or -1, 0.5, 1.0, note)
  end }

-------------------------------------------------------------------------------------------------- K9 rail line
cells[#cells + 1] = { id = "K9", configs = { "base", "sa" }, check_at = 450,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    local x, y = o.x + 20, o.y + 64
    island(S, x - 3, y + 3)
    s.tu = turret(S, "magnetics-rail-cannon", { x, y })
    s.tu.insert { name = "magnetics-rail-slug", count = 1 }
    s.inl = {}
    for _, d in ipairs { 10, 16, 22, 28, 34 } do s.inl[#s.inl + 1] = { d, rec(unit(S, "behemoth-biter", { x + d, y }, "disabled")) } end
    s.off = rec(unit(S, "behemoth-biter", { x + 20, y + 3 }, "disabled"))
    s.far = rec(unit(S, "behemoth-biter", { x + 37.5, y }, "disabled"))
    s.walls = { new(S, "stone-wall", { x + 13.5, y + 0.5 }), new(S, "stone-wall", { x + 25.5, y + 0.5 }) }
  end,
  tick = function(ctx, t)
    local s = ctx.state
    for _, p in ipairs(s.inl) do poll(p[2], t, false) end
    poll(s.off, t, false); poll(s.far, t, false)
  end,
  check = function(ctx)
    L = ctx.L
    local s = ctx.state
    local note = "one rail slug; pinned+disabled behemoths (physical 12/10 %); rounds left " .. rounds(s.tu)
    for _, p in ipairs(s.inl) do
      local _, sum = hits_in(p[2], 0, 1e9)
      eq("K9 in-line behemoth at " .. p[1] .. " damage of one shot", sum, 1069.2, 0, 0.01, note)
    end
    local _, so = hits_in(s.off, 0, 1e9)
    eq("K9 behemoth 3 tiles off the line damage", so, 0, 0, 0, note)
    local _, sf = hits_in(s.far, 0, 1e9)
    eq("K9 behemoth on the line at 37.5 damage (line range 36)", sf, 0, 0, 0,
       "PILOT-8: the line starts at the muzzle (projectile_creation_distance 1.39375 of gun-turret) and reaches ~37.4 from the turret centre")
    for i, w in ipairs(s.walls) do eq("K9 own stone wall " .. i .. " on the line health", w.valid and w.health or 0, 350, 0, 0, "force = enemy on the line") end
  end }

-------------------------------------------------------------------------------------------------- K10 flux rail slug
-- An enemy superconducting wall on the line (electric 100 %, physical 8/35 %) isolates the physical part:
-- (1800 − 8) × 0.65 = 1164.8 per shot. The target gives physical + electric: test target 2400; the stand-in
-- (pinned+disabled behemoth, physical 12/10 %, no electric resistance) gives (1800 − 12) × 0.9 + 600 = 2209.2 (H_res).
cells[#cells + 1] = { id = "K10", configs = { "base", "sa" }, check_at = 900,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    local x, y = o.x + 20, o.y + 64
    island(S, x - 3, y + 3)
    s.tu = turret(S, "magnetics-rail-cannon", { x, y })
    s.tu.insert { name = "magnetics-flux-rail-slug", count = 1 }
    s.tt = prototypes.entity["magnetics-test-target"] ~= nil
    s.r = rec(s.tt and new(S, "magnetics-test-target", { x + 14, y }, "enemy") or unit(S, "behemoth-biter", { x + 14, y }, "disabled"))
    s.w = rec(new(S, "magnetics-superconducting-wall", { x + 8.5, y + 0.5 }, "enemy"))
  end,
  tick = function(ctx, t)
    local s = ctx.state
    poll(s.r, t, true); poll(s.w, t, true)
    if t == 900 then s.st = status(s.tu) end
  end,
  check = function(ctx)
    L = ctx.L
    local s = ctx.state
    local n, _, lo, hi = hits_in(s.r, 0, 900)
    local nw, _, wlo, whi = hits_in(s.w, 0, 900)
    local exp = s.tt and 2400 or 2209.2
    local note = (s.tt and "magnetics-test-target" or "stand-in behemoth (H_res)") .. string.format("; shots %d, SC wall hits %d", n, nw)
    eq("K10 flux rail slug per shot on target (1800 physical + 600 electric)", lo, exp, 0, 0.01, note)
    eq("K10 flux rail slug per shot on target (max)", hi, exp, 0, 0.01, note)
    eq("K10 physical part per shot on an enemy SC wall (electric absorbed)", wlo, 1164.8, 0, 0.01, note)
    is("K10 shots from one flux rail slug item", n, 3, note .. "; turret status after: " .. tostring(s.st))
  end }

-------------------------------------------------------------------------------------------------- K11 bonus mirroring
local K11_PH = 900
local K11_TECH = {
  { "physical-projectile-damage-1", "physical-projectile-damage-2", "physical-projectile-damage-3",
    "weapon-shooting-speed-1", "weapon-shooting-speed-2", "weapon-shooting-speed-3" },
  { "physical-projectile-damage-4", "physical-projectile-damage-5", "physical-projectile-damage-6",
    "weapon-shooting-speed-4", "weapon-shooting-speed-5", "weapon-shooting-speed-6" },
}
local MCATS = { "magnetics-slug", "magnetics-gauss", "magnetics-rail" }
local MTUR = { "magnetics-coilgun-turret", "magnetics-gauss-turret", "magnetics-rail-cannon" }
local function k11_mods(f)
  local m = { bullet = f.get_ammo_damage_modifier("bullet"), sp_bullet = f.get_gun_speed_modifier("bullet"),
              ta_gun = f.get_turret_attack_modifier("gun-turret"), cats = {}, sp = {}, ta = {} }
  for i, c in ipairs(MCATS) do m.cats[i] = f.get_ammo_damage_modifier(c); m.sp[i] = f.get_gun_speed_modifier(c) end
  for i, t in ipairs(MTUR) do m.ta[i] = f.get_turret_attack_modifier(t) end
  return m
end
cells[#cells + 1] = { id = "K11", configs = { "base", "sa" }, check_at = 3 * K11_PH,
  setup = function(ctx)
    local S, o, s = ctx.S, ctx.origin, ctx.state
    local f = game.forces["magnetics-k11"] or game.create_force("magnetics-k11")
    s.f = f.name
    s.stages = ctx.sa and 2 or 1
    local x, y = o.x + 20, o.y + 20
    local g = turret(S, "gun-turret", { x, y }, f)
    g.insert { name = "firearm-magazine", count = 100 }
    island(S, x - 3, y + 67, f)
    local c = turret(S, "magnetics-coilgun-turret", { x, y + 64 }, f)
    c.insert { name = "magnetics-ferrite-slug", count = 60 }
    s.g, s.c = g, c
    s.rg = rec(target(S, { x + 12, y }))
    s.rc = rec(target(S, { x + 12, y + 64 }))
    s.mods = {}
  end,
  tick = function(ctx, t)
    local s = ctx.state
    poll(s.rg, t, true); poll(s.rc, t, true)
    if t % 60 == 0 then
      if s.g.get_item_count("firearm-magazine") < 50 then s.g.insert { name = "firearm-magazine", count = 50 } end
      if s.c.get_item_count("magnetics-ferrite-slug") < 30 then s.c.insert { name = "magnetics-ferrite-slug", count = 30 } end
    end
    local stage = t / K11_PH
    if stage >= 1 and stage <= s.stages and t % K11_PH == 0 then
      local f = game.forces[s.f]
      for _, n in ipairs(K11_TECH[stage]) do f.technologies[n].researched = true end
      s.mods[stage] = k11_mods(f)
    end
  end,
  check = function(ctx)
    L = ctx.L
    local s = ctx.state
    for ph = 0, s.stages do
      local t0, t1 = ph * K11_PH + 120, (ph + 1) * K11_PH
      local ng, _, glo, ghi = hits_in(s.rg, t0, t1)
      local nc, _, clo, chi = hits_in(s.rc, t0, t1)
      local note = string.format("%s; force magnetics-k11, research stage %d; gun per hit %s..%s (%d hits), coilgun %s..%s (%d hits)",
        tt_note(), ph, tostring(glo), tostring(ghi), ng, tostring(clo), tostring(chi), nc)
      eq("K11 stage " .. ph .. " per-hit ratio coilgun-ferrite / gun-turret-firearm", (glo and clo) and clo / glo or -1, 4.0, 0.01, 0, note)
      L.check(G, "K11 stage " .. ph .. " per-hit values constant in the phase", glo ~= nil and clo ~= nil and math.abs(ghi - glo) < 1e-3 and math.abs(chi - clo) < 1e-3,
        { glo, ghi, clo, chi }, nil, note)
    end
    for st = 1, s.stages do
      local m = s.mods[st]
      local note = string.format("after research stage %d: bullet damage %.3f, gun speed %.3f, gun-turret attack %.3f", st, m.bullet, m.sp_bullet, m.ta_gun)
      for i, c in ipairs(MCATS) do
        eq("K11 stage " .. st .. " ammo damage modifier " .. c .. " = bullet", m.cats[i], m.bullet, 0, 1e-9, note)
        eq("K11 stage " .. st .. " gun speed modifier " .. c .. " = bullet", m.sp[i], m.sp_bullet, 0, 1e-9, note)
      end
      for i, t in ipairs(MTUR) do eq("K11 stage " .. st .. " turret attack modifier " .. t .. " = gun-turret", m.ta[i], m.ta_gun, 0, 1e-9, note) end
      if st == 1 then eq("K11 bullet ammo damage modifier after PPD-1..3", m.bullet, 0.4, 0, 1e-6, note) end
    end
  end }

-------------------------------------------------------------------------------------------------- K12 range caps
cells[#cells + 1] = { id = "K12", configs = { "base", "sa" }, slots = 0, check_at = 1,
  check = function(ctx)
    L = ctx.L
    for _, t in ipairs { { "magnetics-coilgun-turret", 20 }, { "magnetics-gauss-turret", 30 }, { "magnetics-arc-emitter", 20 }, { "magnetics-rail-cannon", 36 } } do
      local p = prototypes.entity[t[1]]
      eq("K12 turret_range " .. t[1], p and p.turret_range or "missing", t[2], 0, 0)
    end
  end }

-------------------------------------------------------------------------------------------------- T-W wave scenario
-- 20 medium + 10 big biters spawned 45 tiles north of a 3×3 turret block, `attack_area` on the block (radius 16).
-- The block sits inside a closed 2-deep wall ring (inner half-size 9, 160 walls) so the attack must go through walls.
-- Turrets are destructible; ammo is topped up every second; power from two isolated substation + EEI-meter islands.
-- Reported per variant: time to clear, wall HP lost, walls destroyed, turret losses, energy. Seed: run.py does not set
-- --map-gen-seed, so unit behaviour may differ between runs.
local TW_T = 7200
local TW_TURRETS = {
  { key = "gun", n = "gun-turret", ammo = "firearm-magazine", alt = "piercing-rounds-magazine", mag = true },
  { key = "coilgun", n = "magnetics-coilgun-turret", ammo = "magnetics-magnet-slug", mgn = true },
  { key = "gauss", n = "magnetics-gauss-turret", ammo = "magnetics-gauss-slug", mgn = true },
  { key = "laser", n = "laser-turret" },
  { key = "arc", n = "magnetics-arc-emitter", mgn = true },
}
local TW_WALLS = { { key = "stone", n = "stone-wall" }, { key = "sc", n = "magnetics-superconducting-wall" } }
local function tw_id(tk, wk) return "TW-" .. tk .. "-" .. wk end
for ti, T in ipairs(TW_TURRETS) do
  for wi, Wl in ipairs(TW_WALLS) do
    local id = tw_id(T.key, Wl.key)
    local ammo = T.alt or T.ammo
    cells[#cells + 1] = { id = id, configs = { "base", "sa" }, check_at = TW_T,
      setup = function(ctx)
        local S, o, s = ctx.S, ctx.origin, ctx.state
        local cx, cy = o.x + 64, o.y + 90
        s.tur, s.walls, s.biters = {}, {}, {}
        for i = -1, 1 do for j = -1, 1 do s.tur[#s.tur + 1] = new(S, T.n, { cx + 4 * i, cy + 4 * j }) end end
        if ammo then for _, tu in ipairs(s.tur) do tu.insert { name = ammo, count = 50 } end end
        -- two isolated islands (substation + EEI meter) inside the ring; energy = sum of both meters
        local _, ma = island(S, cx - 7, cy, "player", cx - 7, cy + 4)
        local _, mb = island(S, cx + 7, cy, "player", cx + 7, cy + 4)
        s.m = { ma, mb }
        s.me = { 0, 0 } -- energy drawn from each meter, last value while the meter exists
        for tx = cx - 11, cx + 10 do
          for ty = cy - 11, cy + 10 do
            if tx <= cx - 10 or tx >= cx + 9 or ty <= cy - 10 or ty >= cy + 9 then
              s.walls[#s.walls + 1] = new(S, Wl.n, { tx + 0.5, ty + 0.5 })
            end
          end
        end
        s.wmax = s.walls[1].max_health
        local k = 0
        for row = 0, 4 do
          for col = 0, 5 do
            k = k + 1
            local b = new(S, k <= 20 and "medium-biter" or "big-biter", { cx - 7.5 + 3 * col, cy - 51 + 3 * row }, "enemy")
            b.ai_settings.allow_destroy_when_commands_fail = false
            b.ai_settings.allow_try_return_to_spawner = false
            b.commandable.set_command { type = defines.command.attack_area, destination = { cx, cy }, radius = 16,
                                        distraction = defines.distraction.by_enemy }
            s.biters[k] = b
          end
        end
      end,
      tick = function(ctx, t)
        local s = ctx.state
        if t % 60 == 0 and ammo then
          for _, tu in ipairs(s.tur) do
            if tu.valid and tu.get_item_count(ammo) < 25 then tu.insert { name = ammo, count = 25 } end
          end
        end
        for k = 1, 2 do if s.m[k].valid then s.me[k] = 1e10 - s.m[k].energy end end
        if not s.clear then
          local alive = 0
          for _, b in ipairs(s.biters) do if b.valid then alive = alive + 1 end end
          if alive == 0 then s.clear = t end
        end
        if t == TW_T then
          local lost, gone = 0, 0
          for _, w in ipairs(s.walls) do if w.valid then lost = lost + (w.max_health - w.health) else lost = lost + s.wmax; gone = gone + 1 end end
          local tl = 0
          for _, tu in ipairs(s.tur) do if not tu.valid then tl = tl + 1 end end
          local alive = 0
          for _, b in ipairs(s.biters) do if b.valid then alive = alive + 1 end end
          for _, b in ipairs(s.biters) do if b.valid then b.destroy() end end -- survivors must not wander into other cells
          s.res = { variant = id, turret = T.n, ammo = ammo, wall = Wl.n, clear_s = s.clear and s.clear / 60 or nil, alive = alive,
                    wall_hp_lost = lost, wall_hp_total = #s.walls * s.wmax, walls_destroyed = gone, walls = #s.walls, turrets_lost = tl,
                    energy_MJ = (s.me[1] + s.me[2]) / 1e6 }
        end
      end,
      check = function(ctx)
        L = ctx.L
        local r = ctx.state.res
        local note = string.format("clear %s s, alive %d, wall HP lost %.1f (%d of %d destroyed), turrets lost %d, energy %.2f MJ",
          tostring(r.clear_s), r.alive, r.wall_hp_lost, r.walls_destroyed, r.walls, r.turrets_lost, r.energy_MJ)
        if T.mgn then
          is("T-W " .. id .. " all 30 attackers dead within 120 s", r.alive, 0, note)
        end
        if Wl.key == "sc" then
          local st = storage.cells[tw_id(T.key, "stone")]
          local sr = st and st.res
          -- §15: доля потерянной прочности стен (потеряно / суммарная прочность), а не абсолютные очки:
          -- у SC-стены прочность в 4,3 раза больше, и абсолютные потери зависят от числа укусов, а не от стойкости
          local lim = sr and (sr.wall_hp_lost / sr.wall_hp_total) / 2
          local frac = r.wall_hp_lost / r.wall_hp_total
          L.check(G, "T-W " .. T.key .. " SC-wall share of wall HP lost <= 1/2 of stone-wall share", sr ~= nil and frac <= lim + 1e-9,
            frac, lim, note .. "; stone variant lost " .. tostring(sr and sr.wall_hp_lost) .. " of " .. tostring(sr and sr.wall_hp_total))
        end
        if ti == #TW_TURRETS and wi == #TW_WALLS then
          local all = {}
          for _, T2 in ipairs(TW_TURRETS) do for _, W2 in ipairs(TW_WALLS) do
            local st = storage.cells[tw_id(T2.key, W2.key)]
            all[#all + 1] = st and st.res or { variant = tw_id(T2.key, W2.key), missing = true }
          end end
          helpers.write_file("magnetics-combat-tw.json", helpers.table_to_json({ cfg = ctx.cfg, tick = game.tick, variants = all }), false)
        end
      end }
  end
end

return cells
