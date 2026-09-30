# Magnetics for Factorio 2.0.77: design document (angle: player appeal and memorable mechanics)

Status: design proposal. Every number below is a design target, and the test plan (§8) checks each one.
Vanilla numbers are cited from the recon files: `crafting.md`, `logistics.md`, `power.md`, `mining.md`, `combat.md`, `tech.md`, `harness.md`.
A few extra vanilla facts were read directly from the game files. They are cited as `GAME: path:line` and marked "(not in recon)".
Where the engine's behaviour is not in the sources, the text says so and names the pilot that settles it.

---

## 0. The pitch in one paragraph

Magnetics adds a **magnetic industry** alongside vanilla. It starts with **ferrite**, a sintered iron-stone ceramic, and continues through **magnet alloy**, wound **coils** and **superconducting cable** to **flux crystals**. Two new fluids carry the chain: **ferrofluid**, a black magnetic "lubricant" made from ferrite and light oil, and **liquid nitrogen**, liquefied from air in the cryo chamber.

The mod has eight signature moments:
1. **Electrified walls** shock the biters that bite them.
2. **Mend coils** repair walls from the power grid.
3. **Arc emitters** throw chain lightning through a swarm.
4. **Rail cannons** fire one violet line through a whole attack wave.
5. **Maglev belts** run at 75 items/s, the fastest belts in the game.
6. A 5×5 **flux resonator** grows rechargeable **flux crystals** that power a compact **flux dynamo** and act as **maglev train fuel** (+30 % top speed).
7. **Geomagnetic coils** harvest the planet's magnetic field. That makes Fulgora (field 99, solar 20 %) the best place for them.
8. **Superconducting pylons** span 64 tiles, twice a big pole.

Every world sprite is a tinted `table.deepcopy` of a vanilla entity. Every icon is new and drawn by Python/PIL. There is only one control-script feature, the mend coil, and it is event-driven.

---

## 1. Concept and progression

### 1.1 Mindustry → Factorio port map (what was kept, changed or dropped)

| Mindustry Magnetics (`games/Mindustry_Magnetics/tools/spec.py`) | Factorio Magnetics | Why |
|---|---|---|
| ferrite (sand + lead) | `magnetics-ferrite` (iron ore + stone, sintered) | Uses Factorio raw resources. Stone gets a mid-game use. |
| magnet alloy (titanium + silicon) | `magnetics-magnet-alloy` (ferrite + steel + copper) | Hangs on steel, the vanilla mid-game metal. |
| coil | `magnetics-coil` (alloy + copper cable) | Same role: the universal part. |
| superconductor (+ cryofluid) | `magnetics-superconducting-cable` (+ liquid nitrogen) | Renamed because SA already has the item `superconductor` (names_sa.tsv). |
| flux crystal (+ phase fabric) | `magnetics-flux-crystal` (SC cable + U-238 + ferrofluid + LN2) | Fuel, ammo, and the endgame power loop. |
| cryofluid | `magnetics-liquid-nitrogen` (new fluid) + `magnetics-ferrofluid` (new fluid) | Factorio loves fluid chains. Ferrofluid is the magnetic counterpart of lubricant. |
| kiln / induction furnace / coil winder / cryo chamber / flux resonator / magnetic separator | same six machines | Same roles. The recipes are Factorio-native: multi-input, fluids, productivity. |
| magnetic drill | `magnetics-magnetic-drill`, the upgrade target of the electric drill | Uses the upgrade planner (`next_upgrade`). |
| mag conveyor / junction / router / bridge | maglev belt / underground / splitter | Factorio has no junction or router. The underground belt plays the bridge's role. |
| coil battery / superconducting battery | `magnetics-coil-capacitor` (1×1 accumulator) / `magnetics-smes` (high-flow accumulator) | Two real niches: early storage without batteries, and burst power. |
| superconducting node (22 blocks) | `magnetics-superconducting-pylon` (wire 64) | The Factorio equivalent of reach is wire distance. |
| MHD generator | **dropped** | It overlaps boiler + steam engine (chemical fuel, 100 % effectivity, power.md §6). Its slot goes to the geomagnetic coil, which is a Factorio-native surface-property mechanic. |
| flux dynamo | `magnetics-flux-dynamo` (burner-generator, its own fuel category) | It gains a spent → recharge loop, like uranium fuel cells. |
| 6 walls (1×1 and 2×2) | 3 walls (1×1), upgrade chain stone → ferrite → magnet → superconducting | Factorio walls are 1×1 and merge visually. "Deflects bullets" becomes `attack_reaction` (electric shock). |
| mend coil (MendProjector) | `magnetics-mend-coil` (script) | Factorio has no native area repair (§6). |
| magnetic shield (ForceProjector) | **dropped** | No native area shield exists. Shock walls plus mend coils cover "defense that sustains itself". |
| coilgun + gauss | `magnetics-coilgun-turret` with two ammo tiers (ferrite slug = coilgun, magnet slug = gauss) | Factorio is native in using one turret with ammo tiers. |
| arc emitter | `magnetics-arc-emitter` (chain lightning via `chain-active-trigger`) | A core prototype type, so it works in base (combat.md §15.4). |
| maglev flak (anti-air) | **dropped** | Factorio has no air units. |
| railgun | `magnetics-rail-cannon` | Renamed because of SA `railgun`/`railgun-turret`. It fires a line (hitscan) attack. |
| magnet factory + Spark / Inductor / Magnetar (air units) | **dropped**. Replaced by flux-fuelled "maglev trains" (the locomotive accepts flux crystals: top speed ×1.3) | Mindustry's air-unit role (fast movers) maps onto Factorio's trains. |

### 1.2 Tiers and where they sit in a normal playthrough

| Tier | Science | Typical time in a first run | Vanilla techs it hangs on (tech.md §3) | Content |
|---|---|---|---|---|
| I. Ferrite age | red + green | right after steel and green science | steel-processing, logistic-science-pack, stone-wall, advanced-material-processing, automation-2, solar-energy | kiln, ferrite, induction furnace, magnet alloy, coil winder, coils, coil capacitor, geomagnetic coil, ferrite wall |
| I-M. Magnetic defense | red + green + military | when the first attacks grow | military-science-pack | coilgun + two slugs, magnet wall (shock), mend coil |
| II. Fluid age | + blue | oil, plastics, advanced circuits | advanced-oil-processing, plastics, advanced-circuit, laser, electric-energy-distribution-2, electric-energy-accumulators | ferrofluid, magnetic drill, magnetic separator, arc emitter, cryo chamber + LN2 + SC cable, SMES, pylon, SC wall |
| III. Resonance age | + purple (+ yellow, + military) | late game, next to nuclear and logistics-3 | logistics-3, uranium-processing, production-science-pack, utility-science-pack, military-4 | maglev belts, flux resonator, flux crystals, flux dynamo, maglev train fuel, rail cannon |
| SA. Fulgoran magnetism | + space + EM | after landing on Fulgora | electromagnetic-science-pack (SA) | magnetic scrap separation (2× holmium), Fulgoran flux crystals (double yield, field = 99) |

### 1.3 Coexistence with Space Age

Space Age content is used only behind `mods["space-age"]` guards. The mod never depends on it.

| SA content | Magnetics counterpart | How they coexist |
|---|---|---|
| turbo belt (60/s, metallurgy, A+L+C+P+S+Met; logistics.md §6-7) | maglev belt, 75/s | Base: the maglev recipe consumes express belts and needs utility science. **SA: it consumes turbo belts, the tech also needs `turbo-transport-belt` + EM science, and the upgrade chain is express → turbo → maglev.** The maglev tier never undercuts Vulcanus. |
| electromagnetic plant (speed 2, +50 % prod; crafting.md §1) | coil winder (speed 1, +50 % prod, coils only) | Under SA, `magnetics-winding` is added to the EM plant's categories, so the EM plant winds coils at 2× the winder's rate. The winder stays the base and pre-Fulgora machine. |
| cryogenic plant (speed 2, 8 modules) | cryo chamber (speed 1, 3 modules) | Under SA, `magnetics-cryogenics` is added to the cryogenic plant. Aquilo becomes a natural LN2 / SC cable site. |
| tesla turret (range 30, 12 MJ/shot, 120 dmg + 10-jump chain + stun; combat.md §5.5) | arc emitter (range 20, 1.2 MJ/shot, 30 + 6×20, mild slow) | The arc emitter is the pre-space, base-available chain weapon: weaker and cheaper. Tesla stays the upgrade. |
| railgun turret (4000 HP, range 40, 10000 dmg line, Aquilo-tier; combat.md §5.4, §6.4) | rail cannon (2000 HP, range 36, 1200 dmg line) | Rail cannon is roughly 1/8 of the SA railgun's damage and needs no SA. The railgun stays the endgame. |
| big mining drill (2.5 speed, 13×13, 50 % drain, 5×5; mining.md §1) | magnetic drill (1.0 speed, 7×7, 3×3) | It fits existing 3×3 electric-drill layouts through the upgrade planner. The big drill remains the Vulcanus prize. |
| recycler / scrap-recycling (0.2 s per scrap; holmium p = 0.01; GAME: space-age/prototypes/recipe.lua:2113-2128, not in recon) | magnetic scrap separation (SA-only recipe) | It gives 2× holmium per scrap but discards every non-magnetic output. A specialist option, not a replacement. |
| `magnetic-field` surface property (Nauvis 90, Fulgora 99, Vulcanus/Gleba 25, Aquilo 10, platform 0; power.md §11.6) | geomagnetic coil output, flux resonator recipe condition (≥ 90), Fulgoran flux recipe (= 99), placement condition magnetic-field ≥ 10 on dynamo, geomagnetic coil, mend coil and the three turrets | Magnetics is **planet-side hardware**: it does not work on space platforms (field 0). SA platform power and defense balance is therefore untouched. |
| quality | all entities inherit the default quality scaling; `auto_recycle` is set per recipe (§3) | Recycling is kept for buildings and coils. It is off for smelted/fluid/crystal chains, following the vanilla smelting/superconductor exclusions (crafting.md §11.3). |
| elevated rails | pylon copies the big pole's `collision_mask` including `elevated_rail` (power.md §3.1) | No other interaction. |

