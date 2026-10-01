--[[ Power cells E1–E9 (FINAL_SPEC §11.5). Expected values are typed here from the spec text (§11.5, §4.4, §8.3),
not read from spec.py. Method (pilot-settled, design/pilots_power.md):
  * sources: `magnetics-test-source` (primary-output, test mod), a vanilla EEI (tertiary) cannot charge a storage;
  * generator output: primary = `pole.electric_network_statistics.get_flow_count{category = "output",
    precision_index = five_seconds, count = false}` × 60 (§11.1); cross-check = energy delta of a
    `magnetics-test-load` (secondary-input, power_usage 0, 10 GJ buffer, i.e. demand far above the spec's 10/20 MW);
  * consumer power: vanilla EEI as a meter (tertiary, production 0, buffer delta), as the production cells;
  * pollution: `LuaSurface.pollution_statistics.get_input_count(<entity name>)` (PILOT-18: emissions are counted as input,
    per prototype name and per surface), so the E4 coal MHD runs alone on its own surface;
  * surface properties and daytime are surface-wide, so E7, E8 and E9 run on their own small lab surfaces
    (`magnetics-power-E7/E8/E9…`); changing the shared lab would break other modules' cells (e.g. P7 in SA).
Every electric group is an island: its substation is created with `auto_connect = false`. ]]
local G = "power"
local WARM = 600

local SN = {}
for k, v in pairs(defines.entity_status) do SN[v] = k end
local function status(e) return (e and e.valid and e.status) and SN[e.status] or "nil" end

local L -- set in each check
local function eq(name, got, exp, rel, abs, note) L.eq(G, name, got, exp, rel, abs, note) end
local function range(name, got, lo, hi, note) L.check(G, name, type(got) == "number" and got >= lo and got <= hi, got, { lo, hi }, note) end
local function is(name, got, exp, note) L.check(G, name, got == exp, got, exp, note) end

-- a private lab surface (used only where the test changes surface-wide state)
local function own_surface(name)
  local S = game.surfaces[name] or game.create_surface(name, { width = 256, height = 256 })
  S.generate_with_lab_tiles = true
  S.request_to_generate_chunks({ 0, 0 }, 2)
  S.force_generate_chunk_requests()
  return S
end

local function pole(S, x, y)
  return S.create_entity { name = "substation", position = { x, y }, force = "player", auto_connect = false }
end
local function src_at(S, x, y)
  local s = S.create_entity { name = "magnetics-test-source", position = { x, y }, force = "player" }
  s.power_production = 1e10 / 60
  s.electric_buffer_size = 1e10
  s.energy = 1e10
  return s
end
-- test load; usage/buffer in J per tick (nil = pure meter: usage 0, 10 GJ buffer)
local function load_at(S, x, y, usage, buffer)
  local l = S.create_entity { name = "magnetics-test-load", position = { x, y }, force = "player" }
  l.power_usage = usage or 0
  l.electric_buffer_size = buffer or 1e10
  l.energy = 0
  return l
end
-- vanilla EEI as a consumer meter (buffer delta = energy drawn)
local function meter(S, x, y)
  local eei = S.create_entity { name = "electric-energy-interface", position = { x, y }, force = "player" }
  eei.power_production = 0
  eei.power_usage = 0
  eei.electric_buffer_size = 1e10
  eei.energy = 1e10
  return eei
end
local function out_flow_W(p, name)
  return p.electric_network_statistics.get_flow_count { name = name, category = "output",
    precision_index = defines.flow_precision_index.five_seconds, count = false } * 60
end

--[[ E1/E2: storage charged from the test source, then (source removed) discharged into a test load with demand 5 MW. ]]
local function storage_cell(def)
  local switch = def.ticks + 100
  local stop = switch + def.ticks + 100
  return { id = def.id, configs = { "base", "sa" }, check_at = stop,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      local x, y = o.x + 20, o.y + 20
      s.acc = S.create_entity { name = def.name, position = { x + def.off, y + def.off }, force = "player" }
      s.src = src_at(S, x + 5, y)
      s.pole = pole(S, x + 2, y + 4)
      s.lx, s.ly = x + 5, y
      s.e = { s.acc.energy }            -- s.e[t + 1] = energy at relative tick t
    end,
    tick = function(ctx, t)
      local s = ctx.state
      if t == switch then
        s.src.destroy()
        s.load = load_at(ctx.S, s.lx, s.ly, 5e6 / 60, 5e6 / 60)   -- demand 5 MW (one tick of usage per tick)
      end
      s.e[t + 1] = s.acc.energy
    end,
    check = function(ctx)
      L = ctx.L
      local s = ctx.state
      local full = s.e[switch + 1]
      local t_full
      for t = 0, switch do if s.e[t + 1] >= full * (1 - 1e-9) then t_full = t; break end end
      local n, sum = 0, 0
      for t = switch + 1, stop do
        local d = s.e[t + 1] - s.e[t]
        if d < -1 then n = n + 1; sum = sum - d end
      end
      local tail = 0
      for t = stop - 19, stop do tail = tail + math.abs(s.e[t + 1] - s.e[t]) end
      local cap, flow = def.cap, def.flow
      eq(def.id .. " " .. def.label .. " energy when full (J)", full, cap, 0.01, 0, "starts empty (" .. s.e[1] .. " J)")
      eq(def.id .. " " .. def.label .. " ticks to full", t_full, def.ticks, 0, 2, "buffer / input flow")
      eq(def.id .. " " .. def.label .. " discharge power into 5 MW demand (W)", n > 0 and sum / n * 60 or 0, flow, 0.01)
      eq(def.id .. " " .. def.label .. " discharge duration (ticks)", n, def.ticks, 0, 2)
      eq(def.id .. " " .. def.label .. " then 0: energy change over the last 20 ticks (J)", tail, 0, 0, 1)
      eq(def.id .. " " .. def.label .. " empty at the end (J)", s.e[stop + 1], 0, 0, 1)
    end }
end

--[[ generator cell helpers: fuel top-up with an insert counter, window snapshots ]]
local function gen_new(S, name, x, y, fuel, keep)
  local r = { name = name, fuel = fuel, keep = keep, ins = 0 }
  r.g = S.create_entity { name = name, position = { x + 0.5, y + 0.5 }, force = "player" }
  r.l = load_at(S, x + 6, y)
  r.p = pole(S, x + 3, y + 4)
  return r
end
local function gen_topup(r)
  local inv = r.g.get_inventory(defines.inventory.fuel)
  local n = inv.get_item_count(r.fuel)
  if n < r.keep then r.ins = r.ins + inv.insert { name = r.fuel, count = r.keep - n } end
end
local function gen_snap(r, pollution)
  local b = r.g.burner
  local sn = { n = r.g.get_inventory(defines.inventory.fuel).get_item_count(r.fuel), ins = r.ins, E = r.l.energy,
               rbf = b.remaining_burning_fuel, flow = out_flow_W(r.p, r.name), st = status(r.g) }
  if pollution then sn.pol = r.g.surface.pollution_statistics.get_input_count(r.name) end
  return sn
end

return {
  -- E1 coil capacitor: full at 1.00 MJ ± 1 % after 60 ± 2 ticks; discharge 1.00 MW ± 1 % for 60 ± 2 ticks, then 0
  storage_cell { id = "E1", name = "magnetics-coil-capacitor", label = "coil capacitor", off = 0.5, cap = 1e6, flow = 1e6, ticks = 60 },
  -- E2 SC accumulator: 20.0 MJ ± 1 % after 1000 ± 2 ticks (1.2 MW); discharge 1.20 MW ± 1 %
  storage_cell { id = "E2", name = "magnetics-superconducting-accumulator", label = "SC accumulator", off = 0, cap = 20e6, flow = 1.2e6, ticks = 1000 },

  -- E3 pylon reach 48.0 connects, 48.5 does not; big pole 32 / 32.5; supply 2: 1×1 consumer at 2.0 powered, 3.0 not
  { id = "E3", configs = { "base", "sa" }, check_at = 5,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      s.w = {}
      local y = o.y + 10
      for _, c in ipairs({ { "magnetics-superconducting-pylon", 48 }, { "magnetics-superconducting-pylon", 48.5 },
                           { "big-electric-pole", 32 }, { "big-electric-pole", 32.5 } }) do
        local a = S.create_entity { name = c[1], position = { o.x + 4, y }, force = "player", auto_connect = false }
        local b = S.create_entity { name = c[1], position = { o.x + 4 + c[2], y }, force = "player", auto_connect = false, snap_to_grid = false }
        local ca = a.get_wire_connector(defines.wire_connector_id.pole_copper, true)
        local cb = b.get_wire_connector(defines.wire_connector_id.pole_copper, true)
        local can = ca.can_wire_reach(cb)
        local con = ca.connect_to(cb, true)
        s.w[#s.w + 1] = { name = c[1], d = c[2], dist = b.position.x - a.position.x, can = can, con = con, linked = ca.is_connected_to(cb) }
        y = y + 6
      end
      -- supply area: pylon at (px, py), a test source inside its area, small lamps at +2.0 and +3.0 tiles (exact positions)
      local px, py = o.x + 60, o.y + 80
      s.py = S.create_entity { name = "magnetics-superconducting-pylon", position = { px, py }, force = "player", auto_connect = false }
      src_at(S, px - 1, py - 2)
      s.lamps = {}
      for _, off in ipairs({ 2.0, 3.0 }) do
        s.lamps[#s.lamps + 1] = { off = off, e = S.create_entity { name = "small-lamp", position = { px + off, py }, force = "player", snap_to_grid = false } }
      end
    end,
    check = function(ctx)
      L = ctx.L
      local s = ctx.state
      local exp = { [48] = true, [48.5] = false, [32] = true, [32.5] = false }
      for _, w in ipairs(s.w) do
        local tag = "E3 " .. w.name .. " at " .. w.d
        eq(tag .. ": placed distance", w.dist, w.d, 0, 1e-9)
        is(tag .. ": can_wire_reach", w.can, exp[w.d])
        is(tag .. ": connect_to(target, reach_check = true)", w.con, exp[w.d])
        is(tag .. ": connected", w.linked, exp[w.d])
      end
      for _, lp in ipairs(s.lamps) do
        local e = lp.e
        local powered = e.is_connected_to_electric_network() and e.electric_network_id == s.py.electric_network_id
        is(string.format("E3 pylon supply: 1x1 lamp %.1f tiles off-centre powered", lp.off), powered, lp.off == 2.0,
           string.format("lamp at dx = %.3f", e.position.x - s.py.position.x))
      end
    end },

  -- E4 MHD, 60 s: 5.40 MW ± 1 %; coal 90 ± 2; solid fuel 30 ± 1; pollution statistics 100/min ± 2 % [PILOT-18]
  { id = "E4", configs = { "base", "sa" }, check_at = WARM + 3600,
    setup = function(ctx)
      local s = ctx.state
      local S4 = own_surface("magnetics-power-E4")   -- alone on its surface: pollution statistics are per surface and per name
      s.coal = gen_new(S4, "magnetics-mhd-generator", 0, 0, "coal", 40)
      s.sf = gen_new(ctx.S, "magnetics-mhd-generator", ctx.origin.x + 10, ctx.origin.y + 10, "solid-fuel", 20)
      gen_topup(s.coal); gen_topup(s.sf)
    end,
    tick = function(ctx, t)
      local s = ctx.state
      if t % 30 == 0 then gen_topup(s.coal); gen_topup(s.sf) end
      if t == WARM then s.c0 = gen_snap(s.coal, true); s.f0 = gen_snap(s.sf) end
      if t == WARM + 3600 then s.c1 = gen_snap(s.coal, true); s.f1 = gen_snap(s.sf) end
    end,
    check = function(ctx)
      L = ctx.L
      local s = ctx.state
      local c0, c1, f0, f1 = s.c0, s.c1, s.f0, s.f1
      eq("E4 MHD (coal) output, electric network statistics (W)", c1.flow, 5.4e6, 0.01, 0, "five_seconds flow × 60, §11.1")
      eq("E4 MHD (coal) output, test-load energy / 60 s (W)", (c1.E - c0.E) / 60, 5.4e6, 0.01)
      eq("E4 MHD coal burnt in 60 s (items)", (c1.ins - c0.ins) - (c1.n - c0.n), 90, 0, 2, "6 MW × 60 s / 4 MJ")
      eq("E4 MHD (solid fuel) output, electric network statistics (W)", f1.flow, 5.4e6, 0.01)
      eq("E4 MHD solid fuel burnt in 60 s (items)", (f1.ins - f0.ins) - (f1.n - f0.n), 30, 0, 1, "6 MW × 60 s / 12 MJ")
      eq("E4 MHD pollution statistics per minute (PILOT-18)", c1.pol - c0.pol, 100, 0.02, 0,
         "delta of pollution_statistics.get_input_count('magnetics-mhd-generator') over 60 s on the MHD's own surface")
      is("E4 MHD working at window end", c1.st, "working")
    end },

  -- E5 flux dynamo, 10 charged crystals, 60 s: 10.0 MW ± 1 %; 6 ± 1 crystals burnt; the same count uncharged in the burnt slot; 0 pollution
  { id = "E5", configs = { "base", "sa" }, check_at = 3600,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      s.r = gen_new(S, "magnetics-flux-dynamo", o.x + 10, o.y + 10, "magnetics-flux-crystal", 0)
      s.r.g.get_inventory(defines.inventory.fuel).insert { name = "magnetics-flux-crystal", count = 10 }
      s.pol0 = S.pollution_statistics.get_input_count("magnetics-flux-dynamo")
      s.E0 = s.r.l.energy
    end,
    check = function(ctx)
      L = ctx.L
      local s, r = ctx.state, ctx.state.r
      local b = r.g.burner
      local left = r.g.get_inventory(defines.inventory.fuel).get_item_count("magnetics-flux-crystal")
      local taken = 10 - left
      local burning = (b.currently_burning ~= nil and b.remaining_burning_fuel > 0) and 1 or 0
      local burnt = taken - b.remaining_burning_fuel / 100e6          -- crystals' worth of fuel used (fuel value 100 MJ, §8.3)
      local slot = b.burnt_result_inventory.get_item_count("magnetics-flux-crystal-uncharged")
      eq("E5 flux dynamo output, test-load energy / 60 s (W)", (r.l.energy - s.E0) / 60, 10e6, 0.01)
      eq("E5 flux dynamo output, electric network statistics (W)", out_flow_W(r.p, "magnetics-flux-dynamo"), 10e6, 0.01)
      eq("E5 crystals burnt in 60 s", burnt, 6, 0, 1, string.format("taken %d, remaining in the burning one %.0f J", taken, b.remaining_burning_fuel))
      is("E5 uncharged crystals in the burnt slot = crystals fully burnt", slot, taken - burning, "burnt slot " .. slot)
      eq("E5 flux dynamo pollution (statistics, 60 s)", ctx.S.pollution_statistics.get_input_count("magnetics-flux-dynamo") - s.pol0, 0, 0, 1e-9)
    end },

  -- E6 flux round trip = dynamo energy out per crystal / resonator energy in per crystal = 0.798 ± 0.016; ≥ 1.0 is a release blocker
  { id = "E6", configs = { "base", "sa" }, check_at = WARM + 6000,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      s.r = gen_new(S, "magnetics-flux-dynamo", o.x + 10, o.y + 10, "magnetics-flux-crystal", 0)
      s.r.g.get_inventory(defines.inventory.fuel).insert { name = "magnetics-flux-crystal", count = 10 }
      s.last = 10; s.takes = {}
      s.m = meter(S, o.x + 10, o.y + 40)
      pole(S, o.x + 12, o.y + 40)
      s.res = S.create_entity { name = "magnetics-flux-resonator", position = { o.x + 16.5, o.y + 40.5 }, force = "player" }
    end,
    tick = function(ctx, t)
      local s = ctx.state
      local n = s.r.g.get_inventory(defines.inventory.fuel).get_item_count("magnetics-flux-crystal")
      if n < s.last then s.takes[#s.takes + 1] = { t = t, E = s.r.l.energy } end
      s.last = n
      if t % 30 == 0 then
        local inv = s.res.get_inventory(defines.inventory.crafter_input)
        if inv.get_item_count("magnetics-flux-crystal-uncharged") < 4 then inv.insert { name = "magnetics-flux-crystal-uncharged", count = 4 } end
        s.res.get_inventory(defines.inventory.crafter_output).clear()
      end
      if t == WARM then s.m0 = { E = s.m.energy, c = s.res.products_finished + s.res.crafting_progress } end
      if t == WARM + 6000 then s.m1 = { E = s.m.energy, c = s.res.products_finished + s.res.crafting_progress } end
    end,
    check = function(ctx)
      L = ctx.L
      local s = ctx.state
      local k = #s.takes
      -- whole crystals between the 2nd and the last take (the 1st take starts at setup)
      local out = k >= 3 and (s.takes[k].E - s.takes[2].E) / (k - 2) or 0
      local crafts = s.m1.c - s.m0.c
      local inn = crafts > 0 and (s.m0.E - s.m1.E) / crafts or 0
      local ratio = inn > 0 and out / inn or 0
      local note = string.format("out %.4g J per crystal over %d crystals; in %.6g J per crystal over %.3f crafts", out, k - 2, inn, crafts)
      eq("E6 flux round trip (dynamo out / resonator in per crystal)", ratio, 0.798, 0, 0.016, note)
      L.check(G, "E6 flux round trip < 1.0 (release blocker)", ratio > 0 and ratio < 1.0, ratio, "< 1.0", note)
    end },

  -- E7 geomagnetic coil: output ∝ magnetic-field, identical day and night (± 1 %). PILOT-12 picked H2 (v / default 90):
  -- 0 / 2.22 / 5.56 / 20.0 / 22.0 kW for v = 0 / 10 / 25 / 90 / 99. (H1, v / 100 = 0 / 2 / 5 / 18 / 19.8 kW, was rejected by the pilot.)
  { id = "E7", configs = { "base", "sa" }, check_at = 10 * 120 + 1,
    setup = function(ctx)
      local S = own_surface("magnetics-power-E7")
      local s = ctx.state
      S.always_day = false
      S.freeze_daytime = true
      S.daytime = 0
      s.S = S
      s.coil = S.create_entity { name = "magnetics-geomagnetic-coil", position = { 0.5, 0.5 }, force = "player" }
      s.l = load_at(S, 4, 0)
      pole(S, 2, 4)
      s.seq = {}
      for _, v in ipairs({ 0, 10, 25, 90, 99 }) do for _, d in ipairs({ 0, 0.5 }) do s.seq[#s.seq + 1] = { v = v, day = d } end end
      s.res = {}
    end,
    tick = function(ctx, t)
      local s = ctx.state
      local ph, k = math.floor((t - 1) / 120) + 1, (t - 1) % 120   -- phases start at t = 1 (the first tick call)
      local e = s.seq[ph]
      if not e then return end
      if k == 0 then s.S.set_property("magnetic-field", e.v); s.S.daytime = e.day end
      if k == 59 then s.E0 = s.l.energy end
      if k == 119 then s.res[ph] = { v = e.v, day = e.day, W = (s.l.energy - s.E0), mf = s.S.get_property("magnetic-field"), dt = s.S.daytime } end
    end,
    check = function(ctx)
      L = ctx.L
      local s = ctx.state
      local H2 = { [0] = 0, [10] = 2222.22, [25] = 5555.56, [90] = 20000, [99] = 22000 }
      local by = {}
      for _, r in pairs(s.res) do by[r.v .. "/" .. r.day] = r end
      for _, v in ipairs({ 0, 10, 25, 90, 99 }) do
        local d, n = by[v .. "/0"], by[v .. "/0.5"]
        local note = string.format("measured at magnetic-field %s, daytime %s; H1 (v/100) would be %.0f W", d and d.mf, d and d.dt, 200 * v)
        eq("E7 geomagnetic coil at magnetic-field " .. v .. ", noon (W)", d and d.W, H2[v], 0.01, 1, note)
        eq("E7 geomagnetic coil at magnetic-field " .. v .. ", midnight (W)", n and n.W, H2[v], 0.01, 1,
           string.format("daytime %s", n and n.dt))
        eq("E7 geomagnetic coil at magnetic-field " .. v .. ", midnight minus noon (W)", (n and n.W or 0) - (d and d.W or 1e9), 0, 0,
           math.max(0.01 * H2[v], 1))
      end
    end },

  -- E8 (SA) placement: all 26 Magnetics entities false at magnetic-field 0, true at 10 (pressure 1000); kiln and MHD false at pressure 0
  { id = "E8", configs = { "sa" }, check_at = 2,
    setup = function(ctx)
      local S = own_surface("magnetics-power-E8")
      -- ore under the probe position: a mining drill cannot be placed manually without a resource in its area
      for dx = -1, 1 do for dy = -1, 1 do S.create_entity { name = "iron-ore", position = { 10.5 + dx, 10.5 + dy }, amount = 1000 } end end
    end,
    check = function(ctx)
      L = ctx.L
      local S = game.surfaces["magnetics-power-E8"]
      local names = {
        "magnetics-sintering-kiln", "magnetics-induction-furnace", "magnetics-coil-winder", "magnetics-cryo-chamber",
        "magnetics-flux-resonator", "magnetics-magnetic-separator", "magnetics-magnetic-drill",
        "magnetics-maglev-transport-belt", "magnetics-maglev-underground-belt", "magnetics-maglev-splitter",
        "magnetics-coil-capacitor", "magnetics-superconducting-accumulator", "magnetics-superconducting-pylon",
        "magnetics-mhd-generator", "magnetics-flux-dynamo", "magnetics-geomagnetic-coil",
        "magnetics-ferrite-wall", "magnetics-magnet-wall", "magnetics-superconducting-wall", "magnetics-magnet-gate",
        "magnetics-superconducting-gate", "magnetics-mend-coil",
        "magnetics-coilgun-turret", "magnetics-gauss-turret", "magnetics-arc-emitter", "magnetics-rail-cannon" }
      L.check(G, "E8 entity list has 26 names", #names == 26, #names, 26, nil, "harness")   -- самопроверка списка стенда (§15.4)
      -- build_check_type: "manual" (a player building). PILOT: "script"/"script_ghost" ignore surface conditions.
      local function can(n)
        if not prototypes.entity[n] then return "missing prototype" end
        return S.can_place_entity { name = n, position = { 10.5, 10.5 }, force = "player", build_check_type = defines.build_check_type.manual }
      end
      local function probe(mf, p)
        S.set_property("magnetic-field", mf); S.set_property("pressure", p)
        local r = {}
        for _, n in ipairs(names) do r[n] = can(n) end
        r["stone-furnace"] = can("stone-furnace"); r["solar-panel"] = can("solar-panel"); r["electric-mining-drill"] = can("electric-mining-drill")
        return r
      end
      local mf0, mf10, p0 = probe(0, 1000), probe(10, 1000), probe(90, 0)
      S.set_property("magnetic-field", 90); S.set_property("pressure", 1000)
      for _, n in ipairs(names) do
        is("E8 " .. n .. " can be placed at magnetic-field 0", mf0[n], false)
        is("E8 " .. n .. " can be placed at magnetic-field 10", mf10[n], true)
      end
      is("E8 magnetics-sintering-kiln can be placed at pressure 0", p0["magnetics-sintering-kiln"], false)
      is("E8 magnetics-mhd-generator can be placed at pressure 0", p0["magnetics-mhd-generator"], false)
      is("E8 control: solar-panel placeable at magnetic-field 0", mf0["solar-panel"], true, "vanilla, no magnetic-field condition")
      is("E8 control: stone-furnace not placeable at pressure 0", p0["stone-furnace"], false, "SA stone furnace: pressure ≥ 10")
      is("E8 control: electric-mining-drill placeable on the probe ore at magnetic-field 0", mf0["electric-mining-drill"], true)
    end },

  -- E9 (SA) stone separation: crafts at magnetic-field 90; blocked (no crafts in 60 s) at 25
  { id = "E9", configs = { "sa" }, check_at = 3600,
    setup = function(ctx)
      local s = ctx.state
      for _, t in pairs({ "magnetics-ferrite-sintering", "magnetics-electromagnetic-coils", "magnetics-induction-smelting", "magnetics-magnetic-separation" }) do
        game.forces.player.technologies[t].researched = true
      end
      s.sep = {}
      for _, mf in ipairs({ 90, 25 }) do
        local S = own_surface("magnetics-power-E9-mf" .. mf)
        S.set_property("magnetic-field", mf)
        local e = S.create_entity { name = "magnetics-magnetic-separator", position = { 0.5, 0.5 }, force = "player", recipe = "magnetics-stone-separation" }
        src_at(S, 5, 0)
        pole(S, 3, 4)
        s.sep[#s.sep + 1] = { mf = mf, e = e, pf0 = e.products_finished, r0 = e.get_recipe() and e.get_recipe().name or "nil" }
      end
    end,
    tick = function(ctx, t)
      if t % 30 ~= 0 then return end
      for _, x in pairs(ctx.state.sep) do
        local e = x.e
        local inv = e.get_inventory(defines.inventory.crafter_input)
        if inv.get_item_count("stone") < 40 then inv.insert { name = "stone", count = 40 - inv.get_item_count("stone") } end
        e.insert_fluid { name = "magnetics-ferrofluid", amount = 1000 }
        e.get_inventory(defines.inventory.crafter_output).clear()
      end
    end,
    check = function(ctx)
      L = ctx.L
      for _, x in pairs(ctx.state.sep) do
        local crafts = x.e.products_finished - x.pf0
        local note = string.format("recipe at creation %s, status %s", x.r0, status(x.e))
        if x.mf == 90 then
          L.check(G, "E9 separator crafts stone separation at magnetic-field 90", crafts > 0, crafts, "> 0", note)
        else
          is("E9 separator at magnetic-field 25: crafts in 60 s", crafts, 0, note)
        end
      end
    end },
}
