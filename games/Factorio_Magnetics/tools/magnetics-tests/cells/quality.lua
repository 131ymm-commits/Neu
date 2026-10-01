--[[ Quality cells Q1–Q5 (FINAL_SPEC §11.8) and the legendary part of E6 (§11.5), configs BQ and SA
(`configs = {"bq"}` = bq, bqe and sa in the harness). Expected values are typed from the spec text (§11.8, §11.5, §7.5),
not read from spec.py. Method (pilot-settled, design/pilots_power.md):
  * entities are created with `create_entity{quality = "legendary"}`;
  * storage charged from `magnetics-test-source`; consumers metered by a vanilla EEI (buffer delta);
  * generator energy per fuel item = test-load energy between two fuel-take events / items (formula-free);
  * the quality roll only yields qualities the force has unlocked (pilot: 0 quality items of 206 crafts at 12.4 %
    until `LuaForce.unlock_quality`), so Q4 unlocks all qualities for the player force before its dynamic check.
Every electric group is an island: its substation is created with `auto_connect = false`. ]]
local G = "quality"
local WARM = 600

local L
local function eq(name, got, exp, rel, abs, note) L.eq(G, name, got, exp, rel, abs, note) end
local function is(name, got, exp, note) L.check(G, name, got == exp, got, exp, note) end

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
local function load_at(S, x, y)
  local l = S.create_entity { name = "magnetics-test-load", position = { x, y }, force = "player" }
  l.power_usage = 0
  l.electric_buffer_size = 1e10
  l.energy = 0
  return l
end
local function meter(S, x, y)
  local eei = S.create_entity { name = "electric-energy-interface", position = { x, y }, force = "player" }
  eei.power_production = 0
  eei.power_usage = 0
  eei.electric_buffer_size = 1e10
  eei.energy = 1e10
  return eei
end
local function research(list) for _, t in pairs(list) do game.forces.player.technologies[t].researched = true end end

-- resonator (given quality) on a vanilla-EEI meter; energy per crystal over a 100 s window after warm-up
local function resonator_new(S, x, y, q)
  local r = { m = meter(S, x, y) }
  pole(S, x + 2, y)
  r.e = S.create_entity { name = "magnetics-flux-resonator", position = { x + 6.5, y + 0.5 }, force = "player", quality = q }
  return r
end
local function resonator_tick(r, t)
  if t % 30 == 0 then
    local inv = r.e.get_inventory(defines.inventory.crafter_input)
    if inv.get_item_count("magnetics-flux-crystal-uncharged") < 4 then inv.insert { name = "magnetics-flux-crystal-uncharged", count = 4 } end
    r.e.get_inventory(defines.inventory.crafter_output).clear()
  end
  if t == WARM then r.E0 = r.m.energy; r.c0 = r.e.products_finished + r.e.crafting_progress end
  if t == WARM + 6000 then r.E1 = r.m.energy; r.c1 = r.e.products_finished + r.e.crafting_progress end
end
local function resonator_per_crystal(r)
  local c = (r.c1 or 0) - (r.c0 or 0)
  return c > 0 and (r.E0 - r.E1) / c or 0, c
end

