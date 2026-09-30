# Recon: mining drills and resources in Factorio 2.0.77 (for the "Magnetics" mod)

Sources used (all read directly, nothing from memory unless marked):

- `D/` = `/opt/factorio/data/`
- `D/base/prototypes/entity/mining-drill.lua` (1870 lines: electric-mining-drill, burner-mining-drill, pumpjack)
- `D/space-age/prototypes/entity/big-mining-drill.lua` (687 lines)
- `D/base/prototypes/entity/resources.lua`, `D/space-age/prototypes/entity/resources.lua`
- `D/base/prototypes/{item,recipe,technology}.lua`, `D/space-age/prototypes/{item,recipe,technology}.lua`
- `D/space-age/base-data-updates.lua`, `D/space-age/prototypes/entity/base-frozen-graphics.lua`, `D/quality/prototypes/base-data-updates.lua`, `D/quality/data-updates.lua`, `D/quality/prototypes/quality.lua`
- `D/core/lualib/circuit-connector-generated-definitions.lua`, `D/core/lualib/circuit-connector-sprites.lua`, `D/core/lualib/util.lua`, `D/core/lualib/collision-mask-defaults.lua`
- `/opt/factorio-api/prototype-api.json` (application_version 2.0.77, api_version 6)
- `/opt/factorio-api/runtime-api.json` (application_version 2.0.77)

Notation: `file:line` refers to line numbers in the file. `API:Proto.prop` is an entry in prototype-api.json, `RT:Class.member` is an entry in runtime-api.json.

The headless build has no PNG files: `find /opt/factorio/data -name "*.png"` gives 0. `D/base/graphics/` holds only `.lua` sprite-metadata files (1469 `.lua` in total under graphics dirs). Every `filename = "...png"` below is a reference as written in the Lua. Its existence on disk could not be checked here.

---

## 1. Summary table (vanilla values, verbatim from Lua)

| field | burner-mining-drill | electric-mining-drill | big-mining-drill (SA) | pumpjack |
|---|---|---|---|---|
| file:line of `name` | mining-drill.lua:1570 | mining-drill.lua:259 | big-mining-drill.lua:557 | mining-drill.lua:1754 |
| collision_box | `{{-0.7,-0.7},{0.7,0.7}}` (:1578) | `{{-1.35,-1.35},{1.35,1.35}}` (:267) | `{{-2.35,-2.35},{2.35,2.35}}` (:565) | `{{-1.2,-1.2},{1.2,1.2}}` (:1762) |
| selection_box (footprint) | `{{-1,-1},{1,1}}` = 2x2 (:1579) | `{{-1.5,-1.5},{1.5,1.5}}` = 3x3 (:268) | `{{-2.5,-2.5},{2.5,2.5}}` = 5x5 (:566) | `{{-1.5,-1.5},{1.5,1.5}}` = 3x3 (:1763) |
| mining_speed | 0.25 (:1581) | 0.5 (:1545) | 2.5 (:639) | 1 (:1786) |
| resource_searching_radius | 0.99 (:1740) | 2.49 (:1553) | 6.49 (:647) | 0.49 (:1787) |
| vector_to_place_result | `{-0.5, -1.3}` (:1741) | `{0, -1.85}` (:1554) | `{0, -2.85}` (:648) | `{0, 0}` (:1788) |
| resource_categories | `{"basic-solid"}` (:1573) | `{"basic-solid"}` (:264) | `{"basic-solid", "hard-solid"}` (:562) | `{"basic-fluid"}` (:1758) |
| energy_usage | "150kW" (:1608) | "90kW" (:1552) | "300kW" (:646) | "90kW" (:1785) |
| energy_source | burner, `fuel_categories={"chemical"}`, pollution 12/min (:1591-1607) | electric, secondary-input, pollution 10/min (:1546-1551) | electric, secondary-input, pollution 40/min (:640-645) | electric, secondary-input, pollution 10/min (:1766-1771) |
| module_slots | not set (API default: none) | 3 (:1555) | 4 (:649) | 2 (:1789) |
| allowed_effects | `{}` "no beacon effects" (:1590) | not set (API default: all) | not set | not set in base; quality mod sets `{"consumption","speed","productivity","pollution"}` (`D/quality/prototypes/base-data-updates.lua:7`) |
| input_fluid_box | none | volume 200, 3 connections W/E/S (:270-280) | volume 200, 4 connections (:572-583) | none |
| output_fluid_box | none | none | none | volume 1000, 1 output connection (:1772-1784) |
| graphics_set | yes (:1609) | yes (:291) | `graphical_set(false)` (:628) | yes, plus `base_picture` (:1798, :1820) |
| wet_mining_graphics_set | none | yes (:697) | `graphical_set(true)` (:629) | none |
| radius_visualisation_picture | none | 10x10 png (:1556-1561) | 10x10 png (:650-655) | 12x12 png (:1790-1795) |
| drilling_sound / moving_sound | none | none | both (:602-624) | none |
| fast_replaceable_group | "mining-drill" (:1742) | "mining-drill" (:1563) | "big-mining-drill" (:657) | "pumpjack" (:1864) |
| next_upgrade | none | none | none | none |
| circuit_connector | `circuit_connector_definitions["burner-mining-drill"]` (:1744) | `circuit_connector_definitions["electric-mining-drill"]` (:1565) | `table.deepcopy(circuit_connector_definitions["big-mining-drill"])` (:658) | `circuit_connector_definitions["pumpjack"]` (:1866) |
| circuit_wire_max_distance | `default_circuit_wire_max_distance` (= 9, `D/core/lualib/circuit-connector-sprites.lua:95`) | same | same | same |
| max_health | 150 | 300 | 300 | 200 |
| minable (entity) | `{mining_time = 0.3, result = "burner-mining-drill"}` | `{mining_time = 0.3, result = "electric-mining-drill"}` | `{mining_time = 0.3, result = "big-mining-drill"}` | `{mining_time = 0.5, result = "pumpjack"}` |
| icon | `__base__/graphics/icons/burner-mining-drill.png` | `__base__/graphics/icons/electric-mining-drill.png` | `__space-age__/graphics/icons/big-mining-drill.png` | `__base__/graphics/icons/pumpjack.png` |
| Space Age heating_energy | "50kW" (`space-age/base-data-updates.lua:121`) | "100kW" (:120) | "200kW" (big-mining-drill.lua:569) | "50kW" (:122) |
| Space Age surface_conditions | pressure min 10 (`space-age/base-data-updates.lua:163-171,185`) | none | none | none |
| other | — | `perceived_performance = {maximum = 30.0}`, `integration_patch` | `resource_drain_rate_percent = 50`, `drops_full_belt_stacks = true`, `drawing_box_vertical_extension = 1`, `perceived_performance = {maximum = 30.0}` | `drawing_box_vertical_extension = 1`, `base_render_layer = "object"` |

All four use `flags = {"placeable-neutral", "player-creation"}`, `damaged_trigger_effect = hit_effects.entity()`, and `monitor_visualization_tint = {78, 173, 255}`. The big drill writes it as `{r=78, g=173, b=255}` (:656).

Mining rate (derived from `API:MinableProperties.mining_time`: "How many seconds are required to mine this object at 1 mining speed."): an electric drill (speed 0.5) on iron-ore (mining_time 1) mines 1 ore per 2 s, i.e. 0.5/s before productivity and modules. The formula with productivity is not spelled out in the API JSON. It points to the wiki "mining" page, which was not available here.

---

## 2. electric-mining-drill (base) in detail

### 2.1 Prototype body (non-graphics), verbatim

`D/base/prototypes/entity/mining-drill.lua:257-290` and `:1503-1567`:

```lua
  {
    type = "mining-drill",
    name = "electric-mining-drill",
    icon = "__base__/graphics/icons/electric-mining-drill.png",
    flags = {"placeable-neutral", "player-creation"},
    minable = {mining_time = 0.3, result = "electric-mining-drill"},
    max_health = 300,
    resource_categories = {"basic-solid"},
    corpse = "electric-mining-drill-remnants",
    dying_explosion = "electric-mining-drill-explosion",
    collision_box = {{-1.35, -1.35}, {1.35, 1.35}},
    selection_box = {{-1.5, -1.5}, {1.5, 1.5}},
    damaged_trigger_effect = hit_effects.entity(),
    input_fluid_box =
    {
      pipe_covers = pipecoverspictures(),
      volume = 200,
      pipe_connections =
      {
        { direction = defines.direction.west, position = {-1, 0}},
        { direction = defines.direction.east, position = {1, 0}},
        { direction = defines.direction.south, position = {0, 1}}
      }
    },
    working_sound =
    {
      sound = {filename = "__base__/sound/electric-mining-drill.ogg", volume = 1.0, advanced_volume_control = {attenuation = "exponential"}},
      max_sounds_per_prototype = 4,
      fade_in_ticks = 4,
      fade_out_ticks = 20
    },
    open_sound = sounds.drill_open,
    close_sound = sounds.drill_close,

    graphics_set = { ... },            -- :291-695
    wet_mining_graphics_set = { ... }, -- :697-1501

    perceived_performance = {maximum = 30.0},

    integration_patch = { north = {...}, east = {...}, south = {...}, west = {...} }, -- :1505-1543

    mining_speed = 0.5,
    energy_source =
    {
      type = "electric",
      emissions_per_minute = { pollution = 10 },
      usage_priority = "secondary-input"
    },
    energy_usage = "90kW",
    resource_searching_radius = 2.49,
    vector_to_place_result = {0, -1.85},
    module_slots = 3,
    radius_visualisation_picture =
    {
      filename = "__base__/graphics/entity/electric-mining-drill/electric-mining-drill-radius-visualization.png",
      width = 10,
      height = 10
    },
    monitor_visualization_tint = {78, 173, 255},
    fast_replaceable_group = "mining-drill",

    circuit_connector = circuit_connector_definitions["electric-mining-drill"],
    circuit_wire_max_distance = default_circuit_wire_max_distance
  },
```

Notes:
- There is no `drilling_sound` on any base drill. `grep drilling_sound` finds it only in `big-mining-drill.lua:614`.
- The fluid box has no north connection because north is the output side (`vector_to_place_result = {0,-1.85}`, 0.35 tiles beyond the 1.5 edge).
- `pipecoverspictures` is a global function defined in `D/base/prototypes/entity/pipecovers.lua:1` (`pipecoverspictures = function() ...`). The drill file loads it with `require ("__base__.prototypes.entity.pipecovers")` (mining-drill.lua:1), and so does big-mining-drill.lua:1.
- `sounds` = `require("__base__.prototypes.entity.sounds")`; `sounds.drill_open`/`drill_close` are defined in `D/base/prototypes/entity/sounds.lua:317-318`.
- The corpse and explosion exist: `electric-mining-drill-remnants` (`D/base/prototypes/entity/remnants.lua:937`) and `electric-mining-drill-explosion` (`D/base/prototypes/entity/explosions.lua:1972`).

### 2.2 Global helper functions defined in mining-drill.lua (reusable by mods)

These are declared without `local`, so they are globals in the data stage. Space Age calls one of them: `big-mining-drill.lua:183` has `status_colors = electric_mining_drill_status_colors()`.

- `electric_drill_animation_speed = 0.4` (:6)
- `electric_drill_animation_sequence`, `electric_drill_animation_shadow_sequence` (:7-47)
- `electric_mining_drill_smoke()`, `electric_mining_drill_smoke_front()`, `electric_mining_drill_animation()`, `electric_mining_drill_shadow_animation()`, `electric_mining_drill_horizontal_animation()`, `electric_mining_drill_horizontal_front_animation()`, `electric_mining_drill_horizontal_shadow_animation()` (:49-159)
- `electric_mining_drill_status_colors()` (:161-177):

```lua
function electric_mining_drill_status_colors()
  return
  {
    -- If no_power, idle, no_minable_resources, disabled, insufficient_input or full_output is used, always_draw of corresponding layer must be set to true to draw it in those states.

    no_power = {0, 0, 0, 0},                  -- If no_power is not specified or is nil, it defaults to clear color {0,0,0,0}

    idle = {1, 0, 0, 1},                      -- If idle is not specified or is nil, it defaults to white.
    no_minable_resources = {1, 0, 0, 1},      -- If no_minable_resources, disabled, insufficient_input or full_output are not specified or are nil, they default to idle color.
    insufficient_input = {1, 0, 0, 1},
    full_output = {1, 1, 0, 1},
    disabled = {1, 1, 0, 1},

    working = {0, 1, 0, 1},                   -- If working is not specified or is nil, it defaults to white.
    low_power = {1, 1, 0, 1},                 -- If low_power is not specified or is nil, it defaults to working color.
  }
end
```

- `electric_mining_drill_status_leds_working_visualisation()` (:179-231): `apply_tint = "status"`, `always_draw = true`, 4 directional LED sprites with `draw_as_glow = true`.
- `electric_mining_drill_add_light_offsets(t)` (:233-239). The two lights are `local`: `electric_mining_drill_primary_light` (:241) and `electric_mining_drill_secondary_light` (:247).

### 2.3 graphics_set structure (electric-mining-drill, :291-695)

Top level keys, in file order:

```lua
    graphics_set =
    {
      drilling_vertical_movement_duration = 10 / electric_drill_animation_speed,
      animation_progress = 1,

      status_colors = electric_mining_drill_status_colors(),

      circuit_connector_layer = "object",
      circuit_connector_secondary_draw_order = {north = 14, east = 30, south = 30, west = 30},

      animation =
      {
        north = { layers = { <N.png 190x208, repeat_count=5>, <N-output.png frame_count=5>, <N-shadow.png draw_as_shadow> } },
        east  = { layers = { <E.png>, <E-output.png>, <E-shadow.png> } },
        south = { layers = { <S.png>, <S-shadow.png> } },
        west  = { layers = { <W.png>, <W-output.png>, <W-shadow.png> } }
      },

      shift_animation_waypoints =
      {
        -- Movement should be between 0.25-0.4 distance
        -- Bounds -0.5 - 0.6
        north = {{0, 0}, {0, -0.3}, {0, 0.1}, {0, 0.5}, {0, 0.2}, {0, -0.1}, {0, -0.5}, {0, -0.15}, {0, 0.25}, {0, 0.6}, {0, 0.3}},
        -- Bounds -1 - 0
        east = {{0, 0}, {-0.4, 0}, {-0.1, 0}, {-0.5, 0}, {-0.75, 0}, {-1, 0}, {-0.65, 0}, {-0.3, 0}, {-0.9, 0}, {-0.6, 0}, {-0.3, 0}},
        -- Bounds -1 - 0
        south = {{0, 0}, {0, -0.4}, {0, -0.1}, {0, -0.5}, {0, -0.75}, {0, -1}, {0, -0.65}, {0, -0.3}, {0, -0.9}, {0, -0.6}, {0, -0.3}},
        -- Bounds 0 - 1
        west = {{0, 0}, {0.4, 0}, {0.1, 0}, {0.5, 0}, {0.75, 0}, {1, 0}, {0.65, 0}, {0.3, 0}, {0.9, 0}, {0.6, 0}, {0.3, 0}}
      },

      shift_animation_waypoint_stop_duration = 195 / electric_drill_animation_speed,
      shift_animation_transition_duration = 30 / electric_drill_animation_speed,

      working_visualisations = { ... 9 entries, see below ... }
    },
```

`working_visualisations` (:470-694), in draw order:

