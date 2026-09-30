# Factorio 2.0.77: belts, undergrounds, splitters, loaders. Reference for the "Magnetics" belt tier

All claims cite a file under `/opt/factorio/data/...` (abbreviated below as `base/`, `space-age/`, `core/`, `quality/`, `elevated-rails/`) with line numbers, or an entry in `/opt/factorio-api/prototype-api.json` / `runtime-api.json` (cited as `API: <Type>::<property>`). Version check: every `info.json` says `"version": "2.0.77"`, and `prototype-api.json` says `application_version = 2.0.77`, `api_version = 6`.

Items marked **[inference]** are my conclusions from the code and are not stated anywhere in the sources. Items marked **[not found in sources]** have no answer in the files available here.

---

## 0. TL;DR for the mod author

| Question | Answer (source) |
|---|---|
| items/s from `speed` | `speed × 480 = items/s` (API: TransportBeltConnectablePrototype::speed) |
| Speed granularity | Fixed point with 8 fractional bits, so the smallest step is `1/256 = 0.00390625`, which is 1.875 items/s on a straight belt (same API entry) |
| Upper bound on speed | The API only says "Must be a positive non-infinite number". **No maximum found in the sources.** |
| Vanilla speeds | 0.03125 / 0.0625 / 0.09375 / 0.125, which are 15 / 30 / 45 / 60 items/s. All are multiples of 8/256. |
| Natural next tier | `0.15625` (= 40/256), which is **75 items/s** [inference: simply the next step of the vanilla +8/256 progression] |
| `animation_speed_coefficient` | Always `32` in vanilla, on every belt-connectable entity (base and SA transport-belts.lua) |
| UG `max_distance` | 5 / 7 / 9 / 11 (base, base, base, SA). The type is `uint8` (API: UndergroundBeltPrototype::max_distance). |
| Can we tint express graphics? | **Yes, per the API types.** Every graphics field involved (RotatedAnimation, Sprite4Way, Animation4Way, Sprite, RotatedSprite, IconData) inherits `SpriteParameters::tint` or has its own `tint`. No vanilla belt uses `tint`, so the visual result is untested. |
| Biggest trap | In base, one Lua table `express_belt_animation_set` is shared by 4 entities, and `data:extend` stores prototypes **by reference**. Always `table.deepcopy` before mutating, or you will recolour vanilla express belts too. |
| SA-only names | `pressing`, `metallurgy`, `crafting-with-fluid-or-metallurgy` recipe categories; `vulcanus` import location; any `__space-age__/` graphics path. Guard all of them with `mods["space-age"]`. |

---

## 1. Where things are defined, and load order

- `base/data.lua:10`: `require("prototypes.entity.transport-belts")`. This happens before `prototypes.item` (l.25), `prototypes.recipe` (l.27) and so on.
- `space-age/data.lua:9`: `require("prototypes.entity.transport-belts")`. `space-age/data.lua:65`: `require("base-data-updates")`. **This runs in the data stage, not in data-updates.** `space-age/base-data-updates.lua:2` requires `prototypes.entity.base-frozen-graphics`.
- `space-age/info.json`: `"dependencies": ["base >= 2.0.0", "elevated-rails >= 2.0.0", "quality >= 2.0.0"]`, plus `"freezing_required": true`.
- `data:extend` stores the prototype table itself, without copying it (`core/lualib/dataloader.lua:36-44`, `t[e.name] = e`).
- Globals persist across mods in the data stage. Evidence: the base file defines `belt_reader_gfx = -- not local` (`base/prototypes/entity/transport-belts.lua:75`), and SA then uses it (`space-age/prototypes/entity/transport-belts.lua:29`, `meld(tungsten_belt_animation_set, belt_reader_gfx)`).
- Globals that a mod can reuse:
  - from `core/lualib/circuit-connector-sprites.lua`: `transport_belt_connector_frame_sprites` (l.137), `transport_belt_circuit_wire_max_distance = 9` (l.195), `splitter_circuit_wire_max_distance = 9` (l.201), and `circuit_connector_definitions["belt"|"splitter"|"loader-1x2"]`. Both belt files `require ("circuit-connector-sprites")` on line 1.
  - `belt_reader_gfx`, from base.
  - modules: `require("__base__.prototypes.entity.sounds")` (returns `sounds`, sounds.lua:1478), `require("__base__.prototypes.entity.hit-effects")` (`hit_effects.entity()`, l.443), `require("__base__.prototypes.item_sounds")`, `require("meld")` (core/lualib/meld.lua), and `table.deepcopy` (core/lualib/util.lua:6).
- Detecting space-age: API type `Mods`: "A dictionary of mod names to mod versions of all active mods… `if mods["pizza"] then`". API type `FeatureFlags`: accessible as global `feature_flags`, with keys `expansion_shaders, freezing, quality, rail_bridges, segmented_units, space_travel, spoiling`, e.g. `if feature_flags["spoiling"] then`.
- **[not found in sources]** The sources do not document the exact mod ordering rules (optional-dependency syntax, the data → data-updates → data-final-fixes order). For the next_upgrade chain and the frozen patches to be seen correctly, Magnetics must load **after** space-age. Verify the chosen `info.json` dependency form on the headless stand.

---

## 2. Speed, throughput, and speed constraints

API (`prototype-api.json`, TransportBeltConnectablePrototype::speed, type `double`, MANDATORY), verbatim:

> The speed of the belt: `speed × 480 = x Items/second`. The raw value is expressed as the number of tiles traveled by each item on the belt per tick, relative to the belt's maximum density - e.g. `x items/second ÷ (4 items/lane × 2 lanes/belt × 60 ticks/second) = <speed> belts/tick` where a "belt" is the size of one tile. … Must be a positive non-infinite number. The number is a fixed point number with 8 bits reserved for decimal precision, meaning the smallest value step is `1/2^8 = 0.00390625`. In the simple case of a non-curved belt, the rate is multiples of `1.875` items/s, even though the entity tooltip may show a different rate.

| Tier | Source (speed line) | `speed` | ×256 | items/s = ×480 |
|---|---|---|---|---|
| transport-belt / underground-belt / splitter / loader | base transport-belts.lua:180 / 306 / 659 / 995 | 0.03125 | 8 | 15 |
| fast-* | :216 / 431 / 772 / 1092 | 0.0625 | 16 | 30 |
| express-* | :252 / 560 / 883 / 1148 | 0.09375 | 24 | 45 |
| turbo-* (SA) | space-age transport-belts.lua:68 / 131 / 253 / 387 | 0.125 | 32 | 60 |
| candidate Magnetics | — | 0.15625 | 40 | 75 |
| candidate (alt.) | — | 0.1875 | 48 | 90 |