### 1.4 Content count

- **22 buildings** (each = entity + placeable item)
- **10 non-placeable items**: 5 intermediates, the spent crystal and 4 ammo types
- **2 fluids**

That is **34 content units** and **54 item+entity prototypes**. Hidden helpers come on top: 2 projectiles, 1 chain trigger, 2 beams, 1 explosion, 3 ammo categories, 1 fuel category, 6 recipe categories and 2 subgroups.
If the target of "30–45 prototypes" means item+entity prototypes, the agreed trim order is: coil capacitor → flux rail slug → ferrite wall → magnetic separator. Each cut is independent of the others.

---

## 2. Items and fluids

Icons: 64 px, drawn by PIL, in the Mindustry palette (`spec.py` colours: ferrite `5c4a52`, magnet alloy `6d86c9`, coil `d6854a`, superconductor `9fe8ff`, flux crystal `b58cff`).
Two new subgroups:
- `magnetics-intermediates` (group `intermediate-products`, order `ga`)
- `magnetics-processes` (same group, order `gb`) for multi-product and special recipes.

### 2.1 Non-placeable items

| # | name | type / special fields | stack | subgroup / order | use | icon motif |
|---|---|---|---|---|---|---|
| 1 | `magnetics-ferrite` | item | 100 | magnetics-intermediates / `a[ferrite]` | alloy, ferrofluid, walls, slugs, capacitor, geomagnetic coil | dark grey-mauve hexagonal ceramic tile with sinter speckles |
| 2 | `magnetics-magnet-alloy` | item | 100 | … / `b[magnet-alloy]` | coils, SC cable, slugs, most buildings | blue ingot with a red/white N-S split |
| 3 | `magnetics-coil` | item | 100 | … / `c[coil]` | nearly every building, maglev belts | copper winding on a blue core, seen from the side |
| 4 | `magnetics-superconducting-cable` | item | 200 | … / `d[superconducting-cable]` | flux crystal, SMES, pylon, SC wall, maglev UG/splitter, rail slug, dynamo, resonator | pale-cyan flat tape spool with a frost rim |
| 5 | `magnetics-flux-crystal` | item. `fuel_category = "magnetics-flux"`, `fuel_value = "2GJ"`, `burnt_result = "magnetics-spent-flux-crystal"`, `fuel_acceleration_multiplier = 1.8`, `fuel_top_speed_multiplier = 1.3` | 50 | … / `e[flux-crystal]` | flux dynamo fuel, locomotive fuel, flux rail slug | violet faceted crystal with field lines |
| 6 | `magnetics-spent-flux-crystal` | item | 50 | … / `f[spent-flux-crystal]` | recharge in the resonator | the same crystal, grey and cracked |
| 7 | `magnetics-ferrite-slug` | ammo, category `magnetics-coil-slug`, `magazine_size = 10` | 100 | `ammo` / `m[magnetics]-a[ferrite-slug]` | coilgun, tier 1 | five dark slugs in a clip |
| 8 | `magnetics-magnet-slug` | ammo, `magnetics-coil-slug`, `magazine_size = 10` | 100 | `ammo` / `m[magnetics]-b[magnet-slug]` | coilgun, tier 2 | blue slugs with red tips |
| 9 | `magnetics-rail-slug` | ammo, category `magnetics-rail`, `magazine_size = 1` | 20 | `ammo` / `m[magnetics]-c[rail-slug]` | rail cannon | long blue dart with cyan rails |
| 10 | `magnetics-flux-rail-slug` | ammo, `magnetics-rail`, `magazine_size = 3` | 10 | `ammo` / `m[magnetics]-d[flux-rail-slug]` | rail cannon, premium | dart with a violet crystal core |

New category prototypes:
- **Ammo categories** `magnetics-coil-slug`, `magnetics-arc` and `magnetics-rail`. Each has an icon and an explicit `bonus_gui_order`, because the vanilla ordering table has no entry for mod categories (combat.md §2.1).
- **Fuel category** `magnetics-flux` (power.md §9.3).

### 2.2 Fluids

| name | fields | barrels | use | icon motif |
|---|---|---|---|---|
| `magnetics-ferrofluid` | `default_temperature = 25`, `base_color = {0.07, 0.06, 0.09}`, `flow_color = {0.48, 0.36, 0.72}`, order `a[fluid]-b[oil]-f[magnetics-ferrofluid]` (after lubricant `…-e[lubricant]`, GAME: base/prototypes/fluid.lua:108-114, not in recon) | `auto_barrel` default (true); fill/empty barrel recipes are auto-generated under fluid-handling (tech.md §3, fluid-handling row) | maglev belts, magnetic separator, flux crystal, recharge | a black droplet with the ferrofluid "spike crown" and a violet sheen |
| `magnetics-liquid-nitrogen` | `default_temperature = -196` (negative temperatures are valid: SA `fluoroketone-cold` uses -150, GAME: space-age/prototypes/fluid.lua:48, not in recon), `base_color = {0.75, 0.90, 1.0}`, `flow_color = {0.90, 0.97, 1.0}` | `auto_barrel = false` (cryogenic liquid) | SC cable, flux crystal, recharge | a pale-blue droplet with frost wisps |

Why a fluid chain: ferrofluid is to the maglev tier what lubricant is to the express tier. Express belts take 20 lubricant each (logistics.md §6); maglev belts take 20 ferrofluid each. The ferrofluid recipe mirrors lubricant's shape (10 → 10 in 1 s, GAME: base/prototypes/recipe.lua:439-453, not in recon), with one ferrite added per craft.

---

## 3. Recipes

Categories (all new; recipe-category prototypes have no own properties, crafting.md §12):

| category | crafted by (base) | added under SA (in `data-updates.lua`) |
|---|---|---|
| `magnetics-sintering` | kiln, induction furnace | — |
| `magnetics-induction` | induction furnace | — |
| `magnetics-winding` | coil winder, assembling-machine-2/3, **character** (coils are hand-craftable) | electromagnetic-plant |
| `magnetics-cryogenics` | cryo chamber | cryogenic-plant |
| `magnetics-resonance` | flux resonator | — |
| `magnetics-separation` | magnetic separator | — |

All AM2/AM3/character/EM-plant/cryo-plant inserts happen in `data-updates.lua`, because SA overwrites those lists with `=` (crafting.md §3, §10.5).
All recipes use `enabled = false` and are unlocked by exactly one technology. Energies are in seconds at crafting speed 1.
"Prod" is `allow_productivity`. "Recycle" is `auto_recycle` (quality mod).

### 3.1 Intermediates and fluids