1. "dust animation 1" (:473-483): `constant_speed = true, synced_fadeout = true, align_to_waypoint = true, apply_tint = "resource-color", animation = electric_mining_drill_smoke()`, plus `north_position = {0, 0.25}` and the other three positions.
2. "dust animation directional 1" (:486-510): `constant_speed, fadeout, apply_tint = "resource-color"`, `north_animation` only (N-smoke.png). East, south and west are `nil`.
3. "drill back animation" (:513-548): `animated_shift = true, always_draw = true`. N/S use `electric_mining_drill_animation()` and `electric_mining_drill_shadow_animation()`; E/W use the `horizontal` variants.
4. "dust animation 2" (:551-561): like #1 but with `electric_mining_drill_smoke_front()`.
5. "dust animation directional 2" (:564-620): E/S/W smoke sprites, north `nil`.
6. "drill front animation" (:623-630): `animated_shift = true, always_draw = true`, E/W = `electric_mining_drill_horizontal_front_animation()`.
7. "front frame" (:633-686): `always_draw = true`. E = E-front.png, S = layers {S-output.png, S-front.png}, W = W-front.png.
8. LEDs: `electric_mining_drill_status_leds_working_visualisation()` (:689).
9. light: `electric_mining_drill_secondary_light` (:693). The primary light is commented out at :692.

### 2.4 wet_mining_graphics_set (:697-1501)

This set has the same top-level keys as `graphics_set`, with these differences:
- `circuit_connector_secondary_draw_order = {north = 14, east = 48, south = 48, west = 48}` (:705)
- `animation` uses the `*-wet.png` and `*-wet-shadow.png` bodies (:707-858)
- different `shift_animation_waypoints`, with 4 points per direction (:860-871):

```lua
      shift_animation_waypoints =
      {
        -- Movement should be between 0.25-0.4 distance
        -- Bounds -0.5 - 0.2
        north = {{0, 0}, {0, -0.4}, {0, -0.1}, {0, 0.2}},
        -- Bounds -0.3 - 0
        east = {{0, 0}, {-0.3, 0}, {0, 0}, {-0.25, 0}},
        -- Bounds -0.7 - 0
        south = {{0, 0}, {0, -0.4}, {0, -0.7}, {0, -0.3}},
        -- Bounds 0 - 0.3
        west = {{0, 0}, {0.3, 0}, {0, 0}, {0.25, 0}}
      },
```

- extra working visualisations for the fluid window. Structural lines, from the file comments:
  - "fluid window background (bottom)" :1024, `secondary_draw_order = -49, always_draw = true`
  - "fluid base (bottom)" :1080, `secondary_draw_order = -48, apply_tint = "input-fluid-base-color"`
  - "fluid flow (bottom)" :1137, `secondary_draw_order = -47, apply_tint = "input-fluid-flow-color"`
  - "drill front animation" :1194
  - "fluid window background (front)" :1204
  - "fluid base (front)" :1273, `apply_tint = "input-fluid-base-color"`
  - "fluid flow (front)" :1343, `apply_tint = "input-fluid-flow-color"`
  - "front frame (wet)" :1413
  - LEDs :1494, light :1497-1499

**When the wet set is used is not found in sources.** `API:MiningDrillPrototype.wet_mining_graphics_set` has an empty description. The name and the `input-fluid-*` tints suggest it is drawn when the drill mines with an input fluid. That is an inference.

### 2.5 integration_patch (:1505-1543)

A `Sprite4Way` with 4 directional pngs: `...-N-integration.png` 216x218, E 236x214, S 214x230, W 234x214, all `scale = 0.5`. Per `API:EntityWithHealthPrototype.integration_patch` it is a "Sprite drawn on ground under the entity" and "May also be defined inside `graphics_set`".

### 2.6 Circuit connector

`D/core/lualib/circuit-connector-generated-definitions.lua:573-582`:

```lua
circuit_connector_definitions["electric-mining-drill"] = circuit_connector_definitions.create_vector
(
  universal_connector_template,
  {
    { variation = 4, main_offset = util.by_pixel(-44, -41), shadow_offset = util.by_pixel(-34, -36), show_shadow = false },
    { variation = 2, main_offset = util.by_pixel(34, 30), shadow_offset = util.by_pixel(36, 35), show_shadow = false },
    { variation = 0, main_offset = util.by_pixel(-35, 24), shadow_offset = util.by_pixel(-34, 31), show_shadow = false },
    { variation = 6, main_offset = util.by_pixel(-34, 37), shadow_offset = util.by_pixel(-40, 49), show_shadow = false }
  }
)
```

The burner drill is at :534-543 and the pumpjack at :640-649 (same values for all 4 directions). Big drill: `D/space-age/prototypes/entity/circuit-network.lua:68-77`. `API:MiningDrillPrototype.circuit_connector` is a tuple of 4 `CircuitConnectorDefinition`, one per direction.

### 2.7 Item, recipe, technology

Item, `D/base/prototypes/item.lua:254-265`:

```lua
  {
    type = "item",
    name = "electric-mining-drill",
    icon = "__base__/graphics/icons/electric-mining-drill.png",
    subgroup = "extraction-machine",
    order = "a[items]-b[electric-mining-drill]",
    inventory_move_sound = item_sounds.drill_inventory_move,
    pick_sound = item_sounds.drill_inventory_pickup,
    drop_sound = item_sounds.drill_inventory_move,
    place_result = "electric-mining-drill",
    stack_size = 50
  },
```

The burner item is at :241-253 (order `a[items]-a[burner-mining-drill]`, stack 50, `random_tint_color = item_tints.iron_rust`). The pumpjack item is at :1947-1958 (order `b[fluids]-b[pumpjack]`, stack 20). The subgroup `extraction-machine` is defined in `D/base/prototypes/item-groups.lua:87`.

Recipe, `D/base/prototypes/recipe.lua:773-785`:

```lua
  {
    type = "recipe",
    name = "electric-mining-drill",
    energy_required = 2,
    ingredients =
    {
      {type = "item", name = "electronic-circuit", amount = 3},
      {type = "item", name = "iron-gear-wheel", amount = 5},
      {type = "item", name = "iron-plate", amount = 10}
    },
    results = {{type="item", name="electric-mining-drill", amount=1}},
    enabled = false
  },
```

Other recipes:
- burner-mining-drill (:786-797): 3 iron-gear-wheel + 1 stone-furnace + 3 iron-plate, 2 s. `enabled` is not set, so it is available from the start.
- pumpjack (:2266-2279): 5 steel-plate + 10 iron-gear-wheel + 5 electronic-circuit + 10 pipe, 5 s, `enabled = false`.

Technology, `D/base/prototypes/technology.lua:107-126`:

```lua
  {
    type = "technology",
    name = "electric-mining-drill",
    icon = "__base__/graphics/technology/electric-mining-drill.png",
    icon_size = 256,
    effects =
    {
      {
        type = "unlock-recipe",
        recipe = "electric-mining-drill"
      }
    },
    prerequisites = {"automation-science-pack"},
    unit =
    {
      count = 25,
      ingredients = {{"automation-science-pack", 1}},
      time = 10
    }
  },
```

The pumpjack is unlocked by `oil-gathering` (:4572-4591), with prerequisite `fluid-handling`, 100 x (red+green), 30 s.

Mining productivity: `mining-productivity-1..3` (:5212-5287) with effect `{type = "mining-drill-productivity-bonus", modifier = 0.1}`. Space Age rewrites `mining-productivity-3` into an infinite tech and deletes `mining-productivity-4` (`D/space-age/base-data-updates.lua:757-771`). `API:MiningDrillPrototype.uses_force_mining_productivity_bonus` defaults to true.

### 2.8 Modifications by Space Age and Quality (all `data.raw` touches of type "mining-drill" in the tree)

