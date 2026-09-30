# Recon: technologies, items, groups, locale, info.json — Factorio 2.0.77

Scope: reference for the "Magnetics" mod (base-only AND base+quality+elevated-rails+space-age).
All paths below are relative to `/opt/factorio/data/` unless they start with `/opt/factorio-api/`.
"API" = `/opt/factorio-api/prototype-api.json` (application_version 2.0.77, stage "prototype") or
`/opt/factorio-api/runtime-api.json` (2.0.77, stage "runtime").

## 0. Method and how far to trust the tables

* Prototype facts are quoted from the Lua sources and from the API JSON.
* The tech/item/group tables were produced by **running the real data-stage Lua** (core `dataloader.lua`,
  `core/data.lua`, then `data.lua` → `data-updates.lua` → `data-final-fixes.lua` of every mod, in the assumed order base, elevated-rails, quality, space-age — stage order is an assumption, see §9.2) inside Lua 5.2 (python `lupa`),
  with a `require` that resolves `__mod__/...`, mod-root-relative and `core/lualib` paths. Emulator:
  `/tmp/claude-0/-home-user-Neu/5dc61be6-6c38-58c2-939b-4b416832b0f1/scratchpad/recon/work/emu.py`; dumps: `work/base.json`
  (base only), `work/bq.json` (base+quality), `work/be.json` (base+elevated-rails), `work/sa.json` (base, elevated-rails, quality, space-age).
  - Stubs/assumptions in the emulator: `defines` built from `runtime-api.json` (define values are only ordinals, not engine values);
    `defines.default_icon_size = 64` is an **assumption** — the define exists in both API files (`defines[name="default_icon_size"]`)
    but its value is not given there; 64 is `IconData.icon_size`'s documented default. `feature_flags` set per active mods;
    `mods`/`settings.startup` minimal; `log`, `serpent` stubbed. Engine-side post-processing (defaults applied by C++) is NOT reproduced.
  - Sanity checks passed: in both base and SA dumps every tech prerequisite and every `unlock-recipe` target exists (0 dangling refs).
  - Counts: base 196 technologies, 7 tools, 11 item-groups, 113 item-subgroups; base+quality 202 techs; base+elevated-rails 197; full SA 275 techs, 12 tools, 12 groups, 136 subgroups.
* Headless data has **no PNG files at all** (`find /opt/factorio/data -name '*.png'` → 0; only `core/graphics/background-image.jpg`
  and shader/lua files remain). Icon paths in Lua therefore cannot be checked against files here.
* ru and de locale folders **exist** in headless data: `base/locale/ru/base.cfg`, `base/locale/de/base.cfg`,
  `base/locale/en/base.cfg` (UTF-8, no BOM; checked with `od -c`), likewise `core/locale/{ru,de}/core.cfg`,
  `space-age/locale/{ru,de}/space-age.cfg`, `quality/locale/ru/quality.cfg`, `elevated-rails/locale/ru/elevated-rails.cfg`.
  56 language folders under `base/locale/`.

---

## 1. Technology prototype (`type = "technology"`)

### 1.1 Fields (API `prototypes[name=TechnologyPrototype]`, parent `Prototype` → `PrototypeBase`)

| field | type | req/opt, default | note (API text, abridged) |
|---|---|---|---|
| `name` | string | REQ | "If this name ends with `-<number>`, that number is ignored for localization purposes. E.g. if the name is `technology-3`, the game looks for the `technology-name.technology` localization. The technology tree will also show the number on the technology icon." |
| `icons` | array[IconData] | opt | "Can't be an empty array." |
| `icon` | FileName | opt | "Only loaded, and mandatory if `icons` is not defined." |
| `icon_size` | SpriteSizeType | opt, **default 64** | "The base game uses 256px icons for technologies." → a 256px PNG **must** set `icon_size = 256`. |
| `upgrade` | boolean | opt, false | "When set to true, and the technology contains several levels, only the relevant one is displayed in the technology screen." |
| `enabled` | boolean | opt, true | not reloaded into existing saves |
| `essential` | boolean | opt, false | shown with "Show only essential technologies" |
| `visible_when_disabled` | boolean | opt, false | |
| `ignore_tech_cost_multiplier` | boolean | opt, false | |
| `allows_productivity` | boolean | opt, true | |
| `research_trigger` | TechnologyTrigger | opt | "Mandatory if `unit` is not defined." |
| `unit` | TechnologyUnit | opt | "Mandatory if `research_trigger` is not defined." (Whether both may be set at once: not found in sources.) |
| `max_level` | uint32 \| "infinite" | opt | defaults to the level of the tech |
| `prerequisites` | array[TechnologyID] | opt | |
| `show_levels_info` | boolean | opt | |
| `effects` | array[Modifier] | opt | applied when researched |
| `hidden` | boolean | opt, false | |
| inherited from PrototypeBase | `order`, `localised_name`, `localised_description`, `factoriopedia_description`, `subgroup`, `hidden_in_factoriopedia`, `parameter`, `factoriopedia_simulation`; from Prototype: `factoriopedia_alternative`, `custom_tooltip_fields` | | PrototypeBase `name`: "May only contain alphanumeric characters, dashes and underscores. May not exceed a length of 200 characters." |

**TechnologyUnit** (API `types[name=TechnologyUnit]`): "Either `count` or `count_formula` must be defined, never both."
* `count` uint64 (>0) · `count_formula` MathExpression — "If the last characters of the prototype name are `-<number>`, the level is taken to be the number … This defaults to `1`." Variables `L`/`l` = level (MathExpression doc: "in TechnologyUnit::count_formula `L` and `l` may be used for the technology level"); operators `+ - * / ^ ( )`, functions `abs log2 sign max min`.
* `time` double REQ (seconds per unit at lab speed 1) · `ingredients` array[ResearchIngredient] REQ; ResearchIngredient = tuple(ItemID, uint16), "The items must all be ToolPrototypes", amount ≠ 0.

**TechnologyTrigger** (new in 2.0; API `types[name=TechnologyTrigger]`, union by `type`):

| `type` | fields |
|---|---|
| `"mine-entity"` | `entity` EntityID (REQ) |
| `"craft-item"` | `item` ItemIDFilter (REQ), `count` ItemCountType (opt, default 1) |
| `"craft-fluid"` | `fluid` FluidID (REQ), `amount` double (opt, default 0) |
| `"send-item-to-orbit"` | `item` ItemIDFilter (REQ) |
| `"capture-spawner"` | `entity` EntityID (opt) |
| `"build-entity"` | `entity` EntityIDFilter (REQ) |
| `"create-space-platform"` | — |
| `"scripted"` | `trigger_description` LocalisedString, `icon`/`icons`/`icon_size` (opt); fired only by `LuaForce::script_trigger_research` |

**Modifier** (`effects[]`) — all variants in API `types[name=Modifier]` (every variant also accepts `icon`/`icons`/`icon_size`/`hidden`/`use_icon_overlay_constant`):

| `type` string | payload |
|---|---|
| `unlock-recipe` | `recipe` (REQ) |
| `unlock-space-location` | `space_location` |
| `unlock-quality` | `quality` |
| `give-item` | `item`, `count?`, `quality?` |
| `ammo-damage` / `gun-speed` | `ammo_category`, `modifier`, `infer_icon?` |
| `turret-attack` | `turret_id`, `modifier`, `infer_icon?` |
| `change-recipe-productivity` | `recipe`, `change` |
| `nothing` | `effect_description?` |
| SimpleModifier (`modifier` double): `inserter-stack-size-bonus`, `bulk-inserter-capacity-bonus`, `laboratory-speed`, `character-logistic-trash-slots`, `maximum-following-robots-count`, `worker-robot-speed`, `worker-robot-storage`, `character-crafting-speed`, `character-mining-speed`, `character-running-speed`, `character-build-distance`, `character-item-drop-distance`, `character-reach-distance`, `character-resource-reach-distance`, `character-item-pickup-distance`, `character-loot-pickup-distance`, `character-inventory-slots-bonus`, `deconstruction-time-to-live`, `max-failed-attempts-per-tick-per-construction-queue`, `max-successful-attempts-per-tick-per-construction-queue`, `character-health-bonus`, `mining-drill-productivity-bonus`, `train-braking-force-bonus`, `worker-robot-battery`, `laboratory-productivity`, `follower-robot-lifetime`, `artillery-range`, `cargo-landing-pad-count`, `beacon-distribution`, `belt-stack-size-bonus` | |
| BoolModifier (`modifier` boolean): `character-logistic-requests`, `vehicle-logistics`, `unlock-space-platforms`, `unlock-circuit-network`, `cliff-deconstruction-enabled`, `mining-with-fluid`, `rail-support-on-deep-oil-ocean`, `rail-planner-allow-elevated-rails`, `create-ghost-on-entity-death` | |

UnlockRecipeModifier: `use_icon_overlay_constant` (opt, false) — "If `false`, do not draw the small "constant" icon over the technology effect icon."

Related, RecipePrototype `enabled` (API): "This can be `false` to disable the recipe at the start of the game … If a recipe is unlocked via technology, this should be set to `false`." (base example: `base/prototypes/recipe.lua:1323-1324` `name = "fast-transport-belt", enabled = false,`).

### 1.2 Verbatim examples

research_trigger tech — `base/prototypes/technology.lua:17-51`:
```lua
  {
    type = "technology",
    name = "steam-power",
    icon = "__base__/graphics/technology/steam-power.png",
    icon_size = 256,
    effects =
    {
      {
        type = "unlock-recipe",
        recipe = "pipe"
      },
      ...
    },
    research_trigger =
    {
      type = "craft-item",
      item = "iron-plate",
      count = 50
    }
  },
```

Plain `unit.count` tech — `base/prototypes/technology.lua:1981-2004`:
```lua
  {
    type = "technology",
    name = "steel-processing",
    icon = "__base__/graphics/technology/steel-processing.png",
    icon_size = 256,
    effects =
    {
      {
        type = "unlock-recipe",
        recipe = "steel-plate"
      },
      {
        type = "unlock-recipe",
        recipe = "steel-chest"
      }
    },
    prerequisites = {"automation-science-pack"},
    unit =
    {
      count = 50,
      ingredients = {{"automation-science-pack", 1}},
      time = 5
    }
  },
```

Two-pack tier example — `base/prototypes/technology.lua:2494-2525` (`logistics-2`): prerequisites `{"logistics", "logistic-science-pack"}`, `unit = { count = 200, ingredients = { {"automation-science-pack", 1}, {"logistic-science-pack", 1} }, time = 30 }`, three `unlock-recipe` effects (fast-transport-belt, fast-underground-belt, fast-splitter).

Infinite `count_formula` + `icons` helper — `base/prototypes/technology.lua:5288-5316`:
```lua
  {
    type = "technology",
    name = "mining-productivity-4",
    icons = util.technology_icon_constant_productivity("__base__/graphics/technology/mining-productivity.png"),
    effects =
    {
      {
        type = "mining-drill-productivity-bonus",
        modifier = 0.1
      }
    },
    prerequisites = {"mining-productivity-3", "space-science-pack"},
    unit =
    {
      count_formula = "2500*(L - 3)",
      ingredients =
      {
        {"automation-science-pack", 1},
        ...
        {"space-science-pack", 1}
      },
      time = 60
    },
    max_level = "infinite",
    upgrade = true
  },
```
(NB: space-age deletes this tech: `space-age/base-data-updates.lua:771` `data.raw.technology["mining-productivity-4"] = nil`.)

Upgrade tech with modifiers — `base/prototypes/technology.lua:167-200` (`physical-projectile-damage-1`): `icons = util.technology_icon_constant_damage(physical_projectile_damage_1_icon)`, effects `{type = "ammo-damage", ammo_category = "bullet", modifier = 0.1}`, `{type = "turret-attack", turret_id = "gun-turret", modifier = 0.1}`, `{type = "ammo-damage", ammo_category = "shotgun-shell", modifier = 0.1}`, `unit = {count = 100 * 1, ingredients = {{"automation-science-pack", 1}}, time = 30}`, `upgrade = true`.

### 1.3 Technology icons

* Plain: `icon = ".../x.png", icon_size = 256` — 101 of 196 base techs (`grep "icon_size = 256" base/prototypes/technology.lua` → 101); the other 95 use `icons = util.technology_icon_constant_*(...)`.
* Helpers in `core/lualib/util.lua:392-612`: `technology_icon_constant_damage`, `_speed`, `_movement_speed`, `_range`, `_planet`, `_equipment`, `_followers`, `_capacity`, `_stack_size`, `_productivity`, `_recipe_productivity`, `_braking_force`, `_mining`. Structure (`core/lualib/util.lua:392-408`):
```lua
function util.technology_icon_constant_damage(technology_icon)
  local icons =
  {
    {
      icon = technology_icon,
      icon_size = 256,
    },
    {
      icon = "__core__/graphics/icons/technology/constants/constant-damage.png",
      icon_size = 128,
      scale = 0.5,
      shift = {50, 50},
      floating = true
    }
  }
  return icons
end
```
  These take a 256px base icon (hard-coded `icon_size = 256`).
* `util` is global after `require("util")`; base `data.lua:2` does `require "util"`; `core/lualib/util.lua:1-4` defines `util = { table = {} }` as a global.

---

## 2. Science packs

Science packs are `type = "tool"` (API ToolPrototype, parent ItemPrototype: `durability` (mandatory unless `infinite`), `durability_description_key`, `durability_description_value`, `infinite`). Base example `base/prototypes/item.lua:682-700`:
```lua
  {
    type = "tool",
    name = "automation-science-pack",
    localised_description = {"item-description.science-pack"},
    icon = "__base__/graphics/icons/automation-science-pack.png",
    subgroup = "science-pack",
    color_hint = { text = "A" },
    order = "a[automation-science-pack]",
    inventory_move_sound = item_sounds.science_inventory_move,
    pick_sound = item_sounds.science_inventory_pickup,
    drop_sound = item_sounds.science_inventory_move,
    stack_size = 200,
    weight = 1 * kg,
    durability = 1,
    durability_description_key = "description.science-pack-remaining-amount-key",
    factoriopedia_durability_description_key = "description.factoriopedia-science-pack-remaining-amount-key",
    durability_description_value = "description.science-pack-remaining-amount-value",
    random_tint_color = item_tints.bluish_science
  },
```
(`factoriopedia_durability_description_key` is used by base but is **not** listed in API ToolPrototype properties; API `types[name=Data]`: "Any extra properties are ignored.")

| pack (tool name) | abbrev in tables | mod | order | recipe (from emulated data.raw) | time s | category |
|---|---|---|---|---|---|---|
| `automation-science-pack` | A | base | a[automation-science-pack] | 1 copper-plate + 1 iron-gear-wheel → 1 | 5 | (crafting) |
| `logistic-science-pack` | L | base | b[logistic-science-pack] | 1 inserter + 1 transport-belt → 1 | 6 | |
| `military-science-pack` | M | base | c[military-science-pack] | 1 piercing-rounds-magazine + 1 grenade + 2 stone-wall → 2 | 10 | |
| `chemical-science-pack` | C | base | d[chemical-science-pack] | 2 engine-unit + 3 advanced-circuit + 1 sulfur → 2 | 24 | |
| `production-science-pack` | P | base | e[production-science-pack] | 1 electric-furnace + 1 productivity-module + 30 rail → 3 | 21 | |
| `utility-science-pack` | U | base | f[utility-science-pack] | 3 low-density-structure + 2 processing-unit + 1 flying-robot-frame → 3 | 21 | |
| `space-science-pack` | S | base | g[space-science-pack] | base: no recipe (satellite launch); SA: 2 iron-plate + 1 carbon + 1 ice → 5 | 15 | |
| `metallurgic-science-pack` | Met | SA | h | 3 tungsten-carbide + 2 tungsten-plate + 200 molten-copper → 1 | 10 | metallurgy |
| `agricultural-science-pack` | Agr | SA | i | 1 bioflux + 1 pentapod-egg → 1 (spoil_ticks 216000) | 4 | organic |
| `electromagnetic-science-pack` | EM | SA | j | 1 supercapacitor + 1 accumulator + 25 electrolyte + 25 holmium-solution → 1 | 10 | electromagnetics |
| `cryogenic-science-pack` | Cry | SA | k | 3 ice + 1 lithium-plate + 6 fluoroketone-cold → 1 (+3 fluoroketone-hot) | 20 | cryogenics |
| `promethium-science-pack` | Pro | SA | l | 25 promethium-asteroid-chunk + 1 quantum-processor + 10 biter-egg → 10 | 5 | cryogenics |

