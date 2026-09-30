# Crafting machines and recipes in Factorio 2.0.77: a source-backed reference

Scope: stone-furnace, steel-furnace, electric-furnace, assembling-machine-1/2/3, chemical-plant and centrifuge (base), plus foundry, electromagnetic-plant and cryogenic-plant (space-age). The report also covers the 2.0 recipe format, recipe categories, and the deepcopy-and-tint pattern.

Sources (all 2.0.77, checked from `base/info.json` and `space-age/info.json`: `"version": "2.0.77"`):
- `D` = `/opt/factorio/data`, so `D/base/prototypes/entity/entities.lua` is written `base/…/entities.lua`.
- `API` = `/opt/factorio-api/prototype-api.json` (`application_version: 2.0.77`, `api_version: 6`). Entries are cited as `API: Type::property`.
- `CL` = `D/changelog.txt`, cited by line number. The first 2.0 entry is "Version: 2.0.7" at CL:2854, and CL:3678+ is 1.1.x.
- The headless build has **no PNG files at all**: `find D -name '*.png' | wc -l` gives 0. Sprite `.lua` metadata files (for `util.sprite_load`) are present, e.g. `space-age/graphics/entity/foundry/foundry-main.lua`.

I checked every property below in the files. Where the sources say nothing, the text says **"not found in sources"**.

---

## 1. Summary table

| entity (file:line of `name =`) | type | size (collision / selection) | crafting_speed | energy_usage | energy_source type, emissions | module_slots | allowed_effects | fast_replaceable_group / next_upgrade | max_health |
|---|---|---|---|---|---|---|---|---|---|
| stone-furnace (base/…/entities.lua:1018) | `furnace` | 2×2: `{{-0.7,-0.7},{0.7,0.7}}` / `{{-0.8,-1},{0.8,1}}` (1064-1065) | 1 | "90kW" | burner, `{ pollution = 2 }` | (none → default 0) | `{"speed","consumption","pollution"}` + `effect_receiver = {uses_module_effects=false, uses_beacon_effects=false, uses_surface_effects=true}` (1033-1034) | "furnace" / "steel-furnace" (1022-1023) | 200 |
| steel-furnace (4741) | `furnace` | 2×2, same boxes (4777-4778) | 2 | "90kW" | burner, `{ pollution = 4 }` | (0) | same as stone (4754-4755) | "furnace" / none | 300 |
| electric-furnace (4301) | `furnace` | 3×3: `{{-1.2,-1.2},{1.2,1.2}}` / `{{-1.5,-1.5},{1.5,1.5}}` | 2 | "180kW" | electric, `{ pollution = 1 }` | 2 | consumption, speed, productivity, pollution, quality (4327) | "furnace" / none | 350 |
| assembling-machine-1 (3134) | `assembling-machine` | 3×3 (3149-3150) | 0.5 | "75kW" | electric, `{ pollution = 4 }` | (0) | `{"speed","consumption","pollution"}` + effect_receiver with module and beacon effects off (3198-3199) | "assembling-machine" / "assembling-machine-2" | 300 |
| assembling-machine-2 (3210) | `assembling-machine` | 3×3 | 0.75 | "150kW" | electric, `{ pollution = 3 }` | 2 | 5 effects (3303) | "assembling-machine" / "assembling-machine-3" | 350 |
| assembling-machine-3 (5391) | `assembling-machine` | 3×3 | 1.25 | "375kW" | electric, `{ pollution = 2 }` | 4 | 5 effects (5485) | "assembling-machine" / none | 400 |
| chemical-plant (8274) | `assembling-machine` | 3×3 | 1 | "210kW" | electric, `{ pollution = 4 }` | 3 | 5 effects (8290) | "chemical-plant" / none | 300 |
| centrifuge (8798) | `assembling-machine` | 3×3 | 1 | "350kW" | electric, `{ pollution = 4 }` | 2 | 5 effects (8974) | "centrifuge" / none | 350 |
| foundry (space-age/…/entities.lua:1130) | `assembling-machine` | 5×5: `{{-2.2,-2.2},{2.2,2.2}}` / `{{-2.5,-2.5},{2.5,2.5}}` | 4 | "2500kW" | electric, `{ pollution = 6 }` | 4 | 5 effects; `effect_receiver = { base_effect = { productivity = 0.5 }}` | "foundry" / none | 350 |
| electromagnetic-plant (1692) | `assembling-machine` | 4×4: `{{-1.7,-1.7},{1.7,1.7}}` / `{{-2,-2},{2,2}}` | 2 | "2000kW" | electric, `{ pollution = 4 }` | 5 | 5 effects; `base_effect = { productivity = 0.5 }` | "electromagnetic-plant" / none | 350 |
| cryogenic-plant (1949) | `assembling-machine` | 5×5: `{{-2.4,-2.4},{2.4,2.4}}` / `{{-2.5,-2.5},{2.5,2.5}}` | 2 | "1500kW" | electric, `{ pollution = 6 }` | 8 | 5 effects | "cryogenic-plant" / none | 350 |

"5 effects" means `{"consumption", "speed", "productivity", "pollution", "quality"}`. These base machines list `"quality"` even without the quality mod (base/…/entities.lua:3303, 4327, 5485, 8290, 8974).

Furnace inventories: all three vanilla furnaces set `result_inventory_size = 1` and `source_inventory_size = 1` (stone 1068/1071, steel 4781/4784, electric 4329/4332). The quality mod's `recycler` is also a `furnace` and uses `result_inventory_size = 12`, `source_inventory_size = 1` (quality/prototypes/entity/entity.lua:48-51). API: `FurnacePrototype::source_inventory_size` says "The number of input slots, but not more than 1."

Electric energy sources: all use `usage_priority = "secondary-input"` and set no `drain`. API `CraftingMachinePrototype::energy_source`: "When using an electric energy source and `drain` is not specified, it will be set to `energy_usage ÷ 30` automatically."

---

## 2. Per-machine details (verbatim where structure matters)

### 2.1 stone-furnace (base/prototypes/entity/entities.lua:1016-1186)

```lua
  {
    type = "furnace",
    name = "stone-furnace",
    icon = "__base__/graphics/icons/stone-furnace.png",
    flags = {"placeable-neutral", "placeable-player", "player-creation"},
    minable = {mining_time = 0.2, result = "stone-furnace"},
    fast_replaceable_group = "furnace",
    next_upgrade = "steel-furnace",
    circuit_wire_max_distance = furnace_circuit_wire_max_distance,
    circuit_connector = circuit_connector_definitions["stone-furnace"],
    max_health = 200,
    corpse = "stone-furnace-remnants",
    dying_explosion = "stone-furnace-explosion",
    ...
    allowed_effects = {"speed", "consumption", "pollution"},
    effect_receiver = {uses_module_effects = false, uses_beacon_effects = false, uses_surface_effects = true},
    impact_category = "stone",
    icon_draw_specification = {scale = 0.66, shift = {0, -0.1}},
    ...
    collision_box = {{-0.7, -0.7}, {0.7, 0.7}},
    selection_box = {{-0.8, -1}, {0.8, 1}},
    damaged_trigger_effect = hit_effects.rock(),
    crafting_categories = {"smelting"},
    result_inventory_size = 1,
    energy_usage = "90kW",
    crafting_speed = 1,
    source_inventory_size = 1,
    energy_source =
    {
      type = "burner",
      fuel_categories = {"chemical"},
      effectivity = 1,
      fuel_inventory_size = 1,
      emissions_per_minute = { pollution = 2 },
      light_flicker = { color = {0,0,0}, minimum_intensity = 0.6, maximum_intensity = 0.95 },
      smoke = { { name = "smoke", deviation = {0.1, 0.1}, frequency = 5, position = {0.0, -0.8},
                  starting_vertical_speed = 0.08, starting_frame_deviation = 60 } }
    },
    graphics_set = { animation = { layers = { <main>, <shadow draw_as_shadow=true> } },
                     working_visualisations = {...}, water_reflection = {...} }
  },
```

The graphics are described in section 7.3.

### 2.2 steel-furnace (4739-4914)
It matches stone-furnace except: `max_health = 300`, `impact_category = "metal"`, fire resistance 100, `crafting_speed = 2`, burner `emissions_per_minute = { pollution = 4 }` (4790), smoke at `position = {0.7, -1.2}`, `frequency = 10`, and **no `next_upgrade`**. `circuit_connector = circuit_connector_definitions["steel-furnace"]`.

### 2.3 electric-furnace (4299-4469)
```lua
    type = "furnace",
    name = "electric-furnace",
    minable = {mining_time = 0.2, result = "electric-furnace"},
    fast_replaceable_group = "furnace",
    circuit_wire_max_distance = furnace_circuit_wire_max_distance,
    circuit_connector = circuit_connector_definitions["electric-furnace"],
    max_health = 350,
    corpse = "electric-furnace-remnants",
    dying_explosion = "electric-furnace-explosion",
    collision_box = {{-1.2, -1.2}, {1.2, 1.2}},
    selection_box = {{-1.5, -1.5}, {1.5, 1.5}},
    module_slots = 2,
    icon_draw_specification = {shift = {0, -0.1}},
    icons_positioning =
    {
      {inventory_index = defines.inventory.furnace_modules, shift = {0, 0.8}}
    },
    allowed_effects = {"consumption", "speed", "productivity", "pollution", "quality"},
    crafting_categories = {"smelting"},
    result_inventory_size = 1,
    crafting_speed = 2,
    energy_usage = "180kW",
    source_inventory_size = 1,
    energy_source =
    {
      type = "electric",
      usage_priority = "secondary-input",
      emissions_per_minute = { pollution = 1 }
    },
```
It shares `fast_replaceable_group = "furnace"` with the 2×2 furnaces even though its size is different.

