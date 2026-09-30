# Runtime test harness for "Magnetics" — Factorio 2.0.77 API reference (headless `--create` → `--benchmark`)

Source conventions used throughout:

- **R: `Class.member`** = `/opt/factorio-api/runtime-api.json` (`application_version` = `2.0.77`, `api_version` = 6), entry `classes[Class].methods|attributes[member]`; **R-concept: X** = `concepts[X]`; **R-define: X** = `defines[X]`; **R-event: X** = `events[X]`.
- **P: `Proto.prop`** = `/opt/factorio-api/prototype-api.json` (`application_version` = `2.0.77`).
- **D: path:line** = file under `/opt/factorio/data/`.
- **BIN** = a string found by `strings` in `/opt/factorio/bin/x64/factorio` (the binary was not run).
- Everything tagged **[not in sources]** or **[pilot-check]** is a gap: the docs are silent, so the harness must measure it in a pilot run and must not assume it.

---

## 0. Answers in one screen

| Question | Answer (source) |
|---|---|
| Empty test area | `game.create_surface(name, MapGenSettings)`, then `surface.generate_with_lab_tiles = true`, then `request_to_generate_chunks` + `force_generate_chunk_requests()` before you build (R: `LuaGameScript.create_surface`, R: `LuaSurface.generate_with_lab_tiles`, R: `LuaSurface.force_generate_chunk_requests`; the pattern and the comment "Must force generate the starting chunks before placing the silo, walls etc." are in D: base/script/wave-defense/wave_defense.lua:297-303). |
| Default force of `create_entity` | **enemy**. Always pass `force = "player"` (R: `LuaSurface.create_entity`, parameter `force`: "Force of the entity, default is enemy."). |
| Directions | 16 values: north, northnortheast, northeast, eastnortheast, east, … (R-define: `direction`). The opposite direction is `(d + 8) % 16` (D: core/lualib/util.lua:161). The changelog says: "Added 8 new directions into defines.direction … migrate them by multiplying by 2" (D: changelog.txt:3431). The API JSON does not give numeric values, so always use the names. |
| Crafter inventories | `defines.inventory.crafter_input / crafter_output / crafter_modules / crafter_trash`. The old `assembling_machine_*`, `furnace_source`, `furnace_result`, `furnace_modules` and `rocket_silo_*` are marked **Deprecated** (R-define: `inventory`). |
| Turret ammo / fuel | `defines.inventory.turret_ammo`, `defines.inventory.fuel`, `defines.inventory.burnt_result` (R-define: `inventory`). |
| Set recipe | `assembler.set_recipe(recipe?, quality?)` works on the **AssemblingMachine subclass only** (R: `LuaEntity.set_recipe`, `subclasses: ['AssemblingMachine']`). You can also pass `recipe = "..."` to `create_entity` (variant `assembling-machine`). A furnace has no setter; its `previous_recipe` is read-only (R: `LuaEntity.previous_recipe`). |
| Freeze biters | Give a `stop` command with `distraction = defines.distraction.none` (R-concept: `Command`, variant `defines.command.stop`; R-define: `distraction.none` = "Perform command even if someone attacks the unit.") and turn off `ai_settings.allow_destroy_when_commands_fail`. Base biters ship with `destroy_when_commands_fail = true` (D: base/prototypes/entity/biter-ai-settings.lua:1). `LuaEntity.active` write is **deprecated**; use `disabled_by_script` (R: `LuaEntity.active`). |
| Research | `force.technologies[name].researched = true` applies the effects ("Switching from false to true will trigger the technology advancement perks", R: `LuaTechnology.researched`). `research_recursive()` also researches the prerequisites. |
| Statistics in 2.0 | Per surface: `force.get_item_production_statistics(surface)` returns `LuaFlowStatistics`. For item statistics, input = production and output = consumption (R: `LuaFlowStatistics` class description). |
| Output | `helpers.write_file(filename, data, append?, for_player?)` writes into `script-output`; `helpers.table_to_json(table)` (R: `LuaHelpers.*`). |

---

## 1. Run model and which calls are valid in which state

### 1.1 Command line (BIN strings only; the binary was not run)

The binary contains these option names: `create`, `map-gen-settings`, `map-settings`, `map-gen-seed`, `benchmark-ticks`, `benchmark-runs`, `benchmark-sanitize`, `benchmark-verbose`, `benchmark-ignore-paused`, `mod-directory`, `instrument-mod`, `until-tick`. It also contains these help strings:

- "number of ticks for benchmarking. Default is 1000"
- "leaves the game paused if it was paused when saved. By default the game is unpaused when a benchmark starts."
- "Map generation settings for use with --create, --start-server-load-scenario or --generate-map-preview. See data/map-gen-settings.example.json"
- "Map settings for use with --create or --start-server-load-scenario. See data/base/prototypes/map-settings.lua"
- "Map generation seed for use with --create, …"
- "--until-tick requires --load-game"
- "comma separated list of timings to output each tick. "all", "timestamp" as well as all other values … An empty string disabled verbose benchmarking." (by its wording presumably the help text of `--benchmark-verbose`; which option a help string belongs to is not visible in `strings` output)
- "--instrument-mod cannot be used with multiplayer games" (so an instrument mode exists; its semantics are **[not in sources]**)

Where `script-output` lives: `/opt/factorio/config-path.cfg` contains `config-path=__PATH__executable__/../../config` and `use-system-read-write-data-directories=false`. Its comment says that with `false` "it will use application root directory". The inference is that write-data = `/opt/factorio`, so output goes to `/opt/factorio/script-output/`. **[pilot-check]** (no `config/config.ini` exists yet).

Whether `--create` runs the `freeplay` scenario is **[not in sources]**. `D: base/scenarios/freeplay/control.lua` only contains `require('__base__/script/freeplay/control.lua')`, and on a headless run with no players it hardly matters. Which mods the benchmark loads (mod-list.json versus the save) is also **[not in sources]**.

### 1.2 Lifecycle facts (R: `LuaBootstrap.*`)

- `script.on_init(handler)`: "only called when a new save game is created or when a save file is loaded that previously didn't contain the mod … It has full access to LuaGameScript and the storage table … No other events will be raised for the mod until it has finished this step." Its example is `script.on_init(function() storage.players = {} end)`. With `--create`, this is where the lab can be built, and the result is saved into `save.zip`.
- `script.on_load(handler)`: runs when a save is loaded. "Access to LuaGameScript is not available. The storage table can be accessed and is safe to read from, but not write to, as doing so will lead to an error." It is only for metatables, conditional handlers and local references. `--benchmark` loads a save that already contains the mod, so by the on_init description on_load runs there, **not** on_init.
- `script.on_configuration_changed(handler)`: runs when the game version, any mod version, the mod list or a startup setting changes.
- `script.on_nth_tick(tick | array | nil, handler(NthTickEventData{nth_tick, tick}))`: "When the game is on tick 0 it will trigger all registered handlers." Passing `nil` as the only parameter unregisters all of them.
- `script.on_event(event, handler, filters?)`: "Each mod can only register once for every event, as any additional registration will overwrite the previous one." So the harness must keep **one** `on_tick` handler and dispatch inside it.
- R-event `on_tick` has data `{name, tick}`. R-event `on_entity_died` has `{cause, damage_type, entity, force, loot, name, tick}`. R-event `on_research_finished` has `{by_script, name, research, tick}`.
- Registering handlers in the main chunk of control.lua, unconditionally, covers both processes (`--create` and `--benchmark`). The rule that `game` is unavailable in the main chunk is **[not in sources]** as JSON text; the docs state it only for on_load. Do not touch `game` there.

### 1.3 Storage rules

- LuaEntity references are stored in `storage` by base code: `storage.train_stop = surface.create_entity{...}` (D: base/prototypes/tips-and-tricks-simulations.lua:2342). Stored entities survive the create → save → benchmark cycle; always check `.valid` (R: `LuaEntity.valid`).
- **LuaCustomTable cannot be serialized** (R: class `LuaCustomTable` description). The API text reads: "as soon as the user tries to save the game, a 'LuaCustomTable cannot be serialized' error will be shown." So never put `force.technologies`, `prototypes.item`, `game.players` and similar into `storage`.
- **LuaProfiler cannot be serialized** (R: `LuaHelpers.create_profiler`). It is also "Not available in settings and prototype stages". Its raw time cannot be read from Lua; it can only be printed as a LocalisedString (R: class `LuaProfiler`).
- An alternative to references is `game.get_entity_by_unit_number(unit_number)`. It returns `nil` if the prototype does not have the flag `get-by-unit-number` (R: `LuaGameScript.get_entity_by_unit_number`), so stored references are the safer choice.

### 1.4 Calls with timing or state restrictions (collected)

| Call | Restriction | Source |
|---|---|---|
| `create_entity`, `set_tiles` on a new surface | Chunks must be generated first ("Must force generate the starting chunks before placing …") | D: base/script/wave-defense/wave_defense.lua:301-303 |
| `find_non_colliding_position(..., radius = 0, ...)` | "will not stop searching until it finds a suitable position … would not be able to find a solution is running it before any chunks have been generated" | R: `LuaSurface.find_non_colliding_position` |
| `surface.clear()`, `delete_chunk()` | The raised events are `timeframe: future_tick`, so the effect is deferred. Do not clear and build in the same tick. | R: `LuaSurface.clear`, `LuaSurface.delete_chunk` (raises) |
| `game.create_surface` | Raises `on_surface_created` instantly. Names must be unique. | R: `LuaGameScript.create_surface` |
| `game.create_force` | At most 64 forces including the 3 built-in ones | R: `LuaGameScript.create_force` |
| `LuaEntity.active` write | Deprecated; affects only `disabled_by_script`. Corpses, fire, roboports, rolling stock and dying entities ignore writes. | R: `LuaEntity.active` |
| `LuaEntity.disabled_by_script` | Ignored if the entity is not updatable (`is_updatable`) | R: `LuaEntity.disabled_by_script` |
| `LuaEntity.electric_buffer_size` write | "Write access is limited to the ElectricEnergyInterface type." | R: `LuaEntity.electric_buffer_size` |
| `LuaEntity.drop_position` write | Drills and crafting machines cannot change it; inserters only with `allow_custom_vectors` | R: `LuaEntity.drop_position` |
| `LuaEntity.initial_amount` write | Error for a non-infinite resource | R: `LuaEntity.initial_amount` |
| `LuaEntity.health` write | Clamped to `[0, max_health]` | R: `LuaEntity.health` |
| `LuaEntity.shooting_target` | "Can't be set to nil via script." | R: `LuaEntity.shooting_target` |
| `LuaEntity.result_quality` | "Writing nil is not allowed." | R: `LuaEntity.result_quality` |
| `LuaForce.bulk_inserter_capacity_bonus` | Must be `>= 0` and `<= 254` | R: attribute |
| `LuaForce.research_queue` write | Only techs the force is able to research | R: attribute |
| `LuaFluidBox[i]` | Reading returns a **copy**; read, modify, write back. The index must be in bounds. | R: class `LuaFluidBox`, operator `index` |
| `helpers.write_file(..., for_player)` | `for_player` cannot be used in settings or prototype stages. `0` = "only write to the server's output if present" | R: `LuaHelpers.write_file` |

---

## 2. Building an empty lab surface

### 2.1 Signatures

- `LuaGameScript.create_surface(name: string, settings?: MapGenSettings) -> LuaSurface`. Positional arguments; raises `on_surface_created`.
- R-concept `MapGenSettings`: "When reading MapGenSettings, all properties will always be present, but they can be omitted when writing."
  `table{autoplace_controls?: dictionary[string -> AutoplaceControl], autoplace_settings?: dictionary['entity' | 'tile' | 'decorative' -> AutoplaceSettings], cliff_settings?: CliffPlacementSettings, default_enable_all_autoplace_controls?: boolean, height?: uint32, no_enemies_mode?: boolean, peaceful_mode?: boolean, property_expression_names?: PropertyExpressionNames, seed?: uint32, starting_area?: MapGenSize, starting_points?: array[MapPosition], territory_settings?: TerritorySettings, width?: uint32}`
  - `default_enable_all_autoplace_controls`: "Whether undefined autoplace_controls should fall back to the default controls or not. Defaults to true."
  - `width/height`: "If 0, the map has 'infinite' width".
  - `no_enemies_mode`: "Whether enemy creatures will not naturally spawn from spawners, map gen, or trigger effects." Whether script-created units still work under it is **[not in sources]**, so keep it `false` on the test surface.
  - `peaceful_mode`: "Whether enemy creatures will not attack unless the player first attacks them."
- R-concept `AutoplaceSettings` = `table{settings?: dictionary[string -> AutoplaceControl], treat_missing_as_default?: boolean}`.
- R-concept `CliffPlacementSettings` = `table{cliff_elevation_0, cliff_elevation_interval, cliff_smoothing, control, name, richness}`. The example JSON comment says "0 will result in no cliffs" (D: map-gen-settings.example.json).
- `LuaGameScript.default_map_gen_settings` (read, `MapGenSettings`): "The default map gen settings for this save". Start from it so that every sub-table (cliff_settings, territory_settings) is complete.
- `LuaSurface.generate_with_lab_tiles` (R/W boolean): "When set to true, new chunks will be generated with lab tiles, instead of using the surface's map generation settings." Set it **before** the chunks are requested.
- `LuaSurface.request_to_generate_chunks(position: MapPosition, radius?: uint32)`: the radius is in chunks, defaults to 0.
- `LuaSurface.force_generate_chunk_requests()`: "Blocks and generates all chunks that have been requested using all available threads."
- `LuaSurface.is_chunk_generated(chunk_position)`: use it for assertions.
- `LuaSurface.always_day`, `freeze_daytime`, `daytime` (R/W), `solar_power_multiplier` (R/W, "Cannot be less than 0"): these matter for solar tests.
- `LuaSurface.peaceful_mode`, `no_enemies_mode` (R/W boolean).

The lab tile names are `lab-dark-1` (D: base/prototypes/tile/tiles.lua:1974), `lab-dark-2` (:2002) and `lab-white` (:2030). There is also `out-of-map` (:832), and `empty-space` exists in Space Age only (D: space-age/prototypes/tile/tiles.lua:135).

Real base code builds a surface this way (D: base/script/wave-defense/wave_defense.lua:297-303):

```lua
  local surface = game.create_surface(name, settings)
  ...
  surface.request_to_generate_chunks(starting_point, 1 + ceil(get_base_radius() / 32))
  surface.force_generate_chunk_requests()
  --Must force generate the starting chunks before placing the silo, walls etc.
  create_silo(starting_point)
```

A tiny surface is made the same way: `game.create_surface(lobby_name, {width = 1, height = 1})` followed by `surface.set_tiles({{name = "out-of-map", position = {1,1}}})` (D: base/script/pvp/pvp.lua:69-70).

### 2.2 Alternative: reuse nauvis and repaint

- `LuaSurface.set_tiles(tiles: array[Tile], correct_tiles?: boolean, remove_colliding_entities?: boolean | 'abort_on_collision', remove_colliding_decoratives?: boolean, raise_event?: boolean, player?: PlayerIdentification, undo_index?: uint32)`. The arguments are **positional, not a table** (`format.takes_table = false`). R-concept `Tile` = `table{name: string, position: TilePosition}`. `remove_colliding_entities` defaults to `true`. The docs recommend one call for all tiles. Base usage: `surface.set_tiles(grass_tiles, false)` (D: base/script/wave-defense/wave_defense.lua:152).
- `LuaSurface.build_checkerboard(area: BoundingBox)`: "Sets the given area to the checkerboard lab tiles." Base uses `game.surfaces[1].build_checkerboard{{-24, -13}, {22, 13}}` (D: elevated-rails/prototypes/tips-and-tricks-simulations.lua:15).
- Nauvis already contains ore, trees, cliffs and enemies from map generation. To empty an area, use `find_entities_filtered{area=..., type=...}` and `.destroy()`, or `set_tiles` with `remove_colliding_entities=true`. A separate surface is cleaner and identical in base-only and Space Age runs, so it is the recommended choice.

### 2.3 Surface properties (relevant for a magnetics mod)