Within each tier, vanilla uses the same `speed` for the belt, the UG, the splitter and the loader. (Whether the engine requires this is **[not found in sources]**.)

Constraints on speed:
- Lower bound: positive and finite (API text above). The binary contains the string `speed must be a positive valid number`, but I could not tell from the strings which prototype emits it.
- Quantisation is 1/256. Pick exact multiples of 1/256. How non-multiples are rounded is **[not found in sources]**.
- Upper bound: **[not found in sources]**. Neither the API nor the binary strings give a maximum belt speed.
- Quality: `QualityPrototype` has no belt-speed multiplier. Its properties list includes `inserter_speed_multiplier`, `crafting_machine_speed_multiplier` and others, but nothing for belts (API).
- Belt stacking (SA): the `belt-stack-size-bonus` effects are in `space-age/prototypes/technology.lua:1155,1185,1216` (stack-inserter, transport-belt-capacity-1/2), and `core/prototypes/utility-constants.lua:594` has `max_belt_stack_size = 4`. How stacking combines with the ×480 formula is **[not found in sources]**.
- Tooltip: the locale keys `[description] belt-speed=Belt speed` and `belt-items=Items` are at `core/locale/en/core.cfg:1736-1737`. The binary has the symbol `addBeltSpeedToDescription`, so the tooltip is generated by the engine and needs no locale work from the mod.

---

## 3. Entity prototypes: field-by-field

### 3.1 TransportBeltPrototype (`type = "transport-belt"`)

API hierarchy: `TransportBeltPrototype` → `TransportBeltConnectablePrototype` (abstract; fields `belt_animation_set`, `speed`, `animation_speed_coefficient` [default 1, no description], `collision_box`, `flags` ["cannot have building-direction-8-way"], `selection_priority` [default 45]) → `EntityWithOwnerPrototype`.
TransportBelt-specific fields: `connector_frame_sprites`, `circuit_wire_max_distance`, `draw_copper_wires`, `draw_circuit_wires`, `circuit_connector` ("Set of 7 … in order: X, H, V, SE, SW, NE and NW"), `belt_animation_set` : **TransportBeltAnimationSetWithCorners**, `related_underground_belt` : EntityID ("used in quick-replace fashion when the smart belt dragging behavior is triggered").

Vanilla express belt, verbatim (`base/prototypes/entity/transport-belts.lua:221-256`):
```lua
  {
    type = "transport-belt",
    name = "express-transport-belt",
    icon = "__base__/graphics/icons/express-transport-belt.png",
    flags = {"placeable-neutral", "player-creation"},
    minable = {mining_time = 0.1, result = "express-transport-belt"},
    max_health = 170,
    corpse = "express-transport-belt-remnants",
    dying_explosion = "express-transport-belt-explosion",
    resistances = { { type = "fire", percent = 50 } },
    collision_box = {{-0.4, -0.4}, {0.4, 0.4}},
    selection_box = {{-0.5, -0.5}, {0.5, 0.5}},
    damaged_trigger_effect = hit_effects.entity(),
    open_sound = sounds.transport_belt_open,
    close_sound = sounds.transport_belt_close,
    working_sound =
    {
      sound = { filename = "__base__/sound/express-transport-belt.ogg", volume = 0.3 },
      persistent = true,
      use_doppler_shift = false
    },
    animation_speed_coefficient = 32,
    belt_animation_set = express_belt_animation_set,
    related_underground_belt = "express-underground-belt",
    fast_replaceable_group = "transport-belt",
    speed = 0.09375,
    connector_frame_sprites = transport_belt_connector_frame_sprites,
    circuit_connector = circuit_connector_definitions["belt"],
    circuit_wire_max_distance = transport_belt_circuit_wire_max_distance
  },
```
(The resistances table is compacted here; the original spans lines 229-236.)

| belt | lines | max_health | fire res. | corpse | dying_explosion | next_upgrade (base) | related_underground_belt |
|---|---|---|---|---|---|---|---|
| transport-belt | 149-184 | 150 | 90% | transport-belt-remnants | transport-belt-explosion | fast-transport-belt (l.179) | underground-belt |
| fast-transport-belt | 185-220 | 160 | 50% | fast-transport-belt-remnants | fast-transport-belt-explosion | express-transport-belt (l.215) | fast-underground-belt |
| express-transport-belt | 221-256 | 170 | 50% | express-transport-belt-remnants | express-transport-belt-explosion | **none** in base | express-underground-belt |
| turbo-transport-belt (SA) | SA 37-73 | 170 | 50% | turbo-transport-belt-remnants | turbo-transport-belt-explosion | **none** | turbo-underground-belt |

All four: `fast_replaceable_group = "transport-belt"`, `animation_speed_coefficient = 32`, collision `{{-0.4,-0.4},{0.4,0.4}}`. The turbo belt adds `heating_energy = "10kW"` (SA l.72). Transport belts have **no** `related_transport_belt` field (the API lists it only on SplitterPrototype).

### 3.2 UndergroundBeltPrototype (`type = "underground-belt"`)

API fields: `max_distance` : **uint8, MANDATORY** (no description); `structure` : UndergroundBeltStructure; `underground_sprite` : Sprite; `underground_remove_belts_sprite` : Sprite; `max_distance_underground_remove_belts_sprite` : Sprite; `underground_collision_mask` : CollisionMaskConnector (default "no masks"); `max_distance_tint` : Color.
There is **no** `structure_render_layer` and **no** `related_transport_belt` on undergrounds (API property list).
`UndergroundBeltStructure` = `direction_in, direction_out, back_patch, front_patch, direction_in_side_loading, direction_out_side_loading, frozen_patch_in, frozen_patch_out`, all of type **Sprite4Way**.

| UG | lines | max_distance | max_health | next_upgrade | remove-belts sprite | heating_energy (SA) |
|---|---|---|---|---|---|---|
| underground-belt | 258-382 | 5 (l.268) | 150 | fast-underground-belt (l.305) | no | 50kW (SA base-data-updates.lua:114) |
| fast-underground-belt | 384-504 | 7 (l.394) | 160 | express-underground-belt (l.430) | no | 100kW (l.115) |
| express-underground-belt | 505-633 | 9 (l.515) | 170 | none in base; SA sets turbo (SA transport-belts.lua:32) | yes (l.525-533) | 150kW (l.116) |
| turbo-underground-belt (SA) | SA 74-227 | 11 (SA l.84) | 170 | none | yes | 200kW (SA l.85) |

All: `fast_replaceable_group = "transport-belt"`, resistances fire 60 / impact 30, `open_sound = sounds.machine_open`. `underground_sprite` is `__core__/graphics/arrows/underground-lines.png` (64×64, x=64, scale 0.5).
The runtime equivalent is `LuaEntityPrototype::max_underground_distance` (uint8, runtime-api.json).
`core/prototypes/utility-constants.lua:21` has `underground_belt_max_distance_tint = {0, 1, 0, 1}`. That this is the default for `max_distance_tint` is **[inference]** from the name.

