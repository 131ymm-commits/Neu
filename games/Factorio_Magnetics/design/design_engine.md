# Magnetics for Factorio 2.0.77: design document (engine-feasibility-first version)

Angle: every mechanic uses a prototype type and fields that the recon files prove exist. Every entity is a `table.deepcopy` of a vanilla entity of the **same type**. Scripting is limited to one feature (the mend coil). Every number can be checked on the headless server. Space Age, quality and elevated-rails compatibility is handled explicitly, feature by feature.

## 0. Sources and citation keys

| Key | File | What it is |
|---|---|---|
| [C] | `scratchpad/recon/crafting.md` | crafting machines, recipes, categories, tint walker, recycling rules |
| [L] | `scratchpad/recon/logistics.md` | belts, undergrounds, splitters, upgrade chains |
| [P] | `scratchpad/recon/power.md` | poles, accumulator, burner-generator, EEI, fuels |
| [M] | `scratchpad/recon/mining.md` | drills, resources, area arithmetic |
| [K] | `scratchpad/recon/combat.md` | turrets, ammo, line/chain triggers, walls, biters, bonuses |
| [T] | `scratchpad/recon/tech.md` | tech tree, science packs, subgroups, locale, info.json |
| [H] | `scratchpad/recon/harness.md` | runtime API for tests (surfaces, EEI, belts, biters, statistics) |
| [RB] / [RS] | `scratchpad/fx/raw_base.json` / `raw_sa.json` | `data.raw` dumped by the 2.0.77 headless pilot (base only / base + elevated-rails + quality + space-age) |
| [PL] | `scratchpad/fx/wd/script-output/pilot.json` | pilot runtime measurements, 2.0.77 headless |
| [API] | `/opt/factorio-api/prototype-api.json`, `runtime-api.json` | property existence checked on 2026-09-30 |
| [D] | `/opt/factorio/data/...` | game Lua, cited by path and line |

The pilot [PL] already confirms four harness methods on the real server:
- AM2 made 15 gears in 600 ticks, i.e. 1.5/s = 0.75/0.5.
- The electric drill mined 5 ore in 600 ticks, i.e. 0.5/s, with `mining_area` 5×5 (4.01 to 8.99).
- An express belt measured 45 items/s = 0.09375 × 480.
- An EEI buffer drop of about 2.45 MJ in 10 s matches AM2 (150 kW + 5 kW drain) plus the drill (90 kW).

Anything not settled by these sources is marked **PILOT-n** and listed in §9.

---

## 1. Concept and progression

### 1.1 Theme mapping: Mindustry → Factorio-native

| Mindustry Magnetics | Factorio Magnetics | Why it changed |
|---|---|---|
| Kiln (sand+lead→ferrite) | **Sintering kiln** (burner furnace: iron ore → ferrite) | A Factorio furnace has one input slot: "The number of input slots, but not more than 1" [C §1]. Single-ingredient sintering fits the burner-furnace tier. |
| Induction furnace (Ti+Si→alloy) | **Induction furnace** (assembler: steel + ferrite + copper → magnet alloy) | Multi-ingredient, so it must be an `assembling-machine` [C §4]. |
| Coil winder | **Coil winder**: coil specialist with +25% built-in productivity. Coils are also craftable in AM2/AM3. | Mirrors SA's electromagnetic plant (`base_effect = {productivity = 0.5}`) [C §2.10]. |
| Cryo chamber + cryofluid | **Cryo chamber** (chemical-plant body) + **cryofluid** (water + petroleum gas: a hydrocarbon refrigerant) | Base Factorio has no cold fluid. Fluid recipes need fluid boxes, and the chemical plant has 2 in / 2 out [C §2.7]. |
| Flux resonator (phase fabric) | **Flux resonator** (centrifuge body): superconductor + U-238 + processing unit → flux crystal | Thorium ≈ uranium. This gives a sink for surplus U-238. |
| Magnetic separator (scrap) | **Magnetic separator** (furnace, auto-recipe like the recycler): stone → iron ore (magnetite recovery); uranium ore → U-235/U-238 (**calutron**) | Base has no scrap. A calutron is a real electromagnetic isotope separator. The recycler is the vanilla precedent for a multi-output furnace (`result_inventory_size = 12`) [C §1]. |
| Magnetic drill (+20%) | **Magnetic mining drill**: electric-drill upgrade with 2× speed | Drop-in `next_upgrade` from the electric drill [M §9.1]. |
| Mag conveyor / junction / router / bridge | **Maglev belt, underground (reach 13), splitter**, 75 items/s | Factorio has belts, undergrounds and splitters. Junctions and routers do not exist. |
| Coil / superconducting batteries | **SMES** (accumulator, 10 MJ, 2.5 MW) | Factorio accumulators are 2×2. The theme becomes "fast, dense storage". |
| Superconducting node | **Superconducting substation** (wire 24, supply 24×24) | `substation.next_upgrade` [P §3]. |
| MHD generator (pyratite+cryofluid) | **MHD generator**: burner-generator, 3 MW, 80% efficiency, no water | A `burner-generator` takes item fuel only [P §7.1]. |
| Flux reactor | **Flux dynamo**: burner-generator, 10 MW, burns flux crystals (new fuel category) | Same type. A fuel category is a base prototype [P §9.3]. |
| Ferrite / magnet / superconducting walls (1×1 and 2×2) | 3 walls, 1×1, in an upgrade chain from the stone wall | Factorio walls are 1×1 [K §11]. |
| Mend projector | **Mend coil** (EEI body + control script) | Vanilla has no area-repair building. This is the one scripted feature (§6). |
| Force projector | **Dropped** | No building type makes a dome shield. Energy shields exist only as armor equipment, which the recon does not cover. |
| Duo-class coilgun / Gauss | **Coilgun turret**: electric + ammo, fires hitscan slugs (ferrite / alloy) | Two Mindustry turrets merge into one turret with two ammo tiers, the Factorio convention (firearm → piercing → uranium) [K §6.2]. |
| Arc | **Arc emitter** (electric turret, chain lightning) | `chain-active-trigger` is a core type [K §9, §15.4]. |
| Maglev flak (AA) | **Dropped** | Base Factorio has no air enemies. |
| Railgun | **Rail cannon**: line attack, power per shot | SA railgun structure (line trigger + `energy_per_shot`) [K §5.4, §6.4], rebuilt on the base gun-turret body. |
| Air units + unit factory | **Dropped** | No air combat units in base. The support role goes to the mend coil, the fighter role to the coilgun. |

### 1.2 Where the mod sits in a normal playthrough

| Stage (packs) | Magnetics content | Hangs on vanilla tech |
|---|---|---|
| Red (A), about 20–40 min | Ferrite, sintering kiln, ferrite wall | `stone-wall` |
| Green (A+L) | Magnet alloy, induction furnace, coils, coil winder, coilgun + ferrite slugs | `steel-processing`, `logistic-science-pack`, `automation-2`, `gun-turret`, `military-2` |
| Military (A+L+M) | Magnet wall, alloy slugs, mend coil | `military-science-pack`, `repair-pack` |
| Blue (A+L+C) | MHD generator, magnetic drill, separator (+ calutron after uranium), cryofluid, superconducting cable, SMES, superconducting substation, arc emitter (+M), superconducting wall (+M) | `chemical-science-pack`, `advanced-material-processing-2`, `uranium-processing`, `electric-energy-distribution-2`, `electric-energy-accumulators`, `laser-turret`, `military-3`, `concrete` |
| Purple (A+L+C+P) | Maglev belts (base) | `logistics-3` (+ SA: `turbo-transport-belt`) |
| Yellow (A+L+C+P+U) | Flux resonator, flux crystal, flux dynamo, rail cannon, rail slugs | `production-science-pack`, `utility-science-pack` |

The mod never requires space science in base. It hooks in only after vanilla milestones (never before them) and is not required for any vanilla technology.

### 1.3 Coexistence with Space Age

| SA content | Magnetics counterpart | How they coexist |
|---|---|---|
| Turbo belt 60/s (Vulcanus, metallurgic pack) [L §2] | Maglev 75/s | Under SA the maglev recipe consumes **turbo** belts, undergrounds and splitters. Its tech requires `turbo-transport-belt` and costs A+L+C+P+S+Met ×500×60 s, the same set as turbo [RS]. Upgrade chain: express → turbo → maglev. In base: express → maglev. |
| Electromagnetic plant (Fulgora) | Coil winder | In data-updates the EM plant gets the category `magnetics-winding-or-assembling`. On Fulgora the EM plant (speed 2, +50%) becomes the better coil maker, which fits the SA philosophy. |
| Tesla turret (EM pack; 120 dmg/bounce, 10 jumps, range 30) [K §5.5, §9] | Arc emitter (C+M; 60 + 4×40, range 20) | Arrives earlier and is weaker. It uses ammo category `laser`, so it gets vanilla laser bonuses in both configs. |
| Railgun turret (Aquilo; 10 000 dmg line, range 40) [K §5.4, §6.4] | Rail cannon (U; 600 dmg line, range 36) | Arrives earlier and is weaker. Different display name: "Rail cannon". |
| Big mining drill (Vulcanus; 2.5 speed, 13×13, 50% drain, hard-solid) [M §5] | Magnetic drill (1.0 speed, 5×5, 100% drain, basic-solid only) | Hard-solid is never added. The big drill stays strictly better once reached. |
| SA item `superconductor` [T §10] | Our item `magnetics-superconductor`, displayed as "Superconducting cable" | Avoids two different items both called "Superconductor". |
| Fulgora recycler / scrap | Magnetic separator | Different inputs. Nothing references scrap. |
| Freezing (Aquilo), pressure (space) | Heating and surface conditions are inherited from the deepcopied source, plus one explicit pressure condition on the MHD generator | §7.4 |

---

## 2. Items and fluids