All 12: stack_size 200, weight 1000 (=1 kg), durability 1. SA packs carry `default_import_location` (vulcanus/gleba/fulgora/aquilo/aquilo), e.g. `space-age/prototypes/item.lua:60`.
Lab inputs: `base/prototypes/entity/entities.lua:3929-3938` lists the 7 base packs; SA appends the 5 others (`space-age/base-data-updates.lua:275-279`, `table.insert(data.raw.lab["lab"].inputs, ...)`).

---

## 3. Key technologies to hang Magnetics onto (base vs Space Age)

All techs below exist in every configuration (base, base+quality, base+elevated-rails, full SA) — checked against the four dumps.
Pack letters as in §2. Line = line of `name = "…"` in `base/prototypes/technology.lua`. SA differences come from
`space-age/base-data-updates.lua`, which space-age runs **inside its data.lua** (`space-age/data.lua:65` `require("base-data-updates")`).

| tech (base line) | prerequisites | cost base | cost in SA (only if different) | unlocks (base) | direct children in base | children added/removed in SA |
|---|---|---|---|---|---|---|
| `automation-science-pack` (89) | steam-power, electronics | trigger `craft-item` item=lab |  | automation-science-pack | automation, electric-mining-drill, fast-inserter, gun-turret, lamp, logistic-science-pack, logistics, military, radar, repair-pack, steel-processing, stone-wall | — |
| `logistic-science-pack` (1960) | automation-science-pack | 75×5s [A] |  | logistic-science-pack | advanced-material-processing, automation-2, circuit-network, electric-energy-distribution-1, engine, landfill, logistics-2, military-2, physical-projectile-damage-2, solar-energy, toolbelt, weapon-shooting-speed-2 | — |
| `steel-processing` (1983) | automation-science-pack | 50×5s [A] |  | steel-plate, steel-chest | advanced-material-processing, automation-2, electric-energy-distribution-1, engine, heavy-armor, military-2, solar-energy, steel-axe | — |
| `advanced-material-processing` (2384) | steel-processing, logistic-science-pack | 75×30s [A+L] |  | steel-furnace | advanced-material-processing-2, concrete, low-density-structure | — |
| `advanced-material-processing-2` (3773) | advanced-material-processing, chemical-science-pack | 250×30s [A+L+C] |  | electric-furnace | production-science-pack | +rocket-silo |
| `electric-energy-distribution-1` (2352) | steel-processing, logistic-science-pack | 120×30s [A+L] |  | medium-electric-pole, big-electric-pole, iron-stick | electric-energy-accumulators, electric-energy-distribution-2 | — |
| `electric-energy-distribution-2` (3723) | electric-energy-distribution-1, chemical-science-pack | 100×45s [A+L+C] |  | substation | — | — |
| `electric-energy-accumulators` (3748) | electric-energy-distribution-1, battery | 150×30s [A+L] |  | accumulator | rocket-silo | +planet-discovery-fulgora; −rocket-silo |
| `logistics` (2103) | automation-science-pack | 20×15s [A] |  | underground-belt, splitter | logistics-2 | — |
| `logistics-2` (2496) | logistics, logistic-science-pack | 200×30s [A+L] |  | fast-transport-belt, fast-underground-belt, fast-splitter | automobilism, bulk-inserter, railway | — |
| `logistics-3` (3289) | production-science-pack, lubricant | 300×15s [A+L+C+P] |  | express-transport-belt, express-underground-belt, express-splitter | — | +turbo-transport-belt |
| `automation` (1914) | automation-science-pack | 10×10s [A] |  | assembling-machine-1, long-handed-inserter | automation-2 | — |
| `automation-2` (1939) | automation, steel-processing, logistic-science-pack | 40×15s [A+L] |  | assembling-machine-2 | concrete, fluid-handling, research-speed-1 | — |
| `automation-3` (2843) | speed-module, production-science-pack, electric-engine | 150×60s [A+L+C+P] | 500×60s [A+L+C+P] | assembling-machine-3 | — | — |
| `electric-mining-drill` (109) | automation-science-pack | 25×10s [A] |  | electric-mining-drill | — | +big-mining-drill |
| `advanced-circuit` (2998) | plastics | 200×15s [A+L] |  | advanced-circuit | bulk-inserter, chemical-science-pack, mining-productivity-1, modular-armor, modules | — |
| `processing-unit` (3022) | chemical-science-pack | 300×30s [A+L+C] |  | processing-unit | effect-transmission, efficiency-module-2, exoskeleton-equipment, power-armor, productivity-module-2, speed-module-2, utility-science-pack | +rocket-silo; −efficiency-module-2, −productivity-module-2, −speed-module-2 |
| `lubricant` (3824) | advanced-oil-processing | 50×30s [A+L+C] |  | lubricant | electric-engine, logistics-3 | — |
| `electric-engine` (3849) | lubricant | 50×30s [A+L+C] |  | electric-engine-unit | automation-3, exoskeleton-equipment, power-armor, robotics | — |
| `battery` (3874) | sulfur-processing | 150×30s [A+L] |  | battery | battery-equipment, electric-energy-accumulators, laser, robotics | — |
| `laser` (3323) | battery, chemical-science-pack | 100×30s [A+L+C] |  | (none) | distractor, laser-shooting-speed-1, laser-turret, laser-weapons-damage-1 | — |
| `laser-turret` (3468) | laser, military-science-pack | 150×30s [A+L+M+C] |  | laser-turret | discharge-defense-equipment, personal-laser-defense-equipment | — |
| `stone-wall` (2551) | automation-science-pack | 10×10s [A] |  | stone-wall | gate, military-science-pack | — |
| `gate` (2571) | stone-wall, military-2 | 100×30s [A+L] |  | gate | — | — |
| `gun-turret` (2283) | automation-science-pack | 10×10s [A] |  | gun-turret | — | — |
| `military` (2027) | automation-science-pack | 10×15s [A] |  | submachine-gun, shotgun, shotgun-shell | heavy-armor, military-2, physical-projectile-damage-1, weapon-shooting-speed-1 | — |
| `military-2` (2055) | military, steel-processing, logistic-science-pack | 20×15s [A+L] |  | piercing-rounds-magazine, grenade | cliff-explosives, gate, military-science-pack, stronger-explosives-1 | −cliff-explosives |
| `military-3` (2714) | chemical-science-pack, military-science-pack | 100×30s [A+L+C+M] |  | poison-capsule, slowdown-capsule, combat-shotgun | discharge-defense-equipment, distractor, energy-shield-mk2-equipment, explosive-rocketry, military-4, personal-laser-defense-equipment, tank | +captivity; −energy-shield-mk2-equipment |
| `military-4` (2748) | military-3, utility-science-pack, explosives | 150×45s [A+L+C+M+U] |  | piercing-shotgun-shell, cluster-grenade | artillery, atomic-bomb, destroyer, power-armor-mk2, spidertron, uranium-ammo | +energy-shield-mk2-equipment, +tesla-weapons |
| `uranium-processing` (5094) | uranium-mining | trigger `mine-entity` entity=uranium-ore |  | centrifuge, uranium-processing | kovarex-enrichment-process, nuclear-power, uranium-ammo | +biolab |
| `nuclear-power` (5117) | uranium-processing | 800×30s [A+L+C] |  | nuclear-reactor, heat-exchanger, heat-pipe, steam-turbine, uranium-fuel-cell | fission-reactor-equipment, nuclear-fuel-reprocessing | — |
| `chemical-science-pack` (2596) | advanced-circuit, sulfur-processing | 75×10s [A+L] |  | chemical-science-pack | advanced-combinators, advanced-material-processing-2, advanced-oil-processing, braking-force-1, electric-energy-distribution-2, follower-robot-count-3, inserter-capacity-bonus-3, laser, low-density-structure, military-3, mining-productivity-2, physical-projectile-damage-5, processing-unit, refined-flammables-3, research-speed-3, stronger-explosives-3, uranium-mining, weapon-shooting-speed-5 | — |
| `military-science-pack` (2623) | military-2, stone-wall | 30×15s [A+L] |  | military-science-pack | defender, energy-shield-equipment, fission-reactor-equipment, flamethrower, land-mine, laser-shooting-speed-1, laser-turret, laser-weapons-damage-1, military-3, physical-projectile-damage-3, rocketry, stronger-explosives-2, weapon-shooting-speed-3 | +cliff-explosives, +health |
| `production-science-pack` (2648) | productivity-module, advanced-material-processing-2, railway | 100×30s [A+L+C] |  | production-science-pack | automation-3, braking-force-3, coal-liquefaction, effect-transmission, efficiency-module-3, inserter-capacity-bonus-4, kovarex-enrichment-process, logistics-3, mining-productivity-3, nuclear-fuel-reprocessing, productivity-module-3, research-speed-5, speed-module-3, worker-robots-speed-5, worker-robots-storage-2 | +advanced-asteroid-processing, +biolab, +elevated-rail, +follower-robot-count-5, +low-density-structure-productivity, +overgrowth-soil, +plastic-bar-productivity, +processing-unit-productivity, +rocket-fuel-productivity, +scrap-recycling-productivity, +spidertron, +stack-inserter, +steel-plate-productivity; −coal-liquefaction, −efficiency-module-3, −kovarex-enrichment-process, −productivity-module-3, −speed-module-3 |
| `utility-science-pack` (2674) | robotics, processing-unit, low-density-structure | 100×30s [A+L+C] |  | utility-science-pack | braking-force-6, fission-reactor-equipment, inserter-capacity-bonus-7, laser-shooting-speed-5, laser-weapons-damage-5, logistic-system, military-4, mining-productivity-3, personal-roboport-mk2-equipment, physical-projectile-damage-6, refined-flammables-4, research-speed-6, rocket-silo, stronger-explosives-4, weapon-shooting-speed-6, worker-robots-speed-3, worker-robots-storage-3 | +advanced-asteroid-processing, +battery-mk2-equipment, +biolab, +epic-quality, +health, +overgrowth-soil, +rail-support-foundations, +stack-inserter; −logistic-system, −mining-productivity-3, −rocket-silo |
| `solar-energy` (2239) | steel-processing, logistic-science-pack | 250×30s [A+L] |  | solar-panel | rocket-silo, solar-panel-equipment | −rocket-silo |
| `concrete` (2408) | advanced-material-processing, automation-2 | 250×30s [A+L] |  | concrete, hazard-concrete, refined-concrete, refined-hazard-concrete, iron-stick | artillery, rocket-silo, uranium-mining | +elevated-rail; −artillery |
| `low-density-structure` (3544) | advanced-material-processing, chemical-science-pack | 300×45s [A+L+C] |  | low-density-structure | battery-mk2-equipment, energy-shield-mk2-equipment, personal-laser-defense-equipment, utility-science-pack | +rocket-silo; −battery-mk2-equipment, −energy-shield-mk2-equipment |
| `engine` (2448) | steel-processing, logistic-science-pack | 100×15s [A+L] |  | engine-unit | automobilism, fluid-handling, railway | — |
| `sulfur-processing` (4692) | oil-processing | 150×30s [A+L] |  | sulfuric-acid, sulfur | battery, chemical-science-pack, explosives | — |
| `plastics` (4716) | oil-processing | 200×30s [A+L] |  | plastic-bar | advanced-circuit | — |
| `oil-processing` (4594) | oil-gathering | trigger `mine-entity` entity=crude-oil |  | oil-refinery, chemical-plant, basic-oil-processing, solid-fuel-from-petroleum-gas | flammables, plastics, sulfur-processing | — |
| `fluid-handling` (4546) | automation-2, engine | 50×15s [A+L] |  | storage-tank, pump, barrel + 14 auto-generated fill/empty barrel recipes (base/data-updates.lua) **SA: storage-tank, pump, barrel + 14 auto-generated fill/empty barrel recipes (base/data-updates.lua) + 4 fluoroketone barrel recipes** | fluid-wagon, oil-gathering | — |
| `mining-productivity-1` (5214) | advanced-circuit | 250×60s [A+L] |  | <mining-drill-productivity-bonus> | mining-productivity-2 | — |
| `research-speed-1` (2304) | automation-2 | 100×30s [A+L] |  | <laboratory-speed> | research-speed-2 | — |
| `rocket-silo` (3569) | concrete, rocket-fuel, electric-energy-accumulators, solar-energy, utility-science-pack, speed-module-3, productivity-module-3, radar **SA: concrete, rocket-fuel, processing-unit, logistic-robotics, low-density-structure, advanced-material-processing-2** | 1000×60s [A+L+C+P+U] | 1000×60s [A+L+C] | rocket-silo, rocket-part, cargo-landing-pad, satellite **SA: rocket-silo, rocket-part, cargo-landing-pad, <unlock-space-platforms>, space-platform-starter-pack, space-platform-foundation** | space-science-pack | +space-platform; −space-science-pack |
| `space-science-pack` (2700) | rocket-silo **SA: space-platform** | trigger `send-item-to-orbit` item=satellite | trigger `build-entity` entity=asteroid-collector | (none) **SA: space-science-pack** | artillery-shell-range-1, artillery-shell-speed-1, follower-robot-count-5, laser-weapons-damage-7, mining-productivity-4, physical-projectile-damage-7, refined-flammables-7, stronger-explosives-7, worker-robots-speed-6 | +efficiency-module-2, +electric-weapons-damage-2, +kovarex-enrichment-process, +logistic-system, +productivity-module-2, +quality-module-2, +refined-flammables-6, +space-platform-thruster, +speed-module-2, +stronger-explosives-5; −artillery-shell-range-1, −artillery-shell-speed-1, −mining-productivity-4, −refined-flammables-7, −stronger-explosives-7 |

Reading the table: to put a Magnetics tech "between" vanilla tiers, depend on the tech in column 1 and on the science-pack tech
of the highest pack you use (vanilla convention: e.g. `logistics-2` depends on `logistic-science-pack`; `automation-2` on
`automation, steel-processing, logistic-science-pack`). Only `automation-3` changes cost under SA among the "hang-on" candidates
(150 → 500 units, `space-age/base-data-updates.lua:547`). `rocket-silo` and `space-science-pack` change heavily under SA.

### 3.1 All Space Age edits to base technologies (source: `space-age/base-data-updates.lua` unless noted)

| tech | what SA changes | line(s) |
|---|---|---|
| `rocket-silo` | effects → rocket-silo, rocket-part, cargo-landing-pad, `unlock-space-platforms`, space-platform-starter-pack, space-platform-foundation (satellite removed); ingredients → A+L+C; prerequisites → concrete, rocket-fuel, processing-unit, logistic-robotics, low-density-structure, advanced-material-processing-2 | 32, 578, 585 |
| `space-science-pack` | localised_description; research_trigger → `build-entity` asteroid-collector; prerequisites → space-platform; effects → unlock space-science-pack recipe | 10, 61, 66, 67 |
| `logistic-system` | prereq space-science-pack; ingredients A+L+C+S | 403-404 |
| `physical-projectile-damage-6/7` | modifiers; -7 prereq adds space-science-pack | 413-417 |
| `stronger-explosives-5/6/7`, `refined-flammables-6/7`, `laser-weapons-damage-5/6/7` | prereqs/ingredients/effects | 419-494 |
| `artillery-shell-range-1`, `artillery-shell-speed-1` | prereq artillery only; unit | 503-521 |
| `atomic-bomb` | ingredients | 537 |
| `automation-3` | unit.count = 500 | 547 |
| `cliff-explosives` | prereqs explosives, military-science-pack, metallurgic-science-pack; unit | 549-556 |
| `power-armor-mk2` | prereqs → power-armor, military-4, speed-module, efficiency-module | 570 |
| `follower-robot-count-5` | + production-science-pack prereq | 595 |
| `worker-robots-speed-6` | finite (count 1000, max_level nil) | 597-601 |
| `energy-shield-mk2-equipment`, `battery-mk2-equipment`, `personal-roboport-mk2-equipment` | prereqs/units | 603-643 |
| `coal-liquefaction` | prereq metallurgic-science-pack; unit | 654-655 |
| `speed-module-2/3`, `productivity-module-2/3`, `efficiency-module-2/3` | move to space/planet packs | 669-733 |
| `kovarex-enrichment-process` | prereqs uranium-processing, space-science-pack | 742-743 |
| `mining-productivity-3` | becomes infinite (`count_formula`), prereqs mining-productivity-2, production-science-pack | 757-769 |
| `mining-productivity-4` | **deleted** (`= nil`) | 771 |
| `artillery` | prereqs military-4, metallurgic-science-pack, radar; count 1500 | 774-781 |
| `spidertron` | prereqs/ingredients/order | 792-813 |
| `quality-module-2/3`, `epic-quality`, `legendary-quality` (quality mod techs) | prereqs/units | 833-875 |
| `recycling` (quality) | prereq planet-discovery-fulgora | 920 |
| `fluid-handling` | +4 fluoroketone barrel recipes (auto-generated by `base/data-updates.lua` barrel code) | — |
| `modules` | icon → `__quality__/graphics/technology/module.png` (by **quality**, not SA) | `quality/prototypes/base-data-updates.lua:8-9` |
| `energy-weapons-damage-1..7` | set to nil (these names do not exist in base 2.0.77, so no effect) | 28-30 |