Structure layout (express, verbatim excerpt, l.561-632). One sheet of 4 directions × 192 px per row. Rows: y=0 is `direction_out`, y=192 `direction_in`, y=384 `direction_out_side_loading`, y=576 `direction_in_side_loading`. Patches are separate files:
```lua
    structure =
    {
      direction_in =
      {
        sheet =
        {
          filename = "__base__/graphics/entity/express-underground-belt/express-underground-belt-structure.png",
          priority = "extra-high",
          width = 192,
          height = 192,
          y = 192,
          scale = 0.5
        }
      },
      direction_out = { sheet = { filename = ".../express-underground-belt-structure.png", priority = "extra-high", width = 192, height =192, scale = 0.5 } },
      direction_in_side_loading = { sheet = { ..., y = 192*3, scale = 0.5 } },
      direction_out_side_loading = { sheet = { ..., y = 192*2, scale = 0.5 } },
      back_patch = { sheet = { filename = "__base__/graphics/entity/express-underground-belt/express-underground-belt-structure-back-patch.png", ... } },
      front_patch = { sheet = { filename = "__base__/graphics/entity/express-underground-belt/express-underground-belt-structure-front-patch.png", ... } }
    }
```
Space Age adds to the underground-belt entities:
- `underground_collision_mask = {layers={lava_tile=true, empty_space=true}}` on all four UGs (`space-age/base-data-updates.lua:20-24`; also turbo SA l.117). Both collision layers are defined in **base** (`base/prototypes/collision-layers.lua:19-20`), so setting this mask is also legal without SA.
- `structure.frozen_patch_in/out`, using `__space-age__/graphics/entity/frozen/underground-belt/underground-belt-structure.png` (`space-age/prototypes/entity/base-frozen-graphics.lua:493-522`; turbo SA l.203-225).

### 3.3 SplitterPrototype (`type = "splitter"`)

API fields: `structure` : **Animation4Way**; `structure_patch` : Animation4Way ("Drawn 1 tile north of `structure` when the splitter is facing east or west"); `frozen_patch` : Sprite4Way; `structure_animation_speed_coefficient` (default 1); `structure_animation_movement_cooldown` (default 10); `related_transport_belt` : EntityID ("used for the sound of the underlying belt"); circuit fields; `default_input/output_left/right_condition`.

| splitter | lines | max_health | structure_anim_speed_coef | related_transport_belt | next_upgrade |
|---|---|---|---|---|---|
| splitter | 634-745 | 170 | 0.7 | transport-belt | fast-splitter (l.658) |
| fast-splitter | 746-857 | 180 | 1.2 | fast-transport-belt | express-splitter (l.771) |
| express-splitter | 858-968 | 190 | 1.2 | express-transport-belt | none in base; SA → turbo-splitter (SA l.33) |
| turbo-splitter (SA) | SA 228-359 | 190 | 1.2 | turbo-transport-belt | none |

All: collision `{{-0.9,-0.4},{0.9,0.4}}`, `fast_replaceable_group = "transport-belt"`, `icon_draw_specification = {scale = 0.5}`, `structure_animation_movement_cooldown = 10`. SA gives every splitter `heating_energy = "40kW"` (base-data-updates.lua:117-119; turbo SA l.258).

Express structure, verbatim excerpt (l.888-961). Every direction is a plain 32-frame Animation:
```lua
    structure =
    {
      north =
      {
        filename = "__base__/graphics/entity/express-splitter/express-splitter-north.png",
        frame_count = 32,
        line_length = 8,
        priority = "extra-high",
        width = 160,
        height = 70,
        shift = util.by_pixel(7, 0),
        scale = 0.5
      },
      east  = { filename = ".../express-splitter-east.png",  frame_count = 32, line_length = 8, width = 90, height = 84, shift = util.by_pixel(4, 13), scale = 0.5, priority = "extra-high" },
      south = { filename = ".../express-splitter-south.png", frame_count = 32, line_length = 8, width = 164, height = 64, shift = util.by_pixel(4, 0), scale = 0.5, priority = "extra-high" },
      west  = { filename = ".../express-splitter-west.png",  frame_count = 32, line_length = 8, width = 94, height = 86, shift = util.by_pixel(5, 12), scale = 0.5, priority = "extra-high" }
    },
    structure_patch =
    {
      north = util.empty_sprite(),
      east = { filename = "__base__/graphics/entity/express-splitter/express-splitter-east-top_patch.png", frame_count = 32, line_length = 8, width = 90, height = 104, shift = util.by_pixel(4, -20), scale = 0.5, priority = "extra-high" },
      south = util.empty_sprite(),
      west = { filename = "__base__/graphics/entity/express-splitter/express-splitter-west-top_patch.png", frame_count = 32, line_length = 8, width = 94, height = 96, shift = util.by_pixel(5, -18), scale = 0.5, priority = "extra-high" }
    },
```
Note that the express-splitter west frame is 94 px wide, while splitter and fast-splitter use 90 (l.707, 819 vs 929). `util.empty_sprite()` returns `{filename="__core__/graphics/empty.png", priority="extra-high", width=1, height=1}` (core/lualib/util.lua:637-645).

### 3.4 Loaders (all hidden in vanilla)

`LoaderPrototype` (abstract) → `Loader1x2Prototype` (`type="loader"`, belt_distance hardcoded 0.5) / `Loader1x1Prototype` (`type="loader-1x1"`, belt_distance 0). API fields: `structure` : LoaderStructure (`direction_in, direction_out, back_patch, front_patch, frozen_patch_in, frozen_patch_out`, all Sprite4Way); `filter_count` : uint8 MANDATORY (max 5); `structure_render_layer` (default "object"); `circuit_connector_layer`; `container_distance` (default 1.5); `allow_rail_interaction`; `allow_container_interaction`; `per_lane_filters`; `max_belt_stack_size` (default 1); `adjustable_belt_stack_size`; `wait_for_full_stack`; `respect_insert_limits`; `belt_length` (default 0.5); `energy_source`; `energy_per_item`.

Vanilla loaders: `loader` (l.969-1023), `loader-1x1` (1024-1064, no minable, `subgroup="other"`), `fast-loader` (1065-1120), `express-loader` (1121-1176), `turbo-loader` (SA 360-415). All have `hidden = true`, `filter_count = 5`, `structure_render_layer = "lower-object"`, `fast_replaceable_group = "loader"` (not "transport-belt"), `corpse = "small-remnants"`, the structure sheet `__base__/graphics/entity/loader/loader-structure.png` (64×64; direction_out has y=64), and no next_upgrade. Their items and recipes are also `hidden = true`.