### 2.4 assembling-machine-1 (3132-3205)
```lua
    type = "assembling-machine",
    name = "assembling-machine-1",
    icon = "__base__/graphics/icons/assembling-machine-1.png",
    flags = {"placeable-neutral", "placeable-player", "player-creation"},
    minable = {mining_time = 0.2, result = "assembling-machine-1"},
    max_health = 300,
    corpse = "assembling-machine-1-remnants",
    dying_explosion = "assembling-machine-1-explosion",
    icon_draw_specification = {shift = {0, -0.3}},
    resistances = { { type = "fire", percent = 70 } },
    collision_box = {{-1.2, -1.2}, {1.2, 1.2}},
    selection_box = {{-1.5, -1.5}, {1.5, 1.5}},
    damaged_trigger_effect = hit_effects.entity(),
    fast_replaceable_group = "assembling-machine",
    next_upgrade = "assembling-machine-2",
    circuit_wire_max_distance = assembling_machine_circuit_wire_max_distance,
    circuit_connector = circuit_connector_definitions["assembling-machine"],
    alert_icon_shift = util.by_pixel(0, -12),
    graphics_set = { animation = { layers = { <main 32 frames>, <shadow> } } },
    crafting_categories = {"crafting", "basic-crafting", "advanced-crafting"},
    crafting_speed = 0.5,
    energy_source =
    {
      type = "electric",
      usage_priority = "secondary-input",
      emissions_per_minute = { pollution = 4 }
    },
    energy_usage = "75kW",
    ...
    allowed_effects = {"speed", "consumption", "pollution"},
    effect_receiver = {uses_module_effects = false, uses_beacon_effects = false, uses_surface_effects = true},
```
assembling-machine-1 has no `fluid_boxes` and no `module_slots` (default 0 per `API: CraftingMachinePrototype::module_slots`).

### 2.5 assembling-machine-2 (3208-3304). This is the reference for 3×3 fluid boxes.
```lua
    fluid_boxes =
    {
      {
        production_type = "input",
        pipe_picture = assembler2pipepictures(),
        pipe_covers = pipecoverspictures(),
        volume = 1000,
        pipe_connections = {{ flow_direction="input", direction = defines.direction.north, position = {0, -1} }},
        secondary_draw_orders = { north = -1 }
      },
      {
        production_type = "output",
        pipe_picture = assembler2pipepictures(),
        pipe_covers = pipecoverspictures(),
        volume = 1000,
        pipe_connections = {{ flow_direction="output", direction = defines.direction.south, position = {0, 1} }},
        secondary_draw_orders = { north = -1 }
      }
    },
    fluid_boxes_off_when_no_fluid_recipe = true,
    ...
    fast_replaceable_group = "assembling-machine",
    next_upgrade = "assembling-machine-3",
    crafting_categories = {"basic-crafting", "crafting", "advanced-crafting", "crafting-with-fluid"},
    crafting_speed = 0.75,
    energy_source = { type = "electric", usage_priority = "secondary-input", emissions_per_minute = { pollution = 3 } },
    energy_usage = "150kW",
    module_slots = 2,
    allowed_effects = {"consumption", "speed", "productivity", "pollution", "quality"}
```

### 2.6 assembling-machine-3 (5389-5486)
It has the same fluid_boxes as assembling-machine-2 but uses `pipe_picture = assembler3pipepictures()`. It also sets `drawing_box_vertical_extension = 0.2`, `graphics_set.animation_progress = 0.5`, `crafting_speed = 1.25`, `energy_usage = "375kW"`, `emissions_per_minute = { pollution = 2 }`, `module_slots = 4`, the 5 effects, and has **no next_upgrade**.

### 2.7 chemical-plant (8272-8535)
```lua
    type = "assembling-machine",
    name = "chemical-plant",
    minable = {mining_time = 0.1, result = "chemical-plant"},
    fast_replaceable_group = "chemical-plant",
    max_health = 300,
    corpse = "chemical-plant-remnants",
    dying_explosion = "chemical-plant-explosion",
    icon_draw_specification = {shift = {0, -0.3}},
    circuit_wire_max_distance = assembling_machine_circuit_wire_max_distance,
    circuit_connector = circuit_connector_definitions["chemical-plant"],
    collision_box = {{-1.2, -1.2}, {1.2, 1.2}},
    selection_box = {{-1.5, -1.5}, {1.5, 1.5}},
    drawing_box_vertical_extension = 0.4,
    module_slots = 3,
    allowed_effects = {"consumption", "speed", "productivity", "pollution", "quality"},
    graphics_set = { animation = make_4way_animation_from_spritesheet({ layers = {...} }), working_visualisations = {...} },
    crafting_speed = 1,
    energy_source = { type = "electric", usage_priority = "secondary-input", emissions_per_minute = { pollution = 4 } },
    energy_usage = "210kW",
    crafting_categories = {"chemistry"},
    fluid_boxes =
    {
      { production_type = "input",  pipe_covers = pipecoverspictures(), volume = 1000,
        pipe_connections = { { flow_direction="input", direction = defines.direction.north, position = {-1, -1} } } },
      { production_type = "input",  pipe_covers = pipecoverspictures(), volume = 1000,
        pipe_connections = { { flow_direction="input", direction = defines.direction.north, position = {1, -1} } } },
      { production_type = "output", pipe_covers = pipecoverspictures(), volume = 100,
        pipe_connections = { { flow_direction = "output", direction = defines.direction.south, position = {-1, 1} } } },
      { production_type = "output", pipe_covers = pipecoverspictures(), volume = 100,
        pipe_connections = { { flow_direction = "output", direction = defines.direction.south, position = {1, 1} } } }
    },
```
(The fluid boxes are condensed from 8465-8518 with values unchanged. No `pipe_picture`, and no `fluid_boxes_off_when_no_fluid_recipe`.)

### 2.8 centrifuge (8796-8980)
`fast_replaceable_group = "centrifuge"`, `drawing_box_vertical_extension = 0.7`, `crafting_categories = {"centrifuging"}`, `crafting_speed = 1`, `energy_usage = "350kW"`, `module_slots = 2`, the 5 effects. It has no fluid boxes. The graphics use **`idle_animation` with `always_draw_idle_animation = true` and no `animation` key** (8821-8824).

### 2.9 foundry (space-age/prototypes/entity/entities.lua:1128-1246)
```lua
    type = "assembling-machine",
    name = "foundry",
    icon = "__space-age__/graphics/icons/foundry.png",
    flags = {"placeable-neutral","player-creation"},
    minable = {mining_time = 0.2, result = "foundry"},
    fast_replaceable_group = "foundry",
    max_health = 350,
    corpse = "foundry-remnants",
    dying_explosion = "foundry-explosion",
    circuit_wire_max_distance = assembling_machine_circuit_wire_max_distance,
    circuit_connector = circuit_connector_definitions["foundry"],
    collision_box = {{-2.2, -2.2}, {2.2, 2.2}},
    selection_box = {{-2.5, -2.5}, {2.5, 2.5}},
    heating_energy = "300kW",
    drawing_box_vertical_extension = 1.3,
    effect_receiver = { base_effect = { productivity = 0.5 }},
    module_slots = 4,
    icon_draw_specification = {scale = 2, shift = {0, -0.3}},
    icons_positioning =
    {
      {inventory_index = defines.inventory.assembling_machine_modules, shift = {0, 1.25}}
    },
    allowed_effects = {"consumption", "speed", "productivity", "pollution", "quality"},
    crafting_categories = {"metallurgy", "pressing", "crafting-with-fluid-or-metallurgy", "metallurgy-or-assembling"},
    crafting_speed = 4,
    energy_source = { type = "electric", usage_priority = "secondary-input", emissions_per_minute = { pollution = 6 } },
    energy_usage = "2500kW",
    perceived_performance = {minimum = 0.25, maximum = 20},
    graphics_set = require("__space-age__.prototypes.entity.foundry-pictures").graphics_set,
```
Fluid boxes: 2 inputs at `position = {-1, 2}` and `{1, 2}` facing south, and 2 outputs at `{-1,-2}` and `{1,-2}` facing north. Inputs have volume 1000 and outputs volume 100. They use `pipe_picture = util.empty_sprite()`, `always_draw_covers = false`, and `enable_working_visualisations = { "input-pipe" }` / `{ "output-pipe" }`. The pipes are drawn by working visualisations named "input-pipe" and "output-pipe" (see 7.3). `fluid_boxes_off_when_no_fluid_recipe = true`.

### 2.10 electromagnetic-plant (1690-1776)
```lua
    flags = {"placeable-neutral", "placeable-player", "player-creation"},
    minable = {mining_time = 0.1, result = "electromagnetic-plant"},
    fast_replaceable_group = "electromagnetic-plant",
    heating_energy = "100kW",
    effect_receiver = { base_effect = { productivity = 0.5 }},
    collision_box = {{-1.7, -1.7}, {1.7, 1.7}},
    selection_box = {{-2, -2}, {2, 2}},
    fluid_boxes =
    {
      {
        production_type = "input",
        pipe_picture = require("__space-age__.prototypes.entity.electromagnetic-plant-pictures").pipe_pictures,
        pipe_picture_frozen = require("__space-age__.prototypes.entity.electromagnetic-plant-pictures").pipe_pictures_frozen,
        pipe_covers = pipecoverspictures(),
        volume = 200,
        secondary_draw_orders = { north = -1 },
        pipe_connections = {{ flow_direction="input-output", direction = defines.direction.west, position = {-1.5, 0.5} }}
      },
      ... input east {1.5,-0.5}; output (volume 100) south {0.5,1.5}; output north {-0.5,-1.5}; all flow_direction="input-output"
    },
    fluid_boxes_off_when_no_fluid_recipe = true,
    forced_symmetry = "horizontal",
    perceived_performance = {minimum = 0.25, maximum = 10},
    graphics_set = require("__space-age__.prototypes.entity.electromagnetic-plant-pictures").graphics_set,
    crafting_speed = 2,
    crafting_categories = {"electromagnetics", "electronics", "electronics-with-fluid", "electronics-or-assembling"},
    energy_source = { type = "electric", usage_priority = "secondary-input", emissions_per_minute = { pollution = 4 } },
    energy_usage = "2000kW",
    module_slots = 5,
    icons_positioning = { {inventory_index = defines.inventory.furnace_modules, shift = {0, 1}} },
    allowed_effects = {"consumption", "speed", "productivity", "pollution", "quality"},
    water_reflection = require("__space-age__.prototypes.entity.electromagnetic-plant-pictures").water_reflection,
```
On an even-sized (4×4) entity the connection positions are half-integers. The electromagnetic-plant uses `flow_direction="input-output"` even on boxes with `production_type` input or output.