| recipe | category | ingredients | results | energy | prod | recycle | notes |
|---|---|---|---|---|---|---|---|
| `magnetics-ferrite` | sintering | 2 iron-ore, 1 stone | 2 ferrite | 3.2 | yes | false | Same time per ore as iron-plate smelting (3.2 s, crafting.md §11.2). |
| `magnetics-magnet-alloy` | induction | 2 ferrite, 1 steel-plate, 1 copper-plate | 1 magnet-alloy | 3.2 | yes | false | |
| `magnetics-coil` | winding | 1 magnet-alloy, 3 copper-cable | 1 coil | 1 | yes | true | |
| `magnetics-ferrofluid` | chemistry | 1 ferrite, 10 light-oil | 10 ferrofluid | 1 | yes | false | `crafting_machine_tint` primary `{0.07,0.06,0.09}`, secondary `{0.48,0.36,0.72}`, tertiary `{0.3,0.25,0.4}`, quaternary `{0.15,0.1,0.2}`. The chemical plant's windows then show black-violet liquid. |
| `magnetics-liquid-nitrogen` | cryogenics | — (empty list, allowed by the API: "May be `{}`", crafting.md §11.1) | 20 liquid-nitrogen | 2 | no | false | "Air liquefaction": costs only power. Icon: LN2 droplet over an air swirl. |
| `magnetics-superconducting-cable` | cryogenics | 1 magnet-alloy, 3 copper-plate, 1 plastic-bar, 20 liquid-nitrogen | 2 SC cable | 4 | yes | false | Recycling is off, like SA `superconductor` (crafting.md §11.3). |
| `magnetics-flux-crystal` | resonance | 2 SC cable, 1 uranium-238, 5 ferrite, 50 ferrofluid, 50 liquid-nitrogen | 1 flux-crystal | 30 | yes | false | SA: `surface_conditions = {{property="magnetic-field", min=90}}` (Nauvis 90, Fulgora 99). |
| `magnetics-flux-crystal-recharge` | resonance | 1 spent-flux-crystal, 20 ferrofluid, 20 liquid-nitrogen | 1 flux-crystal, `probability = 0.9` | 10 | **no** (no loop multiplication) | false | Same SA condition. Subgroup magnetics-processes. |
| `magnetics-magnetite-separation` | separation | 10 stone, 10 ferrofluid | 4 iron-ore; 1 copper-ore p = 0.5 | 5 | no | false | Multi-product: `icon`, `subgroup`, `order` are set (crafting.md §11.2). |
| `magnetics-scrap-separation` **(SA only)** | separation | 10 scrap, 5 ferrofluid | 2 iron-gear-wheel; 1 steel-plate p = 0.4; 1 holmium-ore p = 0.2 | 4 | no | false | Per scrap: gears 0.2 and steel 0.04, the same as scrap-recycling; **holmium 0.02 = 2× recycler (0.01)**; everything else is lost. |
| `magnetics-flux-crystal-holmium` **(SA only)** | resonance | 2 SC cable, 1 holmium-plate, 50 ferrofluid, 50 liquid-nitrogen | 2 flux-crystal | 30 | yes | false | `surface_conditions = {{property="magnetic-field", min=99, max=99}}`, i.e. Fulgora only. |

### 3.2 Ammo

| recipe | category | ingredients | result | energy | prod |
|---|---|---|---|---|---|
| `magnetics-ferrite-slug` | crafting | 3 ferrite, 1 iron-plate | 1 ferrite-slug (10 shots) | 2 | no |
| `magnetics-magnet-slug` | crafting | 1 magnet-alloy, 2 ferrite | 1 magnet-slug (10 shots) | 3 | no |
| `magnetics-rail-slug` | crafting | 2 magnet-alloy, 1 SC cable, 1 steel-plate | 1 rail-slug (1 shot) | 6 | no |
| `magnetics-flux-rail-slug` | crafting | 1 rail-slug, 1 flux-crystal | 1 flux-rail-slug (3 shots) | 10 | no |

### 3.3 Buildings

All buildings: prod no, recycle true. Result is 1 item unless noted.

| recipe | category | ingredients | energy |
|---|---|---|---|
| `magnetics-sintering-kiln` | crafting | 1 stone-furnace, 10 stone-brick, 5 iron-plate | 3 |
| `magnetics-induction-furnace` | crafting | 10 steel-plate, 10 ferrite, 5 electronic-circuit, 20 copper-cable | 5 |
| `magnetics-coil-winder` | crafting | 1 assembling-machine-2, 5 magnet-alloy, 5 electronic-circuit, 5 iron-gear-wheel | 5 |
| `magnetics-cryo-chamber` | crafting | 1 chemical-plant, 10 coil, 10 steel-plate, 5 advanced-circuit, 10 pipe | 10 |
| `magnetics-flux-resonator` | crafting | 20 SC cable, 20 coil, 10 processing-unit, 50 steel-plate, 50 concrete | 20 |
| `magnetics-magnetic-separator` | crafting | 10 coil, 10 magnet-alloy, 10 steel-plate, 5 advanced-circuit, 10 iron-gear-wheel | 5 |
| `magnetics-magnetic-drill` | crafting | 1 electric-mining-drill, 10 coil, 5 magnet-alloy, 5 advanced-circuit | 3 |
| `magnetics-maglev-belt` | crafting-with-fluid | 1 **TOP**-transport-belt, 2 coil, 20 ferrofluid | 0.5 |
| `magnetics-maglev-underground-belt` | crafting-with-fluid | 2 **TOP**-underground-belt, 10 coil, 2 SC cable, 40 ferrofluid → **2** | 2 |
| `magnetics-maglev-splitter` | crafting-with-fluid | 1 **TOP**-splitter, 5 coil, 2 SC cable, 2 processing-unit, 80 ferrofluid | 2 |
| `magnetics-coil-capacitor` | crafting | 2 coil, 2 ferrite, 1 iron-plate | 5 |
| `magnetics-smes` | crafting | 10 SC cable, 10 coil, 20 steel-plate, 5 processing-unit | 15 |
| `magnetics-superconducting-pylon` | crafting | 2 SC cable, 5 steel-plate, 4 iron-stick | 2 |
| `magnetics-geomagnetic-coil` | crafting | 6 coil, 10 ferrite, 5 steel-plate, 5 electronic-circuit | 10 |
| `magnetics-flux-dynamo` | crafting | 30 SC cable, 20 coil, 10 processing-unit, 40 steel-plate, 20 refined-concrete | 20 |
| `magnetics-ferrite-wall` | crafting | 3 ferrite, 2 stone-brick | 0.5 |
| `magnetics-magnet-wall` | crafting | 1 ferrite-wall, 2 magnet-alloy, 1 coil | 1 |
| `magnetics-superconducting-wall` | crafting | 1 magnet-wall, 1 SC cable, 5 concrete | 2 |
| `magnetics-mend-coil` | crafting | 4 coil, 5 steel-plate, 5 electronic-circuit, 10 repair-pack | 5 |
| `magnetics-coilgun-turret` | crafting | 1 gun-turret, 4 coil, 4 magnet-alloy, 5 electronic-circuit | 8 |
| `magnetics-arc-emitter` | crafting | 10 coil, 10 steel-plate, 10 advanced-circuit, 10 battery | 15 |
| `magnetics-rail-cannon` | crafting | 1 coilgun-turret, 20 SC cable, 20 magnet-alloy, 40 steel-plate, 10 processing-unit | 30 |

**TOP** means `express` in base and `turbo` when `mods["space-age"]`; it is resolved in `data.lua`. The category `crafting-with-fluid` is base and remains valid under SA (logistics.md §6). The `crafting` category cannot hold fluids (crafting.md §11.1), so the maglev recipes use `crafting-with-fluid`.

---

## 4. Entities

The world-graphics rule is `table.deepcopy(vanilla)`, then the tint walker from crafting.md §10.3. The walker:
- tints only leaf sprites;
- skips `draw_as_shadow`, `draw_as_glow` and `draw_as_light` layers, recipe- and status-tinted WVs, and `apply_runtime_tint` masks;
- does not touch `frozen_patch`, `water_reflection` or circuit connectors.

Every copy also:
- overwrites `name`, `minable.result`, `icons` (our PNG), `next_upgrade`, and the `related_*` links;
- keeps the vanilla `corpse` and `dying_explosion` (crafting.md §2.13).

Tint blending is not documented; the inference is multiplicative (logistics.md §12.1). All tints are therefore light values, which darken or shift hue.

Size notation: "3×3" means collision `{{-1.2,-1.2},{1.2,1.2}}` / selection `{{-1.5,-1.5},{1.5,1.5}}` as in the source.

### 4.1 Production and mining

