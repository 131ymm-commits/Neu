# Power buildings in Factorio 2.0.77: a source-backed reference for the "Magnetics" mod

Sources used (and nothing else):
- Lua prototypes: `/opt/factorio/data/{core,base,quality,elevated-rails,space-age}`. Paths below are relative to `/opt/factorio/data/`.
- API: `/opt/factorio-api/prototype-api.json` (header: `application=factorio`, `application_version=2.0.77`, `api_version=6`, `stage=prototype`) and `/opt/factorio-api/runtime-api.json`.
- `changelog.txt` (top entry `Version: 2.0.77`, `Date: 21. 05. 2026`).

Notation: `B/e:1234` means `base/prototypes/entity/entities.lua` line 1234. `SA/e:1234` means `space-age/prototypes/entity/entities.lua`. "API X.y" means the property `y` of prototype/type `X` in prototype-api.json. Anything labelled **derived** is my arithmetic on sourced numbers. Anything labelled **inference** is my reasoning and has not been checked by running the game.

Helper script I used to query the API JSON: `/tmp/claude-0/-home-user-Neu/5dc61be6-6c38-58c2-939b-4b416832b0f1/scratchpad/recon/tools/api.py` (usage: `python3 api.py BurnerGeneratorPrototype ElectricEnergySource --full`).

---

## 0. Headline facts

1. **There is a `burner-generator` entity in base.** Its name is `"burner-generator"`, it is `hidden = true`, and no recipe or technology makes it (B/e:9945-9993; the item is in `base/prototypes/item.lua:2465-2478`). Space Age, quality and elevated-rails define no burner-generator. So the mod must not reuse the name `burner-generator`. Pick something like `magnetics-...`.
2. **In 2.0 burners use `fuel_categories = {...}` (a list).** `fuel_category` was removed from `BurnerEnergySource` (changelog.txt:3154, 2.0.7 section: "Removed BurnerEnergySource::fuel_category. Use BurnerEnergySource::fuel_categories instead."). The API default is `{"chemical"}`.
3. **Space Age defines no accumulator-type prototype.** `grep 'type = "accumulator"'` matches only base (B/e:5280). The SA "energy storage" buildings are the `lightning-attractor` type (lightning-rod, lightning-collector), which carry an electric `buffer_capacity`.
4. **The headless data tree contains zero `.png` files** (`find /opt/factorio/data -name '*.png' | wc -l` gives `0`). `base/graphics/` holds only `entity/**.lua` sprite-metadata files, 193 of them. Base still references `__base__/graphics/icons/*.png` and `__core__/graphics/empty.png`, and those files are absent here. **Inference:** the headless build does not check whether a `.png` referenced from a prototype exists. `util.sprite_load` is different: it `require`s the `.lua` metadata, which is present (e.g. `space-age/graphics/entity/lightning-rod/lightning-rod.lua`).
5. **`SurfaceCondition` is documented as "Requires Space Age to use."** (API type `SurfaceCondition`). The recipe categories `electronics` and `electromagnetics` exist only in SA (`space-age/prototypes/categories/recipe-category.lua:53,61`). Base-only mode must not use either of these.
6. **The surface property `magnetic-field` is defined in base** (`base/prototypes/planet/surface-property.lua:12-16`, `default_value = 90`). Only SA sets per-planet values and uses it in recipes. See section 11.

---

## 1. Summary table (vanilla numbers)

| Entity (name) | type | Defined at | Key power numbers | Box (collision / selection) | fast_replaceable_group | Item stack / subgroup |
|---|---|---|---|---|---|---|
| small-electric-pole | electric-pole | B/e:1629-1754 | `maximum_wire_distance = 7.5`, `supply_area_distance = 2.5` (B/e:1643-1644) | `{{-0.15,-0.15},{0.15,0.15}}` / `{{-0.4,-0.4},{0.4,0.4}}` | `"electric-pole"` | 50 / energy-pipe-distribution (item.lua:373) |
| medium-electric-pole | electric-pole | B/e:4605-4738 | `9` / `3.5` (B/e:4627-4628) | `{{-0.15,-0.15},{0.15,0.15}}` / `{{-0.5,-0.5},{0.5,0.5}}` | `"electric-pole"` | 50 / energy-pipe-distribution (item.lua:830) |
| big-electric-pole | electric-pole | B/e:4470-4604 | `32` / `2` (B/e:4492-4493) | `{{-0.65,-0.65},{0.65,0.65}}` / `{{-1,-1},{1,1}}`, explicit `collision_mask` incl. `elevated_rail=true` (B/e:4488) | `"big-electric-pole"` | 50 / energy-pipe-distribution (item.lua:817) |
| substation | electric-pole | B/e:7308-7454 | `18` / `9` (B/e:7329-7330) | `{{-0.7,-0.7},{0.7,0.7}}` / `{{-1,-1},{1,1}}` | `"substation"` | 50 / energy-pipe-distribution (item.lua:1800) |
| accumulator | accumulator | B/e:5279-5353 | `buffer_capacity = "5MJ"`, `usage_priority = "tertiary"`, in/out `"300kW"` (B/e:5293-5300) | `{{-0.9,-0.9},{0.9,0.9}}` / `{{-1,-1},{1,1}}` | `"accumulator"` | 50 / energy (item.lua:1126) |
| solar-panel | solar-panel | B/e:5220-5277 | `usage_priority = "solar"`, `production = "60kW"` (B/e:5236, 5276) | `{{-1.4,-1.4},{1.4,1.4}}` / `{{-1.5,-1.5},{1.5,1.5}}` | `"solar-panel"` | 50 / energy (item.lua:937) |
| boiler | boiler | B/e:1221-1528 | `energy_consumption = "1.8MW"`, burner chemical, `target_temperature = 165` | `{{-1.29,-0.79},{1.29,0.79}}` / `{{-1.5,-1},{1.5,1}}` | `"boiler"` | 50 / energy (item.lua:347) |
| steam-engine | generator | B/e:1756-1898 | `fluid_usage_per_tick = 0.5`, `maximum_temperature = 165`, `effectivity = 1`, `secondary-output` | `{{-1.25,-2.35},{1.25,2.35}}` / `{{-1.5,-2.5},{1.5,2.5}}` | `"steam-engine"` | 10 / energy (item.lua:360) |
| steam-turbine | generator | B/e:9244-9388 | `fluid_usage_per_tick = 1`, `maximum_temperature = 500`, `burns_fluid = false` | same as steam-engine | `"steam-engine"` (shared!) | 10 / energy (item.lua:2372) |
| nuclear-reactor | reactor | B/e:8568-8797 | `consumption = "40MW"`, burner nuclear, `burnt_inventory_size = 1`, `neighbour_bonus = 1` | `{{-2.2,-2.2},{2.2,2.2}}` / `{{-2.5,-2.5},{2.5,2.5}}` | `"reactor"` | 10 / energy (item.lua:2242) |
| heat-exchanger | boiler (heat source) | B/e:8991-9243 | `energy_consumption = "10MW"`, `target_temperature = 500` | same as boiler | `"heat-exchanger"` | 50 / energy (item.lua:2358) |
| heat-pipe | heat-pipe | B/e:9389-… | heat_buffer `specific_heat = "1MJ"`, `max_transfer = "1GW"` (B/e:9427-9433) | n/a here | `"heat-pipe"` | 50 / energy (item.lua:2385) |
| burner-generator (hidden) | burner-generator | B/e:9945-9993 | `max_power_output = "1MW"`, burner chemical `effectivity = 0.5` | `{{-1.35,-2.35},{1.35,2.35}}` / `{{-1.5,-2.5},{1.5,2.5}}` | none | 10 / other (item.lua:2467) |
| electric-energy-interface (hidden) | electric-energy-interface | B/e:8537-8567 | `buffer_capacity = "10GJ"`, `tertiary`, `energy_production = "500GW"` | `{{-0.9,-0.9},{0.9,0.9}}` / `{{-1,-1},{1,1}}` | none | 50 / other (item.lua:2216) |
| hidden-electric-energy-interface | electric-energy-interface | B/e:5355-5382 | `10GJ`, in `0kW`, out `500GW`, `energy_production = "500GW"` | zero boxes, `selectable_in_game = false` | none | no item |
| lightning-rod (SA) | lightning-attractor | SA/e:1780-1860 | `efficiency = 0.2`, `range_elongation = 15.0`, buffer `500MJ`, `primary-output`, out `500MJ`, `drain = "2.5MJ"` | `{{-0.15,-0.15},{0.15,0.15}}` / `{{-0.5,-0.5},{0.5,0.5}}` | none | 50 / environmental-protection (SA item.lua:1336) |
| lightning-collector (SA) | lightning-attractor | SA/e:1862-1947 | `efficiency = 0.4`, `range_elongation = 25.0`, buffer `1000MJ`, out `1000MJ`, drain `2.5MJ` | `{{-0.7,-0.7},{0.7,0.7}}` / `{{-1,-1},{1,1}}` | none | 20 (SA item.lua:1350) |
| fusion-generator (SA) | fusion-generator | SA/e:2330-2413 | `secondary-output`, `output_flow_limit = "50MW"`, `max_fluid_usage = 2/second` | `{{-1.4,-2.4},{1.4,2.4}}` / `{{-1.5,-2.5},{1.5,2.5}}` | `"fusion-generator"` | 5 (SA item.lua:1567) |
| fusion-reactor (SA) | fusion-reactor | SA/e:2414-2522 | electric `primary-input`, `power_input = "10MW"`, burner `fuel_categories = {"fusion"}` | `{{-2.9,-2.9},{2.9,2.9}}` / `{{-3,-3},{3,3}}` | `"fusion-reactor"` | 1 (SA item.lua:1553) |
| heating-tower (SA) | reactor | SA/e:2066-… | `consumption = "40MW"`, burner chemical `effectivity = 2.5`, fuel/burnt 2/2, `neighbour_bonus = 0`, pressure ≥ 10 | `{{-1.25,-1.25},{1.25,1.25}}` / `{{-1.5,-1.5},{1.5,1.5}}` | none | 20 (SA item.lua:1364) |