- `D/space-age/base-data-updates.lua:120-122`: heating_energy is electric 100kW, burner 50kW, pumpjack 50kW. `API:EntityPrototype.heating_energy`: "This entity can freeze if heating_energy is larger than zero."
- `D/space-age/base-data-updates.lua:185`: the burner drill gets `surface_conditions = ten_pressure_condition()` (pressure min 10, :163-171).
- `D/space-age/prototypes/entity/base-frozen-graphics.lua:45-46`: the electric drill and pumpjack are listed in the frozen pipe-cover loop. That loop only reads `prototype.fluid_boxes or {prototype.fluid_box}` (:52), so it does not touch `input_fluid_box` or `output_fluid_box`. This is an observation from the code; its effect on drills is none. `:317-328`: pumpjack `graphics_set.reset_animation_when_frozen = true` and `graphics_set.frozen_patch = {sheet = {...frozen/pumpjack/pumpjack.png...}}`. The electric drill gets no frozen_patch.
- `D/quality/prototypes/base-data-updates.lua:7`: `data.raw["mining-drill"]["pumpjack"].allowed_effects = {"consumption", "speed", "productivity", "pollution"}`.
- `D/quality/prototypes/quality.lua`: `mining_drill_resource_drain_multiplier` = 5/6, 4/6, 3/6, 1/6 for uncommon, rare, epic, legendary (:14, :28, :42, :54). The levels are 1, 2, 3, 5 (:6, :20, :34, :48).
- `D/quality/data-updates.lua:1-6` generates a recycling recipe for every recipe in `data.raw.recipe`, so a mod's drill recipe also gets one. `:8-26` also generates self-recycling for items without a `-recycling` recipe.

---

## 3. burner-mining-drill (base) — `mining-drill.lua:1568-1746`

```lua
    mining_speed = 0.25,
    ...
    allowed_effects = {}, -- no beacon effects on the burner drill
    energy_source =
    {
      type = "burner",
      fuel_categories = {"chemical"},
      effectivity = 1,
      fuel_inventory_size = 1,
      emissions_per_minute = { pollution = 12 },
      light_flicker = {color = {0,0,0}},
      smoke =
      {
        {
          name = "smoke",
          deviation = {0.1, 0.1},
          frequency = 3
        }
      }
    },
    energy_usage = "150kW",
    graphics_set =
    {
      animation =
      {
        north = { layers = { {... N.png 173x188, frame_count = 32, animation_speed = 0.5, run_mode = "forward-then-backward", scale = 0.5}, {... N-shadow.png, draw_as_shadow = true} } },
        east = {...}, south = {...}, west = {...}
      }
    },
    monitor_visualization_tint = {78, 173, 255},
    resource_searching_radius = 0.99,
    vector_to_place_result = {-0.5, -1.3},
    fast_replaceable_group = "mining-drill",
```

- The graphics_set has only `animation` (4 dirs x {body, shadow}): no working_visualisations, no wet set, no radius picture, no module slots.
- Sound: `working_sound = { sound = sound_variations("__base__/sound/burner-mining-drill", 2, 0.6, volume_multiplier("tips-and-tricks", 0.8)), fade_in_ticks = 4, fade_out_ticks = 20 }` (:1582-1587).
- The footprint is 2x2 (center on a tile corner). The radius of 0.99 gives a 2x2 area, per the API text in section 6.

---

## 4. pumpjack (base) — `mining-drill.lua:1750-1870`

```lua
    resource_categories = {"basic-fluid"},
    ...
    drawing_box_vertical_extension = 1,
    energy_source =
    {
      type = "electric",
      emissions_per_minute = { pollution = 10 },
      usage_priority = "secondary-input"
    },
    output_fluid_box =
    {
      volume = 1000,
      pipe_covers = pipecoverspictures(),
      pipe_connections =
      {
        {
          direction = defines.direction.north,
          positions = {{1, -1}, {1, -1}, {-1, 1}, {-1, 1}},
          flow_direction = "output"
        }
      }
    },
    energy_usage = "90kW",
    mining_speed = 1,
    resource_searching_radius = 0.49,
    vector_to_place_result = {0, 0},
    module_slots = 2,
    radius_visualisation_picture =
    {
      filename = "__base__/graphics/entity/pumpjack/pumpjack-radius-visualization.png",
      width = 12,
      height = 12
    },
    monitor_visualization_tint = {78, 173, 255},
    base_render_layer = "object",
    base_picture = { sheets = { {pumpjack-base.png 261x273 ...}, {pumpjack-base-shadow.png, draw_as_shadow = true} } },
    graphics_set =
    {
      animation =
      {
        north = { layers = { {pumpjack-horsehead.png, frame_count = 40, line_length = 8, 206x202}, {horsehead-shadow, draw_as_shadow = true} } }
      }
    },
    ...
    fast_replaceable_group = "pumpjack",
```

- Only `north` is defined in `animation`. `API:Animation4Way`: "Any direction that is not defined defaults to the north animation."
- `positions` is a 4-tuple, one per direction. `API:PipeConnectionDefinition.positions`: "This is used for example by "pumpjack" where connections are consistently near bottom-left corner (2 directions) or near top-right corner (2 directions)."
- `vector_to_place_result = {0,0}` for a fluid-only drill. `API:MiningDrillPrototype.vector_to_place_result`: "a vector of `{0,0}` disables the yellow arrow alt-mode indicator".
- Sounds (:1855-1863): open and close `pumpjack-open/close.ogg`; `working_sound = { sound = {filename = "__base__/sound/pumpjack.ogg", volume = 0.7, audible_distance_modifier = 0.6}, max_sounds_per_prototype = 3, fade_in_ticks = 4, fade_out_ticks = 10 }`.

---

## 5. big-mining-drill (Space Age) — `D/space-age/prototypes/entity/big-mining-drill.lua`

The file header says: `--This is a placeholder file, a rescaled version of the old miner graphic.` (:2).

### 5.1 Prototype body, verbatim (:553-660)

```lua
  {
    type = "mining-drill",
    name = "big-mining-drill",
    icon = "__space-age__/graphics/icons/big-mining-drill.png",
    flags = {"placeable-neutral", "player-creation"},
    minable = {mining_time = 0.3, result = "big-mining-drill"},
    max_health = 300,
    resource_categories = {"basic-solid", "hard-solid"},
    corpse = "big-mining-drill-remnants",
    dying_explosion = "big-mining-drill-explosion",
    collision_box = {{ -2.35, -2.35}, {2.35, 2.35}},
    selection_box = {{ -2.5, -2.5}, {2.5, 2.5}},
    drawing_box_vertical_extension = 1,
    damaged_trigger_effect = hit_effects.entity(),
    heating_energy = "200kW",
    resource_drain_rate_percent = 50,
    drops_full_belt_stacks = true,
    input_fluid_box =
    {
      pipe_covers = pipecoverspictures(),
      volume = 200,
      pipe_connections =
      {
        { direction = defines.direction.west, position = {-2, -1} },
        { direction = defines.direction.east, position = {2, -1} },
        { direction = defines.direction.south, position = {1, 2} },
        { direction = defines.direction.south, position = {-1, 2} }
      }
    },
    working_sound =
    {
      main_sounds =
      {
        sound = {filename = "__space-age__/sound/entity/big-mining-drill/big-mining-drill-working-loop.ogg", volume = 0.3},
        fade_in_ticks = 4,
        fade_out_ticks = 30
      },
      sound_accents =
      {
        {
          sound = {filename = "__space-age__/sound/entity/big-mining-drill/big-mining-drill-start.ogg", volume = 0.75, audible_distance_modifier = 0.3},
          play_for_working_visualisation = "drill-animation",
          frame = 8,
        }
      },
      max_sounds_per_prototype = 1
    },
    moving_sound =
    {
      sound =
      {
        filename = "__space-age__/sound/entity/big-mining-drill/big-mining-drill-moving-loop.ogg", volume = 0.6,
        aggregation = {max_count = 2, remove = true, count_already_playing = true},
        audible_distance_modifier = 0.25
      },
      stopped_sound = {filename = "__space-age__/sound/entity/big-mining-drill/big-mining-drill-moving-stop.ogg", volume = 0.4},
      minimal_sound_duration_for_stopped_sound = 33, -- at least third of the movement duration (which is drilling_frames / animation_speed)
      fade_ticks = 2
    },
    drilling_sound =
    {
      sound =
      {
        filename = "__space-age__/sound/entity/big-mining-drill/big-mining-drill-loop.ogg", volume = 0.7,
        aggregation = {max_count = 2, remove = true, count_already_playing = true}
      },
      fade_ticks = 10
    },
    drilling_sound_animation_start_frame = 12,
    drilling_sound_animation_end_frame = 156,
    open_sound = sounds.drill_open,
    close_sound = sounds.drill_close,

    graphics_set = graphical_set(false),
    wet_mining_graphics_set = graphical_set(true),
    integration_patch =
    {
      north = bmd_sprite_load("N-integration", nil),
      east = bmd_sprite_load("E-integration", nil),
      south = bmd_sprite_load("S-integration", nil),
      west = bmd_sprite_load("W-integration", nil),
    },
    perceived_performance = {maximum = 30.0},

    mining_speed = 2.5,
    energy_source =
    {
      type = "electric",
      emissions_per_minute = { pollution = 40 },
      usage_priority = "secondary-input"
    },
    energy_usage = "300kW",
    resource_searching_radius = 6.49,
    vector_to_place_result = {0, -2.85},
    module_slots = 4,
    radius_visualisation_picture =
    {
      filename = "__space-age__/graphics/entity/big-mining-drill/big-mining-drill-radius-visualization.png",
      width = 10,
      height = 10
    },
    monitor_visualization_tint = {r=78, g=173, b=255},
    fast_replaceable_group = "big-mining-drill",
    circuit_connector = table.deepcopy(circuit_connector_definitions["big-mining-drill"]),
    circuit_wire_max_distance = default_circuit_wire_max_distance
  },
```