| entity | type | deepcopy of | size | key stats | vanilla reference (recon) | upgrade / FRG | tint |
|---|---|---|---|---|---|---|---|
| `magnetics-sintering-kiln` | assembling-machine (type changed; `source/result_inventory_size` removed) | stone-furnace | 2×2 | speed 1; burner `{"chemical"}`, 90 kW; pollution 3/min; 0 modules; categories {sintering}; HP 250. SA pressure ≥ 10 condition inherited. | stone furnace: speed 1, 90 kW, pollution 2 (crafting.md §1) | FRG `magnetics-kiln` | `{1.00,0.78,0.62}` #FFC79E terracotta |
| `magnetics-induction-furnace` | assembling-machine (type changed) | electric-furnace | 3×3 | speed 2; 360 kW; pollution 2; 2 modules (5 effects); categories {induction, sintering}; HP 400 | electric furnace: speed 2, 180 kW, 2 modules | FRG `magnetics-induction-furnace` | `{0.72,0.80,1.00}` #B8CCFF |
| `magnetics-coil-winder` | assembling-machine | assembling-machine-2 (fluid_boxes removed) | 3×3 | speed 1; 250 kW; pollution 2; 3 modules; **`effect_receiver.base_effect.productivity = 0.5`**; categories {winding}; HP 350 | AM2 0.75/150 kW; EM plant +50 % base prod (crafting.md §2.10) | FRG `magnetics-coil-winder` (not "assembling-machine", to avoid fast-replacing an AM with it) | `{1.00,0.82,0.62}` #FFD19E copper |
| `magnetics-cryo-chamber` | assembling-machine | chemical-plant | 3×3 | speed 1; 600 kW; pollution 1; 3 modules; categories {cryogenics}; fluid boxes as the chem plant (2 in, 2 out); recipe tints show LN2/ferrofluid in the windows; HP 350 | chem plant 1/210 kW/3 modules | FRG `magnetics-cryo-chamber` | `{0.78,0.95,1.00}` #C7F2FF |
| `magnetics-flux-resonator` | assembling-machine | oil-refinery | **5×5** | speed 1; **5 MW**; pollution 2; 4 modules; categories {resonance}; refinery fluid boxes; HP 600 | oil refinery: 5×5, speed 1, 420 kW, 3 modules (GAME: base/prototypes/entity/entities.lua:8060-8082, not in recon) | FRG `magnetics-flux-resonator` | `{0.85,0.72,1.00}` #D9B8FF violet |
| `magnetics-magnetic-separator` | assembling-machine | centrifuge, plus 1 input fluid box (volume 1000, `pipecoverspictures()`, south `{0,1}`) | 3×3 | speed 1; 350 kW; pollution 3; 2 modules; categories {separation}; HP 400 | centrifuge 1/350 kW/2 modules (crafting.md §2.8) | FRG `magnetics-magnetic-separator` | `{0.75,0.85,1.00}` #BFD9FF |
| `magnetics-magnetic-drill` | mining-drill | electric-mining-drill (the box, `vector_to_place_result`, input fluid box and graphics are kept) | 3×3 | `mining_speed = 1.0`; `resource_searching_radius = 3.49` (7×7); 270 kW; pollution 12/min; 4 modules; HP 450; mines uranium (fluid box kept) | electric drill 0.5, 2.49 (5×5), 90 kW, 3 modules; big drill 2.5, 6.49, 300 kW (mining.md §1) | FRG `mining-drill`; **`electric-mining-drill.next_upgrade = "magnetics-magnetic-drill"`** (same box, mask and group: mining.md §9.1) | `{0.70,0.80,1.00}` #B3CCFF |

### 4.2 Logistics (maglev tier)

| entity | type | deepcopy of | key stats | reference | upgrade | tint |
|---|---|---|---|---|---|---|
| `magnetics-maglev-belt` | transport-belt | express-transport-belt (with a **deep-copied** animation set; the vanilla set is shared by 4 entities, logistics.md §4.2) | `speed = 0.15625` (40/256), **75 items/s** (speed × 480); HP 190; `animation_speed_coefficient = 32` kept | express 0.09375 = 45/s; turbo 0.125 = 60/s (logistics.md §2) | FRG `transport-belt`; `related_underground_belt` → maglev UG; **TOP-transport-belt.next_upgrade → maglev belt** | `{0.95,0.70,1.00}` #F2B3FF (express blue × this = violet) |
| `magnetics-maglev-underground-belt` | underground-belt | express-underground-belt | `max_distance = 13` (5/7/9/11 progression, uint8); speed 0.15625; HP 190 | logistics.md §3.2 | TOP-UG.next_upgrade → maglev UG | same |
| `magnetics-maglev-splitter` | splitter | express-splitter | speed 0.15625; HP 210; `related_transport_belt` → maglev belt | logistics.md §3.3 | TOP-splitter.next_upgrade → maglev splitter | same |

### 4.3 Power

| entity | type | deepcopy of | size | key stats | reference | upgrade | tint |
|---|---|---|---|---|---|---|---|
| `magnetics-coil-capacitor` | accumulator | accumulator; every sprite `scale` and `shift` × 0.5 | **1×1** (`{{-0.4,-0.4},{0.4,0.4}}` / `{{-0.5,-0.5},{0.5,0.5}}`) | buffer **1 MJ**, in/out **100 kW**, tertiary; HP 100 | accumulator 5 MJ, 300 kW, 2×2 (power.md §4) | FRG `magnetics-coil-capacitor` | `{1.00,0.80,0.62}` #FFCC9E |
| `magnetics-smes` | accumulator | accumulator; scale/shift × 1.5 | 3×3 | buffer **12 MJ**, in/out **3 MW**, tertiary; HP 400 | as above | FRG `magnetics-smes` | `{0.70,0.95,1.00}` #B3F2FF |
| `magnetics-superconducting-pylon` | electric-pole | big-electric-pole (4-direction pictures and connection points kept) | 2×2 | `maximum_wire_distance = 64` (the API max), `supply_area_distance = 2`; HP 300 | big pole 32 / 2; substation 18 / 9 (power.md §1) | FRG `big-electric-pole`; **`big-electric-pole.next_upgrade = pylon`** | #B3F2FF |
| `magnetics-geomagnetic-coil` | solar-panel | solar-panel | 3×3 | `production = "40kW"`, **`solar_coefficient_property = "magnetic-field"`**, `performance_at_day = 1`, `performance_at_night = 1` (constant output); HP 250; SA: `surface_conditions = {{property="magnetic-field", min=10}}` | solar 60 kW peak (power.md §5). API: when pointed at another property, output depends only on that property's value (GAME API text: SolarPanelPrototype::solar_coefficient_property) | FRG `magnetics-geomagnetic-coil` | `{0.82,0.75,1.00}` #D1BFFF |
| `magnetics-flux-dynamo` | burner-generator | new prototype. `animation` = deepcopy of centrifuge `graphics_set.idle_animation` (3×3 layers, crafting.md §2.8), tinted | 3×3 | `max_power_output = "10MW"`; `burner = {type="burner", fuel_categories={"magnetics-flux"}, effectivity=1, fuel_inventory_size=1, burnt_inventory_size=1, emissions_per_minute={pollution=0}}`; `energy_source = {type="electric", usage_priority="secondary-output"}`; HP 800; SA: magnetic-field ≥ 10 | nuclear reactor 40 MW, fuel cell 8 GJ (power.md §1, §9.2); base burner-generator 1 MW, eff 0.5 (power.md §7) | none | `{0.85,0.65,1.00}` #D9A6FF |

Vanilla edit (additive only): in `data-updates.lua`, `"magnetics-flux"` is appended to `data.raw.locomotive.locomotive.energy_source.fuel_categories`. The locomotive has no burnt-result slot, so spent crystals are voided in locomotives (power.md §2.6: "void burnt results"). Locomotive reference: `max_speed = 1.2`, `max_power = "600kW"` (GAME: base/prototypes/entity/trains.lua:504-505, not in recon).

### 4.4 Defense

Wall resistances are written `decrease/percent`. The stone-wall reference is phys 3/20, impact 45/60, explosion 10/30, fire 0/100, acid 0/80, laser 0/70, no electric entry, HP 350 (combat.md §11.2).

| entity | type | deepcopy of | HP | resistances | special | upgrade | tint |
|---|---|---|---|---|---|---|---|
| `magnetics-ferrite-wall` | wall | stone-wall | 450 | phys 4/25, impact 45/60, expl 10/35, fire 0/100, acid 0/80, laser 0/70, **electric 0/30** | — | **`stone-wall.next_upgrade = ferrite-wall`**, FRG `wall` | `{0.62,0.55,0.58}` #9E8C94 |
| `magnetics-magnet-wall` | wall | stone-wall | 700 | phys 6/30, impact 50/65, expl 15/40, fire 0/100, acid 0/85, laser 0/75, electric 0/50 | **`attack_reaction = {range = 2, damage_type = "physical", reaction_modifier = 0, action = {type="direct", action_delivery={type="instant", target_effects={{type="damage", damage={amount=12, type="electric"}}}}}}`**: shocks every biter that bites it. The template comes from vanilla's commented stone-wall code (GAME: base/prototypes/entity/entities.lua:3383-3409, not in recon); the field is `EntityWithHealthPrototype::attack_reaction` in the API | ferrite.next_upgrade → magnet | `{0.62,0.72,1.00}` #9EB8FF |
| `magnetics-superconducting-wall` | wall | stone-wall | 1500 | phys 15/50, impact 60/70, expl 25/60, fire 0/100, acid 0/90, laser 0/90, electric 0/100 | attack_reaction 25 electric (range 2) | magnet.next_upgrade → SC | `{0.72,0.95,1.00}` #B8F2FF |
| `magnetics-mend-coil` | electric-energy-interface | new. `picture = {layers = …}` built from the substation's first-direction frame (`x = 0`) plus its shadow layer | 2×2 | 300 | — | `energy_source = {type="electric", buffer_capacity="1MJ", usage_priority="secondary-input", input_flow_limit="200kW"}`, `energy_usage = "0kW"`, `gui_mode = "none"`; repairs in a 25×25 square (range 12) via script (§6); SA: magnetic-field ≥ 10 | FRG `magnetics-mend-coil` | `{0.65,1.00,0.75}` #A6FFBF |