Consequence for Magnetics: never list `mining-productivity-4` as a prerequisite; if you depend on `space-science-pack`,
its trigger differs (satellite vs asteroid collector) but the name exists in both.


---

## 4. Full list of base technologies (196) — prerequisites and packs

Source: emulated `data.raw.technology` after all base stages (`work/base.json`), so barrel recipes added by
`base/data-updates.lua` appear under `fluid-handling`. Cost column: `count × time [packs]`; for `count_formula` the formula is shown
(L = level). `<type …>` = non-recipe modifier. Source column = line of `name = "…"` in the Lua file.

| # | technology | prerequisites | cost (count × time [packs]) | flags | effects (unlock-recipe names; <modifier>) | source |
|---|---|---|---|---|---|---|
| 1 | `advanced-circuit` | plastics | 200×15s [A+L] |  | advanced-circuit | base/prototypes/technology.lua:2998 |
| 2 | `advanced-combinators` | circuit-network, chemical-science-pack | 50×30s [A+L+C] |  | selector-combinator | base/prototypes/technology.lua:5435 |
| 3 | `advanced-material-processing` | steel-processing, logistic-science-pack | 75×30s [A+L] |  | steel-furnace | base/prototypes/technology.lua:2384 |
| 4 | `advanced-material-processing-2` | advanced-material-processing, chemical-science-pack | 250×30s [A+L+C] |  | electric-furnace | base/prototypes/technology.lua:3773 |
| 5 | `advanced-oil-processing` | chemical-science-pack | 75×30s [A+L+C] |  | advanced-oil-processing, heavy-oil-cracking, light-oil-cracking, solid-fuel-from-heavy-oil, solid-fuel-from-light-oil | base/prototypes/technology.lua:4625 |
| 6 | `artillery` | military-4, tank, concrete, radar | 2000×30s [A+L+C+M+U] |  | artillery-wagon, artillery-turret, artillery-shell | base/prototypes/technology.lua:5319 |
| 7 | `artillery-shell-range-1` | artillery, space-science-pack | 2^L*1000×60s [A+L+C+M+U+S] | max_level=infinite | <artillery-range +0.3> | base/prototypes/technology.lua:1542 |
| 8 | `artillery-shell-speed-1` | artillery, space-science-pack | 1000+3^(L-1)*1000×60s [A+L+C+M+U+S] | max_level=infinite | <gun-speed artillery-shell +1> | base/prototypes/technology.lua:1570 |
| 9 | `atomic-bomb` | military-4, kovarex-enrichment-process, rocketry | 5000×45s [A+L+C+M+P+U] |  | atomic-bomb | base/prototypes/technology.lua:2814 |
| 10 | `automated-rail-transportation` | railway | 200×30s [A+L] |  | train-stop, rail-signal, rail-chain-signal | base/prototypes/technology.lua:2163 |
| 11 | `automation` | automation-science-pack | 10×10s [A] |  | assembling-machine-1, long-handed-inserter | base/prototypes/technology.lua:1914 |
| 12 | `automation-2` | automation, steel-processing, logistic-science-pack | 40×15s [A+L] |  | assembling-machine-2 | base/prototypes/technology.lua:1939 |
| 13 | `automation-3` | speed-module, production-science-pack, electric-engine | 150×60s [A+L+C+P] |  | assembling-machine-3 | base/prototypes/technology.lua:2843 |
| 14 | `automation-science-pack` | steam-power, electronics | trigger:craft-item item=lab | essential | automation-science-pack | base/prototypes/technology.lua:89 |
| 15 | `automobilism` | logistics-2, engine | 100×30s [A+L] |  | car | base/prototypes/technology.lua:2195 |
| 16 | `battery` | sulfur-processing | 150×30s [A+L] |  | battery | base/prototypes/technology.lua:3874 |
| 17 | `battery-equipment` | battery, solar-panel-equipment | 50×15s [A+L] |  | battery-equipment | base/prototypes/technology.lua:4345 |
| 18 | `battery-mk2-equipment` | battery-equipment, low-density-structure, power-armor | 100×30s [A+L+C] |  | battery-mk2-equipment | base/prototypes/technology.lua:4364 |
| 19 | `belt-immunity-equipment` | solar-panel-equipment | 50×15s [A+L] |  | belt-immunity-equipment | base/prototypes/technology.lua:4301 |
| 20 | `braking-force-1` | railway, chemical-science-pack | 100×30s [A+L+C] | upgrade | <train-braking-force-bonus +0.1> | base/prototypes/technology.lua:3073 |
| 21 | `braking-force-2` | braking-force-1 | 200×30s [A+L+C] | upgrade | <train-braking-force-bonus +0.15> | base/prototypes/technology.lua:3098 |
| 22 | `braking-force-3` | braking-force-2, production-science-pack | 250×30s [A+L+C+P] | upgrade | <train-braking-force-bonus +0.15> | base/prototypes/technology.lua:3123 |
| 23 | `braking-force-4` | braking-force-3 | 350×30s [A+L+C+P] | upgrade | <train-braking-force-bonus +0.15> | base/prototypes/technology.lua:3149 |
| 24 | `braking-force-5` | braking-force-4 | 450×35s [A+L+C+P] | upgrade | <train-braking-force-bonus +0.15> | base/prototypes/technology.lua:3175 |
| 25 | `braking-force-6` | braking-force-5, utility-science-pack | 550×45s [A+L+C+P+U] | upgrade | <train-braking-force-bonus +0.15> | base/prototypes/technology.lua:3201 |
| 26 | `braking-force-7` | braking-force-6 | 650×60s [A+L+C+P+U] | upgrade | <train-braking-force-bonus +0.15> | base/prototypes/technology.lua:3228 |
| 27 | `bulk-inserter` | fast-inserter, logistics-2, advanced-circuit | 150×30s [A+L] |  | bulk-inserter, <bulk-inserter-capacity-bonus +1> | base/prototypes/technology.lua:1699 |
| 28 | `chemical-science-pack` | advanced-circuit, sulfur-processing | 75×10s [A+L] | essential | chemical-science-pack | base/prototypes/technology.lua:2596 |
| 29 | `circuit-network` | logistic-science-pack | 100×15s [A+L] |  | <unlock-circuit-network true>, arithmetic-combinator, decider-combinator, constant-combinator, power-switch, programmable-speaker, display-panel, iron-stick | base/prototypes/technology.lua:5382 |
| 30 | `cliff-explosives` | explosives, military-2 | 200×15s [A+L] |  | cliff-explosives, <cliff-deconstruction-enabled true> | base/prototypes/technology.lua:2894 |
| 31 | `coal-liquefaction` | advanced-oil-processing, production-science-pack | 200×30s [A+L+C+P] |  | coal-liquefaction | base/prototypes/technology.lua:4666 |
| 32 | `concrete` | advanced-material-processing, automation-2 | 250×30s [A+L] |  | concrete, hazard-concrete, refined-concrete, refined-hazard-concrete, iron-stick | base/prototypes/technology.lua:2408 |
| 33 | `construction-robotics` | robotics | 100×30s [A+L+C] |  | roboport, passive-provider-chest, storage-chest, construction-robot, <create-ghost-on-entity-death true> | base/prototypes/technology.lua:3898 |
| 34 | `defender` | military-science-pack | 100×30s [A+L+M] |  | defender-capsule, <maximum-following-robots-count +4> | base/prototypes/technology.lua:4987 |
| 35 | `destroyer` | military-4, distractor, speed-module | 300×30s [A+L+C+M+U] |  | destroyer-capsule | base/prototypes/technology.lua:5042 |
| 36 | `discharge-defense-equipment` | laser-turret, military-3, power-armor, solar-panel-equipment | 100×30s [A+L+C+M] |  | discharge-defense-equipment | base/prototypes/technology.lua:4427 |
| 37 | `distractor` | defender, military-3, laser | 200×30s [A+L+C+M] |  | distractor-capsule | base/prototypes/technology.lua:5016 |
| 38 | `effect-transmission` | processing-unit, production-science-pack | 75×30s [A+L+C+P] |  | beacon | base/prototypes/technology.lua:3798 |
| 39 | `efficiency-module` | modules | 50×30s [A+L] | upgrade | efficiency-module | base/prototypes/technology.lua:4909 |
| 40 | `efficiency-module-2` | efficiency-module, processing-unit | 75×30s [A+L+C] | upgrade | efficiency-module-2 | base/prototypes/technology.lua:4934 |
| 41 | `efficiency-module-3` | efficiency-module-2, production-science-pack | 300×60s [A+L+C+P] | upgrade | efficiency-module-3 | base/prototypes/technology.lua:4960 |
| 42 | `electric-energy-accumulators` | electric-energy-distribution-1, battery | 150×30s [A+L] |  | accumulator | base/prototypes/technology.lua:3748 |
| 43 | `electric-energy-distribution-1` | steel-processing, logistic-science-pack | 120×30s [A+L] |  | medium-electric-pole, big-electric-pole, iron-stick | base/prototypes/technology.lua:2352 |
| 44 | `electric-energy-distribution-2` | electric-energy-distribution-1, chemical-science-pack | 100×45s [A+L+C] |  | substation | base/prototypes/technology.lua:3723 |
| 45 | `electric-engine` | lubricant | 50×30s [A+L+C] |  | electric-engine-unit | base/prototypes/technology.lua:3849 |
| 46 | `electric-mining-drill` | automation-science-pack | 25×10s [A] |  | electric-mining-drill | base/prototypes/technology.lua:109 |
| 47 | `electronics` | — | trigger:craft-item item=copper-plate count=10 |  | copper-cable, electronic-circuit, lab, inserter, small-electric-pole | base/prototypes/technology.lua:54 |
| 48 | `energy-shield-equipment` | solar-panel-equipment, military-science-pack | 150×15s [A+L+M] |  | energy-shield-equipment | base/prototypes/technology.lua:4258 |
| 49 | `energy-shield-mk2-equipment` | energy-shield-equipment, military-3, low-density-structure, power-armor | 200×30s [A+L+C+M] |  | energy-shield-mk2-equipment | base/prototypes/technology.lua:4320 |
| 50 | `engine` | steel-processing, logistic-science-pack | 100×15s [A+L] |  | engine-unit | base/prototypes/technology.lua:2448 |
| 51 | `exoskeleton-equipment` | processing-unit, electric-engine, solar-panel-equipment | 50×30s [A+L+C] |  | exoskeleton-equipment | base/prototypes/technology.lua:4478 |
| 52 | `explosive-rocketry` | rocketry, military-3 | 100×30s [A+L+C+M] |  | explosive-rocket | base/prototypes/technology.lua:3370 |
| 53 | `explosives` | sulfur-processing | 100×15s [A+L] |  | explosives | base/prototypes/technology.lua:2870 |
| 54 | `fast-inserter` | automation-science-pack | 30×15s [A] |  | fast-inserter | base/prototypes/technology.lua:2083 |
| 55 | `fission-reactor-equipment` | utility-science-pack, power-armor, military-science-pack, nuclear-power | 200×30s [A+L+C+M+U] |  | fission-reactor-equipment | base/prototypes/technology.lua:4452 |
| 56 | `flamethrower` | flammables, military-science-pack | 50×30s [A+L+M] |  | flamethrower, flamethrower-ammo, flamethrower-turret | base/prototypes/technology.lua:2965 |
| 57 | `flammables` | oil-processing | 50×30s [A+L] |  |  | base/prototypes/technology.lua:2922 |
| 58 | `fluid-handling` | automation-2, engine | 50×15s [A+L] |  | storage-tank, pump, barrel, heavy-oil-barrel, empty-heavy-oil-barrel, crude-oil-barrel, empty-crude-oil-barrel, water-barrel, empty-water-barrel, lubricant-barrel, empty-lubricant-barrel, sulfuric-acid-barrel, empty-sulfuric-acid-barrel, petroleum-gas-barrel, empty-petroleum-gas-barrel, light-oil-barrel, empty-light-oil-barrel | base/prototypes/technology.lua:4546 |
| 59 | `fluid-wagon` | railway, fluid-handling | 200×30s [A+L] |  | fluid-wagon | base/prototypes/technology.lua:3048 |
| 60 | `follower-robot-count-1` | defender | 100×30s [A+L+M] | upgrade | <maximum-following-robots-count +5> | base/prototypes/technology.lua:1658 (create_follower_upgrade, fn at 1600) |
| 61 | `follower-robot-count-2` | follower-robot-count-1 | 200×30s [A+L+M] | upgrade | <maximum-following-robots-count +10> | base/prototypes/technology.lua:1659-1662 (create_follower_upgrade) |
| 62 | `follower-robot-count-3` | follower-robot-count-2, chemical-science-pack | 300×30s [A+L+C+M] | upgrade | <maximum-following-robots-count +10> | base/prototypes/technology.lua:1659-1662 (create_follower_upgrade) |
| 63 | `follower-robot-count-4` | follower-robot-count-3, destroyer | 400×30s [A+L+C+M+U] | upgrade | <maximum-following-robots-count +20> | base/prototypes/technology.lua:1659-1662 (create_follower_upgrade) |
| 64 | `follower-robot-count-5` | follower-robot-count-4, space-science-pack | 1000*(L-4)×30s [A+L+C+M+P+U+S] | max_level=infinite upgrade | <maximum-following-robots-count +25> | base/prototypes/technology.lua:1669 |
| 65 | `gate` | stone-wall, military-2 | 100×30s [A+L] |  | gate | base/prototypes/technology.lua:2571 |
| 66 | `gun-turret` | automation-science-pack | 10×10s [A] |  | gun-turret | base/prototypes/technology.lua:2283 |
| 67 | `heavy-armor` | military, steel-processing | 30×30s [A] |  | heavy-armor | base/prototypes/technology.lua:2263 |
| 68 | `inserter-capacity-bonus-1` | bulk-inserter | 200×30s [A+L] | upgrade | <bulk-inserter-capacity-bonus +1> | base/prototypes/technology.lua:1727 |
| 69 | `inserter-capacity-bonus-2` | inserter-capacity-bonus-1 | 250×30s [A+L] | upgrade | <inserter-stack-size-bonus +1>, <bulk-inserter-capacity-bonus +1> | base/prototypes/technology.lua:1752 |
| 70 | `inserter-capacity-bonus-3` | inserter-capacity-bonus-2, chemical-science-pack | 250×30s [A+L+C] | upgrade | <bulk-inserter-capacity-bonus +1> | base/prototypes/technology.lua:1780 |
| 71 | `inserter-capacity-bonus-4` | inserter-capacity-bonus-3, production-science-pack | 250×30s [A+L+C+P] | upgrade | <bulk-inserter-capacity-bonus +1> | base/prototypes/technology.lua:1805 |
| 72 | `inserter-capacity-bonus-5` | inserter-capacity-bonus-4 | 300×30s [A+L+C+P] | upgrade | <bulk-inserter-capacity-bonus +2> | base/prototypes/technology.lua:1831 |
| 73 | `inserter-capacity-bonus-6` | inserter-capacity-bonus-5 | 400×30s [A+L+C+P] | upgrade | <bulk-inserter-capacity-bonus +2> | base/prototypes/technology.lua:1857 |
| 74 | `inserter-capacity-bonus-7` | inserter-capacity-bonus-6, utility-science-pack | 600×30s [A+L+C+P+U] | upgrade | <inserter-stack-size-bonus +1>, <bulk-inserter-capacity-bonus +2> | base/prototypes/technology.lua:1883 |
| 75 | `kovarex-enrichment-process` | production-science-pack, uranium-processing, rocket-fuel | 1500×30s [A+L+C+P] |  | kovarex-enrichment-process, nuclear-fuel | base/prototypes/technology.lua:5158 |
| 76 | `lamp` | automation-science-pack | 10×15s [A] |  | small-lamp | base/prototypes/technology.lua:2219 |
| 77 | `land-mine` | explosives, military-science-pack | 100×30s [A+L+M] |  | land-mine | base/prototypes/technology.lua:2939 |
| 78 | `landfill` | logistic-science-pack | 50×30s [A+L] |  | landfill | base/prototypes/technology.lua:2472 |
| 79 | `laser` | battery, chemical-science-pack | 100×30s [A+L+C] |  |  | base/prototypes/technology.lua:3323 |
| 80 | `laser-shooting-speed-1` | laser, military-science-pack | 50×30s [A+L+M+C] | upgrade | <gun-speed laser +0.1> | base/prototypes/technology.lua:1350 |
| 81 | `laser-shooting-speed-2` | laser-shooting-speed-1 | 100×30s [A+L+M+C] | upgrade | <gun-speed laser +0.2> | base/prototypes/technology.lua:1377 |
| 82 | `laser-shooting-speed-3` | laser-shooting-speed-2 | 200×60s [A+L+C+M] | upgrade | <gun-speed laser +0.3> | base/prototypes/technology.lua:1404 |
| 83 | `laser-shooting-speed-4` | laser-shooting-speed-3 | 200×60s [A+L+C+M] | upgrade | <gun-speed laser +0.3> | base/prototypes/technology.lua:1431 |
| 84 | `laser-shooting-speed-5` | laser-shooting-speed-4, utility-science-pack | 200×60s [A+L+C+M+U] | upgrade | <gun-speed laser +0.4> | base/prototypes/technology.lua:1458 |
| 85 | `laser-shooting-speed-6` | laser-shooting-speed-5 | 350×60s [A+L+C+M+U] | upgrade | <gun-speed laser +0.4> | base/prototypes/technology.lua:1486 |
| 86 | `laser-shooting-speed-7` | laser-shooting-speed-6 | 450×60s [A+L+C+M+U] | upgrade | <gun-speed laser +0.5> | base/prototypes/technology.lua:1514 |
| 87 | `laser-turret` | laser, military-science-pack | 150×30s [A+L+M+C] |  | laser-turret | base/prototypes/technology.lua:3468 |
| 88 | `laser-weapons-damage-1` | laser, military-science-pack | 100×30s [A+L+M+C] | upgrade | <ammo-damage laser +0.2> | base/prototypes/technology.lua:974 |
| 89 | `laser-weapons-damage-2` | laser-weapons-damage-1 | 200×30s [A+L+M+C] | upgrade | <ammo-damage laser +0.2> | base/prototypes/technology.lua:1001 |
| 90 | `laser-weapons-damage-3` | laser-weapons-damage-2 | 300×60s [A+L+M+C] | upgrade | <ammo-damage laser +0.3> | base/prototypes/technology.lua:1028 |
| 91 | `laser-weapons-damage-4` | laser-weapons-damage-3 | 400×60s [A+L+M+C] | upgrade | <ammo-damage laser +0.4> | base/prototypes/technology.lua:1055 |
| 92 | `laser-weapons-damage-5` | laser-weapons-damage-4, utility-science-pack | 500×60s [A+L+C+M+U] | upgrade | <ammo-damage laser +0.5>, <ammo-damage beam +0.4> | base/prototypes/technology.lua:1082 |
| 93 | `laser-weapons-damage-6` | laser-weapons-damage-5 | 600×60s [A+L+C+M+U] | upgrade | <ammo-damage laser +0.7>, <ammo-damage electric +0.7>, <ammo-damage beam +0.6> | base/prototypes/technology.lua:1115 |
| 94 | `laser-weapons-damage-7` | laser-weapons-damage-6, space-science-pack | 2^(L-7)*1000×60s [A+L+C+M+U+S] | max_level=infinite upgrade | <ammo-damage laser +0.7>, <ammo-damage electric +0.7>, <ammo-damage beam +0.3> | base/prototypes/technology.lua:1153 |
| 95 | `logistic-robotics` | robotics | 250×30s [A+L+C] |  | roboport, passive-provider-chest, storage-chest, logistic-robot, <character-logistic-requests true>, <character-logistic-trash-slots +30> | base/prototypes/technology.lua:3939 |
| 96 | `logistic-science-pack` | automation-science-pack | 75×5s [A] | essential | logistic-science-pack | base/prototypes/technology.lua:1960 |
| 97 | `logistic-system` | utility-science-pack, logistic-robotics | 500×30s [A+L+C+U] |  | active-provider-chest, requester-chest, buffer-chest, <vehicle-logistics true> | base/prototypes/technology.lua:3984 |
| 98 | `logistics` | automation-science-pack | 20×15s [A] |  | underground-belt, splitter | base/prototypes/technology.lua:2103 |
| 99 | `logistics-2` | logistics, logistic-science-pack | 200×30s [A+L] |  | fast-transport-belt, fast-underground-belt, fast-splitter | base/prototypes/technology.lua:2496 |
| 100 | `logistics-3` | production-science-pack, lubricant | 300×15s [A+L+C+P] |  | express-transport-belt, express-underground-belt, express-splitter | base/prototypes/technology.lua:3289 |
| 101 | `low-density-structure` | advanced-material-processing, chemical-science-pack | 300×45s [A+L+C] |  | low-density-structure | base/prototypes/technology.lua:3544 |
| 102 | `lubricant` | advanced-oil-processing | 50×30s [A+L+C] |  | lubricant | base/prototypes/technology.lua:3824 |
| 103 | `military` | automation-science-pack | 10×15s [A] |  | submachine-gun, shotgun, shotgun-shell | base/prototypes/technology.lua:2027 |
| 104 | `military-2` | military, steel-processing, logistic-science-pack | 20×15s [A+L] |  | piercing-rounds-magazine, grenade | base/prototypes/technology.lua:2055 |
| 105 | `military-3` | chemical-science-pack, military-science-pack | 100×30s [A+L+C+M] |  | poison-capsule, slowdown-capsule, combat-shotgun | base/prototypes/technology.lua:2714 |
| 106 | `military-4` | military-3, utility-science-pack, explosives | 150×45s [A+L+C+M+U] |  | piercing-shotgun-shell, cluster-grenade | base/prototypes/technology.lua:2748 |
| 107 | `military-science-pack` | military-2, stone-wall | 30×15s [A+L] | essential | military-science-pack | base/prototypes/technology.lua:2623 |
| 108 | `mining-productivity-1` | advanced-circuit | 250×60s [A+L] | upgrade | <mining-drill-productivity-bonus +0.1> | base/prototypes/technology.lua:5214 |
| 109 | `mining-productivity-2` | mining-productivity-1, chemical-science-pack | 500×60s [A+L+C] | upgrade | <mining-drill-productivity-bonus +0.1> | base/prototypes/technology.lua:5238 |
| 110 | `mining-productivity-3` | mining-productivity-2, production-science-pack, utility-science-pack | 1000×60s [A+L+C+P+U] | upgrade | <mining-drill-productivity-bonus +0.1> | base/prototypes/technology.lua:5263 |
| 111 | `mining-productivity-4` | mining-productivity-3, space-science-pack | 2500*(L - 3)×60s [A+L+C+P+U+S] | max_level=infinite upgrade | <mining-drill-productivity-bonus +0.1> | base/prototypes/technology.lua:5290 |
| 112 | `modular-armor` | heavy-armor, advanced-circuit | 100×30s [A+L] |  | modular-armor | base/prototypes/technology.lua:3396 |
| 113 | `modules` | advanced-circuit | 100×30s [A+L] |  |  | base/prototypes/technology.lua:4736 |
| 114 | `night-vision-equipment` | solar-panel-equipment | 50×15s [A+L] |  | night-vision-equipment | base/prototypes/technology.lua:4282 |
| 115 | `nuclear-fuel-reprocessing` | nuclear-power, production-science-pack | 50×30s [A+L+C+P] |  | nuclear-fuel-reprocessing | base/prototypes/technology.lua:5188 |
| 116 | `nuclear-power` | uranium-processing | 800×30s [A+L+C] |  | nuclear-reactor, heat-exchanger, heat-pipe, steam-turbine, uranium-fuel-cell | base/prototypes/technology.lua:5117 |
| 117 | `oil-gathering` | fluid-handling | 100×30s [A+L] |  | pumpjack | base/prototypes/technology.lua:4574 |
| 118 | `oil-processing` | oil-gathering | trigger:mine-entity entity=crude-oil |  | oil-refinery, chemical-plant, basic-oil-processing, solid-fuel-from-petroleum-gas | base/prototypes/technology.lua:4594 |
| 119 | `personal-laser-defense-equipment` | laser-turret, military-3, low-density-structure, power-armor, solar-panel-equipment | 100×30s [A+L+C+M] |  | personal-laser-defense-equipment | base/prototypes/technology.lua:4402 |
| 120 | `personal-roboport-equipment` | construction-robotics, solar-panel-equipment | 50×30s [A+L+C] |  | personal-roboport-equipment | base/prototypes/technology.lua:4497 |
| 121 | `personal-roboport-mk2-equipment` | personal-roboport-equipment, utility-science-pack | 250×30s [A+L+C+U] |  | personal-roboport-mk2-equipment | base/prototypes/technology.lua:4521 |
| 122 | `physical-projectile-damage-1` | military | 100×30s [A] | upgrade | <ammo-damage bullet +0.1>, <turret-attack gun-turret +0.1>, <ammo-damage shotgun-shell +0.1> | base/prototypes/technology.lua:169 |
| 123 | `physical-projectile-damage-2` | physical-projectile-damage-1, logistic-science-pack | 200×30s [A+L] | upgrade | <ammo-damage bullet +0.1>, <turret-attack gun-turret +0.1>, <ammo-damage shotgun-shell +0.1> | base/prototypes/technology.lua:203 |
| 124 | `physical-projectile-damage-3` | physical-projectile-damage-2, military-science-pack | 300×60s [A+L+M] | upgrade | <ammo-damage bullet +0.2>, <turret-attack gun-turret +0.2>, <ammo-damage shotgun-shell +0.2> | base/prototypes/technology.lua:322 |
| 125 | `physical-projectile-damage-4` | physical-projectile-damage-3 | 400×60s [A+L+M] | upgrade | <ammo-damage bullet +0.2>, <turret-attack gun-turret +0.2>, <ammo-damage shotgun-shell +0.2> | base/prototypes/technology.lua:358 |
| 126 | `physical-projectile-damage-5` | physical-projectile-damage-4, chemical-science-pack | 500×60s [A+L+C+M] | upgrade | <ammo-damage bullet +0.2>, <turret-attack gun-turret +0.2>, <ammo-damage shotgun-shell +0.2>, <ammo-damage cannon-shell +0.9> | base/prototypes/technology.lua:394 |
| 127 | `physical-projectile-damage-6` | physical-projectile-damage-5, utility-science-pack | 600×60s [A+L+C+M+U] | upgrade | <ammo-damage bullet +0.4>, <turret-attack gun-turret +0.4>, <ammo-damage shotgun-shell +0.4>, <ammo-damage cannon-shell +1.3> | base/prototypes/technology.lua:436 |
| 128 | `physical-projectile-damage-7` | physical-projectile-damage-6, space-science-pack | 2^(L-7)*1000×60s [A+L+C+M+U+S] | max_level=infinite upgrade | <ammo-damage bullet +0.4>, <turret-attack gun-turret +0.7>, <ammo-damage shotgun-shell +0.4>, <ammo-damage cannon-shell +1> | base/prototypes/technology.lua:479 |
| 129 | `plastics` | oil-processing | 200×30s [A+L] |  | plastic-bar | base/prototypes/technology.lua:4716 |
| 130 | `power-armor` | modular-armor, electric-engine, processing-unit | 200×30s [A+L+C] |  | power-armor | base/prototypes/technology.lua:3416 |
| 131 | `power-armor-mk2` | power-armor, military-4, speed-module-2, efficiency-module-2 | 400×30s [A+L+C+M+U] |  | power-armor-mk2 | base/prototypes/technology.lua:3441 |
| 132 | `processing-unit` | chemical-science-pack | 300×30s [A+L+C] |  | processing-unit | base/prototypes/technology.lua:3022 |
| 133 | `production-science-pack` | productivity-module, advanced-material-processing-2, railway | 100×30s [A+L+C] | essential | production-science-pack | base/prototypes/technology.lua:2648 |
| 134 | `productivity-module` | modules | 50×30s [A+L] | upgrade | productivity-module | base/prototypes/technology.lua:4831 |
| 135 | `productivity-module-2` | productivity-module, processing-unit | 75×30s [A+L+C] | upgrade | productivity-module-2 | base/prototypes/technology.lua:4856 |
| 136 | `productivity-module-3` | productivity-module-2, production-science-pack | 300×60s [A+L+C+P] | upgrade | productivity-module-3 | base/prototypes/technology.lua:4882 |
| 137 | `radar` | automation-science-pack | 20×10s [A] |  | radar | base/prototypes/technology.lua:149 |
| 138 | `railway` | logistics-2, engine | 75×30s [A+L] |  | rail, locomotive, cargo-wagon, iron-stick | base/prototypes/technology.lua:2127 |
| 139 | `refined-flammables-1` | flamethrower | 100×30s [A+L+M] | upgrade | <ammo-damage flamethrower +0.2>, <turret-attack flamethrower-turret +0.2> | base/prototypes/technology.lua:746 |
| 140 | `refined-flammables-2` | refined-flammables-1 | 200×30s [A+L+M] | upgrade | <ammo-damage flamethrower +0.2>, <turret-attack flamethrower-turret +0.2> | base/prototypes/technology.lua:777 |
| 141 | `refined-flammables-3` | refined-flammables-2, chemical-science-pack | 300×60s [A+L+M+C] | upgrade | <ammo-damage flamethrower +0.2>, <turret-attack flamethrower-turret +0.2> | base/prototypes/technology.lua:808 |
| 142 | `refined-flammables-4` | refined-flammables-3, utility-science-pack | 400×60s [A+L+M+C+U] | upgrade | <ammo-damage flamethrower +0.3>, <turret-attack flamethrower-turret +0.3> | base/prototypes/technology.lua:840 |
| 143 | `refined-flammables-5` | refined-flammables-4 | 500×60s [A+L+M+C+U] | upgrade | <ammo-damage flamethrower +0.3>, <turret-attack flamethrower-turret +0.3> | base/prototypes/technology.lua:873 |
| 144 | `refined-flammables-6` | refined-flammables-5 | 600×60s [A+L+C+M+U] | upgrade | <ammo-damage flamethrower +0.4>, <turret-attack flamethrower-turret +0.4> | base/prototypes/technology.lua:906 |
| 145 | `refined-flammables-7` | refined-flammables-6, space-science-pack | 2^(L-7)*1000×60s [A+L+C+M+U+S] | max_level=infinite upgrade | <ammo-damage flamethrower +0.2>, <turret-attack flamethrower-turret +0.2> | base/prototypes/technology.lua:939 |
| 146 | `repair-pack` | automation-science-pack | 25×10s [A] |  | repair-pack | base/prototypes/technology.lua:129 |
| 147 | `research-speed-1` | automation-2 | 100×30s [A+L] | upgrade | <laboratory-speed +0.2> | base/prototypes/technology.lua:2304 |
| 148 | `research-speed-2` | research-speed-1 | 200×30s [A+L] | upgrade | <laboratory-speed +0.3> | base/prototypes/technology.lua:2328 |
| 149 | `research-speed-3` | research-speed-2, chemical-science-pack | 250×30s [A+L+C] | upgrade | <laboratory-speed +0.4> | base/prototypes/technology.lua:3620 |
| 150 | `research-speed-4` | research-speed-3 | 500×30s [A+L+C] | upgrade | <laboratory-speed +0.5> | base/prototypes/technology.lua:3645 |
| 151 | `research-speed-5` | research-speed-4, production-science-pack | 500×30s [A+L+C+P] | upgrade | <laboratory-speed +0.5> | base/prototypes/technology.lua:3670 |
| 152 | `research-speed-6` | research-speed-5, utility-science-pack | 500×30s [A+L+C+P+U] | upgrade | <laboratory-speed +0.6> | base/prototypes/technology.lua:3696 |
| 153 | `robotics` | electric-engine, battery | 75×30s [A+L+C] |  | flying-robot-frame | base/prototypes/technology.lua:3494 |
| 154 | `rocket-fuel` | flammables, advanced-oil-processing | 300×45s [A+L+C] |  | rocket-fuel | base/prototypes/technology.lua:3519 |
| 155 | `rocket-silo` | concrete, rocket-fuel, electric-energy-accumulators, solar-energy, utility-science-pack, speed-module-3, productivity-module-3, radar | 1000×60s [A+L+C+P+U] | essential | rocket-silo, rocket-part, cargo-landing-pad, satellite | base/prototypes/technology.lua:3569 |
| 156 | `rocketry` | explosives, flammables, military-science-pack | 120×15s [A+L+M] |  | rocket-launcher, rocket | base/prototypes/technology.lua:3341 |
| 157 | `solar-energy` | steel-processing, logistic-science-pack | 250×30s [A+L] |  | solar-panel | base/prototypes/technology.lua:2239 |
| 158 | `solar-panel-equipment` | modular-armor, solar-energy | 100×15s [A+L] |  | solar-panel-equipment | base/prototypes/technology.lua:4383 |
| 159 | `space-science-pack` | rocket-silo | trigger:send-item-to-orbit item=satellite | essential |  | base/prototypes/technology.lua:2700 |
| 160 | `speed-module` | modules | 50×30s [A+L] | upgrade | speed-module | base/prototypes/technology.lua:4753 |
| 161 | `speed-module-2` | speed-module, processing-unit | 75×30s [A+L+C] | upgrade | speed-module-2 | base/prototypes/technology.lua:4778 |
| 162 | `speed-module-3` | speed-module-2, production-science-pack | 300×60s [A+L+C+P] | upgrade | speed-module-3 | base/prototypes/technology.lua:4804 |
| 163 | `spidertron` | military-4, exoskeleton-equipment, fission-reactor-equipment, rocketry, efficiency-module-3, radar | 2500×30s [A+L+M+C+P+U] |  | spidertron | base/prototypes/technology.lua:5354 |
| 164 | `steam-power` | — | trigger:craft-item item=iron-plate count=50 |  | pipe, pipe-to-ground, offshore-pump, boiler, steam-engine | base/prototypes/technology.lua:19 |
| 165 | `steel-axe` | steel-processing | trigger:craft-item item=steel-plate count=50 |  | <character-mining-speed +1> | base/prototypes/technology.lua:2007 |
| 166 | `steel-processing` | automation-science-pack | 50×5s [A] |  | steel-plate, steel-chest | base/prototypes/technology.lua:1983 |
| 167 | `stone-wall` | automation-science-pack | 10×10s [A] |  | stone-wall | base/prototypes/technology.lua:2551 |
| 168 | `stronger-explosives-1` | military-2 | 100×30s [A+L] | upgrade | <ammo-damage grenade +0.25> | base/prototypes/technology.lua:297 |
| 169 | `stronger-explosives-2` | stronger-explosives-1, military-science-pack | 200×30s [A+L+M] | upgrade | <ammo-damage grenade +0.2>, <ammo-damage landmine +0.2> | base/prototypes/technology.lua:524 |
| 170 | `stronger-explosives-3` | stronger-explosives-2, chemical-science-pack | 300×60s [A+L+M+C] | upgrade | <ammo-damage rocket +0.3>, <ammo-damage grenade +0.2>, <ammo-damage landmine +0.2> | base/prototypes/technology.lua:555 |
| 171 | `stronger-explosives-4` | stronger-explosives-3, utility-science-pack | 400×60s [A+L+M+C+U] | upgrade | <ammo-damage rocket +0.4>, <ammo-damage grenade +0.2>, <ammo-damage landmine +0.2> | base/prototypes/technology.lua:592 |
| 172 | `stronger-explosives-5` | stronger-explosives-4 | 500×60s [A+L+M+C+U] | upgrade | <ammo-damage rocket +0.5>, <ammo-damage grenade +0.2>, <ammo-damage landmine +0.2> | base/prototypes/technology.lua:630 |
| 173 | `stronger-explosives-6` | stronger-explosives-5 | 600×60s [A+L+C+M+U] | upgrade | <ammo-damage rocket +0.6>, <ammo-damage grenade +0.2>, <ammo-damage landmine +0.2> | base/prototypes/technology.lua:668 |
| 174 | `stronger-explosives-7` | stronger-explosives-6, space-science-pack | 2^(L-7)*1000×60s [A+L+C+M+U+S] | max_level=infinite upgrade | <ammo-damage rocket +0.5>, <ammo-damage grenade +0.2>, <ammo-damage landmine +0.2> | base/prototypes/technology.lua:706 |
| 175 | `sulfur-processing` | oil-processing | 150×30s [A+L] |  | sulfuric-acid, sulfur | base/prototypes/technology.lua:4692 |
| 176 | `tank` | automobilism, military-3, explosives | 250×30s [A+L+C+M] |  | tank, cannon-shell, explosive-cannon-shell | base/prototypes/technology.lua:3255 |
| 177 | `toolbelt` | logistic-science-pack | 100×30s [A+L] |  | <character-inventory-slots-bonus +10> | base/prototypes/technology.lua:2528 |
| 178 | `uranium-ammo` | uranium-processing, military-4, tank | 1000×45s [A+L+C+M+U] |  | uranium-rounds-magazine, uranium-cannon-shell, explosive-uranium-cannon-shell | base/prototypes/technology.lua:2779 |
| 179 | `uranium-mining` | chemical-science-pack, concrete | 100×30s [A+L+C] |  | <mining-with-fluid true> | base/prototypes/technology.lua:5069 |
| 180 | `uranium-processing` | uranium-mining | trigger:mine-entity entity=uranium-ore |  | centrifuge, uranium-processing | base/prototypes/technology.lua:5094 |
| 181 | `utility-science-pack` | robotics, processing-unit, low-density-structure | 100×30s [A+L+C] | essential | utility-science-pack | base/prototypes/technology.lua:2674 |
| 182 | `weapon-shooting-speed-1` | military | 100×30s [A] | upgrade | <gun-speed bullet +0.1>, <gun-speed shotgun-shell +0.1> | base/prototypes/technology.lua:238 |
| 183 | `weapon-shooting-speed-2` | weapon-shooting-speed-1, logistic-science-pack | 200×30s [A+L] | upgrade | <gun-speed bullet +0.2>, <gun-speed shotgun-shell +0.2> | base/prototypes/technology.lua:267 |
| 184 | `weapon-shooting-speed-3` | weapon-shooting-speed-2, military-science-pack | 300×60s [A+L+M] | upgrade | <gun-speed bullet +0.2>, <gun-speed shotgun-shell +0.2>, <gun-speed rocket +0.5> | base/prototypes/technology.lua:1193 |
| 185 | `weapon-shooting-speed-4` | weapon-shooting-speed-3 | 400×60s [A+L+M] | upgrade | <gun-speed bullet +0.3>, <gun-speed shotgun-shell +0.3>, <gun-speed rocket +0.7> | base/prototypes/technology.lua:1229 |
| 186 | `weapon-shooting-speed-5` | weapon-shooting-speed-4, chemical-science-pack | 500×60s [A+L+C+M] | upgrade | <gun-speed bullet +0.3>, <gun-speed shotgun-shell +0.4>, <gun-speed cannon-shell +0.8>, <gun-speed rocket +0.9> | base/prototypes/technology.lua:1265 |
| 187 | `weapon-shooting-speed-6` | weapon-shooting-speed-5, utility-science-pack | 600×60s [A+L+C+M+U] | upgrade | <gun-speed bullet +0.4>, <gun-speed shotgun-shell +0.4>, <gun-speed cannon-shell +1.5>, <gun-speed rocket +1.3> | base/prototypes/technology.lua:1307 |
| 188 | `worker-robots-speed-1` | robotics | 50×30s [A+L+C] | upgrade | <worker-robot-speed +0.35> | base/prototypes/technology.lua:4022 |
| 189 | `worker-robots-speed-2` | worker-robots-speed-1 | 100×30s [A+L+C] | upgrade | <worker-robot-speed +0.4> | base/prototypes/technology.lua:4047 |
| 190 | `worker-robots-speed-3` | worker-robots-speed-2, utility-science-pack | 150×60s [A+L+C+U] | upgrade | <worker-robot-speed +0.45> | base/prototypes/technology.lua:4072 |
| 191 | `worker-robots-speed-4` | worker-robots-speed-3 | 250×60s [A+L+C+U] | upgrade | <worker-robot-speed +0.55> | base/prototypes/technology.lua:4098 |
| 192 | `worker-robots-speed-5` | worker-robots-speed-4, production-science-pack | 500×60s [A+L+C+P+U] | upgrade | <worker-robot-speed +0.65> | base/prototypes/technology.lua:4124 |
| 193 | `worker-robots-speed-6` | worker-robots-speed-5, space-science-pack | 2^(L-6)*1000×60s [A+L+C+P+U+S] | max_level=infinite upgrade | <worker-robot-speed +0.65> | base/prototypes/technology.lua:4151 |
| 194 | `worker-robots-storage-1` | robotics | 200×30s [A+L+C] | upgrade | <worker-robot-storage +1> | base/prototypes/technology.lua:4180 |
| 195 | `worker-robots-storage-2` | worker-robots-storage-1, production-science-pack | 300×60s [A+L+C+P] | upgrade | <worker-robot-storage +1> | base/prototypes/technology.lua:4205 |
| 196 | `worker-robots-storage-3` | worker-robots-storage-2, utility-science-pack | 450×60s [A+L+C+P+U] | upgrade | <worker-robot-storage +1> | base/prototypes/technology.lua:4231 |