---

## 2. Energy-related types (prototype-api.json)

### 2.1 `Energy` (string)
API type `Energy`: "Specifies an amount of electric energy in joules, or electric energy per time in watts. Internally, the input in `Watt` or `Joule/second` is always converted into `Joule/tick` … `Power in Joule/tick = Power in Watt / 60`." Multipliers: `k, M, G, T, P, E, Z, Y, R, Q`. API example:
```lua
buffer_capacity = "5MJ"
input_flow_limit = "300W"
-- the following two lines result in the same power consumption:
energy_usage = "60W"
energy_usage = "1J" -- not recommended, Watt is convention for power
```
Note: SA writes `output_flow_limit = "500MJ"` in J, not W, for the lightning-rod (SA/e:1790). By the API text above, that is read as J/s.

### 2.2 `EnergySource` union
API type `EnergySource`: `ElectricEnergySource | BurnerEnergySource | HeatEnergySource | FluidEnergySource | VoidEnergySource`. The `type` key picks the variant.

### 2.3 `BaseEnergySource` (abstract; shared by all variants)
- `emissions_per_minute`: `dict[AirbornePollutantID -> double]`, optional. "The pollution an entity emits per minute at full energy consumption."
- `render_no_power_icon`: boolean, default `true`
- `render_no_network_icon`: boolean, default `true`

### 2.4 `ElectricEnergySource` (`type = "electric"`)
| field | type | req | default | API description |
|---|---|---|---|---|
| type | `"electric"` | REQUIRED | | |
| buffer_capacity | Energy | opt | | "How much energy this entity can hold." |
| usage_priority | ElectricUsagePriority | REQUIRED | | |
| input_flow_limit | Energy | opt | Max `double` | "The rate at which energy can be taken, from the network, to refill the energy buffer. `0` means no transfer." |
| output_flow_limit | Energy | opt | Max `double` | "The rate at which energy can be provided, to the network, from the energy buffer. `0` means no transfer." |
| drain | Energy | opt | | "How much energy (per second) will be continuously removed from the energy buffer. … 'Min. Consumption'." |

API examples (verbatim from `ElectricEnergySource.examples`):
```lua
energy_source = -- energy source of oil pumpjack
{
  type = "electric",
  emissions_per_minute = { pollution = 10 },
  usage_priority = "secondary-input"
}
energy_source = -- energy source of accumulator
{
  type = "electric",
  buffer_capacity = "5MJ",
  usage_priority = "tertiary",
  input_flow_limit = "300kW",
  output_flow_limit = "300kW"
}
energy_source = -- energy source of steam engine
{
  type = "electric",
  usage_priority = "secondary-output"
}
```

### 2.5 `ElectricUsagePriority` (literal union, with the API's own descriptions)
- `"primary-input"`: "Used for the most important machines, for example laser turrets."
- `"primary-output"`: (no description). Used by SA lightning-rod and lightning-collector.
- `"secondary-input"`: "Used for all other machines."
- `"secondary-output"`: "Used in steam generators." Used by steam-engine, steam-turbine, burner-generator and fusion-generator.
- `"tertiary"`: "As input/output used for accumulators, to collect the overproduction or provide energy when neither primary/secondary output can't." Used by accumulator and both EEIs.
- `"solar"`: "Can only be used by SolarPanelPrototype, will be ignored otherwise."
- `"lamp"`: "Can only be used by LampPrototype, will be ignored otherwise."

### 2.6 `BurnerEnergySource` (`type = "burner"`), 2.0 format
| field | type | req | default |
|---|---|---|---|
| type | `"burner"` | REQUIRED | |
| fuel_inventory_size | ItemStackIndex | REQUIRED | |
| burnt_inventory_size | ItemStackIndex | opt | `0` |
| smoke | array[SmokeSource] | opt | |
| light_flicker | LightFlickeringDefinition | opt | |
| effectivity | double | opt | `1` ("`1` means 100% effectivity. Must be greater than `0`. Multiplier of the energy output.") |
| burner_usage | BurnerUsageID | opt | `"fuel"` |
| fuel_categories | array[FuelCategoryID] | opt | `{"chemical"}` |
| initial_fuel | ItemID | opt | `""` |
| initial_fuel_percent | double | opt | `0.25` |
| (+ emissions_per_minute etc. from BaseEnergySource) | | | |

The API has no `fuel_category` (singular) field; changelog.txt:3154 records its removal. Changelog.txt:3672 (2.0.7 section) says: "Changed burner energy sources without burnt result inventory to void burnt results instead of getting stuck." So a fuel with a `burnt_result` burned in a machine whose `burnt_inventory_size` is 0 has its burnt result deleted.

All burner energy sources in the data (every one uses `fuel_categories`):

| Where | Entity | Fields |
|---|---|---|
| B/e:1075 | stone-furnace | chemical, eff 1, fuel 1, pollution 2 |
| B/e:1279 | boiler | chemical, eff 1, fuel 1, pollution 30 |
| B/e:2614 | burner-inserter | chemical, `initial_fuel = "wood"`, `initial_fuel_percent = 0.25`, eff 1, fuel 1 |
| B/e:4016 | car | chemical, eff 1, fuel 1 |
| B/e:4788 | steel-furnace | chemical, eff 1, pollution 4, fuel 1 |
| B/e:7690 | tank | chemical, eff 1, fuel 2 |
| B/e:8583 | nuclear-reactor | **nuclear**, eff 1, fuel 1, **burnt 1** |
| B/e:9970 | burner-generator (`burner` field) | chemical, **eff 0.5**, fuel 1, pollution 10 |
| base/prototypes/entity/trains.lua:549 | locomotive | chemical, eff 1, fuel 3 |
| base/prototypes/entity/mining-drill.lua:1594 | burner-mining-drill | chemical, eff 1, fuel 1, pollution 12 |
| SA/e:112 | biochamber | nutrients, `burner_usage = "nutrients"`, pollution -1 |
| SA/e:1553 | captive-biter-spawner | food, `burner_usage = "food"`, pollution -1 |
| SA/e:2087 | heating-tower | chemical, **eff 2.5**, fuel 2, burnt 2, pollution 100 |
| SA/e:2481 | fusion-reactor (`burner` field) | **fusion**, eff 1, fuel 1, pollution 0 |

Canonical boiler burner (B/e:1276-1302, verbatim):
```lua
    energy_consumption = "1.8MW",
    energy_source =
    {
      type = "burner",
      fuel_categories = {"chemical"},
      effectivity = 1,
      fuel_inventory_size = 1,
      emissions_per_minute = { pollution = 30 },
      light_flicker =
      {
        color = {0,0,0},
        minimum_intensity = 0.6,
        maximum_intensity = 0.95
      },
      smoke =
      {
        {
          name = "smoke",
          north_position = util.by_pixel(-38, -47.5),
          south_position = util.by_pixel(38.5, -32),
          east_position = util.by_pixel(20, -70),
          west_position = util.by_pixel(-19, -8.5),
          frequency = 15,
          starting_vertical_speed = 0.0,
          starting_frame_deviation = 60
        }
      }
    },
```

### 2.7 `HeatEnergySource` / `HeatBuffer` (brief)
Both have REQUIRED `max_temperature` (double, ≥ default_temperature), `specific_heat` (Energy) and `max_transfer` (Energy). Optional: `default_temperature` = 15, `min_temperature_gradient` = 1, `min_working_temperature` = 15, `minimum_glow_temperature` = 1, `pipe_covers`, `heat_pipe_covers`, `heat_picture`, `heat_glow` (all Sprite4Way), and `connections: array[HeatConnection]` ("May contain up to 32 connections"). `HeatEnergySource` adds `type = "heat"`.

