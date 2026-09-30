-- Промежуточные предметы, кристаллы потока и боеприпасы (болванки катушечника и Гаусса — снаряды с пробитием,
-- рельсовые — удар по линии). Предметы построек создаёт entities.lua.
local U = require("prototypes.util")
local S = U.S
local out = {}

local SOUND_FROM = {
  ["magnetics-ferrite"] = "iron-plate", ["magnetics-coil"] = "copper-cable", ["magnetics-magnet-alloy"] = "steel-plate",
  ["magnetics-superconducting-cable"] = "copper-cable", ["magnetics-flux-crystal-uncharged"] = "uranium-fuel-cell",
  ["magnetics-flux-crystal"] = "uranium-fuel-cell",
}
local function sounds(it, src)
  local s = data.raw.item[src] or data.raw.ammo[src]
  if s then
    it.inventory_move_sound = table.deepcopy(s.inventory_move_sound)
    it.pick_sound = table.deepcopy(s.pick_sound)
    it.drop_sound = table.deepcopy(s.drop_sound)
  end
end

for name, d in pairs(S.items) do
  local it = { type = "item", name = name, icons = U.icon(name), subgroup = "magnetics-intermediate", order = d.order,
               stack_size = d.stack, auto_recycle = d.auto_recycle }
  if d.fuel_category then
    it.fuel_category = d.fuel_category
    it.fuel_value = d.fuel_value
    it.burnt_result = d.burnt_result
  end
  sounds(it, SOUND_FROM[name])
  out[#out + 1] = it
end

-- снаряды болванок: копия пушечного снаряда с ограниченным пробитием, не задевают свою силу
local function slug_projectile(name, d)
  local p = table.deepcopy(data.raw.projectile["cannon-projectile"])
  p.name = d.projectile
  p.piercing_damage = d.piercing
  p.direction_only = true
  p.force_condition = "not-same"
  p.action = { type = "direct", action_delivery = { type = "instant", target_effects = {
    { type = "damage", damage = { amount = d.damage, type = "physical" } },
    { type = "create-entity", entity_name = "explosion-hit", offsets = { { 0, 1 } }, offset_deviation = { { -0.5, -0.5 }, { 0.5, 0.5 } } },
  } } }
  p.final_action = nil
  local c = d.tint
  local tint = { tonumber(c:sub(1, 2), 16) / 255, tonumber(c:sub(3, 4), 16) / 255, tonumber(c:sub(5, 6), 16) / 255, 1 }
  p.animation = { filename = "__base__/graphics/entity/bullet/bullet.png", draw_as_glow = true, width = 3, height = 50, priority = "high", tint = tint }
  return p
end

for name, d in pairs(S.ammo) do
  local a = table.deepcopy(data.raw.ammo["piercing-rounds-magazine"])
  a.name = name
  a.icon = nil
  a.icons = U.icon(name)
  a.ammo_category = d.category
  a.magazine_size = d.magazine
  a.stack_size = d.stack
  a.subgroup = "ammo"
  a.order = d.order
  a.weight = nil
  if d.projectile then
    a.ammo_type = { target_type = "direction", action = { type = "direct", action_delivery = {
      type = "projectile", projectile = d.projectile, starting_speed = d.speed, direction_deviation = 0.02, range_deviation = 0.02,
      max_range = d.max_range, source_effects = { type = "create-explosion", entity_name = "explosion-gunshot" } } } }
    out[#out + 1] = slug_projectile(name, d)
  else
    local effects = {}
    for _, dm in pairs(d.line.damage) do
      effects[#effects + 1] = { type = "damage", damage = { amount = dm[1], type = dm[2] } }
    end
    a.ammo_type = { target_type = "direction", clamp_position = true, action = {
      type = "line", range = d.line.range, width = d.line.width, force = "enemy",
      range_effects = { type = "create-explosion", entity_name = "magnetics-rail-tracer" },
      action_delivery = { type = "instant", target_effects = effects,
                          source_effects = { type = "create-explosion", entity_name = "explosion-gunshot" } } } }
  end
  out[#out + 1] = a
end

-- трассер рельсового выстрела: единственный новый спрайт в мире (градиент, нарисован кодом)
out[#out + 1] = {
  type = "explosion", name = "magnetics-rail-tracer", flags = { "not-on-map" }, hidden = true, subgroup = "explosions",
  rotate = true, beam = true,
  animations = { { filename = "__magnetics__/graphics/entity/rail-tracer.png", priority = "extra-high", width = 64, height = 440,
                   frame_count = 8, line_length = 8, animation_speed = 0.5, draw_as_glow = true, blend_mode = "additive" } },
  light = { intensity = 1.5, size = 16, color = { r = 0.71, g = 0.55, b = 1.0 } },
}
data:extend(out)