### 2.11 cryogenic-plant (1947-2065)
`flags = {"placeable-neutral","player-creation"}`, `heating_energy = "100kW"`, `drawing_box_vertical_extension = 0.4`, `module_slots = 8`, `icons_positioning = { {inventory_index = defines.inventory.furnace_modules, shift = {0, 0.95}, max_icons_per_row = 4} }`, `icon_draw_specification = {scale = 2, shift = {0, -0.3}}`, `crafting_categories = {"cryogenics", "chemistry-or-cryogenics", "cryogenics-or-assembling"}`, `crafting_speed = 2`, `energy_usage = "1500kW"`, `emissions_per_minute = { pollution = 6 }`. There are 6 fluid boxes: 3 inputs (volume 1000) at `{-2,2}`, `{0,2}`, `{2,2}` facing south, and 3 outputs (volume 100) at `{-2,-2}`, `{0,-2}`, `{2,-2}` facing north. The middle ones set a custom `pipe_picture` and `always_draw_covers = true -- fighting against FluidBoxPrototype::always_draw_covers crazy default`. `water_reflection` reuses the foundry reflection sprite (2053-2059).

### 2.12 Items that place these machines (minable / placeable_by)
**No crafting machine uses `placeable_by`.** In the whole data tree `placeable_by` appears only on rails, elevated rails and tiles: base/…/trains.lua:162, elevated-rails/…/elevated-rails.lua:145+, base/prototypes/tile/tiles.lua:2251+. Each machine uses `minable.result = "<same name>"` together with an item that has `place_result`. For example (base/prototypes/item.lua:420-433):
```lua
  {
    type = "item",
    name = "assembling-machine-1",
    icon = "__base__/graphics/icons/assembling-machine-1.png",
    subgroup = "production-machine",
    color_hint = { text = "1" },
    order = "a[assembling-machine-1]",
    inventory_move_sound = item_sounds.mechanical_inventory_move,
    pick_sound = item_sounds.mechanical_inventory_pickup,
    drop_sound = item_sounds.mechanical_inventory_move,
    place_result = "assembling-machine-1",
    stack_size = 50,
    random_tint_color = item_tints.iron_rust
  },
```
Item lines: stone-furnace item.lua:231 (subgroup "smelting-machine", stack 50), steel-furnace 901, electric-furnace 758, AM2 437, AM3 1340, chemical-plant 1973 (stack 10), centrifuge 2300. Space-age: foundry space-age/prototypes/item.lua:536 (subgroup "smelting-machine", stack 20, `default_import_location = "vulcanus"`, `weight = 200 * kg`), electromagnetic-plant 1377 ("production-machine", stack 20, "fulgora"), cryogenic-plant 1581.

`API: EntityPrototype::placeable_by` is `ItemToPlace | array[ItemToPlace]` with `{item, count}`. It "Determines which item is picked when "Q" (smart pipette) is used… which item and item amount is needed in a blueprint". `API: MinableProperties`: `mining_time` (mandatory), `result` (ItemID, "Only loaded if `results` is not defined"), `count` (default 1), and `results: array[ProductPrototype]`.

### 2.13 corpse / dying_explosion
Every machine points to `<name>-remnants` (type `corpse`) and `<name>-explosion` (type `explosion`). Where they are defined: base/prototypes/entity/remnants.lua (AM1 262, AM2 289, AM3 3042, stone 824, steel 852, electric-furnace 880, chemical-plant 2918, centrifuge 2487); base/prototypes/entity/explosions.lua (stone 494, steel 2206, electric 2269, AM1 2333, AM2 2420, AM3 6323, chem 6519, centrifuge 6607); space-age/prototypes/entity/remnants.lua (foundry 196, EM plant 480, cryo 507) and space-age/…/explosions.lua (730, 1139, 1234). A copied machine can keep pointing at the vanilla corpse and explosion. `API: EntityWithHealthPrototype::corpse` is `EntityID | array[EntityID]` and `dying_explosion` is `ExplosionDefinition | array[ExplosionDefinition]`.

---

## 3. What Space Age (and quality) change on the base machines

`space-age/data.lua:65` runs `require("base-data-updates")` at the end of Space Age's **data.lua** stage. Its effects:

- **Crafting categories are overwritten with `=`, not appended** (space-age/base-data-updates.lua:80-84):
```lua
data.raw["assembling-machine"]["assembling-machine-1"].crafting_categories = {"crafting", "basic-crafting", "advanced-crafting", "electronics", "pressing"}
data.raw["assembling-machine"]["assembling-machine-2"].crafting_categories = {"basic-crafting", "crafting", "advanced-crafting", "crafting-with-fluid", "electronics", "electronics-with-fluid", "pressing", "metallurgy-or-assembling", "organic-or-hand-crafting", "organic-or-assembling", "electronics-or-assembling", "cryogenics-or-assembling", "crafting-with-fluid-or-metallurgy"}
data.raw["assembling-machine"]["assembling-machine-3"].crafting_categories = { ...same as AM2... }
data.raw["assembling-machine"]["chemical-plant"].crafting_categories = {"chemistry", "chemistry-or-cryogenics", "organic-or-chemistry"}
```
  **Consequence for a mod:** if your data.lua does `table.insert(data.raw["assembling-machine"]["assembling-machine-2"].crafting_categories, "magnetics")` and it runs *before* Space Age's data.lua, Space Age wipes the insertion. Put such inserts in `data-updates.lua` (see 10.5 for the evidence on stage ordering).
- The character's crafting categories are also replaced: `{"crafting", "electronics", "pressing", "recycling-or-hand-crafting", "organic-or-hand-crafting", "organic-or-assembling"}` (line 75). Base alone uses `crafting_categories = {"crafting"}` (base/…/entities.lua:709).
- `heating_energy` is set to 100kW on electric-furnace, AM1-3, chemical-plant and centrifuge (lines 88-99). The stone and steel furnace lines are commented out (86-87).
- `surface_conditions = ten_pressure_condition()` (`{{property="pressure", min=10}}`) is set on stone-furnace and steel-furnace (184, 186).
- Many base recipes are recategorised (lines 241-320). Examples: `transport-belt`, `underground-belt`, `splitter` and the fast variants become `"pressing"`; express belts become `"crafting-with-fluid-or-metallurgy"`; `electronic-circuit`, `copper-cable` and `advanced-circuit` become `"electronics"`; `processing-unit` becomes `"electronics-with-fluid"`; `sulfuric-acid` and `plastic-bar` become `"chemistry-or-cryogenics"`. The `assembling-machine-3` recipe ingredients are replaced (364-368).
- Frozen graphics (space-age/prototypes/entity/base-frozen-graphics.lua, required at base-data-updates.lua:2):
  - `graphics_set.frozen_patch` plus `reset_animation_when_frozen = true` on AM1/2/3 (104-137) and the centrifuge (232-240).
  - `frozen_patch` on chemical-plant (146) and electric-furnace (243).
  - `fluid_box.pipe_picture_frozen = assemblerpipepicturesfrozen()` on AM2/AM3 (124-143).
  - `pipe_covers_frozen` on every fluid box whose `pipe_covers.north.layers[1].filename` is the vanilla pipe cover (38-59).

  After Space Age loads, all of these frozen sprites live under `__space-age__/graphics/...`.
- Quality: quality/prototypes/base-data-updates.lua changes no crafting machine. It only touches the pumpjack's allowed_effects (line 7) and sets `allow_quality = false` on five oil recipes (lines 2-6).

---

## 4. CraftingMachinePrototype, FurnacePrototype and AssemblingMachinePrototype (from the API)

Inheritance (API `parent` chain): `FurnacePrototype | AssemblingMachinePrototype → CraftingMachinePrototype → EntityWithOwnerPrototype → EntityWithHealthPrototype → EntityPrototype → Prototype → PrototypeBase`.

`CraftingMachinePrototype` description: "Note that a crafting machine cannot be rotated unless it has at least one of the following: a fluid box, a heat energy source, a fluid energy source, or a non-square collision box."

| property | type | req | default / note (API text) |
|---|---|---|---|
| energy_usage | Energy | **yes** | "Energy usage has to be positive." |
| crafting_speed | double | **yes** | "Crafting speed has to be positive." |
| crafting_categories | array[RecipeCategoryID] | **yes** | |
| energy_source | EnergySource | **yes** | electric without `drain` → drain = energy_usage/30 |
| fluid_boxes | array[FluidBox] | no | "For assembling machines, any filters set on the fluidboxes are ignored." |
| effect_receiver | EffectReceiver | no | `{base_effect?, uses_module_effects=true, uses_beacon_effects=true, uses_surface_effects=true}` |
| module_slots | ItemStackIndex | no | 0 |
| allowed_effects | EffectTypeLimitation | no | "No effects are allowed" |
| allowed_module_categories | array[ModuleCategoryID] | no | all |
| quality_affects_energy_usage / quality_affects_module_slots | bool | no | false |
| crafting_speed_quality_multiplier / module_slots_quality_bonus / energy_usage_quality_multiplier | dict[QualityID → …] | no | |
| show_recipe_icon, show_recipe_icon_on_map, draw_entity_info_icon_background, match_animation_speed_to_activity, return_ingredients_on_change | bool | no | true |
| ignore_output_full, fast_transfer_modules_into_module_slots_only | bool | no | false |
| graphics_set / graphics_set_flipped | CraftingMachineGraphicsSet | no | |
| perceived_performance | PerceivedPerformance | no | `{minimum=0, maximum=MAX, performance_to_activity_rate=1}` |
| production_health_effect, trash_inventory_size, vector_to_place_result, forced_symmetry (Mirroring, default none) | | no | |