### 2.8 `FluidEnergySource` / `VoidEnergySource` (brief)
`FluidEnergySource` (`type = "fluid"`) has REQUIRED `fluid_box`. Optional: `effectivity`, `burns_fluid`, `scale_fluid_usage`, `destroy_non_fuel_fluid`, `fluid_usage_per_tick`, `maximum_temperature`, `smoke`, `light_flicker`. `VoidEnergySource` (`type = "void"`): "Void energy sources provide unlimited free energy."

---

## 3. Electric poles (`ElectricPolePrototype`, typename `electric-pole`)

### 3.1 API (all own properties)
Inheritance: `ElectricPolePrototype < EntityWithOwnerPrototype < EntityWithHealthPrototype < EntityPrototype < Prototype < PrototypeBase`. Fields required across the whole chain: `connection_points`, `supply_area_distance`, `name`, `type`. `icon`/`icons` is conditionally mandatory; see section 10.

| field | type | req | default | notes (API) |
|---|---|---|---|---|
| pictures | RotatedSprite | opt | | |
| supply_area_distance | double | REQUIRED | | "The 'radius' of this pole's supply area. Corresponds to *half* of the 'supply area' in the item tooltip. If this is 3.5, the pole will have a 7x7 supply area. Max value is 64." |
| connection_points | array[WireConnectionPoint] | REQUIRED | | |
| radius_visualisation_picture | Sprite | opt | | |
| active_picture | Sprite | opt | | "Drawn above the `pictures` when the electric pole is connected to an electric network." |
| maximum_wire_distance | double | opt | `0` | "The maximum distance between this pole and any other connected pole … 'wire reach' in the item tooltip. Max value is 64." |
| draw_copper_wires / draw_circuit_wires | boolean | opt | `true` | |
| light | LightDefinition | opt | | "Drawn when the electric pole is connected to an electric network." |
| track_coverage_during_drag_building | boolean | opt | `true` | big-electric-pole sets `false` (B/e:4497) |
| auto_connect_up_to_n_wires | uint8 | opt | `5` | "`0` means disable auto-connect." |
| rewire_neighbours_when_destroying | boolean | opt | `true` | added in 2.0.40 (changelog.txt:1272) |

`WireConnectionPoint` = `{ wire: WirePosition (REQUIRED), shadow: WirePosition (REQUIRED) }`. `WirePosition` = `{ copper?: Vector, red?: Vector, green?: Vector }`.

Quality effects on poles (API `QualityPrototype`): `electric_pole_wire_reach_bonus` (float, default `2 * level`, additive) and `electric_pole_supply_area_distance_bonus` (float, default `level`). Changelog.txt:1759 (2.0.29): "Fixed that quality could add a supply area to an electric pole without one." Quality levels: normal `level = 0` (`base/prototypes/categories/quality.lua:5-6`); uncommon 1, rare 2, epic 3, legendary **5** (`quality/prototypes/quality.lua:5-48`).

Relevant 2.0 changelog lines (2.0.7 section): "Increased Big electric pole maximum wire reach from 30 to 32." (3099), "Electric poles are no longer limited to 5 copper connections to other electric poles." (2957), "Added ElectricPolePrototype::auto_connect_up_to_n_wires." (3228), "Removed LuaEntity::neighbours support for electric poles and power switches." (3452).

### 3.2 Small electric pole, verbatim (B/e:1629-1754, reflection trimmed)
```lua
  {
    type = "electric-pole",
    name = "small-electric-pole",
    icon = "__base__/graphics/icons/small-electric-pole.png",
    quality_indicator_scale = 0.75,
    flags = {"placeable-neutral", "player-creation"},
    minable = {mining_time = 0.1, result = "small-electric-pole"},
    max_health = 100,
    corpse = "small-electric-pole-remnants",
    dying_explosion = "small-electric-pole-explosion",
    collision_box = {{-0.15, -0.15}, {0.15, 0.15}},
    selection_box = {{-0.4, -0.4}, {0.4, 0.4}},
    damaged_trigger_effect = hit_effects.entity({{-0.2, -2.2}, {0.2, 0.2}}),
    drawing_box_vertical_extension = 2.2,
    maximum_wire_distance = 7.5,
    supply_area_distance = 2.5,
    impact_category = "wood",
    open_sound = sounds.electric_network_open,
    close_sound = sounds.electric_network_close,
    fast_replaceable_group = "electric-pole",
    pictures =
    {
      layers =
      {
        {
          filename = "__base__/graphics/entity/small-electric-pole/small-electric-pole.png",
          priority = "extra-high",
          width = 72,
          height = 220,
          direction_count = 4,
          shift = util.by_pixel(1.5, -42.5),
          scale = 0.5
        },
        {
          filename = "__base__/graphics/entity/small-electric-pole/small-electric-pole-shadow.png",
          priority = "extra-high",
          width = 256,
          height = 52,
          direction_count = 4,
          shift = util.by_pixel(51, 3),
          draw_as_shadow = true,
          scale = 0.5
        }
      }
    },
    connection_points =
    {
      {
        shadow =
        {
          copper = util.by_pixel(98.5, 2.5),
          red = util.by_pixel(111.0, 4.5),
          green = util.by_pixel(85.5, 4.0)
        },
        wire =
        {
          copper = util.by_pixel(0.0, -82.5),
          red = util.by_pixel(13.0, -81.0),
          green = util.by_pixel(-12.5, -81.0)
        }
      },
      -- … three more entries of the same shape (B/e:1690-1731): one per direction_count
    },
    radius_visualisation_picture =
    {
      filename = "__base__/graphics/entity/small-electric-pole/electric-pole-radius-visualization.png",
      width = 12,
      height = 12,
      priority = "extra-high-no-scale"
    },
    water_reflection = { … }
  },
```
All four vanilla poles use `direction_count = 4` in both picture layers and exactly 4 `connection_points` entries (small B/e:1674-1732, medium B/e:4657-4715, big B/e:4523-4581, substation B/e:7374-7432). The API text does not state that the counts must match; the base data always keeps them equal.

Coordinate helpers (`core/lualib/util.lua:174-180`):
```lua
function util.by_pixel(x,y)
  return {x / 32, y / 32}
end

function util.by_pixel_hr(x,y)
  return {x / 64, y / 64}
end
```
Small pole and substation use `util.by_pixel`; medium and big use `util.by_pixel_hr`.

Other pole differences:
- medium pole: `resistances = {{type = "fire", percent = 100}}`, `impact_category = "metal"`, `drawing_box_vertical_extension = 2.3`, `quality_indicator_scale = 0.75` (B/e:4605-4631).
- big pole: `max_health = 150`, fire 100%, explicit `collision_mask = {layers={item=true, object=true, player=true, water_tile=true, elevated_rail=true, is_object=true, is_lower_object=true}}` (B/e:4488), `track_coverage_during_drag_building = false`.
- substation: `max_health = 200`, fire 90%, `drawing_box_vertical_extension = 2`, has a `working_sound` (`__base__/sound/substation.ogg`), pictures `priority = "high"` (B/e:7308-7373).
- `radius_visualisation_picture` is the same file for all four: `__base__/graphics/entity/small-electric-pole/electric-pole-radius-visualization.png`.

Recipes (`base/prototypes/recipe.lua`): small `{wood 1, copper-cable 2}` gives 2 (l.871-881). Medium `{iron-stick 4, steel-plate 2, copper-cable 2}` (l.1138-1149). Big `{iron-stick 8, steel-plate 5, copper-cable 4}` (l.1126-1137). Substation `{steel-plate 10, advanced-circuit 5, copper-cable 6}` (l.2221-2232). Space Age sets `category = "electronics"` on all four recipes (`space-age/base-data-updates.lua:312-318`).

---

## 4. Accumulator (`AccumulatorPrototype`, typename `accumulator`)

API own properties:
- `energy_source`: ElectricEnergySource, REQUIRED. "The capacity of the energy source buffer specifies the capacity of the accumulator."
- `chargable_graphics`: ChargableGraphics, opt
- `circuit_wire_max_distance`: double, default `0`
- `draw_copper_wires`, `draw_circuit_wires`: boolean, default `true`
- `circuit_connector`: CircuitConnectorDefinition, opt
- `default_output_signal`: SignalIDConnector, opt

`ChargableGraphics`: `picture` (Sprite), `charge_animation` (Animation), `charge_animation_is_looped` (bool, default true), `charge_light`, `charge_cooldown` (uint16, default 0), `discharge_animation`, `discharge_light`, `discharge_cooldown` (uint16, default 0); every field is optional. Changelog.txt (2.0.7): "Added AccumulatorPrototype::chargable_graphics and moved graphics related properties there." Quality: `QualityPrototype.accumulator_capacity_multiplier`, default `1 + level`.