Stack sizes follow the nearest vanilla analogue [RB]: plates, steel and plastic 100; copper cable 200; solid fuel 50; accumulator, substation and turrets 50; chemical plant 10 [C §2.12]; steam engine 10 [P §1].

| # | name | type | stack | subgroup / order | use |
|---|---|---|---|---|---|
| I1 | `magnetics-ferrite` | item | 100 | raw-material / `a[smelting]-d[magnetics-ferrite]` (after steel `c`) [T §6] | alloy, ferrite wall, ferrite slugs, induction furnace, coilgun |
| I2 | `magnetics-magnet-alloy` | item | 100 | raw-material / `a[smelting]-e[magnetics-magnet-alloy]` | coils, superconductor, walls, machines |
| I3 | `magnetics-coil` | item | 100 | intermediate-product / `a[basic-intermediates]-e[magnetics-coil]` | nearly every machine, belts, power |
| I4 | `magnetics-superconductor` ("Superconducting cable") | item | 100 | intermediate-product / `c[advanced-intermediates]-e[magnetics-superconductor]` | maglev, SMES, substation, walls, flux, rail slugs |
| I5 | `magnetics-flux-crystal` | item, `fuel_category = "magnetics-flux"`, `fuel_value = "1GJ"` | 50 | intermediate-product / `c[advanced-intermediates]-f[magnetics-flux-crystal]` | flux dynamo fuel, flux rail slug |
| F1 | `magnetics-cryofluid` | fluid: `default_temperature = 15`, `base_color = {0.62,0.90,1.00}`, `flow_color = {0.85,0.97,1.00}`, **`auto_barrel = false`** | — | fluid / `a[fluid]-c[magnetics]-a[cryofluid]` | superconductor |
| A1 | `magnetics-ferrite-slug` | ammo, `magnetics-slug`, magazine 10 | 100 | new `magnetics-ammo` (group combat, order `ba`) / `a` | coilgun |
| A2 | `magnetics-alloy-slug` | ammo, `magnetics-slug`, magazine 10 | 100 | `magnetics-ammo` / `b` | coilgun |
| A3 | `magnetics-rail-slug` | ammo, `magnetics-rail`, magazine 5 | 20 | `magnetics-ammo` / `c` | rail cannon |
| A4 | `magnetics-flux-rail-slug` | ammo, `magnetics-rail`, magazine 5, `range_modifier = 1.1` | 20 | `magnetics-ammo` / `d` | rail cannon |

Notes on the table:
- **Cryofluid** has `auto_barrel = false`. Base `data-updates.lua` would otherwise create `magnetics-cryofluid-barrel` and `empty-magnetics-cryofluid-barrel`. The second name breaks the prefix rule. The opt-out is at [D base/data-updates.lua:13,279], and `FluidPrototype.auto_barrel` exists [API]. Cryofluid is an in-situ coolant: it is made next to the chamber that consumes it.
- `default_temperature = 15` is a plain, documented value [RB water]. A negative "cold" temperature is not used because nothing in the recon exercises it.
- **Placing items** (one per entity, 21 items). Each has `place_result = <entity>` (same name as the entity). The display name comes from the entity [T §8.4]. Stack size, vanilla subgroup and order [T §6]:

| placing item | stack | subgroup / order |
|---|---|---|
| sintering-kiln | 50 | smelting-machine / `a[stone-furnace]-m[magnetics-sintering-kiln]` |
| magnetic-separator | 50 | smelting-machine / `c[electric-furnace]-m[magnetics-magnetic-separator]` |
| induction-furnace, coil-winder | 50 | production-machine / `m[magnetics]-a[induction-furnace]`, `-b[coil-winder]` |
| cryo-chamber | 10 | production-machine / `m[magnetics]-c[cryo-chamber]` |
| flux-resonator | 20 | production-machine / `m[magnetics]-d[flux-resonator]` |
| magnetic-drill | 50 | extraction-machine / `a[items]-b[electric-mining-drill]-m[magnetics]` |
| maglev-belt / -underground-belt / -splitter | 100 / 50 / 50 | belt / `a[transport-belt]-e[…]`, `b[underground-belt]-e[…]`, `c[splitter]-e[…]` [L §5] |
| mhd-generator, flux-dynamo | 10, 10 | energy / `b[steam-power]-m[…]`, `f[nuclear-energy]-m[…]` |
| smes | 50 | energy / `e[accumulator]-m[magnetics-smes]` |
| superconducting-substation | 50 | energy-pipe-distribution / `a[energy]-e[magnetics-…]` |
| ferrite-wall, magnet-wall, superconducting-wall | 100 each | defensive-structure / `a[stone-wall]-m[magnetics]-a/b/c` |
| mend-coil | 50 | defensive-structure / `e[magnetics-mend-coil]` |
| coilgun, arc-emitter | 50, 50 | turret / `b[turret]-m[magnetics]-a/b` |
| rail-cannon | 10 | turret / `b[turret]-m[magnetics]-c` |
- **Ammo** uses hitscan `line` triggers (§4.4). No projectile prototypes are needed.

Content count:
- 5 intermediate items + 1 fluid + 4 ammo = 10.
- 21 entities (each with its placing item).
- That is **31 content pieces** (52 item/entity prototypes).

Helper prototypes (not content):
- 6 recipe-categories: `magnetics-sintering`, `magnetics-induction`, `magnetics-winding-or-assembling`, `magnetics-cryogenics`, `magnetics-resonance`, `magnetics-separation`.
- 1 fuel-category: `magnetics-flux`.
- 2 ammo-categories: `magnetics-slug`, `magnetics-rail`, each with its own `bonus_gui_order` [K §2.1].
- 1 item-subgroup: `magnetics-ammo`.
- 1 chain-active-trigger: `magnetics-arc-chain`.
- 1 beam: `magnetics-arc-beam`, visual only.
- 1 explosion: `magnetics-rail-tracer`, the only procedurally drawn world sprite (§4.6).

In total 33 recipes and 16 technologies.

---

## 3. Recipes

"Prod" = `allow_productivity`. The vanilla default is false, and vanilla intermediates set true [C §11.1, §13]. "AR" = `auto_recycle` (default true) [C §11.3]. Every recipe has `enabled = false` and is unlocked by exactly one tech.

### 3.1 Intermediates, fluid, ammo

| # | recipe | category (machine) | ingredients | results | energy_required s | Prod | AR |
|---|---|---|---|---|---|---|---|
| R1 | `magnetics-ferrite` | magnetics-sintering (kiln) | iron-ore 1 | ferrite 1 | 3.2 | yes | **false** (smelting-like; vanilla smelting is not recycled [C §11.3]) |
| R2 | `magnetics-magnet-alloy` | magnetics-induction (induction furnace) | steel-plate 1, ferrite 3, copper-plate 1 | magnet-alloy 2 | 6 | yes | **false** (metal, like steel) |
| R3 | `magnetics-coil` | magnetics-winding-or-assembling (coil winder, AM2, AM3, SA EM plant) | magnet-alloy 1, copper-cable 6 | coil 2 | 3 | yes | true |
| R4 | `magnetics-cryofluid` | magnetics-cryogenics (cryo chamber) | water 100, petroleum-gas 20 | cryofluid 100 | 2 | yes | **false** (fluid only) |
| R5 | `magnetics-superconductor` | magnetics-cryogenics | magnet-alloy 2, plastic-bar 1, cryofluid 25 | superconductor 1 | 8 | yes | true |
| R6 | `magnetics-flux-crystal` | magnetics-resonance (flux resonator) | superconductor 2, uranium-238 3, processing-unit 1 | flux-crystal 1 | 30 | yes | true |
| R7 | `magnetics-magnetite-recovery` | magnetics-separation (separator) | stone 10 | iron-ore 3 | 5 | yes | **false** |
| R8 | `magnetics-calutron-enrichment` | magnetics-separation | uranium-ore 10 | uranium-235 1 (probability 0.01), uranium-238 1 (probability 0.99) | 20 | yes | **false** (2 products; `main_product = ""`, own icon, subgroup `uranium-processing`) |
| R9 | `magnetics-ferrite-slug` | crafting | ferrite 2, iron-plate 1 | ferrite-slug 1 | 2 | no | true |
| R10 | `magnetics-alloy-slug` | crafting | ferrite-slug 1, magnet-alloy 1, copper-plate 2 | alloy-slug 1 | 5 | no | true |
| R11 | `magnetics-rail-slug` | crafting | superconductor 1, magnet-alloy 2, steel-plate 2 | rail-slug 1 | 10 | no | true |
| R12 | `magnetics-flux-rail-slug` | crafting | rail-slug 1, flux-crystal 1 | flux-rail-slug 1 | 15 | no | true |

Recipe details:
- **R7** is a single-product recipe whose product (iron ore) has a different name. It sets its own `icons`, `localised_name` and subgroup `raw-resource`, because otherwise the name and icon default to iron ore [T §8.4].
- **R8** follows the vanilla multi-product pattern (uranium-processing: 10 ore, 12 s, 0.007/0.993) [RB] [C §11.2].
- **R4/R5** set `crafting_machine_tint`, as plastic-bar does [C §11.2], because the chemical-plant body tints its liquid and smoke working visualisations by recipe [C §7.3].

### 3.2 Buildings

Every recipe is in category `crafting` (hand-craftable in both configs, [C §3]) unless it has fluid. "TOP" means `express-*` in base and `turbo-*` when `mods["space-age"]` is set.

