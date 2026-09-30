# Combat reference for Factorio 2.0.77 ("Magnetics" mod), backed by sources

Every claim below cites a source. Abbreviations:
- `B/` = `/opt/factorio/data/base/`, `SA/` = `/opt/factorio/data/space-age/`, `CORE/` = `/opt/factorio/data/core/`
- `P:Name.prop` = `/opt/factorio-api/prototype-api.json` (prototype or type `Name`, property `prop`); `R:Class.member` = `/opt/factorio-api/runtime-api.json`
- Both JSON files report `application_version = 2.0.77`, `api_version = 6`.
- "Not found in sources" means the fact is not in the data files or the JSON. I did not fill gaps from memory.
- The helper scripts I used to query the JSON are in `recon/tools/` (`proto.py`, `rt.py`, `techfx.py`).

---

## 0. Findings a mod author must know (summary)

1. **Required turret fields** (`P:TurretPrototype`, optional=False): `attack_parameters`, `call_for_help_radius`, `folded_animation`, `graphics_set`. `graphics_set` can be an empty table: vanilla worms use `graphics_set = {}` (B/prototypes/entity/turrets.lua:357). Add per subtype:
   - `ammo-turret`: `inventory_size` and `automated_ammo_count` (P:AmmoTurretPrototype).
   - `electric-turret`: `energy_source` (Electric **or Void**) (P:ElectricTurretPrototype).
   - `fluid-turret`: `fluid_box`, `fluid_buffer_size`, `fluid_buffer_input_flow`, `activation_buffer_ratio`, and a `StreamAttackParameters` (P:FluidTurretPrototype).
2. A turret that is **not** an `ammo-turret` must have `ammo_type` inside `attack_parameters` (P:TurretPrototype.attack_parameters: "Requires ammo_type in attack_parameters unless this is a AmmoTurretPrototype").
3. **Upgrades are bound to ammo category.** `ammo-damage` and `gun-speed` technology effects name an `ammo_category`. `turret-attack` names a `turret_id` (P:AmmoDamageModifier, P:GunSpeedModifier, P:TurretAttackModifier). A new ammo category gets **no** vanilla upgrades until the mod adds them.
4. **Space Age overwrites base technology effects in place:**
   - `SA/base-data-updates.lua:413-417` changes `physical-projectile-damage-6/7` by **index** (`effects[1]`, `effects[2]`).
   - `SA/base-data-updates.lua:476-503` **replaces** the whole `effects` table of `laser-weapons-damage-5/6/7`.

   So append effects to these technologies (never prepend them), and do it after Space Age's data stage.
5. Space Age runs `base-data-updates.lua` from its own `data.lua` (SA/data.lua:65), not from `data-updates.lua`.
6. **Space Age makes vanilla turrets freeze and restricts flamethrower placement:**
   - It gives `heating_energy` to gun-turret, laser-turret and artillery-turret (SA/base-data-updates.lua:128-130). The railgun and rocket turrets set it inline (SA/.../turrets.lua:318, :430).
   - It restricts `flamethrower-turret` to surfaces with pressure ≥ 10 (SA/base-data-updates.lua:163-171, :183).
   - "Freezing" is a feature flag that Space Age requires (`SA/info.json`: `"freezing_required": true`). The API documents `feature_flags` with the example `if feature_flags["spoiling"] then ... end` (P:FeatureFlags). A base-only mod should guard `heating_energy` with `feature_flags["freezing"]`. This is a recommendation. What the engine does with `heating_energy` when the flag is off: not found in sources.