Other belt-connectables, all hidden: `linked-belt` (l.1181-1259, `structure_render_layer = "object"`, `fast_replaceable_group = "linked-belts"`) and `lane-splitter` (l.1260-1376, `-- next_upgrade = "fast-lane-splitter"` commented out).

**Summary of `structure_render_layer`:** it exists only on LoaderPrototype and LinkedBeltPrototype (default "object"). Belts, UGs and splitters have no such field.

### 3.5 Engine validation strings (from `strings` on the headless binary)

- `Related underground belt of %s (%s) doesn't have underground belt type.`
- `Related transport belt of %s (%s) doesn't have transport belt type.`
- `Index of '%s' animation is %zu, which is out of bounds of direction_count (%u) of animation_set.`
- `BeltReaderLayer sprite must have exactly 4 frames: North,East,South,West. Given was frame_count=%u`
- `BeltReaderLayer sprite must have exactly 4 rows: StraightSolidBand,StraightOpenBand,CurvedSolidBand,Ending. Given was %u`
- `Loader belt tile must collide with the loader collision box.`
- The symbol `alternateAnimationOffset` also appears. It presumably implements `TransportBeltAnimationSet::alternate` [inference; the API gives no description].

---

## 4. `belt_animation_set`

### 4.1 API structure

`TransportBeltAnimationSet` (used by UG, splitter and loader), fields:
- `animation_set` : **RotatedAnimation, MANDATORY**
- the indexes `east_index`=1, `west_index`=2, `north_index`=3, `south_index`=4, `starting_south_index`=13, `ending_south_index`=14, `starting_west_index`=15, `ending_west_index`=16, `starting_north_index`=17, `ending_north_index`=18, `starting_east_index`=19, `ending_east_index`=20
- `frozen_patch` : RotatedSprite, plus `*_index_frozen` twins ("Only loaded if `frozen_patch` is defined")
- `alternate` : boolean, default false, no description
- `belt_reader` : array[BeltReaderLayer], where each layer has `render_layer` (default 'transport-belt-reader') and `sprites` : RotatedAnimation ("Must have a `frame_count` of `4`")

`TransportBeltAnimationSetWithCorners` (required by TransportBeltPrototype) adds the corner indices `east_to_north`=5, `north_to_east`=6, `west_to_north`=7, `north_to_west`=8, `south_to_east`=9, `east_to_south`=10, `south_to_west`=11, `west_to_south`=12, plus their `_frozen` twins. That is why `direction_count = 20` everywhere.

### 4.2 Base definitions (verbatim, `base/prototypes/entity/transport-belts.lua`)

```lua
local basic_belt_animation_set =
{
  animation_set =
  {
    filename = "__base__/graphics/entity/transport-belt/transport-belt.png",
    priority = "extra-high",
    size = 128,
    scale = 0.5,
    frame_count = 16,
    direction_count = 20
  },
  --east_index = 1,  ... (commented index list, lines 19-44)
}

local fast_belt_animation_set =
{
  animation_set =
  {
    filename = "__base__/graphics/entity/fast-transport-belt/fast-transport-belt.png",
    priority = "extra-high",
    size = 128,
    scale = 0.5,
    frame_count = 32,
    direction_count = 20
  }
}

local express_belt_animation_set =
{
  animation_set =
  {
    filename = "__base__/graphics/entity/express-transport-belt/express-transport-belt.png",
    priority = "extra-high",
    size = 128,
    scale = 0.5,
    frame_count = 32,
    direction_count = 20
  }
}
```
`belt_reader_gfx` (a global, l.75-141) is 6 layers loaded with `util.sprite_load("__base__/graphics/entity/transport-belt/belt-reader-{top,base,middle,under-middle,bottom,shadow}", {priority="low", scale=0.5, frame_count=4, direction_count=4})`, on render layers object / transport-belt-reader / floor-mechanics / transport-belt-endings / floor / floor. It is then merged in (l.143-145):
```lua
meld(basic_belt_animation_set, belt_reader_gfx)
meld(fast_belt_animation_set, belt_reader_gfx)
meld(express_belt_animation_set, belt_reader_gfx)
```
`meld` (core/lualib/meld.lua:42-55) is a recursive merge **in place into the target**. New table values are `util.copy`'d, so each set gets its own copy of `belt_reader`.
`util.sprite_load(path, t)` (core/lualib/util.lua:673-705) does `require(path)` on a `.lua` metadata file (width/height/shift/line_length) and sets `filename = path .. '.png'`. These `.lua` files **do exist** in the headless install (e.g. `base/graphics/entity/transport-belt/belt-reader-top.lua`, `space-age/graphics/entity/turbo-splitter/*.lua`). The `.png` files do not.

**Sharing:** `express_belt_animation_set` is referenced by express-transport-belt (l.249), express-underground-belt (l.558), express-splitter (l.881) and express-loader (l.1146). Because `data:extend` stores by reference (dataloader.lua:44), `data.raw["transport-belt"]["express-transport-belt"].belt_animation_set` **is the same table** as that of the express UG, splitter and loader. SA exploits this: `base-frozen-graphics.lua:483-491` sets `frozen_patch` only via the transport-belt entry, and it thereby applies to all four [inference from the shared reference].

### 4.3 Space Age turbo set (verbatim, `space-age/prototypes/entity/transport-belts.lua:7-29`)

```lua
local tungsten_belt_animation_set =
{
  alternate = true,
  animation_set =
  {
    filename = "__space-age__/graphics/entity/turbo-transport-belt/turbo-transport-belt.png",
    priority = "extra-high",
    size = 128,
    scale = 0.5,
    frame_count = 64,
    direction_count = 20
  },
  frozen_patch = {
    filename = "__space-age__/graphics/entity/turbo-transport-belt/turbo-transport-belt-frozen.png",
    priority = "extra-high",
    size = 128,
    scale = 0.5,
    line_length = 1,
    direction_count = 20
  }
}

meld(tungsten_belt_animation_set, belt_reader_gfx)
```
Frozen patches that SA adds to base belts (`space-age/prototypes/entity/base-frozen-graphics.lua:465-491`):
```lua
data.raw["transport-belt"]["express-transport-belt"].belt_animation_set.frozen_patch =
{
  filename = "__space-age__/graphics/entity/frozen/express-transport-belt/express-transport-belt.png",
  priority = "extra-high",
  size = 128,
  scale = 0.5,
  line_length = 1,
  direction_count = 20
}
```
The same is done for transport-belt and fast-transport-belt, each with its own frozen png. Splitters (all 3 base ones, l.524-563) get `frozen_patch` N/E/S/W from `__space-age__/graphics/entity/frozen/splitter/splitter.png` (N: 192×128 at x=0; E: 128×192 at x=192; S: 192×128 at x=320; W: 128×192 at x=512).