`FurnacePrototype` adds: `result_inventory_size` (**required**), `source_inventory_size` (**required**, "not more than 1"), `cant_insert_at_source_message_key`, `custom_input_slot_tooltip_key`, `circuit_connector` / `circuit_connector_flipped` (tuple of 4 CircuitConnectorDefinition), `circuit_wire_max_distance` (default 0), `draw_copper_wires`, `draw_circuit_wires`, `default_recipe_finished_signal`, `default_working_signal`. Description: "furnaces automatically choose their recipe based on input."

`AssemblingMachinePrototype` adds: `fixed_recipe`, `fixed_quality`, `gui_title_key`, circuit fields as above, `enable_logistic_control_behavior` (true), `ingredient_count` (65535, counts item ingredients only), `max_item_product_count` (65535), `fluid_boxes_off_when_no_fluid_recipe` (false), `disabled_when_recipe_not_researched` ("Defaults to true if `fixed_recipe` is not given").

Relevant EntityPrototype fields (API):
- `icon` / `icons` / `icon_size`: `icon_size` defaults to 64. "Either this or `icons` is mandatory for entities that have at least one of these flags active: "placeable-neutral", "placeable-player", "placeable-enemy"."
- `collision_box`: "customary to leave 0.1 wide border". `selection_box`: "should match the tile size of the building". `tile_width` / `tile_height` default to the collision box rounded up.
- `fast_replaceable_group`: string, default "".
- `next_upgrade`: EntityID. "The upgrade target entity needs to have the same bounding box, collision mask, and fast replaceable group as this entity. The upgrade target entity must have least 1 item that builds it that isn't hidden." It must be minable and not have "not-upgradable".
- `heating_energy`: Energy, default "0W". "This entity can freeze if heating_energy is larger than zero." CL:3338 tags it "[space-age] Added EntityPrototype::heating_energy".
- `surface_conditions`: array[SurfaceCondition]. **`API: SurfaceCondition` description: "Requires Space Age to use."**
- `drawing_box_vertical_extension`, `icon_draw_specification` (IconDrawSpecification `{shift, scale, scale_for_many, render_layer}`), `icons_positioning` (array of `{inventory_index, max_icons_per_row, max_icon_rows, shift, scale, separation_multiplier, multi_row_initial_height_modifier}`), `alert_icon_shift`, `impact_category` (default "default"), `water_reflection` ("May also be defined inside `graphics_set`").
- `EntityWithHealthPrototype`: `max_health` (default 10), `corpse`, `dying_explosion`, `resistances`, `damaged_trigger_effect`, `integration_patch` (Sprite4Way, may also live inside graphics_set).

---

## 5. energy_source and emissions in 2.0

`API: EnergySource` = `ElectricEnergySource | BurnerEnergySource | HeatEnergySource | FluidEnergySource | VoidEnergySource`, chosen by `type`.

- `BaseEnergySource::emissions_per_minute: dict[AirbornePollutantID -> double]`: "The pollution an entity emits per minute at full energy consumption." In 2.0 it is **a table keyed by pollutant name**, e.g. `emissions_per_minute = { pollution = 4 }` (every machine above). The pollutants are `airborne-pollutant` "pollution" (base/prototypes/pollution.lua:4-5) and "spores" (space-age/prototypes/spores.lua:4-5). CL:3253: "Added airborne-pollutant prototype and changed various pollution related properties to support multiple pollution types."
- `ElectricEnergySource`: `type="electric"`, `usage_priority` (**required**; `ElectricUsagePriority` = primary-input | primary-output | secondary-input | secondary-output | tertiary | solar | lamp), `buffer_capacity`, `input_flow_limit`, `output_flow_limit`, `drain`.
- `BurnerEnergySource`: `type="burner"`, `fuel_inventory_size` (**required**), `burnt_inventory_size` (0), `smoke: array[SmokeSource]`, `light_flicker`, `effectivity` (1), `burner_usage` ("fuel"), `fuel_categories` (default `{"chemical"}`), `initial_fuel`, `initial_fuel_percent`. CL:3154: "Removed BurnerEnergySource::fuel_category. Use BurnerEnergySource::fuel_categories instead."
- `VoidEnergySource`: `{type="void"}`, "unlimited free energy".
- `Energy` is a string with SI prefixes k, M, G, T, P, E, Z, Y, R, Q. CL:3167 notes "Removed 'K' from allowed SI prefixes - use 'k' instead."

---

## 6. fluid_boxes in 2.0

### 6.1 API
`FluidBox` (API) properties: `volume` (**required**, FluidAmount > 0), `pipe_connections` (**required**, array[PipeConnectionDefinition], at most 255), `filter`, `render_layer` ("object"), `draw_only_when_connected` (false), `hide_connection_info` (false), `volume_reservation_fraction` (0), `pipe_covers`, `pipe_covers_frozen`, `pipe_picture`, `pipe_picture_frozen`, `mirrored_pipe_picture`, `mirrored_pipe_picture_frozen` (all Sprite4Way), `minimum_temperature`, `maximum_temperature`, `max_pipeline_extent`, `production_type` (default "none"), `secondary_draw_order` (1), `secondary_draw_orders` (`{north,east,south,west}` int8), `always_draw_covers` ("Defaults to true if `pipe_picture` is not defined, otherwise defaults to false"), `enable_working_visualisations` (array of WorkingVisualisation names).

The FluidBox property list in 2.0.77 contains **no `base_area`, `base_level` or `height`**. Only `volume` exists.

`ProductionType` = `'none' | 'input' | 'input-output' | 'output'`. API: "`input-output` should only be used for boilers in fluid heating mode."

`PipeConnectionDefinition`:
- `flow_direction`: `'input-output' | 'input' | 'output'`, default "input-output".
- `connection_type`: default "normal" (other values "underground" and "linked").
- `direction: defines.direction`: "Primary direction this connection points to when entity direction is north… Only loaded, and mandatory if `connection_type` is "normal" or "underground"."
- `position: MapPosition`: "Position relative to entity's center…". Alternatively `positions` (tuple of 4, one per direction).
- `connection_category` (string | array, default "default"), `enable_working_visualisations`, `max_underground_distance`, `underground_collision_mask`, `linked_connection_id`.

CL:3237: "Reworked how PipeConnectionDefinitions are specified. Added 'connection_type'… Renamed 'type' into 'flow_direction'. Added direction. 'position' now has to be inside of the entity."

**Rule of thumb from the vanilla data:** `position` is the centre of the *edge tile inside the entity*, and `direction` points outward.
- 3×3 machines: `{0,-1}` north, `{0,1}` south, `{±1,±1}` (AM2/AM3/chemical-plant).
- 4×4 machines: `{-1.5,0.5}` west (electromagnetic-plant).
- 5×5 machines: `{±2,±2}` and `{0,±2}` (foundry and cryogenic-plant).

Neither the docs nor the changelog give numeric values for `defines.direction`. Use `defines.direction.north/east/south/west` symbolically; 16 names exist, from north to northnorthwest.

Related:
- `AssemblingMachinePrototype::fluid_boxes_off_when_no_fluid_recipe` (moved there from FluidBoxManagerPrototype, CL:3145).
- Recipe `fluidbox_index` / `fluidbox_multiplier` (section 11).

### 6.2 Graphics helpers (globals defined by base Lua files)
- `pipecoverspictures()` is defined in base/prototypes/entity/pipecovers.lua:1. It returns `{north={layers={cover, cover-shadow(draw_as_shadow=true)}}, east=…, south=…, west=…}`.
- `assembler2pipepictures()` (base/prototypes/entity/assemblerpipes.lua:1) and `assembler3pipepictures()` (:43) return `{north=Sprite, east=Sprite, south=Sprite, west=Sprite}` with no shadow layer.
- `util.empty_sprite()` (core/lualib/util.lua:637) returns a 1×1 `__core__/graphics/empty.png` sprite. The foundry uses it as `pipe_picture`.
- To use these helpers from another mod, follow the Space Age pattern: `require ("__base__.prototypes.entity.pipecovers")` (space-age/prototypes/entity/big-mining-drill.lua:1, biochamber-pictures.lua:1). By analogy, `require("__base__.prototypes.entity.assemblerpipes")` should also work. base/…/entities.lua:4 requires it as `"prototypes.entity.assemblerpipes"`; I did not find a mod that requires it by the `__base__.` path.

---

## 7. graphics_set structure