### 4.5 Turrets

| entity | type | deepcopy of | size / HP | attack | energy | reference | tint |
|---|---|---|---|---|---|---|---|
| `magnetics-coilgun-turret` | ammo-turret | gun-turret | 2×2 / 600 | projectile; `ammo_category = "magnetics-coil-slug"`; `cooldown = 20` (3 shots/s); `range = 24`; `health_penalty = 1`; `inventory_size = 1`, `automated_ammo_count = 10` | `energy_source = {type="electric", buffer_capacity="180kJ", input_flow_limit="400kW", usage_priority="primary-input"}`, `energy_per_shot = "60kJ"` (an AmmoTurret field, combat.md §3.4) | gun turret: 400 HP, range 18, cooldown 6 (combat.md §5) | `{0.70,0.78,1.00}` #B3C7FF (the runtime-tint mask is skipped) |
| `magnetics-arc-emitter` | electric-turret | laser-turret | 2×2 / 1000 | beam params: `cooldown = 60`, `range = 20`, `range_mode = "center-to-bounding-box"`, `ammo_category = "magnetics-arc"`, built-in `ammo_type` (details below) | `buffer_capacity = "2.4MJ"`, `input_flow_limit = "3MW"`, `drain = "30kW"`, primary-input; `energy_consumption = "1.2MJ"` per shot | laser: 800 kJ/shot, cd 40, range 24; tesla: 12 MJ/shot, cd 120, range 30 (combat.md §5.2, §5.5) | `{0.70,0.95,1.00}` #B3F2FF |
| `magnetics-rail-cannon` | ammo-turret | gun-turret; all layer `scale`/`shift` × 1.5; `projectile_creation_distance` × 1.5 | 3×3 / 2000 | projectile; `ammo_category = "magnetics-rail"`; `cooldown = 180`; `range = 36`; `min_range = 4`; `rotation_speed = 0.008`; `health_penalty = -1` (prefers big targets, like SA railgun); `true_collinear_ejection = true` | `buffer_capacity = "4MJ"`, `input_flow_limit = "2MW"`, `energy_per_shot = "4MJ"` | SA railgun 4000 HP, cd 170, range 40, 10 MJ/shot (combat.md §5.4) | `{0.85,0.70,1.00}` #D9B3FF |

SA placement condition for all three turrets: magnetic-field ≥ 10.

**Ammo actions and hidden helpers:**
- **Ferrite slug:**
  - `target_type = "direction"`, projectile `magnetics-ferrite-slug-projectile` with `starting_speed = 1.2`, `max_range = 28`.
  - Projectile: `piercing_damage = 60`, `direction_only = true`, **`force_condition = "not-same"`** (does not hit own walls), `acceleration = 0`, action damage **16 physical**.
  - Animation: base `bullet.png` (3×50, glow), tinted `#6E5A62`. Cannon shells use the same pattern (combat.md §6.3, §7).
- **Magnet slug:** the same shape with damage **45 physical**, `piercing_damage = 300`, tint `#6D86C9`.
- **Rail slug:**
  - `target_type = "direction"`, `clamp_position = true`.
  - `action = {type = "line", range = 40, width = 1.5, force = "enemy", …}`, instant damage **1200 physical**.
  - `range_effects` = create-explosion `magnetics-rail-trail`. The pattern is from SA railgun-ammo (combat.md §6.4, §10).
- **Flux rail slug:** line range 44, damage **2400 physical + 600 electric**, `magazine_size = 3`.
- **Arc emitter `ammo_type.action`:** direct / instant, target_effects in this order:
  1. nested chain `magnetics-arc-chain`. It goes first, as SA comments that the "chain effect must go first in case the beam kills the target" (combat.md §9).
  2. damage **30 electric**.
  3. sticker `electric-mini-stun` (a base sticker: 40 ticks, movement × 0.2; GAME: base/prototypes/entity/entities.lua:8047-8052, not in recon).
  4. a nested **cosmetic** beam `magnetics-arc-beam` (`max_length = 22`, `duration = 12`).
- **`magnetics-arc-chain` (chain-active-trigger):** `max_jumps = 6`, `max_range_per_jump = 7`, `jump_delay_ticks = 4`, **`fork_chance = 0`** (deterministic at normal quality), `fork_chance_increase_per_quality_level = 0.05`. Its action is direct with two deliveries: instant (damage **20 electric** + `electric-mini-stun`) and a cosmetic beam `magnetics-arc-bounce-beam` (duration 12, `add_to_shooter = false`). The fields and defaults are in combat.md §9.
- **Beams:**
  - Both are built with base's global `append_base_electric_beam_graphics(beam, "additive-soft", {"trilinear-filtering"}, tint, light_tint)` (GAME: base/prototypes/entity/beams.lua:197, not in recon), with tint #9FE8FF.
  - Both have `action = nil`, so all damage is instant and deterministic.
  - `damage_interval = 20` is required by the API (combat.md §8).
- **`magnetics-rail-trail`:** an explosion with `beam = true`, `rotate = true`, `draw_as_glow`, `blend_mode = "additive"`, light `{intensity 1.5, size 16, color #B58CFF}`. It uses a **procedurally drawn** 64×440, 16-frame violet-cyan gradient strip. Justification: base has no line-beam sprite, and SA's `railgun-beam.png` is unavailable without SA (combat.md §10). It is a plain gradient that PIL can draw exactly.

**Upgrades for new ammo categories.** These are appended in `data-updates.lua`, after SA's in-place edits (combat.md §0.4). Each copy takes the modifier the source effect has *at that moment*, so SA's changed values (e.g. physical-projectile-damage-6 bullet 0.2) carry over:
- Every `ammo-damage`/`gun-speed` effect with `ammo_category = "bullet"` in `physical-projectile-damage-N` / `weapon-shooting-speed-N` → a copy with `magnetics-coil-slug`.
- `cannon-shell` → a copy with `magnetics-rail` (+0.9 / +1.3 / +1 at levels 5-7; gun-speed +0.8 / +1.5 at 5-6; combat.md §14.2).
- `laser` in `laser-weapons-damage-N` / `laser-shooting-speed-N` → a copy with `magnetics-arc` (+0.2 / 0.2 / 0.3 / 0.4 …).

Result: no new upgrade techs, and every Magnetics weapon scales with the vanilla infinite research.

---

## 5. Technologies

The `icon_size = 256` icons are drawn by PIL (tech.md §1.3). Packs: A automation, L logistic, M military, C chemical, P production, U utility, S space, Met metallurgic, EM electromagnetic.

| # | technology | prerequisites | cost | unlocks |
|---|---|---|---|---|
| T1 | `magnetics-ferrite-sintering` | steel-processing, logistic-science-pack, stone-wall | 50 × 15 s [A+L] | sintering-kiln, ferrite, ferrite-wall |
| T2 | `magnetics-induction-smelting` | T1, advanced-material-processing | 75 × 30 s [A+L] | induction-furnace, magnet-alloy |
| T3 | `magnetics-electromagnetic-coils` | T2, automation-2 | 100 × 30 s [A+L] | coil-winder, coil, coil-capacitor |
| T4 | `magnetics-geomagnetic-induction` | T3, solar-energy | 150 × 30 s [A+L] | geomagnetic-coil |
| T5 | `magnetics-coilgun` | T3, military-science-pack | 100 × 30 s [A+L+M] | coilgun-turret, ferrite-slug, magnet-slug |
| T6 | `magnetics-electrified-walls` | T3, military-science-pack | 150 × 30 s [A+L+M] | magnet-wall, mend-coil |
| T7 | `magnetics-ferrofluid` | T1, advanced-oil-processing | 100 × 30 s [A+L+C] | ferrofluid |
| T8 | `magnetics-magnetic-mining` | T3, advanced-circuit, chemical-science-pack | 200 × 30 s [A+L+C] | magnetic-drill |
| T9 | `magnetics-magnetic-separation` | T3, T7 | 150 × 30 s [A+L+C] | magnetic-separator, magnetite-separation |
| T10 | `magnetics-arc-emitter` | T3, laser, military-science-pack | 200 × 30 s [A+L+C+M] | arc-emitter |
| T11 | `magnetics-superconductivity` | T3, plastics, chemical-science-pack | 250 × 30 s [A+L+C] | cryo-chamber, liquid-nitrogen, superconducting-cable |
| T12 | `magnetics-superconducting-grid` | T11, T6, electric-energy-distribution-2, electric-energy-accumulators | 250 × 30 s [A+L+C] | smes, superconducting-pylon, superconducting-wall |
| T13 | `magnetics-maglev-logistics` | logistics-3, T7, T11, utility-science-pack; **SA adds** turbo-transport-belt, electromagnetic-science-pack | base 400 × 30 s [A+L+C+P+U]; **SA** 1000 × 60 s [A+L+C+P+U+S+Met+EM] | maglev-belt, maglev-underground-belt, maglev-splitter |
| T14 | `magnetics-flux-resonance` | T7, T11, T12, uranium-processing, production-science-pack | 300 × 45 s [A+L+C+P] | flux-resonator, flux-crystal, flux-crystal-recharge, flux-dynamo |
| T15 | `magnetics-rail-cannon` | T5, T14, military-4 | 600 × 45 s [A+L+C+M+P+U] | rail-cannon, rail-slug, flux-rail-slug |
| T16 | `magnetics-fulgoran-magnetism` **(SA only)** | electromagnetic-science-pack, T9, T14 | 500 × 60 s [A+L+C+P+S+EM] | scrap-separation, flux-crystal-holmium |