### 4.4 Frame counts vs speed and coefficient

| set | frame_count | speed | coef | speed×coef |
|---|---|---|---|---|
| basic | 16 | 0.03125 | 32 | 1 |
| fast | 32 | 0.0625 | 32 | 2 |
| express | 32 | 0.09375 | 32 | 3 |
| turbo | 64 (+`alternate=true`) | 0.125 | 32 | 4 |

`animation_speed_coefficient` has no description in the API (TransportBeltConnectablePrototype). The runtime API says only "The animation speed coefficient of this belt connectable prototype." **[inference]** `speed×coef` is probably the number of animation frames advanced per tick. The coefficient is constant at 32 across all tiers, so the belt texture would move in step with the items for any `speed`, provided the sheet was drawn at the same pixels-per-frame. Under that hypothesis, express frames reused at 0.15625 would advance 5 frames per tick out of a 32-frame cycle. Nothing in the sources confirms this, and the PNGs are absent, so it has to be checked visually in a graphical client.

---

## 5. Items

All belt items are in subgroup `"belt"` (`base/prototypes/item-groups.lua:17-22`: group "logistics", order "b").

| item | file:line | stack_size | order | color_hint | weight | extra |
|---|---|---|---|---|---|---|
| transport-belt | base item.lua:1284-1296 | 100 | a[transport-belt]-a[transport-belt] | "1" | (auto) | |
| fast-transport-belt | :1297-1309 | 100 | a[transport-belt]-b[fast-transport-belt] | "2" | (auto) | |
| express-transport-belt | :1310-1323 | 100 | a[transport-belt]-c[express-transport-belt] | "3" | 10*kg | |
| turbo-transport-belt | SA item.lua:150-164 | 100 | a[transport-belt]-d[turbo-transport-belt] | "4" | 20*kg | default_import_location="vulcanus" |
| underground-belt | base :1482-1494 | 50 | b[underground-belt]-a[underground-belt] | "1" | auto | |
| fast-underground-belt | :1495-1507 | 50 | b[underground-belt]-b[fast-underground-belt] | "2" | auto | |
| express-underground-belt | :1508-1521 | 50 | b[underground-belt]-c[express-underground-belt] | "3" | 20*kg | |
| turbo-underground-belt | SA :165-179 | 50 | b[underground-belt]-d[turbo-underground-belt] | "4" | 40*kg | vulcanus |
| splitter | base :1522-1535 | 50 | c[splitter]-a[splitter] | "1" | 20*kg | |
| fast-splitter | :1560-1572 | 50 | c[splitter]-b[fast-splitter] | "2" | auto | |
| express-splitter | :1573-1586 | 50 | c[splitter]-c[express-splitter] | "3" | 20*kg | |
| turbo-splitter | SA :180-194 | 50 | c[splitter]-d[turbo-splitter] | "4" | 40*kg | vulcanus |
| loader / fast- / express- / turbo-loader | base :1587-1628, SA :195-207 | 50 | d[loader]-a/b/c/d | 1-4 | | `hidden = true` |

Every item has `place_result = <same name>` and `icon = "__base__/graphics/icons/<name>.png"` (SA: `__space-age__/graphics/icons/...`). Belts use `item_sounds.transport_belt_inventory_move/pickup`; UGs and splitters use `mechanical_inventory_*`. `kg = 1000*grams` (core/lualib/util.lua:881).
API details:
- ItemPrototype::weight: "default weight is calculated automatically from recipes".
- ItemPrototype::color_hint: "Only used by hidden setting".
- ItemPrototype::default_import_location: SpaceLocationID, default 'nauvis'. `nauvis` is defined in base (`base/prototypes/planet/planet.lua:9`). `vulcanus` exists only with SA, so only set it under a guard.
- ItemPrototype::place_result: "The localised name of the entity will be used as the in-game item name".

Suggested Magnetics order: `a[transport-belt]-e[...]`, `b[underground-belt]-e[...]`, `c[splitter]-e[...]`. These sort after turbo's `d`.

---

## 6. Recipes

| recipe | file:line | category (base) | category under SA | energy | ingredients → result | enabled |
|---|---|---|---|---|---|---|
| transport-belt | base recipe.lua:763-772 | crafting | pressing | 0.5 (default) | iron-plate 1, iron-gear-wheel 1 → 2 | **true** (no `enabled` key) |
| underground-belt | :1062-1073 | crafting | pressing | 1 | iron-plate 10, transport-belt 5 → 2 | false |
| splitter | :1049-1061 | crafting | pressing | 1 | electronic-circuit 5, iron-plate 5, transport-belt 4 → 1 | false |
| fast-transport-belt | :1321-1331 | crafting | pressing | 0.5 | iron-gear-wheel 5, transport-belt 1 → 1 | false |
| fast-underground-belt | :1230-1241 | crafting | pressing | 2 | iron-gear-wheel 40, underground-belt 2 → 2 | false |
| fast-splitter | :1242-1253 | crafting | pressing | 2 | splitter 1, iron-gear-wheel 10, electronic-circuit 10 → 1 | false |
| express-transport-belt | :1763-1775 | crafting-with-fluid | crafting-with-fluid-or-metallurgy | 0.5 | iron-gear-wheel 10, fast-transport-belt 1, lubricant 20 → 1 | false |
| express-underground-belt | :2012-2025 | crafting-with-fluid | crafting-with-fluid-or-metallurgy | 2 | iron-gear-wheel 80, fast-underground-belt 2, lubricant 40 → 2 | false |
| express-splitter | :2052-2065 | crafting-with-fluid | crafting-with-fluid-or-metallurgy | 2 | fast-splitter 1, iron-gear-wheel 10, advanced-circuit 10, lubricant 80 → 1 | false |
| turbo-transport-belt | SA recipe.lua:1685-1705 | metallurgy, surface pressure = 4000 | — | 0.5 | tungsten-plate 5, express-transport-belt 1, lubricant 20 → 1 | false |
| turbo-underground-belt | SA :1706-1727 | metallurgy, pressure 4000 | — | 2 | tungsten-plate 40, express-underground-belt 2, lubricant 40 → 2 | false |
| turbo-splitter | SA :1728-1750 | metallurgy, pressure 4000 | — | 2 | express-splitter 1, tungsten-plate 15, processing-unit 2, lubricant 80 → 1 | false |
| loaders | base :1074-1088, 2026-2051; SA :1751-1762 | crafting | — | 1/3/10/20 | … | false, hidden |