### 7.1 API types
- `CraftingMachineGraphicsSet` (parent `WorkingVisualisations`) adds `frozen_patch: Sprite4Way`, `circuit_connector_layer`, `circuit_connector_secondary_draw_order`, `animation_progress` (float, default 0.5), `reset_animation_when_frozen` (false), `water_reflection`.
- `WorkingVisualisations`: `animation: Animation4Way`, `idle_animation: Animation4Way` ("Idle animation must have the same frame count as animation"), `always_draw_idle_animation` (false), `default_recipe_tint`, `recipe_not_set_tint` (GlobalRecipeTints), `states: array[VisualState]` ("At least 2 visual states must be defined or no states at all. At most 32"), `working_visualisations: array[WorkingVisualisation]`, `shift_animation_*`, `status_colors`.
- `WorkingVisualisation`:
  - `render_layer` ("object"), `fadeout`, `synced_fadeout`, `constant_speed`, `always_draw`, `animated_shift`, `align_to_waypoint`, `secondary_draw_order`, `light: LightDefinition`, `effect: 'flicker'|'uranium-glow'|'none'`.
  - **`apply_recipe_tint: 'primary'|'secondary'|'tertiary'|'quaternary'|'none'`** ("Has precedence over `apply_tint`") and `apply_tint`.
  - `animation: Animation` or `north_animation` / `east_animation` / `south_animation` / `west_animation`, `north_position` etc., `*_secondary_draw_order`, fog masks, `draw_in_states`, `draw_when_state_filter_matches`, `enabled_by_name`, `name`.
- `Animation4Way`: "If this is loaded as a single Animation, it applies to all directions. Any direction that is not defined defaults to the north animation." It is either a plain `Animation` or `{north=…, north_east=…, east=…, …}`.
- `Animation` (parent AnimationParameters → SpriteParameters): `layers: array[Animation]`, `filename`, `stripes`, `filenames` + `lines_per_file`, `slice`.
- **`Animation::layers`**: "`animation_speed` and `max_advance` of the first layer are used for all layers… **If this property is present, all other properties, including those inherited from AnimationParameters, are ignored.**" `Sprite::layers` has the same sentence. Layers can nest.
- `SpriteParameters` includes `draw_as_shadow`, `draw_as_glow`, `draw_as_light` ("Only one of … can be true"; shadow takes precedence), `apply_runtime_tint`, `tint_as_overlay`, `invert_colors`, **`tint: Color` (default `{r=1, g=1, b=1, a=1}`)**, `blend_mode`, `scale`, `shift`, `priority`, `flags`. The API gives **no description text** for `tint`, `tint_as_overlay` or `apply_runtime_tint`, so exactly how `tint` is blended is **not found in sources**.
- `Color`: `{r,g,b,a}` or a 3/4-array. "values can be from 0-255, they are interpreted as such if at least one value is `> 1`… The game usually expects colors to be in pre-multiplied form."
- CL:3175: "Removed WorkingVisualisation::draw_as_sprite and WorkingVisualisation::draw_as_light. Use SpriteParameters::draw_as_light and draw_as_glow instead." CL:3257: "Removed hr_version from all graphics definitions." CL:3277: "Added CraftingMachinePrototype::graphics_set and moved graphics related properties there."

### 7.2 `util.sprite_load` (Space Age graphics)
core/lualib/util.lua:673-705: `util.sprite_load(path, table)` `require`s `path` (a `.lua` file with `width`, `height`, `shift`, `line_length`, optional `filenames` + `lines_per_file`). It fills the passed table (`filename = path..'.png'` or `filenames = {path.."-1.png", …}`) and returns it. The result is a normal leaf Sprite or Animation table with `filename` or `filenames`, which the tint walker in 10.3 recognises. Example data file: space-age/graphics/entity/foundry/foundry-main.lua → `{width=376, height=398, shift=util.by_pixel(0.0,-6.0), line_length=8, filenames={"-1.png","-2.png"}, lines_per_file=8}`.

### 7.3 Layer inventory per machine (shadow, glow and light flags, and existing tint)

"shadow", "glow" and "light" below mean `draw_as_shadow` / `draw_as_glow` / `draw_as_light = true`. Every line cited was checked by grep.

| machine | main body lives in | shadow layers | glow/light layers | recipe-tinted WVs | explicit `tint` |
|---|---|---|---|---|---|
| stone-furnace (1097-1185) | `animation.layers[1]` | `animation.layers[2]` (1116) | WV1 fire (glow 1138) + light (additive glow 1148); WV2 ground-light (light 1165) | — | none |
| steel-furnace (4809-4913) | `animation.layers[1]` | `layers[2]` (4828) | WV fire (glow 4847), glow (additive glow 4861), working (additive glow 4876), ground-light (light 4892) | — | none |
| electric-furnace (4356-4468) | `animation.layers[1]` | `layers[2]` (4375) | WV1 heater (glow 4396) + light (additive glow 4406); WV2 ground-light (light 4421) | — | none. **WV3/WV4 propeller-1/-2 are plain body-coloured animations**, so tint them too |
| assembling-machine-1 (3157-3185) | `animation.layers[1]` (32 frames) | `layers[2]` (3180, `repeat_count = 32`) | — | — | none |
| assembling-machine-2 (3253-3283) | `animation.layers[1]` | `layers[2]` (3276, `frame_count = 32`) | — | — | none |
| assembling-machine-3 (5443-5473) | `animation.layers[1]` | `layers[2]` (5467) | — | — | none |
| chemical-plant (8292-8441) | `animation = make_4way_animation_from_spritesheet({layers={main, shadow}})`, which returns `{north={layers=…}, east=…, south=…, west=…}` (helper at base/…/entities.lua:214-275; it copies `tint`, `draw_as_shadow` etc. into each direction) | shadow source 8311 | — | WV1 primary (liquid, per-direction `north_animation…`), WV2 secondary (foam), WV3 tertiary (smoke-outer, `render_layer="wires"`), WV4 quaternary (smoke-inner) | none |
| centrifuge (8821-8960) | **`idle_animation.layers`** (C, B, A) with `always_draw_idle_animation = true`, no `animation` | C-shadow 8841, B-shadow 8863, A-shadow 8886 | WV1 light only (`effect="uranium-glow"`, `light={…}`); WV2 3 additive glow layers (8921, 8934, 8947) | — | none |
| foundry (space-age foundry-pictures.lua:126-166) | `animation.layers = {foundry_main, foundry_shadow}` | foundry-shadow (18) | lights (flicker, additive glow), status-lamp (additive glow) | — | **chimney-smoke WV has `tint = {0.4, 0.4, 0.4, 1}` (line 119)**. Also: WV "output-pipe" / "input-pipe" (`always_draw`, `enabled_by_name`, per-direction animations), and a "working" WV (fadeout, plain) |
| electromagnetic-plant (em-plant-pictures.lua:312-319) | **`idle_animation = { layers = base_layers() }`**, plus the moving body in **`working_visualisations` with `always_draw = true`** keyed by `draw_in_states` (218-248) | base-shadow (74) and one shadow per state animation (93, 113, 133, 153) | 4 light WVs (additive glow), 1 `light`-only WV | — | none. `states = states()` defines 8 visual states (idle, warm-up, working-1..3, *-continue, cool-down) |
| cryogenic-plant (cryo-pictures.lua:55-163) | `animation.layers` = main, shadow, anim1-base, anim2-base, anim4-base, anim5-base (`frame_sequence`), anim6-base | shadow (62) | anim6-working-light, working-lights, status-lamp (additive glow) | anim1/2/3/4/6 mask WVs with primary/secondary; smoke-mask-1 tertiary, smoke-mask-2 quaternary | none. The `glass` WV is `always_draw` and plain |

Pipe graphics: `pipecoverspictures()` layers include shadows. The electromagnetic-plant and cryogenic-plant `pipe_picture` directions contain `{layers={pipe, pipe-shadow(draw_as_shadow)}}` (em-plant-pictures.lua:290; cryo-pictures.lua:180/199/218/237). The `assembler2/3pipepictures()` sprites have no shadow.

---

## 8. Circuit connectors

- `circuit_connector` is a **tuple of 4 `CircuitConnectorDefinition`** (`{sprites: CircuitConnectorSprites, points: WireConnectionPoint}`), per `API: AssemblingMachinePrototype::circuit_connector` and `FurnacePrototype::circuit_connector`. CL:3179: "removed circuit_wire_connection_points and circuit_connector_sprites but added circuit_connector". CL:1447-1448 added furnace circuit connectors and `circuit_connector_flipped`.
- Built with `circuit_connector_definitions.create_vector(template, {4 × {variation, main_offset, shadow_offset, show_shadow}})` (core/lualib/circuit-connector-sprites.lua:85-102; `make_single_circuit_connector_definition` at 77-83 returns `{sprites=…, points=…}`). Example (core/lualib/circuit-connector-generated-definitions.lua:523-532):
```lua
circuit_connector_definitions["assembling-machine"] = circuit_connector_definitions.create_vector
(
  universal_connector_template,
  {
    { variation = 18, main_offset = util.by_pixel(24, 25), shadow_offset = util.by_pixel(35, 31), show_shadow = true },
    { variation = 18, main_offset = util.by_pixel(24, 25), shadow_offset = util.by_pixel(35, 31), show_shadow = true },
    { variation = 18, main_offset = util.by_pixel(24, 25), shadow_offset = util.by_pixel(35, 31), show_shadow = true },
    { variation = 18, main_offset = util.by_pixel(24, 25), shadow_offset = util.by_pixel(35, 31), show_shadow = true }
  }
)
```
- Keys used by these machines:
  - "stone-furnace" (generated-definitions.lua:894), "steel-furnace" (904), "electric-furnace" (914), "assembling-machine" (AM1/2/3; 523), "chemical-plant" (556), "centrifuge" (545).
  - "foundry", "electromagnetic-plant" and "cryogenic-plant" are defined in **space-age/prototypes/entity/circuit-network.lua:2/24/46**, so **they exist only when Space Age is loaded**.
- Wire distance globals (core/lualib/circuit-connector-sprites.lua): `default_circuit_wire_max_distance = 9` (95), `assembling_machine_circuit_wire_max_distance = 9` (197), `furnace_circuit_wire_max_distance = 9` (198). Mods get them via `require("circuit-connector-sprites")`, as space-age/prototypes/entity/entities.lua:2 and base-data-updates.lua:1 do.
- A deepcopy carries the connector tables along. They contain real sprite definitions with `filename`, `width` and `height`, so a blind recursive tint recolours them too (see 10.2).