| # | recipe → result | ingredients | energy s |
|---|---|---|---|
| R13 | sintering kiln | stone-furnace 1, iron-plate 5 | 1 |
| R14 | induction furnace | steel-plate 10, electronic-circuit 10, ferrite 20, stone-brick 10 | 5 |
| R15 | coil winder | assembling-machine-2 1, magnet-alloy 10, coil 10, electronic-circuit 10 | 5 |
| R16 | cryo chamber | chemical-plant 1, coil 10, magnet-alloy 10, advanced-circuit 5 | 5 |
| R17 | flux resonator | centrifuge 1, superconductor 20, coil 20, processing-unit 10 | 10 |
| R18 | magnetic separator | electric-furnace 1, coil 20, magnet-alloy 10, advanced-circuit 10 | 5 |
| R19 | magnetic mining drill | electric-mining-drill 1, coil 5, magnet-alloy 5, advanced-circuit 2 | 3 |
| R20 | maglev belt ×2 | TOP transport-belt 2, superconductor 1, coil 2, **lubricant 40** — category `crafting-with-fluid` (exists in base, and on AM2/AM3 under SA [RS]) | 1 |
| R21 | maglev underground belt ×2 | TOP underground-belt 2, superconductor 4, coil 8, lubricant 80 — `crafting-with-fluid` | 2 |
| R22 | maglev splitter | TOP splitter 1, superconductor 2, coil 4, processing-unit 2, lubricant 80 — `crafting-with-fluid` | 2 |
| R23 | MHD generator | steel-plate 20, coil 20, magnet-alloy 10, advanced-circuit 10, stone-brick 20 | 10 |
| R24 | flux dynamo | superconductor 20, coil 40, processing-unit 10, low-density-structure 10 | 20 |
| R25 | SMES | accumulator 1, superconductor 4, coil 6 | 10 |
| R26 | superconducting substation | substation 1, superconductor 2, coil 4 | 2 |
| R27 | ferrite wall | ferrite 5, stone-brick 2 | 0.5 |
| R28 | magnet wall | ferrite-wall 1, magnet-alloy 2 | 1 |
| R29 | superconducting wall | magnet-wall 1, superconductor 1, concrete 4 | 2 |
| R30 | mend coil | coil 10, steel-plate 5, electronic-circuit 5, repair-pack 10 | 5 |
| R31 | coilgun turret | gun-turret 1, coil 6, ferrite 10, electronic-circuit 5 | 8 |
| R32 | arc emitter | laser-turret 1, coil 20, magnet-alloy 10 | 20 |
| R33 | rail cannon | steel-plate 40, superconductor 20, coil 30, magnet-alloy 20, processing-unit 10 | 20 |

Building recipes keep the vanilla defaults `allow_productivity = false` and `auto_recycle = true`, so under quality they get recycling recipes. The "previous tier as ingredient" pattern (R15–R19, R25, R26, R28, R29, R31, R32) copies vanilla (AM2 takes AM1; express belt takes fast belt) [RB].

---

## 4. Entities

### 4.1 Common deepcopy procedure (data.lua)

`make(ptype, src, name, tint)`:
1. `e = table.deepcopy(data.raw[ptype][src])` [C §10.1].
2. Set `e.name = name` and `e.minable.result = name`.
3. Replace the icon: `e.icon = nil; e.icons = {{icon = "__magnetics__/graphics/icons/<name>.png", icon_size = 64}}`.
4. Clear inherited links: `e.next_upgrade = nil` [C §10.2] and `e.factoriopedia_simulation = nil`. The express-UG simulation is a blueprint of express entities [L §12.3].
5. Set `fast_replaceable_group` to the value in the table below (the name itself for non-upgrades).
6. Set the type-specific links: `related_underground_belt` for the belt and `related_transport_belt` for the splitter [L §12.3].
7. **Tint walker** [C §10.3], [M §9.4]. Walk only the graphics keys listed for the type. Set `tint` on leaves that have `filename`, `filenames` or `stripes`. Skip `draw_as_shadow`, `draw_as_glow`, `draw_as_light` and `apply_runtime_tint` (turret masks). Skip working visualisations with `apply_tint` or `apply_recipe_tint`. Never enter `circuit_connector`, `water_reflection`, `frozen_patch`, `belt_reader`, `connector_frame_sprites` or `icons`.
8. Keep `corpse` and `dying_explosion` (vanilla names are valid IDs [C §2.13]). Keep `heating_energy` and `surface_conditions` exactly as inherited (§7.4).

Graphics keys walked per type:

| type | keys |
|---|---|
| furnace, assembling-machine | `graphics_set` (+ `fluid_boxes[i].pipe_picture`) |
| mining-drill | `graphics_set`, `wet_mining_graphics_set` |
| transport-belt, underground-belt, splitter | one shared deepcopy of express `belt_animation_set` with only `animation_set` tinted, then per entity `structure` (UG sheets) or `structure` + `structure_patch` (splitter) [L §12.4] |
| accumulator | `chargable_graphics.picture` |
| electric-pole | `pictures` |
| burner-generator | `animation`, `idle_animation` |
| wall | `pictures` |
| electric-energy-interface | `picture` is replaced by base global `accumulator_picture(tint)`, the same way base builds the EEI [P §4, §8] |
| ammo-turret, electric-turret | `folded_animation`, `preparing_animation`, `prepared_animation`, `attacking_animation`, `folding_animation`, `graphics_set` (`energy_glow_animation` is glow and stays untouched) |

`tint` is valid on every Sprite/Animation leaf and on IconData [C §7.1, §10.1]. How the engine blends it is **not documented** [C §14]. It is assumed to be multiplicative, so tints are chosen as light multipliers (every channel ≥ 0.42). The world look can only be judged in a graphical client (§8.8, risk R4).

### 4.2 Production and mining

For every electric crafting machine, working draw = `energy_usage × (1 + 1/30)`, because drain defaults to `energy_usage/30` [C §1]. The pilot agrees for AM2 [PL].

| # | name | type ← vanilla base | size | key stats | modules / effects | HP | categories | tint (r,g,b) |
|---|---|---|---|---|---|---|---|---|
| E1 | `magnetics-sintering-kiln` | furnace ← `stone-furnace` [C §2.1] | 2×2 | speed 1, 90 kW, burner chemical, effectivity 1, pollution 3/min; source 1, result 1 | 0; effect_receiver inherited (no modules or beacons) | 250 | `magnetics-sintering` | 0.75, 0.60, 0.64 |
| E2 | `magnetics-induction-furnace` | assembling-machine ← `assembling-machine-2` [C §2.5] | 3×3 | speed 1, 300 kW (+10 kW drain), pollution 3/min | 2; 5 effects | 350 | `magnetics-induction` | 1.00, 0.60, 0.42 |
| E3 | `magnetics-coil-winder` | assembling-machine ← `assembling-machine-3` [C §2.6] | 3×3 | speed 1.5, 350 kW (+11.67 kW), pollution 2/min, **`effect_receiver = {base_effect = {productivity = 0.25}}`** | 4; 5 effects | 400 | `magnetics-winding-or-assembling` | 1.00, 0.75, 0.50 |
| E4 | `magnetics-cryo-chamber` | assembling-machine ← `chemical-plant` [C §2.7] | 3×3 | speed 1, 500 kW (+16.67 kW), 2 fluid inputs / 2 fluid outputs inherited | 3; 5 effects | 350 | `magnetics-cryogenics` | 0.68, 0.90, 1.00 |
| E5 | `magnetics-flux-resonator` | assembling-machine ← `centrifuge` [C §2.8] | 3×3 | speed 1, 1.5 MW (+50 kW); body in `idle_animation` (walker covers it [C §10.3]) | 2; 5 effects | 400 | `magnetics-resonance` | 0.78, 0.60, 1.00 |
| E6 | `magnetics-magnetic-separator` | furnace ← `electric-furnace` [C §2.3] | 3×3 | speed 1, 800 kW (+26.67 kW), `source_inventory_size = 1`, **`result_inventory_size = 2`** (recycler precedent [C §1]) | 2; 5 effects | 400 | `magnetics-separation` | 0.55, 0.70, 1.00 |
| E7 | `magnetics-magnetic-drill` | mining-drill ← `electric-mining-drill` [M §2.1] | 3×3 | `mining_speed = 1.0`, 240 kW, pollution 15/min, `resource_searching_radius = 2.49` (5×5), `resource_categories = {"basic-solid"}`, drain 100%, input fluid box inherited (uranium works) | 4 | 400 | — | 0.62, 0.74, 1.00 |

Upgrade links and fast-replace groups:
- E2–E6 use their own name as `fast_replaceable_group`, so pasting a coil winder cannot silently replace an AM2. `next_upgrade = nil`.
- E1 uses its own name as the group, for the same reason with respect to the stone furnace.
- E7 keeps `fast_replaceable_group = "mining-drill"` and the same boxes. **Vanilla `electric-mining-drill.next_upgrade = "magnetics-magnetic-drill"`** (valid: same box, mask and group [M §9.4]).

Furnace auto-recipe safety: a furnace picks its recipe from its single input.
- E1 has 1 recipe (iron-ore).
- E6 has 2 recipes (stone, uranium-ore).
- A load-time assertion in the test mod (S11) requires unique first ingredients per furnace category set.
- The induction furnace deliberately does **not** get `smelting`: iron ore would then map to both iron-plate and ferrite.

### 4.3 Logistics

| # | name | type ← base | stats | HP | links | tint |
|---|---|---|---|---|---|---|
| E8 | `magnetics-maglev-belt` | transport-belt ← `express-transport-belt` [L §3.1] | `speed = 0.15625` (40/256) = **75 items/s** [L §2] | 180 | `related_underground_belt = magnetics-maglev-underground-belt`; group `transport-belt` | anim 0.85, 0.55, 1.00 |
| E9 | `magnetics-maglev-underground-belt` | underground-belt ← `express-underground-belt` [L §3.2] | speed 0.15625, **`max_distance = 13`** (vanilla 5/7/9/11 → +2) | 180 | group `transport-belt` | same |
| E10 | `magnetics-maglev-splitter` | splitter ← `express-splitter` [L §3.3] | speed 0.15625 | 200 | `related_transport_belt = magnetics-maglev-belt` | same |

Upgrade chain, set in **data-updates.lua**:
- Base: `express-transport-belt/underground/splitter.next_upgrade = magnetics-maglev-*`.
- SA: the same on `turbo-*` (SA itself links express → turbo [L §11]).
- All maglev entities keep `next_upgrade = nil`.