- The SA category overrides are at `space-age/base-data-updates.lua:241-249`.
- The categories `pressing`, `crafting-with-fluid-or-metallurgy` and `metallurgy` are defined only in `space-age/prototypes/categories/recipe-category.lua:9,17,25`. Using them without SA is an error [inference: an undefined category reference].
- `crafting-with-fluid` is in base (`base/prototypes/categories/recipe-category.lua:21`).
- Under SA, `crafting-with-fluid-or-metallurgy` is craftable by assembling-machine-2/3 (base-data-updates.lua:81-82) and the foundry (`space-age/prototypes/entity/entities.lua:1153`).
- API RecipePrototype facts: `energy_required` defaults to 0.5, "Must be > 0.001"; `enabled` defaults to true, "If a recipe is unlocked via technology, this should be set to false"; category "crafting" "can not contain recipes with fluid ingredients". The character crafts only `{"crafting"}` in base (`base/prototypes/entity/entities.lua:709`), so a lubricant recipe cannot be hand-crafted.
- **Quality recycling:** `quality/data-updates.lua` auto-generates a recycling recipe for **every** recipe unless `auto_recycle == false` (API RecipePrototype::auto_recycle). The rules are at `quality/prototypes/recycling.lua:160-183`. Recipes in category `metallurgy` are skipped unless their name is in the hardcoded list `{"big-mining-drill","turbo-transport-belt","turbo-underground-belt","turbo-splitter"}` (l.173-174). So a Magnetics belt recipe in `metallurgy` would get **no** recycling recipe.

---

## 7. Technologies

| tech | file:line | unlocks | prerequisites | cost |
|---|---|---|---|---|
| logistics | base technology.lua:2101-2124 | underground-belt, splitter | automation-science-pack | 20 × (red 1), time 15 |
| logistics-2 | :2494-2519 | fast-transport-belt, fast-underground-belt, fast-splitter | logistics, logistic-science-pack | 200 × (red, green), 30 |
| logistics-3 | :3287-3317 | express-transport-belt, express-underground-belt, express-splitter | production-science-pack, lubricant | 300 × (red, green, blue, purple), 15 |
| turbo-transport-belt | SA technology.lua:753-786 | turbo-transport-belt, turbo-underground-belt, turbo-splitter | metallurgic-science-pack, logistics-3 | 500 × (red, green, blue, purple, space, metallurgic), 60 |

Icons are `__base__/graphics/technology/logistics-{1,2,3}.png` and `__space-age__/graphics/technology/turbo-transport-belt.png`, all with `icon_size = 256`. No mod (SA, quality, elevated-rails) modifies logistics-1/2/3. The only mention outside base is the turbo prerequisite at SA l.773.
Naming (API TechnologyPrototype::name): "If this name ends with `-<number>`, that number is ignored for localization purposes. E.g. if the name is `technology-3`, the game looks for the `technology-name.technology` localization. The technology tree will also show the number on the technology icon." This is why only the `logistics=` key exists in `base/locale/en/base.cfg:855` (`[technology-name]`) and `:957` (`[technology-description]`). A Magnetics tech called `logistics-4` would inherit "Logistics" plus the number 4. A tech with its own name needs its own locale keys.

---

## 8. Corpses (remnants) and dying explosions

| remnants | file:line | tile | animation |
|---|---|---|---|
| transport-belt-remnants | base remnants.lua:~424-450 | 1×1 | `make_rotated_animation_variations_from_sheet(2, {...})` |
| fast-transport-belt-remnants | :~1531-1557 | 1×1 | same helper |
| express-transport-belt-remnants | :2291-2317 | 1×1 | same helper, 106×102, direction_count 4 |
| splitter / fast / express-splitter-remnants | :452 / 1560 / 2318-2344 | 2×1 | plain RotatedAnimation, 190×190, dir 4 |
| underground / fast / express-underground-belt-remnants | :480 / 1588 / 2345-2372 | 1×1, flag "building-direction-8-way" | 156×144, dir 8 |
| turbo-* remnants | SA remnants.lua:115 / 142 / 169 | | |

Verbatim (express belt remnants, base remnants.lua:2291-2317):
```lua
  {
    type = "corpse",
    name = "express-transport-belt-remnants",
    icon = "__base__/graphics/icons/express-transport-belt.png",
    flags = {"placeable-neutral", "not-on-map"},
    hidden_in_factoriopedia = true,
    subgroup = "belt-remnants",
    order = "a-c-a",
    selection_box = {{-0.5, -0.5}, {0.5, 0.5}},
    tile_width = 1,
    tile_height = 1,
    selectable_in_game = false,
    time_before_removed = 60 * 60 * 15, -- 15 minutes
    expires = false,
    final_render_layer = "remnants",
    remove_on_tile_placement = false,
    animation =  make_rotated_animation_variations_from_sheet (2,
    {
      filename = "__base__/graphics/entity/express-transport-belt/remnants/express-transport-belt-remnants.png",
      line_length = 1,
      width = 106,
      height = 102,
      direction_count = 4,
      shift = util.by_pixel(1, -0.5),
      scale = 0.5
    })
  },
```
`make_rotated_animation_variations_from_sheet` is a **global** function (base remnants.lua:3; redefined identically in quality and SA remnants.lua:3). It returns an array of deep-copied RotatedAnimations with y offsets. The API type is `CorpsePrototype::animation` : RotatedAnimationVariations = `RotatedAnimation | array[RotatedAnimation]`.
Explosions: base explosions.lua `transport-belt-explosion` :737, `underground-belt-explosion` :830, `splitter-explosion` :857, `fast-*` :2962/3110/3137, `express-transport-belt-explosion` :4844, `express-underground-belt-explosion` :4938, `express-splitter-explosion` :4966. SA explosions.lua turbo :495/589/617. Each has an `*-explosion-base` plus particles (SA particles.lua:595-656 for turbo). Subgroups: `belt-remnants` (item-groups.lua:428-433) and `belt-explosions` (:588-593).
The simplest option for a mod tier is to reference the express corpse and explosion **by name** (`corpse = "express-transport-belt-remnants"`, `dying_explosion = "express-transport-belt-explosion"`). A tinted corpse needs a deep-copied corpse prototype with `tint` set on every element of `animation`.

---

## 9. How Space Age adds the turbo tier (the pattern to copy)