### 5.2 graphical_set(with_fluid) (:176-550)

- Keys: `drilling_vertical_movement_duration = 15 / animation_speed`, `shift_animation_waypoint_stop_duration = drilling_frames / animation_speed`, `shift_animation_transition_duration = transition_frames / animation_speed` (with `animation_speed = 0.5`, `drilling_frames = 180`, `transition_frames = 50`, :6-8), `animation_progress = 1`, `status_colors = electric_mining_drill_status_colors()`, `circuit_connector_layer = "object"`, `circuit_connector_secondary_draw_order = { north = 40, east = 40, south = 40, west = 40 }`, `animation` = N/E/S/W `*-still` + `*-still-shadow` (:187-220), `shift_animation_waypoints` built by `waypoints_stops(min,max)` (:222-227).
- The sprites use `bmd_sprite_load(file_name, table)` → `util.sprite_load(path, table)` (:103-121). `util.sprite_load` (`D/core/lualib/util.lua:673-705`) does `require(path)` on the sprite metadata `.lua` file, which exists in the headless build (e.g. `D/space-age/graphics/entity/big-mining-drill/North/big-mining-drill-N-still.lua`), and sets `filename = path .. '.png'`.
- `working_visualisations` (:231-548), in order:
  1. scorch mark: `mining_drill_scorch_mark = true, scorch_mark_fade_in_frames = 30, scorch_mark_fade_out_duration = 300, scorch_mark_lifetime = 600`
  2. drill: `name = "drill-animation", animated_shift = true, always_draw = true`. The name is referenced by `working_sound.sound_accents[1].play_for_working_visualisation`.
  3. dust
  4. tinted dust (`apply_tint = "resource-color"`)
  5. still reel
  6. wheels transition
  7. wheels waypoint stop, using `enabled_in_animated_shift_during_waypoint_stop/_transition` and `frame_based_on_shift_animation_progress`
  8. output
  9. only if `with_fluid`: `fluids()` pipe connections
  10. drill support
  11. front frame
  12. output particles (`apply_tint = "resource-color"`)
  13. only if `with_fluid`: `fluids_front()`
  14. LEDs (`apply_tint = "status"`, `draw_as_glow`)
  15. top nozzle
  16. drill top
  17. LED glow light (`apply_tint = "status"`, :537-546)

  The only difference between the dry and wet sets is the two optional fluid pipe-connection visualisations (:124-174, :346-348, :435-437).

### 5.3 Item, recipe, tech

- Item: `D/space-age/prototypes/item.lua:507-520`. Subgroup `extraction-machine`, order `a[items]-c[big-mining-drill]`, `stack_size = 20`, `default_import_location = "vulcanus"`, `weight = 50 * kg`. `kg` is a global from `D/core/lualib/util.lua:881`.
- Recipe: `D/space-age/prototypes/recipe.lua:1764-1787`. `category = "metallurgy"`, `surface_conditions = {{property = "pressure", min = 4000, max = 4000}}`, 30 s. Ingredients: 1 electric-mining-drill, 200 molten-iron (fluid), 20 tungsten-carbide, 10 electric-engine-unit, 10 advanced-circuit.
- Tech: `D/space-age/prototypes/technology.lua:640-658`. Prerequisites `{"foundry", "electric-mining-drill"}`, `research_trigger = {type = "craft-item", item = "foundry"}`. `tungsten-steel` has prerequisite big-mining-drill (:746).
- Quality: `D/quality/prototypes/recycling.lua:173` whitelists "big-mining-drill" among the metallurgy recipes that may be recycled.

---

## 6. MiningDrillPrototype API (prototype-api.json, 2.0.77)

Inheritance: `MiningDrillPrototype → EntityWithOwnerPrototype → EntityWithHealthPrototype → EntityPrototype → Prototype → PrototypeBase`. The typename is `mining-drill`. The default collision mask is `building()` (`D/core/lualib/collision-mask-defaults.lua:45`).

Own properties (name, required or optional, type, default, and the description quoted where relevant):

| property | req | type | default | note (quoted from API) |
|---|---|---|---|---|
| vector_to_place_result | REQUIRED | Vector | — | "The position where any item results are placed, when the mining drill is facing north (default direction)." |
| resource_searching_radius | REQUIRED | double | — | "This is 2.49 for electric mining drills (a 5x5 area) and 0.99 for burner mining drills (a 2x2 area). The drill searches resource outside its natural boundary box, which is 0.01 (the middle of the entity); making it 2.5 and 1.0 gives it another block radius." |
| resource_searching_offset | opt | Vector | `{0, 0}` | "Offset of the `resource_searching_radius` from the entity center when the mining drill is facing north." |
| energy_usage | REQUIRED | Energy | — | "Can't be less than or equal to 0." |
| mining_speed | REQUIRED | double | — | |
| energy_source | REQUIRED | EnergySource | — | |
| resource_categories | REQUIRED | array of ResourceCategoryID | — | "Categories containing resources which produce items, fluids, or items+fluids may be combined on the same entity, but may not work as expected..." |
| output_fluid_box / input_fluid_box | opt | FluidBox | — | |
| graphics_set / wet_mining_graphics_set | opt | MiningDrillGraphicsSet | — | (no description) |
| perceived_performance | opt | PerceivedPerformance | — | "Affects animation speed." |
| base_picture | opt | Sprite4Way | — | "Used by the pumpjack to have a static 4 way sprite." |
| effect_receiver | opt | EffectReceiver | — | |
| module_slots | opt | ItemStackIndex | — (none) | |
| quality_affects_module_slots | opt | boolean | false | adds `QualityPrototype::mining_drill_module_slots_bonus` (default = quality level) |
| allowed_effects | opt | EffectTypeLimitation | "All effects are allowed" | empty array → no modules or beacons |
| allowed_module_categories | opt | array ModuleCategoryID | all | |
| radius_visualisation_picture | opt | Sprite | — | "The sprite used to show the range of the mining drill." |
| circuit_wire_max_distance | opt | double | 0 | |
| draw_copper_wires / draw_circuit_wires | opt | boolean | true | |
| base_render_layer | opt | RenderLayer | "lower-object" | |
| resource_drain_rate_percent | opt | uint8 | 100 | "May not be `0` or larger than `100`." |
| shuffle_resources_to_mine | opt | boolean | false | |
| drops_full_belt_stacks | opt | boolean | false | |
| uses_force_mining_productivity_bonus | opt | boolean | true | |
| quality_affects_mining_radius | opt | boolean | false | adds `QualityPrototype::mining_drill_mining_radius_bonus` (default "Value of `level`") to resource_searching_radius |
| moving_sound / drilling_sound | opt | InterruptibleSound | — | InterruptibleSound = {sound, minimal_change_per_tick, stopped_sound, minimal_sound_duration_for_stopped_sound, fade_ticks} |
| drilling_sound_animation_start_frame / _end_frame | opt | uint16 | 0 | |
| monitor_visualization_tint | opt | Color | — | tint of the resources the drill reads when hovered while circuit-connected |
| circuit_connector | opt | tuple of 4 CircuitConnectorDefinition | — | |
| filter_count | opt | uint8 | 0 | "Maximum count of filtered resources in a mining drill is 5." |