That is 15 technologies in base and 16 under SA. There are no new upgrade technologies (see the appended effects in §4.5).

Reference costs used for calibration (tech.md §3):
- logistics-2: 200×30 [A+L]
- logistics-3: 300×15 [A+L+C+P]
- laser-turret: 150×30 [A+L+M+C]
- nuclear-power: 800×30 [A+L+C]
- turbo-transport-belt: 500×60 [A+L+C+P+S+Met]

Each Magnetics tech costs about the same as the vanilla tech on its tier.

Locale: en/ru/de for every name and description, in the same set of languages as the Mindustry mod. Tech names carry no `-N` suffix, so none of them falls back to a stripped name (tech.md §8.4).

---

## 6. Control-script feature: mend coil (the only script)

### 6.1 Behaviour
A powered mend coil repairs damaged buildings of its force inside a 25×25 square (|dx| ≤ 12, |dy| ≤ 12) centred on it:
- up to **10 HP/s per damaged entity**;
- a coil budget of **40 HP/s**;
- energy drawn from the coil's own buffer at **2 kJ per HP**, i.e. 80 kW at full budget.

Several coils may cover one entity. The per-entity cap still holds, so overlapping coils do not stack on the same target.

### 6.2 Algorithm (UPS-cheap, event-driven)
- **Storage:**
  - `storage.coils[unit_number] = {entity, surface, x, y}`;
  - `storage.grid[surface][cx][cy] = array of unit_numbers`, with cell = 32×32 tiles, insertion-ordered;
  - `storage.damaged = array of {entity, unit_number}` plus `storage.damaged_index[unit_number] = i`;
  - `storage.cursor`.
- **Register:**
  - on `on_built_entity`, `on_robot_built_entity`, `script_raised_built` and `script_raised_revive` (+ `on_space_platform_built_entity` when SA is active), filtered to `name = magnetics-mend-coil`;
  - then call `script.register_on_object_destroyed(coil)`. Removal is handled in `on_object_destroyed`, a single path for mined, died and destroyed coils.
  - On building a coil, run **one** `find_entities_filtered{area = coil square, force = coil.force}` and enqueue entities whose `health < max_health`. This is a one-off cost.
- **Detect damage:**
  - `on_entity_damaged` with filters `{filter="type", type="unit", invert=true}`, `{mode="and", filter="type", type="unit-spawner", invert=true}`, `{mode="and", filter="type", type="character", invert=true}`, `{mode="and", filter="final-health", comparison=">", value=0}`. These filter kinds exist in `LuaEntityDamagedEventFilter` (runtime-api.json concept, read for this design).
  - Result: biters being shot never reach Lua.
  - The handler is O(1): if `storage.coils_by_force[entity.force.index] > 0` and the entity is not yet queued, append it.
  - The handler is registered only while at least one coil exists. The conditional registration is repeated in `on_load` from `storage` (the standard deterministic pattern, harness.md §1.2).
- **Heal:** `script.on_nth_tick(30)`:
  - process at most **200** queued entities starting at `storage.cursor` (round-robin);
  - for each valid entity: look up the 3×3 grid cells around it and take the first coil (in insertion order) that is valid, in range, and has `coil.energy ≥ cost` and remaining cycle budget;
  - heal `h = min(max_health - health, 5, coil_budget_left)` (5 HP per 30 ticks = 10 HP/s; the coil budget is 20 HP per cycle), then `coil.energy -= 2000 * h`, `entity.health += h`;
  - dequeue the entity when it is at full health, or when no coil covers it (checked once per cycle).
  - Optional flourish: `rendering.draw_line` from coil to target, `time_to_live = 20`, at most 20 lines per cycle.
- **UPS bound:**
  - idle cost 0: no queue, and no handler if there are no coils;
  - per damage event on a player building: one table lookup;
  - per 30 ticks: ≤ 200 × (≤ 9 cells × coils per cell) checks.
  - No `find_entities` in the steady state.
- **MP-determinism:**
  - all state lives in `storage`;
  - iteration uses arrays (insertion order), never `pairs` over hash keys for decisions;
  - no `math.random`;
  - rendering objects are part of game state.

### 6.3 Tests (details in §8, R1–R3)
The tests cover:
- heal rate and energy per HP on a single wall;
- no healing out of range or without power;
- the per-entity cap with two overlapping coils;
- survival of the queue across a create → save → benchmark cycle;
- a UPS benchmark with and without 100 coils and 1000 queued walls.

---

## 7. Balance justification and risks

### 7.1 Why each number

**Ferrite:**
- 2 ore + 1 stone → 2 ferrite in 3.2 s. The kiln is a stone furnace (speed 1, 90 kW; crafting.md §1) that processes ore at the same per-ore time as iron plates, so early players can think in "furnace columns".
- Stone, usually a low-value resource, gets a steady sink.

**Magnet alloy:** it needs steel, so it is placed after steel-processing. Its cost (≈ 5 iron-equivalent ore + stone + copper) makes it a valued intermediate, on the level of steel.

**Coil winder (+50 % productivity):**
- It follows the SA pattern of specialised machines with base productivity (EM plant and foundry +50 %; crafting.md §1).
- It is restricted to one intermediate, so base-game power creep is limited to coils.
- Under SA, the EM plant (speed 2) winds coils 2× faster. That is the natural upgrade.

**Magnetic drill, 2× electric speed on a 7×7 area:**
- It sits between electric (0.5, 5×5) and big drill (2.5, 13×13) (mining.md §1).
- The price is 3× the energy (270 vs 90 kW, so 1.5× energy per ore), plus a blue-science recipe.
- As a 3×3 upgrade target it keeps existing layouts. The big drill keeps its Vulcanus advantage (hard-solid, 50 % drain).

**Maglev 75/s:**
- It is the next point of the vanilla +8/256 speed progression (logistics.md §0, candidate row).
- It is gated behind utility science (base) or turbo + EM science (SA), so it never precedes the tier it upgrades.
- The ferrofluid cost per belt equals express's lubricant cost (20).

**Coil capacitor (1 MJ, 100 kW, 1×1):**
- Per tile it stores less than an accumulator (1.0 vs 1.25 MJ/tile) and flows a little more (100 vs 75 kW/tile) (power.md §4).
- Niche: it is unlocked at A+L without the oil → sulfur → battery chain, and it is 1×1.
- It costs more per MJ than an accumulator (coils vs batteries).

**SMES (12 MJ, 3 MW, 3×3):**
- Capacity per tile ≈ an accumulator (1.33 vs 1.25 MJ/tile). Flow per tile is 4.4× (333 vs 75 kW/tile).
- Niche: burst power for turret banks. A laser turret refills at up to 9.6 MW (combat.md §5.2), an arc emitter at 3 MW, a rail cannon at 2 MW.
- It is not bulk storage, so accumulators keep their role.

**Pylon (wire 64):**
- 2× the big pole's 32 (power.md §1); 64 is the API maximum.
- It is a convenience and spectacle item (spanning lakes). Poles are cheap in vanilla, so the SC-cable cost is the only real price.

**Geomagnetic coil (40 kW × field factor, constant):**
- On Nauvis it gives 36 kW if output = production × field/100, or 40 kW if the factor is field/default (pilot E1 settles this).
- Solar: 60 kW peak, 0 at night (power.md §5).
- The coil needs no accumulators but has a lower peak density: 4.0–4.4 vs 6.7 kW/tile.
- **On Fulgora** (field 99, solar-power 20; power.md §5, §11.6): solar peaks at 12 kW, the coil gives ≈ 40 kW, i.e. ≈ 3.3× solar's *peak*. That is the memorable Fulgora niche.
- On Vulcanus (field 25) and Aquilo (field 10) it is weak (10 and 4 kW). In space it is blocked.

