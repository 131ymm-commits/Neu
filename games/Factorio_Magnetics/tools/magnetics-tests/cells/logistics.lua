--[[ Mining and logistics cells M1–M4, L1–L4 (FINAL_SPEC §11.4). Expected values are typed here from the spec text.
Method (pilot-settled, design/pilots_production.md):
  * drills: 7×7 ore patch, 1 000 000 per tile; an iron chest at drop_position, counted and cleared every 30 ticks;
    each drill on its own metered power group (base tertiary EEI + substation, auto_connect = false);
  * belts: every tick insert_at_back on both lines of the first belt; on the last belt remove every item whose
    position is in the last half tile (DetailedItemOnLine.stack.clear()); validated on express = 45.0 items/s;
  * UG "distance d" = difference of the input and output tile positions (express, max_distance 9, connects at 9, not 10);
  * 600-tick warm-up, 3600-tick window. ]]
local G = "logistics"
local WARM, WIN = 600, 3600
local EAST, NORTH = defines.direction.east, defines.direction.north
local SN = {}
for k, v in pairs(defines.entity_status) do SN[v] = k end
local function status(e) return (e and e.valid and e.status) and SN[e.status] or "nil" end

local function meter(S, x, y)
  local eei = S.create_entity { name = "electric-energy-interface", position = { x, y }, force = "player" }
  eei.power_production = 0
  eei.power_usage = 0
  eei.electric_buffer_size = 1e10
  eei.energy = 1e10
  S.create_entity { name = "substation", position = { x + 2, y }, force = "player", auto_connect = false }
  return eei
end