Verbatim (B/e:5279-5353, sound block trimmed):
```lua
  {
    type = "accumulator",
    name = "accumulator",
    icon = "__base__/graphics/icons/accumulator.png",
    flags = {"placeable-neutral", "player-creation"},
    minable = {mining_time = 0.1, result = "accumulator"},
    fast_replaceable_group = "accumulator",
    max_health = 150,
    corpse = "accumulator-remnants",
    dying_explosion = "accumulator-explosion",
    collision_box = {{-0.9, -0.9}, {0.9, 0.9}},
    selection_box = {{-1, -1}, {1, 1}},
    damaged_trigger_effect = hit_effects.entity(),
    drawing_box_vertical_extension = 0.5,
    energy_source =
    {
      type = "electric",
      buffer_capacity = "5MJ",
      usage_priority = "tertiary",
      input_flow_limit = "300kW",
      output_flow_limit = "300kW"
    },
    chargable_graphics =
    {
      picture = accumulator_picture(),
      charge_animation = accumulator_charge(),
      charge_cooldown = 30,
      discharge_animation = accumulator_discharge(),
      discharge_cooldown = 60
      --discharge_light = {intensity = 0.7, size = 7, color = {r = 1.0, g = 1.0, b = 1.0}},
    },
    water_reflection = accumulator_reflection(),
    impact_category = "metal",
    open_sound = sounds.electric_large_open,
    close_sound = sounds.electric_large_close,
    working_sound = { … },
    circuit_connector = circuit_connector_definitions["accumulator"],
    circuit_wire_max_distance = default_circuit_wire_max_distance,

    default_output_signal = {type = "virtual", name = "signal-A"}
  },
```
The helpers are **global** functions in B/e: `accumulator_picture(tint, repeat_count)` (l.125-152, two layers: `accumulator.png` 130×189 and `accumulator-shadow.png` 234×106, scale 0.5, with a `tint` parameter), `accumulator_charge()` (l.154-173), `accumulator_reflection()` (l.175-191) and `accumulator_discharge()` (l.193-212). `accumulator_picture({1, 0.8, 1, 1})` is how base tints the EEI (B/e:8563); a mod can make a tinted accumulator the same way. `circuit_connector_definitions["accumulator"]` is set in `core/lualib/circuit-connector-generated-definitions.lua:517`. `default_circuit_wire_max_distance = 9` is set in `core/lualib/circuit-connector-sprites.lua:95`.

Recipe: `{iron-plate 2, battery 5}`, `energy_required = 10` (recipe.lua:2233-2244). SA sets `category = "electronics"` (space-age/base-data-updates.lua:309). The accumulator is an ingredient of SA's `electromagnetic-science-pack` (SA recipe.lua:828) and `lightning-collector` (SA recipe.lua:2290).

---

## 5. Solar panel (`SolarPanelPrototype`, typename `solar-panel`)

API own properties:
- `energy_source`: ElectricEnergySource, REQUIRED
- `picture`: SpriteVariations, opt
- `production`: Energy, REQUIRED. "The maximum amount of power this solar panel can produce."
- `overlay`: SpriteVariations, opt. "Overlay has to be empty or have same number of variations as `picture`."
- `performance_at_day`: double, default `1`
- `performance_at_night`: double, default `0`
- `solar_coefficient_property`: SurfacePropertyID, default `"solar-power"`. "Surface property must have a positive default value. When [it] is set to point at a different surface property than 'solar-power', then LuaSurface::solar_power_multiplier and SpaceLocationPrototype::solar_power_in_space will be ignored…"

Verbatim (B/e:5220-5277):
```lua
  {
    type = "solar-panel",
    name = "solar-panel",
    icon = "__base__/graphics/icons/solar-panel.png",
    flags = {"placeable-neutral", "player-creation"},
    minable = {mining_time = 0.1, result = "solar-panel"},
    fast_replaceable_group = "solar-panel",
    max_health = 200,
    corpse = "solar-panel-remnants",
    dying_explosion = "solar-panel-explosion",
    collision_box = {{-1.4, -1.4}, {1.4, 1.4}},
    selection_box = {{-1.5, -1.5}, {1.5, 1.5}},
    damaged_trigger_effect = hit_effects.entity(),
    energy_source =
    {
      type = "electric",
      usage_priority = "solar"
    },
    picture =
    {
      layers =
      {
        { filename = "__base__/graphics/entity/solar-panel/solar-panel.png", priority = "high", width = 230, height = 224, shift = util.by_pixel(-3, 3.5), scale = 0.5 },
        { filename = "__base__/graphics/entity/solar-panel/solar-panel-shadow.png", priority = "high", width = 220, height = 180, shift = util.by_pixel(9.5, 6), draw_as_shadow = true, scale = 0.5 }
      }
    },
    overlay = { layers = { { filename = "__base__/graphics/entity/solar-panel/solar-panel-shadow-overlay.png", priority = "high", width = 214, height = 180, shift = util.by_pixel(10.5, 6), scale = 0.5 } } },
    impact_category = "glass",
    production = "60kW"
  },
```
(The picture layers are written one per line here; each field is verbatim.)

The `solar-power` surface property is defined in base with `default_value = 100` (`base/prototypes/planet/surface-property.lua:17-21`). Nauvis has `solar_power_in_space = 300` and does not set `solar-power` (`base/prototypes/planet/planet.lua:22,28-31`). SA planets (`space-age/prototypes/planet/planet.lua`): vulcanus `solar-power = 400`, in space 600. Gleba 50 / 200. Fulgora 20 / 120. Aquilo 1 / 60. Recipe: `{steel-plate 5, electronic-circuit 15, copper-plate 5}`, `energy_required = 10` (recipe.lua:1333-1345). SA sets category `electronics` (space-age/base-data-updates.lua:252).

---

## 6. Boiler and generators

### 6.1 `BoilerPrototype` (typename `boiler`)
REQUIRED own fields: `energy_source` (EnergySource), `fluid_box`, `output_fluid_box`, `energy_consumption` (Energy), `burning_cooldown` (uint16). Optional: `pictures` (BoilerPictureSet), `target_temperature` (float; "Only loaded, and mandatory if `mode` is `output-to-separate-pipe`"), `fire_glow_flicker_enabled`/`fire_flicker_enabled` (default false), `mode` (`"heat-fluid-inside"` (default) | `"output-to-separate-pipe"`). About the output filter the API says: "the heated input fluid is converted to the filtered fluid in a ratio … `output_fluid_amount = input_fluid_amount * (output_fluid_heat_capacity / input_fluid_heat_capacity)`".

`BoilerPictureSet` = `{north, east, south, west}`, all REQUIRED, each a `BoilerPictures` = `{structure: Animation (REQUIRED), patch?: Sprite, fire?: Animation, fire_glow?: Animation}`.

Boiler, verbatim non-graphics part (B/e:1221-1275). The burner block is quoted in section 2.6. The tail at B/e:1524-1527 is `fire_flicker_enabled = true, fire_glow_flicker_enabled = true, burning_cooldown = 20, water_reflection = boiler_reflection()`.
```lua
  {
    type = "boiler",
    name = "boiler",
    icon = "__base__/graphics/icons/boiler.png",
    flags = {"placeable-neutral", "player-creation"},
    minable = {mining_time = 0.2, result = "boiler"},
    fast_replaceable_group = "boiler",
    max_health = 200,
    corpse = "boiler-remnants",
    dying_explosion = "boiler-explosion",
    impact_category = "metal-large",
    mode = "output-to-separate-pipe",
    resistances = { {type = "fire", percent = 90}, {type = "explosion", percent = 30}, {type = "impact", percent = 30} },
    collision_box = {{-1.29, -0.79}, {1.29, 0.79}},
    selection_box = {{-1.5, -1}, {1.5, 1}},
    damaged_trigger_effect = hit_effects.entity(),
    target_temperature = 165,
    fluid_box =
    {
      volume = 200,
      pipe_covers = pipecoverspictures(),
      pipe_connections =
      {
        {flow_direction = "input-output", direction = defines.direction.west, position = {-1, 0.5}},
        {flow_direction = "input-output", direction = defines.direction.east, position = {1, 0.5}}
      },
      production_type = "input",
      filter = "water"
    },
    output_fluid_box =
    {
      volume = 200,
      pipe_covers = pipecoverspictures(),
      pipe_connections =
      {
        {flow_direction = "output", direction = defines.direction.north, position = {0, -0.5}}
      },
      production_type = "output",
      filter = "steam"
    },
    energy_consumption = "1.8MW",
```
Pictures (B/e:1312-1522): each direction has `structure = {layers = {idle, shadow}}`, `fire` (64 frames, `line_length = 8`, `draw_as_glow = true`) and `fire_glow` (`blend_mode = "additive"`). East also has `patch`. Recipe `{stone-furnace 1, pipe 4}` (recipe.lua:726-732). **Space Age** adds `data.raw["boiler"]["boiler"].surface_conditions = ten_pressure_condition()`, i.e. `{{property = "pressure", min = 10}}` (space-age/base-data-updates.lua:163-171, 187).