Relevant inherited properties (quoted from `API:EntityPrototype.*`):
- `fast_replaceable_group` (string, default ""). "Entities with the same fast replaceable group can be configured as upgrades for each other in the upgrade planner."
- `next_upgrade` (EntityID). "The upgrade target entity needs to have the same bounding box, collision mask, and fast replaceable group as this entity. The upgrade target entity must have least 1 item that builds it that isn't hidden." The source entity "must be minable".
- `heating_energy` (Energy, default "0W").
- `icon`/`icons`/`icon_size` (icon_size default 64). "Either this or `icons` is mandatory for entities that have at least one of these flags active: "placeable-neutral"...".
- `surface_conditions`, `drawing_box_vertical_extension` (default 0.0), `tile_width`/`tile_height` ("calculated by the collision box ... rounded up").
- `integration_patch` and `integration_patch_render_layer` (EntityWithHealthPrototype, default "lower-object").

`API:UpgradeItemPrototype` (description): "For two entities to be upgrades of each other, the two entities must have the same fast replaceable group, the same collision box and the same collision mask."

### 6.1 MiningDrillGraphicsSet (API type), parent `WorkingVisualisations`

Own fields:
- `frozen_patch` (Sprite4Way)
- `reset_animation_when_frozen` (bool, default false)
- `circuit_connector_layer` (RenderLayer or CircuitConnectorLayer{north,east,south,west}, default "object")
- `circuit_connector_secondary_draw_order` (int8 or {north..west}, default 100)
- `drilling_vertical_movement_duration` (uint16, default 0)
- `animation_progress` (float, default 1)
- `water_reflection`

Inherited `WorkingVisualisations` fields:
- `animation` (Animation4Way), `idle_animation`, `always_draw_idle_animation`
- `default_recipe_tint`, `recipe_not_set_tint`, `states`
- `working_visualisations` (array of WorkingVisualisation)
- `shift_animation_waypoints` ({north,east,south,west}). "Only loaded if one of `shift_animation_waypoint_stop_duration` or `shift_animation_transition_duration` is not 0."
- `shift_animation_waypoint_stop_duration`, `shift_animation_transition_duration` (uint16)
- `status_colors` (StatusColors: disabled, full_output, idle, insufficient_input, low_power, no_minable_resources, no_power, working)

`WorkingVisualisation` fields used by drills:
- `render_layer`, `fadeout`, `synced_fadeout`, `constant_speed`, `always_draw`, `animated_shift`, `align_to_waypoint`, `mining_drill_scorch_mark`, `secondary_draw_order`, `light`
- `apply_tint`: "resource-color" | "input-fluid-base-color" | "input-fluid-flow-color" | "status" | "none" | "visual-state-color". "For "resource-color", the colors are specified via ResourceEntityPrototype::mining_visualisation_tint".
- `north_animation` .. `west_animation`, `north_position` .. `west_position`, `animation`
- `name`, `enabled_by_name`, `enabled_in_animated_shift_during_waypoint_stop` (default true), `enabled_in_animated_shift_during_transition` (default true), `frame_based_on_shift_animation_progress`
- `scorch_mark_fade_out_duration`, `scorch_mark_lifetime`, `scorch_mark_fade_in_frames`: "Only loaded, and mandatory if `mining_drill_scorch_mark` is `true`."

---

## 7. Resources

### 7.1 Resource categories

- `D/base/prototypes/categories/resource-category.lua:1-12` defines `basic-solid` and `basic-fluid`.
- `D/space-age/prototypes/categories/resource-category.lua:1-6` defines `hard-solid`. **This category exists only when space-age is loaded.**
- `API:ResourceEntityPrototype.category` defaults to `"basic-solid"`.

### 7.2 Base ore factory function (`D/base/prototypes/entity/resources.lua:13-65`), verbatim core

```lua
local function resource(resource_parameters, autoplace_parameters)
  return
  {
    type = "resource",
    name = resource_parameters.name,
    icon = "__base__/graphics/icons/" .. resource_parameters.name .. ".png",
    flags = {"placeable-neutral"},
    order="a-b-"..resource_parameters.order,
    tree_removal_probability = 0.8,
    tree_removal_max_distance = 32 * 32,
    minable = resource_parameters.minable or
    {
      mining_particle = resource_parameters.name .. "-particle",
      mining_time = resource_parameters.mining_time,
      result = resource_parameters.name
    },
    category = resource_parameters.category,
    ...
    collision_box = {{-0.1, -0.1}, {0.1, 0.1}},
    selection_box = {{-0.5, -0.5}, {0.5, 0.5}},
    autoplace = resource_autoplace.resource_autoplace_settings{ ... },
    stage_counts = {15000, 9500, 5500, 2900, 1300, 400, 150, 80},
    stages = { sheet = { filename = "__base__/graphics/entity/" .. name .. "/" .. name .. ".png", priority = "extra-high", size = 128, frame_count = 8, variation_count = 8, scale = 0.5 } },
    map_color = resource_parameters.map_color,
    mining_visualisation_tint = resource_parameters.mining_visualisation_tint,
    factoriopedia_simulation = resource_parameters.factoriopedia_simulation
  }
end
```

`resource_autoplace = require("resource-autoplace")` (:1) resolves to `D/core/lualib/resource-autoplace.lua`. The default collision mask for type "resource" is `{layers={resource=true}}` (`D/core/lualib/collision-mask-defaults.lua:187`).

### 7.3 Per-resource values

| resource | file:line | category | minable.mining_time | minable result | required_fluid / fluid_amount | mining_particle | mining_visualisation_tint | map_color |
|---|---|---|---|---|---|---|---|---|
| iron-ore | base resources.lua:75-92 | not set → "basic-solid" (API default) | 1 | "iron-ore" | — | "iron-ore-particle" (particles.lua:223) | `{r=0.895,g=0.965,b=1.000,a=1}` | `{0.415,0.525,0.580}` |
| copper-ore | :93-110 | → "basic-solid" | 1 | "copper-ore" | — | "copper-ore-particle" (particles.lua:230) | `{r=1.000,g=0.675,b=0.541,a=1}` | `{0.803,0.388,0.215}` |
| coal | :111-127 | → "basic-solid" | 1 | "coal" | — | "coal-particle" (particles.lua:319) | `{r=0.465,g=0.465,b=0.465,a=1}` | `{0,0,0}` |
| stone | :128-144 | → "basic-solid" | 1 | "stone" | — | "stone-particle" (particles.lua:311) | `{r=0.984,g=0.883,b=0.646,a=1}` | `{0.690,0.611,0.427}` |
| uranium-ore | :146-214 | not set → "basic-solid" | 2 | "uranium-ore" | `required_fluid = "sulfuric-acid"`, `fluid_amount = 10` | "stone-particle" | `{r=0.814,g=1.000,b=0.499,a=1}` | `{0, 0.7, 0}` |
| crude-oil (pumpjack) | :215-320 | "basic-fluid" | 1 | `results = {{type="fluid", name="crude-oil", amount_min=10, amount_max=10, probability=1}}` | — | — | — | `{0.78,0.2,0.77}` |
| tungsten-ore (SA) | space-age resources.lua:104-118 | "hard-solid" | 5 | "tungsten-ore" | — | "tungsten-ore-particle" (by factory, :47) | `{r=150/256,g=150/256,b=180/256,a=1}` | `{r=98/256,g=86/256,b=150/256,a=1}` |