---

## 9. Icons, items and locale

- Machines use `icon = "<path>.png"` with the default `icon_size` of 64. CL:3191: "Changed icon_size default to be always 64". CL:3159: "Removed icon_mipmaps".
- `IconData` = `{icon (required), icon_size (64), tint (Color, default white), shift, scale, draw_background, floating}`. **`tint` is valid on `IconData`.** Base example (base/…/entities.lua:9924-9933):
```lua
local infinity_pipe = util.table.deepcopy(data.raw["pipe"]["pipe"])
infinity_pipe.type = "infinity-pipe"
infinity_pipe.name = "infinity-pipe"
infinity_pipe.hidden = true
infinity_pipe.icon = nil
infinity_pipe.icons =
{{
  icon = "__base__/graphics/icons/pipe.png",
  tint = {0.5, 0.5, 1}
}}
```
- Locale: the base locale has sections `[entity-description]` (base/locale/en/base.cfg:43), `[entity-name]` (:94, e.g. `assembling-machine-1=Assembling machine 1` at :164), `[item-name]` (:611) and `[recipe-name]` (:809). The AM1 item has no `[item-name]` entry. An item with `place_result` falls back to `{"entity-name.<place_result>"}`, which is how quality/prototypes/recycling.lua:12-34 (`get_item_localised_name`) resolves it.

---

## 10. How to `table.deepcopy` a machine and tint it

### 10.1 Facts
- `table.deepcopy` is defined in core/lualib/util.lua:6-22. It preserves shared-reference topology and metatables. Aliases: `util.table.deepcopy` and `util.copy` (:39-41).
- **`tint` is a valid property on every Sprite and Animation leaf**: `SpriteParameters::tint: Color`, inherited by `Sprite`, `AnimationParameters → Animation`, `RotatedAnimation`, and so on. It is also valid on `IconData`.
- **`tint` placed on a table that has `layers` is ignored.** Per `Animation::layers` / `Sprite::layers`, "all other properties … are ignored". It has to go on each leaf layer.
- Vanilla already uses `tint` on a crafting-machine WorkingVisualisation animation: the foundry chimney smoke, `tint = {0.4, 0.4, 0.4, 1}` (foundry-pictures.lua:119). `make_4way_animation_from_spritesheet` forwards `tint = anim.tint` (base/…/entities.lua:248).
- `util.recursive_tint(array, tint)` exists (core/lualib/util.lua:858-876):
```lua
local function is_sprite_def(array)
  return array.icon or array.width and array.height and (array.filename or array.stripes or array.filenames)
end
--- Recursively tint all sprite definitions in the given table.
--- If `tint` is `false`, all tinting will be removed.
function util.recursive_tint(array, tint)
  for _, v in pairs(array) do
    if type(v) == "table" then
      if is_sprite_def(v) then
        if tint == false then
          v.tint = nil
        else
          v.tint = tint
        end
      end
      v = util.recursive_tint(v, tint)
    end
  end
  return array
end
```
  Base uses it on a whole prototype: `util.recursive_tint(infinity_cargo_wagon, {r = 0.5, g = 0.5, b = 1})` (base/prototypes/entity/trains.lua:1684; also elevated-rails/prototypes/sloped-trains-updates.lua:293). **Caveats, read from the code:**
  - it does **not** check `draw_as_shadow`, `draw_as_glow` or `draw_as_light`, so shadows, glows and lights get tinted too;
  - called on the whole prototype, it also tints `IconData` entries (`array.icon`), the circuit connector sprites, `water_reflection`, `frozen_patch`, `pipe_covers` and anything else with filename, width and height;
  - it does not skip `layers` containers. That is harmless, because containers usually lack width and height, but leaves are what matter.

  How the engine renders a tinted `draw_as_shadow` sprite is **not found in sources**.

### 10.2 What to change on the copy (every field below appears in the vanilla prototypes)
| field | action | reason (source) |
|---|---|---|
| `name` | new unique name | PrototypeBase::name: alphanumeric, dashes, underscores; ≤200 characters (CL:3203) |
| `minable.result` | new item name | the copy still points at the vanilla item (e.g. `minable = {mining_time = 0.2, result = "assembling-machine-3"}`) |
| `icon` / `icons` | set `icon = nil`, `icons = {{icon = orig.icon, icon_size = orig.icon_size, tint = T}}` | IconData::tint; pattern from infinity-pipe (entities.lua:9928-9933) |
| `next_upgrade` | set to nil or to a valid target | a copy of AM1 keeps `next_upgrade = "assembling-machine-2"` (3153). The target must share the bounding box, collision mask and fast_replaceable_group (API) |
| upgrade *into* the copy | e.g. `data.raw["assembling-machine"]["assembling-machine-3"].next_upgrade = "<copy>"` | allowed only when the copy keeps the 3×3 boxes and `fast_replaceable_group = "assembling-machine"` (API next_upgrade text) |
| `fast_replaceable_group` | keep it (to allow fast replace or upgrade with vanilla) or change it | EntityPrototype::fast_replaceable_group |
| `corpse`, `dying_explosion` | can keep the vanilla names | they are plain IDs (2.13) |
| `crafting_categories`, `crafting_speed`, `energy_usage`, `module_slots`, `allowed_effects`, `effect_receiver` | set as designed | section 4 |
| `circuit_connector` | keep (it is copied); geometry is unchanged | section 8 |
| `graphics_set` (+ `fluid_boxes[i].pipe_picture`) | tint the leaves, skipping shadow, glow, light and recipe-tinted WVs | 10.3 |
| `localised_name` | optional; otherwise add `[entity-name] <name>=…` to the locale | section 9 |
| Space Age-only fields present on the copy (`heating_energy`, `surface_conditions` on stone/steel furnace, `frozen_patch`, `pipe_picture_frozen`, `pipe_covers_frozen`) | keep only when Space Age is active | SurfaceCondition "Requires Space Age to use"; CL:3338 marks heating_energy as [space-age]; the frozen sprites are `__space-age__/…` paths |

### 10.3 Suggested tint walker (derived from the API rules above; not vanilla code)
```lua
-- Magnetics: tint every *body* sprite leaf of a crafting-machine graphics_set.
-- Leaves are tables with filename/filenames/stripes (Sprite/Animation leaf per API);
-- a table with `layers` ignores its own properties (API Animation::layers), so recurse into it.
local function tint_leaves(node, tint)
  if type(node) ~= "table" then return end
  if node.layers then
    for _, layer in pairs(node.layers) do tint_leaves(layer, tint) end
    return
  end
  if node.filename or node.filenames or node.stripes then
    if not (node.draw_as_shadow or node.draw_as_glow or node.draw_as_light) then
      node.tint = tint          -- overwrites an existing tint (e.g. foundry smoke {0.4,0.4,0.4,1})
    end
    return                       -- do not descend into stripes/filenames of a leaf
  end
  -- Animation4Way {north=..., east=...} or Sprite4Way {north=..., ...}
  for _, v in pairs(node) do tint_leaves(v, tint) end
end

local function tint_crafting_graphics_set(gs, tint)
  if not gs then return end
  tint_leaves(gs.animation, tint)        -- Animation4Way (may be single Animation)
  tint_leaves(gs.idle_animation, tint)   -- centrifuge / EM plant keep the body here
  for _, wv in pairs(gs.working_visualisations or {}) do
    -- leave recipe/status-coloured layers to the engine; the interaction of sprite tint with
    -- apply_recipe_tint is not documented in sources
    if not wv.apply_recipe_tint and not wv.apply_tint then
      tint_leaves(wv.animation, tint)
      tint_leaves(wv.north_animation, tint); tint_leaves(wv.east_animation, tint)
      tint_leaves(wv.south_animation, tint); tint_leaves(wv.west_animation, tint)
    end
  end
  -- deliberately NOT touched: gs.frozen_patch, gs.water_reflection, wv.light, circuit_connector
end

local function make_tinted_machine(ptype, src, new_name, tint)
  local e = table.deepcopy(data.raw[ptype][src])
  e.name = new_name
  e.minable.result = new_name
  e.icons = {{icon = e.icon, icon_size = e.icon_size, tint = tint}}
  e.icon = nil
  e.next_upgrade = nil
  tint_crafting_graphics_set(e.graphics_set, tint)
  for _, fb in pairs(e.fluid_boxes or {}) do
    if type(fb) == "table" then tint_leaves(fb.pipe_picture, tint) end  -- pipe_covers left vanilla
  end
  return e
end
```
Notes that follow from the per-machine inventory (7.3):
- For **electromagnetic-plant** the moving body sits in `always_draw` working visualisations. Tinting `idle_animation` alone would leave most of the machine untinted, which is why the walker covers WVs.
- For **centrifuge** there is no `animation`, only `idle_animation`.
- For **chemical-plant** and **cryogenic-plant** the recipe-tinted WVs (liquids, foam, smoke, masks) are skipped on purpose, so recipe colours keep working.
- For **electric-furnace**, WV3/WV4 (propellers) are body-coloured and get tinted.
- For the **foundry**, the walker overwrites the chimney smoke's existing `{0.4,0.4,0.4,1}`. Add `if node.tint == nil then` before the assignment to keep it.
- `fb.pipe_picture` for the foundry is `util.empty_sprite()`, so tinting it does nothing visible. Its pipes are the "input-pipe"/"output-pipe" WVs, which the walker tints.