### 6.2 `GeneratorPrototype` (typename `generator`): steam engine and turbine
REQUIRED: `energy_source` (ElectricEnergySource), `fluid_box` ("must have a filter if `max_power_output` is not defined"), `fluid_usage_per_tick` (FluidAmount), `maximum_temperature` (float). Optional: `horizontal_animation`, `vertical_animation` (Animation), `horizontal_frozen_patch`, `vertical_frozen_patch` (Sprite), `effectivity` (default 1), `smoke`, `burns_fluid` (default false), `scale_fluid_usage` (default false), `destroy_non_fuel_fluid` (default true), `perceived_performance`, `max_power_output` (Energy; "The power production of the generator is capped to this value").

The API formula, verbatim from `maximum_temperature`: "the max power output is `(min(fluid_max_temp, maximum_temperature) - fluid_default_temp) × fluid_usage_per_tick × fluid_heat_capacity × effectivity`".

Steam (`base/prototypes/fluid.lua:40-49`): `default_temperature = 15`, `max_temperature = 5000`, `heat_capacity = "0.2kJ"`. Water (l.28-32): `default_temperature = 15`, `max_temperature = 100`, `heat_capacity = "2kJ"`.
- **Derived**, steam-engine: (165 − 15) × 0.5 × 0.2 kJ × 1 = 15 kJ/tick = **900 kW**.
- **Derived**, steam-turbine: (500 − 15) × 1 × 0.2 kJ = 97 kJ/tick = **5.82 MW**.
- **Derived**, boiler: 1.8 MW / ((165 − 15) × 0.2 kJ) = 60 steam/s. That feeds 2 steam engines (each 0.5/tick × 60 = 30/s). By the boiler conversion formula it uses 60 × (0.2/2) = 6 water/s.

Steam engine, verbatim non-graphics (B/e:1756-1801):
```lua
  {
    type = "generator",
    name = "steam-engine",
    icon = "__base__/graphics/icons/steam-engine.png",
    flags = {"placeable-neutral","player-creation"},
    minable = {mining_time = 0.3, result = "steam-engine"},
    max_health = 400,
    corpse = "steam-engine-remnants",
    dying_explosion = "steam-engine-explosion",
    alert_icon_shift = util.by_pixel(0, -12),
    effectivity = 1,
    fluid_usage_per_tick = 0.5,
    maximum_temperature = 165,
    resistances = { {type = "fire", percent = 70}, {type = "impact", percent = 30} },
    fast_replaceable_group = "steam-engine",
    collision_box = {{-1.25, -2.35}, {1.25, 2.35}},
    selection_box = {{-1.5, -2.5}, {1.5, 2.5}},
    damaged_trigger_effect = hit_effects.entity(),
    fluid_box =
    {
      volume = 200,
      pipe_covers = pipecoverspictures(),
      pipe_connections =
      {
        { flow_direction = "input-output", direction = defines.direction.south, position = {0, 2} },
        { flow_direction = "input-output", direction = defines.direction.north, position = {0, -2} }
      },
      production_type = "input",
      filter = "steam",
      minimum_temperature = 100.0
    },
    energy_source =
    {
      type = "electric",
      usage_priority = "secondary-output"
    },
```
Animations: `horizontal_animation` / `vertical_animation`, each `{layers = {main (frame_count 32, line_length 8), shadow (draw_as_shadow)}}` (B/e:1802-1851). Also `smoke = {{name = "light-smoke", …}}`, `perceived_performance = {minimum = 0.25, performance_to_activity_rate = 2.0}` (B/e:1852-1882).

Steam turbine (B/e:9244-9285) differs as follows: `max_health = 300`, `fluid_usage_per_tick = 1`, `maximum_temperature = 500`, `burns_fluid = false`, no impact resistance. It uses the same `fast_replaceable_group = "steam-engine"`, the same boxes and fluid_box, 8-frame animations with `run_mode = "backward"`, and `smoke = {{name = "turbine-smoke", …}}`. Recipes: steam-engine `{iron-gear-wheel 8, pipe 5, iron-plate 10}` (recipe.lua:733-744); steam-turbine `{iron-gear-wheel 50, copper-plate 50, pipe 20}`, `energy_required = 3` (recipe.lua:2621-2628). **Space Age:** `heating_energy = "50kW"` on both (space-age/base-data-updates.lua:109-110).

---

## 7. Burner generator (`BurnerGeneratorPrototype`, typename `burner-generator`)

### 7.1 API (verbatim property list)
Inheritance: `BurnerGeneratorPrototype < EntityWithOwnerPrototype < EntityWithHealthPrototype < EntityPrototype < Prototype < PrototypeBase`. Description: "An entity that produces power from a burner energy source."

| field | type | req | default | API text |
|---|---|---|---|---|
| energy_source | ElectricEnergySource | **REQUIRED** | | "The output energy source of the generator. Any emissions specified on this energy source are ignored, they must be specified on `burner`." |
| burner | BurnerEnergySource | **REQUIRED** | | "The input energy source of the generator." |
| animation | Animation4Way | opt | | "Plays when the generator is active. `idle_animation` must have the same frame count as animation." |
| max_power_output | Energy | **REQUIRED** | | "How much energy this generator can produce." |
| idle_animation | Animation4Way | opt | | "Plays when the generator is inactive. Idle animation must have the same frame count as `animation`." |
| always_draw_idle_animation | boolean | opt | `false` | "Whether the `idle_animation` should also play when the generator is active." |
| perceived_performance | PerceivedPerformance | opt | | "Affects animation speed and working sound." |

Fields required across the whole chain: `burner`, `energy_source`, `max_power_output`, `name`, `type`. **`animation` and `idle_animation` are optional.** `Animation4Way` = struct `{north (REQUIRED), north_east?, east?, south_east?, south?, south_west?, west?, north_west?}` **or** a single `Animation`: "If this is loaded as a single Animation, it applies to all directions. Any direction that is not defined defaults to the north animation." `PerceivedPerformance` = `{minimum? (default 0), maximum? (default max double), performance_to_activity_rate? (default 1)}`. The API JSON has no `examples` entry for this prototype.

### 7.2 The only definition in the data: base, hidden (B/e:9945-9993, verbatim)
```lua
data:extend({
{
  name = "burner-generator",
  type = "burner-generator",
  icon = "__base__/graphics/icons/steam-engine.png",
  flags = {"placeable-neutral","player-creation"},
  hidden = true,
  max_health = 400,
  dying_explosion = "medium-explosion",
  corpse = "steam-engine-remnants",
  collision_box = {{-1.35, -2.35}, {1.35, 2.35}},
  selection_box = {{-1.5, -2.5}, {1.5, 2.5}},
  max_power_output = "1MW",
  minable = {mining_time = 1, result = "burner-generator"},
  animation =
  {
    north = util.table.deepcopy(data.raw.generator["steam-engine"].vertical_animation),
    east = util.table.deepcopy(data.raw.generator["steam-engine"].horizontal_animation),
    south = util.table.deepcopy(data.raw.generator["steam-engine"].vertical_animation),
    west = util.table.deepcopy(data.raw.generator["steam-engine"].horizontal_animation)
  },
  -- idle_animation can also be specified
  perceived_performance = {minimum = 0.25, performance_to_activity_rate = 2.0},
  burner =
  {
    type = "burner",
    fuel_categories = {"chemical"},
    effectivity = 0.5,
    fuel_inventory_size = 1,
    emissions_per_minute = { pollution = 10 },
    smoke =
    {
      {
        name = "smoke",
        north_position = {0.9, 0.0},
        east_position = {-2.0, -2.0},
        deviation = {0.1, 0.1},
        frequency = 9
      }
    }
  },
  energy_source =
  {
    type = "electric",
    usage_priority = "secondary-output"
  }
}})
```
Hidden item (`base/prototypes/item.lua:2465-2478`):
```lua
  {
    type = "item",
    name = "burner-generator",
    icon = "__base__/graphics/icons/steam-engine.png",
    hidden = true,
    subgroup = "other",
    order = "t[item]-o[burner-generator]",
    inventory_move_sound = item_sounds.mechanical_inventory_move,
    pick_sound = item_sounds.mechanical_inventory_pickup,
    drop_sound = item_sounds.mechanical_inventory_move,
    stack_size = 10,
    place_result = "burner-generator",
    random_tint_color = item_tints.iron_rust
  },
```
- There is no recipe named `burner-generator` in base or SA recipe files, and no technology unlocks it (checked with grep; the only hits are entities.lua, item.lua and collision-mask-defaults.lua).
- Space Age / quality / elevated-rails: no `type = "burner-generator"` anywhere.
- Default collision mask: `["burner-generator"] = building()` (`core/lualib/collision-mask-defaults.lua:33`).
- Related changelog lines: "Fixed that the burner generator prototype type did not report its max consumption correctly." (2.0.45, changelog.txt:1011); "Added LuaEntityPrototype::max_power_output read support for burner generators." (changelog.txt:4185, a pre-2.0 section). "Changed various entity prototypes to only accept 'energy_source' for the energy source, not 'burner'." (2.0.7, changelog.txt:3211). This does not affect burner-generator: its API still has a separate REQUIRED `burner` field.
- Runtime: `LuaEntityPrototype.get_max_power_output(quality?)`: "The maximum power output of this burner generator or generator prototype." `LuaEntityPrototype.max_power_output` is deprecated in its favor. `LuaEntityPrototype.burner_prototype` gives `LuaBurnerPrototype`, and `LuaEntity.burner` gives `LuaBurner`.