### 4.1 Technologies added by quality alone (base+quality; `work/bq.json`)

| # | technology | prerequisites | cost (count × time [packs]) | flags | effects (unlock-recipe names; <modifier>) | source |
|---|---|---|---|---|---|---|
| 1 | `epic-quality` | quality-module, utility-science-pack, production-science-pack | 5000×60s [A+L+C+P+U] |  | <unlock-quality epic> | quality/prototypes/technology.lua:91 |
| 2 | `legendary-quality` | space-science-pack, epic-quality | 5000×60s [A+L+C+P+U+S] |  | <unlock-quality legendary> | quality/prototypes/technology.lua:119 |
| 3 | `quality-module` | modules | 500×30s [A+L] | upgrade | quality-module, <unlock-quality uncommon>, <unlock-quality rare> | quality/prototypes/technology.lua:5 |
| 4 | `quality-module-2` | quality-module, processing-unit | 75×30s [A+L+C] | upgrade | quality-module-2 | quality/prototypes/technology.lua:38 |
| 5 | `quality-module-3` | quality-module-2, production-science-pack | 300×60s [A+L+C+P] | upgrade | quality-module-3 | quality/prototypes/technology.lua:64 |
| 6 | `recycling` | production-science-pack, processing-unit, concrete | 5000×15s [A+L+C+P] |  | recycler | quality/prototypes/technology.lua:148 |