- Base defines the surface properties `gravity` (default 10), `pressure` (1000), **`magnetic-field` (90)**, `solar-power` (100) and `day-night-cycle` (300) (D: base/prototypes/planet/surface-property.lua:3-26).
- Space Age sets `magnetic-field` = 25 on vulcanus (D: space-age/prototypes/planet/planet.lua:45, planet at :18), 25 on gleba (:146), 99 on fulgora (:311), 10 on aquilo (:629) and 0 on space-platform (D: space-age/prototypes/surface.lua:13). The recycler recipe requires `magnetic-field` min 99 / max 99 (D: space-age/base-data-updates.lua:911-917).
- `LuaSurface.get_property(property) -> double` and `LuaSurface.set_property(property, value)` (R). `prototypes.surface_property[name].default_value` is readable (R: `LuaSurfacePropertyPrototype.default_value`, which has no description).
- **[not in sources]**: whether a planet-less surface created by `create_surface` reports `default_value` for each property. **Pilot**: log `surface.get_property(p)` for each `p` in `prototypes.surface_property`, then pin the values the tests need with `set_property`.
- `LuaSurface.ignore_surface_conditions` (R/W): "If surface condition checks should not be performed on this surface." Use it only in a test that deliberately bypasses conditions. Leave it `false` when the test checks the conditions themselves.
- Freezing: `entities_require_heating = true` appears only on aquilo (D: space-age/prototypes/planet/planet.lua:668). It is a `PlanetPrototype` property (P: `PlanetPrototype.entities_require_heating`), so a planet-less test surface should not freeze entities. **[pilot-check]** with `LuaEntity.frozen`.

---

## 3. `create_entity`: signature and per-type parameters

`LuaSurface.create_entity{...} -> LuaEntity?` (`format.takes_table = true`). It returns "The created entity or nil if the creation failed", so always check for `nil`.

Common fields (R: `LuaSurface.create_entity`):
`name: EntityID, position: MapPosition, direction?: defines.direction, mirror?: boolean, quality?: QualityID ("Defaults to normal"), force?: ForceID ("default is enemy"), target?, source?, cause?, snap_to_grid?: boolean ("If false the exact position given is used"), fast_replace?, undo_index?, player?, character?, spill?, raise_built?: boolean (fires script_raised_built), create_build_effect_smoke?: boolean (default true), spawn_decorations?, move_stuck_players?, item?, preserve_ghosts_and_corpses?, register_plant?, burner_fuel_inventory?: BlueprintInventoryWithFilters`.

Position: `LuaEntityPrototype.tile_width` and `tile_height` decide "if the center should be in the center of the tile (odd tile size dimension) or on the tile border (even tile size dimension)" (R). Compute the center as `top_left + size/2`. `can_place_entity{name, position, direction?, force?, build_check_type?, forced?, inner_name?} -> boolean` tests placement first (R: `LuaSurface.can_place_entity`).

Variant fields for the kinds the harness needs (R: `LuaSurface.create_entity`, `variant_parameter_groups`):

| Entity type | Extra fields |
|---|---|
| `assembling-machine` | `recipe?: string, recipe_quality?: string, control_behavior?` |
| `furnace` | `control_behavior?` only; no recipe field |
| `transport-belt` | `control_behavior?` |
| `underground-belt` | `type?: BeltConnectionType` ("Defaults to input"), where `BeltConnectionType` = `'input' \| 'output'` |
| `loader`, `loader-1x1` | `type?: BeltConnectionType` (default "input"), `belt_stack_size_override?, filter_mode?, filters?, control_behavior?` |
| `inserter` | `drop_position?, pickup_position?` (only if the prototype has `allow_custom_vectors`), `filters?, filter_mode?, use_filters?, override_stack_size?: uint8, spoil_priority?, control_behavior?` |
| `infinity-container` | `infinity_settings?: BlueprintInfinityInventorySettings, bar?, request_filters?, control_behavior?` |
| `infinity-pipe` | `infinity_settings?: InfinityPipeFilter` |
| `electric-energy-interface` | `buffer_size?: double, power_production?: double, power_usage?: double` |
| `electric-pole` | `auto_connect?: boolean` ("True by default. If set to false, created electric pole will not auto connect to neighbour electric poles.") |
| `resource` | `amount?: uint32, enable_cliff_removal?, enable_tree_removal?, snap_to_tile_center?: boolean` (default true) |
| `mining-drill` | `filter?, control_behavior?` |
| `ammo-turret`, `electric-turret`, `fluid-turret`, `turret` | `priority-list?: array[SlotFilter], ignore-unprioritised?: boolean, control_behavior?` |
| `container` | `bar?: uint32, control_behavior?` |
| `wall` | `control_behavior?` |
| unit (biter) | no variant group. The API examples say `game.surfaces[1].create_entity{name = "big-biter", position = {15, 3}, force = game.forces.player} -- Friendly biter` and `... name = "medium-biter", ..., force = game.forces.enemy} -- Enemy biter`. |

R-concept `BlueprintInfinityInventorySettings` = `table{filters?: array[InfinityInventoryFilter], remove_unfiltered_items?: boolean (default false)}`.
R-concept `InfinityInventoryFilter` = `table{count?: ItemCountType (default 0), index?: uint32, mode?: 'at-least' | 'at-most' | 'exactly' (default at-least), name: ItemID, quality?: QualityID (default normal)}`.
R-concept `InfinityPipeFilter` = `table{mode?: 'at-least' | 'at-most' | 'exactly' | 'add' | 'remove' (default at-least), name: string, percentage?: double, temperature?: double}`.

Warning: one of the API's own examples uses a 1.1-era entity name, `name = "filter-inserter"` (R: `LuaSurface.create_entity`, examples), which is not a 2.0 base prototype. Do not copy the API examples blindly. The 2.0 base inserters are `inserter` (D: base/prototypes/entity/entities.lua:2282), `fast-inserter` (:2385) and `bulk-inserter` (:5489); Space Age adds `stack-inserter` (D: space-age/prototypes/entity/entities.lua:2524).

Real 2.0 calls from the game data:

```lua
-- D: base/prototypes/tips-and-tricks-simulations.lua:629  (resource with amount)
game.surfaces[1].create_entity{name = "iron-ore", position = {-5.5, 1.5}, amount = 314159}
-- D: base/prototypes/tips-and-tricks-simulations.lua:186 (inserter with direction and force)
inserter = game.surfaces[1].create_entity{name = "inserter", position = {chest.position.x, chest.position.y + 1}, direction = defines.direction.south, force = player.force, create_build_effect_smoke = false}
-- D: base/prototypes/tips-and-tricks-simulations.lua:880 (assembler)
local assembler = game.surfaces[1].create_entity{name = "assembling-machine-1", position = {x - assembler_box.left_top.x, y}, force = "player"}
-- R: LuaSurface.create_entity example (assembler with recipe)
local asm = game.surfaces[1].create_entity{name = "assembling-machine-1", position = {15, 3}, force = game.forces.player, recipe = "iron-stick"}
```

Base names useful as reference or infrastructure:

- `electric-energy-interface` (D: base/prototypes/entity/entities.lua:8539; `hidden = true`, 2x2 collision `{{-0.9,-0.9},{0.9,0.9}}`, `buffer_capacity = "10GJ"` :8556, `usage_priority = "tertiary"` :8557, `energy_production = "500GW"` :8560, `energy_usage = "0kW"`). There is also `hidden-electric-energy-interface` (D: …:5357; collision box `{{0,0},{0,0}}`, `selectable_in_game = false`, `input_flow_limit = "0kW"`, `output_flow_limit = "500GW"`), a zero-size pure source.
- `infinity-chest` (type `infinity-container`, a deepcopy of `storage-chest`, D: base/prototypes/entity/entities.lua:9886-9893)
- `infinity-pipe` (D: …:9925)
- `substation` (D: …:7310; `maximum_wire_distance = 18`, `supply_area_distance = 9` at :7329-7330)
- `medium-electric-pole` (D: …:4607; wire 9, supply 3.5 at :4627-4628)
- `stone-furnace` (D: …:1018), `electric-furnace` (D: …:4301)
- `assembling-machine-1` (D: …:3134; `crafting_speed = 0.5` :3188, `energy_usage = "75kW"` :3195)
- `lab` (D: …:3819), `stone-wall` (D: …:3366), `heat-interface` (D: …:9996)
- Transport belts: `transport-belt` / `fast-transport-belt` / `express-transport-belt` (D: base/prototypes/entity/transport-belts.lua:151/187/223, speeds 0.03125/0.0625/0.09375 at :180/:216/:252) and SA `turbo-transport-belt` (speed 0.125, D: space-age/prototypes/entity/transport-belts.lua:39,68)
- Loaders: `loader` (:971), `loader-1x1` (:1026, both 0.03125, `hidden = true`), `fast-loader` (:1067, 0.0625), `express-loader` (:1123, 0.09375), SA `turbo-loader` (D: space-age/prototypes/entity/transport-belts.lua:362)
- Drills: `electric-mining-drill` (D: base/prototypes/entity/mining-drill.lua:259, `mining_speed = 0.5`, `energy_usage = "90kW"`), `burner-mining-drill` (:1570, `mining_speed = 0.25`, `energy_usage = "150kW"`), SA `big-mining-drill` (D: space-age/prototypes/entity/big-mining-drill.lua:557)
- Resources: `iron-ore` has `mining_time = 1` (D: base/prototypes/entity/resources.lua:77-80); copper, coal and stone are the same
- Turrets: `gun-turret` (D: base/prototypes/entity/turrets.lua:459, `max_health = 400`, `inventory_size = 1`, `automated_ammo_count = 10` at :476-477), `laser-turret` (:593, `buffer_capacity = "801kJ"`, `input_flow_limit = "9600kW"`, `drain = "24kW"` at :617-619)
- Biters: `small-biter` (D: base/prototypes/entity/enemies.lua:36; `max_health = 15` :39, `healing_per_tick = 0.01` :44, `vision_distance = 30` :61, `movement_speed = 0.2` :62, `distraction_cooldown = 300` :65), `behemoth-biter` (:378, `max_health = 3000`)
- The quality `normal` exists in base (D: base/prototypes/categories/quality.lua:5). `uncommon`, `rare`, `epic` and `legendary` come from the quality mod (D: quality/prototypes/quality.lua).

---

## 4. `defines.direction` in 2.0

- 16 members (R-define `direction`): `north, northnortheast, northeast, eastnortheast, east, eastsoutheast, southeast, southsoutheast, south, southsouthwest, southwest, westsouthwest, west, westnorthwest, northwest, northnorthwest`. The order here follows D: core/lualib/util.lua:122-139 (table closes after :138) (`util.direction_vectors`, e.g. `[defines.direction.east] = { 1, 0 }`, `[defines.direction.south] = { 0, 1 }`, so +y is south).
- `util.oppositedirection(direction)` returns `(direction + 8) % 16` (D: core/lualib/util.lua:159-162).
- The changelog says: "Added 8 new directions into defines.direction. If mods are storing any direction values in their storage, they will need to migrate them by multiplying by 2." (D: changelog.txt:3431). The numeric values themselves are not in runtime-api.json, so never hard-code numbers.
- The prototype flag `building-direction-16-way` exists (D: changelog.txt:3207). A fix note says "Fixed script could rotate inserters into diagonal directions" (D: changelog.txt:633), so use the 4 cardinal directions for belts and inserters.
- `helpers.direction_to_string(direction) -> string` (R) helps when writing JSON.
- Belt direction semantics (does `east` mean the items flow east?) and inserter semantics (is `direction` the pickup side or the drop side?) are **[not in sources]** as text. Measure them instead of assuming. For inserters, read `inserter.pickup_position` / `inserter.drop_position` after creation (R: `LuaEntity.pickup_position`, `drop_position`). The base `inserter` prototype has `pickup_position = {0, -1}` and `insert_position = {0, 1.2}` (D: base/prototypes/entity/entities.lua:2365-2366), and `long-handed-inserter` (name at :2488) has `{0, -2}` / `{0, 2.2}` (:2506-2507). The API says nothing about which direction these unrotated vectors belong to. The skeleton creates the inserter, checks `pickup_position.y < position.y`, and rotates if that is false.

---

## 5. Inventories and inserting items

R-define `inventory` in 2.0.77. The ones relevant here:

| Entity | Use | Deprecated alias (do not use) |
|---|---|---|
| Assembler / furnace / rocket silo input | `crafter_input` | `assembling_machine_input`, `furnace_source`, `rocket_silo_input` |
| … output | `crafter_output` | `assembling_machine_output`, `furnace_result`, `rocket_silo_output` |
| … modules | `crafter_modules` | `assembling_machine_modules`, `furnace_modules`, `rocket_silo_modules` |
| … trash / dump | `crafter_trash`, `assembling_machine_dump` | `assembling_machine_trash`, `furnace_trash` |
| Burner fuel | `fuel` | — |
| Burner spent fuel | `burnt_result` | — |
| Ammo turret | `turret_ammo` | — |
| Artillery | `artillery_turret_ammo` | — |
| Chest (`container`, `infinity-container`) | `chest` | — |
| Lab | `lab_input`, `lab_modules`, `lab_trash` | — |
| Drill modules | `mining_drill_modules` | — |
| Beacon | `beacon_modules` | — |

- `LuaControl.get_inventory(inventory: defines.inventory) -> LuaInventory?`. The docs warn that a define "is only meaningful for the corresponding LuaObject type … if the type of 'this' isn't the type referred to … it's almost guaranteed to not be the inventory asked for." Check with `get_inventory_name(inventory) -> string?` (R: `LuaControl.get_inventory_name`).
- `LuaEntity.get_output_inventory() -> LuaInventory?`, `get_fuel_inventory() -> LuaInventory?`, `get_burnt_result_inventory() -> LuaInventory?` (R).
- `LuaControl.insert(items: ItemStackIdentification) -> uint32` ("the 'best' inventory is chosen automatically"; the return is the number actually inserted). Also `get_item_count(item?: ItemFilter) -> uint32`, `remove_item(items) -> uint32`, `can_insert(items) -> boolean`.
- `LuaInventory.insert(items) -> uint32`, `remove(items) -> uint32`, `clear()`, `get_item_count(item?: ItemWithQualityID) -> uint32`, `get_contents() -> array[ItemWithQualityCount]` (`{count, name, quality}`), `get_item_quality_counts(item?) -> dictionary[string -> uint32]`, `is_empty()`, `count_empty_stacks(include_filtered?, include_bar?)`. The operator `inv[i]` returns a `LuaItemStack`, and `#inv` gives the slot count.
- R-concept `ItemStackIdentification` = `string | ItemStackDefinition | LuaItemStack`. `ItemStackDefinition` = `{name, count? (default 1), quality? (default "normal"), ammo?: float, durability?, health?, spoil_percent?, tags?, custom_description?}`. The string form means a **full stack** (example: `"iron-plate"` = `{name="iron-plate", count=100}`).
- Real 2.0 usage: `turret.insert({name = "firearm-magazine", quality = "legendary", count = 200})` and `furnace.insert({name = "iron-ore", count = 100})` (D: space-age/prototypes/tips-and-tricks-simulations.lua:141,146).
- Fluids: `LuaEntity.insert_fluid(fluid: Fluid) -> double` ("Fluidbox is chosen automatically"), `remove_fluid{name, amount, minimum_temperature?, maximum_temperature?, temperature?} -> double`, `get_fluid(index) -> Fluid?`, `set_fluid(index, fluid?) -> Fluid?`, `fluids_count`, `get_fluid_contents()`, `clear_fluid_inside()`. `Fluid` = `{amount: double, name: string, temperature?: float}`. An assembler "will change its number of fluid boxes depending on its active recipe" (R: class `LuaFluidBox`), so set the recipe **before** inserting fluid. Base usage: `tank1.insert_fluid{name = "thruster-fuel", amount = 25000}` (D: space-age/prototypes/tips-and-tricks-simulations.lua:131).

---

## 6. Sources and sinks: infinity chest, infinity pipe, EEI

### 6.1 Infinity chest

