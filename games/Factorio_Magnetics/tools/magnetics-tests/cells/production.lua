--[[ Production cells P1–P9 (FINAL_SPEC §11.3). Expected values are typed here from the spec text, not read from spec.py.
Method (pilot-settled, design/pilots_production.md):
  * one machine per metered group; each group = base `electric-energy-interface` (tertiary, production 0, buffer 1e10 J)
    + one substation with auto_connect = false; power = buffer delta / window (validated: AM2 155.000 kW);
  * inputs topped up and outputs drained every 30 ticks; 600-tick warm-up; window counted between two drain ticks;
  * crafts cross-check = delta(products_finished + crafting_progress) (PILOT-4: products_finished counts crafts,
    including productivity bonus crafts, not product items);
  * fluids in: LuaEntity.insert_fluid (fills up to the recipe-scaled capacity); fluids out: output fluid boxes emptied.
Recipes are unlocked by researching the Magnetics technologies (LuaTechnology.researched = true). ]]
local G = "production"
local WARM = 600
local SN = {}
for k, v in pairs(defines.entity_status) do SN[v] = k end
local function status(e) return (e and e.valid and e.status) and SN[e.status] or "nil" end

local function research(list)
  local f = game.forces.player
  for _, t in pairs(list) do f.technologies[t].researched = true end
end

-- isolated power group: tertiary EEI as a metered source, one substation that does not auto-connect
local function meter(S, x, y)
  local eei = S.create_entity { name = "electric-energy-interface", position = { x, y }, force = "player" }
  eei.power_production = 0
  eei.power_usage = 0
  eei.electric_buffer_size = 1e10
  eei.energy = 1e10
  S.create_entity { name = "substation", position = { x + 2, y }, force = "player", auto_connect = false }
  return eei
end

-- a single LuaFluidBoxPrototype, or the first of the merged list (get_prototype returns either)
local function fbproto(fb, i)
  local p = fb.get_prototype(i)
  if p.object_name == nil then p = p[1] end
  return p
end

