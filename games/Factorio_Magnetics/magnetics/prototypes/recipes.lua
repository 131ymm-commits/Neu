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
  -- условия поверхности рецепта (только Space Age): магнитное поле (сепарация камня) и давление — «нужен воздух»
  -- (сжижение воздуха, §15.4: иначе криогенный завод Space Age делал жидкий азот из вакуума платформы)
  local sc = {}
  if d.sa_magnetic_field_min then sc[#sc + 1] = { property = "magnetic-field", min = d.sa_magnetic_field_min } end
  if d.sa_pressure_min then sc[#sc + 1] = { property = "pressure", min = d.sa_pressure_min } end
  if U.SA and #sc > 0 then r.surface_conditions = sc end
  out[#out + 1] = r
end
data:extend(out)
