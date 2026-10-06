# Снять из игры (слот 6) дерево исследований до rocket-silo, рецепты и характеристики машин. python game_facts.py
import factorio_rcon
c = factorio_rcon.RCONClient("localhost", 27106, "factorio")
mods = c.send_command('/sc local s="" for k,v in pairs(script.active_mods) do s=s..k.."="..v.." " end rcon.print(s)').strip()
tree = c.send_command(r'''/sc local f=game.forces.player
local seen={} local order={}
local function visit(t) if seen[t.name] then return end seen[t.name]=true for _,p in pairs(t.prerequisites) do visit(p) end table.insert(order,t) end
visit(f.technologies["rocket-silo"])
local tot={} local s=""
for _,t in ipairs(order) do local ing="" local tr=t.prototype.research_trigger
 if tr then ing="ТРИГГЕР "..tr.type..":"..tostring(tr.item and (tr.item.name or tr.item) or tr.entity or "")..":"..tostring(tr.count or "")
 else for _,i in pairs(t.research_unit_ingredients) do ing=ing..i.name:gsub("-science%-pack","").."," tot[i.name]=(tot[i.name] or 0)+i.amount*t.research_unit_count end end
 s=s..t.name.." | "..(t.researched and "исслед." or "-").." | x"..t.research_unit_count.." | "..ing.." | "..t.research_unit_energy/60 .." с/ед\n" end
s=s.."ВСЕГО колб: " for k,v in pairs(tot) do s=s..k.."="..v.." " end
rcon.print(s.."\nтехнологий в цепочке: "..#order)''').strip()
open('campaign/research_tree.txt', 'w').write(f"# Дерево исследований до rocket-silo из игры. Моды: {mods}\n\n{tree}\n")
items = ["iron-plate","copper-plate","steel-plate","stone-brick","iron-gear-wheel","copper-cable","electronic-circuit","advanced-circuit","processing-unit","pipe","iron-stick","engine-unit","electric-engine-unit","plastic-bar","sulfur","sulfuric-acid","lubricant","solid-fuel","rocket-fuel","low-density-structure","concrete","battery","flying-robot-frame","rail","productivity-module","speed-module","automation-science-pack","logistic-science-pack","chemical-science-pack","military-science-pack","production-science-pack","utility-science-pack","firearm-magazine","piercing-rounds-magazine","submachine-gun","grenade","gun-turret","stone-wall","repair-pack","lab","transport-belt","inserter","burner-inserter","fast-inserter","long-handed-inserter","assembling-machine-1","assembling-machine-2","assembling-machine-3","electric-mining-drill","burner-mining-drill","stone-furnace","steel-furnace","electric-furnace","boiler","steam-engine","offshore-pump","small-electric-pole","medium-electric-pole","big-electric-pole","underground-belt","splitter","pumpjack","oil-refinery","chemical-plant","storage-tank","pipe-to-ground","pump","rocket-silo","rocket-part","basic-oil-processing","advanced-oil-processing","heavy-oil-cracking","light-oil-cracking","solid-fuel-from-light-oil","solid-fuel-from-petroleum-gas","solid-fuel-from-heavy-oil","radar","solar-panel","accumulator","iron-chest","wooden-chest"]
rec = c.send_command('/sc local s="" local R=game.forces.player.recipes for _,n in pairs({' + ','.join('"%s"' % i for i in items) + '}) do local r=R[n] if r then s=s..n.." ["..r.category..", "..r.energy.." с]: " for _,i in pairs(r.ingredients) do s=s..i.amount.." "..i.name..", " end s=s.."=> " for _,p in pairs(r.products) do s=s..(p.amount or ((p.amount_min or 0).."-"..(p.amount_max or 0))).." "..p.name..", " end s=s.."\\n" end end rcon.print(s)').strip()
ent = c.send_command(r'''/sc local s="" local P=prototypes.entity local function g(f) local ok,v=pcall(f) return ok and tostring(v) or "?" end
for _,n in pairs({"assembling-machine-1","assembling-machine-2","assembling-machine-3","stone-furnace","steel-furnace","electric-furnace","chemical-plant","oil-refinery","rocket-silo"}) do s=s..n..": скорость крафта "..g(function() return P[n].get_crafting_speed() end).."\n" end
for _,n in pairs({"burner-mining-drill","electric-mining-drill","pumpjack"}) do s=s..n..": скорость добычи "..g(function() return P[n].mining_speed end).."\n" end
for _,n in pairs({"transport-belt","fast-transport-belt","express-transport-belt"}) do s=s..n..": "..g(function() return P[n].belt_speed*480 end).." предметов/с (обе полосы)\n" end
for _,n in pairs({"burner-inserter","inserter","long-handed-inserter","fast-inserter"}) do s=s..n..": вращение "..g(function() return P[n].get_inserter_rotation_speed() end).." об/тик\n" end
s=s.."steam-engine: макс. мощность "..g(function() return P["steam-engine"].get_max_energy_production()*60/1e6 end).." МВт\nboiler: потребление "..g(function() return P["boiler"].get_max_energy_usage()*60/1e6 end).." МВт\noffshore-pump: "..g(function() return P["offshore-pump"].get_pumping_speed()*60 end).." ед/с\n"
for _,n in pairs({"small-electric-pole","medium-electric-pole","big-electric-pole","substation"}) do s=s..n..": провод "..g(function() return P[n].get_max_wire_distance() end)..", зона питания ±"..g(function() return P[n].get_supply_area_distance() end).."\n" end
s=s.."gun-turret: дальность "..g(function() return P["gun-turret"].attack_parameters.range end).."\nrocket-silo: частей на ракету "..g(function() return P["rocket-silo"].rocket_parts_required end).."\n"
local ch=storage.agent_characters and storage.agent_characters[1] local ii="" if ch and ch.valid then for _,v in pairs(ch.get_main_inventory().get_contents()) do ii=ii..v.name.."="..v.count.." " end end
s=s.."\nинвентарь персонажа на старте: "..ii.."\nвражеских сущностей: "..game.surfaces[1].count_entities_filtered{force="enemy"}
rcon.print(s)''').strip()
open('campaign/game_facts.txt', 'w').write(f"# Рецепты и машины из игры (Factorio 2.0.77, моды: {mods}), формат: имя [категория, время с]: ингредиенты => продукты\n\n{rec}\n\n# Характеристики машин\n\n{ent}\n")
print(mods); print(tree); print(ent[-600:])