- `LuaEntity.set_infinity_container_filter(index: uint32, filter: InfinityInventoryFilter | nil)` (`nil` clears) and `get_infinity_container_filter(index) -> InfinityInventoryFilter?`. `infinity_container_filters` is R/W `array[InfinityInventoryFilter]`. `remove_unfiltered_items` is R/W boolean: "Whether items not included in this infinity container filters should be removed from the container." Subclasses: InfinityContainer, InfinityCargoWagon (R).
- Base usage: `chest_1.set_infinity_container_filter(1, {name = science_1, count = 100, index = 1})` (D: base/prototypes/tips-and-tricks-simulations.lua:1661).
- **Source**: filter `{name=X, count=N, mode="exactly"}`. **Void sink**: no filters plus `remove_unfiltered_items = true` (inferred from the description; **[pilot-check]** the timing of removal). For **counting** throughput use an ordinary chest (`steel-chest`) that the harness reads and `clear()`s on each sample.
- Prototype facts: `gui_mode = "admins"`, `erase_contents_when_mined = true`, `preserve_contents_when_created = true` (D: base/prototypes/entity/entities.lua:9891-9893). P: `InfinityContainerPrototype.preserve_contents_when_created` says: "items created inside the infinity chest will not start to spoil until they have been removed". This matters for spoilable items in Space Age.

### 6.2 Infinity pipe

- `LuaEntity.set_infinity_pipe_filter(filter: InfinityPipeFilter | nil)` and `get_infinity_pipe_filter() -> InfinityPipeFilter?` (R, subclass InfinityPipe). Example: `pipe.set_infinity_pipe_filter{name = "water", percentage = 1, mode = "exactly"}`. The `percentage` field is described as "The fill percentage the pipe (for example 0.5 for 50%)". Use `mode = "remove"` or `"exactly"` with percentage 0 as a fluid sink.

### 6.3 Electric energy interface (test power plant or load)

- R/W `power_production: double`, `power_usage: double` ("specific to the ElectricEnergyInterface entity type"). R/W `electric_buffer_size: double?` (write only on EEI). R/W `energy: double` ("Energy stored in the entity's energy buffer"; the API example prints `.. "J"`, so the unit of `energy` is joules). `get_electric_input_flow_limit(quality?)` and `get_electric_output_flow_limit(quality?)` return `double?`.
- The **units of `power_production` / `power_usage`** (J/tick versus W) are **[not in sources]**. Pilot: create the base EEI and log `power_production`; the prototype says `energy_production = "500GW"` (D: base/prototypes/entity/entities.lua:8560).
- Unit-free way to measure consumption: set `power_production = 0`, set `electric_buffer_size = B` and `energy = B` at `t0`; network draw over the window is `B - energy(t1)` in joules. This works because the base EEI is `usage_priority = "tertiary"` (D: …:8557), i.e. accumulator-like. **[pilot-check]** that `get_electric_output_flow_limit()` does not cap it.
- Power needs a pole: an EEI and a consumer connect through a pole's supply area (P: `ElectricPolePrototype.supply_area_distance`: "The 'radius' of this pole's supply area … If this is 3.5, the pole will have a 7x7 supply area"). One `substation` (supply 9, which gives an 18x18 area) per test cell, created with `auto_connect = false`, gives **one isolated network per cell**. Its statistics then describe only that cell.
- `LuaSurface.create_global_electric_network()`, `destroy_global_electric_network()`, `has_global_electric_network` and `global_electric_network_statistics` exist (added in 2.0.7, D: changelog.txt:3550-3551; the statistics in 2.0.48, :850). What exactly joins such a network is **[not in sources]**, so use poles.
- `LuaEntity.is_connected_to_electric_network() -> boolean` ("connected to an electric network that has at least one entity that can produce power") and `electric_network_id: uint32?` are the assertions to use after setup.

---

## 7. Reading machines

| Member | Type | Meaning (R) |
|---|---|---|
| `products_finished` | uint32 R/W | "The number of products this machine finished crafting in its lifetime." Subclass CraftingMachine. Whether it counts **crafts or product items** for multi-product recipes is **[not in sources]**; cross-check against the output inventory. |
| `crafting_progress` | float R/W | `[0,1]` |
| `is_crafting()` | boolean | "whether a crafting process has been started", not whether it is progressing |
| `crafting_speed` | double RO | "current crafting speed, including speed bonuses from modules and beacons" |
| `speed_bonus`, `productivity_bonus`, `consumption_bonus` | double RO | including force bonuses and modules |
| `get_recipe()` | `LuaRecipe?, LuaQualityPrototype?` | CraftingMachine |
| `set_recipe(recipe?, quality?)` | returns `array[ItemWithQualityCount]` ("Any items removed … as a result of setting the recipe") | AssemblingMachine only |
| `recipe_locked` | boolean R/W | AssemblingMachine |
| `previous_recipe` | `RecipeIDAndQualityIDPair?` RO | Furnace |
| `result_quality` | R `LuaQualityPrototype?` / W `QualityID` | nil when not crafting |
| `status` | `defines.entity_status?` RO | "always the actual status … even if custom_status is set" |
| `energy` | double R/W | buffer, J (see §6.3) |
| `burner` | `LuaBurner?` | burner energy source |
| `mining_target` | `LuaEntity?` RO | MiningDrill |
| `mining_progress` | double? R/W | "a number in range [0, mining_target.prototype.mineable_properties.mining_time]" |
| `bonus_mining_progress` | double? R/W | the productivity part, same range |
| `mining_area` | BoundingBox RO | MiningDrill |
| `drop_position` | MapPosition | where drills, crafters with a drop target and inserters put items; read it to place the sink chest |
| `amount` / `initial_amount` | uint32 | ResourceEntity |
| `health` / `max_health` / `get_health_ratio()` | float | EntityWithHealth |
| `destructible` | boolean R/W | "If set to false, this entity can't be damaged and won't be attacked automatically." |
| `kills`, `damage_dealt` | uint32 / double R/W | Turret: "The number of units killed by this turret", "The damage dealt by this turret". Whether damage is counted before or after resistances is **[not in sources]**. |
| `shooting_target` | `LuaEntity?` | Turret |
| `energy_generated_last_tick` | double RO | Generator |
| `quality` | `LuaQualityPrototype` | "Not all entities support quality and will give the normal quality back" |
| `electric_network_statistics` | LuaFlowStatistics | **ElectricPole** only |

Status codes a harness should map (R-define `entity_status`, each with its docs note): `working`, `normal`, `no_power`, `low_power`, `no_fuel`, `no_recipe` (assemblers), `recipe_not_researched` (assemblers), `no_ingredients` (furnaces), `item_ingredient_shortage`, `fluid_ingredient_shortage`, `full_output`, `waiting_for_space_in_destination` (inserters, drills, crafters with `vector_to_place_result`), `no_minable_resources` (drills), `missing_required_fluid` (drills), `no_ammo` (ammo turrets), `disabled_by_script`, `disabled_by_control_behavior`, `frozen`, `waiting_for_source_items` (inserters), `not_plugged_in_electric_network` (generators, solar), `charging`/`discharging`/`fully_charged` (accumulators).

Consequence: an assembler whose recipe is not enabled for its force reports `recipe_not_researched`. The harness therefore enables the mod's recipes (`force.recipes[name].enabled = true`, R: `LuaRecipe.enabled` R/W) or researches the technology.

Formulas that are documented (use them as the expected values):

- Crafting: "crafting_speed … 1 means that for example a 1 second long recipe take 1 second to craft. 0.5 means it takes 2 seconds" (P: `CraftingMachinePrototype.crafting_speed`). "energy_required … Equals the number of seconds it takes to craft at crafting speed 1" (P: `RecipePrototype.energy_required`). At runtime, `LuaRecipePrototype.energy` is "exactly its crafting time in seconds, when crafted in an assembling machine with crafting speed exactly equal to one" (R). So **crafts/s = crafting_speed / energy**, and crafting_progress grows by `crafting_speed / (energy*60)` per tick (the per-tick form assumes 60 ticks/s, R: `LuaGameScript.speed`: "1.0 is normal speed -- 60 UPS").
- Belts: "`speed × 480 = x Items/second` … `x items/second ÷ (4 items/lane × 2 lanes/belt × 60 ticks/second)`" (P: `TransportBeltConnectablePrototype.speed`).
- Mining: `mining_speed` is only "The speed of this drill" (P: `MiningDrillPrototype.mining_speed`). The rate formula is **[not in sources]**. Measure `mining_progress` increments per tick and compare them with `mining_speed/60` as a hypothesis. A resource's `mining_time` comes from `prototypes.entity[ore].mineable_properties.mining_time` (R-concept `MineableProperties`).
- Mining area: "resource_searching_radius … 2.49 for electric mining drills (a 5x5 area) and 0.99 for burner mining drills (a 2x2 area)" (P: `MiningDrillPrototype.resource_searching_radius`). At runtime use `LuaEntityPrototype.get_mining_drill_radius(quality?)`.

---

## 8. Belts and transport lines

- `LuaEntity.get_transport_line(index: defines.transport_line) -> LuaTransportLine` ("Transport lines are 1-indexed") and `get_max_transport_line_index()`. The subclass is TransportBeltConnectable.
- R-define `transport_line`: `left_line, right_line, left_underground_line, right_underground_line, secondary_left_line, secondary_right_line, left_split_line, right_split_line, secondary_left_split_line, secondary_right_split_line`.
- LuaTransportLine: `get_item_count(item?: ItemFilter) -> uint32`, `get_contents() -> array[ItemWithQualityCount]`, `get_detailed_contents() -> array[DetailedItemOnLine{position: float, stack: LuaItemStack, unique_id: uint32}]`, `can_insert_at_back() -> boolean`, `insert_at_back(items, belt_stack_size?: uint8) -> boolean`, `can_insert_at(position: float)`, `insert_at(position, items, belt_stack_size?)`, `force_insert_at`, `remove_item(items) -> uint32`, `clear()`, `line_length: float` ("Items can be inserted at line position from 0 up to returned value"), `total_segment_length`, `input_lines`, `output_lines`, `owner`.
- Throughput method with no loaders:
  1. Every tick, `insert_at_back` on both lines of the **first** belt whenever `can_insert_at_back()` is true.
  2. Every tick, on the **last** belt, add `get_item_count()` of both lines to a counter and `clear()` them.

  The result is items/s = counter / seconds, and the expected value is `speed × 480` (P). The belt-stacking bonus (`LuaForce.belt_stack_size_bonus`, uint32 R/W) and the `belt_stack_size` argument of `insert_at_back` change the item count per slot. Keep both at their defaults for the base comparison.
- Loader alternative: base loaders top out at express speed (0.09375) and SA `turbo-loader` at 0.125 (§3). They **cannot saturate a belt faster than turbo**. If the Magnetics belt is faster, the harness mod can define its own loader in its `data.lua` (see §13.3) or use the method above.
- A belt mod also needs underground belts. `underground-belt` pairs are created with `type = "input"`/`"output"`, and their lines include `left_underground_line`/`right_underground_line` (R-define). `LuaEntityPrototype.max_underground_distance` (uint8) gives the reach.

---

## 9. Inserters

- Read after creation: `pickup_position`, `drop_position`, `pickup_target`, `drop_target` (writable when several entities overlap the point), `held_stack: LuaItemStack`, `inserter_stack_size_override` (uint32 R/W, `0` resets), `status` (`waiting_for_source_items`, `waiting_for_space_in_destination`, …).
- Prototype speeds: `get_inserter_extension_speed(quality?) -> double?` and `get_inserter_rotation_speed(quality?) -> double?`. Base `inserter` has `extension_speed = 0.035`, `rotation_speed = 0.014`, `energy_per_movement = "5kJ"`, `energy_per_rotation = "5kJ"` (D: base/prototypes/entity/entities.lua:2299, 2307-2308). The swings/s formula is **[not in sources]**, so measure it (items moved into the sink chest per window).
- Force bonuses: `inserter_stack_size_bonus` (double, "for non stack inserters") and `bulk_inserter_capacity_bonus` (uint32, 0..254). P: `InserterPrototype.bulk` and `uses_inserter_stack_size_bonus` decide which bonus applies.

---

## 10. Units (biters), turrets, walls

### 10.1 Keeping biters in place

- `unit.commandable -> LuaCommandable?` ("Units and SpiderUnits are commandable", R: `LuaEntity.commandable`).
- `LuaCommandable.set_command(command: Command)`, `set_distraction_command(command)`, `release_from_spawner()`, plus `has_command`, `command`, `moving_state`.
- R-concept `Command` variants:
  - `defines.command.stop` takes `{distraction?: defines.distraction (default by_enemy), ticks_to_wait?: MapTick ("Default is max uint64, which means stop forever")}`.
  - `wander` takes `{distraction?, radius? (default 10), ticks_to_wait?, wander_in_group?}`.
  - `attack` takes `{target: LuaEntity, distraction?}`.
  - `attack_area` takes `{destination, radius, distraction?}`.
  - `go_to_location` takes `{destination?, destination_entity?, distraction?, pathfind_flags?, radius? (default 3)}`.
  - The others are `flee`, `group`, `build_base` and `compound`.
- R-define `distraction`: `none` ("Perform command even if someone attacks the unit"), `by_enemy`, `by_damage`, `by_anything`.
- `unit.ai_settings -> LuaAISettings` has R/W `allow_destroy_when_commands_fail` ("units that repeatedly fail to succeed at commands will be destroyed"), `allow_try_return_to_spawner`, `do_separation`, `join_attacks`, `path_resolution_modifier` and `size_in_group`. Base biters are created with `{ destroy_when_commands_fail = true, allow_try_return_to_spawner = true }` (D: base/prototypes/entity/biter-ai-settings.lua:1, assigned as `ai_settings = biter_ai_settings` in D: base/prototypes/entity/enemies.lua:75, 313, 372, 432, …). **Script-spawned targets must have both turned off**, or they may be destroyed or wander off. `game.map_settings.max_failed_behavior_count`: "If a behavior fails this many times, the enemy (or enemy group) is destroyed." (R-concept `MapSettings`; the default is 3 at D: base/prototypes/map-settings.lua:229).
- `unit.speed` is R/W for units ("the maximum speed if this is a unit … tiles per tick"). Setting it to 0 is another way to pin a target. Base sets `biter.speed = 0.05` (D: base/prototypes/tips-and-tricks-simulations.lua:4528).
- `unit.disabled_by_script = true` stops the unit's update ("Deactivating an entity will stop all its operations", R: `LuaEntity.active`). Whether turrets still target a disabled unit is **[not in sources]**, so prefer the `stop` + `none` command and check with `unit.position` drift in the pilot.
- Base attack command, verbatim (D: base/prototypes/tips-and-tricks-simulations.lua:4527-4533):

```lua
      biter = game.surfaces[1].create_entity{name = "medium-biter", position = {12 + (math.random() * 2), -4 + (math.random() * 4)}}
      biter.speed = 0.05
      biter.commandable.set_command
      {
        type = defines.command.attack,
        target = player.character
      }
```

- Force-level controls:
  - `LuaForce.set_cease_fire(other, bool)`: "Forces on the cease fire list won't be targeted for attack".
  - `set_friend(other, bool)`.
  - `ai_controllable` (R/W): "Setting this to false does not turn off biters' AI. They will still move around and attack players who come close."
  - `kill_all_units()`.
  - `set_evolution_factor(factor, surface?)`.
  - `game.map_settings.pollution.enabled = false` and `game.map_settings.enemy_expansion.enabled = false` are used in D: base/script/wave-defense/wave_defense.lua:1316-1317. `enemy_evolution.enabled` exists in R-concept `EnemyEvolutionMapSettings`.
- Healing: biters regenerate (`healing_per_tick = 0.01` for small-biter, D: base/prototypes/entity/enemies.lua:44; `0.02` at :127 for the next tier). Account for it or use `damage_dealt` instead of the health delta.

### 10.2 Turrets and ammo