### 4.2 Technology added by elevated-rails alone (`work/be.json`)

| # | technology | prerequisites | cost (count × time [packs]) | flags | effects (unlock-recipe names; <modifier>) | source |
|---|---|---|---|---|---|---|
| 1 | `elevated-rail` | concrete, production-science-pack | 100×30s [A+L+C+P] |  | rail-support, rail-ramp, <rail-planner-allow-elevated-rails true> | elevated-rails/prototypes/technology/elevated-rails.lua:5 |

### 4.3 Technologies present in the full Space Age set but not in base (80; `work/sa.json`)

Includes the quality and elevated-rails techs as modified by SA (e.g. `quality-module-2` cost changes, `recycling` becomes a trigger tech).

| # | technology | prerequisites | cost (count × time [packs]) | flags | effects (unlock-recipe names; <modifier>) | source |
|---|---|---|---|---|---|---|
| 1 | `advanced-asteroid-processing` | agricultural-science-pack, production-science-pack, utility-science-pack | 2000×60s [A+L+C+P+U+S+Agr] |  | advanced-metallic-asteroid-crushing, advanced-carbonic-asteroid-crushing, advanced-oxide-asteroid-crushing, advanced-thruster-fuel, advanced-thruster-oxidizer | space-age/prototypes/technology.lua:1733 |
| 2 | `agricultural-science-pack` | bioflux-processing, bacteria-cultivation, artificial-soil | trigger:craft-item item=bioflux count=100 | essential | agricultural-science-pack | space-age/prototypes/technology.lua:1093 |
| 3 | `agriculture` | planet-discovery-gleba | trigger:mine-entity entity=iron-stromatolite |  | agricultural-tower, nutrients-from-spoilage | space-age/prototypes/technology.lua:882 |
| 4 | `artificial-soil` | yumako, jellynut | trigger:craft-item item=nutrients count=500 |  | artificial-yumako-soil, artificial-jellynut-soil | space-age/prototypes/technology.lua:1011 |
| 5 | `artillery-shell-damage-1` | artillery | 2^(L-1)*1000×60s [A+L+C+M+U+S+Met] | max_level=infinite | <ammo-damage artillery-shell +0.1> | space-age/prototypes/technology.lua:201 |
| 6 | `asteroid-productivity` | advanced-asteroid-processing | 1.5^L*1000×60s [A+L+C+P+U+S+Agr] | max_level=infinite upgrade | <change-recipe-productivity carbonic-asteroid-crushing +0.1>, <change-recipe-productivity oxide-asteroid-crushing +0.1>, <change-recipe-productivity metallic-asteroid-crushing +0.1>, <change-recipe-productivity advanced-carbonic-asteroid-crushing +0.1>, <change-recipe-productivity advanced-oxide-asteroid-crushing +0.1>, <change-recipe-productivity advanced-metallic-asteroid-crushing +0.1> | space-age/prototypes/technology.lua:2014 |
| 7 | `asteroid-reprocessing` | metallurgic-science-pack | 500×60s [A+L+C+S+Met] |  | metallic-asteroid-reprocessing, oxide-asteroid-reprocessing, carbonic-asteroid-reprocessing | space-age/prototypes/technology.lua:1697 |
| 8 | `bacteria-cultivation` | bioflux | trigger:craft-item item=bioflux |  | copper-bacteria-cultivation, iron-bacteria-cultivation | space-age/prototypes/technology.lua:1036 |
| 9 | `battery-mk3-equipment` | battery-mk2-equipment, electromagnetic-science-pack | 500×60s [A+L+C+U+S+EM] |  | battery-mk3-equipment | space-age/prototypes/technology.lua:504 |
| 10 | `big-mining-drill` | foundry, electric-mining-drill | trigger:craft-item item=foundry |  | big-mining-drill | space-age/prototypes/technology.lua:642 |
| 11 | `biochamber` | yumako, jellynut | trigger:craft-item item=nutrients count=10 |  | biochamber, nutrients-from-yumako-mash, burnt-spoilage, pentapod-egg | space-age/prototypes/technology.lua:930 |
| 12 | `bioflux` | biochamber | trigger:craft-item item=biochamber |  | bioflux, nutrients-from-bioflux | space-age/prototypes/technology.lua:987 |
| 13 | `bioflux-processing` | bioflux | trigger:craft-item item=bioflux count=25 |  | bioplastic, rocket-fuel-from-jelly, biosulfur, biolubricant | space-age/prototypes/technology.lua:1060 |
| 14 | `biolab` | biter-egg-handling, production-science-pack, utility-science-pack, uranium-processing | 1000×60s [A+L+C+M+P+U+S+Agr] |  | biolab | space-age/prototypes/technology.lua:1283 |
| 15 | `biter-egg-handling` | captivity | trigger:capture-spawner |  |  | space-age/prototypes/technology.lua:1315 |
| 16 | `calcite-processing` | planet-discovery-vulcanus | trigger:mine-entity entity=calcite |  | acid-neutralisation, steam-condensation, simple-coal-liquefaction | space-age/prototypes/technology.lua:592 |
| 17 | `captive-biter-spawner` | cryogenic-science-pack, biter-egg-handling, kovarex-enrichment-process | 3000×60s [A+L+C+M+P+U+S+Met+Agr+EM+Cry] |  | captive-biter-spawner | space-age/prototypes/technology.lua:1906 |
| 18 | `captivity` | agricultural-science-pack, military-3, rocketry | 1000×60s [A+L+C+M+S+Agr] |  | capture-robot-rocket, biter-egg, nutrients-from-biter-egg | space-age/prototypes/technology.lua:1245 |
| 19 | `carbon-fiber` | agricultural-science-pack | 500×60s [A+L+C+S+Agr] |  | carbon-fiber | space-age/prototypes/technology.lua:1361 |
| 20 | `cryogenic-plant` | lithium-processing | trigger:craft-item item=lithium-plate |  | cryogenic-plant, fluoroketone, fluoroketone-cooling | space-age/prototypes/technology.lua:1668 |
| 21 | `cryogenic-science-pack` | cryogenic-plant | trigger:craft-item item=cryogenic-plant | essential | cryogenic-science-pack | space-age/prototypes/technology.lua:1811 |
| 22 | `electric-weapons-damage-1` | destroyer | 250×30s [A+L+M+C+U] | upgrade | <ammo-damage beam +0.3> | space-age/prototypes/technology.lua:58 |
| 23 | `electric-weapons-damage-2` | electric-weapons-damage-1, space-science-pack | 500×60s [A+L+C+M+U+S] | upgrade | <ammo-damage beam +0.4> | space-age/prototypes/technology.lua:86 |
| 24 | `electric-weapons-damage-3` | electric-weapons-damage-2, tesla-weapons | 1000×60s [A+L+C+M+U+S+EM] | upgrade | <ammo-damage tesla +0.7>, <ammo-damage electric +0.7>, <ammo-damage beam +0.6> | space-age/prototypes/technology.lua:115 |
| 25 | `electric-weapons-damage-4` | electric-weapons-damage-3 | 2^(L-3)*1000×60s [A+L+C+M+U+S+EM] | max_level=infinite upgrade | <ammo-damage tesla +0.7>, <ammo-damage electric +0.7>, <ammo-damage beam +0.3> | space-age/prototypes/technology.lua:155 |
| 26 | `electromagnetic-plant` | holmium-processing | trigger:craft-item item=holmium-plate count=50 |  | electromagnetic-plant, superconductor, supercapacitor, electrolyte | space-age/prototypes/technology.lua:1463 |
| 27 | `electromagnetic-science-pack` | electromagnetic-plant | trigger:craft-item item=supercapacitor | essential | electromagnetic-science-pack | space-age/prototypes/technology.lua:1496 |
| 28 | `elevated-rail` | concrete, production-science-pack | 100×30s [A+L+C+P] |  | rail-support, rail-ramp, <rail-planner-allow-elevated-rails true> | elevated-rails/prototypes/technology/elevated-rails.lua:5 |
| 29 | `epic-quality` | agricultural-science-pack, utility-science-pack, quality-module | 5000×60s [A+L+C+U+S+Agr] |  | <unlock-quality epic> | quality/prototypes/technology.lua:91 |
| 30 | `fish-breeding` | tree-seeding | 500×60s [S+Agr] |  | fish-breeding, nutrients-from-fish | space-age/prototypes/technology.lua:1411 |
| 31 | `foundation` | cryogenic-science-pack | 2000×60s [A+L+C+P+U+S+Met+Agr+EM+Cry] |  | foundation | space-age/prototypes/technology.lua:1982 |
| 32 | `foundry` | calcite-processing, tungsten-carbide | trigger:craft-item item=tungsten-carbide |  | foundry, molten-iron-from-lava, molten-copper-from-lava, concrete-from-molten-iron, casting-low-density-structure, molten-iron, molten-copper, casting-iron, casting-steel, casting-copper, casting-iron-gear-wheel, casting-iron-stick, casting-pipe, casting-pipe-to-ground, casting-copper-cable | space-age/prototypes/technology.lua:661 |
| 33 | `fusion-reactor` | quantum-processor | 2000×60s [A+L+C+P+U+S+Met+Agr+EM+Cry] |  | fusion-reactor, fusion-generator, fusion-power-cell | space-age/prototypes/technology.lua:1832 |
| 34 | `fusion-reactor-equipment` | fusion-reactor, fission-reactor-equipment | 1000×60s [A+L+C+P+U+S+Met+Agr+EM+Cry] |  | fusion-reactor-equipment | space-age/prototypes/technology.lua:1873 |
| 35 | `health` | agricultural-science-pack, utility-science-pack, military-science-pack | 2^L*50×60s [M+U+Agr] | max_level=infinite | <character-health-bonus +50> | space-age/prototypes/technology.lua:1388 |
| 36 | `heating-tower` | planet-discovery-gleba | trigger:mine-entity entity=copper-stromatolite |  | heating-tower, heat-pipe, heat-exchanger, steam-turbine | space-age/prototypes/technology.lua:1613 |
| 37 | `holmium-processing` | recycling | trigger:craft-item item=holmium-ore |  | holmium-solution, holmium-plate | space-age/prototypes/technology.lua:1439 |
| 38 | `jellynut` | agriculture | trigger:mine-entity entity=jellystem |  | jellynut-processing, iron-bacteria | space-age/prototypes/technology.lua:963 |
| 39 | `legendary-quality` | cryogenic-science-pack, epic-quality | 5000×60s [A+L+C+P+U+S+Met+Agr+EM+Cry] |  | <unlock-quality legendary> | quality/prototypes/technology.lua:119 |
| 40 | `lightning-collector` | electromagnetic-science-pack | 1000×60s [A+L+C+S+EM] |  | lightning-collector | space-age/prototypes/technology.lua:1517 |
| 41 | `lithium-processing` | planet-discovery-aquilo | trigger:mine-entity entity=lithium-iceberg-big |  | lithium, lithium-plate | space-age/prototypes/technology.lua:1644 |
| 42 | `low-density-structure-productivity` | production-science-pack, metallurgic-science-pack | 1.5^L*1000×60s [A+L+C+P+Met] | max_level=infinite upgrade | <change-recipe-productivity low-density-structure +0.1>, <change-recipe-productivity casting-low-density-structure +0.1> | space-age/prototypes/technology.lua:2200 |
| 43 | `mech-armor` | electromagnetic-science-pack, power-armor-mk2 | 5000×60s [A+L+C+M+U+S+EM] |  | mech-armor | space-age/prototypes/technology.lua:852 |
| 44 | `metallurgic-science-pack` | tungsten-steel | trigger:craft-item item=tungsten-plate | essential | metallurgic-science-pack | space-age/prototypes/technology.lua:791 |
| 45 | `overgrowth-soil` | biter-egg-handling, production-science-pack, utility-science-pack | 2000×60s [A+L+C+P+U+S+Agr] |  | overgrowth-yumako-soil, overgrowth-jellynut-soil | space-age/prototypes/technology.lua:1327 |
| 46 | `planet-discovery-aquilo` | rocket-turret, advanced-asteroid-processing, heating-tower, asteroid-reprocessing, electromagnetic-science-pack | 3000×60s [A+L+C+P+U+S+Met+Agr+EM] | essential | <unlock-space-location aquilo>, ammoniacal-solution-separation, solid-fuel-from-ammonia, ammonia-rocket-fuel, ice-platform | space-age/prototypes/technology.lua:425 |
| 47 | `planet-discovery-fulgora` | space-platform-thruster, electric-energy-accumulators | 1000×60s [A+L+C+S] | essential | <unlock-space-location fulgora>, lightning-rod | space-age/prototypes/technology.lua:393 |
| 48 | `planet-discovery-gleba` | space-platform-thruster, landfill | 1000×60s [A+L+C+S] | essential | <unlock-space-location gleba> | space-age/prototypes/technology.lua:365 |
| 49 | `planet-discovery-vulcanus` | space-platform-thruster | 1000×60s [A+L+C+S] | essential | <unlock-space-location vulcanus> | space-age/prototypes/technology.lua:337 |
| 50 | `plastic-bar-productivity` | agricultural-science-pack, production-science-pack | 1.5^L*1000×60s [A+L+C+P+Agr] | max_level=infinite upgrade | <change-recipe-productivity plastic-bar +0.1>, <change-recipe-productivity bioplastic +0.1> | space-age/prototypes/technology.lua:2235 |
| 51 | `processing-unit-productivity` | electromagnetic-science-pack, production-science-pack | 1.5^L*1000×60s [A+L+C+P+EM] | max_level=infinite upgrade | <change-recipe-productivity processing-unit +0.1> | space-age/prototypes/technology.lua:2106 |
| 52 | `promethium-science-pack` | biter-egg-handling, fusion-reactor | 2000×60s [A+L+C+P+U+S+Met+Agr+EM+Cry] | essential | <unlock-space-location solar-system-edge>, <unlock-space-location shattered-planet>, promethium-science-pack | space-age/prototypes/technology.lua:1940 |
| 53 | `quality-module` | modules | 500×30s [A+L] | upgrade | quality-module, <unlock-quality uncommon>, <unlock-quality rare> | quality/prototypes/technology.lua:5 |
| 54 | `quality-module-2` | quality-module, space-science-pack | 500×30s [A+L+C+S] | upgrade | quality-module-2 | quality/prototypes/technology.lua:38 |
| 55 | `quality-module-3` | quality-module-2, electromagnetic-science-pack | 2000×60s [A+L+C+S+EM] | upgrade | quality-module-3 | quality/prototypes/technology.lua:64 |
| 56 | `quantum-processor` | cryogenic-science-pack | 500×60s [A+L+C+P+U+S+Met+Agr+EM+Cry] |  | quantum-processor | space-age/prototypes/technology.lua:1779 |
| 57 | `rail-support-foundations` | electromagnetic-science-pack, utility-science-pack, metallurgic-science-pack, elevated-rail | 2000×30s [A+L+C+P+U+S+Met+EM] |  | <rail-support-on-deep-oil-ocean true> | space-age/prototypes/technology.lua:1545 |
| 58 | `railgun` | quantum-processor | 2000×60s [A+L+C+M+U+S+Met+EM+Agr+Cry] |  | railgun, railgun-turret, railgun-ammo | space-age/prototypes/technology.lua:812 |
| 59 | `railgun-damage-1` | railgun | 2^(L-1)*1000×60s [A+L+C+M+U+S+Met+Agr] | max_level=infinite | <ammo-damage railgun +0.4> | space-age/prototypes/technology.lua:264 |
| 60 | `railgun-shooting-speed-1` | railgun | 2^(L-1)*1000×60s [A+L+C+M+U+S+EM+Cry] | max_level=infinite | <gun-speed railgun +0.15> | space-age/prototypes/technology.lua:231 |
| 61 | `recycling` | planet-discovery-fulgora | trigger:mine-entity entity=fulgoran-ruin-vault |  | recycler, scrap-recycling | quality/prototypes/technology.lua:148 |
| 62 | `research-productivity` | promethium-science-pack | 1.2^L*1000×120s [A+L+M+C+P+U+S+Met+EM+Agr+Cry+Pro] | max_level=infinite upgrade | <laboratory-productivity +0.1> | space-age/prototypes/technology.lua:2070 |
| 63 | `rocket-fuel-productivity` | agricultural-science-pack, production-science-pack | 1.5^L*1000×60s [A+L+C+P+Agr] | max_level=infinite upgrade | <change-recipe-productivity rocket-fuel +0.1>, <change-recipe-productivity rocket-fuel-from-jelly +0.1>, <change-recipe-productivity ammonia-rocket-fuel +0.1> | space-age/prototypes/technology.lua:2270 |
| 64 | `rocket-part-productivity` | cryogenic-science-pack | 1.5^L*2000×60s [A+L+C+P+Cry] | max_level=infinite upgrade | <change-recipe-productivity rocket-part +0.1> | space-age/prototypes/technology.lua:2310 |
| 65 | `rocket-turret` | rocketry, carbon-fiber, stronger-explosives-2 | 1000×30s [A+L+M+C+S+Agr] |  | rocket-turret, coal-synthesis | space-age/prototypes/technology.lua:534 |
| 66 | `scrap-recycling-productivity` | electromagnetic-science-pack, production-science-pack | 1.5^L*500×60s [A+L+C+P+EM] | max_level=infinite upgrade | <change-recipe-productivity scrap-recycling +0.1> | space-age/prototypes/technology.lua:2136 |
| 67 | `space-platform` | rocket-silo | trigger:create-space-platform |  | asteroid-collector, crusher, metallic-asteroid-crushing, carbonic-asteroid-crushing, oxide-asteroid-crushing, cargo-bay | space-age/prototypes/technology.lua:22 |
| 68 | `space-platform-thruster` | space-science-pack | 500×60s [A+L+C+S] |  | thruster, ice-melting, thruster-fuel, thruster-oxidizer | space-age/prototypes/technology.lua:299 |
| 69 | `stack-inserter` | carbon-fiber, production-science-pack, utility-science-pack, bulk-inserter | 1000×60s [A+L+C+P+U+S+Agr] |  | stack-inserter, <belt-stack-size-bonus +1> | space-age/prototypes/technology.lua:1145 |
| 70 | `steel-plate-productivity` | production-science-pack | 1.5^L*1000×60s [A+L+C+P] | max_level=infinite upgrade | <change-recipe-productivity steel-plate +0.1>, <change-recipe-productivity casting-steel +0.1> | space-age/prototypes/technology.lua:2166 |
| 71 | `tesla-weapons` | electromagnetic-science-pack, military-4 | 1500×60s [A+L+C+M+U+S+EM] |  | teslagun, tesla-turret, tesla-ammo | space-age/prototypes/technology.lua:1576 |
| 72 | `toolbelt-equipment` | power-armor, toolbelt, carbon-fiber | 300×30s [A+L+C+S+Agr] |  | toolbelt-equipment | space-age/prototypes/technology.lua:566 |
| 73 | `transport-belt-capacity-1` | stack-inserter | 2000×60s [A+L+C+P+U+S+Agr] | upgrade | <belt-stack-size-bonus +1> | space-age/prototypes/technology.lua:1179 |
| 74 | `transport-belt-capacity-2` | transport-belt-capacity-1 | 3000×60s [A+L+C+P+U+S+Agr] | upgrade | <belt-stack-size-bonus +1>, <inserter-stack-size-bonus +1> | space-age/prototypes/technology.lua:1210 |
| 75 | `tree-seeding` | agricultural-science-pack | 50×60s [A+L+C+S+Agr] |  | wood-processing | space-age/prototypes/technology.lua:1116 |
| 76 | `tungsten-carbide` | planet-discovery-vulcanus | trigger:mine-entity entity=big-volcanic-rock |  | carbon, tungsten-carbide | space-age/prototypes/technology.lua:619 |
| 77 | `tungsten-steel` | big-mining-drill | trigger:craft-item item=big-mining-drill |  | tungsten-plate | space-age/prototypes/technology.lua:736 |
| 78 | `turbo-transport-belt` | metallurgic-science-pack, logistics-3 | 500×60s [A+L+C+P+S+Met] |  | turbo-transport-belt, turbo-underground-belt, turbo-splitter | space-age/prototypes/technology.lua:755 |
| 79 | `worker-robots-speed-7` | worker-robots-speed-6, electromagnetic-science-pack | 2^(L-6)*1000×60s [A+L+C+P+U+S+EM] | max_level=infinite upgrade | <worker-robot-speed +0.65> | space-age/prototypes/technology.lua:474 |
| 80 | `yumako` | agriculture | trigger:mine-entity entity=yumako-tree |  | yumako-processing, copper-bacteria | space-age/prototypes/technology.lua:906 |