### 10.4 Base-only vs Space Age
- Copying `foundry`, `electromagnetic-plant` or `cryogenic-plant`, or using `circuit_connector_definitions["foundry"|…]`, works **only with Space Age**. Those prototypes and keys are defined only in space-age files.
- Guard with the data-stage global `mods` (`API` type `Mods`: "A dictionary of mod names to mod versions of all active mods…", example `if mods["pizza"] then … end`). The data stage also has a global `feature_flags` (`API: FeatureFlags`: expansion_shaders, freezing, quality, rail_bridges, segmented_units, space_travel, spoiling).
- `surface_conditions` (entity or recipe): "Requires Space Age to use" (API SurfaceCondition). Note that base itself defines surface-property prototypes `gravity` (default 10), `pressure` (1000), **`magnetic-field` (90)**, `solar-power`, and `day-night-cycle` (base/prototypes/planet/surface-property.lua:1-27). Vanilla Space Age uses `magnetic-field` in the electromagnetic-plant recipe: `surface_conditions = {{property = "magnetic-field", min = 99}}` (space-age/prototypes/recipe.lua:2199-2208).
- On whether `heating_energy > 0` is rejected without Space Age: **not found in sources**. The only hint is the "[space-age]" tag at CL:3338.

### 10.5 Load order (deepcopy timing)
- A copy made at time *t* reflects data.raw at *t*. Space Age's base-data-updates run inside Space Age's **data.lua** (space-age/data.lua:65). A copy of AM2 taken before that has the base-only category list, and taken after it has the Space Age list plus `frozen_patch`, `heating_energy` and `pipe_picture_frozen`.
- Evidence that every mod's `data.lua` runs before any mod's `data-updates.lua`: quality's `data-updates.lua` loops over **all** `data.raw.recipe` (quality/data-updates.lua:1-6) and special-cases Space Age recipe names ("big-mining-drill", "turbo-transport-belt", "cryogenic-plant", "tungsten-carbide", "superconductor"; quality/prototypes/recycling.lua:173-181). Yet Space Age depends on quality (space-age/info.json `"dependencies": ["base >= 2.0.0", "elevated-rails >= 2.0.0", "quality >= 2.0.0"]`), so quality loads earlier. The general ordering rule and the optional-dependency syntax (`"? space-age"`) are **not found in sources**. Vanilla info.json files only show hard dependencies.
- Practical consequence: add your recipe categories to vanilla machines (`table.insert(data.raw["assembling-machine"]["assembling-machine-2"].crafting_categories, "magnetics")`) in **data-updates.lua**. Otherwise Space Age's `=` overwrite (3) can erase them.

---

## 11. Recipes in 2.0

### 11.1 `RecipePrototype` (API; parent Prototype → PrototypeBase)
| property | type | default | API notes |
|---|---|---|---|
| category | RecipeCategoryID | "crafting" | "The base "crafting" category can not contain recipes with fluid ingredients or products." |
| additional_categories | array[RecipeCategoryID] | — | no description; added in 2.0.49 (CL:756); **no vanilla recipe uses it** (grep finds only the changelog) |
| ingredients | array[IngredientPrototype] | — | "Duplicate ingredients… are *not* allowed." May be `{}` |
| results | array[ProductPrototype] | — | "Duplicate results… are allowed." May be `{}` |
| main_product | string | — | `""` forces the recipe's own name, icon and subgroup; with multiple products and no main_product, `icon` and `subgroup` become mandatory |
| energy_required | double | 0.5 | "Must be `> 0.001`." |
| enabled | bool | true | "If a recipe is unlocked via technology, this should be set to `false`." |
| hidden, hide_from_stats, hide_from_player_crafting, hide_from_bonus_gui, hide_from_signal_gui | bool | false / auto | |
| allow_productivity | bool | **false** | allow_consumption / allow_speed / allow_pollution / allow_quality default **true**; plus allow_*_message |
| maximum_productivity | double | 3.0 | |
| emissions_multiplier | double | 1 | |
| crafting_machine_tint | RecipeTints `{primary, secondary, tertiary, quaternary}` | — | used by WVs with `apply_recipe_tint` |
| icon / icons / icon_size | | 64 | |
| surface_conditions | array[SurfaceCondition] | — | Space Age only |
| auto_recycle | bool | true | "not read by the game engine itself, but the quality mod's recycling.lua" |
| allow_decomposition, allow_as_intermediate, allow_intermediates, always_show_made_in, show_amount_in_title, always_show_products, unlock_results, preserve_products_in_machine_output, result_is_always_fresh, reset_freshness_on_craft, requester_paste_multiplier (30), overload_multiplier (0), allow_inserter_overload (true), allowed_module_categories, alternative_unlock_methods | | | |
| subgroup, order, localised_name/description, hidden_in_factoriopedia, parameter | (PrototypeBase) | | CL:3217 "Moved subgroup property from individual prototypes to PrototypeBase." |

Ingredients (API):
- `ItemIngredientPrototype = {type='item' (required), name, amount (uint16, not 0), ignored_by_stats}`
- `FluidIngredientPrototype = {type='fluid', name, amount (> 0), temperature, minimum_temperature, maximum_temperature, ignored_by_stats, fluidbox_index (1-based, "separate for input and output fluidboxes"), fluidbox_multiplier (uint8, default 2, ≥1)}`

Products (API):
- `ItemProductPrototype = {type='item' (required), name, amount | amount_min+amount_max, probability (default 1), ignored_by_stats, ignored_by_productivity (default = ignored_by_stats), show_details_in_recipe_tooltip, extra_count_fraction, percent_spoiled}`. Expected value: "`p * (0.5 * (max + min))`". If `amount_max < amount_min` the game uses `amount_min`.
- `FluidProductPrototype = {type='fluid', name, amount | amount_min+amount_max, probability, ignored_by_stats, ignored_by_productivity, temperature, fluidbox_index, show_details_in_recipe_tooltip}`.
- CL:243: "Removed "research-progress" product type from RecipePrototype."

### 11.2 Examples from base/prototypes/recipe.lua (verbatim)
Minimal handcraftable recipe (category defaults to "crafting", enabled defaults to true, energy defaults to 0.5), lines 744-750:
```lua
  {
    type = "recipe",
    name = "iron-gear-wheel",
    ingredients = {{type = "item", name = "iron-plate", amount = 2}},
    results = {{type="item", name="iron-gear-wheel", amount=1}},
    allow_productivity = true
  },
```
Smelting recipe (1428-1437):
```lua
  {
    type = "recipe",
    name = "iron-plate",
    category = "smelting",
    auto_recycle = false,
    energy_required = 3.2,
    ingredients = {{type = "item", name = "iron-ore", amount = 1}},
    results = {{type="item", name="iron-plate", amount=1}},
    allow_productivity = true
  },
```
Machine recipe unlocked by technology (957-968):
```lua
  {
    type = "recipe",
    name = "assembling-machine-1",
    enabled = false,
    ingredients =
    {
      {type = "item", name = "electronic-circuit", amount = 3},
      {type = "item", name = "iron-gear-wheel", amount = 5},
      {type = "item", name = "iron-plate", amount = 9}
    },
    results = {{type="item", name="assembling-machine-1", amount=1}}
  },
```
Fluid ingredient in an assembler (2081-2094):
```lua
  {
    type = "recipe",
    name = "processing-unit",
    category = "crafting-with-fluid",
    enabled = false,
    energy_required = 10,
    ingredients =
    {
      {type = "item", name = "electronic-circuit", amount = 20},
      {type = "item", name = "advanced-circuit", amount = 2},
      {type = "fluid", name = "sulfuric-acid", amount = 5}
    },
    results = {{type="item", name="processing-unit", amount=1}},
    allow_productivity = true
  },
```
Chemistry with `crafting_machine_tint` (306-327):
```lua
  {
    type = "recipe",
    name = "plastic-bar",
    category = "chemistry",
    energy_required = 1,
    enabled = false,
    auto_recycle = false,
    ingredients =
    {
      {type = "fluid", name = "petroleum-gas", amount = 20},
      {type = "item", name = "coal", amount = 1}
    },
    results =
    {
      {type = "item", name = "plastic-bar", amount = 2}
    },
    allow_productivity = true,
    crafting_machine_tint =
    {
      primary = {r = 1.000, g = 1.000, b = 1.000, a = 1.000}, -- #fefeffff
      secondary = {r = 0.771, g = 0.771, b = 0.771, a = 1.000}, -- #c4c4c4ff
      tertiary = {r = 0.768, g = 0.665, b = 0.762, a = 1.000}, -- #c3a9c2ff
      quaternary = {r = 0.000, g = 0.000, b = 0.000, a = 1.000}, -- #000000ff
    }
  },
```
Probability outputs, with `icon`, `subgroup` and `order` required for multiple products (2507-2531):
```lua
  {
    type = "recipe",
    name = "uranium-processing",
    energy_required = 12,
    enabled = false,
    auto_recycle = false,
    category = "centrifuging",
    ingredients = {{type = "item", name = "uranium-ore", amount = 10}},
    icon = "__base__/graphics/icons/uranium-processing.png",
    subgroup = "uranium-processing",
    order = "a[uranium-processing]-a[uranium-processing]",
    results =
    {
      { type = "item", name = "uranium-235", probability = 0.007, amount = 1 },
      { type = "item", name = "uranium-238", probability = 0.993, amount = 1 }
    },
    allow_productivity = true
  },
```
(The results are compacted onto single lines; values unchanged.)

Catalyst-style `ignored_by_stats` / `ignored_by_productivity` with `main_product = ""` (2533-2554, kovarex):
```lua
    ingredients =
    {
      {type = "item", name = "uranium-235", amount = 40, ignored_by_stats = 40},
      {type = "item", name = "uranium-238", amount = 5, ignored_by_stats = 2}
    },
    results =
    {
      {type = "item", name = "uranium-235", amount = 41, ignored_by_stats = 40, ignored_by_productivity = 40},
      {type = "item", name = "uranium-238", amount = 2, ignored_by_stats = 2, ignored_by_productivity = 2}
    },
    main_product = "",
    allow_decomposition = false,
    allow_productivity = true,
    allow_quality = false -- catalyst would be also bumped on quality
```
`fluidbox_index` (basic-oil-processing, 151-170): `{type = "fluid", name = "crude-oil", amount = 100, fluidbox_index = 2}` and result `{type = "fluid", name = "petroleum-gas", amount = 45, fluidbox_index = 3}`, with `main_product = ""`.