**Flux dynamo (10 MW, 3×3) and flux crystal (2 GJ):**
- A crystal lasts 200 s, the same duration as a fuel cell in the 40 MW nuclear reactor (8 GJ / 40 MW; power.md §1, §9.2).
- The dynamo has ¼ of a reactor's power but no heat exchangers, turbines or water. That makes it the late compact option.
- Balance comes from crystal cost:
  - U-238, 2 SC cables and 150 MJ of resonator power for a new crystal;
  - each recharge costs 20 ferrofluid + 20 LN2 + 50 MJ of power and **loses 10 %** of crystals (expected 10 cycles = 20 GJ per new crystal);
  - 50 MJ + LN2 power per 2 GJ ≈ 3 % overhead.
- It is blocked in space, so SA platforms keep their vanilla power problem.

**Flux crystal as locomotive fuel (accel 1.8, top speed 1.3):**
- Nuclear fuel: 2.5 / 1.15; rocket fuel: 1.8 / 1.15 (power.md §9.2).
- Maglev trains get the best top speed, but nuclear fuel keeps the best acceleration. A real trade-off, and a memorable one.

**Walls:**
- HP 350 → 450 → 700 → 1500 along the upgrade chain, with rising physical flat reduction (3 → 4 → 6 → 15).
- Against a behemoth bite of 90 (combat.md §12) the SC wall reduces damage far more than stone. The exact formula is not in the sources; test C1 measures it.
- Thorns: 12 electric kills a small biter (15 HP) on its first bite and a medium biter (75 HP) in about 7 bites. No base biter resists electric (combat.md §12).
- SC walls with 25 electric thorns plus mend coils make a self-sustaining line against medium and big biters. Behemoths (bite 90, heal 0.1/tick) still break through without turrets.

**Coilgun:**

| | Coilgun, ferrite slug | Coilgun, magnet slug | Gun turret (firearm / piercing / uranium; combat.md §5, §6.2) |
|---|---|---|---|
| Single-target | 16 × 3/s = 48 dps | 45 × 3 = 135 dps | 50 / 80 / 240 dps |

- The ferrite slug roughly matches firearm magazines. It adds range (24 vs 18) and pierce (a 60 budget = 4 small biters in a line).
- Heavy slugs lose much less to flat physical resistance than 5-damage bullets. Medium biters: 4/10 %.
- Gun turrets with uranium remain the single-target king. The coilgun needs power (180 kW while firing).

**Arc emitter:**
- It uses the laser turret's power while firing (1.2 MJ per second vs 800 kJ per 40 ticks = 1.2 MW; combat.md §5.2) and has 30 dps single-target.
- Per shot it can deal 30 + 6×20 = 150 across 7 targets, plus a 40-tick slow.
- Its niche is small/medium swarms. Tesla (SA) remains strictly stronger: 120 dmg, 10 jumps, range 30.

**Rail cannon:**
- 1200 per target in a 40-tile line every 3 s: about 1/8 of the SA railgun's 10000 (combat.md §6.4), at a shorter range (36 vs 40).
- It kills any number of medium biters in a line in one shot, and a behemoth (3000 HP, phys 12/10 %) in 3 shots.
- Each shot costs 2 alloy + 1 SC cable + 4 MJ, so it is a late, expensive toy.
- The flux slug doubles the damage and triples the shots per item, at the price of a 2 GJ crystal.

### 7.2 Risks (with mitigation)

1. **Engine semantics that are not in the sources.** All of these are covered by pilots before any test is registered:
   - how `tint` blends (logistics.md §12.1);
   - the `solar_coefficient_property` scaling (field/100 vs field/default);
   - whether `attack_reaction` targets the attacker, and when;
   - how `piercing_damage` counts the hit entity's health;
   - chain re-targeting;
   - whether a `secondary-input` EEI fills its buffer;
   - the resistance formula (combat.md §16).

   Fallbacks:
   - the thorns become plain HP bonuses;
   - the pierce budget is re-tuned so the "4 small biters" target holds;
   - the mend coil switches to a `tertiary` EEI.
2. **Load order with Space Age.** The optional-dependency syntax `"? space-age"` and the claim that it loads us after SA are unverified (tech.md §9.2).
   - A wrong order would break the TOP-belt substitution, `next_upgrade`, the category inserts and the copied upgrade modifiers.
   - Mitigation: all cross-mod edits go in `data-updates.lua`, and the load test runs 4 configurations with a check of every link.
3. **Power creep in late game.** The flux dynamo at 1.1 MW/tile, maglev at 75/s, the SMES flow and the 64-tile pylon could flatten vanilla's power and logistics puzzles.
   - Mitigations: late gates (P/U science, SA turbo + EM), costs in scarce SC cable and crystals, and exclusion from space platforms.
   - Every late number is marked "tunable" and reviewed by the council after the tests (CLAUDE.md, council rule 4).
4. **Mend coil UPS in megabases and big fights.** Mass wall damage could flood the queue.
   - Mitigations: the event filters, a queue cap of 200 per 30 ticks, and no scanning.
   - Fallback: `on_nth_tick(60)` and a cap of 100.
   - Benchmark R3 gates the release.
5. **Visuals cannot be seen headless.** No PNGs are in the install (crafting.md header).
   - Scaled sprites (capacitor × 0.5, SMES and rail cannon × 1.5) may look blurry.
   - Express 32-frame belt animation at 75/s may not match item motion (logistics.md §4.4).
   - Mitigations: every icon is reviewable as a PNG; a showcase sheet lists each entity with its base and tint swatch; the author checks the world look in the real game.
   - Fallbacks: an unscaled 2×2 SMES (15 MJ, 3 MW) and a 2×2 rail cannon.

---

## 8. Test plan (headless server, harness.md)

**Configurations** (every test runs in each unless marked):
- `B` = base;
- `BQ` = base + quality;
- `BE` = base + elevated-rails;
- `SA` = base + elevated-rails + quality + space-age.

**Method:**
- a lab surface (`generate_with_lab_tiles`, harness.md §2);
- EEI power (harness.md §6.3), one substation per cell with `auto_connect = false`;
- infinity chests and pipes as sources and sinks;
- measurement windows after a 5 s warm-up.

**Tolerances:** ±1 craft for crafting counts. For probabilistic products: exact expected value ± 3σ of the binomial count, with the map seed fixed so the run is repeatable.

**Pilots first (harness.md §16).** Each pilot runs on a seed or scenario that is not reused in a test. It settles:
- the EEI power units;
- belt, inserter and loader directions;
- biter pinning (`stop` + `distraction.none`);
- `products_finished` semantics;
- the mining rate formula;
- the properties of a planet-less surface;
- the seven engine questions in risk 1.

### 8.1 Static and load tests

| id | measures | expected |
|---|---|---|
| S0 | Loading in B, BQ, BE, SA | Exit 0; 0 errors and 0 warnings in the log; 22 buildings + 10 items + 2 fluids present; every prototype name starts with `magnetics-`; no name appears in `names_sa.tsv`. |
| S1 | Spec → runtime, every number | Via `prototypes.*` (harness.md §13) compare: crafting speed, energy usage, modules, base effect, categories, box sizes, HP, resistances, belt speed (0.15625), UG distance (13), drill speed/radius (via `get_mining_drill_radius`), buffers and flows, wire/supply distance, solar production and coefficient property, burner categories, turret ranges, cooldowns and energies, ammo categories, magazines, fuel values, every recipe's ingredients, results, probabilities, energy, category, prod and recycle flags. Estimate: about 450 checks, 0 failures. |
| S2 | Technology tree | 15 (B) / 16 (SA) techs; prerequisites exist; costs and packs as in §5; every Magnetics recipe is `enabled = false` and unlocked by exactly one tech; `research_all_technologies()` raises no error. |
| S3 | Vanilla edits are additive only | Present: `next_upgrade` on stone-wall, electric-mining-drill, big-electric-pole and TOP belt/UG/splitter; category inserts on AM2/AM3/character (+ EM plant and cryogenic plant under SA); locomotive fuel category. Every vanilla recipe and tech is byte-identical to a run without the mod, **except** the appended upgrade effects (the effect count grows; no existing effect changes). |
| S4 | Quality recycling (BQ, SA) | `…-recycling` recipes exist for the 22 buildings and for coils. None exist for ferrite, alloy, SC cable, crystals, LN2, ferrofluid or the separations. |
| S5 | SA conditions (SA) | On a surface with `magnetic-field = 0`, `can_place_entity` is false for the dynamo, geomagnetic coil, mend coil and the 3 turrets; at 10 it is true. The flux crystal recipe runs at 90 and stalls at 89; the holmium flux recipe runs only at 99. |

### 8.2 Production simulations (120 s windows, no modules)