**Derived:** coal (4 MJ, section 9) in the base burner-generator: 4 MJ × 0.5 = 2 MJ of electricity per coal. At the full 1 MW that is one coal every 2 s.

### 7.3 Minimal mod template (a suggestion built from the base pattern; not in the sources as written)
```lua
local gen = {
  type = "burner-generator",
  name = "magnetics-dynamo",            -- must NOT be "burner-generator" (taken by base)
  icon = "__base__/graphics/icons/steam-engine.png",
  flags = {"placeable-neutral","player-creation"},
  minable = {mining_time = 0.3, result = "magnetics-dynamo"},
  max_health = 400,
  collision_box = {{-1.35, -2.35}, {1.35, 2.35}},
  selection_box = {{-1.5, -2.5}, {1.5, 2.5}},
  max_power_output = "2MW",
  burner = {type = "burner", fuel_categories = {"chemical"}, effectivity = 0.9,
            fuel_inventory_size = 1, emissions_per_minute = {pollution = 10}},
  energy_source = {type = "electric", usage_priority = "secondary-output"},
  animation = {
    north = util.table.deepcopy(data.raw.generator["steam-engine"].vertical_animation),
    east  = util.table.deepcopy(data.raw.generator["steam-engine"].horizontal_animation),
    south = util.table.deepcopy(data.raw.generator["steam-engine"].vertical_animation),
    west  = util.table.deepcopy(data.raw.generator["steam-engine"].horizontal_animation),
  },
  perceived_performance = {minimum = 0.25, performance_to_activity_rate = 2.0},
}
data:extend({gen})
```

---

## 8. Electric energy interface (`ElectricEnergyInterfacePrototype`, typename `electric-energy-interface`)

API: "Entity with electric energy source with that can have some of its values changed runtime. Useful for modding in energy consumers/producers." REQUIRED: `energy_source` (ElectricEnergySource). Optional: `energy_production` (Energy, default 0; example `energy_production = "500GW"`), `energy_usage` (Energy, default 0; example `energy_usage = "10kW"`), `gui_mode` (`"all" | "none" | "admins"`, default `"none"`), `continuous_animation` (default false), `render_layer` (default `"object"`), `light`, and the graphics chain `picture` (Sprite) → `pictures` (Sprite4Way, "Only loaded if `picture` is not defined") → `animation` → `animations` (Animation4Way). Also `allow_copy_paste` (override, default false).

Base definition used in sandbox/editor (B/e:8537-8567, verbatim):
```lua
  {
    type = "electric-energy-interface",
    name = "electric-energy-interface",
    icons = {{icon = "__base__/graphics/icons/accumulator.png", tint = {1, 0.8, 1, 1}}},
    flags = {"placeable-neutral", "player-creation"},
    hidden = true,
    minable = {mining_time = 0.1, result = "electric-energy-interface"},
    max_health = 150,
    corpse = "medium-remnants",
    subgroup = "other",
    collision_box = {{-0.9, -0.9}, {0.9, 0.9}},
    selection_box = {{-1, -1}, {1, 1}},
    damaged_trigger_effect = hit_effects.entity(),
    drawing_box_vertical_extension = 0.5,
    gui_mode = "all",
    allow_copy_paste = true,
    energy_source =
    {
      type = "electric",
      buffer_capacity = "10GJ",
      usage_priority = "tertiary"
    },

    energy_production = "500GW",
    energy_usage = "0kW",
    -- also 'pictures' for 4-way sprite is available, or 'animation' resp. 'animations'
    picture = accumulator_picture( {1, 0.8, 1, 1} ),
    open_sound = sounds.machine_open,
    close_sound = sounds.machine_close,
    impact_category = "metal",
  },
```
The second base EEI, `hidden-electric-energy-interface` (B/e:5355-5382), has `hidden = true`, zero-size boxes, `selectable_in_game = false`, `energy_source = {type = "electric", buffer_capacity = "10GJ", usage_priority = "tertiary", input_flow_limit = "0kW", output_flow_limit = "500GW"}`, `energy_production = "500GW"` and `picture = {filename = "__core__/graphics/empty.png", …}`. The tutorial `base/tutorials/trains-stations/train-stations.lua:9` places it under a big-electric-pole at the same position, as an invisible power source.

Use in tests (runtime-api.json): `surface.create_entity{name = "electric-energy-interface", position = …, force = …}` (the `LuaSurface.create_entity` params include `name`, `position`, `force`, `quality`, …). Then:
- `LuaEntity.power_production` (read/write double): "The power production specific to the ElectricEnergyInterface entity type."
- `LuaEntity.power_usage` (r/w double): "The power usage specific to the ElectricEnergyInterface entity type."
- `LuaEntity.electric_buffer_size` (r/w double, optional): "Write access is limited to the ElectricEnergyInterface type."
- `LuaEntity.energy` (r/w double): "Energy stored in the entity's energy buffer."
- The units of `power_production`/`power_usage` (per tick or per second) are **not stated in runtime-api.json**.
- Also useful: `LuaEntity.is_connected_to_electric_network()`, `LuaEntity.electric_network_id`, `LuaEntity.status` (defines.entity_status includes `no_power`, `low_power`, `no_fuel`, `charging`, `discharging`, `fully_charged`, `not_plugged_in_electric_network`, `networks_connected`, `networks_disconnected`, `recharging_after_power_outage`), `LuaEntity.get_electric_input_flow_limit(quality?)` / `get_electric_output_flow_limit(quality?)`, `LuaEntity.electric_drain`.
- Pole wiring from a script: `LuaEntity.get_wire_connector(wire_connector_id, or_create)` with `defines.wire_connector_id.pole_copper`, then `LuaWireConnector.connect_to(target, reach_check?, origin?)`.
- Prototype side: `LuaEntityPrototype.get_max_wire_distance(quality?)`, `get_supply_area_distance(quality?)`, `get_max_energy_production(quality?)`, `get_max_energy_usage(quality?)`, `electric_energy_source_prototype` (fields `buffer_capacity`, `drain`, `usage_priority`, `emissions_per_joule`, …).

---

## 9. Fuel items and fuel categories

### 9.1 Fuel item fields (API `ItemPrototype`)
- `fuel_category`: FuelCategoryID, default `""`: "Must exist when a nonzero fuel_value is defined."
- `fuel_value`: Energy, default `"0J"`: "Amount of energy the item gives when used as fuel. Mandatory if `fuel_acceleration_multiplier`, `fuel_top_speed_multiplier` or `fuel_emissions_multiplier` or `fuel_glow_color` are used."
- `burnt_result`: ItemID, default `""`
- `fuel_acceleration_multiplier` / `fuel_top_speed_multiplier`: double, default 1.0, "Must be 0 or positive."
- `fuel_emissions_multiplier`: double, default 1.0
- `fuel_acceleration_multiplier_quality_bonus` / `fuel_top_speed_multiplier_quality_bonus`: default "30% of `(multiplier − 1)`" if multiplier > 1, otherwise 0
- `fuel_glow_color`: Color. Used by ReactorPrototype `use_fuel_glow_color`.

Note that an **item** takes a single `fuel_category` (string), while a **burner** takes `fuel_categories` (list).