-- top up items (4 crafts' worth) and fluid ingredients (insert_fluid fills to capacity); returns fluid inserted per name
local function topup(e)
  local r = e.get_recipe()
  local added = {}
  if not r then return added end
  local inv = e.get_inventory(defines.inventory.crafter_input)
  for _, ing in pairs(r.ingredients) do
    if ing.type == "item" then
      local need = ing.amount * 4 - inv.get_item_count(ing.name)
      if need > 0 then inv.insert { name = ing.name, count = need } end
    else
      added[ing.name] = (added[ing.name] or 0) + e.insert_fluid { name = ing.name, amount = 1000 }
    end
  end
  return added
end

-- empty the output inventory and output fluid boxes into counter[name]; remembers output fluid temperature
local function drain(e, counter)
  local out = e.get_inventory(defines.inventory.crafter_output)
  for _, it in pairs(out.get_contents()) do
    counter[it.name] = (counter[it.name] or 0) + it.count
    out.remove { name = it.name, count = it.count, quality = it.quality }
  end
  local fb = e.fluidbox
  for i = 1, #fb do
    if fbproto(fb, i).production_type == "output" and fb[i] then
      counter[fb[i].name] = (counter[fb[i].name] or 0) + fb[i].amount
      counter["temperature:" .. fb[i].name] = fb[i].temperature
      fb[i] = nil
    end
  end
end

local function copy(t) local c = {} for k, v in pairs(t) do c[k] = v end return c end

--[[ Generic crafting cell. machines: { key, name, recipe (nil = fixed), dx, dy, window (s), fuel = {item, count} } ]]
local function crafter_cell(def)
  local last = 0
  for _, m in ipairs(def.machines) do last = math.max(last, WARM + m.window * 60) end
  return {
    id = def.id, configs = def.configs, check_at = last + 1,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      research(def.research)
      s.m = {}
      for _, m in ipairs(def.machines) do
        local x, y = o.x + m.dx, o.y + m.dy
        local rec = { key = m.key, c = {}, fin = WARM + m.window * 60, fl = {} }
        if not m.fuel then rec.eei = meter(S, x, y) end
        local size = prototypes.entity[m.name].tile_width
        local px = x + 4 + size / 2
        local py = y + ((size % 2 == 1) and 0.5 or 0)
        rec.e = S.create_entity { name = m.name, position = { px, py }, force = "player", recipe = m.recipe }
        if m.fuel then rec.e.get_inventory(defines.inventory.fuel).insert { name = m.fuel[1], count = m.fuel[2] } end
        s.m[#s.m + 1] = rec
      end
    end,
    tick = function(ctx, t)
      for _, r in ipairs(ctx.state.m) do
        if t % 30 == 0 and t <= r.fin then
          drain(r.e, r.c)
          local add = topup(r.e)
          for n, a in pairs(add) do if t > WARM then r.fl[n] = (r.fl[n] or 0) + a end end
          if t == WARM or t == r.fin then
            local snap = { c = copy(r.c), pf = r.e.products_finished, cp = r.e.crafting_progress, st = status(r.e) }
            if r.eei then snap.E = r.eei.energy end
            if r.e.burner then
              local b = r.e.burner
              snap.fuel_n = b.inventory.get_item_count(); snap.rb = b.remaining_burning_fuel; snap.heat = b.heat
            end
            r[t == WARM and "s0" or "s1"] = snap
          end
        end
      end
    end,
    check = function(ctx)
      local by = {}
      for _, r in ipairs(ctx.state.m) do by[r.key] = r end
      def.check(ctx, by)
    end,
  }
end

-- window results of one machine
local function made(r, name) return (r.s1.c[name] or 0) - (r.s0.c[name] or 0) end
local function watts(r) return (r.s0.E - r.s1.E) / ((r.fin - WARM) / 60) end
local function crafts(r) return (r.s1.pf + r.s1.cp) - (r.s0.pf + r.s0.cp) end

local L -- set in each check
local function eq(name, got, exp, rel, abs, note) L.eq(G, name, got, exp, rel, abs, note) end
local function range(name, got, lo, hi, note) L.check(G, name, type(got) == "number" and got >= lo and got <= hi, got, { lo, hi }, note) end

return {
  -- P1 kiln × ferrite on coal, 60 s: 18.75 crafts -> 18–19 ferrite; coal 90 kW × 60 s / 4 MJ = 1.35 (± 1 item)
  crafter_cell { id = "P1", configs = { "base", "sa" }, research = { "magnetics-ferrite-sintering" },
    machines = { { key = "kiln", name = "magnetics-sintering-kiln", recipe = nil, dx = 4, dy = 4, window = 60, fuel = { "coal", 10 } } },
    check = function(ctx, m)
      L = ctx.L
      local k = m.kiln
      range("P1 kiln ferrite in 60 s", made(k, "magnetics-ferrite"), 18, 19)
      range("P1 kiln coal items used in 60 s", k.s0.fuel_n - k.s1.fuel_n, 1.35 - 1, 1.35 + 1, "spec: 1.35 ± 1 item")
      eq("P1 kiln fuel energy 60 s (J), 90 kW", (k.s0.fuel_n - k.s1.fuel_n) * 4e6 + (k.s0.rb - k.s1.rb) + (k.s0.heat - k.s1.heat), 90e3 * 60, 0.02, 0,
         "spec power column: 90 kW × 60 s; coal fuel value 4 MJ")
      L.check(G, "P1 kiln recipe is fixed ferrite (PILOT-16)", (k.e.get_recipe() and k.e.get_recipe().name) == "magnetics-ferrite",
              k.e.get_recipe() and k.e.get_recipe().name, "magnetics-ferrite")
      L.check(G, "P1 kiln working at window end", k.s1.st == "working", k.s1.st, "working")
    end },

  -- P2 induction furnace × ferrite and × alloy, 60 s each: 37–38 ferrite, 18–19 alloy; 248 kW ± 2 %
  crafter_cell { id = "P2", configs = { "base", "sa" }, research = { "magnetics-ferrite-sintering", "magnetics-electromagnetic-coils", "magnetics-induction-smelting" },
    machines = { { key = "fe", name = "magnetics-induction-furnace", recipe = "magnetics-ferrite", dx = 4, dy = 4, window = 60 },
                 { key = "al", name = "magnetics-induction-furnace", recipe = "magnetics-magnet-alloy", dx = 34, dy = 4, window = 60 } },
    check = function(ctx, m)
      L = ctx.L
      range("P2 induction furnace ferrite in 60 s", made(m.fe, "magnetics-ferrite"), 37, 38)
      range("P2 induction furnace alloy in 60 s", made(m.al, "magnetics-magnet-alloy"), 18, 19)
      eq("P2 induction furnace power on ferrite (W)", watts(m.fe), 248e3, 0.02)
      eq("P2 induction furnace power on alloy (W)", watts(m.al), 248e3, 0.02)
    end },

  -- P3 coil winder × coil, 60 s: 37.5 -> 37–38 coils; 155 kW ± 2 %
  crafter_cell { id = "P3", configs = { "base", "sa" }, research = { "magnetics-ferrite-sintering", "magnetics-electromagnetic-coils" },
    machines = { { key = "w", name = "magnetics-coil-winder", recipe = "magnetics-coil", dx = 4, dy = 4, window = 60 } },
    check = function(ctx, m)
      L = ctx.L
      range("P3 coil winder coils in 60 s", made(m.w, "magnetics-coil"), 37, 38)
      eq("P3 coil winder power (W)", watts(m.w), 155e3, 0.02)
    end },

  -- P4 chemical plant × ferrofluid, 60 s: 60 crafts -> 600 ± 10 ferrofluid; 217 kW (vanilla plant)
  crafter_cell { id = "P4", configs = { "base", "sa" },
    research = { "magnetics-ferrite-sintering", "magnetics-electromagnetic-coils", "magnetics-induction-smelting", "magnetics-magnetic-separation" },
    machines = { { key = "cp", name = "chemical-plant", recipe = "magnetics-ferrofluid", dx = 4, dy = 4, window = 60 } },
    check = function(ctx, m)
      L = ctx.L
      eq("P4 chemical plant ferrofluid in 60 s", made(m.cp, "magnetics-ferrofluid"), 600, 0, 10)
      eq("P4 chemical plant power (W)", watts(m.cp), 217e3, 0.02, 0, "tolerance: §11.1 power ± 1–2 %")
    end },

  -- P5 cryo chamber: air liquefaction 60 s -> 1500 ± 50 LN2; SC cable 120 s -> 24 ± 2; crystal growth 120 s -> 6 ± 1; 310 kW ± 2 %
  crafter_cell { id = "P5", configs = { "base", "sa" },
    research = { "magnetics-ferrite-sintering", "magnetics-electromagnetic-coils", "magnetics-induction-smelting",
                 "magnetics-superconductivity", "magnetics-magnetic-separation", "magnetics-superconducting-power", "magnetics-flux-energy" },
    machines = { { key = "ln2", name = "magnetics-cryo-chamber", recipe = "magnetics-liquid-nitrogen", dx = 4, dy = 4, window = 60 },
                 { key = "cab", name = "magnetics-cryo-chamber", recipe = "magnetics-superconducting-cable", dx = 34, dy = 4, window = 120 },
                 { key = "gro", name = "magnetics-cryo-chamber", recipe = "magnetics-flux-crystal-growth", dx = 64, dy = 4, window = 120 } },
    check = function(ctx, m)
      L = ctx.L
      eq("P5 cryo chamber LN2 in 60 s (air liquefaction, no ingredients)", made(m.ln2, "magnetics-liquid-nitrogen"), 1500, 0, 50)
      eq("P5 LN2 output temperature (PILOT-13)", m.ln2.s1.c["temperature:magnetics-liquid-nitrogen"], -196, 0, 0.001,
         "§2.2 default_temperature = -196")
      eq("P5 cryo chamber SC cable in 120 s", made(m.cab, "magnetics-superconducting-cable"), 24, 0, 2)
      eq("P5 cryo chamber uncharged crystals in 120 s", made(m.gro, "magnetics-flux-crystal-uncharged"), 6, 0, 1)
      eq("P5 cryo chamber power on LN2 (W)", watts(m.ln2), 310e3, 0.02)
      eq("P5 cryo chamber power on SC cable (W)", watts(m.cab), 310e3, 0.02)
      eq("P5 cryo chamber power on crystal growth (W)", watts(m.gro), 310e3, 0.02)
    end },

  -- P6 flux resonator × charging, 250 s: 10 ± 1 crystals; 125.25 MJ ± 2 % per crystal; 5.01 MW while working
  crafter_cell { id = "P6", configs = { "base", "sa" },
    research = { "magnetics-ferrite-sintering", "magnetics-electromagnetic-coils", "magnetics-induction-smelting",
                 "magnetics-superconductivity", "magnetics-magnetic-separation", "magnetics-superconducting-power", "magnetics-flux-energy" },
    machines = { { key = "r", name = "magnetics-flux-resonator", recipe = nil, dx = 4, dy = 4, window = 250 } },
    check = function(ctx, m)
      L = ctx.L
      local r = m.r
      eq("P6 resonator charged crystals in 250 s", made(r, "magnetics-flux-crystal"), 10, 0, 1)
      local E = r.s0.E - r.s1.E
      eq("P6 resonator energy per crystal (J)", E / crafts(r), 125.25e6, 0.02, 0, "window energy / delta(products_finished + crafting_progress)")
      eq("P6 resonator power while working (W)", watts(r), 5.01e6, 0.02)
      L.check(G, "P6 resonator recipe is fixed charging (PILOT-16)", (r.e.get_recipe() and r.e.get_recipe().name) == "magnetics-flux-crystal-charging",
              r.e.get_recipe() and r.e.get_recipe().name, "magnetics-flux-crystal-charging")
    end },

  -- P7 magnetic separator × stone separation, 600 s: 120 crafts -> iron ore 240 ± 2; copper ore Binomial(120, 0.5)
  -- -> [44, 76] (mean ± 3 sigma, normal approximation); ferrofluid used 600 ± 5; 258.3 kW ± 2 %
  crafter_cell { id = "P7", configs = { "base", "sa" },
    research = { "magnetics-ferrite-sintering", "magnetics-electromagnetic-coils", "magnetics-induction-smelting", "magnetics-magnetic-separation" },
    machines = { { key = "sep", name = "magnetics-magnetic-separator", recipe = "magnetics-stone-separation", dx = 4, dy = 4, window = 600 } },
    check = function(ctx, m)
      L = ctx.L
      local r = m.sep
      eq("P7 separator iron ore in 600 s", made(r, "iron-ore"), 240, 0, 2)
      range("P7 separator copper ore in 600 s", made(r, "copper-ore"), 44, 76, "Binomial(120, 0.5), mean 60 ± 3σ (σ = 5.48)")
      eq("P7 separator ferrofluid used in 600 s", r.fl["magnetics-ferrofluid"] or 0, 600, 0, 5, "sum of insert_fluid top-ups in the window (input box at capacity at both ends)")
      eq("P7 separator power (W)", watts(r), 258.3e3, 0.02)
      eq("P7 products_finished delta = crafts = iron ore / 2 (PILOT-4)", r.s1.pf - r.s0.pf, made(r, "iron-ore") / 2, 0, 1)
    end },

  -- P8 (SA only) Magnetics categories on SA machines, 60 s each
  crafter_cell { id = "P8", configs = { "sa" },
    research = { "magnetics-ferrite-sintering", "magnetics-electromagnetic-coils", "magnetics-induction-smelting",
                 "magnetics-superconductivity", "magnetics-magnetic-separation" },
    machines = { { key = "em", name = "electromagnetic-plant", recipe = "magnetics-coil", dx = 4, dy = 4, window = 60 },
                 { key = "ffe", name = "foundry", recipe = "magnetics-ferrite", dx = 34, dy = 4, window = 60 },
                 { key = "fal", name = "foundry", recipe = "magnetics-magnet-alloy", dx = 64, dy = 4, window = 60 },
                 { key = "cry", name = "cryogenic-plant", recipe = "magnetics-superconducting-cable", dx = 94, dy = 4, window = 60 } },
    check = function(ctx, m)
      L = ctx.L
      range("P8 EM plant coils in 60 s", made(m.em, "magnetics-coil"), 111, 114, "2 × 60 / 1.6 = 75 crafts × 1.5")
      range("P8 foundry ferrite in 60 s", made(m.ffe, "magnetics-ferrite"), 111, 114, "4 × 60 / 3.2 = 75 × 1.5")
      range("P8 foundry alloy in 60 s", made(m.fal, "magnetics-magnet-alloy"), 55, 57, "4 × 60 / 6.4 = 37.5 × 1.5")
      range("P8 cryogenic plant SC cable in 60 s", made(m.cry, "magnetics-superconducting-cable"), 23, 25, "2 × 60 / 10 = 12 crafts")
    end },

  -- P9 category isolation: AM2/AM3 cannot take the coil recipe; the character cannot hand-craft ferrite, coil, alloy or cable
  { id = "P9", configs = { "base", "sa" }, check_at = 2,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      research { "magnetics-ferrite-sintering", "magnetics-electromagnetic-coils", "magnetics-induction-smelting", "magnetics-superconductivity" }
      s.am = {}
      for i, am in ipairs({ "assembling-machine-2", "assembling-machine-3", "magnetics-coil-winder" }) do
        local a = S.create_entity { name = am, position = { o.x + 6.5 + 6 * i, o.y + 6.5 }, force = "player" }
        local ok, err = pcall(function() return a.set_recipe("magnetics-coil") end)
        local r = a.get_recipe()
        s.am[am] = { ok = ok, err = ok and "" or tostring(err), recipe = r and r.name or "nil" }
      end
      local ch = S.create_entity { name = "character", position = { o.x + 10, o.y + 20 }, force = "player" }
      s.ch_made = ch ~= nil
      s.hand = {}
      if ch then
        for _, it in pairs({ { "iron-ore", 50 }, { "stone", 50 }, { "copper-cable", 50 }, { "steel-plate", 20 }, { "copper-plate", 20 },
                              { "iron-plate", 20 }, { "magnetics-ferrite", 20 }, { "magnetics-magnet-alloy", 10 }, { "plastic-bar", 10 } }) do
          ch.insert { name = it[1], count = it[2] }
        end
        for _, r in pairs({ "iron-gear-wheel", "magnetics-ferrite", "magnetics-coil", "magnetics-magnet-alloy", "magnetics-superconducting-cable" }) do
          local n = ch.get_craftable_count(r)
          local ok, c = pcall(function() return ch.begin_crafting { count = 1, recipe = r, silent = true } end)
          s.hand[r] = { craftable = n, started = ok and c or 0, err = ok and "" or tostring(c) }
        end
        ch.destroy()
      end
      local cats = {}
      for c in pairs(prototypes.entity["character"].crafting_categories) do
        if c:sub(1, 10) == "magnetics-" then cats[#cats + 1] = c end
      end
      table.sort(cats)
      s.char_cats = cats
    end,
    check = function(ctx)
      local s, L2 = ctx.state, ctx.L
      for _, am in ipairs({ "assembling-machine-2", "assembling-machine-3" }) do
        local a = s.am[am]
        L2.check(G, "P9 " .. am .. " cannot take magnetics-coil", a.recipe ~= "magnetics-coil", a, "recipe ~= magnetics-coil")
      end
      local w = s.am["magnetics-coil-winder"]
      L2.check(G, "P9 control: coil winder takes magnetics-coil", w.recipe == "magnetics-coil", w, "magnetics-coil")
      L2.check(G, "P9 character created", s.ch_made, s.ch_made, true)
      local g = s.hand["iron-gear-wheel"] or {}
      L2.check(G, "P9 control: character can hand-craft iron-gear-wheel", (g.craftable or 0) > 0 and (g.started or 0) == 1, g, "craftable > 0, started 1")
      for _, r in ipairs({ "magnetics-ferrite", "magnetics-coil", "magnetics-magnet-alloy", "magnetics-superconducting-cable" }) do
        local h = s.hand[r] or {}
        L2.check(G, "P9 character cannot hand-craft " .. r, h.craftable == 0 and (h.started or 0) == 0, h, "craftable 0, started 0")
      end
      L2.check(G, "P9 character crafting categories contain no magnetics-*", #s.char_cats == 0, s.char_cats, {})
    end },
}