---

## 5. Item prototypes in 2.0.77

### 5.1 Item types
`defines.prototypes.item` (runtime-api.json `defines[name=prototypes].subkeys[name=item]`): `ammo`, `armor`, `blueprint`,
`blueprint-book`, `capsule`, `copy-paste-tool`, `deconstruction-item`, `gun`, `item`, `item-with-entity-data`, `item-with-inventory`,
`item-with-label`, `item-with-tags`, `module`, `rail-planner`, `repair-tool`, `selection-tool`, `space-platform-starter-pack`,
`spidertron-remote`, `tool`, `upgrade-item`. Walls/turrets/belts/drills/power buildings in base are plain `type = "item"` with `place_result`.
Vehicles/wagons use `item-with-entity-data` (e.g. `base/prototypes/item.lua` `car`).

### 5.2 ItemPrototype fields (API `prototypes[name=ItemPrototype]`, all properties)

| field | type | default | API note (abridged) |
|---|---|---|---|
| `stack_size` | ItemCountType | **REQ** | "Must be 1 when the "not-stackable" flag is set." |
| `icons` / `icon` / `icon_size` | IconData[] / FileName / SpriteSizeType | icon_size **64** | icon mandatory if no icons |
| `dark_background_icon(s)`, `dark_background_icon_size` | | 64 | used in alt-mode |
| `place_result` | EntityID | "" | "If this item should be the one that construction bots use to build the specified `place_result`, set the "primary-place-result" item flag. The localised name of the entity will be used as the in-game item name. This behavior can be overwritten by specifying `localised_name` on this item" |
| `place_as_equipment_result`, `place_as_tile`, `plant_result` | | | |
| `fuel_category` | FuelCategoryID | "" | "Must exist when a nonzero fuel_value is defined." |
| `fuel_value` | Energy | 0J | mandatory if any fuel_* multiplier / glow used |
| `burnt_result` | ItemID | "" | |
| `fuel_acceleration_multiplier`, `fuel_top_speed_multiplier`, `fuel_emissions_multiplier` | double | 1.0 | |
| `fuel_acceleration_multiplier_quality_bonus`, `fuel_top_speed_multiplier_quality_bonus` | double | 30% of (mult−1) if mult>1 | |
| `fuel_glow_color` | Color | | |
| `pictures` | SpriteVariations | | "Used to give the item multiple different icons so that they look less uniform on belts … Maximum number of variations is 16. When using sprites of size `64` (same as base game icons), the `scale` should be set to 0.5." |
| `flags` | ItemPrototypeFlags | | array of `"draw-logistic-overlay"`, `"excluded-from-trash-unrequested"`, `"always-show"`, `"hide-from-bonus-gui"`, `"hide-from-fuel-tooltip"`, `"not-stackable"`, `"primary-place-result"`, `"mod-openable"`, `"only-in-cursor"`, `"spawnable"`, `"spoil-result"`, `"ignore-spoil-time-modifier"` |
| `weight` | Weight | computed | "The default weight is calculated automatically from recipes and falls back to UtilityConstants::default_item_weight." (auxiliary page `runtime:item-weight` not in the JSON → details not found in sources) |
| `ingredient_to_weight_coefficient` | double | 0.5 | |
| `default_import_location` | SpaceLocationID | **nauvis** | description empty in API. `nauvis` is a `planet` defined by base too (`base/prototypes/planet/planet.lua:8`), so the default is valid without SA. |
| `spoil_ticks`, `spoil_result`, `spoil_to_trigger_result`, `spoil_level` | | 0 | SA-oriented |
| `send_to_orbit_mode` | SendToOrbitMode | not-sendable | |
| `rocket_launch_products` | ItemProductPrototype[] | | |
| `auto_recycle` | boolean | true | "Whether the item should be included in the self-recycling recipes automatically generated by the quality mod. This property is not read by the game engine itself, but the quality mod's data-updates.lua file." |
| `open_sound`, `close_sound`, `pick_sound`, `drop_sound`, `inventory_move_sound` | Sound | | |
| `color_hint`, `has_random_tint` (true), `random_tint_color`, `moved_to_hub_when_building`, `destroyed_by_dropping_trigger`, `hidden` (false) | | | |
| inherited | `name`, `order`, `subgroup`, `localised_name`, `localised_description`, `factoriopedia_*`, `parameter`, `custom_tooltip_fields` | | |