Speed is a multiple of 1/256, as required [L §2].

### 4.4 Power

| # | name | type ← base | size | stats | HP | links | tint |
|---|---|---|---|---|---|---|---|
| E11 | `magnetics-mhd-generator` | burner-generator ← `burner-generator` (base, hidden) [P §7.2] | 3×5 | `max_power_output = "3MW"`; burner `{fuel_categories = {"chemical"}, effectivity = 0.8, fuel_inventory_size = 1, emissions_per_minute = {pollution = 20}}`; output `secondary-output`; `hidden = nil`; **SA only: `surface_conditions = {{property="pressure", min=10}}`**, the same as the vanilla boiler under SA [P §6.1] | 600 | own group | 1.00, 0.68, 0.45 |
| E12 | `magnetics-flux-dynamo` | burner-generator ← `burner-generator` | 3×5 | `max_power_output = "10MW"`; burner `{fuel_categories = {"magnetics-flux"}, effectivity = 1, fuel_inventory_size = 1, emissions_per_minute = {pollution = 0}}` | 1000 | own group | 0.78, 0.58, 1.00 |
| E13 | `magnetics-smes` | accumulator ← `accumulator` [P §4] | 2×2 | `buffer_capacity = "10MJ"`, `tertiary`, in/out `"2.5MW"` | 300 | group `accumulator`; **vanilla `accumulator.next_upgrade = magnetics-smes`** | 0.62, 0.90, 1.00 |
| E14 | `magnetics-superconducting-substation` | electric-pole ← `substation` [P §3] | 2×2 | `maximum_wire_distance = 24`, `supply_area_distance = 12` (24×24; API max 64 [P §3.1]) | 300 | group `substation`; **vanilla `substation.next_upgrade = ours`** | 0.62, 0.90, 1.00 |

The burner-generator base is hidden and has no recipe or tech, but the prototype and its graphics exist in base [P §7.2] [RB], so the deepcopy works in both configs. Both copies clear `hidden`.

### 4.5 Defense

Walls: `wall` ← `stone-wall` [K §11.2]. They keep `fast_replaceable_group = "wall"`, the collision box, `visual_merge_group = 0` (they join stone walls visually) and `repair_speed_modifier = 2`. Resistances are written `decrease/percent`.

| # | name | HP | physical | impact | explosion | fire | acid | laser | electric | links | tint |
|---|---|---|---|---|---|---|---|---|---|---|---|
| (vanilla) | stone-wall | 350 | 3/20 | 45/60 | 10/30 | 0/100 | 0/80 | 0/70 | — | next → ferrite wall (set by us) | — |
| E15 | `magnetics-ferrite-wall` | 450 | 4/25 | 45/60 | 10/30 | 0/100 | 0/80 | 0/70 | — | next → magnet wall | 0.72, 0.62, 0.66 |
| E16 | `magnetics-magnet-wall` | 800 | 6/35 | 50/65 | 15/40 | 0/100 | 0/85 | 0/70 | 0/50 | next → SC wall | 0.62, 0.70, 1.00 |
| E17 | `magnetics-superconducting-wall` | 1400 | 10/45 | 60/70 | 20/50 | 0/100 | 0/90 | 0/100 | 0/100 | — | 0.70, 0.95, 1.00 |

**E18 `magnetics-mend-coil`**: `electric-energy-interface` ← `electric-energy-interface` (base, hidden) [P §8], 2×2.
- `hidden = nil`, `gui_mode = "none"` (the API default [API]), `allow_copy_paste = false`.
- `energy_source = {type = "electric", buffer_capacity = "2MJ", usage_priority = "secondary-input", input_flow_limit = "500kW", output_flow_limit = "0W"}`.
- `energy_production = "0W"`, `energy_usage = "0W"`.
- 300 HP; `picture = accumulator_picture({0.60, 1.00, 0.70, 1})`.
- Behaviour comes from the script (§6). The **output limit of 0 W** keeps the tertiary-style EEI from ever feeding the network (the base EEI is `tertiary` [RB]).

Turrets:

| # | name | type ← base | size | stats | HP | tint |
|---|---|---|---|---|---|---|
| E19 | `magnetics-coilgun` | ammo-turret ← `gun-turret` [K §5.1] | 2×2 | `attack_parameters`: projectile type (kept), `ammo_category = "magnetics-slug"`, `cooldown = 20` (3 shots/s), `range = 22` (gun 18); **`energy_source = {type="electric", buffer_capacity="200kJ", input_flow_limit="300kW", usage_priority="primary-input"}`, `energy_per_shot = "40kJ"`** (the railgun-turret pattern [K §3.4, §5.4]); `inventory_size = 1`, `automated_ammo_count = 10`, `rotation_speed = 0.015` (gun) | 600 | 0.70, 0.78, 1.00 |
| E20 | `magnetics-arc-emitter` | electric-turret ← `laser-turret` [K §5.2] | 2×2 | `energy_source = {type="electric", buffer_capacity="2MJ", input_flow_limit="3MW", drain="30kW", usage_priority="primary-input"}`; `attack_parameters = {type="beam", cooldown=60, range=20, range_mode="center-to-bounding-box", source_direction_count=64, source_offset=<laser's>, ammo_category="laser", ammo_type={energy_consumption="1MJ", action=direct→instant target_effects: [1] nested chain `magnetics-arc-chain` (first, as vanilla tesla does [K §9]); [2] damage 60 electric; [3] create-sticker `electric-mini-stun` (base: 40 ticks, movement ×0.2 [RB]); [4] nested beam `magnetics-arc-beam` (max_length 22, duration 20, visual only)}}` | 1000 | 0.60, 0.90, 1.00 |
| E21 | `magnetics-rail-cannon` | ammo-turret ← `gun-turret` | 2×2 | `ammo_category = "magnetics-rail"`, `cooldown = 120` (0.5 shots/s), `range = 36`, `min_range = 4`, `health_penalty = -1` (prefers big targets, as the railgun does), `rotation_speed = 0.006`; energy `buffer 4MJ / input 2MW / primary-input`, `energy_per_shot = "2MJ"`; `automated_ammo_count = 5` | 1500 | 0.78, 0.62, 1.00 |

Turret notes:
- Each turret uses its own name as `fast_replaceable_group`. They must not fast-replace vanilla turrets, because the ammo differs.
- Under SA, `heating_energy` 50 kW is inherited from gun-turret and laser-turret [RS].

Helper prototypes:
- `magnetics-arc-chain` (chain-active-trigger [K §9]): `max_jumps = 4`, `max_range_per_jump = 6`, `jump_delay_ticks = 3`, `fork_chance = 0` (deterministic, no forks), action direct → **instant** `{damage 40 electric; create-sticker electric-mini-stun}`. Instant delivery is chosen over beam delivery so that bounce damage is exactly 40 and independent of beam `damage_interval` timing, which is not documented [K §8].
- `magnetics-arc-beam`: deepcopy of base `electric-beam` [RB] with `action = nil`. It is visual only and tinted.

Ammo (hitscan `line`, the SA railgun-ammo structure [K §6.4, §10], built from base-only entities):

| ammo | `ammo_type` | damage per entity in the line | notes |
|---|---|---|---|
| A1 ferrite slug | `target_type="direction"`, `clamp_position=true`, action `{type="line", range=24, width=0.6, force="enemy", action_delivery={type="instant", source_effects={create-explosion "explosion-gunshot"}, target_effects={damage 15 physical, create-entity "explosion-hit"}}}` | 15 physical | `force="enemy"` (TriggerItem.force, values `all/enemy/ally/friend/not-friend/same/not-same` [API]) prevents damage to our own walls |
| A2 alloy slug | as A1, width 0.8 | 40 physical | |
| A3 rail slug | as A1, range 40, width 1.5, `range_effects = create-explosion magnetics-rail-tracer` | 600 physical | |
| A4 flux rail slug | range 44, width 2, `range_modifier = 1.1` (turret range 39.6) | 1200 physical + 300 electric | |

`explosion-gunshot` and `explosion-hit` are the entities vanilla bullets use [K §6.2]. Every hit, damage and friendly-fire outcome is deterministic: there is no travel time, no deviation and no RNG.

### 4.6 The one procedural world sprite

`magnetics-rail-tracer` is an `explosion` with `rotate = true`, `beam = true` and `animations = {{filename="__magnetics__/graphics/entity/rail-tracer.png", width=16, height=512, frame_count=8, line_length=8, draw_as_glow=true, blend_mode="additive"}}`, copying the shape of SA `railgun-beam` [K §10]. The PNG is a PIL-generated 8-frame vertical gradient: a cyan core with alpha fading 1.0 → 0 over the frames. Why it is allowed: it is a pure gradient with no painted detail, and it can be reviewed as an image. Why it is needed: base has no beam-explosion sprite, and SA's `railgun-beam` path is `__space-age__/…`, which is illegal in base-only games [L §12.2]. If the pilot client shows a problem, the tracer is removed from A3/A4 (`range_effects = nil`) and nothing else changes.

---

## 5. Technologies

All techs use `icon = "__magnetics__/graphics/technology/<name>.png", icon_size = 256` [T §1.3, §10.7]. Pack letters follow [T §2]: A automation, L logistic, M military, C chemical, P production, U utility, S space, Met metallurgic. Costs are placed against vanilla neighbours from [T §4].