7. **Asteroid resistances depend on load order.** In Space Age, asteroids get **100 % resistance to every `damage-type` present in `data.raw` when `asteroid.lua` runs**, except impact, poison and acid, unless the asteroid data names that type (SA/prototypes/entity/asteroid.lua:281-297). A new custom damage type is therefore either immune on asteroids (if defined before Space Age's data stage) or unresisted (if defined after).
8. **Graphics can be reused.** The headless build contains **no png files**: `find /opt/factorio/data -name "*.png"` returns 0. It still contains the `.lua` sprite descriptors that `util.sprite_load` needs, e.g. `SA/graphics/entity/tesla-turret/*.lua` (CORE/lualib/util.lua:673-698). The base turret graphics helper functions are **globals**:
   - `gun_turret_extension`, `gun_turret_extension_mask`, `gun_turret_extension_shadow`, `gun_turret_attack`
   - `laser_turret_extension`, `laser_turret_extension_shadow`, `laser_turret_extension_mask`
   - `laser_turret_shooting`, `laser_turret_shooting_glow`, `laser_turret_shooting_mask`, `laser_turret_shooting_shadow`

   They are defined in B/prototypes/entity/turrets.lua:30-290. Space Age calls one directly: `energy_glow_animation = laser_turret_shooting_glow()` (SA/prototypes/entity/turrets.lua:597).

---

## 1. Damage types and resistances

### 1.1 The damage-type prototypes
There are exactly 8. They are defined in B/prototypes/damage-type.lua:1-36. A grep shows no other `type = "damage-type"` in base, quality, elevated-rails or space-age.
```lua
{ type = "damage-type", name = "physical" },
{ type = "damage-type", name = "impact" },
{ type = "damage-type", name = "poison" },
{ type = "damage-type", name = "explosion" },
{ type = "damage-type", name = "fire" },
{ type = "damage-type", name = "laser" },
{ type = "damage-type", name = "acid" },
{ type = "damage-type", name = "electric" }
```
`P:DamageType` (typename `damage-type`) has no properties of its own beyond the base `Prototype`.

### 1.2 Resistance format
`P:Resistance`:
- `type`: DamageTypeID (required).
- `decrease`: float, default 0. "The flat resistance … (Higher is better)".
- `percent`: float, default 0. "Expected range is from 0 to 100".

`P:EntityWithHealthPrototype`:
- `resistances`: array[Resistance].
- `max_health`: default 10.
- `healing_per_tick`: default 0. "The entity must be active for this to work."
- `hide_resistances`: default **true**.

The exact order in which `decrease` and `percent` are applied is **not found in sources**. The API only links to the wiki. You can measure it empirically: `on_entity_damaged` reports both `original_damage_amount` and `final_damage_amount` (§13.4).

### 1.3 Damage effect format
`P:DamageEntityTriggerEffectItem`:
- `type = "damage"`, `damage: DamageParameters` (required).
- `apply_damage_to_trees` (default true), `vaporize` (default false: no corpse), `use_substitute`.
- `lower_damage_modifier`/`upper_damage_modifier` and `lower_distance_threshold`/`upper_distance_threshold`.

`P:DamageParameters` = `{amount: float, type: DamageTypeID}`.

---

## 2. Ammo categories

### 2.1 Base
B/prototypes/categories/ammo-category.lua:
- Visible: `bullet`, `rocket`, `laser`, `electric`, `flamethrower`, `shotgun-shell`, `grenade`, `cannon-shell`, `artillery-shell`, `beam`, `landmine`.
- `hidden = true`: `capsule`, `melee`, `biological`. `melee` and `biological` have no icon.

The file ends with:
```lua
for k,v in pairs(data.raw["ammo-category"]) do
  if not v.bonus_gui_order then
    v.bonus_gui_order = bonus_gui_ordering[k]
  end
end
```
`bonus_gui_ordering` is a fixed table in CORE/lualib/bonus-gui-ordering.lua. It has no entries for `railgun`, `tesla` or any mod category. **A new category should set `bonus_gui_order` itself.** This is an inference: otherwise the value stays at the API default `""` (P:AmmoCategory.bonus_gui_order default `''`).

### 2.2 Space Age
SA/prototypes/categories/ammo-category.lua:5-21:
```lua
{ type = "ammo-category", name = "railgun", icon = "__space-age__/graphics/icons/ammo-category/railgun.png", subgroup = "ammo-category" },
{ type = "ammo-category", name = "tesla",   icon = "__space-age__/graphics/icons/ammo-category/tesla.png",   subgroup = "ammo-category" },
{ type = "ammo-category", name = "seismic", hidden = true }
```

### 2.3 API
`P:AmmoCategory` properties: `bonus_gui_order`, `icon`, `icon_size` (default 64), `icons`. All are optional.

`P:BaseAttackParameters` accepts `ammo_category` **or** `ammo_categories` (array). Each is "Mandatory if [the other] is not defined". A grep for `ammo_categories` over all vanilla data returns 0 hits, so the plural form is documented but unused in vanilla.

---

## 3. Turret prototype family (API)

### 3.1 Hierarchy
- `TurretPrototype` (typename `turret`, parent EntityWithOwnerPrototype): "A turret that needs no extra ammunition".
  - `AmmoTurretPrototype` (typename `ammo-turret`)
  - `ElectricTurretPrototype` (typename `electric-turret`)
  - `FluidTurretPrototype` (typename `fluid-turret`)

### 3.2 TurretPrototype: key properties
All from `P:TurretPrototype`:

| property | type / default | note |
|---|---|---|
| `attack_parameters` | AttackParameters, **required** | |
| `call_for_help_radius` | double, **required** | vanilla uses 40 everywhere |
| `folded_animation` | RotatedAnimation8Way, **required** | |
| `graphics_set` | TurretGraphicsSet, **required** | may be `{}` (worms, B/.../turrets.lua:357) |
| `preparing_animation`, `prepared_animation`, `starting_attack_animation`, `attacking_animation`, `ending_attack_animation`, `folding_animation` | RotatedAnimation8Way, optional | |
| `energy_glow_animation`, `resource_indicator_animation`, `prepared_alternative_animation` | optional | |
| `rotation_speed`, `preparing_speed`, `folding_speed`, `attacking_speed`, `starting_attack_speed`, `ending_attack_speed`, `prepared_speed`, `folded_speed` | float; default = `default_speed` (1) | "`1 ÷ X_speed = duration of the X_animation`" |
| `prepare_range` | default = `attack_parameters.range` | |
| `shoot_in_prepare_state` | false | |
| `start_attacking_only_when_can_shoot` | false | FluidTurret forces true |
| `turret_base_has_direction` | false | true = rotation affects collision box |
| `allow_turning_when_starting_attack`, `can_retarget_while_starting_attack` | false | |
| `attack_target_mask` / `ignore_target_mask` | TriggerTargetMask | |
| `alert_when_attacking` | true | |
| `is_military_target` | **true** for turrets (EntityWithOwner default is false) | |
| `circuit_connector` | array[CircuitConnectorDefinition] | 8 entries if `building-direction-8-way`, 16 if 16-way, 4 if `turret_base_has_direction`, otherwise 1 |
| `special_effect` | TurretSpecialEffect (`type="mask-by-circle"`) | used by the railgun |
| `unfolds_before_dying` | false | |

`P:TurretState` = `'folded' | 'preparing' | 'prepared' | 'starting-attack' | 'attacking' | 'ending-attack' | 'rotate-for-folding' | 'folding'`.

### 3.3 Base graphics (`graphics_set.base_visualisation`)
`P:TurretGraphicsSet`:
- `base_visualisation`: TurretBaseVisualisation | array[TurretBaseVisualisation].
- `water_reflection`.

`P:TurretBaseVisualisation`:
- `animation`: Animation4Way, **required**.
- `render_layer`: default `"lower-object"`.
- `secondary_draw_order`.
- `enabled_states`: array[TurretState]. "If not defined, visualisation will be drawn in all states."
- `draw_when_has_energy`, `draw_when_no_energy`, `draw_when_has_ammo`, `draw_when_no_ammo`, `draw_when_frozen`, `draw_when_not_frozen`: all default true.

Vanilla uses three shapes:
- **Single struct** (gun-turret, B/prototypes/entity/turrets.lua:518-547):
  ```lua
  graphics_set =
  {
    base_visualisation =
    {
      animation =
      {
        layers =
        {
          { filename = "__base__/graphics/entity/gun-turret/gun-turret-base.png", priority = "high", width = 150, height = 118, shift = util.by_pixel(0.5, -1), scale = 0.5 },
          { filename = "__base__/graphics/entity/gun-turret/gun-turret-base-mask.png", flags = {"mask", "low-object"}, line_length = 1, width = 122, height = 102, shift = util.by_pixel(0, -4.5), apply_runtime_tint = true, scale = 0.5 }
        }
      }
    }
  },
  ```
- **4-way animation** (flamethrower-turret, B/prototypes/entity/fire.lua:439-593): `animation = { north = {layers=...}, east = ..., south = ..., west = ... }`, with `render_layer = "object"`.
- **Array with `enabled_states`** (tesla-turret, SA/prototypes/entity/turrets.lua:600-698): the base sprite first, then idle sparks drawn only in `{ "folded", "preparing", "rotate-for-folding", "folding" }` and active sparks only in `{ "prepared", "starting-attack", "attacking", "ending-attack" }`, each with `draw_when_no_energy = false, draw_when_frozen = false`.

### 3.4 Subtypes

**AmmoTurretPrototype:**
- `inventory_size` (required).
- `automated_ammo_count` (required): "The amount of ammo that inserters automatically insert".
- `prepare_with_no_ammo` (default true).
- `energy_source` (ElectricEnergySource, optional) and `energy_per_shot` (optional). The railgun uses both.

**ElectricTurretPrototype:**
- `energy_source`: `ElectricEnergySource | VoidEnergySource`, required.
- A void source gives a free, unpowered turret, which is handy for tests.

**FluidTurretPrototype:**
- `attack_parameters` must be `StreamAttackParameters` and "Requires ammo_type".
- Required: `fluid_box`, `fluid_buffer_size`, `fluid_buffer_input_flow`, `activation_buffer_ratio`.
- `turret_base_has_direction` is "Always `true`".
- Muzzle animation shifts per state and fuel indicator sprites are optional.

---

## 4. `attack_parameters` format

`P:AttackParameters` = `ProjectileAttackParameters | BeamAttackParameters | StreamAttackParameters`. The variant is chosen by the `type` key.

### 4.1 Common fields (`P:BaseAttackParameters`)

| field | type / default | description from the API |
|---|---|---|
| `cooldown` | float, **required** | "Number of ticks in which it will be possible to shoot again. If < 1, multiple shots can be performed in one tick." |
| `range` | float, **required** | tiles |
| `min_range` | 0 | the turret cannot target anything closer |
| `ammo_category` / `ammo_categories` | one required | |
| `ammo_type` | AmmoType, "Can be mandatory" | required for non-ammo turrets |
| `damage_modifier` | float, 1 | |
| `ammo_consumption_modifier` | 1 | |
| `cooldown_deviation` | 0 (0..1) | |
| `range_mode` | `'center-to-center'` (default) \| `'bounding-box-to-bounding-box'` \| `'center-to-bounding-box'` | P:RangeMode |
| `turn_range` | 1 | arc (0.25 = 90°); values > 0.5 and < 1 are clamped to 0.5 |
| `health_penalty` | 0 | higher value = avoid high-HP targets; negative = prefer them |
| `rotate_penalty`, `fire_penalty` | 0 | `fire_penalty` > 0 prefers targets that are not burning |
| `lead_target_for_projectile_speed` / `_delay` | 0 | predictive aiming |
| `warmup` | 0 ticks | |
| `min_attack_distance` | = range | |
| `true_collinear_ejection` | false | "Used for railgun turrets to avoid unexpected friendly fire incidents." |
| `sound`, `cyclic_sound`, `animation`, `activation_type`, `movement_slow_down_factor`, `use_shooter_direction` | | |

### 4.2 Projectile variant (`P:ProjectileAttackParameters`)
- `type = 'projectile'`.
- `projectile_creation_distance`: default 0.
- `projectile_center`: default `{0,0}`.
- `projectile_creation_offsets`: array[Vector], for multi-barrel guns (the rocket-turret uses 6 offsets, SA/.../turrets.lua:508-533).
- `projectile_orientation_offset`, `projectile_creation_parameters`.
- `apply_projection_to_projectile_creation_position`: default true.
- `shell_particle`: CircularParticleCreationSpecification.

`P:CircularParticleCreationSpecification`:
- Required: `name` (ParticleID) and `starting_frame_speed`.
- Optional: `direction_deviation`, `speed` (0.1), `speed_deviation`, `center`, `creation_distance`, `starting_frame_speed_deviation`, `height`, `vertical_speed`, and others.
- Particles used in vanilla: `"shell-particle"` (B/prototypes/particles.lua:3818) and `"railgun-shell-particle"` (SA/prototypes/particles.lua:835).

Although melee units attack at range 0.5-1.5, vanilla biter melee is also `type="projectile"` with an instant damage `ammo_type` (B/prototypes/entity/enemies.lua:12-29, 48-58).

### 4.3 Beam variant (`P:BeamAttackParameters`)
`type = 'beam'`, `source_direction_count` (uint32, default 0), `source_offset`.

### 4.4 Stream variant (`P:StreamAttackParameters`)
- `type = 'stream'`, `fluid_consumption` (0.0), `gun_barrel_length`, `gun_center_shift`, `projectile_creation_parameters`.
- `fluids`: array[StreamFluidProperties{`type`: FluidID, `damage_modifier` default 1.0}].

---

## 5. Vanilla turrets: reference values

| turret | type | file:line | HP | resist. | range (min) | cooldown (ticks) | category | energy |
|---|---|---|---|---|---|---|---|---|
| gun-turret | ammo-turret | B/prototypes/entity/turrets.lua:457-589 | 400 | none | 18 | 6 | bullet | none |
| laser-turret | electric-turret | B/…/turrets.lua:591-735 | 1000 | none | 24 | 40 | laser | 800kJ/shot |
| flamethrower-turret | fluid-turret | B/prototypes/entity/fire.lua:364-671 | 1400 | fire 100 % | 30 (min 6) | 4 | flamethrower | fluid 0.2/shot |
| railgun-turret (SA) | ammo-turret | SA/prototypes/entity/turrets.lua:294-417 | 4000 | none | 40 (min 3.5) | 170 | railgun | 10MJ/shot |
| tesla-turret (SA) | electric-turret | SA/…/turrets.lua:551-773 | 1000 | none | 30 | 120 | tesla | 12MJ/shot |
| rocket-turret (SA) | ammo-turret | SA/…/turrets.lua:418-550 | 400 | none | 36 (min 15) | 120 | rocket | none |

For scale: 60 ticks = 1 s at normal speed (R:LuaGameScript.speed: "1.0 is normal speed -- 60 UPS"). A gun-turret with `cooldown = 6` can therefore fire 10 times per second before any `gun-speed` bonus.

### 5.1 gun-turret
B/prototypes/entity/turrets.lua:457-589, verbatim excerpts:
```lua
type = "ammo-turret",
name = "gun-turret",
flags = {"placeable-player", "player-creation"},
fast_replaceable_group = "ammo-turret",
max_health = 400,
collision_box = {{-0.7, -0.7 }, {0.7, 0.7}},
selection_box = {{-1, -1 }, {1, 1}},
rotation_speed = 0.015,
preparing_speed = 0.08,
folding_speed = 0.08,
inventory_size = 1,
automated_ammo_count = 10,
attacking_speed = 0.5,
folded_animation = { layers = { gun_turret_extension{frame_count=1, line_length = 1}, gun_turret_extension_mask{frame_count=1, line_length = 1}, gun_turret_extension_shadow{frame_count=1, line_length = 1} } },
preparing_animation = { layers = { gun_turret_extension{}, gun_turret_extension_mask{}, gun_turret_extension_shadow{} } },
prepared_animation = gun_turret_attack{frame_count=1},
attacking_animation = gun_turret_attack{},
folding_animation = { layers = { gun_turret_extension{run_mode = "backward"}, gun_turret_extension_mask{run_mode = "backward"}, gun_turret_extension_shadow{run_mode = "backward"} } },
...
attack_parameters =
{
  type = "projectile",
  ammo_category = "bullet",
  health_penalty = 1,
  cooldown = 6,
  projectile_creation_distance = 1.39375,
  projectile_center = {0, -0.0875}, -- same as gun_turret_attack shift
  shell_particle =
  {
    name = "shell-particle",
    direction_deviation = 0.1,
    speed = 0.1,
    speed_deviation = 0.03,
    center = {-0.0625, 0},
    creation_distance = -1.925,
    starting_frame_speed = 0.2,
    starting_frame_speed_deviation = 0.1
  },
  range = 18,
  sound = sounds.gun_turret_gunshot
},
call_for_help_radius = 40,
```
- `icons_positioning = {{inventory_index = defines.inventory.turret_ammo, shift = {0, -0.25}}}` (turrets.lua:486-489).
- `circuit_connector = circuit_connector_definitions["gun-turret"]`, which is a vector made with `create_vector` (CORE/lualib/circuit-connector-generated-definitions.lua:833).

### 5.2 laser-turret
B/…/turrets.lua:591-735:
- `flags = {"placeable-player", "placeable-enemy", "player-creation"}`, `fast_replaceable_group = "laser-turret"`, `rotation_speed = 0.01`, `preparing_speed = 0.05`, `folding_speed = 0.05`.
- Energy source:
  ```lua
  energy_source = { type = "electric", buffer_capacity = "801kJ", input_flow_limit = "9600kW", drain = "24kW", usage_priority = "primary-input" },
  ```
- Glow: `energy_glow_animation = laser_turret_shooting_glow(), glow_light_intensity = 0.5`.
- Attack parameters:
  ```lua
  attack_parameters =
  {
    type = "beam",
    cooldown = 40,
    range = 24,
    range_mode = "center-to-bounding-box",
    source_direction_count = 64,
    source_offset = {0, -3.423489 / 4},
    damage_modifier = 2,
    ammo_category = "laser",
    ammo_type =
    {
      energy_consumption = "800kJ",
      action =
      {
        type = "direct",
        action_delivery =
        {
          type = "beam",
          beam = "laser-beam",
          max_length = 24,
          duration = 40,
          source_offset = {0, -1.31439 }
        }
      }
    }
  },
  ```
  The beam `laser-beam` does `{ amount = 10, type = "laser"}` (B/prototypes/entity/beams.lua:22-23, name set at :181).
- How `damage_modifier = 2` combines with the beam's 10 damage is not spelled out in the API: P:BaseAttackParameters.damage_modifier has no description.

### 5.3 flamethrower-turret
B/prototypes/entity/fire.lua:364-671. Key lines:
```lua
type = "fluid-turret",
name = "flamethrower-turret",
max_health = 1400,
collision_box = {{-0.7, -1.2 }, {0.7, 1.2}},
selection_box = {{-1, -1.5 }, {1, 1.5}},
turret_base_has_direction = true,
resistances = { { type = "fire", percent = 100 } },
fluid_box = { production_type = "none", volume = 100, pipe_covers = pipecoverspictures(),
  pipe_connections = { { direction = defines.direction.west, position = {-0.5, 1.0} }, { direction = defines.direction.east, position = {0.5, 1.0} } } , ...},
fluid_buffer_size = 100,
fluid_buffer_input_flow = 250 / 60 / 5, -- 5s to fill the buffer
activation_buffer_ratio = 0.25,
prepare_range = 35,
shoot_in_prepare_state = false,
attack_parameters =
{
  type = "stream",
  cooldown = 4,
  range = 30,
  min_range = 6,
  turn_range = 1.0 / 3.0,
  fire_penalty = 15,
  fluids =
  {
    {type = "crude-oil"},
    {type = "heavy-oil", damage_modifier = 1.05},
    {type = "light-oil", damage_modifier = 1.1}
  },
  fluid_consumption = 0.2,
  gun_barrel_length = 0.4,
  ammo_category = "flamethrower",
  ammo_type = { action = { type = "direct", action_delivery = { type = "stream", stream = "flamethrower-fire-stream", source_offset = {0.15, -0.5} } } },
  ...
},
```
- The stream `flamethrower-fire-stream` applies `fire-sticker` and `{ amount = 3, type = "fire" }` in radius 2.5, then creates `fire-flame` (fire.lua:755-815).
- `fire-sticker`: `damage_per_tick = { amount = 10 * 100 / 60, type = "fire" }`, `duration_in_ticks = 30 * 60`, `target_movement_modifier = 0.8` (fire.lua:677-700).
- `fire-flame`: `damage_per_tick = {amount = 13 / 60, type = "fire"}` (fire.lua:250).
- Space Age: `surface_conditions = ten_pressure_condition()`, i.e. `{{property = "pressure", min = 10}}` (SA/base-data-updates.lua:163-171, :183).

### 5.4 railgun-turret (Space Age)
SA/prototypes/entity/turrets.lua:294-417:
```lua
type = "ammo-turret",
name = "railgun-turret",
flags = {"placeable-player", "player-creation", "building-direction-8-way"},
max_health = 4000,
collision_box = {{-1.41, -1.9 }, {1.41, 2.1}},
selection_box = {{-1.5, -2.5 }, {1.5, 2.5}},
energy_source = { type = "electric", buffer_capacity = "10MJ", input_flow_limit = "10MW", usage_priority = "primary-input" },
energy_per_shot = "10MJ",
tile_height = 5,
turret_base_has_direction = true,
allow_turning_when_starting_attack = true,
prepare_with_no_ammo = false,
heating_energy = "50kW",
rotation_speed = 0.005,
preparing_speed = 0.04,
automated_ammo_count = 10,
inventory_size = 1,
folding_speed = 0.04,
attacking_speed = 0.35,
starting_attack_speed = 0.02,
ending_attack_speed = 0.05,
can_retarget_while_starting_attack = true,
...
special_effect = { type = "mask-by-circle", center = {...}, min_radius = 0, max_radius = 2.25, falloff = 0.25, attacking_min_radius = 0, attacking_max_radius = -2.25, attacking_falloff = 0.75 },
attack_parameters =
{
  type = "projectile",
  ammo_category = "railgun",
  health_penalty = -1,
  cooldown = 170,
  projectile_creation_distance = 3.6,
  projectile_center = {0, 0},
  apply_projection_to_projectile_creation_position = false,
  shell_particle = { name = "railgun-shell-particle", direction_deviation = 0.1, speed = 0.1, speed_deviation = 0.03, center = {0, 0}, creation_distance = -6, starting_frame_speed = 0.2, starting_frame_speed_deviation = 0.1 },
  min_range = 3.5,
  range = 40,
  turn_range = 0.20,
  sound = space_age_sounds.railgun_turret_gunshot,
  true_collinear_ejection = true
},
```
- The animations come from `require("__space-age__.prototypes.entity.railgun-turret-pictures")`, which returns the keys `base_picture`, `neutral_animation`, `aiming_animation`, `warmup_animation`, `shooting_animation`, `cooldown_animation` and `resource_indicator_animation` (SA/.../railgun-turret-pictures.lua:500-508).
- The turret uses all six state animations (turrets.lua:343-351).
- The handheld `railgun` gun: `cooldown = 120`, `range = 40`, `ammo_category = "railgun"` (SA/prototypes/item.lua:549-578).

### 5.5 tesla-turret (Space Age)
SA/prototypes/entity/turrets.lua:551-773:
```lua
type = "electric-turret",
name = "tesla-turret",
flags = {"placeable-player", "placeable-enemy", "player-creation"},
max_health = 1000,
collision_box = {{-1.7, -1.7 }, {1.7, 1.7}},
selection_box = {{-2, -2 }, {2, 2}},
start_attacking_only_when_can_shoot = true,
rotation_speed = 0.005, preparing_speed = 0.1, folding_speed = 0.1,
ending_attack_speed = 1 / (30 + 1), -- Must be clocked to the beam duration so the face light turns off at the right time
energy_source = { type = "electric", buffer_capacity = "15MJ", input_flow_limit = "7MW", drain = "1MW", usage_priority = "primary-input" },
...
attack_parameters =
{
  type = "beam",
  cooldown = 120,
  range = 30,
  range_mode = "center-to-bounding-box",
  fire_penalty = 0.9,
  source_direction_count = 64,
  source_offset = {0, -0.55},
  ammo_category = "tesla",
  ammo_type =
  {
    energy_consumption = "12MJ",
    action =
    {
      type = "direct",
      action_delivery =
      {
        type = "instant",
        target_effects =
        {
          -- Chain effect must go first in case the beam kills the target
          { type = "nested-result", action = { type = "direct", action_delivery = { type = "chain", chain = "chain-tesla-turret-chain" } } },
          { type = "nested-result", action = { type = "direct", action_delivery = { type = "beam", beam = "chain-tesla-turret-beam-start", max_length = 40, duration = 30, add_to_shooter = false, destroy_with_source_or_target = false, source_offset = {0, -2.6} } } }
        }
      }
    }
  }
},
```
- The tesla **turret** uses no ammo item: it is an electric turret with a built-in `ammo_type` in category `"tesla"`.
- The `tesla-ammo` item is for the handheld `teslagun` (SA/prototypes/item.lua:1416-1434: `type = "beam"`, `ammo_category = "tesla"`, `cooldown = 60`, `range = 24`).
- Both receive `ammo-damage[tesla]` bonuses (§14).
- Stickers (SA/.../turrets.lua:774-792):
  ```lua
  { type = "sticker", name = "tesla-turret-stun", flags = {"not-on-map"}, hidden = true, duration_in_ticks = 30,  target_movement_modifier = 0.05, vehicle_speed_modifier = 0.25 },
  { type = "sticker", name = "tesla-turret-slow", flags = {"not-on-map"}, hidden = true, duration_in_ticks = 120, target_movement_modifier = 0.5,  vehicle_speed_modifier = 0.75 }
  ```

### 5.6 Items, recipes and unlocks (for balancing)
- **gun-turret**: item stack 50 (B/prototypes/item.lua:4594). Recipe: 10 iron-gear-wheel, 10 copper-plate, 20 iron-plate, 8 s (B/prototypes/recipe.lua:687). Unlocked by technology `gun-turret` (B/prototypes/technology.lua:2283).
- **laser-turret**: stack 50 (item.lua:4606). Recipe: 20 steel-plate, 20 electronic-circuit, 12 battery, 20 s (recipe.lua:646). Unlocked by technology `laser-turret` (technology.lua:3468).
- **flamethrower-turret**: stack 50 (item.lua:4619). Recipe: 30 steel, 15 gears, 10 pipe, 5 engine-unit, 20 s (recipe.lua:659). Unlocked by technology `flamethrower` (technology.lua:2965).
- **railgun-turret**: stack 10, `default_import_location = "aquilo"` (SA/prototypes/item.lua:581). Recipe category `cryogenics`: 100 quantum-processor, 30 tungsten-plate, 50 superconductor, 20 carbon-fiber, 100 fluoroketone-cold, 10 s (SA/prototypes/recipe.lua:1827). Unlocked by technology `railgun` (SA/prototypes/technology.lua:812).
- **tesla-turret**: stack 10 (SA/item.lua:1438). Recipe category `electromagnetics`: 1 teslagun, 10 supercapacitor, 10 processing-unit, 50 superconductor, 500 electrolyte, 30 s (SA/recipe.lua:2313). Unlocked by technology `tesla-weapons` (SA/technology.lua:1576).

---

## 6. Ammo items

### 6.1 API
`P:AmmoItemPrototype` (typename `ammo`):
- `ammo_category` (required).
- `ammo_type`: AmmoType | array[AmmoType] (required). With an array, each entry needs `source_type` ∈ `'default' | 'player' | 'turret' | 'vehicle'` (P:AmmoSourceType). An entity kind not covered by the array uses the **first** entry.
- `magazine_size`: default 1. "Number of shots before ammo item is consumed."
- `reload_time`: default 0.
- `shoot_protected`: default false.

`P:AmmoType`:
- `action`: Trigger.
- `target_type`: `'entity'` (default) | `'position'` | `'direction'`.
- `clamp_position`, `consumption_modifier` (1), `cooldown_modifier` (1), `energy_consumption`, `target_filter`.
- `range_modifier` (1): "Affects the range value of the shooting gun … The min_range value of the gun is unaffected."

### 6.2 Bullet magazines (category `bullet`)
All three use an **instant** delivery (no projectile entity), so a bullet hits only its target. Each has `magazine_size = 10` and `stack_size = 100`.

| item | file:line | damage | weight |
|---|---|---|---|
| firearm-magazine | B/prototypes/item.lua:4064-4118 | `{amount = 5, type = "physical"}` | 10 kg |
| piercing-rounds-magazine | item.lua:4119-4166 | `{amount = 8, type = "physical"}` | 20 kg |
| uranium-rounds-magazine | item.lua:2798-2861 | `{amount = 24, type = "physical"}` | 40 kg |

Verbatim firearm-magazine action (item.lua:4069-4108):
```lua
ammo_category = "bullet",
ammo_type =
{
  action =
  {
    {
      type = "direct",
      action_delivery =
      {
        {
          type = "instant",
          source_effects = { { type = "create-explosion", entity_name = "explosion-gunshot", only_when_visible = true } },
          target_effects =
          {
            { type = "create-entity", entity_name = "explosion-hit", offsets = {{0, 1}}, offset_deviation = {{-0.5, -0.5}, {0.5, 0.5}}, only_when_visible = true },
            { type = "damage", damage = {amount = 5, type = "physical"} },
            { type = "activate-impact", deliver_category = "bullet" }
          }
        }
      }
    }
  }
},
magazine_size = 10,
```
Recipes:
- firearm-magazine: 4 iron-plate, 1 s. It has no `enabled = false`, so it is available from the start (B/prototypes/recipe.lua:909).
- piercing-rounds-magazine: 2 firearm-magazine, 1 steel, 2 copper → 2 magazines, 6 s. Unlocked by `military-2` (recipe.lua:1177; technology.lua:2055).
- uranium-rounds-magazine: 1 piercing + 1 uranium-238, 10 s. Unlocked by `uranium-ammo` (recipe.lua:1620; technology.lua:2779).

### 6.3 Cannon shells (category `cannon-shell`)
All four fire a **projectile** with `target_type = "direction"`, `starting_speed = 1`, `direction_deviation = 0.1`, `range_deviation = 0.1`, `max_range = 30`, `min_range = 5`. The plain and uranium shells also have `range_modifier = 1.25`.

| item | file:line | projectile |
|---|---|---|
| cannon-shell | B/item.lua:3077-3113 | cannon-projectile |
| explosive-cannon-shell | item.lua:3114-3149 | explosive-cannon-projectile |
| uranium-cannon-shell | item.lua:3150-3204 | uranium-cannon-projectile |
| explosive-uranium-cannon-shell | item.lua:3205-3258 | explosive-uranium-cannon-projectile |

Cannon shells are fired by vehicles (the tank). No vanilla turret uses `cannon-shell`: the ammo_category of every turret in §5 is bullet, laser, flamethrower, railgun, tesla or rocket.

### 6.4 railgun-ammo (Space Age, category `railgun`): a line attack
SA/prototypes/item.lua:594-633:
```lua
type = "ammo",
name = "railgun-ammo",
ammo_category = "railgun",
ammo_type =
{
  target_type = "direction",
  clamp_position = true,
  action =
  {
    type = "line",
    range = 50,
    width = 1,
    range_effects =
    {
      type = "create-explosion",
      entity_name = "railgun-beam",
      only_when_visible = true
    },
    action_delivery =
    {
      type = "instant",
      target_effects =
      {
        type = "damage",
        damage = {amount = 10000, type = "physical"}
      },
      source_effects =
      {
        type = "create-explosion",
        entity_name = "explosion-gunshot",
        only_when_visible = true
      }
    }
  }
},
stack_size = 10,
weight = 200*kg
```
- No `magazine_size`, so the API default is 1.
- Recipe (SA/prototypes/recipe.lua:1850): 5 steel-plate, 10 copper-cable, 2 explosives, 25 s.

### 6.5 tesla-ammo (Space Age, category `tesla`)
SA/prototypes/item.lua:1451-1500:
- `target_type = "entity"`.
- `target_effects`: a nested `chain` (`chain-tesla-gun-chain`), then a nested `beam` (`chain-tesla-gun-beam-start`, `max_length = 30`, `duration = 30`).
- `magazine_size = 10`, `stack_size = 100`.
- Recipe (category electromagnetics): 1 supercapacitor, 1 plastic-bar, 10 electrolyte, 30 s (SA/recipe.lua:2329).

### 6.6 flamethrower-ammo
B/item.lua:2863-2911, category `flamethrower`. It uses an array `ammo_type` with `source_type = "default"` and `source_type = "vehicle"` (`consumption_modifier = 1.125`). This is the vanilla example of per-source ammo types. It is not used by the flamethrower **turret**, which takes fluid (§5.3).

---

## 7. Projectiles and piercing

`P:ProjectilePrototype` (typename `projectile`):
- `acceleration`: required.
- `action`: "Executed when the projectile hits something".
- `final_action`: "Executed when the projectile hits something, after action and only if the entity that was hit was destroyed. The projectile is destroyed right after the final_action."
- `piercing_damage`: float, default 0. "Whenever an entity is hit by the projectile, this number gets reduced by the health of the entity. If the number is then below 0, the final_action is applied and the projectile destroyed. Otherwise, the projectile simply continues to its destination."
- `direction_only`: "Setting this to true can be used to disable projectile homing behaviour".
- `hit_collision_mask`, `hit_at_collision_position`, `force_condition` (default `'all'`), `max_speed`, `turn_speed`, `animation`, `shadow`, `light`, `smoke`.

`P:ProjectileTriggerDelivery`:
- `projectile` and `starting_speed` (tiles/tick) are required.
- Optional: `max_range` (1000), `min_range`, `direction_deviation`, `range_deviation`, `starting_speed_deviation`.

Cannon projectiles in B/prototypes/entity/projectiles.lua:

| projectile | line | piercing_damage | `action` (on hit) | `final_action` |
|---|---|---|---|---|
| cannon-projectile | 426-481 (piercing 433) | 1000 | 1000 physical + 100 explosion | scorch mark |
| explosive-cannon-projectile | 748-839 (piercing 754) | 100 | 180 physical | area radius 4: 300 explosion |
| uranium-cannon-projectile | 598-653 (piercing 605) | 2200 | 2000 physical + 200 explosion | scorch mark |
| explosive-uranium-cannon-projectile | 655-746 (piercing 661) | 150 | 350 physical | area radius 4.25: 315 explosion |

Verbatim `cannon-projectile` (projectiles.lua:425-481):
```lua
{
  type = "projectile",
  name = "cannon-projectile",
  flags = {"not-on-map"},
  hidden = true,
  collision_box = {{-0.3, -1.1}, {0.3, 1.1}},
  acceleration = 0,
  direction_only = true,
  piercing_damage = 1000,
  action =
  {
    type = "direct",
    action_delivery =
    {
      type = "instant",
      target_effects =
      {
        { type = "damage", damage = {amount = 1000 , type = "physical"} },
        { type = "damage", damage = {amount = 100 , type = "explosion"} },
        { type = "create-entity", entity_name = "explosion" }
      }
    }
  },
  final_action = { type = "direct", action_delivery = { type = "instant", target_effects = { { type = "create-entity", entity_name = "small-scorchmark-tintable", check_buildability = true } } } },
  animation = { filename = "__base__/graphics/entity/bullet/bullet.png", draw_as_glow = true, width = 3, height = 50, priority = "high" }
},
```
`shotgun-pellet` and `piercing-shotgun-pellet` do 8 physical each and have no `piercing_damage` (projectiles.lua:20-49, 395-424). "Piercing" in the pellet's name is flavour only.

Runtime: `create_entity` for a `projectile` accepts `speed`, `max_range`, `base_damage_modifiers` and `bonus_damage_modifiers` (R:LuaSurface.create_entity, variant group `projectile`).

---

## 8. Beams

`P:BeamPrototype` (typename `beam`):
- Required: `damage_interval` ("can't be 0"), `width` and `graphics_set` (BeamGraphicsSet).
- `action`.
- `action_triggered_automatically`: default false. "If false, the action is instead triggered when its owner triggers shooting".
- `random_target_offset`, `target_offset`.

`P:BeamGraphicsSet`:
- `beam` and `ground`: each a BeamAnimationSet with `start`, `ending`, `head`, `tail`, `body`, `render_layer`.
- `desired_segment_length`, `randomize_animation_per_segment`, `transparent_start_end_animations`, `water_reflection`.
- None of these fields is required.

`P:BeamTriggerDelivery`:
- `beam` (required).
- `max_length`, `duration` (uint32 ticks).
- `add_to_shooter` (default true), `destroy_with_source_or_target` (default true).
- `source_offset`.

Vanilla beams:
- **laser-beam** (B/prototypes/entity/beams.lua:3-190): `width = 0.5`, `damage_interval = 20`, `random_target_offset = true`, `action_triggered_automatically = false`, damage `{ amount = 10, type = "laser"}`.
- **make_electric_beam(name, sound, damage)** (B/…/beams.lua:372): the same pattern with `type = "electric"` damage.
- **Tesla beams** (SA/prototypes/entity/beams.lua:247-366): `make_tesla_beam` / `make_tesla_beam_chain` apply four effects: `damage {amount=damage, type="electric"}`, `push-back` (0.5 for the start beam, 0.25 for chain bounces), then `create-sticker tesla-turret-stun` and `tesla-turret-slow`. The instances are:
  ```lua
  make_chain_tesla_beams("chain-tesla-turret-beam-start", "chain-tesla-turret-beam-bounce", true, 120)
  make_chain_tesla_beams("chain-tesla-gun-beam-start", "chain-tesla-gun-beam-bounce", true, 30)
  ```
  So each tesla-turret beam hit does 120 electric damage and each tesla-gun beam hit does 30.

---

## 9. Chain attacks (tesla): `chain-active-trigger`

`P:ChainActiveTriggerPrototype` (typename `chain-active-trigger`, parent ActiveTriggerPrototype):

| property | default |
|---|---|
| `action` | — |
| `max_jumps` | 5 |
| `max_range_per_jump` | 5 |
| `max_range` | infinity |
| `jump_delay_ticks` | 0 |
| `fork_chance` | 0 (range 0..1) |
| `fork_chance_increase_per_quality_level` | 0.1 |
| `max_forks` | max uint32 |
| `max_forks_per_jump` | 1 |

`P:ChainTriggerDelivery` = `{type = 'chain', chain: ActiveTriggerID}`.

Vanilla definitions (SA/prototypes/active-triggers.lua:1-31):
```lua
local function make_tesla_chain_lightning_chain(name, beam_name, max_jumps, jump_range, fork_chance, fork_chance_per_quality, beam_duration)
  return {
    name = name,
    type = "chain-active-trigger",
    max_jumps = max_jumps,
    max_range_per_jump = jump_range,
    jump_delay_ticks = 6,
    fork_chance = fork_chance,
    fork_chance_increase_per_quality_level = fork_chance_per_quality,
    action =
    {
      type = "direct",
      action_delivery =
      {
        type = "beam",
        beam = beam_name,
        max_length = jump_range + 0.5,
        duration = beam_duration,
        add_to_shooter = false,
        destroy_with_source_or_target = false,
        source_offset = {0, 0}, -- should match beam's target_offset
      },
    },
  }
end

data:extend(
{
  make_tesla_chain_lightning_chain("chain-tesla-turret-chain", "chain-tesla-turret-beam-bounce", 10, 12, 0.05, 0.05, 30),
  make_tesla_chain_lightning_chain("chain-tesla-gun-chain", "chain-tesla-gun-beam-bounce", 12, 12, 0.3, 0.05, 30),
})
```
- The ordering comment appears in both the turret and the ammo: "Chain effect must go first in case the beam kills the target" (SA/.../turrets.lua:721; SA/item.lua:1467).
- Load order in Space Age: `active-triggers` is required at SA/data.lua:3, before `entity.beams` at :5 and `entity.turrets` at :14.

---

## 10. Railgun "beam" = line trigger plus a rotated explosion

`P:LineTriggerItem`:
- Required: `type = 'line'`, `range` and `width`.
- Optional: `range_effects` (TriggerEffect).
- Plus the TriggerItem base fields: `action_delivery`, `collision_mask`, `force`, `trigger_target_mask`, `repeat_count`, `probability`, `entity_flags`, `ignore_collision_condition`.

The visible "beam" is a hidden `explosion` entity, `rotate = true, beam = true` (SA/prototypes/entity/explosions.lua:701-727):
```lua
{
  type = "explosion",
  name = "railgun-beam",
  localised_name = {"entity-name.railgun-beam"},
  flags = {"not-on-map"},
  hidden = true,
  subgroup = "explosions",
  rotate = true,
  beam = true,
  animations = { { filename = "__space-age__/graphics/entity/railgun-turret/railgun-beam.png", priority = "extra-high", width = 64, height = 440, frame_count = 16, animation_speed = 1, draw_as_glow = true, blend_mode = "additive" } },
  light = {intensity = 2, size = 20, color = {r = 0.55, g = 0.9, b = 0.9}},
  smoke = "smoke-fast",
  smoke_count = 2,
  smoke_slow_down_factor = 1
},
```
`P:ExplosionPrototype`: `animations` is required, and `beam` and `rotate` both default to false.

The line's damage (10000 physical, §6.4) is applied through `action_delivery.instant.target_effects` to each entity in the line. Whether friendly entities in the line are hit is not stated in the ammo. The API's `true_collinear_ejection` description mentions avoiding "unexpected friendly fire incidents", and `TriggerItem.force` can restrict it.

---

## 11. Walls and gates

### 11.1 API
`P:WallPrototype` (typename `wall`), all optional:
- `pictures`: WallPictures.
- `visual_merge_group`: uint32, default 0. "Different walls will visually connect to each other if their merge group is the same".
- `connected_gate_visualization`: Sprite.
- `wall_diode_green` / `wall_diode_red`: Sprite4Way, plus `wall_diode_*_light_top/right/bottom/left`: LightDefinition.
- `circuit_connector`, `circuit_wire_max_distance`, `default_output_signal`, `draw_circuit_wires`, `draw_copper_wires`.

`P:WallPictures` keys (all optional):
- SpriteVariations: `single`, `straight_vertical`, `straight_horizontal`, `corner_right_down`, `corner_left_down`, `t_up`, `ending_right`, `ending_left`, `filling`.
- Sprite4Way: `water_connection_patch`, `gate_connection_patch`.

`P:GatePrototype` (typename `gate`):
- Required: `activation_distance`, `opening_speed`, `timeout_to_close`.
- Optional: `fadeout_interval`, `vertical_animation`, `horizontal_animation`, `horizontal_rail_animation_left`/`_right`, `vertical_rail_animation_left`/`_right`, `horizontal_rail_base`, `vertical_rail_base`, `wall_patch`, `opening_sound`, `closing_sound`, `opened_collision_mask`.

### 11.2 stone-wall
B/prototypes/entity/entities.lua:3364-3816:
```lua
type = "wall",
name = "stone-wall",
flags = {"placeable-neutral", "player-creation"},
collision_box = {{-0.29, -0.29}, {0.29, 0.29}},
selection_box = {{-0.5, -0.5}, {0.5, 0.5}},
damaged_trigger_effect = hit_effects.wall(),
minable = {mining_time = 0.2, result = "stone-wall"},
fast_replaceable_group = "wall",
max_health = 350,
repair_speed_modifier = 2,
corpse = "wall-remnants",
dying_explosion = "wall-explosion",
impact_category = "stone",
connected_gate_visualization =
{
  filename = "__core__/graphics/arrows/underground-lines.png",
  priority = "high",
  width = 64,
  height = 64,
  scale = 0.5
},
resistances =
{
  { type = "physical",  decrease = 3,  percent = 20 },
  { type = "impact",    decrease = 45, percent = 60 },
  { type = "explosion", decrease = 10, percent = 30 },
  { type = "fire",      percent = 100 },
  { type = "acid",      percent = 80 },
  { type = "laser",     percent = 70 }
},
visual_merge_group = 0, -- different walls will visually connect to each other if their merge group is same (defaults to 0)
pictures = { single = {...}, straight_vertical = {...}, straight_horizontal = {...}, corner_right_down = {...}, corner_left_down = {...}, t_up = {...}, ending_right = {...}, ending_left = {...}, filling = {...}, water_connection_patch = { sheets = {...} }, gate_connection_patch = { sheets = {...} } },
wall_diode_green = { sheet = { filename = "__base__/graphics/entity/wall/wall-diode-green.png", ... } },
...
circuit_connector = circuit_connector_definitions["wall"],
circuit_wire_max_distance = default_circuit_wire_max_distance,
default_output_signal = {type = "virtual", name = "signal-G"}
```
Line anchors:
- `connected_gate_visualization` at :3411, `resistances` at :3419, `pictures` at :3450, `wall_diode_green` at :3719, `circuit_connector` at :3813.
- The picture variation counts are 2, 5, 6, 2, 2, 4, 2, 2 and 8 (filling), from `variation_count` in :3450-3716.
- `circuit_connector_definitions["wall"]` is `create_single` (CORE/lualib/circuit-connector-generated-definitions.lua:584).
- Stone-wall has **no electric resistance entry**.

Item: stack 100 (B/item.lua:568). Recipe: 5 stone-brick (B/recipe.lua:1031). Unlocked by technology `stone-wall` (technology.lua:2551).

### 11.3 gate
B/…/entities.lua:4917-5163:
```lua
type = "gate",
name = "gate",
flags = {"placeable-neutral","placeable-player", "player-creation"},
fast_replaceable_group = "wall",
minable = {mining_time = 0.1, result = "gate"},
max_health = 350,
collision_box = {{-0.29, -0.29}, {0.29, 0.29}},
selection_box = {{-0.5, -0.5}, {0.5, 0.5}},
opening_speed = 0.0666666,
activation_distance = 3,
timeout_to_close = 5,
fadeout_interval = 15,
resistances = -- identical list to stone-wall (physical 3/20, impact 45/60, explosion 10/30, fire 100, acid 80, laser 70)
vertical_animation = { layers = { { filename = "__base__/graphics/entity/gate/gate-vertical.png", line_length = 8, width = 78, height = 120, frame_count = 16, ... }, {...shadow...} } },
horizontal_animation = {...}, horizontal_rail_animation_left/right = {...}, vertical_rail_animation_left/right = {...},
vertical_rail_base = {...}, horizontal_rail_base = {...}, wall_patch = {...},
opening_sound = sounds.gate_open,
closing_sound = sounds.gate_close
```
- All gate animations have `frame_count = 16` (entities.lua:4965-5160).
- Item: stack 50 (B/item.lua:913).
- Recipe: 1 stone-wall, 2 steel-plate, 2 electronic-circuit (B/recipe.lua:1210). Unlocked by technology `gate` (technology.lua:2571).
- Gate and wall share `fast_replaceable_group = "wall"`.

For a new wall to be an upgrade target, `P:EntityPrototype.next_upgrade` says: "The upgrade target entity needs to have the same bounding box, collision mask, and fast replaceable group as this entity".

---

## 12. Enemies relevant to combat tests (base game)

B/prototypes/entity/enemies.lua. All units use `ai_settings = biter_ai_settings`, which is:
```lua
return { destroy_when_commands_fail = true, allow_try_return_to_spawner = true }
```
(B/prototypes/entity/biter-ai-settings.lua)

Biters' `attack_parameters` are `type="projectile"`, `ammo_category="melee"`, `range_mode="bounding-box-to-bounding-box"`. Their `ammo_type` is `make_unit_melee_ammo_type(N)`, which does N physical damage (enemies.lua:12-29).

| unit | line | max_health | healing/tick | resistances | attack | speed | vision |
|---|---|---|---|---|---|---|---|
| small-biter | 35 | 15 | 0.01 | `{}` | melee 7 phys, range 0.5, cd 35 | 0.2 | 30 |
| medium-biter | 260 | 75 | 0.01 | physical 4/10 %, explosion 10 % | melee 15, range 1, cd 35 | 0.24 | 30 |
| big-biter | 318 | 375 | 0.02 | physical 8/10 %, explosion 10 % | melee 30, range 1.5, cd 35 | 0.23 | 30 |
| behemoth-biter | 377 | 3000 | 0.1 | physical 12/10 %, explosion 12/10 % | melee 90, range 1.5, cd 50 | 0.3 | 30 |
| small-spitter | 437 | 10 | 0.01 | `{}` | acid stream, range 13, cd 100, dmg_mod 12 | 0.185 | 30 |
| medium-spitter | 489 | 50 | 0.01 | explosion 10 % | range 14, dmg_mod 24 | 0.165 | 30 |
| big-spitter | 545 | 200 | 0.01 | explosion 15 % | range 15, dmg_mod 36 | 0.15 | 30 |
| behemoth-spitter | 602 | 1500 | 0.1 | explosion 30 % | range 16, dmg_mod 60 | 0.15 | 30 |
| biter-spawner (unit-spawner) | 93 | 350 | 0.02 | physical 2/15 %, explosion 5/0, fire 3/60 % | — | — | — |

Notes on the table:
- Resistance cells are written `decrease/percent`.
- Spitter ranges and damage modifiers come from B/prototypes/entity/enemy-constants.lua:70-73 and :85-88.
- Spitter `attack_parameters` (B/prototypes/entity/enemy-projectiles.lua:6-45) are `type = "stream"`, `ammo_category = "biological"`, `warmup = 30`, with an `ammo_type` stream `data.acid_stream_name`. The acid stream's area effect does `{amount = 1, type = "acid"}` (enemy-projectiles.lua:266-267). How that 1 combines with `damage_modifier` 12-60 is not stated in sources.
- **Only the biter resistances are physical/explosion. No base biter or spitter resists laser, electric or fire.**
- Grepping space-age and quality for these unit names or `data.raw.unit` edits finds no changes to base biter or spitter stats. The only hits are unrelated item effects at SA/item.lua:1050, :1066.

---

## 13. Runtime: spawning, holding still, measuring (runtime-api.json)

### 13.1 Spawning
`R:LuaSurface.create_entity{name, position, force?, ...}`:
- `force` is documented as "Force of the entity, default is enemy."
- `quality` defaults to `normal`.
- It returns the LuaEntity, or `nil` on failure.

Vanilla example (B/menu-simulations/menu-simulations.lua:677-679):
```lua
local biter = game.surfaces[1].create_entity{name = "small-biter", position = {center[1] - 40, center[2] + 4.5}}
biter.speed = character.character_running_speed
biter.commandable.set_command{type = defines.command.go_to_location, destination = {center[1] + 60, center[2] + 4.5}, distraction = defines.distraction.none}
```

### 13.2 Keeping units from moving or acting
Options, each with the API text:

- **`R:LuaEntity.active`** (boolean, read/write). "Deactivating an entity will stop all its operations (car will stop moving, inserters will stop working, fish will stop moving etc)." However: "**Writing to this is deprecated** and affects only the disabled_by_script state."
- **`R:LuaEntity.disabled_by_script`** (boolean, read/write; subclass UpdatableEntity). This is the non-deprecated switch. Writes are ignored for non-updatable entities; check `R:LuaEntity.is_updatable`.
  - Side effect: `P:EntityWithHealthPrototype.healing_per_tick` says "The entity must be active for this to work". A disabled biter should therefore not regenerate, which helps HP-delta measurements. This is an inference from the prototype doc.
  - Whether turrets target a deactivated unit and whether it takes damage: **not found in sources**. Verify on the test bench.
- **`R:LuaEntity.commandable`** (LuaCommandable or nil; "Units and SpiderUnits are commandable"). `R:LuaCommandable.set_command(Command)`. The `Command` concept (runtime-api `concepts`) has the variant `defines.command.stop` with fields:
  - `distraction`: defaults to `defines.distraction.by_enemy`.
  - `ticks_to_wait`: "Default is max uint64, which means stop forever".

  `defines.distraction` values: `by_anything`, `by_damage`, `by_enemy`, and `none` ("Perform command even if someone attacks the unit."). To make a unit stand still even when shot:
  ```lua
  unit.commandable.set_command{type = defines.command.stop, distraction = defines.distraction.none}
  ```
  Other `defines.command` values: attack, attack_area, build_base, compound, flee, go_to_location, group, stop, wander.
- **`R:LuaEntity.ai_settings`** (LuaAISettings; subclasses Unit, SpiderUnit). Writable fields:
  - `allow_destroy_when_commands_fail`: "units that repeatedly fail to succeed at commands will be destroyed". Vanilla biters have it **on** (biter-ai-settings.lua), so set it false in tests.
  - `allow_try_return_to_spawner`, `do_separation`, `join_attacks`, `path_resolution_modifier`, `size_in_group`.
- **`R:LuaEntity.speed`**: "the maximum speed if this is a unit … Only the speed of units, cars, and projectiles are writable." Whether `speed = 0` is accepted: not found in sources.
- **Force and map level:**
  - `R:LuaForce.ai_controllable`: "Setting this to false does not turn off biters' AI".
  - `R:LuaForce.set_cease_fire(other, cease_fire)`: "Forces on the cease fire list won't be targeted for attack." Example: `game.forces.enemy.set_cease_fire("player", true)`. Whether turret targeting remains one-directional is not stated.
  - `R:LuaForce.set_friend`.
  - `R:LuaSurface.peaceful_mode`, `R:LuaSurface.no_enemies_mode`.
  - `game.map_settings.enemy_expansion.enabled`, `game.map_settings.enemy_evolution.enabled` (concept MapSettings: "members of the dictionary that is returned can be modified mid-game").
  - `R:LuaForce.set_evolution_factor(factor, surface?)`.
- **`R:LuaEntity.destructible`**: "If set to false, this entity can't be damaged and won't be attacked automatically." Use it to protect test turrets or walls, not targets.

### 13.3 Supplying turrets in tests
- Ammo:
  - `R:LuaControl.insert(items)` (LuaEntity inherits LuaControl; runtime-api `classes.LuaEntity.parent = "LuaControl"`).
  - Or `R:LuaControl.get_inventory(defines.inventory.turret_ammo)`. The defines list includes `turret_ammo`, `artillery_turret_ammo`, `car_ammo` and others.
- Fluid: `R:LuaEntity.insert_fluid{name=..., amount=...}`, `R:LuaEntity.fluidbox`.
- Energy:
  - `R:LuaEntity.energy` (read/write buffer).
  - Base has an `electric-energy-interface` entity with `energy_production = "500GW"` and `buffer_capacity = "10GJ"` (B/prototypes/entity/entities.lua:8539-8561).
  - Or define the test turret with a `void` energy source (P:ElectricTurretPrototype.energy_source).
- `R:LuaEntity.shooting_target` (Turret): read/write, "Can't be set to nil via script".
- `create_entity` variant groups for `ammo-turret`, `electric-turret` and `fluid-turret` accept `priority-list` and `ignore-unprioritised`.

### 13.4 Measuring damage
- **`defines.events.on_entity_damaged`** (runtime-api `events`):
  - Fields: `entity`, `damage_type` (LuaDamagePrototype), `original_damage_amount` ("before resistances"), `final_damage_amount` ("after resistances"), `final_health`, `cause`, `source`, `force`, `tick`.
  - "This is not called when an entities health is set directly by another mod."
  - Filter `LuaEntityDamagedEventFilter` supports `type`, `name`, `damage-type`, `original-damage-amount`, `final-damage-amount`, `final-health`, and others.
- **`on_entity_died`**: `entity`, `cause`, `damage_type`, `force`, `loot`.
- **`R:LuaEntity.damage(damage, force, type?, source?, cause?)`**: `type` defaults to `"impact"`. Returns "the total damage actually applied after resistances". Useful to verify resistance tables directly.
- Other entity members:
  - `R:LuaEntity.health` (writable, clamped).
  - `R:LuaEntity.get_health_ratio()`.
  - `R:LuaEntity.max_health`.
  - `R:LuaEntity.die(force?, cause?)`.
- Prototype introspection:
  - `R:LuaEntityPrototype.attack_parameters`.
  - `R:LuaEntityPrototype.turret_range`.
  - `R:LuaEntityPrototype.resistances`: a dictionary keyed by damage type.
  - `R:LuaEntityPrototype.get_max_health(quality?)`.
  - `R:LuaItemPrototype.get_ammo_type(ammo_source_type?)`, where the argument is 'default' | 'player' | 'turret' | 'vehicle'.
  - `R:LuaItemPrototype.magazine_size`.

---

## 14. Damage and speed upgrade technologies

### 14.1 API semantics
- **`P:AmmoDamageModifier`** `{type='ammo-damage', ammo_category, modifier: double}`: "Modification value, which will be added to the current ammo damage modifier upon researching."
- **`P:GunSpeedModifier`** `{type='gun-speed', ammo_category, modifier}`: "added to the current gun speed modifier".
- **`P:TurretAttackModifier`** `{type='turret-attack', turret_id: EntityID, modifier}`: "added to the current turret attack modifier". `turret_id` is "Name of the EntityPrototype that is affected. This also works for non-turrets such as tanks, however, the bonus does not appear in the entity's tooltips."
- **Runtime equivalents** (R:LuaForce): `get/set_ammo_damage_modifier(ammo)`, `get/set_gun_speed_modifier(ammo)` and `get/set_turret_attack_modifier(turret)`. The first two take an ammo category name; the last takes a turret prototype name.
- `R:LuaTechnology.researched`: switching false→true "will trigger the technology advancement perks". `R:LuaForce.reset_technology_effects()`.
- The exact damage formula (how `ammo-damage`, `turret-attack`, the attack parameters' `damage_modifier` and quality combine) is **not found in sources**. The API only states that each modifier is additive into its own accumulator. Measure it with `on_entity_damaged`.

### 14.2 Base chains
Extracted by `tools/techfx.py` from B/prototypes/technology.lua.

| tech | line | effects |
|---|---|---|
| physical-projectile-damage-1 | 168 | ammo-damage bullet +0.1; turret-attack gun-turret +0.1; ammo-damage shotgun-shell +0.1 |
| physical-projectile-damage-2 | 202 | same, +0.1 each |
| physical-projectile-damage-3 | 321 | bullet +0.2; gun-turret +0.2; shotgun +0.2 |
| physical-projectile-damage-4 | 357 | +0.2 / +0.2 / +0.2 |
| physical-projectile-damage-5 | 393 | +0.2 / +0.2 / +0.2; **cannon-shell +0.9** |
| physical-projectile-damage-6 | 435 | bullet +0.4; gun-turret +0.4; shotgun +0.4; cannon +1.3 |
| physical-projectile-damage-7 | 478 | bullet +0.4; gun-turret +0.7; shotgun +0.4; cannon +1; `max_level = "infinite"`, `count_formula = "2^(L-7)*1000"` |
| weapon-shooting-speed-1 / -2 | 237 / 266 | gun-speed bullet & shotgun +0.1 / +0.2 |
| weapon-shooting-speed-3 / -4 | 1192 / 1228 | bullet, shotgun +0.2/+0.3; rocket +0.5/+0.7 |
| weapon-shooting-speed-5 | 1264 | bullet +0.3, shotgun +0.4, **cannon-shell +0.8**, rocket +0.9 |
| weapon-shooting-speed-6 | 1306 | bullet +0.4, shotgun +0.4, cannon +1.5, rocket +1.3 |
| laser-weapons-damage-1..4 | 973-1054 | ammo-damage laser +0.2, +0.2, +0.3, +0.4 |
| laser-weapons-damage-5 / 6 / 7 | 1081 / 1114 / 1152 | laser +0.5 & beam +0.4 / laser +0.7, electric +0.7, beam +0.6 / laser +0.7, electric +0.7, beam +0.3 (7 is infinite) |
| laser-shooting-speed-1..7 | 1349-1513 | gun-speed laser +0.1, 0.2, 0.3, 0.3, 0.4, 0.4, 0.5 |
| refined-flammables-1..7 | 745-938 | ammo-damage flamethrower + turret-attack flamethrower-turret: 0.2, 0.2, 0.2, 0.3, 0.3, 0.4, 0.2 (7 is infinite) |
| stronger-explosives-1..7 | 296-705 | grenade / landmine / rocket |

Verbatim physical-projectile-damage-1 (B/prototypes/technology.lua:167-200):
```lua
{
  type = "technology",
  name = "physical-projectile-damage-1",
  icons = util.technology_icon_constant_damage(physical_projectile_damage_1_icon),
  effects =
  {
    { type = "ammo-damage", ammo_category = "bullet", modifier = 0.1 },
    { type = "turret-attack", turret_id = "gun-turret", modifier = 0.1 },
    { type = "ammo-damage", ammo_category = "shotgun-shell", modifier = 0.1 }
  },
  prerequisites = {"military"},
  unit = { count = 100 * 1, ingredients = { {"automation-science-pack", 1} }, time = 30 },
  upgrade = true
},
```

**Which vanilla upgrades a turret receives:**
- The gun-turret gets both `ammo-damage[bullet]` (through its ammo) and `turret-attack[gun-turret]` (by name).
- A new bullet-category turret would get only `ammo-damage[bullet]` and `gun-speed[bullet]`. It gets no `turret-attack` bonus unless the mod adds `turret-attack` effects with its own `turret_id`.
- The laser-turret gets `ammo-damage[laser]` and `gun-speed[laser]`.
- The flamethrower-turret gets `ammo-damage[flamethrower]` and `turret-attack[flamethrower-turret]`.

### 14.3 Space Age changes
SA/base-data-updates.lua (runs from SA/data.lua:65):
```lua
data.raw.technology["physical-projectile-damage-6"].effects[1].modifier = 0.2
data.raw.technology["physical-projectile-damage-6"].effects[2].modifier = 0.2
data.raw.technology["physical-projectile-damage-7"].effects[1].modifier = 0.2
data.raw.technology["physical-projectile-damage-7"].effects[2].modifier = 0.2
data.raw.technology["physical-projectile-damage-7"].prerequisites = {"physical-projectile-damage-6", "space-science-pack"}
```
(:413-417). `laser-weapons-damage-5/6/7` effects are **replaced** with a single laser entry (+0.5 / +0.7 / +0.7) (:476-503).

New Space Age technologies (SA/prototypes/technology.lua):

| tech | line | effects |
|---|---|---|
| electric-weapons-damage-1 | 57 | beam +0.3 |
| electric-weapons-damage-2 | 85 | beam +0.4 |
| electric-weapons-damage-3 | 114 | **tesla +0.7**, electric +0.7, beam +0.6; prerequisite `tesla-weapons` |
| electric-weapons-damage-4 | 154 | tesla +0.7, electric +0.7, beam +0.3; infinite, `2^(L-3)*1000` |
| railgun-damage-1 | 263 | ammo-damage railgun +0.4; infinite |
| railgun-shooting-speed-1 | 230-261 | gun-speed railgun +0.15; infinite; custom `icon` on the effect |

---

## 15. Practical recipe for a Magnetics turret, wall and ammo

These are inferences built from the facts above. They are not engine guarantees.

1. **Clone vanilla prototypes** to get valid graphics without new pngs:
   ```lua
   local t = table.deepcopy(data.raw["ammo-turret"]["gun-turret"])
   t.name = ...
   t.minable.result = ...
   ```
   Then edit `attack_parameters`. The data stage has `util.table.deepcopy` (used in B/prototypes/entity/fire.lua).
2. **Magnetic ammo in category `bullet`** gets all vanilla bullet upgrades for free (§14.2). A **new category** needs:
   - its own `ammo-category` with `bonus_gui_order`;
   - its own `ammo-damage` and `gun-speed` effects, appended to existing technologies (never prepended; see the Space Age index writes at §14.3), or placed on new technologies.
3. **Piercing coil-gun projectile**: use `piercing_damage` on a `projectile` delivered with `target_type = "direction"` and `direction_only = true`, as cannon shells do (§6.3, §7). For a hitscan rail line, use `type = "line"` as railgun-ammo does (§6.4).
4. **Chain or arc effects without Space Age**: `chain-active-trigger` is a core prototype type documented in the 2.0.77 API (`P:ChainActiveTriggerPrototype`). Nothing in the sources says it needs Space Age. The vanilla chain and beam instances, however, exist only when Space Age is active. A base-only mod must define its own chain and beam prototypes and cannot reference `chain-tesla-*` or `tesla-turret-stun`.
5. **Electric damage**: no base biter or spitter resists `electric` (§12), and stone-wall/gate have no electric resistance entry (§11).
6. **Walls**: copy `stone-wall` and change `name`, `resistances` and `max_health`. Keep `fast_replaceable_group = "wall"` and the same `collision_box`, so that `stone-wall.next_upgrade` can point to the new wall (§11.3). `visual_merge_group` controls whether it visually joins stone walls.

---

## 16. Not found in sources (do not assume)

- The formula that combines resistance `decrease` and `percent`.
- How `ammo-damage`, `turret-attack`, `attack_parameters.damage_modifier`, `StreamFluidProperties.damage_modifier` and quality combine into final damage.
- How the acid stream's 1 damage combines with spitter `damage_modifier` values.
- Whether a unit with `disabled_by_script = true` (or `active = false`) is targeted by turrets and whether it takes damage.
- Whether `LuaEntity.speed = 0` is valid for units.
- Whether `set_cease_fire` on the enemy force still lets player turrets fire at it (the API only says cease-fire forces "won't be targeted").
- What the engine does with `heating_energy` when the `freezing` feature flag is off (base-only game).
- Mod load-order rules relative to Space Age (dependency order and alphabetical order). Only the internal order of Space Age's `data.lua` is visible (SA/data.lua).
- Which properties `QualityPrototype.default_multiplier` applies to. The API documents only `range_multiplier`: "Affects the range of attack parameters, e.g. those used by combat robots, units, guns and turrets", default `min(1 + 0.1 * level, 3)`.