Uranium, verbatim (:157-164):

```lua
    minable =
    {
      mining_particle = "stone-particle",
      mining_time = 2,
      result = "uranium-ore",
      fluid_amount = 10,
      required_fluid = "sulfuric-acid"
    },
```

It also has `stage_counts = {10000, 6330, 3670, 1930, 870, 270, 100, 50}` plus a `stages_effect` glow sheet (`blend_mode = "additive"`, `flags = {"light"}`), `effect_animation_period = 5` and the related fields (:178-211). `API:MinableProperties.fluid_amount`: "If this is > 0, this object cannot be mined by hand."

Mining with fluid needs the force flag. The tech `uranium-mining` (`D/base/prototypes/technology.lua:5069-5091`) has the effect `{type = "mining-with-fluid", modifier = true}`, and the runtime counterpart is `RT:LuaForce.mining_with_fluid` (boolean, RW). The base drills that have an `input_fluid_box` are electric and big. It is not stated explicitly in the sources that a drill without `input_fluid_box` cannot mine a `required_fluid` resource; this is an inference from vanilla design.

Crude oil extras (:215-230): `infinite = true, highlight = true, minimum = 60000, normal = 300000, infinite_depletion_amount = 10, resource_patch_search_radius = 12`, `collision_box = {{-1.4,-1.4},{1.4,1.4}}`.

### 7.4 ResourceEntityPrototype API highlights

`stage_counts` is REQUIRED. Other fields: `stages` ("At least one stage must be defined"), `infinite`, `highlight`, `minimum`, `normal`, `infinite_depletion_amount`, `resource_patch_search_radius` (default 3), `category` (default "basic-solid"), `tree_removal_probability`, `tree_removal_max_distance`, `cliff_removal_probability` (default 1.0), `mining_visualisation_tint`, `stages_effect`, `selection_priority` (default 40), `randomize_visual_position`, `map_grid`, `walking_sound`, `driving_sound`. `minable` is `MinableProperties` (`mining_time` REQUIRED; `results`/`result`/`count`, `fluid_amount`, `required_fluid`, `mining_particle`, `mining_trigger`).

---

## 8. Runtime: placing a resource and inspecting drills (runtime-api.json)

### 8.1 `LuaSurface.create_entity{...}`

`format.takes_table = true`. Common parameters: `name` (REQUIRED EntityID), `position` (REQUIRED MapPosition), `direction`, `mirror`, `quality`, `force` ("default is enemy"), `snap_to_grid`, `fast_replace`, `player`, `raise_built`, `create_build_effect_smoke`, `move_stuck_players`, `item`, and others. It returns `LuaEntity` or `nil` ("The created entity or `nil` if the creation failed").

Variant group `resource` (verbatim from the JSON):
- `amount` — optional `uint32` (no description; **the default value is not found in sources**)
- `enable_tree_removal` — optional boolean: "If colliding trees are removed normally for this resource entity based off the prototype tree removal values. Default is true."
- `enable_cliff_removal` — optional boolean: "If colliding cliffs are removed. Default is true."
- `snap_to_tile_center` — optional boolean: "If true, the resource entity will be placed to center of a tile as map generator would place it, otherwise standard non-resource grid alignment rules will apply. Default is true."

Variant group `mining-drill`: `filter` (BlueprintMiningDrillFilter), `control_behavior` (MiningDrillBlueprintControlBehavior).

Real usage in game data:
- `D/base/prototypes/tips-and-tricks-simulations.lua:1183-1187`:

```lua
    for x = -5.5, -3.5, 1 do
      for y = 0.5, 2.5, 1 do
        game.surfaces[1].create_entity{name = "iron-ore", amount = 500, position = {x, y}}
      end
    end
```

- same file :627-629: `game.surfaces[1].create_entity{name = "coal", position = {-5.5, -1.5}, amount = 123456}`
- `D/base/script/team-production/map_scripts.lua:158`: `surface.create_entity{name = name, position = position, amount = entity.amount}`

Test-bench snippet (built from the above; untested here):

```lua
local s = game.surfaces[1]
for x = -4, 4 do
  for y = -4, 4 do
    s.create_entity{name = "iron-ore", position = {x + 0.5, y + 0.5}, amount = 1000}
  end
end
local d = s.create_entity{name = "magnetics-mining-drill", position = {0.5, 0.5}, force = "player"}
-- verify: d.mining_area (BoundingBox), d.mining_target, d.status
```

### 8.2 Related runtime members

- `LuaEntity.amount` (uint32, RW, ResourceEntity): "Count of resource units contained."
- `LuaEntity.initial_amount` (RW): "`nil` if this is not an infinite resource."
- `LuaEntity.mining_area` (BoundingBox, R, MiningDrill): "Area in which this mining drill looks for resources to mine." **Use this to check the effective area of a modded radius.**
- `LuaEntity.mining_target` (R), `mining_progress` (RW), `bonus_mining_progress` (RW), `mining_drill_filter_mode` (RW)
- `LuaEntity.drop_position` (RW): "Mining drills and crafting machines can't have their drop position changed". `drop_target` (RW).
- `LuaEntityPrototype.mining_speed`, `mining_drill_radius`, `get_mining_drill_radius(quality?)`, `resource_categories` (dictionary name→true), `resource_category` ("During data stage, this property is named "category""), `vector_to_place_result`, `resource_drain_rate_percent`, `uses_force_mining_productivity_bonus`, `quality_affects_mining_radius`, `infinite_resource`, `minimum_resource_amount`, `normal_resource_amount`, `infinite_depletion_resource_amount`
- `LuaForce.mining_drill_productivity_bonus` (RW), `LuaForce.mining_with_fluid` (RW)
- `LuaSurface.get_resource_counts()` → dictionary string→uint32

---

## 9. How to make the Magnetics drill by deepcopying electric-mining-drill

### 9.1 What to keep, what to change

A 3x3 drill with a bigger area can keep the whole visual and fluid setup of the electric drill. Nothing in `graphics_set`, `wet_mining_graphics_set`, `integration_patch`, `input_fluid_box` or `circuit_connector` depends on `resource_searching_radius`. All sprite positions, `*_position` offsets and `shift_animation_waypoints` are relative to the entity (see 2.3 and 2.4). The waypoint comments say "Bounds -0.5 - 0.6" etc., which is the head movement inside the body.

Keep unchanged, for a 3x3 footprint:
- `collision_box` / `selection_box`: required for fast-replace and upgrade with electric-mining-drill. The rule from `API:UpgradeItemPrototype`: same fast replaceable group, collision box and collision mask.
- `vector_to_place_result = {0, -1.85}` (the output point just outside the north edge, 1.5)
- `input_fluid_box`: needed if the drill should mine uranium. The drill must also be allowed by `LuaForce.mining_with_fluid` via the `uranium-mining` tech.
- `graphics_set`, `wet_mining_graphics_set`, `integration_patch`, `radius_visualisation_picture`, `circuit_connector`, `circuit_wire_max_distance`, `corpse`, `dying_explosion`, sounds, `fast_replaceable_group = "mining-drill"`

Change:
- `name`, `minable.result`, `icon`/`icons`
- `mining_speed`, `energy_usage`, `resource_searching_radius`, `module_slots`, `max_health`, and optionally `energy_source.emissions_per_minute`
- `resource_categories`: add `"hard-solid"` only if that category exists (Space Age); see 9.3
- optionally `resource_searching_offset`, `resource_drain_rate_percent` (1..100), `quality_affects_mining_radius`, `quality_affects_module_slots`, `filter_count` (≤5), `drops_full_belt_stacks`

