-- 26 построек Magnetics. Каждая — копия ванильной постройки того же вида (печи — сборочные машины на графике печей),
-- окрашенная по листьям спрайтов, с числами из spec_data.lua. Разрядник: мгновенный урон + цепь, лучи только для вида.
local U = require("prototypes.util")
local S = U.S
local out = {}

-- какие ключи графики красить у каждого вида
local GFX = {
  ["assembling-machine"] = { "graphics_set", "graphics_set_flipped" },
  ["mining-drill"] = { "graphics_set", "wet_mining_graphics_set" },
  ["electric-pole"] = { "pictures" },
  ["burner-generator"] = { "animation", "idle_animation" },
  ["solar-panel"] = { "picture" },
  ["wall"] = { "pictures" },
  ["gate"] = { "vertical_animation", "horizontal_animation", "vertical_rail_animation_left", "vertical_rail_animation_right",
               "horizontal_rail_animation_left", "horizontal_rail_animation_right", "vertical_rail_base", "horizontal_rail_base", "wall_patch" },
  ["ammo-turret"] = { "folded_animation", "preparing_animation", "prepared_animation", "attacking_animation", "folding_animation", "graphics_set" },
  ["electric-turret"] = { "folded_animation", "preparing_animation", "prepared_animation", "attacking_animation", "folding_animation", "graphics_set" },
}
local function paint(e, spec)
  for _, k in pairs(GFX[spec.type] or {}) do U.tint(e[k], spec.tint) end
end

local kinds = {}

function kinds.crafter(name, spec)
  local e = U.make(name, spec)
  if spec.base_type == "furnace" then
    -- печь → сборочная машина: убрать поля, которых нет у сборочной машины
    e.result_inventory_size = nil
    e.source_inventory_size = nil
    e.cant_insert_at_source_message_key = nil
    e.custom_input_slot_tooltip_key = nil
  end
  if spec.set.module_slots == 0 then e.allowed_effects = nil end
  paint(e, spec)
  if e.fluid_boxes then
    for _, fb in pairs(e.fluid_boxes) do U.tint(fb.pipe_picture, spec.tint) end
  end
  return e
end

function kinds.kiln(name, spec)
  local e = kinds.crafter(name, spec)
  e.effect_receiver = { uses_module_effects = false, uses_beacon_effects = false, uses_surface_effects = true }
  return e
end

function kinds.drill(name, spec)
  local e = U.make(name, spec)
  paint(e, spec)
  return e
end

-- ленты: у экспресс-ленты, подземки и разделителя один общий belt_animation_set — копируем, потом красим
local maglev_belt_set
local function belt_set(src)
  if not maglev_belt_set then
    maglev_belt_set = table.deepcopy(src)
    U.tint(maglev_belt_set.animation_set, S.entities["magnetics-maglev-transport-belt"].tint)
  end
  return table.deepcopy(maglev_belt_set)
end
function kinds.belt(name, spec)
  local e = U.make(name, spec)
  e.belt_animation_set = belt_set(e.belt_animation_set)
  if spec.type == "transport-belt" then
    e.related_underground_belt = "magnetics-maglev-underground-belt"
  elseif spec.type == "underground-belt" then
    U.tint(e.structure, spec.tint)
  elseif spec.type == "splitter" then
    e.related_transport_belt = "magnetics-maglev-transport-belt"
    U.tint(e.structure, spec.tint)
    U.tint(e.structure_patch, spec.tint)
  end
  return e
end

function kinds.accumulator(name, spec)
  local e = U.make(name, spec)
  U.tint(e.chargable_graphics.picture, spec.tint)
  return e
end

function kinds.capacitor(name, spec)
  local e = U.make(name, spec)
  -- графика аккумулятора 2×2, уменьшенная вдвое (base: accumulator_picture/charge/discharge — глобальные функции base)
  local g = e.chargable_graphics
  g.picture = accumulator_picture({ spec.tint[1], spec.tint[2], spec.tint[3], 1 })
  g.charge_animation = accumulator_charge()
  g.discharge_animation = accumulator_discharge()
  U.rescale(g, 0.5)
  e.circuit_connector = nil
  e.water_reflection = nil
  e.drawing_box_vertical_extension = nil
  return e
end

function kinds.pole(name, spec)
  local e = U.make(name, spec)
  paint(e, spec)
  return e