### 9.2 All fuel items in the data
| item | file:line | fuel_value | fuel_category | extras |
|---|---|---|---|---|
| wood | base item.lua:47-50 | 2MJ | chemical | |
| coal | base item.lua:61-72 | 4MJ | chemical | |
| solid-fuel | base item.lua:771-776 | 12MJ | chemical | accel 1.2, top 1.05 |
| rocket-fuel | base item.lua:788-793 | 100MJ | chemical | accel 1.8, top 1.15 |
| nuclear-fuel | base item.lua:2081-2104 | 1.21GJ | chemical | accel 2.5, top 1.15 (`fuel_glow_color` commented out) |
| uranium-fuel-cell | base item.lua:2313-2340 | 8GJ | nuclear | `burnt_result = "depleted-uranium-fuel-cell"` |
| carbon (SA) | SA item.lua:440-443 | 2MJ | chemical | |
| yumako (SA, capsule) | SA item.lua:643-658 | 2MJ | chemical | spoils |
| jellynut (SA, capsule) | SA item.lua:668-687 | 10MJ | chemical | spoils |
| yumako-seed (SA) | SA item.lua:738-760 | 4MJ | chemical | |
| jellynut-seed (SA) | SA item.lua:764-786 | 4MJ | chemical | |
| nutrients (SA) | SA item.lua:791-799 | 2MJ | nutrients | spoils |
| yumako-mash (SA, capsule) | SA item.lua:808-816 | 1MJ | chemical | spoils |
| jelly (SA, capsule) | SA item.lua:826-834 | 1MJ | chemical | spoils |
| bioflux (SA, capsule) | SA item.lua:844-852 | 6MJ | **food** | spoils |
| biter-egg (SA) | SA item.lua:1083-1093 | 6MJ | chemical | |
| pentapod-egg (SA) | SA item.lua:1149-1159 | 5MJ | chemical | |
| fusion-power-cell (SA) | SA item.lua:1538-1546 | 40GJ | fusion | |
| spoilage (SA) | SA item.lua:1595-1607 | 250kJ | chemical | accel 0.5, top 0.5 |
| tree-seed (SA) | SA item.lua:1678-1698 | 100kJ | chemical | |

### 9.3 `fuel-category` prototypes
API `FuelCategory` (typename `fuel-category`): "Each item which has a fuel_value must have a fuel category…". Optional `fuel_value_type`: LocalisedString, default `{"description.fuel-value"}`. API example: `{ type = "fuel-category", name = "best-fuel" }`.
- base (`base/prototypes/categories/fuel-category.lua:1-12`): `chemical`, `nuclear`.
- SA (`space-age/prototypes/categories/fuel-category.lua:1-18`): `food` (with `fuel_value_type = {"description.food-energy-value"}`), `nutrients` (`{"description.nutrients-energy-value"}`), `fusion`.
- `burner-usage` prototypes: `fuel` in `core/prototypes/burner-usage.lua`; `food` and `nutrients` in `space-age/prototypes/burner-usage.lua`. The API default for `BurnerEnergySource.burner_usage` is `"fuel"`.

A magnetic fuel category would be a new `fuel-category` plus items with `fuel_category = "<it>"` and burners with `fuel_categories = {"<it>"}`. That is fine in base-only mode, because `fuel-category` is a base prototype type with no SA restriction in the API.

---

## 10. Common entity plumbing needed to copy vanilla power buildings