- An ammo turret has **1 ammo slot** in base (`inventory_size = 1`, D: base/prototypes/entity/turrets.lua:476). Top up with `turret.insert{name=ammo, count=n}` or `turret.get_inventory(defines.inventory.turret_ammo).insert{...}` on each sample tick. Rounds left in the current magazine: `inv[1].ammo` (R: `LuaItemCommon.ammo`, "Number of bullets left in the magazine"; LuaItemStack inherits LuaItemCommon). Magazine size: `prototypes.item[ammo].magazine_size`.
- Electric turret: it needs power (laser-turret `buffer_capacity = "801kJ"`, `input_flow_limit = "9600kW"`, `drain = "24kW"`, D: base/prototypes/entity/turrets.lua:617-619). `turret.energy` is R/W, so you can pre-charge it.
- Fluid turret: `insert_fluid{name=..., amount=...}` or an infinity pipe.
- Measuring: `turret.damage_dealt` and `turret.kills` deltas per window. `shooting_target`. Status `no_ammo`.
- Expected-value inputs: `prototypes.entity[t].attack_parameters` (R-concept `AttackParameters{range, cooldown, damage_modifier, ammo_categories?, ammo_type?, min_range, turn_range, warmup, …}`) and `turret_range`; `prototypes.item[a].get_ammo_type("turret") -> AmmoType{action?, consumption_modifier?, cooldown_modifier?, range_modifier?, target_type, …}`; the force modifiers `get_ammo_damage_modifier(category)`, `get_gun_speed_modifier(category)` and `get_turret_attack_modifier(turret)` (setters exist too).
- Set `turret.destructible = false` so that an isolated DPS test cannot lose the turret.

### 10.3 Walls and resistances (deterministic)

- `LuaEntity.damage(damage: float, force: ForceID, type?: DamageTypeID ("defaults to impact"), source?, cause?) -> float`. The return is "the total damage actually applied after resistances". It raises `on_entity_damaged`.
- `prototypes.entity[w].resistances -> dictionary[string -> Resistance{decrease: float, percent: float}]` and `get_max_health(quality?)`.
- The protocol: create the wall, call `damage(D, "enemy", "physical")`, record the applied damage and `health`, `destroy()`. Repeat for each damage type. `die(force?, cause?)` fires `on_entity_died`; `destroy{...}` does not.

---

## 11. Research and force bonuses

- `force.technologies[name]` is a `LuaCustomTable[string -> LuaTechnology]`. Example in the API: `game.player.force.technologies["steel-processing"].researched = true`.
- `LuaTechnology.researched` (R/W): switching to true applies the perks; switching back reverses them. `research_recursive()` researches the technology and all its prerequisites. Also `enabled` (R/W), `level` (R/W; "writing to this is the same as researching the technology to the previous level"), `research_unit_count` (already multiplied by the cost multiplier unless `ignore_tech_cost_multiplier`), `research_unit_ingredients`, `research_unit_energy`, `saved_progress`.
- `LuaForce.research_all_technologies(include_disabled_prototypes?)` raises `on_research_finished`. `enable_all_technologies()`, `enable_all_recipes()`, `reset_technology_effects()`, `add_research(tech) -> boolean`, `research_queue`, `research_progress`, `laboratory_speed_modifier`.
- Base usage: `game.forces.player.technologies[name].researched = true` over the prerequisites, then `add_research(technology)` (D: base/prototypes/tips-and-tricks-simulations.lua:1669-1674). Iterating LuaCustomTables with `pairs` also appears there (`for k, tech in pairs (technologies)`, :1646).
- Bonuses to read or set directly: `mining_drill_productivity_bonus`, `belt_stack_size_bonus`, `inserter_stack_size_bonus`, `bulk_inserter_capacity_bonus`, `laboratory_speed_modifier`, and the ammo, gun and turret modifiers above. `LuaRecipe.productivity_bonus` is R/W per force recipe.
- The technology effect kinds a Magnetics tech might use are all listed in R-concept `TechnologyModifier`, e.g. `unlock-recipe{recipe}`, `turret-attack{turret_id, modifier}`, `ammo-damage{ammo_category, modifier}`, `gun-speed{…}`, `mining-drill-productivity-bonus{modifier}`, `belt-stack-size-bonus{modifier}`, `change-recipe-productivity{recipe, change}`.
- Space Age changes the tree: some techs use `research_trigger` instead of `unit` (R: `LuaTechnologyPrototype.research_trigger`; e.g. `recycling` in D: space-age/base-data-updates.lua:922-925). `research_recursive()` / `researched = true` cover both kinds.

---

## 12. Statistics

- 2.0 statistics are per surface: `LuaForce.get_item_production_statistics(surface)`, `get_fluid_production_statistics(surface)`, `get_kill_count_statistics(surface)` and `get_entity_build_count_statistics(surface)`, each returning `LuaFlowStatistics`. The argument is positional (`SurfaceIdentification = uint32 | string | LuaSurface`).
- Meaning of input and output (R: class `LuaFlowStatistics`):
  - item and fluid statistics: **input = production, output = consumption**;
  - kills: output = the force's own losses;
  - electric: "input describes the power consumption", output = production, storage = accumulator charge.
- Methods: `get_input_count(id: FlowStatisticsID) -> uint64 | double`, `get_output_count(id)`, `get_storage_count(id)`, `get_flow_count{name, category: "input"|"output"|"storage", precision_index: defines.flow_precision_index, sample_index?: uint16 (1..300, 1 = newest), count?: boolean} -> double` (**takes a table**), `clear()`, `on_flow(id, count)`. Attributes: `input_counts`, `output_counts` and `storage_counts` are `dictionary[string -> uint64 | double]` "indexed by prototype name".
- `get_flow_count` note: "All return values are normalized to be per-tick for electric networks and per-minute for all other types." Each precision level holds 300 samples. R-define `flow_precision_index`: `five_seconds, one_minute, ten_minutes, one_hour, ten_hours, fifty_hours, two_hundred_fifty_hours, one_thousand_hours`.
- `FlowStatisticsID` = `ItemWithQualityID | FluidID | EntityWithQualityID | EntityID`, so quality can be passed as `{name=..., quality=...}` (R-concept `ItemIDAndQualityIDPair`). Whether a bare name sums over qualities is **[not in sources]**.
- Electric statistics: `pole.electric_network_statistics` (ElectricPole only) and `surface.global_electric_network_statistics` (optional). Counts are keyed by entity prototype name. The **energy unit** of the cumulative counts is **[not in sources]**; calibrate with the EEI-buffer method (§6.3).
- Pollution statistics are also available: `LuaSurface.pollution_statistics` (D: changelog.txt:849) and `game.get_pollution_statistics`.

---

## 13. Prototype introspection (`prototypes.*`) — verifying the mod's numbers

- The global `prototypes` is a `LuaPrototypes` ("Allows read-only access to prototypes", R: global_objects). Attributes: `item`, `entity`, `recipe`, `technology`, `fluid`, `tile`, `quality`, `surface_property`, … each a `LuaCustomTable[string -> Lua*Prototype]` "indexed by name". Filtered getters exist: `get_entity_filtered(filters)`, `get_recipe_filtered`, `get_item_filtered`, `get_technology_filtered`.
- LuaPrototypeBase (inherited by all): `name, type, hidden, order, subgroup, group, localised_name, …`.
- **LuaEntityPrototype**. Many members are subclass-restricted; wrap reads in `pcall`, which base code also uses (D: base/script/pvp/balance.lua:93).
  - Quality-aware methods: `get_crafting_speed(quality?)`, `get_max_energy_usage(quality?)`, `get_max_energy_production(quality?)`, `get_max_health(quality?)`, `get_inventory_size(index, quality?)`, `get_mining_drill_radius(quality?)`, `get_inserter_extension_speed(quality?)`, `get_inserter_rotation_speed(quality?)`, `get_supply_area_distance(quality?)`, `get_max_wire_distance(quality?)`, `get_max_power_output(quality?)`, `get_researching_speed(quality?)`, `get_fluid_usage_per_tick(quality?)`, `get_pumping_speed(quality?)`, `has_flag(flag)`.
  - Attributes: `energy_usage: double?` ("direct energy usage"), `mining_speed`, `belt_speed`, `electric_energy_source_prototype: LuaElectricEnergySourcePrototype?` (`buffer_capacity`, `drain`, `usage_priority`, `emissions_per_joule`, `get_input_flow_limit(q?)`, `get_output_flow_limit(q?)`), `burner_prototype`, `attack_parameters: AttackParameters?`, `resistances`, `crafting_categories`, `ingredient_count`, `module_inventory_size`, `allowed_effects`, `effect_receiver`, `resource_categories`, `resource_drain_rate_percent`, `vector_to_place_result`, `turret_range`, `automated_ammo_count`, `guns`, `indexed_guns`, `mineable_properties`, `max_underground_distance`, `surface_conditions: array[SurfaceCondition{property, min, max}]?`, `crafting_speed_quality_multiplier`, `energy_usage_quality_multiplier`, `emissions_per_second`, `heating_energy`, `speed` (units), `tile_width`, `tile_height`, `collision_box`, `supports_direction`, `fixed_recipe`, `next_upgrade`, `items_to_place_this`.
  - There are **no** attributes `max_health`, `max_energy_usage`, `inserter_rotation_speed` or `supply_area_distance` on the prototype; they became the quality-aware getters above. `max_power_output` still exists but is "deprecated in favor of get_max_power_output".
- **Units** of `energy_usage`, `get_max_energy_usage`, `drain`, `buffer_capacity` and `research_unit_energy` are **[not in sources]**. Calibrate against the Lua values: `assembling-machine-1` `energy_usage = "75kW"` (D: base/prototypes/entity/entities.lua:3195); `electric-mining-drill` `"90kW"`. A runtime `energy_usage` of `1250` would mean J/tick.
- **LuaRecipePrototype**: `ingredients: array[Ingredient{type, name, amount: double, ignored_by_stats?, (fluid: temperature/min/max, fluidbox_index?, fluidbox_multiplier?)}]`, `products: array[ItemProduct | FluidProduct]` (ItemProduct = `{type="item", name, amount?, amount_min?, amount_max?, probability, extra_count_fraction?, ignored_by_productivity?, ignored_by_stats?, percent_spoiled?}`), `energy` (seconds at speed 1), `category`, `additional_categories`, `enabled` (enabled at game start), `main_product`, `maximum_productivity`, `allowed_effects`, `surface_conditions`, `hidden`.
- **LuaTechnologyPrototype**: `prerequisites: dictionary[string -> LuaTechnologyPrototype]`, `effects: array[TechnologyModifier]`, `research_unit_count`, `research_unit_count_formula`, `research_unit_ingredients: array[ResearchIngredient{name, amount}]`, `research_unit_energy`, `research_trigger`, `max_level`, `level`, `enabled`, `upgrade`, `ignore_tech_cost_multiplier`, `essential`, `successors`. The prototype-side meaning: "TechnologyUnit.time … In a lab with a crafting speed of 1, it corresponds to the number of seconds" (P).
- **LuaItemPrototype**: `stack_size`, `magazine_size`, `get_ammo_type(source?)`, `ammo_category`, `fuel_value`, `fuel_category`, `place_result`, `weight`, `get_spoil_ticks(quality?)`.
- Feature detection: `script.active_mods` (`dictionary[name -> version]`) and `script.feature_flags` (`{expansion_shaders, freezing, quality, rail_bridges, segmented_units, space_travel, spoiling}`). Space Age's info.json requires `quality_required`, `space_travel_required`, `spoiling_required` and `freezing_required` (D: space-age/info.json). `helpers.game_version` gives the game version.

### 13.3 Optional `data.lua` in the harness mod (a test loader matching the Magnetics belt speed)

It copies a base loader using the same `table.deepcopy` that base uses (D: core/lualib/util.lua:6,39; `require ("util")` at the top of D: base/prototypes/entity/entities.lua:1):

```lua
-- magnetics-harness/data.lua (optional)
require("util")
local belt = data.raw["transport-belt"]["<magnetics-belt-name>"]   -- fill in
if belt then
  local l = table.deepcopy(data.raw["loader-1x1"]["loader-1x1"])  -- D: base/prototypes/entity/transport-belts.lua:1026
  l.name = "mh-loader-1x1"
  l.speed = belt.speed
  data:extend({l})
end
```

This is a data-stage snippet; the loader's `type` field (`"input"`/`"output"`) is set at `create_entity`. Which side of a loader faces the container at a given `direction` is **[not in sources]**, so check in the pilot with `loader_type` / `LuaEntity.loader_type` (R/W, Loader).

---

## 14. Output: `helpers.write_file` and JSON

- `helpers.write_file(filename: string, data: LocalisedString, append?: boolean, for_player?: uint32)`. Output goes to `script-output` in the user data directory; "Providing a directory path (ex. save/here/example.txt) will create the necessary folder structure"; `append` defaults to false (overwrite). `helpers.remove_path(path)` deletes inside `script-output`.
- `helpers.table_to_json(data: table) -> string` and `helpers.json_to_table(json: string) -> AnyBasic?`. How it handles NaN/inf, mixed keys and LuaObjects is **[not in sources]**. Pass only plain tables of numbers, strings and booleans. **Never** pass LuaEntity or LuaCustomTable. Convert `input_counts` dictionaries into plain tables first (they are plain `dictionary` per R, but copying is safe).
- `log(LocalisedString)` writes to factorio-current.log, and `localised_print(LocalisedString)` writes to stdout (R: global_functions). stdout is handy for the runner script.
- Whether `write_file` works inside `--benchmark` is **[not in sources]**. Dry-run it first.
- Write partial results on every sample (append a JSONL line) and a final `results.json` when the window closes. The benchmark may stop before the window ends if `--benchmark-ticks` is too small (the default is 1000 ticks, BIN).

---

## 15. Skeleton harness mod

### 15.1 `magnetics-harness/info.json`

The dependency syntax is copied from D: space-age/info.json (`"base >= 2.0.0"`); the optional-dependency prefix syntax is **[not in sources]**.

```json
{
  "name": "magnetics-harness",
  "version": "0.1.0",
  "title": "Magnetics headless test harness",
  "author": "tests",
  "factorio_version": "2.0",
  "dependencies": ["base >= 2.0.0", "magnetics"]
}
```

### 15.2 `magnetics-harness/control.lua`

Every API call below is listed in §§1–14 with its source. Lines marked `PILOT` depend on a **[not in sources]** fact.