-- belts ------------------------------------------------------------------------------------------------
local function belts(S, name, x0, y, n)
  local b = {}
  for i = 0, n - 1 do
    b[#b + 1] = S.create_entity { name = name, position = { x0 + i + 0.5, y + 0.5 }, direction = EAST, force = "player" }
  end
  return b
end
local function feed(belt)
  for li = 1, 2 do
    local l = belt.get_transport_line(li)
    if l.can_insert_at_back() then l.insert_at_back { name = "iron-plate", count = 1 } end
  end
end
local function sink(belt)
  local n = 0
  for li = 1, 2 do
    local l = belt.get_transport_line(li)
    for _, d in pairs(l.get_detailed_contents()) do
      if d.position >= l.line_length - 0.5 then n = n + d.stack.count; d.stack.clear() end
    end
  end
  return n
end
-- one throughput probe: first belt fed, last belts drained, items counted in the window
local function probe(first, lasts)
  return { first = first, lasts = lasts, n = {} }
end
local function probe_tick(p, t)
  feed(p.first)
  for i, b in ipairs(p.lasts) do
    local k = sink(b)
    if t > WARM and t <= WARM + WIN then p.n[i] = (p.n[i] or 0) + k end
  end
end
local function rate(p, i) return (p.n[i] or 0) / (WIN / 60) end

-- drills -----------------------------------------------------------------------------------------------
local function ore_patch(S, ore, cx, cy)
  for dx = -3, 3 do
    for dy = -3, 3 do
      S.create_entity { name = ore, position = { cx + dx, cy + dy }, amount = 1000000 }
    end
  end
end
local function drill(S, name, ore, x, y)
  local eei = meter(S, x, y)
  local cx, cy = x + 6.5, y + 0.5
  ore_patch(S, ore, cx, cy)
  local d = S.create_entity { name = name, position = { cx, cy }, direction = NORTH, force = "player" }
  local chest = S.create_entity { name = "iron-chest", position = d.drop_position, force = "player" }
  return { d = d, chest = chest, eei = eei, n = 0, bad = 0 }
end
local function drill_tick(r, t)
  if t % 30 == 0 then
    local inv = r.chest.get_inventory(defines.inventory.chest)
    if t > WARM and t <= WARM + WIN then r.n = r.n + inv.get_item_count() end
    inv.clear()
  end
  if t == WARM then r.E0 = r.eei.energy end
  if t == WARM + WIN then r.E1 = r.eei.energy end
end

local function top() return script.active_mods["space-age"] and "turbo" or "express" end

return {
  -- M1 magnetic drill vs EMD on iron ore, 60 s: 45 ± 1 vs 30 ± 1, ratio 1.50 ± 0.05; M2 mining area 5×5; M4 150 kW ± 2 %
  { id = "M1", configs = { "base", "sa" }, check_at = WARM + WIN + 1,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      s.mag = drill(S, "magnetics-magnetic-drill", "iron-ore", o.x + 4, o.y + 10)
      s.emd = drill(S, "electric-mining-drill", "iron-ore", o.x + 34, o.y + 10)
    end,
    tick = function(ctx, t) drill_tick(ctx.state.mag, t); drill_tick(ctx.state.emd, t) end,
    check = function(ctx)
      local s, L = ctx.state, ctx.L
      L.eq(G, "M1 magnetic drill iron ore in 60 s", s.mag.n, 45, 0, 1)
      L.eq(G, "M1 control: electric mining drill iron ore in 60 s", s.emd.n, 30, 0, 1)
      L.eq(G, "M1 ratio magnetic / electric drill", s.emd.n > 0 and s.mag.n / s.emd.n or -1, 1.5, 0, 0.05)
      local a = s.mag.d.mining_area
      L.eq(G, "M2 magnetic drill mining_area width (5×5)", a.right_bottom.x - a.left_top.x, 4.977, 0, 0.005, "≈ 4.977 as [PL] (2 × 2.49 in 1/256 steps)")
      L.eq(G, "M2 magnetic drill mining_area height (5×5)", a.right_bottom.y - a.left_top.y, 4.977, 0, 0.005)
      L.eq(G, "M4 magnetic drill power (W)", (s.mag.E0 - s.mag.E1) / (WIN / 60), 150e3, 0.02, 0, "no drain on drills [PL]")
    end },

  -- M3 uranium ore + sulfuric acid through the input fluid box, 60 s: > 0 ore; never missing_required_fluid
  { id = "M3", configs = { "base", "sa" }, check_at = WARM + WIN + 1,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      s.u = drill(S, "magnetics-magnetic-drill", "uranium-ore", o.x + 4, o.y + 10)
      s.u.d.fluidbox[1] = { name = "sulfuric-acid", amount = 1000 }
      s.st = {}
    end,
    tick = function(ctx, t)
      local s = ctx.state
      drill_tick(s.u, t)
      if t % 30 == 0 then s.u.d.fluidbox[1] = { name = "sulfuric-acid", amount = 1000 } end
      local k = status(s.u.d)
      s.st[k] = (s.st[k] or 0) + 1
    end,
    check = function(ctx)
      local s, L = ctx.state, ctx.L
      L.check(G, "M3 magnetic drill mines uranium ore with acid (60 s)", s.u.n > 0, s.u.n, "> 0")
      L.check(G, "M3 never missing_required_fluid", (s.st["missing_required_fluid"] or 0) == 0, s.st, "0 ticks missing_required_fluid")
    end },

  -- L1 40 maglev belts: 75.0 ± 1.875 items/s; control express 45.0 (B) / turbo 60.0 (SA)
  { id = "L1", configs = { "base", "sa" }, check_at = WARM + WIN + 1,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      local m = belts(S, "magnetics-maglev-transport-belt", o.x + 4, o.y + 4, 40)
      local c = belts(S, top() .. "-transport-belt", o.x + 4, o.y + 10, 40)
      s.pm = probe(m[1], { m[40] }); s.pc = probe(c[1], { c[40] })
    end,
    tick = function(ctx, t) probe_tick(ctx.state.pm, t); probe_tick(ctx.state.pc, t) end,
    check = function(ctx)
      local s, L = ctx.state, ctx.L
      L.eq(G, "L1 maglev belt throughput (items/s)", rate(s.pm, 1), 75.0, 0, 1.875)
      L.eq(G, "L1 control: " .. top() .. " belt throughput (items/s)", rate(s.pc, 1), ctx.sa and 60.0 or 45.0, 0, 1.875)
    end },

  -- L2 maglev UG pair at distance 13 connects (75 ± 1.875 items/s); at 14 it does not (throughput 0)
  { id = "L2", configs = { "base", "sa" }, check_at = WARM + WIN + 1,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      s.ok = {}
      for i, d in ipairs({ 13, 14 }) do
        local y = o.y + 4 + 8 * (i - 1)
        local a = belts(S, "magnetics-maglev-transport-belt", o.x + 4, y, 10)
        local ui = S.create_entity { name = "magnetics-maglev-underground-belt", position = { o.x + 14.5, y + 0.5 }, direction = EAST, type = "input", force = "player" }
        local uo = S.create_entity { name = "magnetics-maglev-underground-belt", position = { o.x + 14.5 + d, y + 0.5 }, direction = EAST, type = "output", force = "player" }
        local b = belts(S, "magnetics-maglev-transport-belt", o.x + 15 + d, y, 10)
        s["p" .. d] = probe(a[1], { b[10] })
        s["pair" .. d] = (ui.neighbours ~= nil and ui.neighbours == uo)
      end
    end,
    tick = function(ctx, t) probe_tick(ctx.state.p13, t); probe_tick(ctx.state.p14, t) end,
    check = function(ctx)
      local s, L = ctx.state, ctx.L
      L.check(G, "L2 maglev UG pair connects at distance 13", s.pair13, s.pair13, true)
      L.eq(G, "L2 maglev UG distance 13 throughput (items/s)", rate(s.p13, 1), 75.0, 0, 1.875)
      L.check(G, "L2 maglev UG pair does not connect at distance 14", not s.pair14, s.pair14, false)
      L.eq(G, "L2 maglev UG distance 14 throughput (items/s)", rate(s.p14, 1), 0, 0, 0)
    end },

  -- L3 maglev splitter fed 75/s on one input: each output 37.5 ± 1.875, total 75 ± 1.875
  { id = "L3", configs = { "base", "sa" }, check_at = WARM + WIN + 1,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      local x, y = o.x + 20, o.y + 10
      local a = belts(S, "magnetics-maglev-transport-belt", x - 10, y, 10)
      s.sp = S.create_entity { name = "magnetics-maglev-splitter", position = { x + 0.5, y + 1 }, direction = EAST, force = "player" }
      local b1 = belts(S, "magnetics-maglev-transport-belt", x + 1, y, 10)
      local b2 = belts(S, "magnetics-maglev-transport-belt", x + 1, y + 1, 10)
      s.p = probe(a[1], { b1[10], b2[10] })
    end,
    tick = function(ctx, t) probe_tick(ctx.state.p, t) end,
    check = function(ctx)
      local s, L = ctx.state, ctx.L
      L.check(G, "L3 splitter created", s.sp ~= nil and s.sp.valid, s.sp ~= nil, true)
      L.eq(G, "L3 splitter output 1 (items/s)", rate(s.p, 1), 37.5, 0, 1.875)
      L.eq(G, "L3 splitter output 2 (items/s)", rate(s.p, 2), 37.5, 0, 1.875)
      L.eq(G, "L3 splitter total (items/s)", rate(s.p, 1) + rate(s.p, 2), 75.0, 0, 1.875)
    end },

  -- L4 upgrade links: TOP-* -> magnetics-maglev-*; SA: express-* -> turbo-* unchanged; runtime order_upgrade (PILOT-25)
  { id = "L4", configs = { "base", "sa" }, check_at = 2,
    setup = function(ctx)
      local S, o, s = ctx.S, ctx.origin, ctx.state
      local T = top()
      s.static = {}
      for _, k in ipairs({ "transport-belt", "underground-belt", "splitter" }) do
        local n = prototypes.entity[T .. "-" .. k].next_upgrade
        s.static[k] = n and n.name or "nil"
        if ctx.sa then
          local e = prototypes.entity["express-" .. k].next_upgrade
          s.static["express-" .. k] = e and e.name or "nil"
        end
      end
      -- runtime 1: LuaEntity.order_upgrade
      local b = S.create_entity { name = T .. "-transport-belt", position = { o.x + 10.5, o.y + 10.5 }, direction = EAST, force = "player" }
      local ok, ret = pcall(function() return b.order_upgrade { force = "player", target = "magnetics-maglev-transport-belt" } end)
      local tg = b.get_upgrade_target()
      s.rt1 = { ok = ok, ret = ok and ret or tostring(ret), marked = b.to_be_upgraded(), target = tg and tg.name or "nil" }
      -- runtime 2: an upgrade-planner item mapping TOP belt -> maglev belt, applied with LuaSurface.upgrade_area
      local b2 = S.create_entity { name = T .. "-transport-belt", position = { o.x + 20.5, o.y + 10.5 }, direction = EAST, force = "player" }
      local inv = game.create_inventory(1)
      inv.insert { name = "upgrade-planner", count = 1 }
      local stack = inv[1]
      stack.set_mapper(1, "from", { type = "entity", name = T .. "-transport-belt" })
      stack.set_mapper(1, "to", { type = "entity", name = "magnetics-maglev-transport-belt" })
      local ok2, err2 = pcall(function()
        S.upgrade_area { area = { { o.x + 19, o.y + 9 }, { o.x + 22, o.y + 12 } }, force = "player", item = stack }
      end)
      inv.destroy()
      local tg2 = b2.get_upgrade_target()
      s.rt2 = { ok = ok2, err = ok2 and "" or tostring(err2), marked = b2.to_be_upgraded(), target = tg2 and tg2.name or "nil" }
    end,
    check = function(ctx)
      local s, L = ctx.state, ctx.L
      local T = top()
      for _, k in ipairs({ "transport-belt", "underground-belt", "splitter" }) do
        L.check(G, "L4 " .. T .. "-" .. k .. ".next_upgrade", s.static[k] == "magnetics-maglev-" .. k, s.static[k], "magnetics-maglev-" .. k)
        if ctx.sa then
          L.check(G, "L4 SA: express-" .. k .. ".next_upgrade unchanged", s.static["express-" .. k] == "turbo-" .. k, s.static["express-" .. k], "turbo-" .. k)
        end
      end
      local want = { ok = true, ret = true, marked = true, target = "magnetics-maglev-transport-belt" }
      L.check(G, "L4 runtime order_upgrade of one " .. T .. " belt (PILOT-25)",
              s.rt1.ok and s.rt1.ret == true and s.rt1.marked and s.rt1.target == want.target, s.rt1, want)
      L.check(G, "L4 runtime upgrade planner (upgrade_area) on one " .. T .. " belt (PILOT-25)",
              s.rt2.ok and s.rt2.marked and s.rt2.target == want.target, s.rt2, { ok = true, marked = true, target = want.target })
    end },
}