### 9.2 Area arithmetic

The anchor points from the API text are: 2.49 → 5x5, 0.99 → 2x2, and "making it 2.5 and 1.0 gives it another block radius". The vanilla big drill uses 6.49 on a 5x5 body (13x13 by the same rule).

Rule derived from these anchors (not quoted anywhere): for an odd-size body centered on a tile center, `r = n + 0.49` gives a `(2n+1) x (2n+1)` area. So:
- 2.49 → 5x5 (vanilla)
- 3.49 → 7x7
- 4.49 → 9x9
- 5.49 → 11x11

Avoid exact `.5` values (per the API note). Confirm on the test bench with `LuaEntity.mining_area`.

Quality: if you set `quality_affects_mining_radius = true`, the radius grows by `QualityPrototype.mining_drill_mining_radius_bonus`, which defaults to the level. Levels are 1/2/3/5 (`D/quality/prototypes/quality.lua:6,20,34,48`), so legendary would give 3.49 + 5 = 8.49 → 17x17. The vanilla electric drill does not set this flag.

### 9.3 Can the mining area exceed 5x5 without visual issues?

The engine allows it. Evidence:
- The vanilla `big-mining-drill` mines a 13x13 area (6.49) from a 5x5 body.
- `API:MiningDrillPrototype.resource_searching_radius` states no upper limit (**no maximum found in sources**).

Visual components that relate to the area:
- `radius_visualisation_picture`: the electric drill (5x5 area) and the big drill (13x13 area) both use a 10x10-px image (`mining-drill.lua:1556-1561`, `big-mining-drill.lua:650-655`). So the picture is not sized to the area; the engine fits it to whatever area the radius gives. This is an inference from the two vanilla uses. The exact rendering rule (stretch vs tile) is **not found in sources**.
- `monitor_visualization_tint`: tints the resources being read. The API text covers "the resource in the mining area of the drill".
- The dust and scorch visualisations sit at fixed offsets around the body and do not scale with the area.

So no drill sprite needs changing for a 7x7 or 9x9 area. The only visible differences are the radius overlay and the dust colour (resource-color).

Non-visual caveats (not claimed from sources as bugs): overlapping areas between neighbouring drills, and higher total output per drill.

### 9.4 Code template (data stage)

```lua
-- Magnetics/data.lua  (or data-updates.lua, see note on load order)
local util = require("util")   -- same call as D/space-age/data.lua:1 ("require "util""); table.deepcopy is defined in D/core/lualib/util.lua:6

local NAME = "magnetics-mining-drill"

local base = data.raw["mining-drill"]["electric-mining-drill"]
local drill = table.deepcopy(base)
drill.name = NAME
drill.icon = nil
drill.icons = {{icon = "__base__/graphics/icons/electric-mining-drill.png", icon_size = 64, tint = {r = 0.55, g = 0.70, b = 1.0, a = 1}}}  -- IconData.tint (API)
drill.minable = {mining_time = 0.3, result = NAME}
drill.max_health = 400
drill.mining_speed = 1.0                 -- 2x electric
drill.energy_usage = "180kW"
drill.resource_searching_radius = 3.49   -- 7x7 (derived rule, verify with LuaEntity.mining_area)
drill.module_slots = 4
drill.next_upgrade = nil
-- keep: collision_box, selection_box, vector_to_place_result, input_fluid_box, graphics_set,
--       wet_mining_graphics_set, integration_patch, radius_visualisation_picture, circuit_connector,
--       fast_replaceable_group = "mining-drill", corpse, dying_explosion

-- Optional Space Age category, guarded because "hard-solid" is only defined by space-age:
if data.raw["resource-category"]["hard-solid"] then
  drill.resource_categories = {"basic-solid", "hard-solid"}
end

-- Optional visual distinction: tint body sprites but not shadows/glow and not layers that get runtime tint
local function tint_sprites(t, tint)
  if type(t) ~= "table" then return end
  if t.apply_tint then return end                    -- status LEDs / resource-color dust keep their runtime tint
  if (t.filename or t.filenames or t.stripes) and not (t.draw_as_shadow or t.draw_as_glow or t.draw_as_light) then
    t.tint = tint                                    -- SpriteParameters.tint (API)
  end
  for k, v in pairs(t) do
    if k ~= "tint" and type(v) == "table" then tint_sprites(v, tint) end
  end
end
local TINT = {r = 0.7, g = 0.8, b = 1.0, a = 1}
tint_sprites(drill.graphics_set, TINT)
tint_sprites(drill.wet_mining_graphics_set, TINT)

local item = table.deepcopy(data.raw.item["electric-mining-drill"])
item.name = NAME
item.icon = nil
item.icons = drill.icons
item.place_result = NAME
item.order = "a[items]-b[electric-mining-drill]-m[magnetics]"

data:extend({
  drill,
  item,
  {
    type = "recipe",
    name = NAME,
    energy_required = 4,
    enabled = false,
    ingredients =
    {
      {type = "item", name = "electric-mining-drill", amount = 1},
      -- {type = "item", name = "<magnetics-coil>", amount = N},
    },
    results = {{type = "item", name = NAME, amount = 1}}
  },
  {
    type = "technology",
    name = NAME,
    icon = "__base__/graphics/technology/electric-mining-drill.png",
    icon_size = 256,
    effects = {{type = "unlock-recipe", recipe = NAME}},
    prerequisites = {"electric-mining-drill"},
    unit = {count = 100, ingredients = {{"automation-science-pack", 1}, {"logistic-science-pack", 1}}, time = 30}
  }
})

-- Optional: make the upgrade planner default electric -> magnetics.
-- Valid only because box, collision mask (both default building()) and fast_replaceable_group match (API:EntityPrototype.next_upgrade).
-- This modifies a vanilla entity; decide deliberately.
-- data.raw["mining-drill"]["electric-mining-drill"].next_upgrade = NAME
```

### 9.5 Compatibility notes (base only vs Space Age / Quality / Elevated Rails)

- **heating_energy.** Space Age sets `heating_energy = "100kW"` on the electric drill in `space-age/base-data-updates.lua:120`, which runs from `space-age/data.lua` ("require("base-data-updates")" near the end of that file). A deepcopy inherits this only if it runs after space-age's data.lua. Mod load order and dependency rules are **not found in these sources**. The safe route is to set `drill.heating_energy` explicitly when `mods["space-age"]`, or to declare an optional dependency on space-age and verify the order on the headless bench.
- **hard-solid** exists only with Space Age (`space-age/prototypes/categories/resource-category.lua`), so guard it as in 9.4. Tungsten ore is also Space Age only (`space-age/prototypes/entity/resources.lua:104-118`).
- **Quality:** `quality/data-updates.lua` auto-generates recycling for all recipes present by then. Pumpjack `allowed_effects` is restricted by quality. The vanilla electric drill has no `allowed_effects`, so the API default is "All effects are allowed", and the deepcopy inherits that.
- **Frozen visuals:** in Space Age the electric drill gets no `frozen_patch` (only the pumpjack does, `base-frozen-graphics.lua:317-328`). The deepcopy therefore has none either, while `heating_energy > 0` makes it freezable (API text).
- **Elevated Rails:** `grep` for mining-drill or resource in `D/elevated-rails` found nothing relevant.

---

## 10. Not found in sources (explicitly)

- The condition that switches between `graphics_set` and `wet_mining_graphics_set` (the API description is empty).
- How `radius_visualisation_picture` is scaled or tiled over the area.
- An upper limit for `resource_searching_radius`.
- The default `amount` for `create_entity{name=<resource>}` (the parameter has no description).
- Mod load-order rules (data.lua vs data-updates.lua across mods, optional dependencies).
- The exact mining-rate formula with productivity (the API refers to the wiki).
- Whether PNG paths are validated by the headless server (the PNGs are absent in this build).