| # | technology | prerequisites | count × time | packs | unlocks |
|---|---|---|---|---|---|
| T1 | `magnetics-ferrite-processing` | stone-wall | 30 × 10 s | A | R13 kiln, R1 ferrite, R27 ferrite wall |
| T2 | `magnetics-induction-alloying` | T1, steel-processing, logistic-science-pack | 100 × 15 s | A L | R14 induction furnace, R2 magnet alloy |
| T3 | `magnetics-electromagnetic-coils` | T2, automation-2 | 100 × 30 s | A L | R3 coil, R15 coil winder |
| T4 | `magnetics-coilgun` | T3, gun-turret, military-2 | 100 × 30 s | A L | R31 coilgun, R9 ferrite slug |
| T5 | `magnetics-magnetic-defense` | T4, military-science-pack, repair-pack | 150 × 30 s | A L M | R28 magnet wall, R10 alloy slug, R30 mend coil |
| T6 | `magnetics-mhd-power` | T3, chemical-science-pack | 200 × 30 s | A L C | R23 MHD generator |
| T7 | `magnetics-magnetic-mining` | T3, chemical-science-pack | 250 × 30 s | A L C | R19 magnetic drill |
| T8 | `magnetics-magnetic-separation` | T3, advanced-material-processing-2 | 150 × 30 s | A L C | R18 separator, R7 magnetite recovery |
| T9 | `magnetics-calutron` | T8, uranium-processing | 300 × 30 s | A L C | R8 calutron enrichment |
| T10 | `magnetics-arc-emitter` | T5, laser-turret | 200 × 30 s | A L M C | R32 arc emitter |
| T11 | `magnetics-superconductivity` | T3, chemical-science-pack | 250 × 30 s | A L C | R16 cryo chamber, R4 cryofluid, R5 superconductor |
| T12 | `magnetics-superconducting-power` | T11, electric-energy-distribution-2, electric-energy-accumulators | 250 × 45 s | A L C | R25 SMES, R26 SC substation |
| T13 | `magnetics-superconducting-defense` | T11, T5, military-3, concrete | 250 × 30 s | A L M C | R29 SC wall |
| T14 | `magnetics-maglev-logistics` | T11, logistics-3 (**SA: + turbo-transport-belt**) | base 400 × 30 s; **SA 500 × 60 s** | base A L C P; **SA A L C P S Met** (the same set as turbo [RS]) | R20–R22 maglev belt, UG, splitter |
| T15 | `magnetics-flux-resonance` | T11, uranium-processing, production-science-pack, utility-science-pack | 500 × 45 s | A L C P U | R17 resonator, R6 flux crystal, R24 flux dynamo |
| T16 | `magnetics-rail-cannon` | T13, T15 | 400 × 45 s | A L M C P U | R33 rail cannon, R11 rail slug, R12 flux rail slug |

Reachability check by hand: every ingredient of an unlocked recipe is unlocked by a prerequisite chain. Examples:
- Concrete for R29 comes via `concrete` in T13.
- Repair packs for R30 come via `repair-pack` in T5.
- U-238 comes via `uranium-processing` in T15.
- Processing units come via the C chain.
- The static test S5 repeats this check mechanically.

All prerequisite names exist in both configs [T §3, §4, §4.3]. None of them is `mining-productivity-4`, which SA deletes [T §3.1].

