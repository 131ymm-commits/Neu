-- Общие помощники стадии данных: слияние таблиц, окраска спрайтов, копия ванильной постройки.
local U = {}
U.S = require("prototypes.spec_data")
U.SA = mods["space-age"] ~= nil

local function is_list(t)
  return type(t) == "table" and (t[1] ~= nil or next(t) == nil)
end

-- Глубокое слияние: словари сливаются, списки и значения заменяются копией.
function U.merge(dst, src)
  for k, v in pairs(src) do
    if type(v) == "table" and type(dst[k]) == "table" and not is_list(v) and not is_list(dst[k]) then
      U.merge(dst[k], v)
    else
      dst[k] = table.deepcopy(v)
    end
  end
  return dst
end

-- Ключи, в которые окраска не заходит: тени, подсветка, разъёмы, отражения, иконки.
local SKIP = {
  circuit_connector = true, circuit_connector_flipped = true, water_reflection = true, frozen_patch = true,
  belt_reader = true, connector_frame_sprites = true, icon = true, icons = true, shadow = true,
  integration_patch = false,
}
-- Окрасить листья спрайтов (таблицы с filename/filenames/stripes), кроме теней, свечения, света и масок цвета силы.
function U.tint(node, tint)
  if type(node) ~= "table" then return end
  if node.draw_as_shadow or node.draw_as_glow or node.draw_as_light or node.apply_runtime_tint then return end
  if node.apply_recipe_tint or node.apply_tint then return end
  if node.filename or node.filenames or node.stripes then
    node.tint = { tint[1], tint[2], tint[3], 1 }
    return
  end
  for k, v in pairs(node) do
    if type(v) == "table" and not SKIP[k] then U.tint(v, tint) end
  end
end

-- Уменьшить спрайты (scale и shift) в f раз — для конденсатора 1×1 из графики аккумулятора 2×2.
function U.rescale(node, f)
  if type(node) ~= "table" then return end
  if node.filename or node.filenames or node.stripes then
    node.scale = (node.scale or 1) * f
    if node.shift then node.shift = { node.shift[1] * f, node.shift[2] * f } end
  end
  for _, v in pairs(node) do
    if type(v) == "table" then U.rescale(v, f) end
  end
end

function U.icon(name) return { { icon = "__magnetics__/graphics/icons/" .. name .. ".png", icon_size = 64 } } end

-- Поля SA: условия поверхности и подогрев пишутся явно (не зависят от порядка загрузки).
function U.apply_sa(e, spec)
  if U.SA then
    local cond = { { property = "magnetic-field", min = U.S.sa_magnetic_field_min } }
    for _, c in pairs(spec.cond or {}) do cond[#cond + 1] = { property = c[1], min = c[2] } end
    e.surface_conditions = cond
    e.heating_energy = spec.heat
  else
    e.surface_conditions = nil
    e.heating_energy = nil
  end
end

-- Копия ванильной постройки того же типа (или совместимого, base_type) под новым именем.
function U.make(name, spec)
  local src = data.raw[spec.base_type or spec.type][spec.base]
  assert(src, "magnetics: нет ванильного образца " .. tostring(spec.base))
  local e = table.deepcopy(src)
  e.type = spec.type
  e.name = name
  e.minable = e.minable or { mining_time = 0.2 }
  e.minable.result = name
  e.minable.results = nil
  e.hidden = nil
  e.hidden_in_factoriopedia = nil
  e.placeable_by = nil
  e.icon = nil
  e.icons = U.icon(name)
  e.next_upgrade = nil
  e.factoriopedia_simulation = nil
  e.fast_replaceable_group = spec.frg
  e.max_health = spec.hp
  e.localised_name = nil
  e.localised_description = nil
  U.merge(e, spec.set or {})
  U.apply_sa(e, spec)
  return e
end

-- Предмет постройки: копия ванильного предмета образца (ради звуков), своё имя, иконка, стак, место в меню.
function U.building_item(name, spec)
  local src = data.raw.item[spec.base] or data.raw.item["iron-chest"]
  local it = table.deepcopy(src)
  it.name = name
  it.icon = nil
  it.icons = U.icon(name)
  it.place_result = name
  it.stack_size = spec.item.stack
  it.subgroup = spec.item.subgroup
  it.order = spec.item.order
  it.hidden = nil
  it.hidden_in_factoriopedia = nil
  it.localised_name = nil
  it.localised_description = nil
  it.weight = nil
  it.default_import_location = nil
  it.spoil_ticks = nil
  return it
end

return U
