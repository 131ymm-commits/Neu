"""PLAY-01: справочник игры для общего блока голов — из прототипов Factorio 2.0.77 (правда от кода, не по памяти).
   python3 kb.py <сейв> → kb.json, kb.md"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import game

ITEMS = ['wooden-chest', 'iron-chest', 'stone-furnace', 'burner-mining-drill', 'iron-gear-wheel', 'iron-stick', 'copper-cable',
         'electronic-circuit', 'transport-belt', 'underground-belt', 'splitter', 'burner-inserter', 'inserter', 'long-handed-inserter',
         'pipe', 'pipe-to-ground', 'offshore-pump', 'boiler', 'steam-engine', 'small-electric-pole', 'electric-mining-drill', 'lab',
         'automation-science-pack', 'logistic-science-pack', 'assembling-machine-1', 'assembling-machine-2', 'stone-brick', 'steel-plate',
         'iron-plate', 'copper-plate', 'firearm-magazine']
TECHS = ['steam-power', 'electronics', 'automation-science-pack', 'automation', 'logistics', 'logistic-science-pack', 'steel-processing',
         'electric-energy-distribution-1', 'automation-2', 'logistics-2', 'fast-inserter']

LUA = r'''
local items, techs = helpers.json_to_table(HEXITEMS), helpers.json_to_table(HEXTECHS)
local f = game.forces.player
local unlock = {}
local want = {}
for _, n in pairs(items) do want[n] = true end
for tn, t in pairs(prototypes.technology) do
  for _, e in pairs(t.effects or {}) do if e.type == "unlock-recipe" then unlock[e.recipe] = tn end end
end
local have = {}
for _, tn in pairs(techs) do have[tn] = true end
for r, tn in pairs(unlock) do if want[r] and not have[tn] then have[tn] = true; techs[#techs + 1] = tn end end
local R = {}
for _, n in pairs(items) do
  local r = prototypes.recipe[n]
  if r then
    local ing, pr = {}, {}
    for _, i in pairs(r.ingredients) do ing[#ing + 1] = { i.name, i.amount } end
    for _, p in pairs(r.products) do pr[#pr + 1] = { p.name, p.amount } end
    R[#R + 1] = { name = n, ingredients = ing, products = pr, seconds = r.energy, category = r.category,
                  enabled_at_start = f.recipes[n].enabled, unlocked_by = unlock[n], hand = (r.category == "crafting") }
  end
end
local E = {}
for _, n in pairs(items) do
  local it = prototypes.item[n]
  local e = it and it.place_result
  if e then
    local function g(k) local ok, v = pcall(function() return e[k] end); if ok then return v end end
    local function m(k, ...) local a = { ... }; local ok, v = pcall(function() return e[k](table.unpack(a)) end); if ok then return v end end
    local d = { item = n, entity = e.name, type = e.type, size = e.tile_width .. "x" .. e.tile_height }
    d.mining_speed = g("mining_speed")
    d.crafting_speed = m("get_crafting_speed")
    local mx = m("get_max_energy_usage")
    if mx and mx > 0 then d.energy_kw = mx * 60 / 1000 end
    if g("burner_prototype") then d.fuel = "burner" elseif g("electric_energy_source_prototype") then d.fuel = "electric" end
    local bs = g("belt_speed"); if bs then d.belt_items_per_s = bs * 60 * 8 end
    local sa = m("get_supply_area_distance"); if sa then d.supply_area = 2 * sa .. "x" .. 2 * sa; d.wire_reach = m("get_max_wire_distance") end
    local mp = m("get_max_energy_production"); if mp and mp > 0 then d.max_output_kw = mp * 60 / 1000 end
    local r = g("mining_drill_radius"); if r then d.mining_area = 2 * r .. "x" .. 2 * r end
    local rs = m("get_inserter_rotation_speed"); if rs then d.rotation_turns_per_s = rs * 60 end
    local pu = g("pumping_speed"); if pu then d.pump_per_s = pu * 60 end
    E[#E + 1] = d
  end
end
local F = {}
for _, n in pairs({ "wood", "coal", "solid-fuel" }) do F[#F + 1] = { n, prototypes.item[n].fuel_value / 1e6 } end
local T = {}
for _, tn in pairs(techs) do
  local t = prototypes.technology[tn]
  if t then
    local pre, rec = {}, {}
    for k in pairs(t.prerequisites) do pre[#pre + 1] = k end
    for _, e in pairs(t.effects or {}) do if e.type == "unlock-recipe" then rec[#rec + 1] = e.recipe end end
    local d = { name = tn, prerequisites = pre, unlocks = rec }
    if t.research_trigger then
      local tr = t.research_trigger
      d.trigger = tr.type .. " " .. tostring(tr.item and (tr.item.name or tr.item) or tr.entity or "") .. (tr.count and (" x" .. tr.count) or "")
    else
      local packs = {}
      for _, i in pairs(t.research_unit_ingredients) do packs[#packs + 1] = i.name end
      d.units, d.packs, d.unit_seconds = t.research_unit_count, packs, t.research_unit_energy / 60
    end
    T[#T + 1] = d
  end
end
local ch = prototypes.entity["character"]
rcon.print(helpers.table_to_json({ recipes = R, entities = E, fuels = F, techs = T,
  character = { running_speed = ch.running_speed, mining_speed = ch.mining_speed, build_distance = ch.build_distance,
                reach_distance = ch.reach_distance, resource_reach = ch.reach_resource_distance, inventory_slots = ch.get_inventory_size(defines.inventory.character_main) },
  resource_mining_time = { ["iron-ore"] = prototypes.entity["iron-ore"].mineable_properties.mining_time, coal = prototypes.entity["coal"].mineable_properties.mining_time,
    stone = prototypes.entity["stone"].mineable_properties.mining_time, ["copper-ore"] = prototypes.entity["copper-ore"].mineable_properties.mining_time } }))
'''

def query(save):
    import shutil, tempfile
    w = tempfile.mkdtemp(prefix='kb_')
    srv = game.Server(w, save, next(game.PORTS)).start()
    try:
        lua = LUA.replace('HEXITEMS', json.dumps(json.dumps(ITEMS))).replace('HEXTECHS', json.dumps(json.dumps(TECHS)))
        out = srv.r.raw('/sc ' + ' '.join(l.strip() for l in lua.strip().splitlines()))
    finally:
        srv.stop(); shutil.rmtree(w, ignore_errors=True)
    try: return json.loads(out)
    except ValueError: raise RuntimeError(out[:2000])

if __name__ == '__main__':
    d = query(sys.argv[1])
    json.dump(d, open(os.path.join(HERE, 'kb.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(d, ensure_ascii=False)[:6000])