Mass constants are Lua globals from `core/lualib/util.lua:879-882`: `gram = 1`, `grams = gram`, `kg = 1000*grams`, `tons = 1000*kg`
(so `weight = 2 * kg` = 2000). `core/prototypes/utility-constants.lua:533-534`: `default_item_weight = 100`, `rocket_lift_weight = 1000000, -- 1 000 kg`.

Item sounds: `local item_sounds = require("__base__.prototypes.item_sounds")` (`base/prototypes/item.lua:2`); keys defined in
`base/prototypes/item_sounds.lua` include `metal_small_inventory_move/_pickup`, `metal_large_*`, `electric_small_*`, `electric_large_*`,
`wire_inventory_move/_pickup`, `transport_belt_*`, `drill_*`, `turret_*`, `concrete_*`, `brick_*`, `mechanical_*`, `science_*`, `module_*`,
`reactor_*`, `fuel_cell_*`, `energy_shield_*`, `low_density_*`, `resource_*` (full list: `grep -oE "^\s+[a-z_]+ = item_sound" base/prototypes/item_sounds.lua`).
`item_tints` from `require("__base__.prototypes.item-tints")` (`base/prototypes/item.lua:3`), e.g. `item_tints.iron_rust`.

### 5.3 Verbatim item examples

Intermediate with default 64px icon — `base/prototypes/item.lua:141-153`:
```lua
  {
    type = "item",
    name = "iron-plate",
    icon = "__base__/graphics/icons/iron-plate.png",
    subgroup = "raw-material",
    color_hint = { text = "I" },
    order = "a[smelting]-a[iron-plate]",
    inventory_move_sound = item_sounds.metal_small_inventory_move,
    pick_sound = item_sounds.metal_small_inventory_pickup,
    drop_sound = item_sounds.metal_small_inventory_move,
    stack_size = 100,
    random_tint_color = item_tints.iron_rust
  },
```
`copper-cable` (`base/prototypes/item.lua:166-178`) adds `stack_size = 200, weight = 0.25 * kg, ingredient_to_weight_coefficient = 0.25`.

Belt-variation `pictures` + fuel — `base/prototypes/item.lua:59-81` (`coal`):
```lua
    icon = "__base__/graphics/icons/coal.png",
    dark_background_icon = "__base__/graphics/icons/coal-dark-background.png",
    pictures =
    {
      {size = 64, filename = "__base__/graphics/icons/coal.png", scale = 0.5, mipmap_count = 4},
      {size = 64, filename = "__base__/graphics/icons/coal-1.png", scale = 0.5, mipmap_count = 4},
      ...
    },
    fuel_category = "chemical",
    fuel_value = "4MJ",
    subgroup = "raw-resource",
    order = "b[coal]",
    ...
    stack_size = 50,
    weight = 2 * kg,
```
Fuel with burnt result — `base/prototypes/item.lua:2311-2343` (`uranium-fuel-cell`): `fuel_category = "nuclear", burnt_result = "depleted-uranium-fuel-cell", fuel_value = "8GJ", stack_size = 50, weight = 100*kg`, `pictures = { layers = { {size = 64, filename = ..., scale = 0.5, mipmap_count = 4}, {draw_as_light = true, size = 64, filename = ...-light.png, scale = 0.5} } }`.
Fuel categories: base `chemical`, `nuclear` (`base/prototypes/categories/fuel-category.lua`); SA adds `food`, `nutrients`, `fusion` (`space-age/prototypes/categories/fuel-category.lua`).

Placeable item — `base/prototypes/item.lua:1284-1296`:
```lua
  {
    type = "item",
    name = "transport-belt",
    icon = "__base__/graphics/icons/transport-belt.png",
    subgroup = "belt",
    color_hint = { text = "1" },
    order = "a[transport-belt]-a[transport-belt]",
    inventory_move_sound = item_sounds.transport_belt_inventory_move,
    pick_sound = item_sounds.transport_belt_inventory_pickup,
    drop_sound = item_sounds.transport_belt_inventory_move,
    place_result = "transport-belt",
    stack_size = 100
  },
```
Wall/turret items: `stone-wall` (`base/prototypes/item.lua:566-577`, subgroup `defensive-structure`, order `a[stone-wall]-a[stone-wall]`, stack 100),
`gun-turret` (`:4592-4603`, subgroup `turret`, order `b[turret]-a[gun-turret]`, stack 50), `laser-turret` (`:4604-4616`, stack 50, `weight = 40*kg`).

Space-Age-only field example — `space-age/prototypes/item.lua:494-506`:
```lua
  {
    type = "item",
    name = "tungsten-plate",
    icon = "__space-age__/graphics/icons/tungsten-plate.png",
    subgroup = "vulcanus-processes",
    order = "c[tungsten]-c[tungsten-plate]",
    ...
    stack_size = 50,
    default_import_location = "vulcanus",
    weight = 4*kg
  },
```
A field unknown to the engine is ignored (API `Data`: "Any extra properties are ignored"), and `default_import_location` defaults to `nauvis`, which exists in base,
so the same item table is valid base-only. Setting it to an SA planet (e.g. "vulcanus") without SA: whether the engine errors — not found in sources.

Typical base stack sizes (emulated data): intermediate-product 5..200 (gear/stick 100, cable/circuits 200, engine units 50, LDS 50), raw-material 50..200 (plates 100, battery 200), raw-resource 50 (ores/coal/stone).

### 5.4 Quality mod side-effects on mod items/recipes (base+quality and SA)
`quality/data-updates.lua` runs in the data-updates stage over **all** recipes and items:
* reverse "recycling" recipes for every recipe that passes `default_can_recycle` (`quality/prototypes/recycling.lua:158-184`): skipped if `recipe.auto_recycle == false`, category `smelting`, `chemistry`, `crushing`, `organic`, most `metallurgy`/`cryogenics`, subgroup `empty-barrel`, or name containing "science" and "pack".
* self-recycling `<item>-recycling` recipe for every item unless `item.auto_recycle == false`, `item.parameter`, or name contains `-barrel` (`quality/data-updates.lua:8-25`).
* recycling recipe names use `{"recipe-name.recycling", <item name>}`; item name resolved by `get_item_localised_name` (`quality/prototypes/recycling.lua:12-35`): item `localised_name`, else the **place_result entity's** `localised_name`, else `{"entity-name.<ITEM name>"}` for placeable items / `{"item-name.<name>"}` otherwise. → Keep placeable item name == entity name, or set `localised_name`.

---

## 6. Item groups and subgroups

Prototype shapes (API): ItemGroup (`item-group`): `icon`/`icons`, `icon_size` default 64 ("The base game uses 128px icons for item groups"), `order_in_recipe`; ItemSubGroup (`item-subgroup`): `group` REQ. Verbatim `base/prototypes/item-groups.lua:1-24`:
```lua
data:extend(
{
-------------------------------------------------------------------------- LOGISTICS
  {
    type = "item-group",
    name = "logistics",
    order = "a",
    icon = "__base__/graphics/item-group/logistics.png",
    icon_size = 128,
  },
  {
    type = "item-subgroup",
    name = "storage",
    group = "logistics",
    order = "a"
  },
  {
    type = "item-subgroup",
    name = "belt",
    group = "logistics",
    order = "b"
  },
```

Groups and subgroups (subgroup order in parentheses) — emulated data; only the item-bearing groups:

| group (order) | subgroups, base 2.0.77 | extra / changed in SA |
|---|---|---|
| `logistics` (a) | storage(a), belt(b), inserter(c), energy-pipe-distribution(d), train-transport(e), transport(f), logistic-network(g), circuit-network(h), terrain(i) | — |
| `production` (b) | tool(a), energy(b), extraction-machine(c), smelting-machine(d), production-machine(e), module(f), space-related(g) | agriculture(da), environmental-protection(f); **module → g** (`space-age/base-data-updates.lua:301`); **space-related moved to group `space`, order e** (`:302-303`) |
| `intermediate-products` (c) | fluid-recipes(a), raw-resource(b), raw-material(c), barrel(d), fill-barrel(e), empty-barrel(f), intermediate-product(g), intermediate-recipe(h), uranium-processing(i), science-pack(y), internal-process(z) | vulcanus-processes(k), fulgora-processes(l), agriculture-processes(m), agriculture-products(n), nauvis-agriculture(o), aquilo-processes(p) |
| `space` (d) | — (SA only, icon `__space-age__/graphics/item-group/space.png`) | space-interactors(a), space-platform(a), space-rocket(b), space-related(e), space-environment(f), space-material(g), space-crushing(h), space-processing(i), planets(j), planet-connections(k) |
| `combat` (e) | gun(a), ammo(b), capsule(c), armor(d), equipment(e), utility-equipment(f), military-equipment(g), defensive-structure(h), turret(i), ammo-category(j) | — |
| `fluids` (f) | fluid(a) | — |
| other groups | signals(g), enemies(h), tiles(i), environment(l), effects(y), other(z) | |

Base group icons: `__base__/graphics/item-group/{logistics,production,intermediate-products,military,fluids,signals,effects}.png`, all `icon_size = 128`.

Items per relevant subgroup with `order` strings (base; **bold** = added by SA) — use these to slot Magnetics items:

* **raw-material**: iron-plate `a[smelting]-a[iron-plate]`, copper-plate `a[smelting]-b[copper-plate]`, steel-plate `a[smelting]-c[steel-plate]`, solid-fuel `b[chemistry]-a[solid-fuel]`, plastic-bar `b[chemistry]-b[plastic-bar]`, sulfur `b[chemistry]-c[sulfur]`, battery `b[chemistry]-d[battery]`, explosives `b[chemistry]-e[explosives]`, **carbon `b[chemistry]-f[carbon]`**
* **intermediate-product**: iron-gear-wheel `a[basic-intermediates]-a[iron-gear-wheel]`, iron-stick `…-b[iron-stick]`, copper-cable `…-c[copper-cable]`, barrel `…-d[empty-barrel]`, electronic-circuit `b[circuits]-a[electronic-circuit]`, advanced-circuit `b[circuits]-b[advanced-circuit]`, processing-unit `b[circuits]-c[processing-unit]`, engine-unit `c[advanced-intermediates]-a[engine-unit]`, electric-engine-unit `…-b[electric-engine-unit]`, flying-robot-frame `…-c[flying-robot-frame]`, low-density-structure `d[rocket-parts]-a[low-density-structure]`, rocket-fuel `d[rocket-parts]-b[rocket-fuel]`, rocket-part `d[rocket-parts]-d[rocket-part]` (not in this subgroup under SA)
* **belt**: transport-belt `a[transport-belt]-a[transport-belt]`, fast `…-b[fast-transport-belt]`, express `…-c[express-transport-belt]`, **turbo `a[transport-belt]-d[turbo-transport-belt]`**; underground `b[underground-belt]-a/b/c[...]` (**-d turbo**); splitter `c[splitter]-a/b/c[...]` (**-d turbo**); loaders `d[loader]-a/b/c[...]` (**-d turbo-loader**)
* **energy-pipe-distribution**: small/medium/big-electric-pole `a[energy]-a/b/c[...]`, substation `a[energy]-d[substation]`, pipe `a[pipe]-a[pipe]`, pipe-to-ground `a[pipe]-b[pipe-to-ground]`, pump `b[pipe]-c[pump]`
* **energy**: boiler `b[steam-power]-a[boiler]`, steam-engine `b[steam-power]-b[steam-engine]`, solar-panel `d[solar-panel]-a[solar-panel]`, accumulator `e[accumulator]-a[accumulator]`, nuclear-reactor `f[nuclear-energy]-a[reactor]`, heat-pipe `…-b[heat-pipe]`, heat-exchanger `…-c[heat-exchanger]`, steam-turbine `…-d[steam-turbine]`, **fusion-reactor `g[fusion-energy]-a[reactor]`, fusion-generator `g[fusion-energy]-b[generator]`**
* **extraction-machine**: burner-mining-drill `a[items]-a[burner-mining-drill]`, electric-mining-drill `a[items]-b[electric-mining-drill]`, **big-mining-drill `a[items]-c[big-mining-drill]`**, offshore-pump `b[fluids]-a[offshore-pump]`, pumpjack `b[fluids]-b[pumpjack]`
* **smelting-machine**: stone-furnace `a[stone-furnace]`, steel-furnace `b[steel-furnace]`, electric-furnace `c[electric-furnace]`, **foundry `d[foundry]`, recycler `d[recycler]`**
* **production-machine**: assembling-machine-1/2/3 `a/b/c[assembling-machine-N]`, oil-refinery `d[refinery]`, chemical-plant `e[chemical-plant]`, centrifuge `f[centrifuge]`, **electromagnetic-plant `g[electromagnetic-plant]`, cryogenic-plant `h[cryogenic-plant]`**, lab `z[lab]`, **biolab `z[z-biolab]`**
* **defensive-structure**: stone-wall `a[stone-wall]-a[stone-wall]`, gate `a[wall]-b[gate]`, radar `d[radar]-a[radar]`, land-mine `f[land-mine]`
* **turret**: gun-turret `b[turret]-a[gun-turret]`, laser-turret `b[turret]-b[laser-turret]`, flamethrower-turret `b[turret]-c[flamethrower-turret]`, artillery-turret `b[turret]-d[artillery-turret]-a[turret]`, **rocket-turret `b[turret]-e[...]`, tesla-turret `b[turret]-f[...]`, railgun-turret `b[turret]-g[...]`**
* **science-pack**: see §2 (base `a..g[...]`, SA `h..l`)

---

## 7. Icons and mipmaps in 2.0