- `hit_effects` and `sounds` are **locals** in base (B/e:36-37, `local hit_effects = require("prototypes.entity.hit-effects")`, `local sounds = require("prototypes.entity.sounds")`). SA re-requires them as `require("__base__.prototypes.entity.hit-effects")` and `require("__base__.prototypes.entity.sounds")` (SA/e:7-8). A mod must do the same.
- **Globals** defined by base and used later by SA without a `require` (evidence: SA/e uses `pipecoverspictures()` at l.131+ and `apply_heat_pipe_glow` in the heating tower): `pipecoverspictures` (`base/prototypes/entity/pipecovers.lua:1`), `apply_heat_pipe_glow` (B/e:50), `accumulator_picture/charge/discharge/reflection` (B/e:125-212), `boiler_reflection` (B/e:295), `make_4way_animation_from_spritesheet` (B/e:214).
- `circuit_connector_definitions` and `default_circuit_wire_max_distance = 9` come from `require("circuit-connector-sprites")` (core/lualib; SA/e:2 does this).
- `util.table.deepcopy(data.raw[<type>][<name>])` is base's own way to clone (burner-generator animations B/e:9960-9963, linked-chest B/e:10046).
- `EntityPrototype.icon`/`icons`: "Either this or `icons` is mandatory for entities that have at least one of these flags active: 'placeable-neutral', 'placeable-player', 'placeable-enemy'." `icon_size` default 64.
- Upgrades: `EntityPrototype.next_upgrade`: "The upgrade target entity needs to have the same bounding box, collision mask, and fast replaceable group as this entity. The upgrade target entity must have least 1 item that builds it that isn't hidden." Vanilla sets no `next_upgrade` on poles or power buildings (grep for `next_upgrade` in B/e hits only furnace, inserters and assemblers). Small and medium poles do share `fast_replaceable_group = "electric-pole"`, but their selection boxes differ (0.4 vs 0.5).
- `EntityPrototype.heating_energy` (default "0W"): "This entity can freeze if heating_energy is larger than zero." SA sets it for steam-engine/turbine (50kW). SA sets **no** heating_energy on poles, accumulator or solar-panel (space-age/base-data-updates.lua:86-134 has none).
- Default collision masks by type (`core/lualib/collision-mask-defaults.lua`): `boiler`, `burner-generator`, `electric-energy-interface`, `generator`, `reactor`, `fusion-generator`, `fusion-reactor` → `building()` (includes `meltable`). `accumulator`, `electric-pole`, `solar-panel` → `building_unheated()` (no `meltable`; the file's comment on containers says unheated masks "allow them to be built on meltable surfaces"). `lightning-attractor` → `building_tall()` (adds `elevated_rail`). If a mod sets no `collision_mask`, it gets these per-type defaults.

---

## 11. Space Age specifics

### 11.1 Lightning attractors (`LightningAttractorPrototype`, typename `lightning-attractor`)
API: "Absorbs lightning and optionally converts it into electricity." Fields: `chargable_graphics` (ChargableGraphics), `lightning_strike_offset` (MapPosition), `efficiency` (double, default 0, "Cannot be less than 0"), `range_elongation` (double, default 0), `energy_source` (ElectricEnergySource, opt: "Mandatory if `efficiency` is larger than 0. May not be defined if `efficiency` is 0."). Nothing is required beyond `name`/`type`.

lightning-rod (SA/e:1780-1860, energy part verbatim):
```lua
    type = "lightning-attractor",
    name = "lightning-rod",
    efficiency = 0.2,
    range_elongation = 15.0,
    energy_source =
    {
      type = "electric",
      buffer_capacity = "500MJ",
      usage_priority = "primary-output",
      output_flow_limit = "500MJ",
      drain = "2.5MJ"
    },
```
It also has `resistances` fire 90 / electric 100, `lightning_strike_offset = {0, -4.1}`, `drawing_box_vertical_extension = 4.3`, and `chargable_graphics = require("__space-age__.prototypes.entity.lightning-rod-graphics")`. That module returns `{picture, charge_animation, charge_animation_is_looped = false, charge_cooldown = 30, discharge_animation, discharge_cooldown = 60}` built with `util.sprite_load` (`space-age/prototypes/entity/lightning-rod-graphics.lua:59-67`). lightning-collector (SA/e:1862-1947): `efficiency = 0.4`, `range_elongation = 25.0`, buffer/out `1000MJ`, drain `2.5MJ`, `lightning_strike_offset = {0, -4.8}`. A `lightning-attractor` decorative also exists at `space-age/prototypes/decorative/decoratives-fulgora.lua:169`. Recipes for both have `surface_conditions = {{property = "magnetic-field", min = 99, max = 99}}` (SA recipe.lua:2132-2152, 2274-2294). The rod's category is `electronics`; the collector's is `electromagnetics` and it takes `{lightning-rod 1, supercapacitor 8, accumulator 1, electrolyte 80}`.

### 11.2 Fusion generator (`FusionGeneratorPrototype`)
REQUIRED: `energy_source` ("`output_flow_limit` is mandatory and must be positive. `output_flow_limit` is the maximum power output of the generator."), `input_fluid_box` (filter mandatory), `output_fluid_box` (filter mandatory), `max_fluid_usage` ("Must be positive"). Optional: `graphics_set` (FusionGeneratorGraphicsSet: `north/east/south/west_graphics_set` REQUIRED inside), `perceived_performance`, `burns_fluid` (default false), `effectivity` (default 1). The last two were added in 2.0.67 (changelog.txt:245-246). Definition, verbatim energy part (SA/e:2375-2381):
```lua
    energy_source =
    {
      type = "electric",
      usage_priority = "secondary-output",
      output_flow_limit = "50MW", -- This is used to define max power output. 50MW at normal quality
    },
    max_fluid_usage = 2/second, -- at normal quality
```
Input filter `fusion-plasma` with `connection_category = {"fusion-plasma"}`; output filter `fluoroketone-hot` (SA/e:2383-2412).

### 11.3 Fusion reactor (`FusionReactorPrototype`) — brief
REQUIRED: `energy_source` (Electric: "provides energy"), `burner` (Burner: "provides fuel"), `graphics_set` (FusionReactorGraphicsSet, which requires `plasma_category`), `input_fluid_box`, `output_fluid_box`, `power_input`, `max_fluid_usage`. SA definition: electric `primary-input`, `power_input = "10MW"`, `max_fluid_usage = 4/second`, `burner = {type = "burner", fuel_categories = {"fusion"}, effectivity = 1, fuel_inventory_size = 1, emissions_per_minute = { pollution = 0 }, light_flicker = {…}}`, `two_direction_only = true`, `neighbour_connectable` with 8 connections (SA/e:2414-2522).

### 11.4 Heating tower (`reactor` type) — brief
SA/e:2066-…: `surface_conditions = {{property = "pressure", min = 10}}`, `consumption = "40MW"`, `neighbour_bonus = 0`, burner `{fuel_categories = {"chemical"}, emissions_per_minute = {pollution = 100}, effectivity = 2.5, fuel_inventory_size = 2, burnt_inventory_size = 2}`. `heat_buffer = {max_temperature = 1000, specific_heat = "5MJ", max_transfer = "10GW", minimum_glow_temperature = 50, connections = 4 (N/E/S/W)}`.

### 11.5 What SA changes on base power content
- `space-age/base-data-updates.lua:109-110`: steam-engine and steam-turbine `heating_energy = "50kW"`.
- l.187: boiler `surface_conditions = ten_pressure_condition()` (pressure ≥ 10).
- l.252, 309, 312-314, 318: recipe `category = "electronics"` for solar-panel, accumulator, small/big/medium pole and substation.
- No changes to the technologies steam-power, electronics, solar-energy, electric-energy-distribution-1/2, electric-energy-accumulators or nuclear-power (grep for these names in SA/quality/elevated-rails only hits `planet-discovery-fulgora.prerequisites`, SA technology.lua:409).
- The quality and elevated-rails mods do not touch any power entity (grep for solar/accumulator/pole/generator/boiler/reactor in their `data*.lua` and `prototypes/*.lua` finds only tips-and-tricks and a recycling exclusion).

### 11.6 Surface properties relevant to "Magnetics"
- Base defines (`base/prototypes/planet/surface-property.lua`): `gravity` 10, `pressure` 1000, **`magnetic-field` 90**, `solar-power` 100, `day-night-cycle` 300 (`is_time`).
- Per surface (SA): vulcanus magnetic-field 25, gleba 25, fulgora 99, aquilo 10 (`space-age/prototypes/planet/planet.lua`). Space platform: magnetic-field 0, pressure 0, gravity 0 (`space-age/prototypes/surface.lua:9-15`). Nauvis sets no value, so it uses the default 90.
- SA recipes using `magnetic-field` min/max 99 (Fulgora only): electromagnetic-science-pack (SA recipe.lua:819), lightning-rod (2138), lightning-collector (2280), recycler (space-age/base-data-updates.lua:914). electromagnetic-plant uses min 99 (SA recipe.lua:2204).
- But `SurfaceCondition` "Requires Space Age to use" (API), so any `surface_conditions` must be added only when `mods["space-age"]` is present.

---

## 12. Technologies and recipes that unlock power buildings

| Technology | Defined | Unlocks | Prerequisites / cost |
|---|---|---|---|
| steam-power | base technology.lua:17-51 | pipe, pipe-to-ground, offshore-pump, **boiler**, **steam-engine** | `research_trigger = {type = "craft-item", item = "iron-plate", count = 50}` |
| electronics | base technology.lua:52-~82 | copper-cable, electronic-circuit, lab, inserter, **small-electric-pole** | `research_trigger = {type = "craft-item", item = "copper-plate", count = 10}` |
| solar-energy | base technology.lua:2237-2259 | **solar-panel** | prereq `{"steel-processing", "logistic-science-pack"}`; 250 × (red 1, green 1), time 30 |
| electric-energy-distribution-1 | base technology.lua:2350-2380 | **medium-electric-pole**, **big-electric-pole**, iron-stick | prereq `{"steel-processing", "logistic-science-pack"}`; 120 × (red, green), 30 |
| electric-energy-distribution-2 | base technology.lua:3721-3744 | **substation** | prereq `{"electric-energy-distribution-1", "chemical-science-pack"}`; 100 × (red, green, blue), 45 |
| electric-energy-accumulators | base technology.lua:3746-3770 | **accumulator** | prereq `{"electric-energy-distribution-1", "battery"}`; 150 × (red, green), 30; `localised_name = {"technology-name.electric-energy-accumulators-1"}` |
| nuclear-power | base technology.lua:5115-5153 | **nuclear-reactor**, **heat-exchanger**, **heat-pipe**, **steam-turbine**, uranium-fuel-cell | prereq `{"uranium-processing"}`; 800 × (red, green, blue), 30 |
| (fuels) oil-processing / advanced-oil-processing / rocket-fuel / kovarex-enrichment-process | base technology.lua:4594 / 4625 / 3519 / 5158 | solid-fuel-from-* / rocket-fuel / nuclear-fuel | |
| planet-discovery-fulgora (SA) | SA technology.lua:391-422 | **lightning-rod** (+ fulgora) | prereq `{"space-platform-thruster", "electric-energy-accumulators"}`; 1000 × (red, green, blue, space), 60 |
| lightning-collector (SA) | SA technology.lua:1515-… | **lightning-collector** | prereq `{"electromagnetic-science-pack"}`; count 1000 |
| heating-tower (SA) | SA technology.lua:1611-1640 | **heating-tower**, heat-pipe, heat-exchanger, steam-turbine | prereq `{"planet-discovery-gleba"}`; trigger `mine-entity copper-stromatolite` |
| fusion-reactor (SA) | SA technology.lua:1830-1864 | **fusion-reactor**, **fusion-generator**, fusion-power-cell | prereq `{"quantum-processor"}`; 2000 × 10 packs, 60 |
| (none) | | burner-generator, electric-energy-interface, hidden EEI | hidden, no recipe |

All vanilla power-building recipes have `enabled = false` (see the recipe quotes above), so each is reachable only through the technology listed.

---

## 13. Nuclear reactor / heat exchanger / heat pipe (brief)
- `ReactorPrototype` REQUIRED: `heat_buffer` (HeatBuffer), `energy_source` ("May not be a heat energy source. … in vanilla it is a burner energy source"), `consumption`. Optional: `neighbour_bonus` (default 1), `heating_radius` (default 1), `scale_energy_usage` (default false), `use_fuel_glow_color`, `meltdown_action` ("triggered when the reactor dies … at over 90% of max temperature"), `connection_patches_*` (need ≥ one variation per heat connection), `lower_layer_picture`, `heat_lower_layer_picture`, `picture`, `working_light_picture`, circuit fields, `default_temperature_signal`.
- nuclear-reactor (B/e:8568-8797): burner `{fuel_categories = {"nuclear"}, effectivity = 1, fuel_inventory_size = 1, burnt_inventory_size = 1}`. `heat_buffer = {max_temperature = 1000, specific_heat = "10MJ", max_transfer = "10GW", minimum_glow_temperature = 350, connections = 12}`. `meltdown_action` creates `atomic-rocket`. `default_temperature_signal = {type = "virtual", name = "signal-T"}`.
- heat-exchanger (B/e:8991-9243): `type = "boiler"`, `target_temperature = 500`, `energy_consumption = "10MW"`, `energy_source = {type = "heat", max_temperature = 1000, specific_heat = "1MJ", max_transfer = "2GW", min_working_temperature = 500, minimum_glow_temperature = 350, connections = {{position = {0, 0.5}, direction = defines.direction.south}}, …}`.
- heat-pipe (B/e:9389-…): `heat_buffer = {max_temperature = 1000, specific_heat = "1MJ", max_transfer = "1GW", minimum_glow_temperature = 350, connections = …}` (B/e:9427-9433).
- Recipes: nuclear-reactor `{concrete 500, steel 500, advanced-circuit 500, copper 500}` (recipe.lua:2478-2492). heat-exchanger `{steel 10, copper 100, pipe 10}` (2605-2611). heat-pipe `{steel 10, copper 20}` (2613-2619).

---

## 14. Not found in the sources
- Any `type = "accumulator"` in Space Age (or quality/elevated-rails): **none**.
- Any `burner-generator` in Space Age: **none**. Any recipe or tech for base's `burner-generator`: **none**.
- Any electric-pole, solar-panel or generator prototype in SA/quality/elevated-rails: **none**.
- The units (per tick vs per second) of runtime `LuaEntity.power_production` / `power_usage`: **not stated** in runtime-api.json.
- Whether `connection_points` count must equal `pictures.direction_count`: **not stated** in the API. Vanilla always uses 4/4.
- Whether the headless server tolerates missing `.png` paths in a *mod* (as opposed to base): **not verified**; see the inference in section 0.4.
- An upper bound on `maximum_wire_distance` after quality bonuses: the API only states "Max value is 64" for the prototype property.