**Bonus effects appended to vanilla techs** (data-updates.lua, appended at the end, never by index; SA rewrites `physical-projectile-damage-6/7` by index `[1]`, `[2]` [K §14.3], and appending keeps those indices valid):
- `physical-projectile-damage-1..7`: for each tech, read the existing `ammo-damage bullet` modifier *m* and the `turret-attack gun-turret` modifier *t* **at data-updates time** (so SA's rewritten values are picked up automatically). Append `ammo-damage magnetics-slug m`, `ammo-damage magnetics-rail m`, `turret-attack magnetics-coilgun t`, `turret-attack magnetics-rail-cannon t`.
- `weapon-shooting-speed-1..6`: read `gun-speed bullet` *g*. Append `gun-speed magnetics-slug g` and `gun-speed magnetics-rail g/2`.
- The arc emitter uses category `laser` and needs nothing: `laser-weapons-damage-*` and `laser-shooting-speed-*` already apply in both configs [K §14.2–14.3].

Vanilla numbers for reference: PPD-1 is bullet +0.1 and gun-turret +0.1 [K §14.2]. This design changes no vanilla progression: no prerequisite or cost of a vanilla tech changes. Only effects are appended.

---

## 6. Control script: the mend coil (the only runtime feature)

**Purpose.** Bot-free, power-paid repair of buildings in a radius, the Factorio-native answer to Mindustry's mender. Vanilla repair needs construction robots and repair packs; the mend coil trades repair packs for electricity.

**Constants (all in `control.lua`, read by the tests from a remote interface):**
- `RADIUS = 12` tiles.
- `PERIOD = 120` ticks between scans of one coil.
- `STEP = 10`: `on_nth_tick(10)`, so 12 batches per period.
- `HEAL_FRACTION = 0.04` of the target's `max_health` per scan.
- `J_PER_HP = 2000` J.
- `MIN_ENERGY = 20000` J.
- `IDLE_SKIP = 3`: after a scan that healed nothing, the next 3 scans of that coil are skipped.

**Algorithm (deterministic):**
1. `storage.coils` is an **array** of `{entity=LuaEntity, idle=0}`. It is rebuilt in `on_init` and `on_configuration_changed` by scanning `game.surfaces` in index order with `find_entities_filtered{name="magnetics-mend-coil"}`.
2. Registration events, each with filter `{{filter="name", name="magnetics-mend-coil"}}`: `on_built_entity`, `on_robot_built_entity`, `script_raised_built`, `script_raised_revive`, `on_entity_cloned`, `on_space_platform_built_entity`. All exist in the 2.0.77 runtime API [API]; the last one is registered only if `defines.events.on_space_platform_built_entity ~= nil`. New coils are appended to the array. Removal is lazy: invalid entries are swap-removed during scans. No removal events are needed.
3. `on_nth_tick(10)`: `storage.cursor` walks the array. Each call processes `ceil(#coils / 12)` coils, so every coil is visited once per 120 ticks.
4. For each coil:
   - If `idle > 0`, decrement `idle` and move on.
   - If `coil.energy < MIN_ENERGY`, move on. `LuaEntity.energy` is read/write and measured in J [H §6.3].
   - Otherwise call `surface.find_entities_filtered{position = coil.position, radius = RADIUS, force = coil.force}`. All three fields exist in `EntitySearchFilters` [API].
   - For each result `e` with `e.health` and `e.health < e.max_health`: `heal = min(e.max_health × 0.04, e.max_health − e.health, coil.energy / 2000)`. Then `e.health = e.health + heal` (writes are clamped [H §3]) and `coil.energy = coil.energy − heal × 2000`. Stop when energy runs out.
   - If nothing was healed, set `idle = 3`.
5. The script uses no `math.random`, no `game.player`, no wall-clock time and no mutation in `on_load`. Its only state is `storage`. It is therefore multiplayer-deterministic by construction.

**Throughput.** One coil restores 4%/2 s = 2% of max HP per second on every damaged building in range, limited by energy:
- A 2 MJ buffer covers 1000 HP of burst healing.
- A 500 kW input covers 250 HP/s sustained.
- On a superconducting wall (1400 HP) that is 56 HP per scan = **28 HP/s**. A big biter hitting that wall does (30−10)×0.55 = 11 per 35 ticks = 18.9 HP/s (resistance hypothesis PILOT-3). One coil therefore holds one wall against one big biter, and extra biters out-damage it.

**UPS cost (budget and test).**
- Per scan: one C++ area query plus 2 Lua reads per returned entity. A dense base has about 200 own-force entities within r = 12 (452 tiles).
- Estimate: 100 coils × 200 entities × 2 reads / 120 ticks = 333 reads per tick, about 0.05–0.1 ms/tick at 0.1–0.3 µs per API read. That per-read cost is an estimate, not sourced.
- The idle skip cuts the idle cost by 4×.
- **Budget (test U1):** with 100 idle coils in a 10 000-entity base, benchmark mean ms/tick minus the same map without coils is ≤ 0.05 ms.
- **Fallback if U1 fails:** switch to an event-driven damaged-set using `on_entity_damaged`, whose filters exist (`LuaEntityDamagedEventFilter` [API]). Scans then touch only entities that were damaged. This is documented, not implemented, unless U1 fails.

**Tests:** D1–D7 in §8.6.

**Not shipped:** a developer-only console command `/magnetics-showroom` in the separate test mod. It builds a lab surface with one of every entity and calls `game.take_screenshot` (present in the 2.0.77 runtime API [API]), so that the author can capture every world model **in the graphical Steam client**. On the headless server only the placement part is tested.

---

## 7. Balance justification and compatibility handling

### 7.1 Materials (raw cost in "ore units": 1 ore, 1 stone or 1 plate-worth; vanilla recipes from [RB])

| item | raw cost | reasoning |
|---|---|---|
| Ferrite | 1 iron ore, 3.2 s at kiln speed 1 | Identical to iron-plate smelting (1 ore, 3.2 s [RB]). It is a parallel material, not a cheaper one. The kiln burns 90 kW like the stone furnace [C §1], so sintering costs what smelting costs. |
| Magnet alloy | (5 + 3 + 1)/2 = **4.5 ore** each; steel 16 s per 5 plates [RB] | Steel-tier material (steel is 5 ore). The copper input ties both main ores in. |
| Coil | (4.5 + 3)/2 = **3.75 ore** each | "Copper wire on an alloy core". A green circuit costs 2.5 ore (1 iron + 3 cable = 1.5 copper [RB]), so a coil costs 1.5 green circuits. Coils go into almost everything, so they must stay cheap. |
| Cryofluid | 1 water + 0.2 petroleum per unit | Cheap coolant. Petroleum gas is available by T11 (C tier). |
| Superconducting cable | 9 ore + plastic (≈10 gas + 0.5 coal) + 25 cryofluid (≈5 gas) | About the advanced-circuit tier (AC: 2 EC + 2 plastic + 4 cable [RB]). The C-tier gate matches. |
| Flux crystal (1 GJ fuel) | 2 SC + 3 U-238 + 1 processing unit. Rough estimate from [RB] recipes, excluding water and sulfur: ≈ 80 ore-units + 70 petroleum gas + 30 uranium ore. (PU ≈ 20 EC (50) + 2 AC (14 ore + 40 gas); 2 SC ≈ 18 ore + 30 gas; 3 U-238 ≈ 30 uranium ore at p = 0.993 per 10 ore.) | Coal gives 1 GJ from 250 coal (4 MJ [P §9.2]). Solid fuel gives 1 GJ from 83 × 10 light oil. Nuclear gives 80 GJ of heat per U-235 [RB]. Flux therefore sits between chemical fuel and nuclear in resource cost, and its niche is compactness (§7.2). Production: a resonator makes 1 per 30 s, so 3.33 dynamos are fed per resonator, i.e. 33 MW per resonator. |

### 7.2 Buildings

| entity | vanilla comparison (source) | why this number |
|---|---|---|
| Kiln: speed 1, 90 kW, pollution 3 | stone furnace: speed 1, 90 kW, pollution 2 [C §1] | Same throughput and fuel. Sintering is dirtier (+1/min). |
| Induction furnace: speed 1, 300 kW, 2 modules | AM2 150 kW; electric furnace 180 kW [C §1] | Alloying is energy-heavy (induction heating). 2 slots = the AM2 body. |
| Coil winder: 1.5 speed, +25% productivity, 350 kW, 4 modules | AM3 1.25 / 375 kW / 4; EM plant 2 / +50% / 2 MW / 5 [C §1] | A specialist beats a general assembler on its one product, with half of the EM plant's bonus so that SA's EM plant stays better. Coils/s = 1.5/3 × 2 × 1.25 = **1.25/s** vs AM3 0.833/s. |
| Cryo chamber: 1 speed, 500 kW, 3 modules | chemical plant 1 / 210 kW / 3 [C §1] | Refrigeration costs power (2.4× the plant). |
| Flux resonator: 1 speed, 1.5 MW | centrifuge 1 / 350 kW / 2 [C §1] | The late-game power sink. 30 s crafts × 1.5 MW = 45 MJ per 1 GJ crystal = 4.5% overhead. |
| Separator: 800 kW; calutron 20 s, p(U-235) = 0.01 | centrifuge uranium-processing: 12 s, 0.007, 350 kW [RB] | Ore per U-235: 100 vs 143 (−30%). Energy per U-235: 800 kW × 20 s / 0.1 = **160 MJ** vs 350 × 12 / 0.07 = **60 MJ** (2.7×). Throughput per machine: 0.005 vs 0.00583 U-235/s. The niche is ore-limited uranium patches. Kovarex (1 U-235 net per 60 s) still dominates later. |
| Magnetite recovery: 10 stone → 3 iron ore, 5 s | stone and iron ore both have mining_time 1 [M §7.3] | A 30% conversion gives surplus stone a use and cannot beat mining iron. |
| Magnetic drill: 1.0 speed, 240 kW, 4 modules, 5×5 | electric drill 0.5 / 90 kW / 3 / 5×5 [M §1]; big drill 2.5 / 300 kW / 13×13 / 50% drain [M §5] | 2× ore per tile with a drop-in upgrade. Energy per ore is 240 vs 180 kJ (+33%), paid for density. Pollution per ore is 25% lower (15/min at 1 ore/s vs 10/min at 0.5 ore/s). It stays below the SA big drill on every axis. |
| Maglev belt: 75/s, UG 13 | 15/30/45/60, UG 5/7/9/11 [L §2, §3.2] | The next 8/256 step after turbo [L §2]. In base it jumps from 45 (no 60 tier), but it is gated at A+L+C+P plus superconductor (0.5 SC per belt) and is the logistics capstone. |
| MHD: 3 MW / 15 tiles, 80% efficiency, 20 poll/min, no water | boiler + 2 engines = 1.8 MW, 100% (boiler effectivity 1, engine 1 [P §6]), 3×2 + 2×(3×5) = 36 tiles, boiler pollution 30/min [P §2.6]; base burner-generator 1 MW at 50% [P §7.2] | Density 200 vs 50 kW/tile, waterless, and 6.7 vs 16.7 pollution per MW. It pays 25% more fuel (coal 3.75 MW fuel in → 3 MW out = 0.9375 coal/s). |
| Flux dynamo: 10 MW / 15 tiles, 0 pollution | reactor slice for 10 MW ≈ ¼ reactor + 1 exchanger (10 MW) + 1.72 turbines (5.82 MW) [P §6.2, §13], ≈ 38 tiles + water | Compact, clean, no heat or water logistics, no meltdown. Its fuel is costlier per GJ than nuclear (§7.1). |
| SMES: 10 MJ, 2.5 MW, 2×2 | accumulator 5 MJ, 300 kW, 2×2 [P §4] | Storage per tile 2×, flow 8.3×. It buffers bursty loads (arc emitter 3 MW input, rail cannon 2 MJ/shot, laser turrets). Cost is 4 SC + 6 coils + 1 accumulator. |
| SC substation: wire 24, supply 12 | substation 18 / 9 [P §3] | Area ×1.78 at a cost of SC + coils. Quality bonuses stack as for vanilla (§8.7). |
| Walls: 450 / 800 / 1400 HP | stone 350 [K §11.2] | Big-biter hits to kill (30 physical, hypothesis PILOT-3): stone 350/21.6 = 16; ferrite 450/19.5 = 23; magnet 800/15.6 = 51; SC 1400/11 = 127. Each tier costs the previous wall plus 2 alloy (≈9 ore) or 1 SC + 4 concrete. |
| Coilgun: 3 shots/s, 15 or 40 dmg per line hit, 40 kJ/shot (120 kW firing), range 22 | gun turret: 10 shots/s, firearm 5 / piercing 8 / uranium 24 [K §5, §6.2] | Single-target DPS, no bonuses, with PILOT-3 resistances (decrease then percent): vs medium biter (4/10) ferrite 29.7 vs piercing 36; alloy 97.2. vs big (8/10): piercing 0, alloy 86.4, uranium 144. vs behemoth (12/10): alloy 75.6, uranium 108. Alloy slugs are the military-science answer to armour before uranium ammo. Every slug also hits **all enemies in its line**. |
| Arc emitter: 60 + 4×40 electric, 1/s, 1 MJ/shot, range 20 | laser: 1.5 shots/s, 800 kJ/shot, range 24, laser dmg 10 per 20-tick interval × damage_modifier 2 [K §5.2]; tesla 120/bounce [K §8] | Single target 60/s is about laser-level (the laser's real DPS is measured in the same test run; T-L1). Crowds take 220/s. Stun slows. It uses 1 MW firing vs the laser's 1.2 MW. No biter resists electric [K §12]. |
| Rail cannon: 600 per line hit, 0.5/s, 2 MJ/shot, range 36 | railgun 10 000 per hit, range 40, 10 MJ/shot, Aquilo [K §5.4, §6.4] | Behemoths (3000 HP, 12/10): 529.2 per hit, so 6 shots each, and every behemoth in the line takes it. It fills the base-game gap between uranium rounds and artillery. |
| Mend coil | construction bots + repair pack (speed 2, durability 300 [RB]) | See §6. Slower than bots, but needs no packs. |

### 7.3 Vanilla edits (complete list; everything else is verified untouched by S7)

1. `next_upgrade` on 7 vanilla entities: `electric-mining-drill`, `stone-wall`, `accumulator`, `substation`, and in base `express-transport-belt` / `express-underground-belt` / `express-splitter`, under SA the `turbo-*` equivalents. The API allows this only with the same box, mask and group, which the deepcopies keep [L §11], [M §9.4].
2. Category injection (data-updates): `assembling-machine-2` and `assembling-machine-3` get `magnetics-winding-or-assembling`, and so does `electromagnetic-plant` if it exists. This must run in **data-updates**, because SA **overwrites** AM2/AM3 `crafting_categories` with `=` inside its data.lua [C §3, §10.5].
3. Appended bonus effects on 13 techs (PPD-1..7, WSS-1..6) (§5).

No vanilla recipe, cost, prerequisite, stat or graphic changes.

### 7.4 Space Age / quality / elevated-rails handling (explicit list)

| Concern | Handling | Test |
|---|---|---|
| Load order | `info.json` dependencies: `["base >= 2.0.0", "? quality >= 2.0.0", "? elevated-rails >= 2.0.0", "? space-age >= 2.0.0"]`. The `?` prefix is accepted by the binary's dependency regex [T §9.2]. The expected effect is that Magnetics loads after SA, so deepcopies in data.lua inherit SA's `heating_energy`, `frozen_patch` and `underground_collision_mask`. That effect is **not documented** → PILOT-1. Fallback: under `mods["space-age"]`, set `heating_energy` explicitly from [RS] values (AM2/AM3/chem/centrifuge/electric furnace/electric drill 100 kW, express belt 10 kW, UG 150 kW, splitter 40 kW, gun and laser turret 50 kW). Frozen graphics would then be missing, which is cosmetic only. | S8a: `heating_energy` of every copy equals its source's in the SA config and is nil in base |
| Recipes vs quality recycling | Recipes and items are defined in **data.lua**, so quality's data-updates sees them [C §10.5]. `auto_recycle = false` on R1, R2, R4, R7, R8. Everything else is recycled automatically. Placeable item name = entity name, so recycling names resolve [T §5.4]. | S8b: `magnetics-coil-recycling` exists; `magnetics-ferrite` has only self-recycling |
| Category overwrite by SA | Injection in data-updates (item 2 of §7.3) | S8c + runtime C5 |
| `heating_energy` | Never written by the mod except in the PILOT-1 fallback, and then only under `mods["space-age"]` | S8a |
| `surface_conditions` ("Requires Space Age to use" [C §4]) | Only the MHD pressure ≥ 10 condition, guarded by `if mods["space-age"]`. The kiln inherits SA's pressure ≥ 10 from stone-furnace [RS]. | S8d: absent in the base config |
| `hard-solid` (exists only with SA [M §7.1]) | Never referenced. The drill sets `resource_categories = {"basic-solid"}` explicitly, which preserves the big drill's niche. | S8e: grep over the mod and prototypes: no "hard-solid" |
| SA-only names (`turbo-*`, `metallurgic-science-pack`, `space-science-pack` in tech, `electromagnetic-plant`) | Referenced only inside `if mods["space-age"]` | S1 load in 4 configs with 0 errors |
| New damage types (asteroids get 100% resistance to types present when `asteroid.lua` runs [K §0.7]) | None added: only physical and electric | S8f |
| Ammo categories and bonus GUI | Own `bonus_gui_order` [K §2.1]. Bonuses are read from vanilla techs at data-updates time. | B1 |
| Elevated rails | No interaction. Poles and walls keep their vanilla collision masks. | S1 |
| Quality multipliers | Inherited engine behaviour. No `quality_affects_*` flags are set. | Q1–Q3 |
| Factoriopedia simulations | Cleared on every copy (§4.1) | S1 load |

---

## 8. Test plan

The pipeline has two mods, both already started under `games/Factorio_Magnetics/tools/`:
- `magnetics` is the shipped mod.
- `magnetics-tests` is the harness. Its data-final-fixes dumps prototypes (as `tools/run.py` expects with `MAGNETICS_RAW_BEGIN/END`). Its control.lua builds the lab in `on_init` and measures under `--benchmark` [H §1, §15].

Configurations:
- **base**: base only.
- **sa**: base + elevated-rails + quality + space-age.
- Load-only checks also run in **q** (base + quality) and **er** (base + elevated-rails).

A single `spec.py` (like the Mindustry mod) generates the Lua, the locale, the icons **and** the expected values below. No number is typed twice.

Window defaults: warmup 600 ticks, window 3600 ticks (60 s), sample every 60 ticks.

Resistance hypothesis H_res: `applied = (D − decrease) × (1 − percent/100)`. It is confirmed by PILOT-3 on the vanilla stone wall before any wall or turret expectation is registered.

### 8.1 Static tests (from the prototype dump; one assertion per number)

| ID | Measures | Expected |
|---|---|---|
| S1 | Load `--create` in base, q, er, sa | 0 lines matching `Error`/`non-recoverable`/`stack traceback`; 0 `Warning` lines attributable to magnetics (run.py filters) |
| S2 | Name hygiene | every prototype present only with the mod starts with `magnetics-`. Auto-generated exceptions: `<magnetics-*>-recycling` (quality). No name in `names_sa.tsv` or `names_base.tsv` is reused. |
| S3 | Property typos | `tools/check_props.py` on the dump: 0 unknown keys (vanilla-tolerated list excluded) |
| S4 | Every number in §2–§5 | e.g. `get_crafting_speed()` = 1 / 1 / 1.5 / 1 / 1 / 1 for E1–E6; `energy_usage` ×60 = 90 000, 300 000, 350 000, 500 000, 1 500 000, 800 000 W (units by PILOT-5); `belt_speed` = 0.15625; `max_underground_distance` = 13; `mining_speed` = 1.0; `get_mining_drill_radius()` = 2.49; `get_max_power_output()` ×60 = 3e6 / 1e7; `electric_energy_source_prototype.buffer_capacity` = 1e7 (SMES), 2e6 (mend coil); `get_max_wire_distance()` = 24, `get_supply_area_distance()` = 12; `get_max_health()` per table; resistances per table; `attack_parameters.range/cooldown` = 22/20, 20/60, 36/120; every recipe's ingredients, products, energy, category, allow_productivity; every tech's prerequisites, count, time, ingredients, effects. About 450 assertions. |
| S5 | Tech graph | all prerequisites exist; acyclic; each magnetics recipe is unlocked by exactly one magnetics tech; every ingredient of an unlocked recipe is unlocked in that tech's transitive prerequisites (or enabled at start); vanilla techs have no new prerequisites |
| S6 | Upgrade links | vanilla `next_upgrade` values as in §7.3 per config; source and target share `collision_box`, `collision_mask`, `fast_replaceable_group`; maglev, SMES, SC substation, SC wall and drill have `next_upgrade == nil` |
| S7 | Vanilla untouched | JSON of every vanilla prototype with the mod equals JSON without the mod, except the whitelist in §7.3 (field-level diff). This is the proof of "no vanilla breakage". |
| S8a–f | SA handling (§7.4) | as listed |
| S9 | Icons | every magnetics item, entity, fluid, recipe (R7, R8) and ammo-category has an icon file that exists in the mod folder; PNG decodes; 64×64 (items), 256×256 (techs); thumbnail 144×144 |
| S10 | Locale | every magnetics prototype has `[…-name]` in en, ru, de and a description in en and ru; no unused keys |
| S11 | Furnace input uniqueness | for kiln and separator: the first-ingredient names over all recipes in their categories are unique |
| S12 | Tint isolation | vanilla source entities have no `tint` on any sprite leaf after the mod loads (catches the shared `express_belt_animation_set` trap [L §12.3]); each copy has ≥ 1 tinted leaf and 0 tinted `draw_as_shadow` leaves |

### 8.2 Crafting (both configs; one cell per machine with an EEI + substation island [H §6])

Expected values use crafts/s = speed/energy [H §7]. Power is the EEI buffer delta over the window [H §6.3].

| ID | Cell | Expected in 60 s (tolerance) | Power |
|---|---|---|---|
| C1a | kiln, iron-ore feed, coal fuel | 18.75 ferrite (±1) | coal used 1.35 (±0.3) = 90 kW / 4 MJ ×60 |
| C1b | induction furnace, R2 | 10 crafts, 20 alloy (±2) | 310 kW (±2%) |
| C1c | coil winder, R3 | 30 crafts → **75 coils** (60 × 1.25; ±2.5, the productivity bar granularity) | 361.7 kW |
| C1d | cryo chamber, R4 | 30 crafts, 3000 cryofluid (±100; fluid statistics `get_input_count` [H §12]) | 516.7 kW |
| C1e | cryo chamber, R5, 120 s window | 15 superconductor (±1) | 516.7 kW |
| C1f | resonator, R6, 300 s window | 10 flux crystals (±1) | 1550 kW |
| C1g | separator, stone feed (auto-recipe) | 12 crafts, 36 iron ore (±3) | 826.7 kW |
| C2 | AM2 and AM3 running R3 (category injection) | AM2 15 crafts / 30 coils; AM3 25 crafts / 50 coils (±2); SA: EM plant `set_recipe("magnetics-coil")` succeeds | — |
| C3 | calutron: 40 separators, uranium-ore feed, 30 min | crafts = 40 × 90 = 3600 (±40); U-235 in [16, 56] (binomial p = 0.01, 99.9% band; Monte Carlo estimate, not exact); U-235 + U-238 per craft 1.00 ± 0.008 | — |
| C4 | products_finished semantics | calibrated against the output inventory for single-product (as [PL]) and multi-product (C3) recipes; reported, not asserted until PILOT-4 |

### 8.3 Logistics and mining

| ID | Cell | Expected |
|---|---|---|
| L1 | 40 maglev belts, insert_at_back / clear method [H §8] (validated at 45/s on express [PL]) | **75.0 items/s** (±1.875, one speed quantum [L §2]); control cell express = 45.0 |
| L2 | maglev UG pair at distance 13 in a belt line | 75 items/s; at distance 14 the output does not pair (`belt_to_ground_type` / neighbour check) and throughput is 0 |
| L3 | maglev splitter, input 75/s | each output 37.5 ± 1.9 items/s |
| L4 | SA only: `turbo-transport-belt.next_upgrade == "magnetics-maglev-belt"`; base: express does | — |
| M1 | magnetic drill on 1 000 000-amount iron ore; EMD control cell | **1.0 ore/s** ×60 = 60 (±1); EMD 30 (±1) [PL]; `mining_area` = 5×5 (right_bottom − left_top ≈ 4.98) |
| M2 | drill power (EEI delta) | 240 kW (±2%); if the engine adds a drain, the measured value is recorded and S4 is updated to it (PILOT-5) |

### 8.4 Power

EEI loads are set with `power_usage`, with units per PILOT-5 [H §6.3].

| ID | Cell | Expected |
|---|---|---|
| P1 | MHD, coal, load 5 MW | delivered 3.0 MW (`energy_generated_last_tick` × 60 = 3e6 ± 1%); coal burned in 60 s = 56.25 (±1.5) |
| P2 | MHD, solid fuel | 18.75 solid fuel per 60 s (±1) |
| P3 | flux dynamo, 5 crystals, load 20 MW, 300 s | 10.0 MW delivered; 3 crystals consumed (±1, burner buffer) |
| P4 | SMES charge from EEI source | 0 → 10 MJ in 240 ticks (±2) at 2.5 MW |
| P5 | SMES discharge into a 5 MW load | 2.5 MW for 240 ticks (±2), then 0 |
| P6 | SC substation reach | two poles 24.0 apart (`auto_connect`) are connected (same `electric_network_id`); 25.0 apart are not |
| P7 | SC substation supply | a 1×1 consumer centred 11.5 tiles away is powered (`is_connected_to_electric_network()`); at 12.5 it is not |
| P8 | MHD surface condition, SA only | `can_place_entity` false on a surface with `set_property("pressure", 0)`, true at 1000 |

### 8.5 Walls and combat

Biters are frozen with the stop command, `distraction = none` and the AI settings off [H §10.1]; turrets have `destructible = false`.

| ID | Cell | Expected |
|---|---|---|
| W1 | `damage(100, "enemy", type)` on each wall × 8 damage types [H §10.3] | H_res values, e.g. ferrite physical 72.0, magnet physical 61.1, SC physical 49.5; SC laser 0 and electric 0; magnet electric 50; stone-wall control physical 77.6 (PILOT-3 anchor) |
| W2 | wall max_health | 450 / 800 / 1400 |
| T1 | coilgun + ferrite slugs vs 1 frozen medium biter at 15 tiles | shots/s = 3.0 (±0.1, ammo consumption); applied damage per hit 9.9 via `on_entity_damaged.final_damage_amount` [K §13.4] |
| T2 | coilgun ferrite vs 5 frozen small biters in a line at 6/9/12/15/18 tiles | all 5 die from the **first** shot (15 ≥ 15 HP) |
| T3 | coilgun with 3 stone walls between turret and biters | wall health unchanged after 30 s (`force="enemy"`) |
| T4 | coilgun energy | EEI delta / shots = 40 kJ (±2%); with the substation removed, status `no_power` and 0 shots |
| T5 | coilgun + alloy slugs vs frozen big biter | per hit 28.8; DPS 86.4 (±3%) |
| T6 | arc emitter vs 5 frozen big biters 3 tiles apart, 1 shot | total `final_damage_amount` = 60 + 4 × 40 = 220 (big biters have no electric resist [K §12]); exactly 5 distinct entities damaged |
| T7 | arc emitter friendly check | a stone wall 2 tiles from the cluster has unchanged health |
| T8 | arc emitter energy | 1 MJ per shot (±2%) |
| T9 | rail cannon + rail slugs vs 5 frozen behemoths in a line (10–34 tiles) plus 1 behemoth 3 tiles off-line | each in-line target takes 529.2 per shot; the off-line target takes 0; 2 MJ/shot |
| T10 | rail cannon + flux rail slugs | per hit 1069.2 physical + 300 electric; range 39.6 (`turret_range` × `range_modifier`) |
| T11 | bonus inheritance | after `research_recursive` of `physical-projectile-damage-3` and `weapon-shooting-speed-3`: `get_ammo_damage_modifier("magnetics-slug") == get_ammo_damage_modifier("bullet")` (= 0.4); `get_turret_attack_modifier("magnetics-coilgun") == get_turret_attack_modifier("gun-turret")`; `gun_speed(magnetics-rail) = ½ gun_speed(bullet)`; arc emitter damage scales with `laser-weapons-damage-1` (+0.2) |
| T-L1 | laser turret control (same run) | measured single-target DPS is recorded; the arc emitter's single-target DPS must lie within [0.5×, 1.5×] of it (the niche claim in §7.2) |
| T-W | wave scenario: 20 medium + 10 big biters with `attack_area` on a 3×3 turret block behind a wall line, evolution fixed; four variants (gun turrets + piercing; coilguns + alloy; lasers; arc emitters), each with SC walls vs stone walls | reported: time to clear, wall HP lost, turret losses. Pass: all attackers dead within 120 s in every Magnetics variant; SC-wall variants lose ≤ ½ the wall HP of stone-wall variants. |

### 8.6 Mend coil (script)

| ID | Setup | Expected |
|---|---|---|
| D1 | SC wall at 700/1400, 6 tiles from a powered coil, 1200 ticks | health = min(1400, 700 + k × 56) with k = 10 or 11 (cycle phase) |
| D2 | same, coil not connected to a pole | health unchanged (700) |
| D3 | wall 13 tiles away | unchanged |
| D4 | energy accounting | coil energy drop = healed HP × 2000 J (±1%), read from `coil.energy` before and after each scan (harness samples every tick in this cell) |
| D5 | registration | a coil created with `raise_built = true` is healing within 120 ticks; after destroying a coil, no script error and `#storage.coils` shrinks at the next pass |
| D6 | determinism | two `--benchmark` runs of the same save give identical wall-HP sums (exact equality) |
| D7 | rebuild on `on_configuration_changed` | coils created with `raise_built = false` (no event reaches the script); `storage.coils` is cleared; a mod-version bump triggers `on_configuration_changed`; afterwards the rebuilt list contains every coil and D1 passes on them |

### 8.7 Quality (sa config)

| ID | Expected |
|---|---|
| Q1 | legendary SMES `buffer_capacity` = 10 MJ × (1 + 5) = 60 MJ (`accumulator_capacity_multiplier` default 1 + level, legendary level 5 [P §4, §3.1]) |
| Q2 | legendary SC substation supply 12 + 5 = 17, wire 24 + 2 × 5 = 34 (`electric_pole_supply_area_distance_bonus` = level, `wire_reach_bonus` = 2 × level [P §3.1]) |
| Q3 | legendary coil winder speed / normal = legendary AM3 speed / normal (same engine multiplier; compared as a ratio, so no quality number is invented) |

### 8.8 UPS and graphics

| ID | Expected |
|---|---|
| U1 | benchmark mean ms/tick: 10 000-entity map + 100 idle coils minus the same map without coils ≤ 0.05 ms; with 100 coils actively healing ≤ 0.2 ms |
| U2 | the harness itself is excluded from timing (a separate save without harness cells) |
| G1 | icon contact sheet `showcase_icons.png` (all 52 icons + 16 techs) produced by `tools/paint.py`; reviewed by eye and by S9 |
| G2 | tint cards: for each entity, vanilla base name + tint swatch + icon, in the same sheet. World models can be seen only in the graphical client via `/magnetics-showroom` (§6); headless tests only check that it places all 21 entities without errors. |

---

## 9. Pilots that must pass before the tests above are registered

| # | Unknown (source says "not found" / "pilot") | Pilot | Decides |
|---|---|---|---|
| PILOT-1 | Optional dependency makes the mod load after SA [T §9.2, §11] | log `data.raw["transport-belt"]["express-transport-belt"].next_upgrade` in magnetics' data.lua with SA on | deepcopy in data.lua vs the §7.4 fallback |
| PILOT-2 | `heating_energy` accepted with freezing off [C §14] | never written in base; confirm 0 warnings | — |
| PILOT-3 | Resistance formula [K §1.2, §16] | stone-wall `damage(100, physical)` = 77.6? | all W and T expectations |
| PILOT-4 | `products_finished` for multi-product / furnace-with-2-results [H §7] | separator calutron cell | C3/C4 metric |
| PILOT-5 | Units of `energy_usage` and EEI `power_usage` [H §6.3, §13] | EEI and AM1 calibration (75 kW) | S4 and P tests |
| PILOT-6 | `effect_receiver.base_effect` productivity works in base-only | coil winder cell, base config | C1c |
| PILOT-7 | ammo-turret + `energy_source` + `energy_per_shot` works in base (only the SA railgun uses it) | coilgun cell | E19/E21 design; fallback: an electric-turret with a built-in `ammo_type` (tesla shape) and no slugs |
| PILOT-8 | Line trigger from a turret: `force="enemy"`, width semantics | T3, T9 geometry | A1–A4 widths |
| PILOT-9 | chain-active-trigger: jump count, target selection, friendlies, laser bonus on chained damage | T6, T7, T11 | E20 numbers |
| PILOT-10 | EEI with `secondary-input`, `energy_usage = 0` charges its buffer | mend coil energy after 300 ticks = 2 MJ (500 kW × 4 s) | E18. Fallback if the buffer stays empty: `energy_usage = "1W"`; if it still does not charge, the script sets `power_usage` at runtime (a documented EEI field [H §6.3]) |
| PILOT-11 | Frozen biters stay put while being shot and do not regenerate distorting damage [H §10.1] | position drift and `on_entity_damaged` sums | all T tests use `final_damage_amount`, which is immune to healing |
| PILOT-12 | Tint visuals, tracer sprite | graphical client only (author, `/magnetics-showroom`) | tints in §4 |

Following the project rules, these pilots run on a separate seed/save that does not enter the test set. Their outputs and any number changed after them are written into the plan before the test run is registered.

---

## 10. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | **Load order.** If `? space-age` does not order Magnetics after SA, deepcopies miss SA fields and next_upgrade links could be overwritten (SA sets express → turbo in its data.lua). | PILOT-1. All vanilla edits are already in data-updates. Explicit SA field fallback. S8a catches it in every run. |
| R2 | **Undocumented combat semantics**: resistance order, line width, chain targeting, bonus scaling of chained damage, turret energy on an ammo-turret. | PILOT-3/7/8/9 before registering. Every combat number is also measured relative to a vanilla control turret in the same run, so a wrong absolute formula does not flip conclusions. |
| R3 | **Mend coil UPS and correctness.** Area scans every 2 s per coil; the EEI buffer behaviour is unverified. | Idle skip, batch spreading, U1 budget, documented event-driven fallback, D1–D7. |
| R4 | **Visuals are unverifiable headless.** Tint blending is undocumented; the 32-frame express texture at 0.15625 may look out of sync [L §4.4]. | All icons are drawn by code and reviewed as images (G1). World looks go through the author's graphical client via `/magnetics-showroom`. No mechanic depends on the look. |
| R5 | **Power creep in base.** 75/s belts without a 60/s tier, a 10 MW compact dynamo and 2× drills could flatten late base-game logistics and power. | Gates: A+L+C+P(+U) packs and superconductor/flux costs (§7). The T-W and P tests quantify the advantage, which then goes to the council as a measured result rather than an argument. |

---

## Appendix A. File layout of the shipped mod

`magnetics_1.0.0/`:
- `info.json` (§7.4 dependencies, `factorio_version = "2.0"`)
- `data.lua`: requires `prototypes/{categories,items,fluids,recipes,technology}.lua` and `prototypes/entity/{production,logistics,power,defense,combat}.lua`
- `data-updates.lua`: category injection, vanilla next_upgrade links, tech bonus appends, SA-conditional ingredients and prerequisites
- `control.lua`: mend coil only
- `locale/{en,ru,de}/magnetics.cfg`
- `graphics/icons/*.png` (64 px, drawn by PIL), `graphics/technology/*.png` (256 px), `graphics/entity/rail-tracer.png`
- `thumbnail.png`, `changelog.txt`

Test mod `magnetics-tests_1.0.0/`: `data-final-fixes.lua` (prototype dump), `control.lua` (lab, cells, results.json, showroom command).