`fluidbox_multiplier` (space-age/prototypes/recipe.lua:2184-2195, holmium-plate): `{type = "fluid", name = "holmium-solution", amount = 20, fluidbox_multiplier = 10}`.

**`amount_min` / `amount_max`: no vanilla recipe uses them.** They appear only in `minable.results` of Gleba and Aquilo decoratives (space-age/prototypes/decorative/decoratives-gleba.lua:3501-3503, decoratives-aquilo.lua:438-439), e.g. `{type = "item", name = "stone", amount_min = 3, amount_max = 7}`. The format follows ItemProductPrototype.

Recipe `surface_conditions` (space-age/prototypes/recipe.lua:2199-2215):
```lua
  {
    type = "recipe",
    name = "electromagnetic-plant",
    category = "electronics-or-assembling",
    surface_conditions =
    {
      {
        property = "magnetic-field",
        min = 99
      }
    },
    energy_required = 10,
    ingredients = { ... },
    results = {{type="item", name="electromagnetic-plant", amount=1}},
    enabled = false
  },
```

Technology unlock effect format (space-age/base-data-updates.lua:31-40): `{ type = "unlock-recipe", recipe = "rocket-silo" }`.

### 11.3 Quality recycling (applies whenever the quality mod is active, including Space Age)
quality/data-updates.lua:1-6 calls `recycling.generate_recycling_recipe(recipe)` for every recipe, and lines 8-21 create a self-recycling recipe for every item. `default_can_recycle` (quality/prototypes/recycling.lua:158-184) skips a recipe when any of these hold:
- the category is "recycling";
- `recipe.auto_recycle == false` (162);
- the subgroup is "empty-barrel";
- the category is "smelting" (167) or "chemistry";
- the category is "chemistry-or-cryogenics" (except battery), "crushing", or "organic";
- the category is "metallurgy" (except big-mining-drill and the turbo belt, underground and splitter) or "cryogenics" (except railgun items, cryogenic-plant and fusion items);
- the name contains both "science" and "pack";
- the name is "tungsten-carbide", "superconductor" or "biolab".

**Any Magnetics recipe in a new category is recycled unless it sets `auto_recycle = false`.**

`add_recipe_values` (recycling.lua:75) returns nothing (so no recycling recipe is made) when there is more than one item product, or when the item product has `amount_min ~= amount_max` (78-86). It also requires every ingredient to be a table and errors otherwise (106-108).

Items can opt out with `item.auto_recycle == false` (quality/data-updates.lua:9).

### 11.4 Malformed results
`util.normalize_recipe_products` (core/lualib/util.lua:819-835) errors with "Recipe has no results" and "…malformed results: it should only contain tables (one per product)…".

---

## 12. recipe-category prototypes

Format: `{ type = "recipe-category", name = "<id>" }`. `API: RecipeCategory` has **no own properties**. It inherits PrototypeBase (name, order, localised_name, subgroup, hidden…). Description: "The recipe category with the name "crafting" cannot contain recipes with fluid ingredients or products."

Base (base/prototypes/categories/recipe-category.lua, required at base/data.lua:38): `crafting`, `advanced-crafting`, `smelting`, `chemistry`, `crafting-with-fluid`, `oil-processing`, `rocket-building`, `centrifuging`, `basic-crafting`, `recycling` (comment: "According to the game engine, removing this is illegal :)"), `recycling-or-hand-crafting`.

Space Age (space-age/prototypes/categories/recipe-category.lua, required at space-age/data.lua:39): `chemistry-or-cryogenics`, `pressing`, `crushing`, `crafting-with-fluid-or-metallurgy`, `metallurgy-or-assembling`, `metallurgy`, `organic`, `organic-or-hand-crafting`, `organic-or-assembling`, `organic-or-chemistry`, `captive-spawner-process`, `electronics-or-assembling`, `electronics`, `electronics-with-fluid`, `electromagnetics`, `cryogenics-or-assembling`, `cryogenics`.

Quality and elevated-rails define no recipe categories (grep finds none). Parameter recipes use `category = "parameters"` (base/prototypes/recipe.lua:10). That category is defined in core as `{ type = "recipe-category", name = "parameters" }` (core/prototypes/parameters.lua:1-7).

Vanilla handles "craftable in machine A or B" with **combined category names** (`X-or-Y`) added to both machines' `crafting_categories`. For example, `electronics-or-assembling` is on the electromagnetic-plant and on AM2/AM3 (with Space Age). A Magnetics mod that wants a recipe craftable in both an assembler and its own machine can:
(a) define its own `magnetics-or-assembling` category and insert it into AM2/AM3 in data-updates.lua (with a base-only fallback), or
(b) use `additional_categories`, which exists in the 2.0.77 API but has no description and no vanilla usage, so its behaviour is not verified from sources.

Hand crafting: the base character has `{"crafting"}` (base/…/entities.lua:709) and god-controller has `{"crafting"}` (core/prototypes/god-controller.lua:7). Space Age extends both (section 3).

---

## 13. 2.0 vs 1.1 changes visible in the sources (CL = data/changelog.txt, version 2.0.7 block)
- **No `normal` / `expensive`**: "Removed normal and expensive properties from TechnologyPrototype and RecipePrototype." (CL:3260)
- **No `result` / `result_count`**: "Removed RecipePrototype::result and result_count. Use RecipePrototype::results instead." (CL:3247)
- **Products need `type`**: "ProductPrototype now has a mandatory "type" field and does not accept simplified syntax for item products." (CL:3248)
- **Ingredients need named keys**: "Changed recipe ingredients to only be specified by a table with named keys." (CL:3162). So `{"iron-plate", 2}` is invalid and `{type="item", name="iron-plate", amount=2}` is required. (The API lists `type` as required on both ingredient kinds.)
- "Removed catalyst_amount from recipe ingredients and products." (CL:3163); `ignored_by_stats` / `ignored_by_productivity` added instead (CL:3164-3165).
- Module limitations moved to recipes: "Replaced ModulePrototype::limitation … with RecipePrototype::allow_[effect-name] … By default, all effects except productivity are allowed." (CL:3226). So set `allow_productivity = true` on intermediates.
- `base_productivity` moved into `effect_receiver.base_effect` (CL:3250-3251).
- `graphics_set` introduced for crafting machines (CL:3277). `draw_as_sprite` / `draw_as_light` were removed from WorkingVisualisation (CL:3175). `hr_version` removed (CL:3257). `drawing_box` replaced by `drawing_box_vertical_extension` (CL:3190). `entity_info_icon_shift` / `scale_entity_info_icon` replaced by `icon_draw_specification` (CL:3266, 3268-3269).
- Pipe connections reworked: `flow_direction`, `direction`, `connection_type`, position inside the entity (CL:3237). `off_when_no_fluid_recipe` moved to `AssemblingMachinePrototype::fluid_boxes_off_when_no_fluid_recipe` (CL:3145). FluidBox has `volume` and no `base_area` (API property list; the changelog does not mention base_area).
- Circuit connectors: `circuit_connector` replaces `circuit_wire_connection_points` / `circuit_connector_sprites` (CL:3179).
- Pollution: `emissions_per_minute` is keyed by airborne pollutant (CL:3253).
- `hidden` is a bool on all prototypes, not a flag (CL:3249). `subgroup` moved to PrototypeBase (CL:3217).
- Icons: `icon_size` defaults to 64 (CL:3191), and `icon_mipmaps` was removed (CL:3159).
- `perceived_performance` table replaces min_perceived_performance and related fields (CL:3230).
- "Changed prototype data loading to enforce the correct types are used." (CL:3202) and "Restricted prototype names to only contain alphanumeric characters, dashes and underscores." (CL:3203).
- Later 2.0.x additions:
  - `CraftingMachinePrototype::crafting_speed_quality_multiplier`, `module_slots_quality_bonus`, `energy_usage_quality_multiplier` (CL:521), `quality_affects_energy_usage` (CL:580), `quality_affects_module_slots` (CL:583);
  - `FurnacePrototype::circuit_connector` etc. (CL:1447);
  - `AssemblingMachinePrototype::max_item_product_count` (CL:1449) and `disabled_when_recipe_not_researched` (CL:2743);
  - `FluidBox::mirrored_pipe_picture` (CL:2019);
  - `RecipePrototype::additional_categories` (CL:756) and `hide_from_bonus_gui` (CL:427);
  - `FluidBoxPrototype::volume_reservation_fraction` (CL:1228).

---

## 14. Not found in sources (do not rely on without testing)
- How sprite `tint` is blended (multiplicative, overlay, etc.). The API description for `SpriteParameters::tint` is empty.
- How a tinted `draw_as_shadow` sprite is rendered, and how sprite `tint` interacts with `apply_recipe_tint` in a WorkingVisualisation.
- The mod load-order algorithm, and the optional-dependency syntax in info.json. Vanilla shows only hard deps. Stage ordering (all data.lua before data-updates.lua) is inferred in 10.5, not stated.
- Whether `heating_energy > 0` or `frozen_patch` are rejected without Space Age.
- Semantics of `RecipePrototype::additional_categories` beyond its type.
- Numeric values of `defines.direction.*` (absent from both API JSONs).
- Whether headless validates sprite file existence. There are no PNGs in this install, so the headless server can only be run with vanilla or mod paths that it does not check. Graphics correctness cannot be verified here.
