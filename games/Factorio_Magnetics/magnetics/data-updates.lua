-- Связи улучшения (next_upgrade) с ванилью и внутри Magnetics; категории рецептов у машин Space Age.
-- Space Age перезаписывает списки категорий своих машин в своём data.lua, поэтому вставка — здесь, на стадии updates.
local SA = mods["space-age"] ~= nil
local TOP = SA and "turbo" or "express"

local links = {
  { "wall", "stone-wall", "magnetics-ferrite-wall" },
  { "wall", "magnetics-ferrite-wall", "magnetics-magnet-wall" },
  { "wall", "magnetics-magnet-wall", "magnetics-superconducting-wall" },
  { "gate", "gate", "magnetics-magnet-gate" },
  { "gate", "magnetics-magnet-gate", "magnetics-superconducting-gate" },
  { "mining-drill", "electric-mining-drill", "magnetics-magnetic-drill" },
  { "accumulator", "accumulator", "magnetics-superconducting-accumulator" },
  { "electric-pole", "big-electric-pole", "magnetics-superconducting-pylon" },
  { "transport-belt", TOP .. "-transport-belt", "magnetics-maglev-transport-belt" },
  { "underground-belt", TOP .. "-underground-belt", "magnetics-maglev-underground-belt" },
  { "splitter", TOP .. "-splitter", "magnetics-maglev-splitter" },
}
for _, l in pairs(links) do
  local e = data.raw[l[1]][l[2]]
  if e and data.raw[l[1]][l[3]] then e.next_upgrade = l[3] end
end

if SA then
  local inserts = {
    { "electromagnetic-plant", { "magnetics-winding" } },
    { "cryogenic-plant", { "magnetics-cryogenics" } },
    { "foundry", { "magnetics-sintering", "magnetics-induction" } },
  }
  for _, ins in pairs(inserts) do
    local m = data.raw["assembling-machine"][ins[1]]
    if m then
      for _, c in pairs(ins[2]) do table.insert(m.crafting_categories, c) end
    end
  end
end