```lua
-- magnetics-harness/control.lua  (Factorio 2.0.77)
-- Run:  factorio --create save.zip ...           -> on_init builds the lab (saved into save.zip)
--       factorio --benchmark save.zip --benchmark-ticks N   -> on_tick / on_nth_tick measure, write JSON
-- Output: <write-data>/script-output/magnetics-harness/   (PILOT: write-data = /opt/factorio per config-path.cfg)

local PREFIX = "magnetic"            -- prototype-name prefix of the mod under test (fill in)
local CFG = {
  surface = "mh-lab",
  out     = "magnetics-harness/",
  force   = "player",
  warmup  = 600,                     -- ticks before the window opens
  window  = 3600,                    -- window length in ticks  (--benchmark-ticks must exceed warmup+window)
  sample  = 60,                      -- top-up / sampling period in ticks
  pitch   = 48,                      -- tiles between cells (> substation wire reach 18 → separate networks)
}

---------------------------------------------------------------- utils
local function jwrite(name, t)  helpers.write_file(CFG.out .. name, helpers.table_to_json(t), false) end
local function jappend(name, t) helpers.write_file(CFG.out .. name, helpers.table_to_json(t) .. "\n", true) end

local function try(f) local ok, v = pcall(f) if ok then return v end return nil end

local STATUS = {}                    -- PILOT: assumes defines tables iterate with pairs
for k, v in pairs(defines.entity_status) do STATUS[v] = k end
local function sname(code) if code == nil then return nil end return STATUS[code] or code end

local function center(name, x, y)    -- x,y = top-left tile; R: LuaEntityPrototype.tile_width/tile_height
  local p = prototypes.entity[name]
  return {x = x + p.tile_width / 2, y = y + p.tile_height / 2}
end

local function place(s, spec)        -- R: create_entity default force is "enemy" → always set it
  if spec.force == nil then spec.force = CFG.force end
  spec.create_build_effect_smoke = false
  local e = s.create_entity(spec)
  if not e then error("create_entity failed: " .. spec.name .. " @ " .. spec.position.x .. "," .. spec.position.y) end
  return e
end

---------------------------------------------------------------- lab surface
local function make_surface()
  local s = game.get_surface(CFG.surface)
  if s then return s end
  local mgs = game.default_map_gen_settings           -- all fields present when read
  mgs.seed = 1
  mgs.width, mgs.height = 1024, 1024
  mgs.default_enable_all_autoplace_controls = false
  mgs.autoplace_controls = {}
  mgs.autoplace_settings = {
    entity     = {treat_missing_as_default = false, settings = {}},
    decorative = {treat_missing_as_default = false, settings = {}},
  }
  mgs.cliff_settings.richness = 0                      -- "0 will result in no cliffs" (map-gen-settings.example.json)
  mgs.peaceful_mode = false
  mgs.no_enemies_mode = false                          -- PILOT: effect on script-created units undocumented
  s = game.create_surface(CFG.surface, mgs)
  s.generate_with_lab_tiles = true                     -- before any chunk is generated
  s.always_day = true
  s.request_to_generate_chunks({x = 0, y = 0}, 10)     -- radius in chunks
  s.force_generate_chunk_requests()                    -- must precede create_entity (wave_defense.lua:303)
  return s
end

---------------------------------------------------------------- building blocks
local function power(s, x, y)        -- isolated network: EEI (500GW, 10GJ tertiary) + substation (supply 9)
  local eei  = place(s, {name = "electric-energy-interface", position = {x = x, y = y}})
  local pole = place(s, {name = "substation", position = {x = x + 3, y = y}, auto_connect = false})
  return eei, pole
end

local function cell_crafter(s, cx, cy, machine, recipe, feed)
  local eei, pole = power(s, cx - 8, cy)
  local m = place(s, {name = machine, position = center(machine, cx, cy), recipe = recipe}) -- recipe only for assemblers
  return {kind = "crafter", e = m, eei = eei, pole = pole, recipe = recipe, feed = feed, out = 0}
end

local function top_up_crafter(c)
  local m = c.e
  if not m.valid then return end
  local inv = m.get_inventory(defines.inventory.crafter_input)
  if c.recipe then
    for _, ing in pairs(prototypes.recipe[c.recipe].ingredients) do
      if ing.type == "item" then
        local want = math.ceil(ing.amount) * 5
        local have = inv.get_item_count(ing.name)
        if have < want then inv.insert({name = ing.name, count = want - have}) end
      else
        m.insert_fluid({name = ing.name, amount = ing.amount * 5})
      end
    end
  elseif c.feed then                                    -- furnace: recipe follows the input
    local have = inv.get_item_count(c.feed)
    if have < 20 then inv.insert({name = c.feed, count = 50 - have}) end
  end
  local fuel = m.get_fuel_inventory()                   -- nil for electric machines
  if fuel and fuel.get_item_count("coal") < 5 then fuel.insert({name = "coal", count = 20}) end
  local out = m.get_inventory(defines.inventory.crafter_output)
  c.out = c.out + out.get_item_count()
  out.clear()
end

local function cell_drill(s, cx, cy, drill, ore)
  local eei, pole
  if prototypes.entity[drill].electric_energy_source_prototype then eei, pole = power(s, cx - 10, cy) end
  local pos = center(drill, cx, cy)
  local r = math.ceil(prototypes.entity[drill].get_mining_drill_radius())
  for dx = -r, r do for dy = -r, r do
    place(s, {name = ore, position = {x = math.floor(pos.x) + dx + 0.5, y = math.floor(pos.y) + dy + 0.5},
              amount = 1000000, force = "neutral"})
  end end
  local d = place(s, {name = drill, position = pos, direction = defines.direction.north})
  local chest = place(s, {name = "steel-chest", position = d.drop_position})   -- R: LuaEntity.drop_position
  return {kind = "drill", e = d, chest = chest, pole = pole, eei = eei, out = 0, prog = {}}
end

local function cell_belt(s, cx, cy, belt, len, item)
  local b = {}
  for i = 0, len - 1 do
    b[#b + 1] = place(s, {name = belt, position = {x = cx + i + 0.5, y = cy + 0.5}, direction = defines.direction.east})
  end
  return {kind = "belt", first = b[1], last = b[#b], item = item, passed = 0}   -- PILOT: east = flow east
end

local LINES = {defines.transport_line.left_line, defines.transport_line.right_line}
local function tick_belt(c)
  for _, li in pairs(LINES) do
    local src = c.first.get_transport_line(li)
    if src.can_insert_at_back() then src.insert_at_back({name = c.item, count = 1}) end
    local dst = c.last.get_transport_line(li)
    local n = dst.get_item_count()
    if n > 0 then c.passed = c.passed + n; dst.clear() end
  end
end

local function cell_inserter(s, cx, cy, ins, item)
  local eei, pole = power(s, cx - 8, cy)
  local src = place(s, {name = "infinity-chest", position = {x = cx + 0.5, y = cy - 0.5},
    infinity_settings = {filters = {{index = 1, name = item, count = 100, mode = "exactly"}}}})
  local i = place(s, {name = ins, position = {x = cx + 0.5, y = cy + 0.5}, direction = defines.direction.north})
  if not (i.pickup_position.y < i.position.y) then i.direction = defines.direction.south end  -- PILOT: semantics
  local dst = place(s, {name = "steel-chest", position = i.drop_position})
  return {kind = "inserter", e = i, src = src, chest = dst, pole = pole, eei = eei, out = 0}
end

local function spawn_target(s, c)
  local u = s.create_entity({name = c.target, position = c.target_pos, force = "enemy"})
  if not u then return end
  u.ai_settings.allow_destroy_when_commands_fail = false   -- base biters: destroy_when_commands_fail = true
  u.ai_settings.allow_try_return_to_spawner = false
  u.commandable.set_command({type = defines.command.stop, distraction = defines.distraction.none})
  storage.unit_cell[u.unit_number] = c.id
end

local function cell_turret(s, cx, cy, turret, ammo, target, dist)
  local eei, pole
  if prototypes.entity[turret].electric_energy_source_prototype then eei, pole = power(s, cx - 8, cy) end
  local t = place(s, {name = turret, position = center(turret, cx, cy)})
  t.destructible = false
  if ammo then t.insert({name = ammo, count = 20}) end
  return {kind = "turret", e = t, ammo = ammo, target = target,
          target_pos = {x = cx + dist, y = cy}, pole = pole, eei = eei}
end

local function probe_wall(s, cx, cy, wall)
  local res = {name = wall, hits = {}}
  for _, dt in pairs({"physical", "impact", "explosion", "fire", "acid", "laser", "electric", "poison"}) do
    if prototypes.damage[dt] then
      local w = place(s, {name = wall, position = {x = cx + 0.5, y = cy + 0.5}})
      local applied = w.damage(100, "enemy", dt)                 -- R: returns damage after resistances
      res.hits[dt] = {applied = applied, health = w.health, max = w.max_health}
      w.destroy()
    end
  end
  return res
end

---------------------------------------------------------------- snapshots
local function snap(c)
  local e = c.e
  local r = {kind = c.kind, name = e and e.valid and e.name or nil, tick = game.tick}
  if e and e.valid then
    r.status = sname(e.status)
    r.energy = e.energy
    if c.kind == "crafter" then
      r.finished = e.products_finished; r.progress = e.crafting_progress; r.speed = e.crafting_speed
      r.out = c.out
    elseif c.kind == "drill" then
      r.out = c.out; r.mining_progress = e.mining_progress; r.bonus = e.bonus_mining_progress
    elseif c.kind == "inserter" then
      r.out = c.out
    elseif c.kind == "turret" then
      r.damage = e.damage_dealt; r.kills = e.kills
    end
  end
  if c.kind == "belt" then r.passed = c.passed end
  if c.pole and c.pole.valid then                                  -- R: electric_network_statistics (pole only)
    local st = c.pole.electric_network_statistics
    local inp, outp = {}, {}
    for k, v in pairs(st.input_counts) do inp[k] = v end
    for k, v in pairs(st.output_counts) do outp[k] = v end
    r.power_in, r.power_out = inp, outp
  end
  if c.eei and c.eei.valid then r.eei_energy = c.eei.energy end
  return r
end

local function drain_chest(c)
  if c.chest and c.chest.valid then
    local inv = c.chest.get_inventory(defines.inventory.chest)
    c.out = c.out + inv.get_item_count()
    inv.clear()
  end
end

---------------------------------------------------------------- setup
local function setup()
  if storage.ready then return end
  storage.cells, storage.unit_cell = {}, {}
  local s = make_surface()
  local force = game.forces[CFG.force]
  game.map_settings.pollution.enabled = false
  game.map_settings.enemy_expansion.enabled = false
  game.map_settings.enemy_evolution.enabled = false

  -- unlock everything the mod adds (recipes); research the mod's techs with prerequisites
  for name, rec in pairs(force.recipes) do
    if string.sub(name, 1, #PREFIX) == PREFIX then rec.enabled = true end
  end
  for name, tech in pairs(force.technologies) do
    if string.sub(name, 1, #PREFIX) == PREFIX then tech.research_recursive() end
  end

  -- layout: one row per kind; fill the lists for the mod under test
  local plan = {
    {"crafter", "assembling-machine-1", "iron-gear-wheel"},     -- baseline sanity cell (base names)
    {"crafter", "stone-furnace", nil, "iron-ore"},
    {"drill",   "electric-mining-drill", "iron-ore"},
    {"belt",    "transport-belt", 40, "iron-plate"},
    {"inserter","inserter", "iron-plate"},
    {"turret",  "gun-turret", "firearm-magazine", "behemoth-biter", 12},
  }
  for _, p in pairs(plan) do                                   -- recipes used by baseline cells
    if p[1] == "crafter" and p[3] and force.recipes[p[3]] then force.recipes[p[3]].enabled = true end
  end
  local x = 0
  for i, p in pairs(plan) do
    local cx, cy, c = x, 0, nil
    if p[1] == "crafter"  then c = cell_crafter(s, cx, cy, p[2], p[3], p[4])
    elseif p[1] == "drill"    then c = cell_drill(s, cx, cy, p[2], p[3])
    elseif p[1] == "belt"     then c = cell_belt(s, cx, cy, p[2], p[3], p[4])
    elseif p[1] == "inserter" then c = cell_inserter(s, cx, cy, p[2], p[3])
    elseif p[1] == "turret"   then c = cell_turret(s, cx, cy, p[2], p[3], p[4], p[5]) end
    c.id = i
    storage.cells[i] = c
    if c.kind == "turret" then spawn_target(s, c) end
    x = x + CFG.pitch
  end

  storage.walls = {probe_wall(s, x, 0, "stone-wall")}
  storage.t0 = game.tick
  storage.w0 = storage.t0 + CFG.warmup
  storage.w1 = storage.w0 + CFG.window
  storage.ready = true

  local props = {}
  for name, _ in pairs(prototypes.surface_property) do props[name] = s.get_property(name) end
  jwrite("meta.json", {game_version = helpers.game_version, mods = script.active_mods,
                       features = script.feature_flags, surface_properties = props,
                       t0 = storage.t0, w0 = storage.w0, w1 = storage.w1})
  jwrite("walls.json", storage.walls)
end

---------------------------------------------------------------- prototype dump (numbers to verify)
local function dump_prototypes()
  local E, R, T = {}, {}, {}
  for name, p in pairs(prototypes.entity) do
    if string.sub(name, 1, #PREFIX) == PREFIX then
      -- many members are subclass-restricted (R: "subclasses"), so every read goes through try()
      local es = try(function() return p.electric_energy_source_prototype end)
      local ap = try(function() return p.attack_parameters end)
      E[name] = {
        type = p.type, max_health = p.get_max_health(), tile = {p.tile_width, p.tile_height},
        energy_usage          = try(function() return p.energy_usage end),
        max_energy_usage      = try(function() return p.get_max_energy_usage() end),
        max_energy_production = try(function() return p.get_max_energy_production() end),
        crafting_speed        = try(function() return p.get_crafting_speed() end),
        mining_speed          = try(function() return p.mining_speed end),
        belt_speed            = try(function() return p.belt_speed end),
        mining_radius         = try(function() return p.get_mining_drill_radius() end),
        drain = es and es.drain, buffer = es and es.buffer_capacity, priority = es and es.usage_priority,
        resistances           = try(function() return p.resistances end),
        attack = ap and {range = ap.range, cooldown = ap.cooldown, damage_modifier = ap.damage_modifier,
                         ammo_categories = ap.ammo_categories, type = ap.type} or nil,
        turret_range          = try(function() return p.turret_range end),
        surface_conditions    = try(function() return p.surface_conditions end),
      }
    end
  end
  for name, r in pairs(prototypes.recipe) do
    if string.sub(name, 1, #PREFIX) == PREFIX then
      R[name] = {category = r.category, energy = r.energy, ingredients = r.ingredients,
                 products = r.products, enabled = r.enabled}
    end
  end
  for name, t in pairs(prototypes.technology) do
    if string.sub(name, 1, #PREFIX) == PREFIX then
      local pre, eff = {}, {}
      for pn, _ in pairs(t.prerequisites) do pre[#pre + 1] = pn end
      for _, e in pairs(t.effects) do eff[#eff + 1] = e end
      T[name] = {prerequisites = pre, effects = eff, count = t.research_unit_count,
                 ingredients = t.research_unit_ingredients, unit_energy = t.research_unit_energy}
    end
  end
  jwrite("prototypes.json", {entities = E, recipes = R, technologies = T})
end

---------------------------------------------------------------- events
script.on_init(function()
  setup()
  dump_prototypes()
end)

script.on_event(defines.events.on_tick, function(e)          -- the only on_tick handler (one per event per mod)
  if not storage.ready then setup() end
  for _, c in pairs(storage.cells) do
    if c.kind == "belt" then tick_belt(c)
    elseif c.kind == "drill" and c.e.valid and e.tick >= storage.w0 and #c.prog < 120 then
      c.prog[#c.prog + 1] = c.e.mining_progress                 -- per-tick progress trace for mining_speed check
    end
  end
end)

script.on_nth_tick(CFG.sample, function(e)
  if not storage.ready or storage.done then return end
  for _, c in pairs(storage.cells) do
    if c.kind == "crafter" then top_up_crafter(c)
    elseif c.kind == "drill" or c.kind == "inserter" then
      drain_chest(c)
      local fuel = c.e.valid and c.e.get_fuel_inventory()        -- burner drills only (nil otherwise)
      if fuel and fuel.get_item_count("coal") < 5 then fuel.insert({name = "coal", count = 20}) end
    elseif c.kind == "turret" and c.ammo and c.e.valid then
      local inv = c.e.get_inventory(defines.inventory.turret_ammo)
      if inv.get_item_count(c.ammo) < 5 then inv.insert({name = c.ammo, count = 10}) end
    end
  end
  local row = {tick = e.tick, cells = {}}
  for i, c in pairs(storage.cells) do row.cells[i] = snap(c) end
  jappend("samples.jsonl", row)
  if e.tick >= storage.w0 and not storage.snap0 then storage.snap0 = row end
  if e.tick >= storage.w1 then
    local res = {w0 = storage.snap0, w1 = row, window_ticks = row.tick - storage.snap0.tick, cells = {}}
    for i, c in pairs(storage.cells) do
      local a, b = storage.snap0.cells[i], row.cells[i]
      local sec = res.window_ticks / 60
      local d = {kind = c.kind, name = b.name, status_end = b.status}
      local function rate(k) if a[k] and b[k] then return (b[k] - a[k]) / sec end return nil end
      if c.kind == "crafter" then d.crafts_per_s = rate("finished"); d.items_out_per_s = rate("out")
      elseif c.kind == "drill" or c.kind == "inserter" then d.items_per_s = rate("out")
      elseif c.kind == "belt" then d.items_per_s = rate("passed")
      elseif c.kind == "turret" then d.dps = rate("damage"); d.kills = b.kills and a.kills and (b.kills - a.kills) end
      if c.kind == "drill" then d.progress_trace = c.prog end
      if a.eei_energy and b.eei_energy then d.eei_energy_delta = b.eei_energy - a.eei_energy end
      res.cells[i] = d
    end
    jwrite("results.json", res)
    storage.done = true
  end
end)

script.on_event(defines.events.on_entity_died, function(e)   -- respawn turret targets
  local ent = e.entity
  if not (ent and ent.valid and ent.unit_number) then return end
  local id = storage.unit_cell and storage.unit_cell[ent.unit_number]
  if id then
    storage.unit_cell[ent.unit_number] = nil
    spawn_target(game.get_surface(CFG.surface), storage.cells[id])
  end
end)
```