end

function kinds.generator(name, spec)
  local e = U.make(name, spec)
  paint(e, spec)
  return e
end

function kinds.geomagnetic(name, spec)
  local e = U.make(name, spec)
  paint(e, spec)
  return e
end

-- шипы: на укус отвечают фиксированным электрическим уроном (attack_reaction, как закомментировано у каменной стены в base)
local function thorns(amount)
  return { {
    range = 3, damage_type = "physical", reaction_modifier = 0,   -- большие и гигантские жуки кусают с 2,07–2,16 клетки (пилот боя)
    action = { type = "direct", action_delivery = { type = "instant",
      target_effects = { { type = "damage", damage = { amount = amount, type = "electric" } } } } },
  } }
end
function kinds.wall(name, spec)
  local e = U.make(name, spec)
  paint(e, spec)
  if spec.thorns then e.attack_reaction = thorns(spec.thorns) end
  return e
end
kinds.gate = kinds.wall

function kinds.mend(name, spec)
  local e = U.make(name, spec)
  e.picture = accumulator_picture({ spec.tint[1], spec.tint[2], spec.tint[3], 1 })
  e.subgroup = nil
  e.flags = { "placeable-neutral", "player-creation" }
  return e
end

kinds["ammo-turret"] = function(name, spec)
  local e = U.make(name, spec)
  local a = e.attack_parameters
  a.ammo_category = spec.attack.ammo_category
  a.cooldown = spec.attack.cooldown
  a.range = spec.attack.range
  a.min_range = spec.attack.min_range
  if spec.attack.health_penalty then a.health_penalty = spec.attack.health_penalty end
  paint(e, spec)
  return e
end

function kinds.arc(name, spec)
  local e = U.make(name, spec)
  local at = spec.attack
  local src = data.raw["electric-turret"]["laser-turret"].attack_parameters
  e.attack_parameters = {
    type = "beam", cooldown = at.cooldown, range = at.range, range_mode = "center-to-bounding-box",
    source_direction_count = 64, source_offset = table.deepcopy(src.source_offset), ammo_category = at.ammo_category,
    ammo_type = { energy_consumption = at.energy, action = { type = "direct", action_delivery = { type = "instant", target_effects = {
      { type = "nested-result", action = { type = "direct", action_delivery = { type = "chain", chain = "magnetics-arc-chain" } } },
      { type = "damage", damage = { amount = at.damage, type = "electric" } },
      { type = "create-sticker", sticker = "electric-mini-stun" },
      { type = "nested-result", action = { type = "direct", action_delivery = { type = "beam", beam = "magnetics-arc-beam",
          max_length = at.beam_length, duration = 20, add_to_shooter = false, destroy_with_source_or_target = false,
          source_offset = table.deepcopy(src.ammo_type.action.action_delivery.source_offset) } } },
    } } } },
  }
  paint(e, spec)
  return e
end

for name, spec in pairs(S.entities) do
  local e = kinds[spec.kind](name, spec)
  out[#out + 1] = e
  out[#out + 1] = U.building_item(name, spec)
end

-- вспомогательные прототипы разрядника: цепь и два косметических луча (урон мгновенный, лучи без действия)
local arc = S.entities["magnetics-arc-emitter"].attack
local function cosmetic_beam(bname)
  local b = table.deepcopy(data.raw.beam["electric-beam"])
  b.name = bname
  b.action = nil
  return b
end
out[#out + 1] = cosmetic_beam("magnetics-arc-beam")
out[#out + 1] = cosmetic_beam("magnetics-arc-bounce-beam")
out[#out + 1] = {
  type = "chain-active-trigger", name = "magnetics-arc-chain",
  max_jumps = arc.chain_jumps, max_range_per_jump = arc.chain_range, jump_delay_ticks = 3,
  fork_chance = 0, fork_chance_increase_per_quality_level = 0.05, max_forks = 2,
  action = { type = "direct", action_delivery = {
    { type = "instant", target_effects = {
        { type = "damage", damage = { amount = arc.chain_damage, type = "electric" } },
        { type = "create-sticker", sticker = "electric-mini-stun" } } },
    { type = "beam", beam = "magnetics-arc-bounce-beam", max_length = arc.chain_range + 0.5, duration = 20, add_to_shooter = false,
      destroy_with_source_or_target = false },
  } },
}
data:extend(out)