| id | machine × recipe | expected output in 120 s |
|---|---|---|
| P1 | kiln × ferrite (speed 1, 3.2 s, 2 per craft) | 37.5 crafts → **75 ferrite** (±2) |
| P2 | induction furnace × ferrite / × magnet alloy (speed 2) | **150 ferrite** / **75 alloy** |
| P3 | coil winder × coil (speed 1, +50 % prod) | 120 crafts + 60 bonus = **180 coils** (±2). Controls: AM2 **90**, AM3 **150**, SA EM plant **360**. |
| P4 | chemical plant × ferrofluid | **1200 ferrofluid** |
| P5 | cryo chamber × LN2 / × SC cable | **1200 LN2** / 30 crafts → **60 cables** (SA cryogenic plant: **120**) |
| P6 | resonator × flux crystal (300 s window) | **10 crystals** |
| P7 | resonator × recharge (3000 s, 300 crafts, p = 0.9) | **270** crystals, 3σ band **[254, 286]** |
| P8 | separator × magnetite separation | 24 crafts → **96 iron ore**; copper expected 12, band [5, 19] |
| P9 (SA) | separator × scrap separation (4 s) | 30 crafts → **60 gears**; steel expected 12 [4, 20]; holmium expected 6 [0, 12] |
| P10 | energy draw of each machine while working | equal to `energy_usage` (360 kW, 250 kW, 600 kW, 5 MW, 350 kW …) ± 1 %, measured with the EEI buffer method (harness.md §6.3) |

### 8.3 Mining and logistics

| id | measures | expected |
|---|---|---|
| M1 | Magnetic drill on iron ore (mining_time 1), 60 s, no research | **60 ore** (1.0/s) if the rate is mining_speed / mining_time (pilot). Control: electric drill **30**. `mining_area` is a 7×7 box (±0.02). Draw is 270 kW. Uranium can be mined when sulfuric acid is supplied. |
| L1 | Maglev belt throughput (insert-at-back / clear method, harness.md §8) | **75.0 items/s**, ±1.875 (one quantum). Controls: express 45, turbo 60 (SA). |
| L2 | Maglev underground reach | A pair at 13 tiles apart passes items; a pair 14 apart does not connect. |
| L3 | Maglev splitter | 75 in → 37.5 / 37.5 out (±1.875) |
| L4 | Upgrade planner links | `prototypes.entity[TOP-*].next_upgrade` = maglev names; the chain stone → ferrite → magnet → SC wall; electric drill → magnetic drill; big pole → pylon. |

### 8.4 Power

| id | measures | expected |
|---|---|---|
| E1 | Geomagnetic coil output with `surface.set_property("magnetic-field", v)`, v ∈ {0, 10, 25, 90, 99}, sampled at noon and midnight | Linear in v and identical day and night. H1 (v/100): **0 / 4 / 10 / 36 / 39.6 kW**. H2 (v/90): 0 / 4.44 / 11.1 / 40 / 44 kW. The pilot picks H1 or H2 before registration; the other becomes a failure. |
| E2 | Coil capacitor and SMES charge/discharge from and into EEIs | Capacitor: holds **1 MJ**, charges at **100 kW** (empty → full in 10 s ± 1 tick). SMES: **12 MJ**, **3 MW** (full in 4 s; discharge capped at 3 MW into a 10 MW load). |
| E3 | Pylon wire reach (`connect_to` with reach check) | Connects at 64.0 tiles, fails at 64.5. With quality, `get_max_wire_distance("legendary")` is reported; > 64 is allowed only if the engine accepts it (risk logged). |
| E4 | Flux dynamo into a 20 MW load, 1 crystal | Output **10 MW** ± 1 %; the crystal lasts **200 s** ± 1 s; 1 spent crystal lands in the burnt inventory. |
| E5 | Locomotive fuel | `can_insert` of a flux crystal into the locomotive fuel inventory is true; the item has top speed 1.3 and acceleration 1.8; a spent crystal never appears in the locomotive. |

### 8.5 Combat

Setup: biters are pinned with `stop` + `distraction.none` and `allow_destroy_when_commands_fail = false` (harness.md §10.1). Turrets are `destructible = false` and powered by EEI. Measurements come from `kills`, `damage_dealt` and `on_entity_damaged` sums (combat.md §13.4).

| id | measures | expected |
|---|---|---|
| C1 | Walls: `damage(100, "enemy", t)` for t ∈ {physical, impact, explosion, fire, acid, laser, electric}, on stone, ferrite, magnet and SC walls | Physical, explosion and acid damage strictly ordered SC < magnet < ferrite < stone. Electric: stone 100, ferrite 70, magnet 50, SC 0. Fire 0 on all. HP 350 / 450 / 700 / 1500. The applied values also reveal the decrease/percent order, and that order is then pinned. |
| C2 | Thorns: one medium biter commanded to attack a magnet wall | Each bite deals **12 electric** to the biter (`on_entity_damaged` with `cause` = the wall, or the biter's health delta). The biter dies on bite **7** (75 HP + 0.35 HP of healing per 35-tick bite). SC wall: 25 per bite, death on bite **4** (75 − 75 + 0.7 > 0 after bite 3). Stone wall control: 0 reflected damage. |
| C3 | Coilgun pierce: 8 small biters in a straight line, 1.5 tiles apart, from 8 tiles out | The first ferrite slug kills **4** (budget 60 / 15 HP; band [3, 5] until the pilot fixes the semantics); all 8 are dead by the 2nd shot (≤ 40 ticks after the first shot). Gun turret + firearm control needs ≥ 2 s. Energy: 60 kJ per shot. |
| C4 | Coilgun single target: one big biter (375 HP, phys 8/10 %) for 10 s | The damage ratio magnet slug / ferrite slug is within ±5 % of (45 − 8)/(16 − 8) × (same percent) = **4.6** if decrease is applied first; the pilot pins the formula. |
| C5 | Arc emitter: 10 small biters in a cluster 3 tiles apart (jump range 7) | The first shot kills **7** (1 primary + 6 jumps, fork = 0); all 10 are dead after the 2nd shot (60 ticks). On 10 medium biters, damage per shot = **150** (30 + 6×20) ± 0; every hit biter gets `electric-mini-stun`. Energy is 1.2 MJ per shot. Determinism: two runs give byte-identical results JSON. |
| C6 | Rail cannon: 10 medium biters in a line along the aim, 2 tiles apart, from 10 tiles; then 1 behemoth | Line: **10 kills in 1 shot**. Behemoth: killed by the **3rd** shot (≈ 1069 per hit if decrease is applied first), i.e. ≤ 6.5 s after the first shot. Own stone walls placed in the line take 0 damage (`force = "enemy"`). Energy: 4 MJ per shot. |
| C7 | Upgrade propagation | After researching physical-projectile-damage-1: `get_ammo_damage_modifier("magnetics-coil-slug") = 0.1`. After laser-weapons-damage-1: `get_ammo_damage_modifier("magnetics-arc") = 0.2`. After physical-projectile-damage-5: `magnetics-rail` = 0.9. In SA, level-6 values follow SA's edited modifiers. |

### 8.6 Script (mend coil)

| id | measures | expected |
|---|---|---|
| R1 | One coil at (0,0); magnet walls at (5,0) and (20,0), each hit by `damage(300, "enemy", "physical")` (a direct health write does not raise the event, combat.md §13.4) | Wall 1: +10 HP/s ± 0.5 over the first 10 s; full after (damage applied)/10 s ± 1 s. Wall 2 (out of range) unchanged. Coil energy drop = 2 kJ × HP healed ± 1 %. Unpowered coil: 0 HP/s. |
| R2 | Two overlapping coils, 1 wall; then 1 coil and 6 damaged walls | One wall heals at 10 HP/s, not 20. Six walls: **40 HP/s in total** ± 1; the first four walls in queue order heal at 10 HP/s each until full, then the rest. |
| R3 | Persistence and UPS | The queue survives create → save → `--benchmark`; healing resumes. The benchmark mean ms/tick with 100 coils and 1000 queued walls exceeds the same map without coils by **< 0.05 ms** (pre-registered threshold, tunable only before registration). |

### 8.7 Graphics artefacts

| id | measures | expected |
|---|---|---|
| V1 | Every referenced mod PNG exists; sizes 64 (items, entities, fluids, recipes, ammo categories) and 256 (techs); rail-trail 64×440 × 16 frames | 0 missing; `showcase.png` sheet: 32 item icons + 2 fluids + 16 techs + the rail-trail strip + a table of entity → vanilla base → tint swatch |
| V2 | The tint walker leaves shadow, glow, light and runtime-tint layers untouched | For each copied entity, a data-stage dump shows `tint = nil` on every `draw_as_shadow` / `draw_as_glow` / `draw_as_light` / `apply_runtime_tint` leaf |

**Pre-registration note (CLAUDE.md gate).** The pilots run on a separate seed. Every "if the pilot says…" branch above is resolved and written into the PREREG before the first registered run. Two things are recorded as post-hoc reviews and do not change pass/fail:
- the balance comparisons against vanilla (C3–C6 controls, E1 solar comparison);
- the council review of late numbers.
