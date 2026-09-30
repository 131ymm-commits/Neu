-- 40 рецептов; «TOP-» — экспресс-конвейеры без Space Age и турбо с ним (маглев идёт после верхнего ванильного уровня).
local U = require("prototypes.util")
local S = U.S
local TOP = U.SA and "turbo" or "express"
local out = {}
local function fix(list)
  local r = {}
  for i, x in pairs(list) do
    local c = table.deepcopy(x)
    if c.name:sub(1, 4) == "TOP-" then c.name = TOP .. c.name:sub(4) end
    r[i] = c
  end
  return r
end
for name, d in pairs(S.recipes) do
  local r = { type = "recipe", name = name, category = d.category, enabled = false, energy_required = d.energy,
              ingredients = fix(d.ing), results = fix(d.res), allow_productivity = d.prod, auto_recycle = d.ar }
  if d.allow_quality == false then r.allow_quality = false end
  if d.own_icon then r.icons = U.icon("recipe-" .. name) end
  if d.subgroup then r.subgroup = d.subgroup end
  if d.order then r.order = d.order end
  if #d.res > 1 or d.own_icon then r.main_product = "" end
  if d.tint then r.crafting_machine_tint = d.tint end
  if U.SA and d.sa_magnetic_field_min then
    r.surface_conditions = { { property = "magnetic-field", min = d.sa_magnetic_field_min } }
  end
  out[#out + 1] = r
end
data:extend(out)