Notes on the skeleton:

- `prototypes.damage` is a `LuaPrototypes` attribute (`damage` is in its attribute list; R: `LuaPrototypes`). The base damage types are in `data/base/prototypes/damage-type.lua` (referenced by R: `LuaEntityPrototype.resistances`).
- `storage.cells` holds LuaEntity references. That is allowed (base does it, §1.3), but never pass those tables to `table_to_json`. `snap()` builds plain tables.
- Setup happens in `on_init` (`--create`), so the benchmark starts from a clean, already built lab. The `on_tick` guard re-runs `setup()` only if on_init did not (e.g. the mod was added to an existing save).
- `products_finished` gives crafts; `out` is the actual item count. Report both until the pilot shows how they relate.
- Verification done on this skeleton: it parses (lupa, Lua 5.5 parser; no 5.3+ syntax is used). It also ran for 4600 simulated ticks against a hand-written mock of the API calls it uses (`/tmp/claude-0/-home-user-Neu/5dc61be6-6c38-58c2-939b-4b416832b0f1/scratchpad/recon/harness_work/mock.lua`; the query helper is `harness_work/q.py`). That run proves the control flow (setup → samples → window → `results.json`, the respawn path, no LuaEntity in the JSON) and **nothing** about real game behavior.
- For the EEI-based energy measurement, add at `w0`: `eei.power_production = 0; eei.electric_buffer_size = B; eei.energy = B` (§6.3). The `eei_energy_delta` is then the joules consumed by that cell.

---

## 16. Pilot checklist (every **[not in sources]** item, to settle before registering any test)

1. Where `script-output` is and whether `write_file` works under `--benchmark`: look for `meta.json` after `--create` and `samples.jsonl` after `--benchmark`.
2. Which tick numbers the benchmark runs after `--create` (the first `e.tick` in `samples.jsonl`) and whether `on_init` ran during `--create` (`meta.json` written with `t0`).
3. Lab surface: `count_entities_filtered{surface-wide, type = {"resource","tree","unit","cliff","simple-entity"}}` = 0 at setup; `surface.get_tile(0,0).name` is a lab tile; resources placed on lab tiles are not `nil`.
4. `surface.get_property(p)` for all surface properties on the custom surface, in base-only and Space Age runs; pin the values the tests need with `set_property`.
5. Units: `eei.power_production` right after creation versus `"500GW"`; `prototypes.entity["assembling-machine-1"].energy_usage` versus `"75kW"`; `research_unit_energy` versus the `unit.time` of a known tech.
6. Belt `direction = east` moves items east; inserter pickup and drop positions versus direction; which side of a loader faces the container.
7. Biters with `stop` + `distraction.none` stay put (position drift = 0) while being shot; whether `disabled_by_script` units are still targeted.
8. `products_finished` equals crafts or products, using a multi-product recipe.
9. Mining: `mining_progress` delta per tick versus `mining_speed/60`.
10. `pairs(defines.entity_status)` iterates (otherwise status stays numeric).
11. Whether a bare item name in `get_input_count` counts only `normal` quality or all qualities when the quality mod is enabled.

---

## Appendix A. Exact method signatures (generated from runtime-api.json 2.0.77)

`{…}` means the method takes a single table (`format.takes_table = true`). "(table optional)" means the whole table may be omitted. Otherwise arguments are positional.

- `LuaGameScript.create_surface(name: string, settings?: MapGenSettings) -> LuaSurface`
- `LuaGameScript.get_surface(surface: uint32 | string) -> LuaSurface?`
- `LuaGameScript.get_entity_by_unit_number(unit_number: uint32) -> LuaEntity?`
- `LuaGameScript.create_force(force: string) -> LuaForce`
- `LuaSurface.request_to_generate_chunks(position: MapPosition, radius?: uint32) -> `
- `LuaSurface.force_generate_chunk_requests() -> `
- `LuaSurface.set_tiles(tiles: array[Tile], correct_tiles?: boolean, remove_colliding_entities?: boolean | 'abort_on_collision', remove_colliding_decoratives?: boolean, raise_event?: boolean, player?: PlayerIdentification, undo_index?: uint32) -> `
- `LuaSurface.build_checkerboard(area: BoundingBox) -> `
- `LuaSurface.create_entity({name: EntityID, position: MapPosition, direction?: defines.direction, mirror?: boolean, quality?: QualityID, force?: ForceID, target?: LuaEntity | MapPosition, source?: LuaEntity | MapPosition, cause?: LuaEntity | ForceID, snap_to_grid?: boolean, fast_replace?: boolean, undo_index?: uint32, player?: PlayerIdentification, character?: LuaEntity, spill?: boolean, raise_built?: boolean, create_build_effect_smoke?: boolean, spawn_decorations?: boolean, move_stuck_players?: boolean, item?: LuaItemStack, preserve_ghosts_and_corpses?: boolean, register_plant?: boolean, burner_fuel_inventory?: BlueprintInventoryWithFilters}) -> LuaEntity?`
- `LuaSurface.find_entities_filtered(filter: EntitySearchFilters) -> array[LuaEntity]`
- `LuaSurface.count_entities_filtered(filter: EntitySearchFilters) -> uint32`
- `LuaSurface.find_non_colliding_position(name: EntityID, center: MapPosition, radius: double, precision: double, force_to_tile_center?: boolean) -> MapPosition?`
- `LuaSurface.clear(ignore_characters?: boolean) -> `
- `LuaSurface.create_global_electric_network() -> `
- `LuaSurface.set_property(property: SurfacePropertyID, value: double) -> `
- `LuaSurface.get_property(property: SurfacePropertyID) -> double`
- `LuaSurface.create_unit_group({position: MapPosition, force?: ForceID}) -> LuaCommandable`
- `LuaSurface.find_units({area: BoundingBox, force: ForceID, condition: ForceCondition}) -> array[LuaEntity]`
- `LuaSurface.find_enemy_units(center: MapPosition, radius: double, force?: ForceID) -> array[LuaEntity]`
- `LuaSurface.get_tile(x: int32, y: int32) -> LuaTile`
- `LuaControl.get_inventory(inventory: defines.inventory) -> LuaInventory?`
- `LuaControl.insert(items: ItemStackIdentification) -> uint32`
- `LuaControl.get_item_count(item?: ItemFilter) -> uint32`
- `LuaControl.remove_item(items: ItemStackIdentification) -> uint32`
- `LuaControl.can_insert(items: ItemStackIdentification) -> boolean`
- `LuaControl.teleport(position: MapPosition, surface?: SurfaceIdentification, raise_teleported?: boolean, snap_to_grid?: boolean, build_check_type?: defines.build_check_type) -> boolean`
- `LuaEntity.set_recipe(recipe?: RecipeID, quality?: QualityID) -> array[ItemWithQualityCount]`
- `LuaEntity.get_recipe() -> LuaRecipe?, LuaQualityPrototype?`
- `LuaEntity.set_infinity_container_filter(index: uint32, filter: InfinityInventoryFilter | nil) -> `
- `LuaEntity.get_infinity_container_filter(index: uint32) -> InfinityInventoryFilter?`
- `LuaEntity.set_infinity_pipe_filter(filter: InfinityPipeFilter | nil) -> `
- `LuaEntity.get_infinity_pipe_filter() -> InfinityPipeFilter?`
- `LuaEntity.get_output_inventory() -> LuaInventory?`
- `LuaEntity.get_fuel_inventory() -> LuaInventory?`
- `LuaEntity.get_burnt_result_inventory() -> LuaInventory?`
- `LuaEntity.is_crafting() -> boolean`
- `LuaEntity.destroy({do_cliff_correction?: boolean, raise_destroy?: boolean, player?: PlayerIdentification, undo_index?: uint32} (table optional)) -> boolean`
- `LuaEntity.die(force?: ForceID, cause?: LuaEntity) -> boolean`
- `LuaEntity.damage(damage: float, force: ForceID, type?: DamageTypeID, source?: LuaEntity, cause?: LuaEntity) -> float`
- `LuaEntity.get_transport_line(index: defines.transport_line) -> LuaTransportLine`
- `LuaEntity.get_max_transport_line_index() -> defines.transport_line`
- `LuaEntity.insert_fluid(fluid: Fluid) -> double`
- `LuaEntity.get_fluid(index: uint32) -> Fluid?`
- `LuaEntity.set_fluid(index: uint32, fluid?: Fluid) -> Fluid?`
- `LuaEntity.get_fluid_contents() -> dictionary[string -> FluidAmount]`
- `LuaEntity.clear_fluid_inside() -> `
- `LuaEntity.is_connected_to_electric_network() -> boolean`
- `LuaEntity.get_health_ratio() -> float?`
- `LuaEntity.get_electric_input_flow_limit(quality?: QualityID) -> double?`
- `LuaInventory.insert(items: ItemStackIdentification) -> uint32`
- `LuaInventory.remove(items: ItemStackIdentification) -> uint32`
- `LuaInventory.clear() -> `
- `LuaInventory.get_item_count(item?: ItemWithQualityID) -> uint32`
- `LuaInventory.get_contents() -> array[ItemWithQualityCount]`
- `LuaInventory.is_empty() -> boolean`
- `LuaInventory.get_item_quality_counts(item?: ItemID) -> dictionary[string -> uint32]`
- `LuaTransportLine.get_item_count(item?: ItemFilter) -> uint32`
- `LuaTransportLine.get_contents() -> array[ItemWithQualityCount]`
- `LuaTransportLine.get_detailed_contents() -> array[DetailedItemOnLine]`
- `LuaTransportLine.insert_at_back(items: ItemStackIdentification, belt_stack_size?: uint8) -> boolean`
- `LuaTransportLine.remove_item(items: ItemStackIdentification) -> uint32`
- `LuaTransportLine.clear() -> `
- `LuaFlowStatistics.get_input_count(id: FlowStatisticsID) -> uint64 | double`
- `LuaFlowStatistics.get_output_count(id: FlowStatisticsID) -> uint64 | double`
- `LuaFlowStatistics.get_storage_count(id: FlowStatisticsID) -> uint64 | double`
- `LuaFlowStatistics.get_flow_count({name: FlowStatisticsID, category: string, precision_index: defines.flow_precision_index, sample_index?: uint16, count?: boolean}) -> double`
- `LuaFlowStatistics.clear() -> `
- `LuaFlowStatistics.on_flow(id: FlowStatisticsID, count: float) -> `
- `LuaForce.get_item_production_statistics(surface: SurfaceIdentification) -> LuaFlowStatistics`
- `LuaForce.get_fluid_production_statistics(surface: SurfaceIdentification) -> LuaFlowStatistics`
- `LuaForce.get_kill_count_statistics(surface: SurfaceIdentification) -> LuaFlowStatistics`
- `LuaForce.get_entity_build_count_statistics(surface: SurfaceIdentification) -> LuaFlowStatistics`
- `LuaForce.set_cease_fire(other: ForceID, cease_fire: boolean) -> `
- `LuaForce.set_friend(other: ForceID, friend: boolean) -> `
- `LuaForce.research_all_technologies(include_disabled_prototypes?: boolean) -> `
- `LuaForce.enable_all_technologies() -> `
- `LuaForce.enable_all_recipes() -> `
- `LuaForce.add_research(technology: TechnologyID) -> boolean`
- `LuaForce.get_ammo_damage_modifier(ammo: string) -> double`
- `LuaForce.get_gun_speed_modifier(ammo: string) -> double`
- `LuaForce.get_turret_attack_modifier(turret: EntityID) -> double`
- `LuaForce.set_ammo_damage_modifier(ammo: string, modifier: double) -> `
- `LuaForce.set_turret_attack_modifier(turret: EntityID, modifier: double) -> `
- `LuaForce.set_evolution_factor(factor: double, surface?: SurfaceIdentification) -> `
- `LuaForce.kill_all_units() -> `
- `LuaForce.reset_technology_effects() -> `
- `LuaTechnology.research_recursive() -> `
- `LuaCommandable.set_command(command: Command) -> `
- `LuaCommandable.set_distraction_command(command: Command) -> `
- `LuaCommandable.release_from_spawner() -> `
- `LuaEntityPrototype.get_crafting_speed(quality?: QualityID) -> double`
- `LuaEntityPrototype.get_max_energy_usage(quality?: QualityID) -> double`
- `LuaEntityPrototype.get_max_energy_production(quality?: QualityID) -> double`
- `LuaEntityPrototype.get_max_health(quality?: QualityID) -> float`
- `LuaEntityPrototype.get_inventory_size(index: defines.inventory, quality?: QualityID) -> uint32?`
- `LuaEntityPrototype.get_inserter_extension_speed(quality?: QualityID) -> double?`
- `LuaEntityPrototype.get_inserter_rotation_speed(quality?: QualityID) -> double?`
- `LuaEntityPrototype.get_mining_drill_radius(quality?: QualityID) -> double?`
- `LuaEntityPrototype.get_supply_area_distance(quality?: QualityID) -> double`
- `LuaEntityPrototype.get_max_wire_distance(quality?: QualityID) -> double`
- `LuaEntityPrototype.get_max_power_output(quality?: QualityID) -> double?`
- `LuaEntityPrototype.get_researching_speed(quality?: QualityID) -> double?`
- `LuaEntityPrototype.has_flag(flag: EntityPrototypeFlag) -> boolean`
- `LuaElectricEnergySourcePrototype.get_input_flow_limit(quality?: QualityID) -> double`
- `LuaElectricEnergySourcePrototype.get_output_flow_limit(quality?: QualityID) -> double`
- `LuaItemPrototype.get_ammo_type(ammo_source_type?: 'default' | 'player' | 'turret' | 'vehicle') -> AmmoType?`
- `LuaHelpers.write_file(filename: string, data: LocalisedString, append?: boolean, for_player?: uint32) -> `
- `LuaHelpers.table_to_json(data: table) -> string`
- `LuaHelpers.json_to_table(json: string) -> AnyBasic?`
- `LuaHelpers.remove_path(path: string) -> `
- `LuaHelpers.create_profiler(stopped?: boolean) -> LuaProfiler`
- `LuaHelpers.direction_to_string(direction: defines.direction) -> string`
- `LuaBootstrap.on_init(handler: function() | nil) -> `
- `LuaBootstrap.on_load(handler: function() | nil) -> `
- `LuaBootstrap.on_configuration_changed(handler: function(ConfigurationChangedData) | nil) -> `
- `LuaBootstrap.on_nth_tick(tick: MapTick | array[MapTick] | nil, handler: function(NthTickEventData) | nil) -> `
- `LuaBootstrap.on_event(event: LuaEventType | array[LuaEventType], handler: function(EventData) | nil, filters?: EventFilter) -> `

## Appendix B. Attributes used by the harness (generated from runtime-api.json 2.0.77)

`RO` = read-only; `W T` = writable with type T; `?` = may be nil. Descriptions are the API text, truncated at 230 characters.

