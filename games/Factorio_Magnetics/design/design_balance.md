# Magnetics for Factorio 2.0.77: design document (balance-first, veteran angle)

Author: Claude (design sub-agent). Status: **design proposal, not yet piloted**. Every number below is a spec constant; any number that depends on an undocumented engine semantic is marked **[pilot]** and must be measured and, if needed, retuned *before* the test expectations are registered.

## 0. Citation keys and ground rules

| key | source |
|---|---|
| [C §n] | `scratchpad/recon/crafting.md` |
| [L §n] | `scratchpad/recon/logistics.md` |
| [P §n] | `scratchpad/recon/power.md` |
| [M §n] | `scratchpad/recon/mining.md` |
| [W §n] | `scratchpad/recon/combat.md` |
| [T §n] | `scratchpad/recon/tech.md` |
| [H §n] | `scratchpad/recon/harness.md` |
| [D:file:line] | 2.0.77 game data that I read directly (`/opt/factorio/data/...`) with grep in this session; `B/e` = `base/prototypes/entity/entities.lua`, `B/r` = `base/prototypes/recipe.lua`, `B/i` = `base/prototypes/item.lua`, `SA/bdu` = `space-age/base-data-updates.lua` |

Design rules I applied to myself:
1. **Every building must answer "why would a veteran build this instead of the vanilla thing?"** with a trade-off, not a strictly better number, unless it is an explicit late tier with a late price (Factorio's own AM2→AM3 pattern).
2. **Slot into existing layouts**: same footprint + `next_upgrade` wherever a vanilla analogue exists (drill, belt tier, accumulator, big pole, walls, gate).
3. **No new science packs, no new ores, no vanilla recipe or vanilla tech changes** except: `next_upgrade` links, appended upgrade effects (mirrored, never prepended [W §0.4]), and (Space Age only) extra crafting categories on SA machines.
4. All names start with `magnetics-`. Checked against `fx/names_sa.tsv`: the only hit for "magnetics" is the SA recipe-category `electromagnetics` (substring only), so there are no collisions.
5. The mod never renames a Mindustry feature into a vanilla display name. SA already shows "Superconductor", "Railgun" and "Tesla turret", so ours are "Superconducting wire", "Mass driver" and "Arc emitter".

---

## 1. Concept and progression overview

### 1.1 One-sentence concept
Magnetics adds a **second metallurgy line that runs alongside the vanilla line**: ore + stone → **ferrite** → **coils** → **magnet alloy** → **superconducting wire** → rechargeable **flux crystals**. Each rung unlocks a few buildings that are side-grades or late in-place tiers of vanilla buildings, never replacements.

### 1.2 Mindustry → Factorio mapping (what was kept, changed or dropped)

| Mindustry Magnetics | Factorio Magnetics | why |
|---|---|---|
| ferrite, magnet alloy, coil, superconductor, flux crystal | same 5 materials; superconductor → **superconducting wire** (SA owns "superconductor"); flux crystal → **rechargeable energy cell** (charged/empty pair) | Factorio has no phase fabric. A rechargeable cell is a native mechanic (fuel item + `burnt_result`, like `uranium-fuel-cell` → depleted [P §9.2]) |
| cryofluid | **cryo coolant** (fluid, water + petroleum gas) | base has no cryogenic fluid; one new fluid gives pipes a job |
| kiln, induction furnace, coil winder, cryo chamber, flux resonator, magnetic separator | all 6 kept; each is the only (base) machine for its recipe category, and SA machines get the same categories as the SA-native "X-or-Y" upgrade path [C §12] | a specialised machine for a process is how vanilla does chemistry and centrifuging |
| magnetic drill | 3×3 **in-place upgrade** of the electric mining drill | same footprint, next_upgrade |
| mag conveyor, junction, router, bridge | **maglev belt, underground belt, splitter** (75 items/s) | Factorio has no junctions or routers; the belt tier family is belt + UG + splitter [L §3] |
| coil battery 1×1, superconducting battery 3×3 | **coil capacitor** 1×1 (high flow, low capacity) + **superconducting accumulator** 2×2 (upgrade of accumulator) | two distinct niches: burst flow and storage density |
| superconducting node | **superconducting pylon** 2×2, upgrade of big electric pole (reach 48) | transmission line niche |
| MHD generator | burner-generator, chemical fuel → electricity, no water | compact fuel power |
| flux reactor/dynamo | **flux dynamo**: burns charged flux crystals | portable, pollution-free power |
| ferrite/magnet/superconducting walls (1×1 + 2×2) | 3 walls, 1×1 only, chained by `next_upgrade`, + **magnet gate** | Factorio walls are 1×1 [W §11.2]; a wall tier without a gate leaves a weak spot |
| mend projector | **mend coil** (script, UPS-bounded, powered) | no native building heal in Factorio |
| magnetic shield (dome) | **dropped as a building**; the "field" becomes damage reflection on magnet/superconducting walls and the gate via the native `attack_reaction` | Factorio has no building shields; base ships the reflection code commented out on the stone wall [D:B/e:3383-3410] |
| coilgun, gauss, arc, railgun | **coilgun turret, gauss turret, arc emitter, mass driver** | kinetic (new ammo category), energy chain, directional line gun |
| maglev flak, air units, unit factory | **dropped** | no air enemies in base or on SA planets; flak and air units are not Factorio-native |

### 1.3 Where it sits in a normal playthrough (vanilla techs it hangs on)

| stage (packs) | Magnetics content | hangs on (vanilla tech, [T §3]) |
|---|---|---|
| red (A) | sintering kiln, ferrite | `automation-science-pack` |
| green (A+L) | coil winder, coils; coilgun turret, ferrite slugs, ferrite wall; coil capacitor | `logistic-science-pack`, `military-2`, `stone-wall`, `electric-energy-accumulators` |
| blue (A+L+C) | induction furnace, magnet alloy; magnetic drill; MHD generator; magnetic separator | `advanced-material-processing-2` (the electric-furnace tech) |
| blue + military (A+L+C+M) | magnet wall, magnet gate, gauss turret, alloy slugs, mend coil; arc emitter | `military-3`, `gate`, `laser-turret` |
| purple (A+L+C+P) | cryo chamber, cryo coolant, superconducting wire; superconducting accumulator + pylon | `production-science-pack`, `electric-energy-distribution-2` |
| yellow (…+U) | flux resonator + flux dynamo + flux crystals; maglev belts; superconducting wall + mass driver | `utility-science-pack`, `logistics-3`, `military-4` (+ SA: `turbo-transport-belt`) |

Base game: Magnetics fills the mid game (green→blue) with side-grades and gives the late game (purple→yellow) three late tiers (belts, accumulators, walls) plus portable power. **The mod adds no new end-game goal and no new science pack.**

### 1.4 Coexistence with Space Age (explicit, per SA building)

| SA content | relation | mechanism |
|---|---|---|
| turbo belt (60/s, Vulcanus, [L §2]) | maglev is tier 5 **after** turbo: recipe consumes turbo items, tech requires `turbo-transport-belt`; `turbo-*.next_upgrade = maglev` | data-updates; SA already sets express→turbo [D:space-age/prototypes/entity/transport-belts.lua:31-33] |
| electromagnetic plant (+50 % productivity [C §1]) | gets `magnetics-winding` (coils, SC wire) | SA-native "specialist machine" path; after Fulgora, coils get +50 % productivity |
| cryogenic plant | gets `magnetics-cryogenics` (coolant, crystal growth) | same pattern |
| foundry (+50 % productivity) | gets `magnetics-sintering` and `magnetics-induction` | same pattern |
| tesla turret (range 30, 120/hit, 10 jumps, stun [W §5.5, §9]) | arc emitter is the **pre-Fulgora, weaker** chain turret (range 18, 3 jumps, no stun) | no stun sticker, lower numbers |
| railgun turret (range 40, 10 000 line damage, 10 MJ/shot [W §5.4, §6.4]) | mass driver is the **pre-Aquilo, weaker** line gun (range 36, 1200 line damage) | electric only, no ammo item |
| big mining drill (5×5, speed 2.5, 13×13, 50 % drain [M §1]) | magnetic drill (3×3, speed 0.75, 5×5) is the Nauvis in-place tier; the big drill stays the best drill | no `hard-solid` category |
| heating tower / fusion | flux dynamo is **not** a generation source (80 % round trip); it moves energy | see §7.4 |
| `superconductor` item (SA) | unrelated to our wire; no cross recipes | distinct name and icon |
| surface properties | MHD needs pressure ≥ 10 (like the boiler); kiln needs pressure ≥ 10 (like the stone furnace); the stone-separation recipe needs magnetic-field ≥ 50 (Nauvis 90, Fulgora 99; not Gleba, Vulcanus, Aquilo or platforms [P §11.6]) | `surface_conditions` added **only if `mods["space-age"]`** (API: "Requires Space Age" [C §10.4]) |
| freezing (Aquilo) | `heating_energy` copied from each vanilla analogue (table §4) | guarded by `feature_flags.freezing` [W §0.6] |
| quality | all machines take quality normally, except the flux resonator, which is quality-locked (§7.4) | data-final-fixes |

---

## 2. Items and fluids

New item subgroup `magnetics-intermediate` (group `intermediate-products`, order `gm`, i.e. right after vanilla `intermediate-product` = `g` [T §6]). Placeable items go into **vanilla subgroups** next to their vanilla analogue. Veteran UX: you find the maglev belt next to the turbo belt, not in a separate tab.

### 2.1 Non-placeable items and fluid

| name | type | stack | subgroup / order | use |
|---|---|---|---|---|
| `magnetics-ferrite` | item | 100 (like plates [D:B/i:143]) | magnetics-intermediate / `a[ferrite]` | coils, alloy, ferrite wall, slugs, coil winder, coilgun |
| `magnetics-coil` | item | 200 (like circuits [D:B/i:206]) | `b[coil]` | nearly every Magnetics building, capacitor, MHD |
| `magnetics-magnet-alloy` | item | 100 | `c[magnet-alloy]` | SC wire, walls, gauss, drill, maglev, cryo chamber |
| `magnetics-superconducting-wire` | item | 200 | `d[superconducting-wire]` | late tier: accumulator, pylon, maglev, flux, SC wall, mass driver |
| `magnetics-flux-crystal-empty` | item | 20 | `e[flux-crystal-empty]` | charged in the flux resonator; returned by the flux dynamo as `burnt_result` |
| `magnetics-flux-crystal` | item, `fuel_category = "magnetics-flux"`, `fuel_value = "100MJ"`, `burnt_result = "magnetics-flux-crystal-empty"`, `auto_recycle = false` | 20 (same as rocket fuel, 100 MJ each [D:B/i:788], [P §9.2]) | `f[flux-crystal]` | fuel for the flux dynamo only (own fuel category, so it cannot go into boilers or locomotives) |
| `magnetics-cryo-coolant` | fluid (`default_temperature = -150`, `max_temperature = 0`, base colour #BDEBFF, flow colour #FFFFFF) | — | `fluid` / `z[magnetics-cryo-coolant]` | SC wire, flux crystal growth |
| `magnetics-ferrite-slug` | ammo, category `magnetics-slug`, `magazine_size = 10` | 100 (like magazines [D:B/i:4066]) | `ammo` / `m[magnetics]-a[ferrite-slug]` | coilgun and gauss turrets |
| `magnetics-alloy-slug` | ammo, category `magnetics-slug`, `magazine_size = 10` | 100 | `ammo` / `m[magnetics]-b[alloy-slug]` | coilgun and gauss turrets |

### 2.2 Placeable items (item name = entity name, `place_result` = same; required for quality recycling names [T §5.4])

| item | stack | subgroup / order |
|---|---|---|
| magnetics-sintering-kiln | 50 | smelting-machine / `a[stone-furnace]-m[magnetics-sintering-kiln]` |
| magnetics-induction-furnace | 50 | smelting-machine / `c[electric-furnace]-m[magnetics-induction-furnace]` |
| magnetics-coil-winder | 50 | production-machine / `m[magnetics]-a[coil-winder]` (after `h[cryogenic-plant]`, before `z[lab]`) |
| magnetics-cryo-chamber | 10 (like chemical plant [D:B/i:1973]) | production-machine / `m[magnetics]-b[cryo-chamber]` |
| magnetics-flux-resonator | 20 | production-machine / `m[magnetics]-c[flux-resonator]` |
| magnetics-magnetic-separator | 50 | production-machine / `m[magnetics]-d[magnetic-separator]` |
| magnetics-magnetic-drill | 50 | extraction-machine / `a[items]-b[electric-mining-drill]-m` (between electric and big drill) |
| magnetics-maglev-transport-belt | 100 | belt / `a[transport-belt]-e[magnetics-maglev-transport-belt]` (after turbo `d` [T §10.3]) |
| magnetics-maglev-underground-belt | 50 | belt / `b[underground-belt]-e[...]` |
| magnetics-maglev-splitter | 50 | belt / `c[splitter]-e[...]` |
| magnetics-coil-capacitor | 50 | energy / `e[accumulator]-b[magnetics-coil-capacitor]` |
| magnetics-superconducting-accumulator | 50 | energy / `e[accumulator]-c[magnetics-superconducting-accumulator]` |
| magnetics-superconducting-pylon | 50 | energy-pipe-distribution / `a[energy]-c[big-electric-pole]-m` |
| magnetics-mhd-generator | 10 (like steam turbine [D:B/i:2372]) | energy / `b[steam-power]-c[magnetics-mhd-generator]` |
| magnetics-flux-dynamo | 10 | energy / `h[magnetics-flux]-a[flux-dynamo]` |
| magnetics-ferrite-wall | 100 (like stone wall) | defensive-structure / `a[stone-wall]-b[magnetics-ferrite-wall]` |
| magnetics-magnet-wall | 100 | defensive-structure / `a[stone-wall]-c[magnetics-magnet-wall]` |
| magnetics-superconducting-wall | 100 | defensive-structure / `a[stone-wall]-d[magnetics-superconducting-wall]` |
| magnetics-magnet-gate | 50 (like gate) | defensive-structure / `a[wall]-c[magnetics-magnet-gate]` |
| magnetics-mend-coil | 20 | defensive-structure / `e[magnetics-mend-coil]` |
| magnetics-coilgun-turret | 50 | turret / `b[turret]-m[magnetics]-a[coilgun]` |
| magnetics-gauss-turret | 50 | turret / `b[turret]-m[magnetics]-b[gauss]` |
| magnetics-arc-emitter | 50 | turret / `b[turret]-m[magnetics]-c[arc-emitter]` |
| magnetics-mass-driver | 10 | turret / `b[turret]-m[magnetics]-d[mass-driver]` |

**Content count:** 24 buildings + 9 non-placeable items/fluid = **33 content objects** (57 prototypes if each building's item is counted separately). Hidden helpers: 2 projectiles, 2 beams, 1 chain trigger, 1 explosion (mass-driver trail), 6 recipe categories, 1 fuel category, 2 ammo categories, 1 item subgroup, 15 technologies.

---

## 3. Recipes

New recipe categories: `magnetics-sintering`, `magnetics-induction`, `magnetics-winding`, `magnetics-cryogenics`, `magnetics-resonance`, `magnetics-separation`.

Machine → categories. Base game: kiln {sintering}; induction furnace {sintering, induction}; coil winder {winding}; cryo chamber {cryogenics}; flux resonator {resonance}; separator {separation}. **Space Age only, inserted in data-updates.lua** (SA overwrites vanilla category lists with `=` inside its own data.lua [C §3]): electromagnetic-plant += winding; cryogenic-plant += cryogenics; foundry += sintering and induction.

Unless stated otherwise, `enabled = false` (unlocked by a tech).

### 3.1 Intermediates

| recipe | category | ingredients | results | energy_required (s) | productivity | notes |
|---|---|---|---|---|---|---|
| magnetics-ferrite | sintering | iron-ore 1, stone 1 | ferrite 1 | 3.2 (= iron plate [C §11.2]) | yes | `auto_recycle = false` (smelting-like, as vanilla skips smelting [C §11.3]) |
| magnetics-coil | winding | ferrite 1, copper-cable 4 | coil 1 | 2 | yes | |
| magnetics-magnet-alloy | induction | steel-plate 1, ferrite 2, copper-plate 1 | magnet-alloy 1 | 6.4 | yes | `auto_recycle = false` |
| magnetics-cryo-coolant | cryogenics | water 40, petroleum-gas 10 | cryo-coolant 40 | 2 | yes | `auto_recycle = false` |
| magnetics-superconducting-wire | winding | magnet-alloy 1, copper-cable 6, plastic-bar 1, cryo-coolant 20 | superconducting-wire 2 | 10 | yes | fluid via the winder's AM2 fluid boxes |
| magnetics-flux-crystal-growth | cryogenics | superconducting-wire 2, processing-unit 1, cryo-coolant 50 | flux-crystal-empty 1 | 20 | yes | the crystal is a reusable catalyst |
| magnetics-flux-crystal-charging | resonance | flux-crystal-empty 1 | flux-crystal 1 | 25 | **no** | `allow_quality = false`, `auto_recycle = false`; energy lock §7.4 |
| magnetics-stone-separation | separation | stone 10 | iron-ore 2; copper-ore 1 with `probability = 0.5` | 5 | yes | multi-product → own `icon`, `subgroup = magnetics-intermediate`, `order = z[stone-separation]` [C §11.2]; `auto_recycle = false`; SA: `surface_conditions = {{property="magnetic-field", min=50}}` |
| magnetics-ferrite-slug | crafting | ferrite 3, copper-plate 1 | ferrite-slug 1 | 3 | no | vanilla ammo has no productivity |
| magnetics-alloy-slug | crafting | ferrite-slug 1, magnet-alloy 1 | alloy-slug 1 | 5 | no | |

### 3.2 Buildings (category `crafting` = hand- and assembler-craftable, unless stated)

| recipe → 1 item | ingredients | energy (s) |
|---|---|---|
| magnetics-sintering-kiln | stone-furnace 1, iron-gear-wheel 2, stone-brick 5 | 2 |
| magnetics-induction-furnace | steel-plate 10, advanced-circuit 5, stone-brick 10, coil 10 (the electric furnace recipe [D:B/r:2244] + 10 coils) | 5 |
| magnetics-coil-winder | assembling-machine-1 1, iron-gear-wheel 5, electronic-circuit 5, ferrite 10 | 2 |
| magnetics-cryo-chamber | chemical-plant 1, magnet-alloy 10, coil 10, pipe 10 | 5 |
| magnetics-flux-resonator | centrifuge 1, superconducting-wire 50, processing-unit 20 | 10 |
| magnetics-magnetic-separator | steel-plate 10, magnet-alloy 10, coil 20, electronic-circuit 10 | 5 |
| magnetics-magnetic-drill | electric-mining-drill 1, magnet-alloy 5, coil 5, advanced-circuit 2 | 2 |
| magnetics-maglev-transport-belt (`crafting-with-fluid`) | **base:** express-transport-belt 1, superconducting-wire 1, magnet-alloy 1, lubricant 20. **SA:** turbo-transport-belt 1 instead of express | 0.5 |
| magnetics-maglev-underground-belt (`crafting-with-fluid`) → **2** | **base:** express-underground-belt 2, magnet-alloy 20, superconducting-wire 10, lubricant 40. **SA:** turbo-underground-belt 2 | 2 |
| magnetics-maglev-splitter (`crafting-with-fluid`) | **base:** express-splitter 1, superconducting-wire 5, magnet-alloy 10, processing-unit 2, lubricant 80. **SA:** turbo-splitter 1 | 2 |
| magnetics-coil-capacitor | coil 5, steel-plate 2, electronic-circuit 2 | 5 |
| magnetics-superconducting-accumulator | accumulator 1, superconducting-wire 10, magnet-alloy 5 | 10 |
| magnetics-superconducting-pylon | big-electric-pole 1, superconducting-wire 2, steel-plate 2 | 1 |
| magnetics-mhd-generator | steel-plate 20, coil 20, magnet-alloy 10, advanced-circuit 10 | 10 |
| magnetics-flux-dynamo | steel-plate 20, superconducting-wire 20, coil 20, processing-unit 10 | 10 |
| magnetics-ferrite-wall | ferrite 6 | 0.5 |
| magnetics-magnet-wall | ferrite-wall 1, magnet-alloy 1, steel-plate 1 | 1 |
| magnetics-superconducting-wall | magnet-wall 1, superconducting-wire 1, refined-concrete 4 | 2 |
| magnetics-magnet-gate | magnet-wall 1, steel-plate 2, electronic-circuit 2 (mirrors gate = stone-wall 1 + steel 2 + EC 2 [D:B/r:1208]) | 0.5 |
| magnetics-mend-coil | steel-plate 10, coil 20, repair-pack 10, advanced-circuit 5 | 10 |
| magnetics-coilgun-turret | iron-gear-wheel 10, coil 10, ferrite 20, electronic-circuit 5 | 8 (= gun turret [D:B/r:685]) |
| magnetics-gauss-turret | steel-plate 20, magnet-alloy 10, coil 20, advanced-circuit 10 | 20 |
| magnetics-arc-emitter | steel-plate 20, coil 30, battery 10, advanced-circuit 10 (compare laser turret = steel 20, EC 20, battery 12 [D:B/r:644]) | 20 |
| magnetics-mass-driver | steel-plate 50, magnet-alloy 30, superconducting-wire 30, processing-unit 20, coil 30 | 30 |

Building recipes do not allow productivity (vanilla default). Quality recycling is generated normally for them (quality mod [C §11.3]).

### 3.3 Chain ratios (for players and tests; derived from §3.1 and §4)
- 1 kiln = 0.3125 ferrite/s, the same as a stone furnace on iron plates.
- 1 winder on coils = 0.5 coil/s. It needs 0.5 ferrite/s (1.6 kilns or 0.8 induction furnaces) and 2 cable/s.
- 1 induction furnace on alloy = 0.3125 alloy/s. It needs 0.625 ferrite/s (**exactly 1 more induction furnace on ferrite**), 0.3125 steel/s (2.5 electric furnaces) and 0.3125 copper/s.
- 1 winder on SC wire = 0.2 wire/s. It needs 0.1 alloy/s and 2 coolant/s; 1 cryo chamber (20 coolant/s) feeds 10 such winders.

---

## 4. Entities

Graphics rule: a deepcopy of the vanilla base, with `tint` put on every sprite **leaf** that is not `draw_as_shadow`, `draw_as_glow` or `draw_as_light`, and with recipe-tinted working visualisations skipped (walker from [C §10.3]). **Do not use `util.recursive_tint`**: it also tints shadows and icons [C §10.1]. Belt animation sets must be deep-copied before tinting (a shared table would recolour vanilla express [L §0]). Corpses and dying explosions keep the vanilla names [C §2.13]. All icons are our own PNGs (§8.9).

"type conv." means the prototype is built as a **fresh prototype of the new type**. Only `graphics_set` / animations, boxes, sounds, corpse, explosion and circuit connector are copied from the vanilla entity; type-specific fields such as furnace inventory sizes are not. This is a **[pilot]** load check (risk R1).

| entity | type | vanilla base (art) | size | key stats | next_upgrade (into / from) | tint (r,g,b) | SA heating_energy |
|---|---|---|---|---|---|---|---|
| magnetics-sintering-kiln | assembling-machine (type conv.) | stone-furnace | 2×2 | speed 1; burner `{chemical}`, 90 kW, fuel slots 1; pollution 2/min; modules 0; `fixed_recipe = magnetics-ferrite`; HP 200; FRG `magnetics-sintering-kiln`; SA: pressure ≥ 10 | — | 0.75, 0.62, 0.66 | none (stone furnace has none [D:SA/bdu:86]) |
| magnetics-induction-furnace | assembling-machine (type conv.) | electric-furnace | 3×3 | speed 2; 240 kW electric; pollution 1/min; modules 2 (5 effects); HP 350 | — | 0.62, 0.72, 1.0 | 100 kW (= electric furnace [D:SA/bdu:88]) |
| magnetics-coil-winder | assembling-machine | assembling-machine-2 (fluid boxes kept) | 3×3 | speed 1; 150 kW; pollution 3/min; modules 2; HP 350; FRG `magnetics-coil-winder` | — | 1.0, 0.72, 0.5 | 100 kW (AM2) |
| magnetics-cryo-chamber | assembling-machine | chemical-plant (fluid boxes kept, recipe-tint layers untouched) | 3×3 | speed 1; 300 kW; pollution 3/min; modules 3; HP 350 | — | 0.7, 0.95, 1.0 | **0** (a cold machine; the only deliberate deviation) |
| magnetics-flux-resonator | assembling-machine | centrifuge | 3×3 | speed 1, **quality-locked**; 5 MW, drain 10 kW; pollution 0; modules 0; `effect_receiver = {uses_module_effects=false, uses_beacon_effects=false, uses_surface_effects=false}`; HP 350 | — | 0.82, 0.64, 1.0 | 100 kW (centrifuge) |
| magnetics-magnetic-separator | assembling-machine | assembling-machine-3 | 3×3 | speed 1; 200 kW; pollution 4/min; modules 2; HP 350 | — | 0.72, 0.8, 0.9 | 100 kW (AM3) |
| magnetics-magnetic-drill | mining-drill | electric-mining-drill | 3×3 | mining_speed 0.75; 150 kW; pollution 15/min; modules 3; `resource_searching_radius` 2.49 (5×5); `input_fluid_box` kept (uranium); `resource_categories = {"basic-solid"}`; HP 400; FRG `mining-drill` | **from** electric-mining-drill | 0.6, 0.72, 1.0 | 100 kW (EMD [D:SA/bdu:120]) |
| magnetics-maglev-transport-belt | transport-belt | express-transport-belt | 1×1 | speed 0.15625 (= 40/256 → 75 items/s [L §2]); HP 180; fire 50 %; `animation_speed_coefficient` 32; FRG `transport-belt`; related UG = maglev UG | **from** express (base) / turbo (SA) | 0.55, 0.9, 1.0 | 10 kW |
| magnetics-maglev-underground-belt | underground-belt | express-underground-belt | 1×1 | same speed; `max_distance` 13 (vanilla 5/7/9/11 → +2 [L §3.2]); HP 180; fire 60 / impact 30 | **from** express UG / turbo UG | same | 250 kW (50/100/150/200 → +50) |
| magnetics-maglev-splitter | splitter | express-splitter | 2×1 | same speed; HP 200; `related_transport_belt` = maglev belt | **from** express / turbo splitter | same | 40 kW |
| magnetics-coil-capacitor | accumulator | accumulator via global `accumulator_picture(tint)` [P §4], every leaf `scale` and `shift` × 0.5 | 1×1 | buffer 1 MJ; in/out 1 MW; `tertiary`; HP 100; no circuit connector; FRG `magnetics-coil-capacitor` | — | 1.0, 0.75, 0.55 | none (accumulator has none) |
| magnetics-superconducting-accumulator | accumulator | accumulator | 2×2 | buffer 20 MJ; in/out 1.2 MW (same 16.7 s full-discharge time as vanilla's 5 MJ / 300 kW); HP 250; FRG `accumulator` | **from** accumulator | 0.65, 0.95, 1.0 | none |
| magnetics-superconducting-pylon | electric-pole | big-electric-pole (collision mask with `elevated_rail` kept [P §1]) | 2×2 | `maximum_wire_distance` 48; `supply_area_distance` 2; HP 250; FRG `big-electric-pole` | **from** big-electric-pole | 0.65, 0.95, 1.0 | none |
| magnetics-mhd-generator | burner-generator | base hidden `burner-generator` [D:B/e:9945-9993], animations replaced by steam-turbine horizontal/vertical | 3×5 | `max_power_output` 5 MW; burner `{chemical}`, effectivity 0.9, fuel slots 2; pollution 90/min; `hidden = false`; HP 400; SA: pressure ≥ 10 (like the boiler [P §11.5]) | — | 1.0, 0.6, 0.45 | 50 kW (= steam engine) |
| magnetics-flux-dynamo | burner-generator | base hidden `burner-generator` (steam-engine art) | 3×5 | `max_power_output` 10 MW; burner `{magnetics-flux}`, effectivity 1.0, fuel 1, **burnt 1**; pollution 0; HP 500 | — | 0.8, 0.6, 1.0 | 50 kW |
| magnetics-ferrite-wall | wall | stone-wall | 1×1 | HP 500; res.: physical 3/25 %, impact 45/60 %, explosion 10/30 %, fire 100 %, acid 85 %, laser 70 %; FRG `wall`; `visual_merge_group` 0 | **from** stone-wall; **to** magnet wall | 0.62, 0.55, 0.6 | — |
| magnetics-magnet-wall | wall | stone-wall | 1×1 | HP 800; physical 5/30 %, impact 50/65 %, explosion 15/35 %, fire 100, acid 85, laser 75, electric 50 %; `attack_reaction` = {range 2, damage_type physical, reaction_modifier 0.2, damage 5 electric} **[pilot]** | **to** SC wall | 0.6, 0.7, 1.0 | — |
| magnetics-superconducting-wall | wall | stone-wall | 1×1 | HP 1500; physical 8/35 %, impact 60/70 %, explosion 20/40 %, fire 100, acid 90, laser 90, electric 100 %; `attack_reaction` {range 2, physical, modifier 0.4, damage 10 electric} | — | 0.7, 0.95, 1.0 | — |
| magnetics-magnet-gate | gate | gate | 1×1 | HP 800; resistances and reflection = magnet wall; FRG `wall` | **from** gate | 0.6, 0.7, 1.0 | — |
| magnetics-mend-coil | electric-energy-interface | lab (`on_animation` [D:B/e:3830]) | 3×3 | `energy_usage` 0, `energy_production` 0; buffer 1 MJ, input 200 kW, `secondary-input`; `gui_mode = "none"`; script heal (§6); HP 300 | — | 0.6, 1.0, 0.7 | 50 kW |
| magnetics-coilgun-turret | ammo-turret | gun-turret | 2×2 | range 20; cooldown 30 ticks (2 shots/s); `energy_per_shot` 50 kJ, energy source {primary-input, buffer 200 kJ, input 300 kW, drain 5 kW}; `inventory_size` 1, `automated_ammo_count` 10; category `magnetics-slug`; damage_modifier 1; HP 500; FRG `ammo-turret` | — | 1.0, 0.7, 0.5 | 50 kW (= gun turret [D:SA/bdu:128]) |
| magnetics-gauss-turret | ammo-turret (type conv.) | laser-turret | 2×2 | range 32; cooldown 60 (1 shot/s); `damage_modifier` 3 **[pilot]**; `energy_per_shot` 300 kJ, buffer 1.2 MJ, input 1.5 MW, drain 10 kW; category `magnetics-slug`; HP 1200 | — | 0.55, 0.65, 1.0 | 50 kW |
| magnetics-arc-emitter | electric-turret | laser-turret | 2×2 | range 18; cooldown 60; category `magnetics-arc`; `ammo_type.energy_consumption` 600 kJ; buffer 1.8 MJ, input 3 MW, drain 20 kW; hit 25 electric + chain 3 jumps × 6 tiles × 15 electric **[pilot]**; no stun; HP 1000 | — | 0.6, 0.95, 1.0 | 50 kW (= laser [D:SA/bdu:129]) |
| magnetics-mass-driver | electric-turret (type conv.) | flamethrower-turret (2×3, `turret_base_has_direction = true`) | 2×3 | range 36, min_range 5, `turn_range` 1/3 (= flamethrower [D:base/prototypes/entity/fire.lua:626]); cooldown 150 (0.4 shots/s); built-in `ammo_type` {target_type direction, line range 36, width 1.5, `force = "enemy"`, 1200 physical}; `energy_consumption` 8 MJ; buffer 8 MJ, input 4 MW, drain 50 kW; category `magnetics-slug`; HP 2000 | — | 0.75, 0.55, 1.0 | 100 kW |

Hidden helper prototypes:
- `magnetics-ferrite-slug-projectile`: a copy of `cannon-projectile` [W §7], with `direction_only = true`, `piercing_damage = 30`, action 15 physical, `force_condition = "not-same"` (turrets behind walls must not shoot their own walls), tinted `bullet.png`.
- `magnetics-alloy-slug-projectile`: the same, `piercing_damage = 150`, 40 physical.
- Slug ammo_type: `{target_type = "direction", action = projectile, starting_speed = 1, direction_deviation = 0.02, range_deviation = 0.02, max_range = 40}`.
- `magnetics-arc-beam` and `magnetics-arc-bounce-beam`: built with base's **global** `make_electric_beam(name, sound, damage)` [D:base/prototypes/entity/beams.lua:372-413] (damage 25 / 15 electric; set `action_triggered_automatically = true` and delivery `duration = damage_interval = 20`, so each beam hits once **[pilot]**).
- `magnetics-arc-chain`: `chain-active-trigger` with `max_jumps = 3`, `max_range_per_jump = 6`, `jump_delay_ticks = 6`, `fork_chance = 0` (structure copied from SA's `make_tesla_chain_lightning_chain` [W §9]; the type is core, not SA).
- The arc emitter's ammo_type follows the tesla-turret layout (instant → nested chain first, then nested beam [W §5.5, §9]).
- `magnetics-mass-driver-trail`: explosion with `rotate = true, beam = true` (the pattern of SA's `railgun-beam` [W §10]), animation = our **procedurally drawn** 64×440 additive glow strip. This is the only new world sprite; it is justified because the base game has no line-beam sprite and a gradient strip needs no hand painting.

Categories: `ammo-category` `magnetics-slug` and `magnetics-arc`, each with `bonus_gui_order` set and our own 64 px icon [W §2.1]; `fuel-category` `magnetics-flux` [P §9.3].

---

## 5. Technologies (15)

Packs: A = automation, L = logistic, M = military, C = chemical, P = production, U = utility, S = space, Met = metallurgic. Every prerequisite listed exists in all four configurations (base, +quality, +elevated-rails, full SA) [T §3]. `turbo-transport-belt` is added only when SA is active.

| # | tech | prerequisites | count × time | packs | unlocks (recipes) |
|---|---|---|---|---|---|
| 1 | magnetics-ferrite-sintering | automation-science-pack | 30 × 10 s | A | sintering-kiln, ferrite |
| 2 | magnetics-coils | magnetics-ferrite-sintering, logistic-science-pack | 75 × 15 s | A L | coil-winder, coil |
| 3 | magnetics-defense-1 ("Magnetic defense") | magnetics-coils, military-2, stone-wall | 100 × 15 s | A L | ferrite-wall, coilgun-turret, ferrite-slug |
| 4 | magnetics-coil-capacitor | magnetics-coils, electric-energy-accumulators | 150 × 30 s | A L | coil-capacitor |
| 5 | magnetics-induction-smelting | magnetics-coils, advanced-material-processing-2 | 250 × 30 s | A L C | induction-furnace, magnet-alloy |
| 6 | magnetics-magnetic-mining | magnetics-induction-smelting | 250 × 30 s | A L C | magnetic-drill |
| 7 | magnetics-mhd-generator | magnetics-induction-smelting | 200 × 30 s | A L C | mhd-generator |
| 8 | magnetics-magnetic-separation | magnetics-induction-smelting | 150 × 30 s | A L C | magnetic-separator, stone-separation |
| 9 | magnetics-defense-2 ("Magnetic fortifications") | magnetics-defense-1, magnetics-induction-smelting, military-3, gate | 200 × 30 s | A L C M | magnet-wall, magnet-gate, gauss-turret, alloy-slug, mend-coil |
| 10 | magnetics-arc-emitter | magnetics-coils, laser-turret | 200 × 30 s | A L C M | arc-emitter |
| 11 | magnetics-cryogenics | magnetics-induction-smelting, production-science-pack | 300 × 30 s | A L C P | cryo-chamber, cryo-coolant, superconducting-wire |
| 12 | magnetics-superconducting-power | magnetics-cryogenics, electric-energy-distribution-2 | 300 × 30 s | A L C P | superconducting-accumulator, superconducting-pylon |
| 13 | magnetics-flux-energy | magnetics-superconducting-power, utility-science-pack | 500 × 30 s | A L C P U | flux-resonator, flux-dynamo, flux-crystal-growth, flux-crystal-charging |
| 14 | magnetics-maglev-logistics | **base:** logistics-3, magnetics-cryogenics, utility-science-pack. **SA:** + turbo-transport-belt | **base:** 600 × 30 s. **SA:** 1000 × 60 s | **base:** A L C P U. **SA:** A L C P U S Met | maglev belt, UG, splitter |
| 15 | magnetics-defense-3 ("Superconducting defense") | magnetics-defense-2, magnetics-cryogenics, military-4 | 500 × 45 s | A L C M P U | superconducting-wall, mass-driver |

Anchors [T §3]:
- #1 sits between electric-mining-drill (25×10 A) and steel-processing (50×5 A).
- #2 is next to automation-2 (40×15 A L).
- #4 mirrors electric-energy-accumulators (150×30 A L).
- #5 mirrors advanced-material-processing-2 (250×30 A L C).
- #10 is next to laser-turret (150×30 A L M C).
- #14 SA mirrors turbo-transport-belt (500×60 A L C P S Met) ×2.
- #15 is next to military-4 (150×45).

**Upgrade effects: no new upgrade techs.** In **data-final-fixes.lua**, i.e. after SA's in-place edits [W §0.4, §14.3]:
- For every tech effect `{type="ammo-damage"|"gun-speed", ammo_category="bullet"}`, **append** a copy with `ammo_category="magnetics-slug"`. This covers physical-projectile-damage-1..7 and weapon-shooting-speed-1..6. Under SA the copied -6/-7 values are SA's 0.2.
- For every effect with `ammo_category="laser"`, append a copy for `magnetics-arc` (laser-weapons-damage-1..7, laser-shooting-speed-1..7).
- Result: slug and arc weapons scale exactly like bullets and lasers in each configuration, including the infinite levels.

Tech icons: 256 px PNG with `icon_size = 256` [T §7].

---

## 6. Control-script features

Only **one** script feature: the mend coil. Everything else is pure prototype data.

### 6.1 Mend coil algorithm
- **State (`storage.mend`)**: `list` (an array of `{entity, unit_number, last_tick}`), `index` (unit_number → array slot) and `cursor` (the ring-buffer position).
- **Registration**:
  - Events: `on_built_entity`, `on_robot_built_entity`, `on_space_platform_built_entity` (present in the 2.0 API; harmless without SA), `script_raised_built`, `script_raised_revive` and `on_entity_cloned`, all with the event filter `{filter="name", name="magnetics-mend-coil"}`.
  - Removal: lazy. An invalid entity found during processing is swap-removed. `script.register_on_object_destroyed` handles eager cleanup.
  - `on_init` and `on_configuration_changed` rebuild the list by scanning `find_entities_filtered{name="magnetics-mend-coil"}` on every surface.
- **Tick**: `script.on_nth_tick(30, step)`. Each call processes at most **25 coils** from the cursor, so a base with 100 coils visits each coil every 120 ticks. Per coil:
  1. `dt = min(game.tick - last_tick, 600)`; set `last_tick = game.tick`.
  2. `pool = 20 HP/s × dt/60`, `cap = 10 HP/s × dt/60` per target, `pool = min(pool, floor(entity.energy / 5000))` (**5 kJ per HP**).
  3. `targets = surface.find_entities_filtered{position = coil.position, radius = 10, force = coil.force, type = HEAL_TYPES}`, where `HEAL_TYPES = {"wall","gate","ammo-turret","electric-turret","fluid-turret","artillery-turret","radar"}`.
  4. For each target in returned order with `health < max_health`: `h = min(max_health - health, cap, pool)`; `target.health += h`; `pool -= h`; `spent += h`; stop when `pool <= 0`.
  5. `entity.energy -= spent × 5000`.
- **Numbers**: radius 10, pool 20 HP/s, per-target 10 HP/s, 5 kJ/HP. A fully busy coil draws 100 kW; the buffer holds 1 MJ = 200 HP of reserve and refills at 200 kW.
- **UPS cost**: at most 25 radius-10 area queries per 30 ticks (≤ 50 queries/s total, **independent of coil count**), plus a Lua loop over the returned entities. Idle coils (nothing damaged) cost one query each. Design budget: **< 0.05 ms/tick** with 200 coils and fully damaged walls; measured in the test.
- **Multiplayer determinism**: all state is in `storage`; there is no `math.random`, no player-local data and no state change in `on_load`; iteration is over an array and the engine-ordered query results; the handler is registered unconditionally in the control-stage main chunk.
- **Test**: §8.7.

### 6.2 Deliberately *not* scripted
Walls reflect damage through the native `attack_reaction` (a prototype field [D: prototype-api EntityWithHealthPrototype.attack_reaction]; base ships the example commented out [D:B/e:3383-3410]). The flux loop, turrets, drill and belts are pure data.

---

## 7. Balance justification

### 7.1 Materials and machines
- **Ferrite (1 ore + 1 stone, 3.2 s)**: the same time as an iron plate [C §11.2], so a kiln column has the same throughput as a stone-furnace column. It adds a *second* ore to the metal line, which gives stone a use in the mid game, and it costs 1 iron ore, so it never becomes free iron.
  - The kiln is a burner machine with speed 1 and 90 kW, exactly the stone furnace [C §1]. Its niche: the only red/green-era source of ferrite. It needs a mixed ore/stone lane plus fuel, a small logistics puzzle that fits the early game.
  - The induction furnace (speed 2, 2 modules) is the electric-furnace analogue [C §1], at 240 kW instead of 180 kW because it also alloys.
- **Coil (1 ferrite + 4 cable, 2 s)** ≈ 1 Fe-ore + 1 stone + 2 Cu, slightly above an electronic circuit (1 Fe + 1.5 Cu [D:B/r:751]). That fits a green-tier intermediate.
  - The winder (speed 1, 150 kW) sits between AM2 (0.75 / 150 kW) and AM3 (1.25 / 375 kW). It is the only machine for winding in base, like the chemical plant for chemistry. It gets no built-in productivity in base, so there is no creep; SA players get +50 % in the EM plant, the SA-intended reward.
- **Magnet alloy (steel 1 + ferrite 2 + Cu 1, 6.4 s)** ≈ 7 Fe + 1 Cu + 2 stone, about the cost of an engine unit (9 Fe [D:B/r:1103]). That is right for a blue-tier gating intermediate. The 1 : 1 : 2.5 machine ratio in §3.3 is intentionally clean.
- **Superconducting wire (2 per craft)** ≈ 3.5 Fe + 2 Cu + 1 stone + 0.5 plastic + 10 coolant per wire. It is the purple-tier bottleneck, with the same role as the processing unit.
- **Cryo chamber (300 kW, 3 modules)**: a chemical-plant sibling (210 kW, 3 modules [C §1]). Its only deviation is heating_energy 0 on Aquilo (thematic, and negligible there).
- **Magnetic separator**: 10 stone → 2 iron ore + 0.5 copper ore per 5 s. Four electric drills on stone (2 stone/s) plus one separator give 0.4 Fe + 0.1 Cu ore/s, **worse than one electric drill on iron (0.5/s [M §1])**. Its niche is purely "stone-rich, iron-poor map / remote patch". SA surface condition (magnetic-field ≥ 50) keeps it off Gleba and Vulcanus, so it cannot bypass Gleba's biological iron chain.

### 7.2 Mining and logistics
- **Magnetic drill**: speed 0.75 = +50 % over the electric drill, same 5×5 area, **in-place upgrade**. Energy 150 kW (EMD 90 kW / 0.5 = 180 kW per unit speed; ours 200 → slightly *less* energy-efficient). Pollution 15/min keeps the vanilla 20/min per unit speed.
  - Why not more: SA's big drill (2.5 speed, 13×13, 50 % drain) must stay the best drill [M §1]. A +50 % tier at blue science is modest next to productivity research.
  - Cost: EMD + 5 alloy + 5 coils + 2 advanced circuits, roughly 3× an EMD.
- **Maglev 75/s**: the next exact step of the vanilla +8/256 progression (15/30/45/60 → 75 [L §0]); UG +2 tiles (13). In **base** it follows express (45 → 75) but sits at **yellow science** with superconducting wire + lubricant, i.e. later than logistics-3 (purple). Under SA it follows turbo (60 → 75) and costs 2× the turbo tech. The speed is identical in both configurations (one spec, one test).

### 7.3 Power
- **Coil capacitor 1×1 (1 MJ, 1 MW)**:
  - Per tile it holds **0.8×** the accumulator's capacity (1 vs 1.25 MJ/tile) but moves **13×** the power (1 MW vs 75 kW/tile [P §1]). Per MJ it costs ≈ 15× an accumulator (5 coils + 2 steel + 2 EC ≈ 17 Fe-eq + 13 Cu per MJ vs 1.4 Fe + 1 Cu + 20 acid per MJ).
  - So it is **useless for solar night storage and good for burst loads**. A laser turret can pull 9.6 MW input [W §5.2]: it needs 32 vanilla accumulators or 10 capacitors to buffer.
- **Superconducting accumulator 2×2 (20 MJ, 1.2 MW)**: 4× capacity with the vanilla full-discharge time kept (16.7 s). It is an in-place upgrade at purple science and costs **more per MJ** than the vanilla accumulator (≈ 3.9 Fe + 1.5 Cu per MJ vs 1.4 Fe + 1 Cu).
  - A solar field gets ~20 % smaller in total area (accumulator area per panel 3.36 → 0.84 tiles at the community 21:25 accumulator:panel ratio — a wiki figure, **not** from recon, used only as an illustration).
  - SA adds no accumulator tier [P §0.3], so nothing is overlapped.
- **Superconducting pylon (reach 48)**: 1.5× the big pole's 32 [P §1]. The cost per tile of line is the same (≈ 0.96 vs 0.9 Fe per tile), so the niche is fewer entities (−33 % poles), not cheaper power.
  - Quality adds +2 reach per level [P §3.1], so a legendary pylon reaches 58, below the API maximum of 64. That is why 48 was chosen and not 60.
- **MHD generator (5 MW, 3×5, effectivity 0.9)**:
  - Boiler + 2 steam engines = 1.8 MW in 36 tiles plus a water supply, at effectivity 1 [D:B/e:1276-1282], [P §6.2]. MHD = 5 MW in 15 tiles (6.7× denser), no water, but it **loses 10 % of the fuel**.
  - Pollution: 90/min, which keeps the boiler's 16.7/min per MW of fuel.
  - Fuel draw: 5 MW / 0.9 = 5.56 MW = 1.39 coal/s or 0.46 solid fuel/s, so it is expensive to run. It suits dense or deathworld bases and water-less spots, and is not better than nuclear (much cheaper fuel) or solar (free fuel).
  - It is far below SA's heating tower (40 MW at 250 % [P §11.4]).
- **Flux dynamo + resonator** (the energy loop):
  - The resonator spends 5 MW × 25 s = **125 MJ** (plus 0.25 MJ drain) per crystal. The crystal gives **100 MJ** in the dynamo, so the round trip is **≤ 80 %**, while vanilla accumulators are lossless.
  - The niche is **transport**: power by train, belt or robot to places poles cannot reach (islands, far outposts, SA platforms/Aquilo), pollution-free at the point of use. One dynamo (10 MW) burns 0.1 crystal/s and needs 2.5 resonators (12.5 MW) behind it.
  - Stack 20 × 100 MJ equals rocket fuel's energy per slot [D:B/i:788]. That is far below uranium fuel cells (8 GJ, stack 50), so it never replaces nuclear logistics.

### 7.4 Energy-loop exploit locks (mandatory)
The flux loop must never yield more energy than it consumes. Hard locks:
- resonator `module_slots = 0`;
- `effect_receiver.uses_module_effects = uses_beacon_effects = uses_surface_effects = false`;
- charging recipe `allow_productivity = false` and `allow_quality = false`;
- resonator `crafting_speed_quality_multiplier[q] = 1` for every quality `q` in `data.raw.quality` (data-final-fixes), so quality raises neither speed per joule nor anything else;
- `quality_affects_energy_usage` stays false;
- charged crystal `auto_recycle = false` and charging recipe `auto_recycle = false`, so no recycler path.

Dynamo quality may raise `max_power_output` but not effectivity, so energy per crystal is invariant. Test §8.5 checks this with a **legendary** resonator.

### 7.5 Defense
Vanilla numbers used below [W §5, §12], [D:base/prototypes/entity/enemy-constants.lua:134-137]:
- gun turret: 10 shots/s, firearm 50 dps, piercing 80 dps, uranium 240 dps, range 18, HP 400;
- laser turret: range 24, 800 kJ/shot every 40 ticks, HP 1000;
- worms: range 25 (small), 30 (medium), 38 (big), 48 (behemoth).

| turret | single-target raw DPS | range | niche vs vanilla | why not creep |
|---|---|---|---|---|
| coilgun | 30 (ferrite slug 15 × 2/s), 80 (alloy 40 × 2/s, blue era) + pierce | 20 | green-era **line** defense with cheap ore-based ammo; vs armoured medium biters (4/10 %) a ferrite slug does (15−4)·0.9 = 9.9/hit vs a firearm's 0.9/hit (flat-then-percent assumed) | green era: 30 dps < gun + piercing mags (80); alloy slugs only match piercing mags one tier later; needs power (50 kJ/shot = 100 kW firing) |
| gauss | 45 (ferrite × 3), 120 (alloy × 3) + pierce | **32** | outranges small and medium worms (25/30), so turret creep against medium nests is possible; below big worms (38) and below SA's rocket turret (36) | 1 shot/s; 300 kJ/shot; artillery (range 224) stays the nest killer |
| arc emitter | 25 single; up to 70 per shot over 4 targets | 18 | swarm control with electric damage, which **no base enemy resists** [W §12]; the base-game stand-in for tesla | range 18 < laser 24; no stun; weaker than tesla (range 30, 120/hit, 10 jumps) |
| mass driver | 480 (1200 per 2.5 s), line pierce | 36 | anti-behemoth lanes (behemoth 3000 HP, phys 12/10 % → 3 shots) | directional (turn_range 1/3); 8 MJ/shot = 3.2 MW sustained; far below SA's railgun (10 000/170 ticks, range 40) |

Slug and arc weapons get **exactly** the vanilla bullet and laser upgrade curves (mirrored effects, §5), so late-game scaling stays aligned with vanilla turrets.

**Walls** (vanilla stone wall: HP 350, 5 bricks = 10 stone, physical 3/20 % [W §11.2]):
- ferrite 500 HP = 6 ferrite (6 ore + 6 stone): HP per raw unit 41.7 vs the stone wall's 35;
- magnet 800 HP;
- superconducting 1500 HP.

Magnet and superconducting walls take the previous tier as an ingredient (as the vanilla gate takes a stone wall [D:B/r:1208]), so walls returned by the upgrade planner are re-crafted into the next tier instead of piling up. Against a behemoth bite (90 dmg): stone takes 69.6/bite (≈ 6 bites to break); superconducting takes 53.3/bite (≈ 29 bites), assuming flat-then-percent resistance (order undocumented [W §1.2]). This is the vanilla late-game gap (behemoths shred walls) closed with a late price (SC wire + refined concrete).

**Reflection**:
- 5 (magnet) or 10 (superconducting) electric per bite + 20–40 % of the received damage **[pilot, formula undocumented]**;
- kills small biters in ~3 bites; is ≈ 1 % of a behemoth per bite;
- flavour-level, not a turret replacement.

**Mend coil**:
- 20 HP/s pool, radius 10, 5 kJ/HP; no robots or repair packs needed, but slow (a magnet wall from 0 to 800 takes 80 s).
- A repair pack is 2 EC + 2 gears [D:B/r:969] with durability 300 [D:B/i:554-563]. The coil is the **between-waves** maintenance niche and does not make walls invulnerable in combat (a single medium biter deals ≈ 26 raw dps).

---

## 8. Risks

- **R1 Type-converted clones and un-previewable art.**
  - What: kiln and induction furnace (furnace art → assembling-machine), gauss (laser → ammo-turret) and mass driver (flamethrower → electric-turret) rely on shared graphics types, which is not documented as supported. The headless build has no vanilla PNGs [C §1 header], so no tinted world sprite can be previewed here.
  - Mitigation: a pilot load in both configs. Fallbacks:
    - mass driver → laser art;
    - gauss → gun-turret art;
    - kiln → electric assembling-machine with AM1 art;
    - induction furnace → AM3 art.
  - Author review: our icon sheet + per-entity "base + tint swatch" cards, then one in-game screenshot requested from the author.
- **R2 Undocumented combat semantics.**
  - What: `damage_modifier` on projectile deliveries, the beam and chain hit timing, the `attack_reaction` formula, and `piercing_damage` accounting are not specified in sources [W §16].
  - Mitigation: the pilot measures per-hit damage and hits per shot, and numbers are retuned before PREREG.
  - Fallbacks: gauss gets its own ammo category (`magnetics-gauss`) with separate slugs; wall reflection is dropped.
- **R3 Energy-loop exploits.** Quality, beacons, efficiency modules, productivity or the recycler could turn the flux loop into free energy. Locks are in §7.4, and a legendary-resonator test is mandatory; a round trip ≥ 1.0 in any configuration is a release blocker.
- **R4 Load order / SA overwrite.**
  - What: SA replaces vanilla crafting_categories with `=` and edits techs by index inside its data.lua [C §3], [W §0.4]. Optional-dependency load order is unverified [T §9.2].
  - Mitigation: `info.json` deps `["base >= 2.0", "? quality", "? elevated-rails", "? space-age"]`. All cross-mod edits (categories, next_upgrade on turbo, SA recipe variants, tech prereqs) go in data-updates.lua; mirrored upgrades and quality locks go in data-final-fixes.lua. Tests run in both configs.
- **R5 Perceived power creep.**
  - What: 75/s in base-only (a 45 → 75 jump), 4.3× wall HP, and +50 % in-place drill are the three numbers a veteran will question.
  - Mitigation: each is late, priced above vanilla per unit of benefit, and defined by one spec constant, so it can be retuned in one place. These three are flagged for the council's review of the result.

---

## 9. Test plan (headless 2.0.77; every test runs in **config B** = base only and **config S** = base + quality + elevated-rails + space-age; harness per [H §15])

General rules:
- Lab surface [H §0].
- `force = "player"` on every create.
- Recipes enabled via research [H §11].
- Infinity chests and pipes as sources and sinks.
- An EEI (500 GW) as the power source, or an EEI sink for generator tests [H §6].
- Times in ticks at 60 UPS.
- Expected values come from the spec file (single source of truth, like Mindustry's `spec.py`).
- Tolerances are stated per test.
- Results go to JSON via `helpers.write_file` [H §14].

### 9.1 Static / load (data + `prototypes.*` introspection [H §13])
| # | measures | expected |
|---|---|---|
| S1 | mod loads | 0 errors, 0 warnings in B and S |
| S2 | name audit | every added prototype name starts with `magnetics-`; ∩ `names_sa.tsv` = ∅ |
| S3 | every spec number | crafting_speed, energy_usage (J/tick calibrated against AM1 = 75 kW [H §13]), module slots, allowed effects, mining_speed and radius, belt_speed, max_underground_distance, buffer and flow limits, wire reach and supply, get_max_power_output, burner effectivity, turret range, cooldown and energy per shot, max_health, resistances, stack sizes, recipe ingredients/products/energy/category/allow_productivity, tech prereqs/count/time/ingredients/effects — all == spec |
| S4 | vanilla parity | a dump of every vanilla recipe and tech with vs without Magnetics is identical except: appended `magnetics-slug`/`magnetics-arc` effects, `next_upgrade` on 8 vanilla entities, and (S only) 3 SA machines' categories. Anything else = fail |
| S5 | upgrade chains | stone-wall→ferrite→magnet→SC wall; gate→magnet gate; EMD→magnetic drill; accumulator→SC accumulator; big pole→pylon; (B) express / (S) turbo belt, UG and splitter → maglev. All valid per the API rule (same box, mask, FRG); runtime `order_upgrade` pilot on one of each |
| S6 | mirrored upgrades | after `research_all`: `get_ammo_damage_modifier("magnetics-slug") == get_ammo_damage_modifier("bullet")`, gun-speed likewise; `magnetics-arc` == `laser` (B and S separately) |
| S7 | SA integration | S: EM plant ⊇ {winding}, cryogenic plant ⊇ {cryogenics}, foundry ⊇ {sintering, induction}; kiln and MHD have pressure ≥ 10; separation recipe has magnetic-field ≥ 50. B: none of these fields exist |
| S8 | quality locks (S) | resonator speed is 1.0 at every quality; no recycling recipe produces or consumes `magnetics-flux-crystal`; the charging recipe has allow_productivity = false and allow_quality = false |
| S9 | locale (Python) | every prototype has en/ru/de name keys; no missing key |
| S10 | icons (Python) | each referenced PNG exists; 64×64 (items, entities, fluid, ammo categories) or 256×256 (techs); `showcase.png` contact sheet generated |

### 9.2 Production simulations (single machine, inputs unlimited, full power/fuel, normal quality, no modules)
| # | machine / recipe | window | expected (formula: crafts = speed × t / energy) |
|---|---|---|---|
| P1 | kiln / ferrite (coal fuel) | 3600 ticks | 18.75 → **18–19** ferrite; fuel burnt ≈ 90 kW × 60 s / 4 MJ = 1.35 coal (±1) |
| P2 | induction / ferrite; induction / alloy | 3600 | **37–38** ferrite; **18–19** alloy |
| P3 | winder / coil; winder / SC wire (coolant via infinity pipe) | 3600 | **29–30** coils; **10–12** wire (5–6 crafts × 2) |
| P4 | cryo chamber / coolant; / crystal growth | 3600 | coolant **1180–1200**; empty crystals **2–3** |
| P5 | resonator / charging | 15 000 ticks (250 s) | **9–10** charged crystals; energy drawn from a metered EEI per crystal = **125.25 MJ ±2 %** |
| P6 | separator / stone | 36 000 ticks (600 s, 120 crafts) | iron ore **240 ±2**; copper ore **60 ±17** (3σ, Binomial(120, 0.5)) |
| P7 | SA only: EM plant / coil (base productivity +50 % [C §1]) | 3600 | crafts = 2 × 60 / 2 = 60 → coils **89–90** incl. productivity (confirms the category insert works) |

### 9.3 Mining
| # | measures | expected |
|---|---|---|
| M1 | magnetic drill on iron ore (mining_time 1), 3600 ticks, vs EMD in the same run | **45 ±1** vs **30 ±1**; ratio 1.50 ±0.05 |
| M2 | `mining_area` | 5×5 (same as EMD) |
| M3 | uranium ore + sulfuric acid via input fluid box | mines (> 0 ore in 60 s) |

### 9.4 Logistics (throughput method of [H §8])
| # | measures | expected |
|---|---|---|
| L1 | straight maglev belt, 60 s | **75.0 ±1.875** items/s (express control 45.0) |
| L2 | UG pair at max_distance 13 vs 14 (express control 9 vs 10) | connected / not connected |
| L3 | splitter, both outputs | 75.0 ±1.875 total |

### 9.5 Power
| # | measures | expected |
|---|---|---|
| E1 | coil capacitor charge / discharge into an EEI sink | capacity **1.00 MJ ±1 %**; peak flow **1.00 MW ±1 %** |
| E2 | SC accumulator | **20 MJ ±1 %**, **1.2 MW ±1 %** |
| E3 | pylon reach: `LuaWireConnector.can_wire_reach` (copper connectors via `get_wire_connector`) at 48.0 vs 48.5 tiles | true / false (big pole control 32 / 32.5) |
| E4 | MHD, coal, EEI demand ≥ 5 MW, 3600 ticks | output **5.00 MW ±1 %**; coal burned **83.3 ±2** (= 5 MW / 0.9 / 4 MJ × 60) |
| E5 | flux dynamo, 3600 ticks | **10.0 MW ±1 %**; **6** crystals burned; **6** empty crystals in the burnt slot |
| E6 | flux round trip (P5 energy in / E5 energy out per crystal) | ratio **0.76–0.80**; in S also with a **legendary** resonator: same energy per crystal ±2 % and ratio < 1 (release blocker) |

### 9.6 Combat (biters pinned with `stop` + `distraction.none`, `allow_destroy_when_commands_fail = false` [H §10.1]; turrets `destructible = false`; `on_entity_damaged` records `original_damage_amount`)

DPS is computed as **measured hits/s × measured damage per hit**; this does not depend on biter healing.

| # | measures | expected |
|---|---|---|
| K1 | coilgun, ferrite / alloy slug, damage per hit and shots/s | **15 / 40**; **2.0 ±0.05** shots/s |
| K2 | coilgun pierce: first projectile into 5 small biters in a line (1 tile apart) | ≥ 2 distinct biters damaged by one shot [pilot → exact value registered] |
| K3 | gauss per hit (damage_modifier 3); range | **45 / 120**; a target at 31 tiles is engaged within 5 s, a target at 34 is not |
| K4 | arc emitter: hits per shot on 5 medium biters spaced 4 tiles; damages | primary **25**, bounces **15**, distinct targets per shot **4**; energy per shot **600 kJ ±1 %** |
| K5 | mass driver on 5 medium biters in a line inside its arc, and one biter behind it | line: each biter gets **1200** raw; the biter outside turn_range is never engaged |
| K6 | energy per shot (buffer delta) | coilgun **50 kJ**, gauss **300 kJ**, mass driver **8 MJ** (±1 %) |
| K7 | paired vs vanilla on the same targets | report DPS ratios coilgun(ferrite)/gun(firearm) ≈ **0.6** on unarmoured targets (30/50) and ≈ **2.2** on medium biters after resistances (2×9.9 vs 10×0.9, assuming flat-then-percent, [W §1.2] undocumented → pilot fixes the registered value); gauss(alloy)/laser and arc(4 targets)/laser are measured and recorded (the laser baseline is not documented [W §5.2]; the pilot fixes the registered expectation) |
| K8 | walls: `LuaEntity.damage(100, "enemy", t)` for each of the 8 damage types, per wall + stone control | applied damage equals the pilot-measured stone-wall rule applied to our resistance tables (±0.01); max HP 500/800/1500/800 |
| K9 | reflection: a medium biter attacking a magnet wall, SC wall, stone wall (control) for 10 s | biter takes electric damage with `cause` = wall: > 0 on magnet and SC walls (SC > magnet), 0 on stone |
| K10 | upgrades: after physical-projectile-damage-1, per-hit coilgun damage vs gun-turret control | coilgun/control ratio identical to the no-research ratio; expected 15 × 1.1 = **16.5** if the modifier is multiplicative (combination formula undocumented [W §14.1] → **[pilot]**) |

### 9.7 Mend coil (script)
| # | setup | expected |
|---|---|---|
| R1 | 1 wall at 5 tiles, damaged by 300; 600 ticks | healed **+100 ±5** (per-target cap 10 HP/s) |
| R2 | 3 walls damaged by 300 each; 600 ticks | total healed **200 ±10** (pool 20 HP/s) |
| R3 | wall at 10.5 tiles | 0 healed |
| R4 | coil unpowered (buffer 0, no pole) | 0 healed |
| R5 | energy used vs HP healed (R2) | **5 kJ/HP ±2 %** |
| R6 | enemy-force wall in range | 0 healed |
| R7 | UPS: 200 coils around 2000 damaged walls vs 200 inert EEIs, `--benchmark` 3600 ticks | Δ mean tick time **< 0.05 ms** |
| R8 | determinism: run R1–R6 twice (fresh `--create`) | identical result JSON (hash) |
| R9 | save/load mid-heal, then continue | heal totals identical to an uninterrupted run |

### 9.8 Pictures (for the author)
- `showcase.png`: every item, entity, fluid and tech icon with its en/ru name.
- One card per entity: our icon + "vanilla base: X, tint: (r,g,b)" + a colour swatch.
- Both are generated by the same Python that draws the icons, so every model has a reviewable picture even though world sprites (vanilla PNGs) are absent in the headless build.

**Icon motifs** (all drawn by PIL, 64 px with a 4-level mipmap strip optional; techs 256 px):
- ferrite: dark hexagonal pellet;
- coil: copper toroid;
- alloy: blue ingot with N/S poles;
- SC wire: cyan wire spool with frost;
- empty crystal: grey octahedron; charged crystal: violet glowing octahedron;
- coolant: pale-blue droplet with snowflake;
- slugs: grey / blue cylinders in a clip;
- buildings: simplified top-down silhouettes of their vanilla base in their tint colour, each with a magnet/field-line glyph.