return {
  -- Q1 legendary SC accumulator buffer = 20 MJ × (1 + 5) = 120 MJ; vanilla legendary accumulator as a control (5 MJ × 6)
  { id = "Q1", configs = { "bq" }, check_at = 6600,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      s.a = {}
      for i, a in ipairs({ { "magnetics-superconducting-accumulator", 120e6 }, { "accumulator", 30e6 } }) do
        local x, y = o.x + 10 + 30 * (i - 1), o.y + 10
        local e = S.create_entity { name = a[1], position = { x, y }, force = "player", quality = "legendary" }
        src_at(S, x + 4, y)
        pole(S, x + 2, y + 4)
        s.a[i] = { e = e, name = a[1], exp = a[2] }
      end
    end,
    check = function(ctx)
      L = ctx.L
      for _, a in ipairs(ctx.state.a) do
        local tag = a.name == "accumulator" and "Q1 control: legendary vanilla accumulator" or "Q1 legendary SC accumulator"
        is(tag .. " quality", a.e.quality.name, "legendary")
        eq(tag .. " electric_buffer_size (J)", a.e.electric_buffer_size, a.exp, 1e-6)
        eq(tag .. " energy after charging from the test source (J)", a.e.energy, a.exp, 0.01, 0, "charged 6600 ticks")
      end
    end },

  -- Q2 legendary pylon: wire 48 + 2 × 5 = 58 (≤ 64), supply 2 + 5 = 7
  { id = "Q2", configs = { "bq" }, check_at = 5,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      s.w = {}
      local y = o.y + 10
      for _, d in ipairs({ 58, 58.5 }) do
        local a = S.create_entity { name = "magnetics-superconducting-pylon", position = { o.x + 4, y }, force = "player", auto_connect = false, quality = "legendary" }
        local b = S.create_entity { name = "magnetics-superconducting-pylon", position = { o.x + 4 + d, y }, force = "player", auto_connect = false,
                                    snap_to_grid = false, quality = "legendary" }
        local ca = a.get_wire_connector(defines.wire_connector_id.pole_copper, true)
        local cb = b.get_wire_connector(defines.wire_connector_id.pole_copper, true)
        local can = ca.can_wire_reach(cb)
        local con = ca.connect_to(cb, true)
        s.w[#s.w + 1] = { d = d, dist = b.position.x - a.position.x, can = can, con = con, q = a.quality.name .. "/" .. b.quality.name }
        y = y + 6
      end
      local px, py = o.x + 60, o.y + 80
      s.py = S.create_entity { name = "magnetics-superconducting-pylon", position = { px, py }, force = "player", auto_connect = false, quality = "legendary" }
      src_at(S, px - 1, py - 2)
      s.lamps = {}
      for _, off in ipairs({ 7.0, 8.0 }) do
        s.lamps[#s.lamps + 1] = { off = off, e = S.create_entity { name = "small-lamp", position = { px + off, py }, force = "player", snap_to_grid = false } }
      end
    end,
    check = function(ctx)
      L = ctx.L
      local s = ctx.state
      local p = prototypes.entity["magnetics-superconducting-pylon"]
      eq("Q2 legendary pylon get_max_wire_distance", p.get_max_wire_distance("legendary"), 58, 0, 1e-9)
      L.check(G, "Q2 legendary pylon wire reach ≤ 64", p.get_max_wire_distance("legendary") <= 64, p.get_max_wire_distance("legendary"), "≤ 64")
      eq("Q2 legendary pylon get_supply_area_distance", p.get_supply_area_distance("legendary"), 7, 0, 1e-9)
      for _, w in ipairs(s.w) do
        local tag = "Q2 legendary pylons at " .. w.d
        eq(tag .. ": placed distance", w.dist, w.d, 0, 1e-9, w.q)
        is(tag .. ": can_wire_reach", w.can, w.d == 58)
        is(tag .. ": connect_to(target, reach_check = true)", w.con, w.d == 58)
      end
      for _, lp in ipairs(s.lamps) do
        local e = lp.e
        local powered = e.is_connected_to_electric_network() and e.electric_network_id == s.py.electric_network_id
        is(string.format("Q2 legendary pylon supply: 1x1 lamp %.1f tiles off-centre powered", lp.off), powered, lp.off == 7.0,
           string.format("lamp at dx = %.3f", e.position.x - s.py.position.x))
      end
    end },

  -- Q3 resonator get_crafting_speed(q) = 1.0 for every quality; legendary resonator energy per crystal as E6 (125.25 MJ ± 2 %)
  { id = "Q3", configs = { "bq" }, check_at = WARM + 6000,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      s.r = resonator_new(S, o.x + 10, o.y + 10, "legendary")
    end,
    tick = function(ctx, t) resonator_tick(ctx.state.r, t) end,
    check = function(ctx)
      L = ctx.L
      local r = ctx.state.r
      local p = prototypes.entity["magnetics-flux-resonator"]
      for q in pairs(prototypes.quality) do
        eq("Q3 resonator get_crafting_speed(" .. q .. ")", p.get_crafting_speed(q), 1.0, 0, 1e-9)
      end
      is("Q3 resonator entity quality", r.e.quality.name, "legendary")
      eq("Q3 legendary resonator entity crafting_speed", r.e.crafting_speed, 1.0, 0, 1e-9)
      local per, c = resonator_per_crystal(r)
      eq("Q3 legendary resonator energy per crystal (J)", per, 125.25e6, 0.02, 0, string.format("%.3f crafts in 100 s", c))
    end },

  -- Q4 no quality crystal: growth and charging allow no quality; no recycling recipe has a flux crystal; dynamic check with a control
  { id = "Q4", configs = { "bq" }, check_at = 18000,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      research { "magnetics-ferrite-sintering", "magnetics-electromagnetic-coils", "magnetics-induction-smelting",
                 "magnetics-superconductivity", "magnetics-magnetic-separation", "magnetics-superconducting-power", "magnetics-flux-energy" }
      for q in pairs(prototypes.quality) do game.forces.player.unlock_quality(q) end
      s.c = {}
      for i, r in ipairs({ "magnetics-flux-crystal-growth", "magnetics-superconducting-cable" }) do
        local x, y = o.x + 10 + 30 * (i - 1), o.y + 10
        src_at(S, x, y)
        pole(S, x + 2, y + 4)
        local e = S.create_entity { name = "magnetics-cryo-chamber", position = { x + 6.5, y + 0.5 }, force = "player", quality = "legendary", recipe = r }
        local mi = e.get_inventory(defines.inventory.crafter_modules)
        s.c[i] = { r = r, e = e, out = {}, slots = #mi, mods = mi.insert { name = "quality-module-3", quality = "legendary", count = #mi } }
      end
      -- modules first, then the growth recipe: are the quality modules kept?
      local x, y = o.x + 10, o.y + 40
      src_at(S, x, y)
      pole(S, x + 2, y + 4)
      local e = S.create_entity { name = "magnetics-cryo-chamber", position = { x + 6.5, y + 0.5 }, force = "player", quality = "legendary" }
      local mi = e.get_inventory(defines.inventory.crafter_modules)
      local before = mi.insert { name = "quality-module-3", quality = "legendary", count = #mi }
      e.set_recipe("magnetics-flux-crystal-growth")
      s.late = { before = before, after = mi.get_item_count() }
    end,
    tick = function(ctx, t)
      if t % 30 ~= 0 then return end
      for _, c in pairs(ctx.state.c) do
        local e = c.e
        local inv = e.get_inventory(defines.inventory.crafter_input)
        for _, ing in pairs(e.get_recipe().ingredients) do
          if ing.type == "item" then
            if inv.get_item_count(ing.name) < ing.amount * 4 then inv.insert { name = ing.name, count = ing.amount * 4 } end
          else
            e.insert_fluid { name = ing.name, amount = 1000 }
          end
        end
        local out = e.get_inventory(defines.inventory.crafter_output)
        for _, it in pairs(out.get_contents()) do c.out[it.quality] = (c.out[it.quality] or 0) + it.count end
        out.clear()
      end
    end,
    check = function(ctx)
      L = ctx.L
      local s = ctx.state
      for _, r in ipairs({ "magnetics-flux-crystal-growth", "magnetics-flux-crystal-charging" }) do
        local ae = prototypes.recipe[r].allowed_effects or {}
        is("Q4 " .. r .. " allows no quality effect (allow_quality = false)", ae.quality, false)
      end
      local bad = {}
      for n, r in pairs(prototypes.recipe) do
        if r.category == "recycling" then
          for _, x in pairs(r.ingredients) do if x.name == "magnetics-flux-crystal" or x.name == "magnetics-flux-crystal-uncharged" then bad[#bad + 1] = n end end
          for _, x in pairs(r.products) do if x.name == "magnetics-flux-crystal" or x.name == "magnetics-flux-crystal-uncharged" then bad[#bad + 1] = n end end
        end
      end
      is("Q4 recycling recipes with a flux crystal as ingredient or result", #bad, 0, table.concat(bad, ", "))
      local g, cab = s.c[1], s.c[2]
      local function split(c)
        local n, hi = 0, 0
        for q, k in pairs(c.out) do n = n + k; if q ~= "normal" then hi = hi + k end end
        return n, hi
      end
      local gn, ghi = split(g)
      local cn, chi = split(cab)
      local note = string.format("legendary cryo chamber, 300 s; legendary quality-module-3 accepted: %d of %d slots", g.mods, g.slots)
      L.check(G, "Q4 crystal growth (legendary chamber offered 3 quality modules): crystals made", gn > 0, gn, "> 0", note)
      is("Q4 crystal growth (legendary chamber offered 3 quality modules): non-normal crystals", ghi, 0, note)
      is("Q4 growth chamber accepts quality modules (recipe set first)", g.mods, 0, "the engine enforces allow_quality = false at the module slots")
      is("Q4 growth chamber keeps quality modules (modules first, then set_recipe)", s.late.after, 0,
         string.format("%d inserted before set_recipe", s.late.before))
      L.check(G, "Q4 control: SC cable in the same set-up yields quality items", chi > 0 and cab.mods == cab.slots,
              { made = cn, quality = chi, modules = cab.mods }, "> 0 quality items, all slots filled", "validates that quality modules act in this machine")
    end },

  -- Q5 legendary coil winder speed / normal = legendary AM2 speed / normal
  { id = "Q5", configs = { "bq" }, check_at = 2,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      s.e = {}
      for i, a in ipairs({ { "magnetics-coil-winder", "legendary" }, { "magnetics-coil-winder", "normal" },
                           { "assembling-machine-2", "legendary" }, { "assembling-machine-2", "normal" } }) do
        s.e[a[1] .. ":" .. a[2]] = S.create_entity { name = a[1], position = { o.x + 6.5 + 6 * i, o.y + 10.5 }, force = "player", quality = a[2] }
      end
    end,
    check = function(ctx)
      L = ctx.L
      local e = ctx.state.e
      local pw, pa = prototypes.entity["magnetics-coil-winder"], prototypes.entity["assembling-machine-2"]
      local rw = pw.get_crafting_speed("legendary") / pw.get_crafting_speed("normal")
      local ra = pa.get_crafting_speed("legendary") / pa.get_crafting_speed("normal")
      eq("Q5 winder legendary/normal speed = AM2 legendary/normal (prototype)", rw, ra, 1e-9, 0, string.format("winder %.4f, AM2 %.4f", rw, ra))
      local ew = e["magnetics-coil-winder:legendary"].crafting_speed / e["magnetics-coil-winder:normal"].crafting_speed
      local ea = e["assembling-machine-2:legendary"].crafting_speed / e["assembling-machine-2:normal"].crafting_speed
      eq("Q5 winder legendary/normal speed = AM2 legendary/normal (entities)", ew, ea, 1e-9, 0, string.format("winder %.4f, AM2 %.4f", ew, ea))
    end },

  -- E6 (BQ, SA part): legendary resonator 125.25 MJ ± 2 % per crystal; legendary dynamo 100 MJ ± 2 % per crystal [PILOT-23];
  -- any round trip ≥ 1.0 is a release blocker
  { id = "E6Q", configs = { "bq" }, check_at = WARM + 6000,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      s.g = S.create_entity { name = "magnetics-flux-dynamo", position = { o.x + 10.5, o.y + 10.5 }, force = "player", quality = "legendary" }
      s.l = load_at(S, o.x + 16, o.y + 10)
      pole(S, o.x + 13, o.y + 14)
      s.g.get_inventory(defines.inventory.fuel).insert { name = "magnetics-flux-crystal", count = 20 }
      s.last = 20; s.takes = {}
      s.r = resonator_new(S, o.x + 10, o.y + 50, "legendary")
    end,
    tick = function(ctx, t)
      local s = ctx.state
      local n = s.g.get_inventory(defines.inventory.fuel).get_item_count("magnetics-flux-crystal")
      if n < s.last then s.takes[#s.takes + 1] = { t = t, E = s.l.energy } end
      s.last = n
      resonator_tick(s.r, t)
    end,
    check = function(ctx)
      L = ctx.L
      local s = ctx.state
      local k = #s.takes
      local out = k >= 3 and (s.takes[k].E - s.takes[2].E) / (k - 2) or 0
      local inn, c = resonator_per_crystal(s.r)
      is("E6Q dynamo quality", s.g.quality.name, "legendary")
      eq("E6Q legendary resonator energy per crystal (J)", inn, 125.25e6, 0.02, 0, string.format("%.3f crafts", c))
      eq("E6Q legendary dynamo energy per crystal (J) (PILOT-23)", out, 100e6, 0.02, 0,
         string.format("%d whole crystals between fuel takes; ticks per crystal %.1f", k - 2, k >= 3 and (s.takes[k].t - s.takes[2].t) / (k - 2) or 0))
      local ratio = inn > 0 and out / inn or 0
      eq("E6Q legendary round trip", ratio, 0.798, 0, 0.016)
      L.check(G, "E6Q legendary round trip < 1.0 (release blocker)", ratio > 0 and ratio < 1.0, ratio, "< 1.0")
    end },
}