| Attribute | Read type | Write | API description |
|---|---|---|---|
| `LuaGameScript.tick` | MapTick | RO | Current map tick. |
| `LuaGameScript.ticks_played` | MapTick | RO | The number of ticks since this game was created using either "new game" or "new game from scenario". Notably, this number progresses even when the game is [tick_paused](runtime:LuaGameScript::tick_paused).  This differs from [LuaG… |
| `LuaGameScript.tick_paused` | boolean | W boolean | If the tick has been paused. This means that entity update has been paused. |
| `LuaGameScript.speed` | float | W float | Speed to update the map at. 1.0 is normal speed -- 60 UPS. Minimum value is 0.01. |
| `LuaGameScript.map_settings` | MapSettings | RO | The currently active set of map settings. Even though this property is marked as read-only, the members of the dictionary that is returned can be modified mid-game.  This does not contain difficulty settings, use [LuaGameScript::d… |
| `LuaGameScript.difficulty_settings` | DifficultySettings | RO | The currently active set of difficulty settings. Even though this property is marked as read-only, the members of the dictionary that is returned can be modified mid-game. |
| `LuaGameScript.forces` | LuaCustomTable[uint32 \| string -> LuaForce] | RO | Get a table of all the forces that currently exist. This sparse table allows you to find forces by indexing it with either their `name` or `index`. Iterating this table with `pairs()` will provide the `name`s as the keys. Iteratin… |
| `LuaGameScript.surfaces` | LuaCustomTable[uint32 \| string -> LuaSurface] | RO | Get a table of all the surfaces that currently exist. This sparse table allows you to find surfaces by indexing it with either their `name` or `index`. Iterating this table with `pairs()` will provide the `name`s as the keys. Iter… |
| `LuaGameScript.planets` | LuaCustomTable[string -> LuaPlanet] | RO |  |
| `LuaSurface.generate_with_lab_tiles` | boolean | W boolean | When set to true, new chunks will be generated with lab tiles, instead of using the surface's map generation settings. |
| `LuaSurface.always_day` | boolean | W boolean | When set to true, the sun will always shine. |
| `LuaSurface.freeze_daytime` | boolean | W boolean | True if daytime is currently frozen. |
| `LuaSurface.daytime` | double | W double | Current time of day, as a number in range `[0, 1)`. |
| `LuaSurface.peaceful_mode` | boolean | W boolean | Is peaceful mode enabled on this surface? |
| `LuaSurface.no_enemies_mode` | boolean | W boolean | Is no-enemies mode enabled on this surface? |
| `LuaSurface.map_gen_settings` | MapGenSettings | W MapGenSettings | The generation settings for this surface. These can be modified after surface generation, but note that this will not retroactively update the surface. To manually regenerate it, [LuaSurface::regenerate_entity](runtime:LuaSurface:… |
| `LuaSurface.ignore_surface_conditions` | boolean | W boolean | If surface condition checks should not be performed on this surface. |
| `LuaSurface.has_global_electric_network` | boolean | RO | Whether this surface currently has a global electric network. |
| `LuaSurface.global_electric_network_statistics` | LuaFlowStatistics? | RO | The global electric network statistics for this surface. |
| `LuaSurface.planet` | LuaPlanet? | RO | The planet associated with this surface, if there is one.  Use [LuaPlanet::associate_surface](runtime:LuaPlanet::associate_surface) to create a new association with a planet. |
| `LuaSurface.index` | uint32 | RO | This surface's index in [LuaGameScript::surfaces](runtime:LuaGameScript::surfaces) (unique ID). It is assigned when a surface is created, and remains so until it is [deleted](runtime:on_surface_deleted). Indexes of deleted surface… |
| `LuaSurface.name` | string | W string | The name of this surface. Names are unique among surfaces.  The default surface can't be renamed. |
| `LuaControl.position` | MapPosition | RO | The current position of the entity. |
| `LuaControl.force` | LuaForce | W ForceID | The force of this entity. Reading will always give a [LuaForce](runtime:LuaForce), but it is possible to assign either [string](runtime:string), [uint8](runtime:uint8) or [LuaForce](runtime:LuaForce) to this attribute to change th… |
| `LuaControl.surface` | LuaSurface | RO | The surface this entity is currently on. |
| `LuaEntity.name` | string | RO | Name of the entity prototype. E.g. "inserter" or "fast-inserter". |
| `LuaEntity.type` | string | RO | The entity prototype type of this entity. |
| `LuaEntity.prototype` | LuaEntityPrototype | RO | The entity prototype of this entity. |
| `LuaEntity.valid` | boolean | RO | Is this object valid? This Lua object holds a reference to an object within the game engine. It is possible that the game-engine object is removed whilst a mod still holds the corresponding Lua object. If that happens, the object … |
| `LuaEntity.unit_number` | uint64? | RO | A unique number identifying this entity for the lifetime of the save. These are allocated sequentially, and not re-used (until overflow).  Only entities inheriting from [EntityWithOwnerPrototype](prototype:EntityWithOwnerPrototype… |
| `LuaEntity.direction` | defines.direction | W defines.direction | The current direction this entity is facing. |
| `LuaEntity.quality` | LuaQualityPrototype | RO | The quality of this entity.  Not all entities support quality and will give the "normal" quality back if they don't. |
| `LuaEntity.health` | float? | W float | The current health of the entity, if any. Health is automatically clamped to be between `0` and max health (inclusive). Entities with a health of `0` can not be attacked.  To get the maximum possible health of this entity, see [Lu… |
| `LuaEntity.max_health` | float | RO | Max health of this entity. |
| `LuaEntity.destructible` | boolean | W boolean | If set to `false`, this entity can't be damaged and won't be attacked automatically. It can however still be mined.  Entities that are indestructible naturally (they have no health, like smoke, resource etc) can't be set to be des… |
| `LuaEntity.active` | boolean | W boolean | Deactivating an entity will stop all its operations (car will stop moving, inserters will stop working, fish will stop moving etc).  Reading from this returns `false` if the entity is deactivated in at least one of the following w… |
| `LuaEntity.disabled_by_script` | boolean | W boolean | If the updatable entity is disabled by script.  Note: Some entities (Corpse, FireFlame, Roboport, RollingStock, dying entities) need to remain active and will ignore writes.  If this entity is not considered [updatable](runtime:Lu… [subclasses: UpdatableEntity] |
| `LuaEntity.frozen` | boolean | RO | Whether the freezable entity is currently frozen.  Always returns `false` if this entity is not considered [freezable](runtime:LuaEntity::is_freezable). [subclasses: FreezableEntity] |
| `LuaEntity.status` | defines.entity_status? | RO | The status of this entity, if any.  This is always the actual status of the entity, even if [LuaEntity::custom_status](runtime:LuaEntity::custom_status) is set. |
| `LuaEntity.custom_status` | CustomEntityStatus? | W CustomEntityStatus | A custom status for this entity that will be displayed in the GUI. |
| `LuaEntity.energy` | double | W double | Energy stored in the entity's energy buffer (energy stored in electrical devices etc.). Always 0 for entities that don't have the concept of energy stored inside. |
| `LuaEntity.electric_buffer_size` | double? | W double | The buffer size for the electric energy source. `nil` if the entity doesn't have an electric energy source.  Write access is limited to the ElectricEnergyInterface type. |
| `LuaEntity.power_production` | double | W double | The power production specific to the ElectricEnergyInterface entity type. [subclasses: ElectricEnergyInterface] |
| `LuaEntity.power_usage` | double | W double | The power usage specific to the ElectricEnergyInterface entity type. [subclasses: ElectricEnergyInterface] |
| `LuaEntity.products_finished` | uint32 | W uint32 | The number of products this machine finished crafting in its lifetime. [subclasses: CraftingMachine] |
| `LuaEntity.crafting_progress` | float | W float | The current crafting progress, as a number in range `[0, 1]`. [subclasses: CraftingMachine] |
| `LuaEntity.crafting_speed` | double | RO | The current crafting speed, including speed bonuses from modules and beacons. [subclasses: CraftingMachine,Character] |
| `LuaEntity.speed_bonus` | double | RO | The speed bonus of this entity.  This includes force based bonuses as well as beacon/module bonuses. |
| `LuaEntity.productivity_bonus` | double | RO | The productivity bonus of this entity.  This includes force based bonuses as well as beacon/module bonuses. |
| `LuaEntity.result_quality` | LuaQualityPrototype? | W QualityID | The quality produced when this crafting machine finishes crafting. `nil` when crafting is not in progress.  Note: Writing `nil` is not allowed. [subclasses: CraftingMachine] |
| `LuaEntity.previous_recipe` | RecipeIDAndQualityIDPair? | RO | The previous recipe this furnace was using, if any. [subclasses: Furnace] |
| `LuaEntity.recipe_locked` | boolean | W boolean | When locked; the recipe in this assembling machine can't be changed by the player. [subclasses: AssemblingMachine] |
| `LuaEntity.mining_target` | LuaEntity? | RO | The mining target, if any. [subclasses: MiningDrill] |
| `LuaEntity.mining_progress` | double? | W double | The mining progress for this mining drill. Is a number in range [0, mining_target.prototype.mineable_properties.mining_time]. `nil` if this isn't a mining drill. |
| `LuaEntity.bonus_mining_progress` | double? | W double | The bonus mining progress for this mining drill. Read yields a number in range [0, mining_target.prototype.mineable_properties.mining_time]. `nil` if this isn't a mining drill. |
| `LuaEntity.mining_area` | BoundingBox | RO | Area in which this mining drill looks for resources to mine. [subclasses: MiningDrill] |
| `LuaEntity.amount` | uint32 | W uint32 | Count of resource units contained. [subclasses: ResourceEntity] |
| `LuaEntity.initial_amount` | uint32? | W uint32 | Count of initial resource units contained. `nil` if this is not an infinite resource.  If this is not an infinite resource, writing will produce an error. [subclasses: ResourceEntity] |
| `LuaEntity.drop_position` | MapPosition | W MapPosition | Position where the entity puts its stuff.  Mining drills and crafting machines can't have their drop position changed; inserters must have `allow_custom_vectors` set to true on their prototype to allow changing the drop position. … |
| `LuaEntity.pickup_position` | MapPosition | W MapPosition | Where the inserter will pick up items from.  Inserters must have `allow_custom_vectors` set to true on their prototype to allow changing the pickup position. [subclasses: Inserter] |
| `LuaEntity.drop_target` | LuaEntity? | W LuaEntity | The entity this entity is putting its items to. If there are multiple possible entities at the drop-off point, writing to this attribute allows a mod to choose which one to drop off items to. The entity needs to collide with the t… |
| `LuaEntity.pickup_target` | LuaEntity? | W LuaEntity | The entity this inserter will attempt to pick up items from. If there are multiple possible entities at the pick-up point, writing to this attribute allows a mod to choose which one to pick up items from. The entity needs to colli… [subclasses: Inserter] |
| `LuaEntity.held_stack` | LuaItemStack | RO | The item stack currently held in an inserter's hand. [subclasses: Inserter] |
| `LuaEntity.inserter_stack_size_override` | uint32 | W uint32 | Sets the stack size limit on this inserter.  Set to `0` to reset. [subclasses: Inserter] |
| `LuaEntity.infinity_container_filters` | array[InfinityInventoryFilter] | W array[InfinityInventoryFilter] | The filters for this infinity container. [subclasses: InfinityContainer,InfinityCargoWagon] |
| `LuaEntity.remove_unfiltered_items` | boolean | W boolean | Whether items not included in this infinity container filters should be removed from the container. [subclasses: InfinityContainer,InfinityCargoWagon] |
| `LuaEntity.electric_network_id` | uint32? | RO | Returns the id of the electric network that this entity is connected to, if any. |
| `LuaEntity.electric_network_statistics` | LuaFlowStatistics | RO | The electric network statistics for this electric pole. [subclasses: ElectricPole] |
| `LuaEntity.shooting_target` | LuaEntity? | W LuaEntity | The shooting target for this turret, if any. Can't be set to `nil` via script. [subclasses: Turret] |
| `LuaEntity.kills` | uint32 | W uint32 | The number of units killed by this turret, artillery turret, or artillery wagon. [subclasses: Turret] |
| `LuaEntity.damage_dealt` | double | W double | The damage dealt by this turret, artillery turret, or artillery wagon. [subclasses: Turret] |
| `LuaEntity.commandable` | LuaCommandable? | RO | Returns a LuaCommandable for this entity or nil if entity is not commandable. Units and SpiderUnits are commandable. |
| `LuaEntity.ai_settings` | LuaAISettings | RO | The ai settings of this unit. [subclasses: Unit,SpiderUnit] |
| `LuaEntity.speed` | float? | W float | The current speed if this is a car, rolling stock, projectile or spidertron, or the maximum speed if this is a unit. The speed is in tiles per tick. `nil` if this is not a car, rolling stock, unit, projectile or spidertron.  Only … |
| `LuaEntity.fluidbox` | LuaFluidBox | RO | Fluidboxes of this entity. |
| `LuaEntity.fluids_count` | uint32 | RO | Returns count of fluid storages. This includes fluid storages provided by fluidboxes but also covers other fluid storages like fluid turret's internal buffer and fluid wagon's fluid since they are not fluidbox and cannot be expose… |
| `LuaEntity.burner` | LuaBurner? | RO | The burner energy source for this entity, if any. |
| `LuaEntity.temperature` | double? | W double | The temperature of this entity's heat energy source. `nil` if this entity does not use a heat energy source. |
| `LuaEntity.belt_to_ground_type` | BeltConnectionType | RO | Whether this underground belt goes into or out of the ground. [subclasses: UndergroundBelt] |
| `LuaEntity.loader_type` | BeltConnectionType | W BeltConnectionType | Whether this loader gets items from or puts item into a container. [subclasses: Loader] |
| `LuaEntity.is_updatable` | boolean | RO | Whether the entity is updatable and considered an UpdatableEntity. |
| `LuaEntity.is_military_target` | boolean | W boolean | Whether this entity is a MilitaryTarget. Can be written to if [LuaEntityPrototype::allow_run_time_change_of_is_military_target](runtime:LuaEntityPrototype::allow_run_time_change_of_is_military_target) returns `true`. |
| `LuaCommandable.has_command` | boolean | RO | If this commandable has a command assigned. |
| `LuaCommandable.command` | Command? | RO | The command of this commandable, if any. |
| `LuaCommandable.is_script_driven` | boolean | RO | Whether this unit group is controlled by a script or by the game engine. This can be changed using [LuaCommandable::set_autonomous](runtime:LuaCommandable::set_autonomous). Units created by [LuaSurface::create_unit_group](runtime:… [subclasses: UnitGroup] |
| `LuaCommandable.moving_state` | defines.moving_state | RO | Current moving state of the commandable's behavior |
| `LuaAISettings.allow_destroy_when_commands_fail` | boolean | W boolean | If enabled, units that repeatedly fail to succeed at commands will be destroyed. |
| `LuaAISettings.allow_try_return_to_spawner` | boolean | W boolean | If enabled, units that have nothing else to do will attempt to return to a spawner. |
| `LuaAISettings.do_separation` | boolean | W boolean | If enabled, units will try to separate themselves from nearby friendly units. |
| `LuaAISettings.join_attacks` | boolean | W boolean | If enabled, the unit will join attack groups. |
| `LuaAISettings.path_resolution_modifier` | int8 | W int8 | Defines how coarse the pathfinder's grid is, where smaller values mean a coarser grid. Defaults to `0`, which equals a resolution of `1x1` tiles, centered on tile centers. Values range from `-8` to `8` inclusive, where each intege… |
| `LuaAISettings.size_in_group` | float | W float | The number of "slots" that the unit takes up in a unit group. Must be greater than 0.  If this value is changed after the unit has been added to a group, the exact behavior is undefined. |
| `LuaFlowStatistics.input_counts` | dictionary[string -> uint64 \| double] | RO | List of input counts indexed by prototype name. Represents the data that is shown on the left side of the GUI for the given statistics. |
| `LuaFlowStatistics.output_counts` | dictionary[string -> uint64 \| double] | RO | List of output counts indexed by prototype name. Represents the data that is shown in the middle of the GUI for electric networks and on the right side for all other statistics types. |
| `LuaFlowStatistics.storage_counts` | dictionary[string -> uint64 \| double] | RO | List of storage counts indexed by prototype name. Represents the data that is shown on the right side of the GUI for electric networks. For other statistics types these values are currently unused and hidden. |
| `LuaTransportLine.line_length` | float | RO | Length of the transport line. Items can be inserted at line position from 0 up to returned value |
| `LuaTransportLine.total_segment_length` | double | RO | Total length of segment which consists of this line, all lines in front and lines in the back directly connected. |
| `LuaTransportLine.owner` | LuaEntity | RO | The entity this transport line belongs to. |
| `LuaForce.technologies` | LuaCustomTable[string -> LuaTechnology] | RO | Technologies owned by this force, indexed by `name`. |
| `LuaForce.recipes` | LuaCustomTable[string -> LuaRecipe] | RO | Recipes available to this force, indexed by `name`. |
| `LuaForce.ai_controllable` | boolean | W boolean | Enables some higher-level AI behaviour for this force. When set to `true`, biters belonging to this force will automatically expand into new territories, build new spawners, and form unit groups. By default, this value is `true` f… |
| `LuaForce.friendly_fire` | boolean | W boolean | If friendly fire is enabled for this force. |
| `LuaForce.mining_drill_productivity_bonus` | double | W double |  |
| `LuaForce.belt_stack_size_bonus` | uint32 | W uint32 | Belt stack size bonus. |
| `LuaForce.inserter_stack_size_bonus` | double | W double | The inserter stack size bonus for non stack inserters |
| `LuaForce.bulk_inserter_capacity_bonus` | uint32 | W uint32 | Number of items that can be transferred by bulk inserters. When writing to this value, it must be >= 0 and <= 254. |
| `LuaForce.laboratory_speed_modifier` | double | W double |  |
| `LuaForce.research_queue` | array[TechnologyID] | W array[TechnologyID] | The research queue of this force. The first technology in the array is the currently active one. Reading this attribute gives an array of [LuaTechnology](runtime:LuaTechnology).  To write to this, the entire table must be written.… |
| `LuaForce.current_research` | LuaTechnology? | RO | The currently ongoing technology research, if any. |
| `LuaForce.research_progress` | double | W double | Progress of current research, as a number in range `[0, 1]`. |
| `LuaTechnology.researched` | boolean | W boolean | Has this technology been researched? Switching from `false` to `true` will trigger the technology advancement perks; switching from `true` to `false` will reverse them. |
| `LuaTechnology.enabled` | boolean | W boolean | Can this technology be researched? |
| `LuaTechnology.level` | uint32 | W uint32 | The current level of this technology. For level-based technology writing to this is the same as researching the technology to the previous level. Writing the level will set [LuaTechnology::enabled](runtime:LuaTechnology::enabled) … |
| `LuaTechnology.research_unit_count` | uint32 | RO | The number of research units required for this technology.  This is multiplied by the current research cost multiplier, unless [LuaTechnologyPrototype::ignore_tech_cost_multiplier](runtime:LuaTechnologyPrototype::ignore_tech_cost_… |
| `LuaTechnology.research_unit_ingredients` | array[ResearchIngredient] | RO | The types of ingredients that labs will require to research this technology. |
| `LuaTechnology.research_unit_energy` | double | RO | Amount of energy required to finish a unit of research. |
| `LuaTechnology.prototype` | LuaTechnologyPrototype | RO | The prototype of this technology. |
| `LuaRecipe.enabled` | boolean | W boolean | Can the recipe be used? |
| `LuaRecipe.productivity_bonus` | float | W float | The productivity bonus for this recipe. |
| `LuaRecipe.energy` | double | RO | Energy required to execute this recipe. This directly affects the crafting time: Recipe's energy is exactly its crafting time in seconds, when crafted in an assembling machine with crafting speed exactly equal to one. |
| `LuaRecipe.ingredients` | array[Ingredient] | RO | The ingredients to this recipe. |
| `LuaRecipe.products` | array[Product] | RO | The results/products of this recipe. |
| `LuaPrototypes.item` | LuaCustomTable[string -> LuaItemPrototype] | RO | A dictionary containing every LuaItemPrototype indexed by `name`. |
| `LuaPrototypes.entity` | LuaCustomTable[string -> LuaEntityPrototype] | RO | A dictionary containing every LuaEntityPrototype indexed by `name`. |
| `LuaPrototypes.recipe` | LuaCustomTable[string -> LuaRecipePrototype] | RO | A dictionary containing every LuaRecipePrototype indexed by `name`. |
| `LuaPrototypes.technology` | LuaCustomTable[string -> LuaTechnologyPrototype] | RO | A dictionary containing every [LuaTechnologyPrototype](runtime:LuaTechnologyPrototype) indexed by `name`. |
| `LuaPrototypes.fluid` | LuaCustomTable[string -> LuaFluidPrototype] | RO | A dictionary containing every LuaFluidPrototype indexed by `name`. |
| `LuaPrototypes.tile` | LuaCustomTable[string -> LuaTilePrototype] | RO | A dictionary containing every LuaTilePrototype indexed by `name`. |
| `LuaPrototypes.quality` | LuaCustomTable[string -> LuaQualityPrototype] | RO |  |
| `LuaPrototypes.surface_property` | LuaCustomTable[string -> LuaSurfacePropertyPrototype] | RO |  |
| `LuaEntityPrototype.energy_usage` | double? | RO | The direct energy usage of this entity, if any. |
| `LuaEntityPrototype.mining_speed` | double? | RO | The mining speed of this mining drill/character prototype. [subclasses: MiningDrill,Character] |
| `LuaEntityPrototype.belt_speed` | double? | RO | The speed of this transport belt. [subclasses: TransportBeltConnectable] |
| `LuaEntityPrototype.electric_energy_source_prototype` | LuaElectricEnergySourcePrototype? | RO | The electric energy source prototype this entity uses, if any. |
| `LuaEntityPrototype.burner_prototype` | LuaBurnerPrototype? | RO | The burner energy source prototype this entity uses, if any. |
| `LuaEntityPrototype.attack_parameters` | AttackParameters? | RO | The attack parameters for this entity, if any. |
| `LuaEntityPrototype.resistances` | dictionary[string -> Resistance]? | RO | List of resistances towards each damage type. It is a dictionary indexed by damage type names (see `data/base/prototypes/damage-type.lua`). [subclasses: EntityWithHealth] |
| `LuaEntityPrototype.crafting_categories` | dictionary[string -> True]? | RO | The [crafting categories](runtime:LuaRecipeCategoryPrototype) this entity prototype supports.  The value in the dictionary is meaningless and exists just to allow for easy lookup. [subclasses: CraftingMachine,Character] |
| `LuaEntityPrototype.ingredient_count` | uint32? | RO | The max number of ingredients this crafting machine prototype supports. [subclasses: CraftingMachine] |
| `LuaEntityPrototype.module_inventory_size` | uint32? | RO | The module inventory size. `nil` if this entity doesn't support modules.  Returns the inventory size if this entity is of normal quality. Use [LuaEntityPrototype::get_inventory_size](runtime:LuaEntityPrototype::get_inventory_size)… |
| `LuaEntityPrototype.mining_drill_radius` | double? | RO | The mining radius of this mining drill prototype. [subclasses: MiningDrill] |
| `LuaEntityPrototype.resource_categories` | dictionary[string -> True]? | RO | The [resource categories](runtime:LuaResourceCategoryPrototype) this character or mining drill supports.  The value in the dictionary is meaningless and exists just to allow for easy lookup. [subclasses: MiningDrill,Character] |
| `LuaEntityPrototype.resource_drain_rate_percent` | uint8? | RO | The resource drain rate percent of this mining drill prototype. [subclasses: MiningDrill] |
| `LuaEntityPrototype.turret_range` | uint32? | RO | The range of this turret. [subclasses: Turret] |
| `LuaEntityPrototype.automated_ammo_count` | uint32? | RO | The amount of ammo that inserters automatically insert into this ammo turret, artillery turret or artillery wagon. [subclasses: ArtilleryTurret,ArtilleryWagon,AmmoTurret] |
| `LuaEntityPrototype.guns` | dictionary[string -> LuaItemPrototype]? | RO | A mapping of the gun name to the gun prototype this prototype uses. `nil` if this entity prototype doesn't use guns. |
| `LuaEntityPrototype.indexed_guns` | array[LuaItemPrototype]? | RO | A vector of the gun prototypes of this car, spider vehicle, artillery wagon, or turret. [subclasses: Car,SpiderVehicle,ArtilleryTurret,ArtilleryWagon] |
| `LuaEntityPrototype.vector_to_place_result` | Vector? | RO |  [subclasses: MiningDrill,CraftingMachine] |
| `LuaEntityPrototype.mineable_properties` | MineableProperties | RO | Whether this entity is minable and what can be obtained by mining it. |
| `LuaEntityPrototype.infinite_resource` | boolean? | RO | Whether this resource is infinite. [subclasses: ResourceEntity] |
| `LuaEntityPrototype.minimum_resource_amount` | uint32? | RO | Minimum amount of this resource. [subclasses: ResourceEntity] |
| `LuaEntityPrototype.normal_resource_amount` | uint32? | RO | The normal amount for this resource. [subclasses: ResourceEntity] |
| `LuaEntityPrototype.speed` | double? | RO | The default speed of this flying robot, rolling stock or unit. For rolling stocks, this is their `max_speed`. [subclasses: FlyingRobot,RollingStock,Unit] |
| `LuaEntityPrototype.max_underground_distance` | uint8? | RO | The max underground distance for underground belts and underground pipes. [subclasses: UndergroundBelt,PipeToGround] |
| `LuaEntityPrototype.surface_conditions` | array[SurfaceCondition]? | RO | The surface conditions required to build this entity. |
| `LuaEntityPrototype.crafting_speed_quality_multiplier` | dictionary[QualityID -> double] | RO |  [subclasses: CraftingMachine] |
| `LuaEntityPrototype.energy_usage_quality_multiplier` | dictionary[QualityID -> double] | RO |  [subclasses: CraftingMachine] |
| `LuaEntityPrototype.allowed_effects` | dictionary[string -> boolean]? | RO | The allowed module effects for this entity, if any. |
| `LuaEntityPrototype.effect_receiver` | EffectReceiver? | RO | Effect receiver prototype of this crafting machine, lab, or mining drill. [subclasses: CraftingMachine,Lab,MiningDrill] |
| `LuaEntityPrototype.fixed_recipe` | string? | RO | The fixed recipe name for this assembling machine prototype, if any. [subclasses: AssemblingMachine] |
| `LuaEntityPrototype.heating_energy` | double | RO | The energy required to keep this entity from freezing. Zero energy means it doesn't freeze. |
| `LuaEntityPrototype.emissions_per_second` | dictionary[string -> double] | RO | A table of pollution emissions per second the entity will create, grouped by the name of the pollution type. |
| `LuaEntityPrototype.flags` | EntityPrototypeFlags | RO | The flags for this entity prototype. |
| `LuaEntityPrototype.max_power_output` | double? | RO | The default maximum power output of this generator prototype. This property is deprecated in favor of [LuaEntityPrototype::get_max_power_output](runtime:LuaEntityPrototype::get_max_power_output) and should not be used. [subclasses: BurnerGenerator,Generator] |
| `LuaPrototypeBase.name` | string | RO | Name of this prototype. |
| `LuaPrototypeBase.type` | string | RO | Type of this prototype. |
| `LuaPrototypeBase.hidden` | boolean | RO |  |
| `LuaPrototypeBase.order` | string | RO | The string used to alphabetically sort these prototypes. It is a simple string that has no additional semantic meaning. |
| `LuaPrototypeBase.subgroup` | LuaGroup | RO | Subgroup of this prototype. |
| `LuaElectricEnergySourcePrototype.buffer_capacity` | double | RO |  |
| `LuaElectricEnergySourcePrototype.drain` | double | RO |  |
| `LuaElectricEnergySourcePrototype.usage_priority` | string | RO |  |
| `LuaElectricEnergySourcePrototype.emissions_per_joule` | dictionary[string -> double] | RO | The table of emissions of this energy source in `pollution/Joule`, indexed by pollutant type. Multiplying it by energy consumption in `Watt` gives `pollution/second`. |
| `LuaRecipePrototype.ingredients` | array[Ingredient] | RO | The ingredients to this recipe. |
| `LuaRecipePrototype.products` | array[Product] | RO | The results/products of this recipe. |
| `LuaRecipePrototype.energy` | double | RO | Energy required to execute this recipe. This directly affects the crafting time: Recipe's energy is exactly its crafting time in seconds, when crafted in an assembling machine with crafting speed exactly equal to one. |
| `LuaRecipePrototype.category` | string | RO | Category of the recipe. |
| `LuaRecipePrototype.enabled` | boolean | RO | If this recipe prototype is enabled by default (enabled at the beginning of a game). |
| `LuaRecipePrototype.main_product` | Product? | RO | The main product of this recipe, if any. |
| `LuaRecipePrototype.maximum_productivity` | double | RO | The maximal productivity bonus that can be achieved with this recipe. |
| `LuaRecipePrototype.surface_conditions` | array[SurfaceCondition]? | RO | The surface conditions required to craft this recipe. |
| `LuaRecipePrototype.allowed_effects` | dictionary[string -> boolean]? | RO | The allowed module effects for this recipe, if any. |
| `LuaTechnologyPrototype.prerequisites` | dictionary[string -> LuaTechnologyPrototype] | RO | Prerequisites of this technology. The result maps technology name to the [LuaTechnologyPrototype](runtime:LuaTechnologyPrototype) object. |
| `LuaTechnologyPrototype.effects` | array[TechnologyModifier] | RO | Effects applied when this technology is researched. |
| `LuaTechnologyPrototype.research_unit_count` | uint32 | RO | The number of research units required for this technology.  This is multiplied by the current research cost multiplier, unless [LuaTechnologyPrototype::ignore_tech_cost_multiplier](runtime:LuaTechnologyPrototype::ignore_tech_cost_… |
| `LuaTechnologyPrototype.research_unit_count_formula` | MathExpression? | RO | The count formula, if this research has any. See [TechnologyUnit::count_formula](prototype:TechnologyUnit::count_formula) for details. |
| `LuaTechnologyPrototype.research_unit_ingredients` | array[ResearchIngredient] | RO | The types of ingredients that labs will require to research this technology. |
| `LuaTechnologyPrototype.research_unit_energy` | double | RO | Amount of energy required to finish a unit of research. |
| `LuaTechnologyPrototype.research_trigger` | ResearchTrigger? | RO | The trigger that will research this technology if any. |
| `LuaTechnologyPrototype.max_level` | uint32 | RO | The max level of this research. |
| `LuaTechnologyPrototype.level` | uint32 | RO | The level of this research. |
| `LuaTechnologyPrototype.enabled` | boolean | RO | If this technology prototype is enabled by default (enabled at the beginning of a game). |
| `LuaTechnologyPrototype.upgrade` | boolean | RO | If the is technology prototype is an upgrade to some other technology. |
| `LuaTechnologyPrototype.ignore_tech_cost_multiplier` | boolean | RO | If this technology ignores the technology cost multiplier setting.  [LuaTechnologyPrototype::research_unit_count](runtime:LuaTechnologyPrototype::research_unit_count) will already take this setting into account. |
| `LuaItemPrototype.stack_size` | uint32 | RO | Maximum stack size of the item specified by this prototype. |
| `LuaItemPrototype.magazine_size` | float? | RO | Size of full magazine. [subclasses: AmmoItem] |
| `LuaItemPrototype.ammo_category` | LuaAmmoCategoryPrototype? | RO |  [subclasses: AmmoItem] |
| `LuaItemPrototype.fuel_value` | float | RO | Fuel value when burned. |
| `LuaItemPrototype.fuel_category` | string? | RO | The fuel category, if any. |
| `LuaItemPrototype.place_result` | LuaEntityPrototype? | RO | Prototype of the entity that will be created by placing this item, if any. |
| `LuaItemPrototype.weight` | Weight | RO | Weight of this item. More information on how item weight is determined can be found on its [auxiliary page](runtime:item-weight). |
| `LuaBootstrap.active_mods` | dictionary[string -> string] | RO | A dictionary listing the names of all currently active mods and mapping them to their version. |
| `LuaBootstrap.feature_flags` | table{expansion_shaders: boolean, freezing: boolean, quality: boolean, rail_bridges: boolean, segmented_units: boolean, space_travel: boolean, spoiling: boolean} | RO | A dictionary of feature flags mapping to whether they are enabled. |
| `LuaBootstrap.mod_name` | string | RO | The name of the mod from the environment this is used in. |
| `LuaHelpers.game_version` | string | RO | Current version of game |