* `icon_mipmaps` **no longer exists**: no property with that name anywhere in `prototype-api.json`, and `grep -rn icon_mipmaps` over all 2.0.77 Lua returns 0 hits.
* API `types[name=IconData]` description: "The game automatically generates icon mipmaps for all icons. However, icons can have custom mipmaps defined … If an icon file contains mipmaps then the game will automatically infer the icon's mipmap count. Icon files for custom mipmaps must contain half-size images with a geometric-ratio, for each mipmap level. Each next level is aligned to the upper-left corner, with no extra padding. Example sequence: `128x128@(0,0)`, `64x64@(128,0)`, `32x32@(192,0)` is three mipmaps."
* IconData fields: `icon` (REQ), `icon_size` (default 64), `scale` (default `(expected_icon_size / 2) / icon_size`), `shift` (default {0,0}, in units of `expected_icon_size/2` pixels), `tint`, `draw_background` (true for first layer), `floating` (false).
* **Expected icon sizes** (IconData.scale doc): "`512` for SpaceLocationPrototype::starmap_icon; `256` for TechnologyPrototype; `128` for AchievementPrototype and ItemGroup; `32` for ShortcutPrototype::icons and `24` for ShortcutPrototype::small_icons; `64` for the rest of the prototypes that use icons."
* So: item/recipe/entity/fluid icons 64 px (`icon_size` can be omitted); technology 256 px (`icon_size = 256` required since the default is 64); item-group 128 px.
* Base usage: 233 base item-like prototypes use `icon` without `icon_size` (→64); `copper-wire`/`red-wire`/`green-wire` use `icon_size = 56`. Techs: 101 `icon_size = 256`, 95 via `util.technology_icon_constant_*`.
* `mipmap_count` survives only on Sprite/Animation (`SpriteParameters::mipmap_count`, `AnimationParameters::mipmap_count` …: "Only loaded if this is an icon, that is it has the flag "group=icon" or "group=gui""), used in item `pictures` (`{size = 64, filename = …, scale = 0.5, mipmap_count = 4}`).
* Whether the base 64px icon PNGs contain baked mipmap strips: not found in sources (no PNGs in headless data). The item `pictures` entries declare `mipmap_count = 4` for 64px icons (e.g. `base/prototypes/item.lua:66-69`).
* `util.combine_icons(icons1, icons2, inputs, default_icon_size)` — `core/lualib/util.lua:352-376` — layers icons; uses `defines.default_icon_size`.

---

## 8. Locale (.cfg)

### 8.1 Paths
* `base/locale/en/base.cfg` (1544 lines), `base/locale/ru/base.cfg`, `base/locale/de/base.cfg` — all present in headless data.
* Other mods: `space-age/locale/<lang>/space-age.cfg`, `quality/locale/<lang>/quality.cfg`, `elevated-rails/locale/<lang>/elevated-rails.cfg`, `core/locale/<lang>/core.cfg` (+ `core/locale/<lang>/info.json` with fonts/`language-name`, e.g. ru: `"language-name": "Русский"`).
* Every shipped mod uses `locale/<lang>/<modname>.cfg`. Whether any `*.cfg` name inside `locale/<lang>/` is accepted: not found in sources.
* Language folder names are the codes seen under `base/locale/`: `en`, `ru`, `de`, `fr`, `pt-BR`, `zh-CN`, … (56 folders).

### 8.2 Syntax (observed)
* `[section]` headers, then `key=value` lines; UTF-8 without BOM (`od -c` of first bytes of en/ru `base.cfg` shows `p a r a`).
* A key before any section is legal: line 1 of every `base.cfg` is `parameter-x=Parameter __1__` (ru: `parameter-x=Параметр __1__`).
* Newline inside a value: literal `\n` (58 occurrences in `base/locale/en/base.cfg`, e.g. line 574).
* Parameters `__1__`, `__2__`; control macros `__CONTROL__build__`; rich text `[entity=rail-ramp]`, `[tip=z-dropping]` (e.g. `elevated-rails/locale/en/elevated-rails.cfg`, `base/locale/en/base.cfg:88`).
* Comments: lines beginning with `;` (`core/locale/en/core.cfg:1280`) and `#` (`core/locale/en/core.cfg:4837`) occur in shipped files.

### 8.3 Sections used by base (en, in file order: `grep -n "^\[" base/locale/en/base.cfg`)
`[autoplace-control-names]` 3, `[damage-type-name]` 11, `[map-gen-preset-name]` 21, `[map-gen-preset-description]` 32, **`[entity-description]` 43**, **`[entity-name]` 94**, `[decorative-name]` 333, `[equipment-name]` 376, **`[fluid-name]` 392**, `[virtual-signal-name]` 402, `[virtual-signal-description]` 558, **`[item-description]` 567**, `[item-group-name]` 598, **`[item-name]` 611**, `[modifier-description]` 749, **`[recipe-name]` 809**, **`[technology-name]` 827**, **`[technology-description]` 944**, `[tile-name]` 1060, `[ammo-category-name]` 1102, `[fuel-category-name]` 1118, `[airborne-pollutant-name]`, `[airborne-pollutant-name-with-amount]`, `[achievement-name]`, `[achievement-description]`, `[programmable-speaker-instrument]`, `[programmable-speaker-note]`, **`[mod-name]` 1377**, **`[mod-description]` 1380**, `[story]`, `[shortcut]`, `[controls]`, `[surface-property-name]`, `[surface-property-unit]`, `[space-location-name]`, `[space-location-description]`, `[tips-and-tricks-item-name]`, `[tips-and-tricks-item-description]`.
ru and de `base.cfg` contain the same sections (sorted alphabetically; e.g. ru `[mod-description]` 728, `[mod-name]` 730, `[technology-name]` 1094).
`[recipe-description]` and `[fluid-description]` are not in base but exist in `space-age/locale/en/space-age.cfg` (lines 517, 353) and `core/locale/en/core.cfg` (4681, 4666).

### 8.4 Which key a prototype uses (source-backed rules)
* Item with `place_result`: API ItemPrototype.place_result — "The localised name of the entity will be used as the in-game item name" (unless item `localised_name`). Base follows this: `transport-belt`, `fast-transport-belt`, `gun-turret`, `electric-mining-drill` appear under `[entity-name]` (en lines 112, 113, 124, 122) and **not** under `[item-name]`; `stone-wall=Wall` is in `[entity-name]` (en 196). Descriptions of placeable things are in `[entity-description]` (e.g. `accumulator=Stores a limited amount…` en 85).
* Plain intermediates: `[item-name]` (e.g. en 621 `iron-plate=Iron plate`, 624 `iron-gear-wheel=Iron gear wheel`, 641 `electronic-circuit=Electronic circuit`).
* Recipe: API RecipePrototype.main_product — "For recipes with one or more products: Subgroup, localised_name and icon default to the values of the singular/main product". Base `[recipe-name]` (en 809-825) therefore lists only multi-product/special recipes (`basic-oil-processing`, `fill-barrel=Fill __1__ barrel`, …).
* Technology: API — name `technology-3` → key `technology-name.technology`. Base en `[technology-name]` has `automation=Automation` (845), `logistics=Logistics` (855), `physical-projectile-damage=…` (864), `electric-energy-distribution=…` (887), `advanced-material-processing=…` (890) — i.e. without the number — but `[technology-description]` also has explicit numbered keys `automation-2=` / `automation-3=` (955-956) and `[technology-name]` has `electric-energy-accumulators-1=` (only numbered name key). The exact lookup order (full name first vs stripped) is not stated in sources beyond the API sentence.
* Science packs share `localised_description = {"item-description.science-pack"}` (`base/prototypes/item.lua:686`).
* Mod title/description in the mod list: `[mod-name]` / `[mod-description]` with key = mod name (`base=Base mod`, en 1377-1381; ru `base=Базовый мод`; de `base=Basis-Mod`).
* LocalisedString (API `types[name=LocalisedString]`): `{"key", params…}`, `""` concatenates, `"?"` takes the first valid alternative; max 20 params / 20 levels; keys ≤ 200 chars in prototype stage. Example from API: `localised_description = {"", {"item-name.iron-plate"}, ": ", tostring(60)}`.

### 8.5 Complete small locale example from a shipped mod — `elevated-rails/locale/en/elevated-rails.cfg` (sections at lines 1, 12, 15, 18, 21, 24, 27, 30)
```
[entity-name]
rail-ramp=Rail ramp
...
rail-support=Rail support

[technology-name]
elevated-rail=Elevated rail

[technology-description]
elevated-rail=Raised rail that can be placed over obstacles or water to reach new areas or make more efficient rail networks.

[mod-name]
elevated-rails=Elevated Rails

[mod-description]
elevated-rails=Mod that adds elevated rails.
```
Sample translations (ru/de, `base.cfg`): `transport-belt=Конвейер` / `Fließband` (488); `iron-gear-wheel=Железная шестерня` / `Eisenzahnrad` (633); `laser-turret=Лазерная турель` / `Laser-Geschützturm` (398); `[technology-name]` `steel-processing=Производство стали` / `Stahlverarbeitung` (1197) and `stone-wall=Каменная стена` / `Steinmauern` (1198).

---

## 9. info.json, dependencies, zip

### 9.1 Shipped info.json files (verbatim)
`space-age/info.json`:
```json
{
  "name": "space-age",
  "version": "2.0.77",
  "title": "Space Age",
  "author": "Wube Software",
  "contact": "dev@factorio.com",
  "homepage": "https://www.factorio.com",
  "dependencies": ["base >= 2.0.0", "elevated-rails >= 2.0.0", "quality >= 2.0.0"],
  "quality_required": true,
  "space_travel_required": true,
  "spoiling_required": true,
  "freezing_required": true,
  "segmented_units_required": true,
  "expansion_shaders_required": true,
  "factorio_version": "2.0"
}
```
`quality/info.json`: same shape, `"dependencies": ["base >= 2.0.0"]`, `"quality_required": true`, `"factorio_version": "2.0"`.
`elevated-rails/info.json`: `"dependencies": ["base >= 2.0.0"]`, `"rail_bridges_required": true`, `"factorio_version": "2.0"`.
`base/info.json`: name, version "2.0.77", title, author, contact, homepage, `"dependencies": []` (no factorio_version).

Fields observed: `name`, `version`, `title`, `author`, `contact`, `homepage`, `dependencies`, `factorio_version`, and the `<flag>_required` booleans.
The flags map 1:1 onto API `types[name=FeatureFlags]` properties: `quality`, `rail_bridges`, `space_travel`, `spoiling`, `freezing`, `segmented_units`, `expansion_shaders` (readable in the data stage as global `feature_flags`, API example `if feature_flags["spoiling"] then … end`).
Only quality, elevated-rails and space-age set `_required` flags; a mod meant to run on base alone should set none of them (whether setting one forces the expansion is not stated in sources, but see the next sentence). Locale key `mod-requires-space-age=Mod __1__ requires Space Age expansion.` exists (`core/locale/en/core.cfg:289`); the exact condition that triggers it is not in sources.
Version string format (binary string): `Invalid version: Expected 'a.b' or 'a.b.c', but '%s' was given`.
`description` field, `package`: strings exist in the binary but no shipped info.json uses them → semantics not found in sources.

### 9.2 Dependency syntax
From the game binary's error message (`strings /opt/factorio/bin/x64/factorio`, read-only):
`Mod %s dependency %s not matching pattern "[?|(?)|!|~] ModName [ModVersion specifier]".`
* prefixes allowed: `?`, `(?)`, `!`, `~`. Support in GUI strings: `?` ↔ `optional-dependency=(optional)`, `!` ↔ `incompatibilities=Incompatible with` / `dependency-incompatible=Incompatible with __1__`. The meanings of `(?)` and `~` are **not** spelled out in sources. GUI strings that do exist: `optional-dependency=(optional)`, `incompatibilities=Incompatible with`, `optional-dependencies=Optional dependencies` (`core/locale/en/core.cfg` `[gui-mod-info]`, lines 3689-3713), errors `dependency-missing`, `dependency-not-satisfied`, `dependency-incompatible`, `circular-dependencies`, `factorio-version-incompatible=Incompatible Factorio version (current: __1__, required: __2__)` (`[gui-mod-load-error]`, 4925-4939).
* version specifier example only `>=` (`"base >= 2.0.0"`); other operators: not found in sources.
* Suggested for Magnetics: `"dependencies": ["base >= 2.0.0", "? quality", "? elevated-rails", "? space-age"]`. **Unverified assumption (not in sources):** that an optional dependency makes Magnetics load after that mod when it is active. It matters because SA rewrites base techs inside its own `data.lua` (`space-age/data.lua:65` → `base-data-updates.lua`). Alternative: do cross-mod tech/recipe edits in Magnetics' `data-updates.lua` / `data-final-fixes.lua`. **Also an assumption:** that all mods' `data.lua` run before any `data-updates.lua` (stage order is described only on the API auxiliary page `runtime:data-lifecycle`, which is not in the JSON; the emulator in §0 assumed this order and the quality mod's design — generating recycling recipes for all recipes in `quality/data-updates.lua:4-6` — is consistent with it).
* In the data stage, `mods["space-age"]` is non-nil iff SA is active (API `types[name=Mods]`: "if mods["pizza"] then pineapple() end").

### 9.3 Zip / folder layout
* Binary string: `Filename of mod %s doesn't match the expected %s_%s%s (case sensitive!)` → the zip/folder file name must be `<name>_<version>` (+ `.zip`), e.g. `magnetics_0.1.0.zip`.
* File names present as literal strings in the binary: `info.json`, `thumbnail.png`, `changelog.txt`, `settings.lua`, `settings-updates.lua`, `settings-final-fixes.lua`, `data.lua`, `data-updates.lua`, `data-final-fixes.lua`, `control.lua`. Shipped mods use only `data.lua` (base, quality, elevated-rails, space-age) and `data-updates.lua` (base, quality, space-age); plus `locale/<lang>/<mod>.cfg` and `migrations/` (base, space-age).
* Whether the zip must contain a single top-level folder and what it must be called: not found in sources.
* Max mod name/title length: locale `mod-name-too-long=… maximum mod name length is __2__ characters.` (`core/locale/en/core.cfg:286`); the number itself not found in sources.

---

## 10. Gotchas / name collisions for "Magnetics" (all source-backed)

1. **`magnetic-field` already exists** as a `surface-property` in **base** (`base/prototypes/planet/surface-property.lua:13-16`, `default_value = 90`; en name "Magnetic field", unit `__1__ %`, `base/locale/en/base.cfg:1433, 1441`). Do not reuse the name for another type in the same namespace; it can be used in recipe/entity `surface_conditions`.
2. SA names to avoid: item/recipe `superconductor` (SA), `supercapacitor`, `electrolyte`, `holmium-plate`; tech/tool `electromagnetic-science-pack`; tech/item/entity `electromagnetic-plant`; **recipe-category `electromagnetics`** (`space-age/prototypes/categories/recipe-category.lua:61`). Magnetics names like `superconducting-wire`, `ferrite`, `magnet-alloy`, `*-coil` have no match in any 2.0.77 Lua (grep for magnet|coil|ferrite|supercond over all prototypes). Prefixing all names (e.g. `mag-…`) removes the risk entirely.
3. Belt tier: SA already occupies `a[transport-belt]-d[turbo-transport-belt]` and `d` slots in underground/splitter/loader; SA `turbo-transport-belt` tech depends on `metallurgic-science-pack, logistics-3`. Give the Magnetics belt a distinct order string. API `types[name=Order]`: order strings are sorted lexicographically (UTF-8: `-` < `0-9` < `A-Z` < `[` < `]` < `a-z`), "The `"-"` or `"[]"` structures … do *not* have any special meaning", equal orders fall back to prototype name. E.g. `a[transport-belt]-c[express-transport-belt]` < `a[transport-belt]-ca[…]` < `a[transport-belt]-d[turbo-transport-belt]`.
4. `mining-productivity-4` disappears with SA; `space-science-pack` changes trigger; `rocket-silo` changes prerequisites/effects; `automation-3` costs 500 in SA.
5. `space-related` subgroup is in group `production` in base but `space` in SA; `module` subgroup order f→g in SA.
6. Quality auto-generates `<item>-recycling` and reverse recipes for every Magnetics item/recipe unless `auto_recycle = false`; recycling-recipe names fall back to `entity-name.<item name>` for placeable items.
7. Tech icon: omit `icon_size` and a 256px PNG is read as 64px (default 64 per API).
8. Items: `default_import_location` defaults to `nauvis`, which exists in base, so it is safe to omit.

---

## 11. Not found in sources (explicit list)
* data-stage order (data → data-updates → data-final-fixes across all mods) and effect of optional dependencies on load order;
* numeric value of `defines.default_icon_size` (define exists without value; emulator assumed 64);
* item-weight algorithm (API points to auxiliary page `runtime:item-weight`, not in JSON);
* meanings of `(?)` and `~` dependency prefixes beyond the regex; supported version operators other than `>=`;
* zip inner folder rule; max mod name length; whether any `*.cfg` filename is loaded; mod load order tie-breaking;
* whether `unit` and `research_trigger` may both be set; exact locale lookup order for numbered tech names;
* whether an SA planet name in `default_import_location` errors when SA is absent;
* anything about PNG content (no PNGs in the headless build).