1. **Entities** are in `space-age/prototypes/entity/transport-belts.lua`, required from `space-age/data.lua:9`. The file requires `circuit-connector-sprites`, `meld`, `__base__.prototypes.entity.hit-effects`, `__base__.prototypes.entity.sounds` and `__space-age__.prototypes.factoriopedia-simulations`. It builds a local animation set, melds the base global `belt_reader_gfx` into it, patches `next_upgrade` on the base express entities (l.31-33), then `data:extend`s turbo-transport-belt, turbo-underground-belt, turbo-splitter and turbo-loader.
2. **Graphics paths:**
   - `__space-age__/graphics/entity/turbo-transport-belt/turbo-transport-belt.png` (+ `-frozen.png`)
   - `__space-age__/graphics/entity/turbo-underground-belt/turbo-underground-belt-structure{,-back-patch,-front-patch}.png`
   - `__space-age__/graphics/entity/turbo-splitter/turbo-splitter-{north,east,south,west,east-top_patch,west-top_patch}` via `util.sprite_load` (metadata `.lua` present)
   - frozen: `__space-age__/graphics/entity/frozen/{underground-belt,splitter}/...`
   - icons: `__space-age__/graphics/icons/turbo-{transport-belt,underground-belt,splitter,loader}.png`
   - tech: `__space-age__/graphics/technology/turbo-transport-belt.png`
   - The turbo loader reuses `__base__/graphics/entity/loader/loader-structure.png`.
   - Sounds reuse base ogg files (`__base__/sound/express-transport-belt.ogg`, SA l.60).
3. **Items:** `space-age/prototypes/item.lua:150-207`. **Recipes:** `space-age/prototypes/recipe.lua:1685-1762`. **Technology:** `space-age/prototypes/technology.lua:753-786`. **Remnants:** SA remnants.lua:115-190. **Explosions:** SA explosions.lua:417-680. **Particles:** SA particles.lua:595-656. **Factoriopedia:** `simulations.factoriopedia_turbo_underground_belt` (SA factoriopedia-simulations.lua:6; a blueprint string with hard-coded entity names). This is optional per the API, so a mod can omit it.
4. **Base modifications** (`space-age/base-data-updates.lua`, run from data.lua:65): UG `underground_collision_mask` (l.20-24), `heating_energy` (l.111-119), recipe categories (l.241-249), and frozen patches (base-frozen-graphics.lua).
5. **Locale** (`space-age/locale/en/space-age.cfg`): [entity-description] l.19-20, [entity-name] l.133-135 (turbo-loader l.86), [item-name] l.443-445, [technology-name] l.544, and [technology-description] l.613 ("Even faster transport belts."). There are no separate recipe-name keys for the belts.

---

## 10. Freezing / heating (Space Age only)

API EntityPrototype::heating_energy (default '0W'): "This entity can freeze if heating_energy is larger than zero." Vanilla values under SA: belts 10kW, UG 50/100/150/200kW, splitters 40kW. The freezing feature flag is `FeatureFlags::freezing` (global `feature_flags`), and SA's info.json has `"freezing_required": true`. Whether setting `heating_energy` or `frozen_patch` is harmless with freezing disabled is **[not found in sources]**. Guard it with `if feature_flags["freezing"] then … end`. Alternatively deep-copy from `data.raw` after SA has loaded: the copy then automatically carries SA's heating_energy, frozen_patch and underground_collision_mask when SA is active, and none of them when it is not.

---

## 11. Upgrade planner, fast-replace, and related_* links

- API EntityPrototype::next_upgrade: "This entity may not have 'not-upgradable' flag set and must be minable. … The upgrade target entity needs to have the same bounding box, collision mask, and fast replaceable group as this entity. The upgrade target entity must have least 1 item that builds it that isn't hidden."
- API UpgradeItemPrototype (description): the source may not be hidden and its mining result may not be a hidden item. "[underground belts] cannot be upgraded to [transport belts] and vice versa."
- API EntityPrototype::fast_replaceable_group: "Entities with the same fast replaceable group can be configured as upgrades for each other in the upgrade planner."
- Vanilla chains:
  - base: `transport-belt → fast-transport-belt → express-transport-belt` (end); `underground-belt → fast-underground-belt → express-underground-belt` (end); `splitter → fast-splitter → express-splitter` (end).
  - SA appends `express-* → turbo-*` (SA transport-belts.lua:31-33); turbo is the end.
  - Loaders, linked-belt and lane-splitter: no chain.
- All belts, UGs, splitters and the lane-splitter share `fast_replaceable_group = "transport-belt"`, which enables belt↔UG↔splitter fast replace (tips `base/locale/en/base.cfg:1600-1601`). Loaders use `"loader"`, linked belts `"linked-belts"`.
- `related_underground_belt` (TransportBelt only) is used for smart-drag auto-UG. `related_transport_belt` (Splitter only) is used for the sound of the underlying belt. Both are validated to point at the correct type (binary strings, §3.5). At runtime, `LuaEntityPrototype::related_underground_belt` exists (subclass TransportBelt).
- For the Magnetics tier:
  - With SA: set `turbo-*.next_upgrade = "magnetic-*"`.
  - Without SA: set `express-*.next_upgrade = "magnetic-*"`.
  - Leave the Magnetics tier's own `next_upgrade = nil`. A deep copy of express would otherwise inherit `"turbo-…"` when SA is loaded.
  - Keep the same collision_box as the copied entity, and the same collision mask (a deep copy does this).

---

## 12. Feasibility: a Magnetics belt tier reusing express graphics with a tint

### 12.1 Which graphics fields accept `tint` (per prototype-api.json)

`SpriteParameters` has `tint : Color` (default `{r=1,g=1,b=1,a=1}`), `tint_as_overlay : boolean` (default false, no description), and `apply_runtime_tint : boolean` (no description).

| field | type | inheritance chain → tint | accepts tint |
|---|---|---|---|
| `belt_animation_set.animation_set` | RotatedAnimation | RotatedAnimation → AnimationParameters → SpriteParameters | yes |
| `belt_animation_set.frozen_patch` | RotatedSprite | → SpriteParameters | yes |
| `belt_animation_set.belt_reader[i].sprites` | RotatedAnimation | as above | yes (leave untinted) |
| `UndergroundBeltStructure.*` / `LoaderStructure.*` / `SplitterPrototype::frozen_patch` | Sprite4Way (`sheet`/`sheets` = SpriteNWaySheet → SpriteParameters; or `north..west` = Sprite → SpriteParameters) | | yes (put `tint` inside `sheet`) |
| `SplitterPrototype::structure`, `structure_patch` | Animation4Way (struct of Animation, or a single Animation) → AnimationParameters → SpriteParameters | | yes (per direction) |
| `underground_sprite` / `underground_remove_belts_sprite` | Sprite | | yes (not needed) |
| `CorpsePrototype::animation` | RotatedAnimationVariations = RotatedAnimation \| array | | yes (per element) |
| `icons[i]` | IconData | own `tint` field | yes |
| `connector_frame_sprites` | TransportBeltConnectorFrame (AnimationVariations / SpriteVariations) | | yes, but shared global: do not touch |

The API Color type says: "values can be from 0-255, they are interpreted as such if at least one value is > 1… The game usually expects colors to be in pre-multiplied form."
**[not found in sources]** How `tint` blends with the texture is not documented. **[inference]** The identity default `{1,1,1,1}` suggests multiplication. If so, tinting can only darken or shift the hue of the blue express textures, not brighten them; violet, teal and grey-blue variants are reachable. `tint_as_overlay` is used in vanilla only on runtime-tinted mask layers (`elevated-rails/prototypes/sloped-trains-updates.lua:48-51`) and on particles (`space-age/prototypes/particles.lua:1443`); its semantics are undocumented.
**No vanilla belt, UG or splitter uses `tint`** (grep of both transport-belts.lua files). The visual result must be checked in a graphical client. The headless install contains no `.png` files at all (a `find` shows only `.lua/.cfg/.json` plus shader and `.metal` files), so nothing visual can be verified here.

### 12.2 Why reusing express is the safe base

- `__base__/…` paths are valid with or without SA (API FileName: `__<mod-name>__` "is accessible as long as the mod is active"). Reusing turbo graphics (`__space-age__/…`) would break base-only games.
- Express UG and splitter use plain sheets (no `util.sprite_load`), so a deep copy plus `tint` is straightforward.
- A deep copy of the express entities made **after SA's data.lua** automatically carries SA's frozen patches, heating_energy and underground_collision_mask when SA is active, and has none of them otherwise.

### 12.3 Traps (source-backed)

1. **Shared tables.** Mutating `data.raw["transport-belt"]["express-transport-belt"].belt_animation_set` in place recolours the express belt, UG, splitter and loader (§4.2). Always use `table.deepcopy` (core/lualib/util.lua:6-22, cycle-safe).
2. **Inherited links in a copy.** You must overwrite `name`, `minable.result`, `icon`/`icons`, `related_underground_belt` (belt), `related_transport_belt` (splitter), and `next_upgrade`. Also consider `corpse`, `dying_explosion` and `factoriopedia_simulation`; the express-UG simulation is a blueprint containing express entities (base factoriopedia-simulations.lua:34-42).
3. **Loading order.** If Magnetics loads before SA, SA's `express.next_upgrade = "turbo-…"` (SA l.31-33) overwrites a Magnetics chain, and a deep copy would miss the frozen patches. See §1: an optional dependency on space-age is needed; its syntax is [not found in sources].
4. **SA-only identifiers.** Guard the `pressing` / `metallurgy` / `crafting-with-fluid-or-metallurgy` categories, `default_import_location = "vulcanus"`, `surface_conditions` on pressure, and any `__space-age__` path.
5. **Quality recycling** of a `metallurgy` recipe is skipped (§6).

### 12.4 Sketch

This is my proposal, not vanilla code. Every field is verified against the API or vanilla usage above; the colour and the numbers are placeholders.

```lua
-- data.lua of Magnetics (runs after base, and after space-age if active)
local TINT  = {r = 0.75, g = 0.55, b = 1.0, a = 1}  -- placeholder; tune in a graphical client
local SPEED = 0.15625                               -- 40/256 → 75 items/s (speed × 480)

local function tinted_icon(path) return {{icon = path, icon_size = 64, tint = TINT}} end

-- one tinted animation set, shared by all Magnetics belt entities (vanilla shares too)
local anim = table.deepcopy(data.raw["transport-belt"]["express-transport-belt"].belt_animation_set)
anim.animation_set.tint = TINT        -- RotatedAnimation inherits SpriteParameters::tint
-- anim.frozen_patch / anim.belt_reader exist only if SA loaded first; leave them untinted

local belt = table.deepcopy(data.raw["transport-belt"]["express-transport-belt"])
belt.name, belt.icon = "magnetic-transport-belt", nil
belt.icons = tinted_icon("__base__/graphics/icons/express-transport-belt.png")
belt.minable.result = "magnetic-transport-belt"
belt.speed = SPEED
belt.belt_animation_set = anim
belt.related_underground_belt = "magnetic-underground-belt"
belt.next_upgrade = nil

local ug = table.deepcopy(data.raw["underground-belt"]["express-underground-belt"])
ug.name, ug.icon = "magnetic-underground-belt", nil
ug.icons = tinted_icon("__base__/graphics/icons/express-underground-belt.png")
ug.minable.result = "magnetic-underground-belt"
ug.speed, ug.max_distance = SPEED, 13           -- vanilla progression 5/7/9/11; uint8
ug.belt_animation_set = anim
ug.next_upgrade = nil
for _, k in pairs{"direction_in", "direction_out", "direction_in_side_loading",
                  "direction_out_side_loading", "back_patch", "front_patch"} do
  ug.structure[k].sheet.tint = TINT             -- Sprite4Way.sheet = SpriteNWaySheet → SpriteParameters
end

local sp = table.deepcopy(data.raw["splitter"]["express-splitter"])
sp.name, sp.icon = "magnetic-splitter", nil
sp.icons = tinted_icon("__base__/graphics/icons/express-splitter.png")
sp.minable.result = "magnetic-splitter"
sp.speed = SPEED
sp.belt_animation_set = anim
sp.related_transport_belt = "magnetic-transport-belt"
sp.next_upgrade = nil
for _, d in pairs{"north", "east", "south", "west"} do sp.structure[d].tint = TINT end
sp.structure_patch.east.tint = TINT
sp.structure_patch.west.tint = TINT

data:extend{belt, ug, sp}

-- upgrade chain: append after the current top tier
local top = mods["space-age"] and "turbo" or "express"
data.raw["transport-belt"][top .. "-transport-belt"].next_upgrade = "magnetic-transport-belt"
data.raw["underground-belt"][top .. "-underground-belt"].next_upgrade = "magnetic-underground-belt"
data.raw["splitter"][top .. "-splitter"].next_upgrade = "magnetic-splitter"
```
Items: copy the `express-*` items and change `name`, `icons`, `place_result`, `order` (`…-e[…]`) and `color_hint = {text = "5"}`. Set `default_import_location` only under `mods["space-age"]`.
Recipe: `category = "crafting-with-fluid"` works in base. Optionally switch to `"crafting-with-fluid-or-metallurgy"` under SA, as `base-data-updates.lua:247-249` does for express.
Technology: prerequisites `"logistics-3"`, plus `"turbo-transport-belt"` under SA.

---

## 13. Open points: not found in sources, to verify on the stand

1. The maximum allowed belt `speed`, and how non-multiples of 1/256 are rounded.
2. Semantics of `animation_speed_coefficient`, `alternate`, `tint` blending and `tint_as_overlay` (no API descriptions).
3. Whether the texture stays in sync with the items when 32-frame express frames run at a new speed. This needs visual testing; there are no PNGs here.
4. Mod load-order and optional-dependency syntax for `info.json`.
5. Whether `heating_energy` or `frozen_patch` is accepted or ignored when the `freezing` feature flag is off.
6. Whether belt, UG and splitter speeds must be equal (vanilla keeps them equal).
7. How belt stacking (SA) interacts with the ×480 formula.
