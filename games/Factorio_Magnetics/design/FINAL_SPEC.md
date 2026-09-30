# Magnetics for Factorio 2.0.77 — final design specification

Status: **implementation-ready spec, not yet piloted.** A number that depends on an engine behaviour the sources do not document is marked **[PILOT-n]**. The pilot list is §14, the last section. Following the project rule, every pilot runs on a separate save or seed that does not enter the registered tests. Every number a pilot changes is written into the PREREG before the first registered run.

Synthesis basis: three designs and three judges.

| design | judge 1 (balance) | judge 2 (engine/testability) | judge 3 (appeal) | sum |
|---|---|---|---|---|
| design_engine.md | 6.5 | **8.5** | 7 | **22.0** |
| design_balance.md | **8** | 7 | 6.5 | 21.5 |
| design_appeal.md | 3.5 | 5 | **7.5** | 16.0 |

This spec uses **design_engine as the chassis**: same-type deepcopies, one `make()` procedure, pilots, the reachability/diff/tint tests and the showroom. **design_balance supplies the numbers**: tier placement, balance anchors, energy-loop locks, wall/gate tiers, the MHD, the pylon and the SA category inserts. **design_appeal supplies the signature mechanics**, nerfed where the judges required: ferrofluid, air-liquefied nitrogen, the geomagnetic coil, thorn walls, the event-driven mend coil, the magnet slug tier, the 4-configuration matrix and the planet-side placement rule. §0.3 traces every judge must-fix to where it is resolved.

---

## 0. Conventions

### 0.1 Citation keys (all vanilla numbers carry one)

| key | source |
|---|---|
| [C §n] | `scratchpad/recon/crafting.md` |
| [L §n] | `scratchpad/recon/logistics.md` |
| [P §n] | `scratchpad/recon/power.md` |
| [M §n] | `scratchpad/recon/mining.md` |
| [W §n] | `scratchpad/recon/combat.md` |
| [T §n] | `scratchpad/recon/tech.md` |
| [H §n] | `scratchpad/recon/harness.md` |
| [RB] / [RS] | `scratchpad/fx/raw_base.json` / `raw_sa.json`: `data.raw` dumped from the real 2.0.77 headless server (base / base+ER+Q+SA). Vanilla recipe ingredients, HP values and heating values not quoted in recon were read from these dumps in this session. |
| [PL] / [PL2] | `scratchpad/fx/wd/script-output/pilot.json` / `pilot2.json`: earlier 2.0.77 headless pilot measurements |
| [D:path:line] | game Lua read directly by a judge (e.g. `base/data-updates.lua:169`, `base/prototypes/entity/enemy-constants.lua:134-137`) |
| (not in recon) | a number used only as an illustration, never as a test expectation |

### 0.2 Global rules

1. **Prefix.** Every prototype name starts with `magnetics-`. The only auto-generated names allowed are `magnetics-*-recycling` (quality mod). Checked against `fx/names_base.tsv` and `fx/names_sa.tsv`: no clash (script `design/spec_check.py`, run 2026-09-30).
2. **Graphics.** Every entity is `table.deepcopy` of one vanilla entity with a tint on body leaves (§4.1). Every icon (items, entities, fluids, recipes with their own icon, ammo categories, technologies at 256 px) is drawn by Python/PIL (§10). The only new world sprite is the procedural rail-tracer gradient (§4.7).
3. **Vanilla untouched except a whitelist** (§7.2): `next_upgrade` links, appended bonus effects, and (SA only) crafting-category inserts on three SA machines. No vanilla recipe, technology cost, prerequisite, stat or graphic changes.
4. **One source of truth.** `tools/spec.py` holds every number in this document and generates the Lua data tables, locale files, icons and test expectations. No number is typed twice.
5. **SA guards.** Every SA-only name, `surface_conditions` and `heating_energy` is written only under `if mods["space-age"]` (§7).

### 0.3 Must-fix traceability (judges → this spec)

| must-fix (judge) | resolved in |
|---|---|
| `turret-attack` mirroring for Magnetics ammo turrets (J1, J2) | §5.3; test K11 (ratio constant) |
| Tech prerequisite gaps; static reachability check in all configs (J1, J2, J3) | §5 tree verified by `design/spec_check.py` against [RB] and [RS]: 0 problems in base and SA; test S5 |
| `auto_barrel = false` on every new fluid (J1, J2, J3) | §2.2; test S10 |
| Pilots before PREREG (J1, J2) | §14 (25 pilots, each with a fallback) |
| Same-type deepcopies; no fluid-turret mass driver, no laser→ammo gauss (J1, J2) | §4: 24 of 26 entities are same-type copies. Gauss and rail cannon are `ammo-turret` from `gun-turret`. The only conversions are the kiln and the induction furnace (both CraftingMachine→CraftingMachine, same `graphics_set` type), behind PILOT-2 with a same-size fallback. |
| Arc emitter niche: range 20–22, 0.5–1.0× laser, below tesla; instant damage, cosmetic beams (J1, J2) | §4.6, §8.4; tests K7, K8 |
| Gauss range decided; nothing reaches 38 before artillery (J1) | gauss 30, rail cannon 36, rail line 36; test K12 |
| Balance anchors: drill 0.75, base maglev at utility science, MHD 16.7 pollution/min per MW of fuel, pylon 48, flux round trip ≤ 0.8 with locks, stone separation magnetic-field ≥ 50 (J1) | §4, §8; tests M1, L1, E4, E3, E6, S8 |
| Rejected grafts (J1): rechargeable 2 GJ crystal, locomotive fuel, uncapped geomagnetic coil, thorns-at-blue SC wall, 135-dps magnet slug, unlimited-pierce hitscan slugs, 3× cleaner MHD, purple base maglev, 2× drill | all rejected; §12 |
| Wire reach + quality ≤ 64 (J2, J3) | pylon 48 → legendary 58; test Q2 |
| Bounded coilgun pierce (J2, J3) | projectile with `piercing_damage`; test K3 |
| Reset inherited `next_upgrade`/FRG on every copy (J2) | §4.1 step 4–5; test S6 |
| Mend coil: type-filtered, bounded, energy from buffer, event-driven or capped; save/load, determinism, UPS, rebuild tests (J1, J2) | §6; tests R1–R11, U1–U2 |
| Storage charge tests use a non-tertiary source (J2) | test-mod `magnetics-test-source` (primary-output) and `magnetics-test-sink` (secondary-input); §11.1 |
| Calutron dropped (J2) | dropped; §12 |
| 4-config matrix; S7 field diff; S12 tint isolation; SA platform check (J1, J2, J3) | §11.1, S7, S12, E8 |
| Mindustry continuity: Rail cannon name, flux crystal = fuel + rail ammo, MHD, coil capacitor, magnet gate, SC wall absorbs laser/electric, "Superconducting cable", en/ru/de (J3) | §1.2, §9 |
| Pictures of every model: icons, showcase sheet, per-entity cards, `/magnetics-showroom` (J3) | §10; tests G1–G3 |
| Winder base productivity ≤ 25 % or none; drill 2× speed OR larger area (J3) | winder: none; drill: neither (0.75, 5×5) |
| Geomagnetic coil ≤ ~20 kW on Nauvis; scaling settled by pilot (J1, J3) | 20 kW nominal → 18 or 20 kW on Nauvis; PILOT-12; test E7 |

---

## 1. Concept and progression

### 1.1 One-sentence concept
Magnetics adds a **second metallurgy line beside vanilla's**: iron ore + stone → **ferrite** → ferrite-core **coils** → **magnet alloy** → **superconducting cable**, fed by two new fluids (**ferrofluid**, **liquid nitrogen**), ending in rechargeable **flux crystals**. Each rung unlocks buildings that are side-grades of vanilla buildings or late, priced in-place tiers (Factorio's own AM2→AM3 pattern).

### 1.2 Mindustry → Factorio port map

| Mindustry Magnetics (`games/Mindustry_Magnetics/tools/spec.py`) | Factorio Magnetics | why |
|---|---|---|
| ferrite (sand + lead) | `magnetics-ferrite` (iron ore + stone, sintered) | Factorio raw resources; gives stone a mid-game sink |
| coil (alloy + copper) | `magnetics-coil` (ferrite core + copper cable) | a real ferrite-core inductor; available at green, before alloy |
| magnet alloy (titanium + silicon) | `magnetics-magnet-alloy` (steel + ferrite + copper) | hangs on steel |
| superconductor (+ cryofluid) | `magnetics-superconducting-cable`, shown as "Superconducting cable" (+ liquid nitrogen) | SA owns item `superconductor` [T §10] |
| flux crystal (+ phase fabric) | `magnetics-flux-crystal` (charged fuel) + `magnetics-flux-crystal-uncharged` | a native fuel/`burnt_result` pair like the uranium fuel cell [P §9.2]; also the core of flux rail slugs (fuel **and** rail ammo, as in Mindustry) |
| cryofluid | `magnetics-liquid-nitrogen` (air liquefaction) + `magnetics-ferrofluid` (ferrite + light oil) | a Factorio fluid chain; ferrofluid is the maglev tier's lubricant (express uses 20 lubricant per belt [L §6]) |
| kiln, induction furnace, coil winder, cryo chamber, flux resonator, magnetic separator | all six kept | each is the base-game machine of its own recipe category, like the chemical plant for chemistry |
| magnetic drill | `magnetics-magnetic-drill`, in-place upgrade of the electric mining drill | `next_upgrade` [M §9.1] |
| mag conveyor / junction / router / bridge | maglev belt / underground belt / splitter (75 items/s) | Factorio has no junction or router; the underground belt is the bridge |
| coil battery (1×1), superconducting battery (3×3) | `magnetics-coil-capacitor` (1×1, burst flow) + `magnetics-superconducting-accumulator` (2×2 upgrade) | two different niches: flow and density |
| superconducting node (reach 22) | `magnetics-superconducting-pylon` (big-pole upgrade, wire reach 48) | wire reach is the Factorio equivalent |
| MHD generator | `magnetics-mhd-generator` (burner generator, no water) | kept (J3) |
| flux reactor | `magnetics-flux-dynamo` (burns charged crystals, returns uncharged ones) | power transport, not generation |
| ferrite / magnet / superconducting walls | 3 walls (1×1) + magnet gate + superconducting gate, one upgrade chain from the stone wall | Factorio walls are 1×1 [W §11.2]; every wall tier after the red ferrite wall gets its own gate |
| "magnet wall deflects bullets" | electric thorns through the native `attack_reaction` | base ships the pattern commented out on the stone wall [D:base/prototypes/entity/entities.lua:3383-3410] |
| mend projector | `magnetics-mend-coil` (script, event-driven) | no native area repair |
| magnetic shield (dome) | **dropped** | no building-shield prototype in Factorio |
| coilgun (duo), gauss | `magnetics-coilgun-turret` (2 slug tiers), `magnetics-gauss-turret` | Factorio convention: one turret, several ammo tiers; gauss is the long-range armour breaker |
| arc | `magnetics-arc-emitter` (chain lightning) | `chain-active-trigger` is a core type [W §15] |
| railgun | `magnetics-rail-cannon` (line shot; rail slug, flux rail slug) | SA owns `railgun`/"Railgun"; ammo = superconductor and flux crystal, as in Mindustry |
| maglev flak, air units, unit factory | **dropped** | no air enemies in base or on SA planets |
| — (new, Factorio-native) | `magnetics-geomagnetic-coil` (solar-panel type driven by the `magnetic-field` surface property) | `magnetic-field` is a base surface property, default 90 [P §0.6, §11.6] |

### 1.3 Where it sits in a normal playthrough

| stage (packs) | Magnetics content | hangs on vanilla tech [T §3, §4] |
|---|---|---|
| red (A) | sintering kiln, ferrite, ferrite wall | automation-science-pack, stone-wall |
| green (A+L) | coil winder, coils; coilgun + ferrite slugs | automation-2; gun-turret, military-2 |
| blue (A+L+C) | induction furnace, magnet alloy; magnetic drill; MHD, coil capacitor, geomagnetic coil; ferrofluid, magnetic separator | advanced-material-processing-2, electric-mining-drill, solar-energy, electric-energy-accumulators, advanced-oil-processing |
| blue + military (A+L+C+M) | magnet wall, magnet gate, magnet slugs, gauss turret + slugs, mend coil; arc emitter | military-3, gate, repair-pack; laser-turret |
| purple (A+L+C+P) | cryo chamber, liquid nitrogen, superconducting cable; SC accumulator, SC pylon | production-science-pack, electric-energy-distribution-2 |
| yellow (…+U) | flux resonator, flux dynamo, crystal growth and charging; maglev belts; SC wall, SC gate, rail cannon, rail and flux rail slugs | utility-science-pack, uranium-processing, logistics-3, military-4, concrete (+ SA: turbo-transport-belt, electromagnetic-science-pack) |

Base game: Magnetics fills green→blue with side-grades and gives purple→yellow three priced late tiers (belts, accumulators, walls) plus a power-transport loop and a line-shot turret. **No new science pack, no new ore, no new end-game goal.**

### 1.4 Coexistence with Space Age (per SA building)

| SA content | relation | mechanism |
|---|---|---|
| turbo belt 60/s [L §2] | maglev (75/s) is tier 5 **after** turbo: recipe consumes turbo items; tech requires `turbo-transport-belt` and `electromagnetic-science-pack`; `turbo-*.next_upgrade = magnetics-maglev-*` | data.lua recipe variant + data-updates links; SA itself links express→turbo [L §11] |
| electromagnetic plant (speed 2, +50 % productivity [C §1]) | gets `magnetics-winding` | data-updates insert; the SA-native specialist reward |
| cryogenic plant (speed 2, 8 modules [C §1]) | gets `magnetics-cryogenics` | data-updates insert |
| foundry (speed 4, +50 % [C §1]) | gets `magnetics-sintering`, `magnetics-induction` | data-updates insert |
| tesla turret (range 30, 120 per hit, 10 jumps, stun [W §5.5, §8, §9]) | arc emitter is the earlier, weaker chain turret (range 20, 45 + 4×30) | numbers below tesla |
| railgun turret (range 40, 10 000 line damage, 10 MJ/shot [W §5.4, §6.4]) | rail cannon is the earlier, weaker line gun (range 36, 1200 line damage, 4 MJ/shot) | numbers below railgun |
| big mining drill (2.5 speed, 13×13, 50 % drain, `hard-solid` [M §1]) | magnetic drill (0.75, 5×5, `basic-solid` only) stays below it on every axis | `hard-solid` never referenced |
| `superconductor` item | unrelated to our cable | distinct name, icon, display name |
| surface properties [P §11.6] | **every Magnetics entity requires `magnetic-field ≥ 10`** (Nauvis 90, Vulcanus 25, Gleba 25, Fulgora 99, Aquilo 10: allowed; space platform 0: blocked). Kiln and MHD also require `pressure ≥ 10` (like stone furnace and boiler [C §3], [P §11.5]). Recipe `magnetics-stone-separation` requires `magnetic-field ≥ 50` (Nauvis, Fulgora only) | SA platform balance is untouched by construction (test E8) |
| freezing (Aquilo) | explicit `heating_energy` table copied from each vanilla analogue (§7.4) | SA-guarded |
| quality | everything scales as vanilla, except the flux resonator (quality-locked) and the crystals (no quality variants) | §7.5 |
| heating tower, fusion | flux dynamo is not a generator (80 % round trip) | §8.3 |
| recycler / scrap | nothing references scrap | — |

---

## 2. Items and fluids

New item subgroup `magnetics-intermediate`: group `intermediate-products`, order `gm` (vanilla `intermediate-product` is `g`, `uranium-processing` is `i` [RB]). Placeable items go into vanilla subgroups next to their analogue. Every placeable item has the same name as its entity and `place_result` = that name, as quality recycling requires [T §5.4].

### 2.1 Non-placeable items

| name | type / special fields | stack | subgroup / order | use |
|---|---|---|---|---|
| `magnetics-ferrite` | item | 100 (plates) | magnetics-intermediate / `a[ferrite]` | coils, alloy, ferrofluid, ferrite wall, ferrite slugs, winder, coilgun |
| `magnetics-coil` | item | 200 (like circuits) | `b[coil]` | nearly every building |
| `magnetics-magnet-alloy` | item | 100 | `c[magnet-alloy]` | SC cable, blue-tier buildings, walls, slugs, maglev |
| `magnetics-superconducting-cable` | item, `auto_recycle = false` | 200 | `d[superconducting-cable]` | purple/yellow tier, crystal growth, rail slug |
| `magnetics-flux-crystal-uncharged` | item, `auto_recycle = false` | 20 | `e[flux-crystal-uncharged]` | charged in the resonator; returned by the dynamo as `burnt_result` |
| `magnetics-flux-crystal` | item, `fuel_category = "magnetics-flux"`, `fuel_value = "100MJ"`, `burnt_result = "magnetics-flux-crystal-uncharged"`, `auto_recycle = false` | 20 (same slot energy as rocket fuel: 100 MJ × 20 [P §9.2]) | `f[flux-crystal]` | flux dynamo fuel; core of the flux rail slug |
| `magnetics-ferrite-slug` | ammo, category `magnetics-slug`, `magazine_size = 10` | 100 | `ammo` / `m[magnetics]-a[ferrite-slug]` | coilgun, tier 1 |
| `magnetics-magnet-slug` | ammo, `magnetics-slug`, `magazine_size = 10` | 100 | `ammo` / `m[magnetics]-b[magnet-slug]` | coilgun, tier 2 |
| `magnetics-gauss-slug` | ammo, category `magnetics-gauss`, `magazine_size = 4` | 50 | `ammo` / `m[magnetics]-c[gauss-slug]` | gauss turret |
| `magnetics-rail-slug` | ammo, category `magnetics-rail`, `magazine_size = 1` | 20 | `ammo` / `m[magnetics]-d[rail-slug]` | rail cannon |
| `magnetics-flux-rail-slug` | ammo, `magnetics-rail`, `magazine_size = 3` | 10 | `ammo` / `m[magnetics]-e[flux-rail-slug]` | rail cannon, premium |

Helper category prototypes:
- `ammo-category`: `magnetics-slug` (`bonus_gui_order = "l-m1"`), `magnetics-gauss` (`"l-m2"`), `magnetics-rail` (`"l-m3"`). They sort after `bullet` = `l` [RB], and each has its own 64 px icon (§10). A new category gets no vanilla bonus unless the mod appends it [W §0.3, §14.2]; see §5.3.
- `fuel-category`: `magnetics-flux` (a base prototype type, no SA restriction [P §9.3]).
- `recipe-category` (6): `magnetics-sintering`, `magnetics-induction`, `magnetics-winding`, `magnetics-cryogenics`, `magnetics-resonance`, `magnetics-separation`.
- `item-subgroup`: `magnetics-intermediate`.

### 2.2 Fluids (both `auto_barrel = false`)

Without the opt-out, `base/data-updates.lua:169` generates `empty-magnetics-<fluid>-barrel`, which breaks the prefix rule. The opt-out is read at line 279 [D:base/data-updates.lua:169, 279].

| name | fields | subgroup / order | use |
|---|---|---|---|
| `magnetics-ferrofluid` | `default_temperature = 25` (as lubricant [RB]), `base_color = {0.07, 0.06, 0.09}`, `flow_color = {0.48, 0.36, 0.72}`, `auto_barrel = false` | `fluid` / `a[fluid]-b[oil]-f[magnetics-ferrofluid]` (after lubricant `a[fluid]-b[oil]-e[lubricant]` [RB]) | maglev belts (20/belt), magnetic separator, crystal growth |
| `magnetics-liquid-nitrogen` | `default_temperature = -196` (negative defaults exist: SA `fluoroketone-cold` = −150 [RS]; base-only load is PILOT-13), `base_color = {0.75, 0.90, 1.00}`, `flow_color = {0.94, 0.98, 1.00}`, `auto_barrel = false` | `fluid` / `a[fluid]-z[magnetics-liquid-nitrogen]` | SC cable, crystal growth |

### 2.3 Placeable items

| item (= entity) | stack | subgroup / order |
|---|---|---|
| magnetics-sintering-kiln | 50 | smelting-machine / `a[stone-furnace]-m[magnetics-sintering-kiln]` |
| magnetics-induction-furnace | 50 | smelting-machine / `c[electric-furnace]-m[magnetics-induction-furnace]` |
| magnetics-coil-winder | 50 | production-machine / `m[magnetics]-a[coil-winder]` (after `f[centrifuge]`, before `z[lab]` [RB]) |
| magnetics-cryo-chamber | 10 (chemical plant [RB]) | production-machine / `m[magnetics]-b[cryo-chamber]` |
| magnetics-flux-resonator | 20 | production-machine / `m[magnetics]-c[flux-resonator]` |
| magnetics-magnetic-separator | 50 | production-machine / `m[magnetics]-d[magnetic-separator]` |
| magnetics-magnetic-drill | 50 | extraction-machine / `a[items]-b[electric-mining-drill]-m[magnetics]` |
| magnetics-maglev-transport-belt | 100 | belt / `a[transport-belt]-e[magnetics-maglev]` (express is `…-c[…]` [RB], SA turbo `…-d[…]`) |
| magnetics-maglev-underground-belt | 50 | belt / `b[underground-belt]-e[magnetics-maglev]` |
| magnetics-maglev-splitter | 50 | belt / `c[splitter]-e[magnetics-maglev]` |
| magnetics-coil-capacitor | 50 | energy / `e[accumulator]-b[magnetics-coil-capacitor]` |
| magnetics-superconducting-accumulator | 50 | energy / `e[accumulator]-c[magnetics-superconducting-accumulator]` |
| magnetics-superconducting-pylon | 50 | energy-pipe-distribution / `a[energy]-c[big-electric-pole]-m[magnetics]` |
| magnetics-mhd-generator | 10 (steam engine [P §1]) | energy / `b[steam-power]-m[magnetics-mhd-generator]` |
| magnetics-flux-dynamo | 10 | energy / `f[nuclear-energy]-m[magnetics-flux-dynamo]` |
| magnetics-geomagnetic-coil | 50 | energy / `d[solar-panel]-m[magnetics-geomagnetic-coil]` |
| magnetics-ferrite-wall | 100 (stone wall [RB]) | defensive-structure / `a[stone-wall]-b[magnetics-ferrite-wall]` |
| magnetics-magnet-wall | 100 | defensive-structure / `a[stone-wall]-c[magnetics-magnet-wall]` |
| magnetics-superconducting-wall | 100 | defensive-structure / `a[stone-wall]-d[magnetics-superconducting-wall]` |
| magnetics-magnet-gate | 50 (gate [RB]) | defensive-structure / `a[wall]-c[magnetics-magnet-gate]` |
| magnetics-superconducting-gate | 50 | defensive-structure / `a[wall]-d[magnetics-superconducting-gate]` |
| magnetics-mend-coil | 20 | defensive-structure / `e[magnetics-mend-coil]` |
| magnetics-coilgun-turret | 50 | turret / `b[turret]-m[magnetics]-a[coilgun]` |
| magnetics-gauss-turret | 50 | turret / `b[turret]-m[magnetics]-b[gauss]` |
| magnetics-arc-emitter | 50 | turret / `b[turret]-m[magnetics]-c[arc-emitter]` |
| magnetics-rail-cannon | 10 | turret / `b[turret]-m[magnetics]-d[rail-cannon]` |

**Content count:** 26 buildings + 11 non-placeable items + 2 fluids = **39 content objects** (63 item/entity/fluid prototypes when each building's item is counted). Hidden helpers: 3 projectiles, 2 beams, 1 chain trigger, 1 explosion (tracer), 3 ammo categories, 1 fuel category, 6 recipe categories, 1 subgroup. **40 recipes, 14 technologies.**

---

## 3. Recipes

Machine → categories (base): kiln {sintering}; induction furnace {sintering, induction}; coil winder {winding}; cryo chamber {cryogenics}; flux resonator {resonance}; separator {separation}. Ferrofluid uses vanilla `chemistry` (chemical plant). **SA only, inserted in data-updates.lua**, because SA overwrites vanilla machine category lists with `=` inside its data.lua [C §3]: `electromagnetic-plant` += winding; `cryogenic-plant` += cryogenics; `foundry` += sintering, induction. AM2/AM3 and the character get **no** Magnetics category (the winder is the base-game coil machine, as the chemical plant is for chemistry).

Every recipe has `enabled = false` and is unlocked by exactly one technology (test S5). "Prod" = `allow_productivity` (vanilla default false [C §11.1]). "AR" = `auto_recycle` (default true; read by the quality mod [C §11.3]).

### 3.1 Intermediates and fluids

| recipe | category | ingredients | results | energy (s) | Prod | AR | notes |
|---|---|---|---|---|---|---|---|
| `magnetics-ferrite` | sintering | iron-ore 1, stone 1 | ferrite 1 | 3.2 (= iron plate [RB]) | yes | false | smelting-like; vanilla smelting is not recycled [C §11.3] |
| `magnetics-coil` | winding | ferrite 1, copper-cable 4 | coil 1 | 1.6 | yes | true | |
| `magnetics-magnet-alloy` | induction | steel-plate 1, ferrite 2, copper-plate 1 | magnet-alloy 1 | 6.4 | yes | false | |
| `magnetics-ferrofluid` | chemistry | ferrite 1, light-oil 10 | ferrofluid 10 | 1 (= lubricant: heavy-oil 10 → 10 in 1 s [RB]) | yes | false | `crafting_machine_tint = {primary {0.07,0.06,0.09}, secondary {0.48,0.36,0.72}, tertiary {0.30,0.25,0.40}, quaternary {0.15,0.10,0.20}}` |
| `magnetics-liquid-nitrogen` ("Air liquefaction") | cryogenics | — (empty list, allowed: "May be `{}`" [C §11.1]) | liquid-nitrogen 50 | 2 | no | false | own locale name and icon; `crafting_machine_tint` pale blue |
| `magnetics-superconducting-cable` | cryogenics | magnet-alloy 1, copper-cable 6, plastic-bar 1, liquid-nitrogen 20 | superconducting-cable 2 | 10 | yes | false | |
| `magnetics-flux-crystal-growth` | cryogenics | superconducting-cable 2, processing-unit 1, uranium-238 1, ferrofluid 20, liquid-nitrogen 50 | flux-crystal-uncharged 1 | 20 | yes | false | `allow_quality = false`; own locale name and icon; subgroup magnetics-intermediate, order `z-a` |
| `magnetics-flux-crystal-charging` | resonance | flux-crystal-uncharged 1 | flux-crystal 1 | 25 | **no** | false | `allow_quality = false`; own name/icon; order `z-b`; energy lock §7.5 |
| `magnetics-stone-separation` | separation | stone 10, ferrofluid 5 | iron-ore 2; copper-ore 1 with `probability = 0.5` | 5 | yes | false | multi-product ⇒ own `icon`, `subgroup = magnetics-intermediate`, `order = z-c` [C §11.1]; SA: `surface_conditions = {{property = "magnetic-field", min = 50}}` |

### 3.2 Ammo (category `crafting`, hand-craftable; Prod no, as vanilla ammo)

| recipe | ingredients | result | energy (s) | AR |
|---|---|---|---|---|
| `magnetics-ferrite-slug` | ferrite 6, copper-plate 2 | ferrite-slug 1 (10 shots) | 3 | true |
| `magnetics-magnet-slug` | ferrite-slug 1, magnet-alloy 1 | magnet-slug 1 | 5 | true |
| `magnetics-gauss-slug` | magnet-alloy 2, steel-plate 1 | gauss-slug 1 (4 shots) | 6 | true |
| `magnetics-rail-slug` | superconducting-cable 1, magnet-alloy 2, steel-plate 2 | rail-slug 1 | 10 | true |
| `magnetics-flux-rail-slug` | rail-slug 1, flux-crystal 1 | flux-rail-slug 1 (3 shots) | 15 | **false** (a recycling recipe would return charged crystals with quality) |

### 3.3 Buildings (category `crafting` unless noted; 1 result; Prod no; AR true)

"TOP" = `express-*` in base and `turbo-*` when `mods["space-age"]`, resolved in data.lua.

| recipe → item | ingredients | energy (s) |
|---|---|---|
| magnetics-sintering-kiln | stone-furnace 1, iron-gear-wheel 2, stone-brick 5 | 2 |
| magnetics-induction-furnace | steel-plate 10, advanced-circuit 5, stone-brick 10, coil 10 (the electric-furnace recipe [RB] + 10 coils) | 5 |
| magnetics-coil-winder | assembling-machine-2 1, ferrite 10, copper-cable 20 | 3 |
| magnetics-cryo-chamber | chemical-plant 1, magnet-alloy 10, coil 10, pipe 10 | 5 |
| magnetics-flux-resonator | centrifuge 1, superconducting-cable 50, processing-unit 20 | 10 |
| magnetics-magnetic-separator | steel-plate 10, magnet-alloy 10, coil 20, advanced-circuit 5, iron-gear-wheel 10 | 5 |
| magnetics-magnetic-drill | electric-mining-drill 1, magnet-alloy 5, coil 5, advanced-circuit 2 | 2 |
| magnetics-maglev-transport-belt (`crafting-with-fluid`) | TOP-transport-belt 1, superconducting-cable 1, magnet-alloy 1, ferrofluid 20 | 0.5 |
| magnetics-maglev-underground-belt (`crafting-with-fluid`) → **2** | TOP-underground-belt 2, magnet-alloy 20, superconducting-cable 10, ferrofluid 40 | 2 |
| magnetics-maglev-splitter (`crafting-with-fluid`) | TOP-splitter 1, superconducting-cable 5, magnet-alloy 10, processing-unit 2, ferrofluid 80 | 2 |
| magnetics-coil-capacitor | coil 5, steel-plate 2, electronic-circuit 2 | 5 |
| magnetics-superconducting-accumulator | accumulator 1, superconducting-cable 10, magnet-alloy 5 | 10 |
| magnetics-superconducting-pylon | big-electric-pole 1, superconducting-cable 2, steel-plate 2 | 1 |
| magnetics-mhd-generator | steel-plate 20, coil 20, magnet-alloy 10, advanced-circuit 10 | 10 |
| magnetics-flux-dynamo | steel-plate 20, superconducting-cable 20, coil 20, processing-unit 10 | 10 |
| magnetics-geomagnetic-coil | magnet-alloy 4, coil 10, steel-plate 5, electronic-circuit 5 | 10 |
| magnetics-ferrite-wall | stone-wall 1, ferrite 2 | 0.5 |
| magnetics-magnet-wall | ferrite-wall 1, magnet-alloy 1, steel-plate 1 | 1 |
| magnetics-superconducting-wall | magnet-wall 1, superconducting-cable 1, refined-concrete 4 | 2 |
| magnetics-magnet-gate | magnet-wall 1, steel-plate 2, electronic-circuit 2 (mirrors gate = stone-wall 1 + steel 2 + EC 2 [W §11.3]) | 0.5 |
| magnetics-superconducting-gate | magnet-gate 1, superconducting-cable 1, refined-concrete 4 | 1 |
| magnetics-mend-coil | steel-plate 10, coil 20, repair-pack 10, advanced-circuit 5 | 10 |
| magnetics-coilgun-turret | gun-turret 1, coil 10, ferrite 10, electronic-circuit 5 | 8 (= gun turret [W §5.6]) |
| magnetics-gauss-turret | steel-plate 20, magnet-alloy 10, coil 20, advanced-circuit 10 | 20 |
| magnetics-arc-emitter | laser-turret 1, coil 20, magnet-alloy 10 | 20 |
| magnetics-rail-cannon | steel-plate 40, superconducting-cable 20, coil 30, magnet-alloy 20, processing-unit 10 | 30 |

Every wall and gate takes the previous tier as an ingredient, as vanilla's gate takes a stone wall [W §11.3]. Walls returned by the upgrade planner are therefore re-crafted upward instead of piling up.

### 3.4 Chain ratios (players and tests; from §3.1 and §4)
- 1 kiln = 0.3125 ferrite/s (a stone-furnace column on iron plates).
- 1 winder = 0.625 coils/s; it needs 0.625 ferrite/s (**2 kilns or 1 induction furnace on sintering**) and 2.5 cable/s.
- 1 induction furnace on alloy = 0.3125 alloy/s; it needs 0.625 ferrite/s (**exactly 1 more induction furnace on sintering**), 0.3125 steel/s and 0.3125 copper/s.
- 1 cryo chamber on SC cable = 0.2 cable/s and 2 LN2/s; **1 chamber on air liquefaction (25 LN2/s) feeds 12.5 cable chambers**.
- 1 chemical plant on ferrofluid = 10/s = enough for 30 maglev belts per minute.
- 1 resonator charges 0.04 crystals/s = 4 MW of dynamo output; **one 10 MW dynamo needs 2.5 resonators**.

---

## 4. Entities

### 4.1 Common procedure `make(ptype, src, name, tint, frg)` (data.lua)

1. `e = table.deepcopy(data.raw[ptype][src])` [C §10.1].
2. `e.name = name`; `e.minable.result = name`; `e.hidden = nil` (base `burner-generator` and `electric-energy-interface` are hidden [P §7.2, §8]).
3. `e.icon = nil`; `e.icons = {{icon = "__magnetics__/graphics/icons/<name>.png", icon_size = 64}}`.
4. **Clear inherited links:** `e.next_upgrade = nil` (e.g. stone-furnace → steel-furnace [C §1]; express → turbo under SA [L §11]); `e.factoriopedia_simulation = nil` (the express-UG simulation is a blueprint of express entities [L §12.3]).
5. `e.fast_replaceable_group = frg` from the tables below. Only the intended in-place upgrades keep the vanilla group; all other copies get their own name, so pasting a coil winder can never silently replace an assembler, and an arc emitter never replaces a laser turret.
6. Type-specific links: `related_underground_belt` (belt), `related_transport_belt` (splitter) [L §11].
7. **Tint walker** [C §10.3]: tint only leaves with `filename`/`filenames`/`stripes`; skip `draw_as_shadow`, `draw_as_glow`, `draw_as_light`, `apply_runtime_tint` (turret force masks); skip working visualisations with `apply_recipe_tint` or `apply_tint`; never enter `circuit_connector`, `water_reflection`, `frozen_patch`, `belt_reader`, `connector_frame_sprites`, icons. **Never `util.recursive_tint`**: it also tints shadows and icons [C §10.1]. Belt animation sets are deep-copied before tinting; base shares `express_belt_animation_set` among 4 entities [L §0].
8. Keep `corpse` and `dying_explosion` (vanilla names are valid IDs [C §2.13]).
9. Set `surface_conditions` and `heating_energy` **explicitly** under `mods["space-age"]` from §7.3/§7.4 (never inherited implicitly; this makes the result independent of load order).

Graphics keys walked per type:

| type | keys |
|---|---|
| assembling-machine, furnace | `graphics_set` (+ `fluid_boxes[i].pipe_picture`) |
| mining-drill | `graphics_set`, `wet_mining_graphics_set` |
| transport-belt / underground-belt / splitter | one shared deepcopy of express `belt_animation_set` with only `animation_set` tinted; then `structure` (UG) or `structure` + `structure_patch` (splitter) [L §12.4] |
| accumulator | `chargable_graphics.picture` (charge/discharge animations are light overlays, untouched) |
| electric-pole | `pictures` |
| burner-generator | `animation` (4 directions), `idle_animation` |
| solar-panel | `picture` (the `overlay` is a shadow overlay and stays untouched) |
| wall | `pictures` (except `water_connection_patch`, `gate_connection_patch` shadows as flagged) |
| gate | `vertical_animation`, `horizontal_animation`, `*_rail_animation_*`, `*_rail_base`, `wall_patch` |
| electric-energy-interface | `picture` = base global `accumulator_picture(tint)`, as base builds its EEI [P §4, §8] |
| ammo-turret, electric-turret | `folded_animation`, `preparing_animation`, `prepared_animation`, `attacking_animation`, `folding_animation`, `graphics_set` (`energy_glow_animation` is glow and untouched) |

Tint blending is not documented; the inference is multiplicative [L §12.1], so every tint channel is ≥ 0.45 (a light multiplier). The world look is judged in the author's graphical client (PILOT-21, `/magnetics-showroom`).

### 4.2 Production and mining

Electric crafting machines draw `energy_usage` + drain while working; drain defaults to `energy_usage/30` [C §1], confirmed for AM2 by [PL] (AM2 150 kW + 5 kW + drill 90 kW = the measured 2.45 MJ per 10 s).

| entity | type ← vanilla base | size | key stats | modules / effects | HP | FRG / upgrades | tint (r,g,b) |
|---|---|---|---|---|---|---|---|
| `magnetics-sintering-kiln` | **assembling-machine ← stone-furnace** (type change CraftingMachine→CraftingMachine; the `graphics_set` type is the same; furnace-only keys `result_inventory_size`, `source_inventory_size`, `cant_insert_at_source_message_key`, `custom_input_slot_tooltip_key` removed) **[PILOT-2]** | 2×2 | speed 1; burner `{fuel_categories = {"chemical"}, effectivity = 1, fuel_inventory_size = 1, emissions_per_minute = {pollution = 2}}`, 90 kW; `fixed_recipe = "magnetics-ferrite"` [PILOT-16]; categories {sintering} | 0; `effect_receiver` as stone furnace (module/beacon off, surface on) [RB] | 200 | `magnetics-sintering-kiln` | 0.80, 0.62, 0.66 |
| `magnetics-induction-furnace` | **assembling-machine ← electric-furnace** (same conversion) **[PILOT-2]** | 3×3 | speed 2; 240 kW (drain 8 kW); pollution 1/min; categories {sintering, induction} | 2; 5 effects | 350 | `magnetics-induction-furnace` | 0.62, 0.72, 1.00 |
| `magnetics-coil-winder` | assembling-machine ← assembling-machine-2 | 3×3 | speed 1; 150 kW (drain 5 kW); pollution 3/min; **no base productivity**; categories {winding} | 2; 5 effects | 350 | `magnetics-coil-winder` | 1.00, 0.72, 0.50 |
| `magnetics-cryo-chamber` | assembling-machine ← chemical-plant (fluid boxes 2 in / 2 out kept; recipe-tinted WVs untouched) | 3×3 | speed 1; 300 kW (drain 10 kW); pollution 3/min; categories {cryogenics} | 3; 5 effects | 350 | `magnetics-cryo-chamber` | 0.70, 0.95, 1.00 |
| `magnetics-flux-resonator` | assembling-machine ← centrifuge | 3×3 | speed 1; **5 MW, drain 10 kW (explicit)**; pollution 0; categories {resonance}; `fixed_recipe = "magnetics-flux-crystal-charging"`; **quality-locked** (§7.5) | **0**; `effect_receiver = {uses_module_effects = false, uses_beacon_effects = false, uses_surface_effects = false}` | 350 | `magnetics-flux-resonator` | 0.82, 0.64, 1.00 |
| `magnetics-magnetic-separator` | assembling-machine ← assembling-machine-3 (fluid boxes kept) | 3×3 | speed 1; 250 kW (drain 8.33 kW); pollution 4/min; categories {separation} | 2; 5 effects | 400 | `magnetics-magnetic-separator` | 0.68, 0.78, 0.88 |
| `magnetics-magnetic-drill` | mining-drill ← electric-mining-drill | 3×3 | `mining_speed = 0.75`; 150 kW; pollution 15/min; `resource_searching_radius = 2.49` (5×5); `resource_categories = {"basic-solid"}`; input fluid box kept (uranium) | 3 | 400 | `mining-drill`; **`electric-mining-drill.next_upgrade = magnetics-magnetic-drill`** | 0.60, 0.72, 1.00 |

Fallback if PILOT-2 fails in any configuration: the kiln becomes `assembling-machine ← assembling-machine-1` art at 3×3 with identical stats, and the induction furnace becomes `assembling-machine ← assembling-machine-2` art, same size and stats. Only the look and the kiln's footprint change; the fallback is written into the PREREG.

### 4.3 Logistics (maglev tier)

| entity | type ← base | stats | HP | links | tint (animation and structure) |
|---|---|---|---|---|---|
| `magnetics-maglev-transport-belt` | transport-belt ← express-transport-belt | `speed = 0.15625` (40/256) → **75 items/s** (`speed × 480` [L §2]); `animation_speed_coefficient = 32` (kept [L §0]) | 180 (express 170 [RB]) | FRG `transport-belt`; `related_underground_belt` = maglev UG | 0.90, 0.62, 1.00 |
| `magnetics-maglev-underground-belt` | underground-belt ← express-underground-belt | speed 0.15625; **`max_distance = 13`** (vanilla 5/7/9/11 [L §0]) | 180 | FRG `transport-belt` | same |
| `magnetics-maglev-splitter` | splitter ← express-splitter | speed 0.15625 | 200 (express 190 [RB]) | `related_transport_belt` = maglev belt | same |

Upgrade chain (data-updates.lua): base `express-*.next_upgrade = magnetics-maglev-*`; SA `turbo-*.next_upgrade = magnetics-maglev-*` (SA keeps express→turbo). The maglev entities keep `next_upgrade = nil`.

### 4.4 Power

| entity | type ← base | size | stats | HP | FRG / upgrades | tint |
|---|---|---|---|---|---|---|
| `magnetics-coil-capacitor` | accumulator ← accumulator; `chargable_graphics` rebuilt from base globals `accumulator_picture(tint)`, `accumulator_charge()`, `accumulator_discharge()` [P §4] with every leaf `scale` × 0.5 and `shift` × 0.5; `circuit_connector = nil`; boxes `{{-0.4,-0.4},{0.4,0.4}}` / `{{-0.5,-0.5},{0.5,0.5}}` **[PILOT-21 look]** | 1×1 | buffer **1 MJ**; input and output **1 MW**; `tertiary` | 100 | `magnetics-coil-capacitor` | 1.00, 0.75, 0.55 |
| `magnetics-superconducting-accumulator` | accumulator ← accumulator | 2×2 | buffer **20 MJ**; in/out **1.2 MW** (vanilla 5 MJ / 300 kW [P §1]: same 16.7 s full-discharge time); `tertiary` | 250 | `accumulator`; **`accumulator.next_upgrade = ours`** | 0.65, 0.95, 1.00 |
| `magnetics-superconducting-pylon` | electric-pole ← big-electric-pole (`collision_mask` with `elevated_rail = true` kept [P §1]) | 2×2 | `maximum_wire_distance = 48`, `supply_area_distance = 2` | 250 | `big-electric-pole`; **`big-electric-pole.next_upgrade = ours`** | 0.65, 0.95, 1.00 |
| `magnetics-mhd-generator` | burner-generator ← base hidden `burner-generator` (steam-engine art, 3×5 [P §7.2]) | 3×5 | `max_power_output = "5.4MW"`; `burner = {type = "burner", fuel_categories = {"chemical"}, effectivity = 0.9, fuel_inventory_size = 2, emissions_per_minute = {pollution = 100}}`; output `secondary-output` | 400 | `magnetics-mhd-generator` | 1.00, 0.60, 0.45 |
| `magnetics-flux-dynamo` | burner-generator ← base hidden `burner-generator` | 3×5 | `max_power_output = "10MW"`; `burner = {type = "burner", fuel_categories = {"magnetics-flux"}, effectivity = 1, fuel_inventory_size = 1, burnt_inventory_size = 1, emissions_per_minute = {pollution = 0}}` | 500 | `magnetics-flux-dynamo` | 0.80, 0.60, 1.00 |
| `magnetics-geomagnetic-coil` | solar-panel ← solar-panel | 3×3 | `production = "20kW"`; **`solar_coefficient_property = "magnetic-field"`**, `performance_at_day = 1`, `performance_at_night = 1` (constant output); scaling by the field value **[PILOT-12]** | 200 | `magnetics-geomagnetic-coil` | 0.82, 0.75, 1.00 |

Fallback if the capacitor's scaled art is rejected on look (PILOT-21): a 2×2 "coil capacitor bank" with unscaled accumulator art, **4 MJ, 4 MW** (same per-tile capacity and flow). Fallback if `solar_coefficient_property` fails to load in base (PILOT-12): the base config keeps the default coefficient property and sets `production = "18kW"` (the H1 Nauvis value), so it is still constant day and night.

### 4.5 Walls, gates, mend coil

Walls are `wall ← stone-wall` and keep `fast_replaceable_group = "wall"`, the collision box, `visual_merge_group = 0` (they join stone walls visually) and `repair_speed_modifier = 2` [W §11.2]. Gates are `gate ← gate`, FRG `wall` [W §11.3]. Resistances are written `decrease/percent`.

| entity | HP | physical | impact | explosion | fire | acid | laser | electric | `attack_reaction` | upgrades | tint |
|---|---|---|---|---|---|---|---|---|---|---|---|
| (vanilla stone-wall [W §11.2]) | 350 | 3/20 | 45/60 | 10/30 | 0/100 | 0/80 | 0/70 | — | — | **→ ferrite wall** (set by us) | — |
| `magnetics-ferrite-wall` | 500 | 3/25 | 45/60 | 10/30 | 0/100 | 0/80 | 0/70 | 0/30 | — | → magnet wall | 0.62, 0.55, 0.60 |
| `magnetics-magnet-wall` | 800 | 5/30 | 50/65 | 15/35 | 0/100 | 0/85 | 0/75 | 0/50 | 5 electric per bite **[PILOT-11]** | → SC wall | 0.60, 0.70, 1.00 |
| `magnetics-superconducting-wall` | 1500 | 8/35 | 60/70 | 20/40 | 0/100 | 0/90 | **0/100** | **0/100** | 10 electric per bite | — | 0.70, 0.95, 1.00 |
| (vanilla gate [W §11.3]) | 350 | as stone wall | | | | | | | | **→ magnet gate** (set by us) | — |
| `magnetics-magnet-gate` | 800 | = magnet wall | | | | | | | = magnet wall | → SC gate | 0.60, 0.70, 1.00 |
| `magnetics-superconducting-gate` | 1500 | = SC wall | | | | | | | = SC wall | — | 0.70, 0.95, 1.00 |

`attack_reaction` (a field of EntityWithHealthPrototype, verified by the judges; base ships the pattern commented out [D:base/prototypes/entity/entities.lua:3383-3410]):
```lua
attack_reaction = {{
  range = 2, damage_type = "physical", reaction_modifier = 0,
  action = {type = "direct", action_delivery = {type = "instant",
    target_effects = {{type = "damage", damage = {amount = 5, type = "electric"}}}}}   -- 10 on SC wall/gate
}}
```
`reaction_modifier = 0` keeps the reflected damage a fixed number (the modifier formula is undocumented). Fallback if PILOT-11 shows the reaction does not hit the attacker: thorns are removed and nothing else changes.

**`magnetics-mend-coil`**: `electric-energy-interface ← electric-energy-interface` (base, hidden [P §8]), 2×2.
- `hidden = nil`, `gui_mode = "none"`, `allow_copy_paste = false`.
- `energy_source = {type = "electric", usage_priority = "secondary-input", buffer_capacity = "1MJ", input_flow_limit = "200kW", output_flow_limit = "0W"}`, `energy_production = "0W"`, `energy_usage = "0W"` **[PILOT-10]**.
- `picture = accumulator_picture({0.60, 1.00, 0.70, 1})` (base EEI pattern [P §4]).
- 300 HP; FRG `magnetics-mend-coil`. Behaviour: §6.

### 4.6 Turrets

All four turrets use their own name as FRG (the ammo differs from any vanilla turret). Ammo turrets use the SA railgun pattern `energy_source` + `energy_per_shot` [W §5.4] **[PILOT-6]**.

| entity | type ← base | size | stats | HP | tint |
|---|---|---|---|---|---|
| `magnetics-coilgun-turret` | ammo-turret ← gun-turret | 2×2 | `attack_parameters`: type projectile (kept), `ammo_category = "magnetics-slug"`, `cooldown = 24` (2.5 shots/s), `range = 20` (gun 18 [W §5]); `energy_source = {type = "electric", usage_priority = "primary-input", buffer_capacity = "200kJ", input_flow_limit = "250kW"}`, `energy_per_shot = "40kJ"`; `inventory_size = 1`, `automated_ammo_count = 10`; `rotation_speed = 0.015` (gun [W §5.1]) | 500 | 1.00, 0.70, 0.50 |
| `magnetics-gauss-turret` | ammo-turret ← gun-turret | 2×2 | `ammo_category = "magnetics-gauss"`, `cooldown = 60` (1 shot/s), **`range = 30`** (= medium worm; below big worm 38 [D:enemy-constants.lua:134-137]); `energy_per_shot = "250kJ"`, buffer 1 MJ, input 1 MW; `automated_ammo_count = 8`; `rotation_speed = 0.008` | 800 | 0.55, 0.65, 1.00 |
| `magnetics-arc-emitter` | electric-turret ← laser-turret | 2×2 | `energy_source = {type = "electric", usage_priority = "primary-input", buffer_capacity = "2MJ", input_flow_limit = "3MW", drain = "24kW"}` (laser drain 24 kW [W §5.2]); `attack_parameters = {type = "beam", cooldown = 60, range = 20, range_mode = "center-to-bounding-box", source_direction_count = 64, source_offset = <laser's>, ammo_category = "laser", ammo_type = {energy_consumption = "1MJ", action = <below>}}` | 1000 | 0.60, 0.95, 1.00 |
| `magnetics-rail-cannon` | ammo-turret ← gun-turret | 2×2 | `ammo_category = "magnetics-rail"`, `cooldown = 150` (0.4 shots/s), `range = 36`, `min_range = 4`, `health_penalty = -1` (prefers big targets, as the railgun [W §5.4]), `rotation_speed = 0.005`; `energy_per_shot = "4MJ"`, buffer 8 MJ, input 2 MW; `automated_ammo_count = 5` | 2000 | 0.78, 0.55, 1.00 |

The arc emitter uses ammo category `laser`, so the vanilla laser damage and shooting-speed research applies in both configurations with no appended effects [W §14.2–14.3].

Arc `ammo_type.action` (direct → instant; **all damage instant, beams cosmetic**, because beam `damage_interval` timing is undocumented [W §8]):
1. `nested-result` → chain `magnetics-arc-chain` (first; SA: "Chain effect must go first in case the beam kills the target" [W §9]);
2. `damage {amount = 45, type = "electric"}`;
3. `create-sticker "electric-mini-stun"` (base sticker: 40 ticks, movement × 0.2 [RB]);
4. `nested-result` → beam `magnetics-arc-beam` (`max_length = 22`, `duration = 20`, cosmetic).

### 4.7 Hidden helper prototypes

- `magnetics-arc-chain` (`chain-active-trigger`, core type [W §9]): `max_jumps = 4`, `max_range_per_jump = 6`, `jump_delay_ticks = 3`, `fork_chance = 0`, `fork_chance_increase_per_quality_level = 0.05` (API default 0.1 [W §9]; normal quality stays deterministic), `max_forks = 2`. Action: direct with two deliveries: instant `{damage 30 electric; create-sticker electric-mini-stun}` and beam `magnetics-arc-bounce-beam` (`duration = 20`, `add_to_shooter = false`, cosmetic).
- `magnetics-arc-beam`, `magnetics-arc-bounce-beam`: deepcopy of base `electric-beam` [RB] with `action = nil` (cosmetic; `damage_interval = 20` kept, it is required [W §8]).
- `magnetics-ferrite-slug-projectile`: deepcopy of `cannon-projectile` [W §7] with `direction_only = true`, **`piercing_damage = 30`**, `force_condition = "not-same"` (turrets behind walls never hit their own walls), `action` = instant `{damage 20 physical; create-entity "explosion-hit"}`, `final_action = nil`, `animation` = base `bullet.png` tinted `#6E5A62` **[PILOT-7]**.
- `magnetics-magnet-slug-projectile`: same, `piercing_damage = 150`, damage 32, tint `#6D86C9`.
- `magnetics-gauss-slug-projectile`: same, `piercing_damage = 400`, damage 90, tint `#9FB4FF`.
- Slug ammo types: `{target_type = "direction", action = {type = "direct", action_delivery = {type = "projectile", projectile = <p>, starting_speed = 1 (gauss 1.5), direction_deviation = 0.02, range_deviation = 0.02, max_range = 24 (gauss 34)}}}` plus `source_effects` `explosion-gunshot` [W §6.2].
- Rail ammo (hitscan line, SA railgun-ammo structure built from base-only parts [W §6.4, §10]): `{target_type = "direction", clamp_position = true, action = {type = "line", range = 36, width = 1.5, force = "enemy", range_effects = {type = "create-explosion", entity_name = "magnetics-rail-tracer"}, action_delivery = {type = "instant", target_effects = {{type = "damage", damage = {amount = 1200, type = "physical"}}}, source_effects = {{type = "create-explosion", entity_name = "explosion-gunshot"}}}}}` **[PILOT-8]**. Flux rail slug: `width = 2`, damage `{1800 physical}` + `{600 electric}`, same `range = 36` (no `range_modifier`).
- `magnetics-rail-tracer`: `explosion` with `rotate = true`, `beam = true`, `animations = {{filename = "__magnetics__/graphics/entity/rail-tracer.png", width = 64, height = 440, frame_count = 8, line_length = 8, draw_as_glow = true, blend_mode = "additive"}}`, `light = {intensity = 1.5, size = 16, color = {0.71, 0.55, 1.0}}` (the SA `railgun-beam` shape [W §10]). The PNG is a PIL gradient: a 6 px white core, a violet (#B58CFF) → cyan (#9FE8FF) halo, alpha fading 1.0 → 0 across the 8 frames. It is the only new world sprite: base has no line-beam sprite, and SA's path `__space-age__/…` is illegal in base games [L §12.2]. If PILOT-21 rejects it, `range_effects = nil` and nothing else changes.

---

## 5. Technologies (14)

Packs: A automation, L logistic, M military, C chemical, P production, U utility, S space, Met metallurgic, EM electromagnetic [T §2]. Every tech has `icon = "__magnetics__/graphics/technology/<name>.png"`, `icon_size = 256` [T §1.3]. No tech name ends in `-<number>`, so every tech needs its own locale keys [L §7]. Every vanilla prerequisite exists in all four configurations [T §3]; the SA-only prerequisites of T13 are added only under `mods["space-age"]`.

### 5.1 Tree

| # | technology | prerequisites | count × time | packs | unlocks (recipes) |
|---|---|---|---|---|---|
| T1 | `magnetics-ferrite-sintering` | automation-science-pack, stone-wall | 30 × 10 s | A | sintering-kiln, ferrite, ferrite-wall |
| T2 | `magnetics-electromagnetic-coils` | T1, automation-2 | 75 × 15 s | A L | coil-winder, coil |
| T3 | `magnetics-coilgun` | T2, gun-turret, military-2 | 100 × 15 s | A L | coilgun-turret, ferrite-slug |
| T4 | `magnetics-induction-smelting` | T2, advanced-material-processing-2 | 250 × 30 s | A L C | induction-furnace, magnet-alloy |
| T5 | `magnetics-magnetic-mining` | T4, electric-mining-drill | 250 × 30 s | A L C | magnetic-drill |
| T6 | `magnetics-magnetic-power` | T4, solar-energy, electric-energy-accumulators | 250 × 30 s | A L C | mhd-generator, coil-capacitor, geomagnetic-coil |
| T7 | `magnetics-magnetic-separation` | T4, advanced-oil-processing | 150 × 30 s | A L C | ferrofluid, magnetic-separator, stone-separation |
| T8 | `magnetics-magnetic-fortifications` | T3, T4, military-3, gate, repair-pack | 250 × 30 s | A L C M | magnet-wall, magnet-gate, magnet-slug, gauss-turret, gauss-slug, mend-coil |
| T9 | `magnetics-arc-emitter` | T4, laser-turret | 200 × 30 s | A L C M | arc-emitter |
| T10 | `magnetics-superconductivity` | T4, production-science-pack | 300 × 30 s | A L C P | cryo-chamber, liquid-nitrogen, superconducting-cable |
| T11 | `magnetics-superconducting-power` | T10, electric-energy-distribution-2, electric-energy-accumulators | 300 × 30 s | A L C P | superconducting-accumulator, superconducting-pylon |
| T12 | `magnetics-flux-energy` | T11, T7, utility-science-pack, uranium-processing | 500 × 30 s | A L C P U | flux-resonator, flux-dynamo, flux-crystal-growth, flux-crystal-charging |
| T13 | `magnetics-maglev-logistics` | **base:** logistics-3, T10, T7, utility-science-pack. **SA:** + turbo-transport-belt, electromagnetic-science-pack | **base:** 600 × 30 s. **SA:** 1000 × 60 s | **base:** A L C P U. **SA:** A L C P U S Met EM | maglev-transport-belt, maglev-underground-belt, maglev-splitter |
| T14 | `magnetics-superconducting-defense` | T8, T12, military-4, concrete | 500 × 45 s | A L C M P U | superconducting-wall, superconducting-gate, rail-cannon, rail-slug, flux-rail-slug |

**Reachability (must-fix J1/J2/J3).** `design/spec_check.py` builds each tech's transitive prerequisite closure from the real [RB] and [RS] dumps. It then requires every ingredient of every recipe the tech unlocks to be producible from start-enabled recipes, recipes unlocked in the closure, and mined resources (uranium ore only if `uranium-mining` is in the closure). Result on 2026-09-30: **0 problems in base, 0 in SA**. A negative control that drops `repair-pack` from T8 and T4 from T10 is caught (7 problems). Gaps the three designs had are closed:
- `automation-2` (AM2 in the winder) in T2;
- `gun-turret` in T3;
- `electric-mining-drill` in T5;
- `advanced-oil-processing` (light oil) in T7;
- `repair-pack` in T8;
- `electric-energy-accumulators` (accumulator) in T11;
- `uranium-processing` (centrifuge, U-238; its chain `uranium-mining` → `concrete` also covers the centrifuge's concrete [RB]) in T12;
- `concrete` (refined concrete) in T14.

The same check runs in-game as test S5 on the loaded prototypes.

Cost anchors [T §3, §4], [L §7]:
- T1 sits between electric-mining-drill (25×10 A) and steel-processing (50×5 A).
- T2 is next to automation-2 (40×15 A L) and logistic-science-pack (75×5 A).
- T3 is next to gate (100×30 A L).
- T4, T5 and T6 equal advanced-material-processing-2 and solar-energy (250×30).
- T7 is above lubricant (50×30 A L C) and advanced-oil-processing (75×30).
- T8 and T9 are next to laser-turret (150×30 A L M C).
- T10 and T11 are next to logistics-3 (300×15 A L C P).
- T12 and T14 are next to military-4 (150×45 A L C M U), below kovarex (1500×30).
- T13 SA = 2 × turbo-transport-belt (500×60 A L C P S Met).

### 5.2 Why this order
Red gives stone a job and a cheap wall. Green gives the coil and an early line defence. Blue is the alloy tier: the mid-game side-grades (drill, MHD, separator, geomagnetic coil). Blue+military is the fortification tier. Purple brings the cryogenic chain. Yellow brings the three late priced tiers (belts, walls/rail cannon, power transport). **No Magnetics tech is a prerequisite of any vanilla tech** (test S5).

### 5.3 Upgrade effects (no new upgrade techs; data-final-fixes.lua)

The mirroring runs in `data-final-fixes.lua`, i.e. after SA has rewritten `physical-projectile-damage-6/7` by index and replaced `laser-weapons-damage-5/6/7` [W §0.4, §14.3]. Effects are **appended, never inserted**, so SA's index writes stay valid. For every technology and every effect `e` in a snapshot of its `effects`:

| source effect | appended copies (same modifier) |
|---|---|
| `{type = "ammo-damage", ammo_category = "bullet", modifier = m}` | `ammo-damage` for `magnetics-slug`, `magnetics-gauss`, `magnetics-rail` |
| `{type = "gun-speed", ammo_category = "bullet", modifier = g}` | `gun-speed` for `magnetics-slug`, `magnetics-gauss`, `magnetics-rail` |
| `{type = "turret-attack", turret_id = "gun-turret", modifier = t}` | `turret-attack` for `magnetics-coilgun-turret`, `magnetics-gauss-turret`, `magnetics-rail-cannon` |

- Vanilla values carried over [W §14.2]: PPD-1..7 bullet +0.1/0.1/0.2/0.2/0.2/0.4/0.4 and gun-turret +0.1/0.1/0.2/0.2/0.2/0.4/0.7. Under SA, levels 6/7 are 0.2 on both [W §14.3], read at data-final-fixes time. WSS-1..6 bullet +0.1/0.2/0.2/0.3/0.3/0.4.
- The arc emitter is in category `laser` and needs nothing.
- Result: every Magnetics projectile turret scales **exactly** like the gun turret in each configuration, including the infinite PPD-7. This fixes the balance design's K10: the coilgun/gun-turret per-hit ratio is invariant under research (test K11).

---

## 6. Control-script features

### 6.1 Mend coil (the only runtime feature of the shipped mod)

**Purpose.** Bot-free, power-paid repair of walls and turrets. Vanilla repair needs robots and repair packs (2 EC + 2 gears, durability 300 [RB]). The coil trades packs for electricity and is slow on purpose: it maintains walls between waves.

**Constants** (in `control.lua`; exposed read-only through `remote.call("magnetics", "constants")`):

| constant | value | meaning |
|---|---|---|
| `RADIUS` | 10 | Euclidean distance (tiles) from coil position to target position |
| `PERIOD` | 30 ticks | heal cycle (`script.on_nth_tick(30)`) |
| `TARGET_CAP` | 5 HP per target per cycle | 10 HP/s per target, **no stacking** across coils |
| `COIL_BUDGET` | 10 HP per coil per cycle | 20 HP/s per coil |
| `J_PER_HP` | 5000 J | 100 kW at full budget |
| `QUEUE_CAP` | 100 entries per cycle | bounded work |
| `CELL` | 32 tiles | spatial grid cell (≥ 2 × RADIUS, so a 3×3 cell neighbourhood covers the radius) |
| `HEAL_TYPES` | wall, gate, ammo-turret, electric-turret, fluid-turret, artillery-turret, radar | never characters, vehicles, robots, production or logistics buildings |

**State (`storage`)**: `coils.list` (array of `{entity, unit, surface, x, y, force, budget, budget_tick}`), `coils.index[unit] → slot`, `grid[surface_index]["cx,cy"] → array of units` (insertion order), `force_coils[force_index] → count`, `queue` (array of `{entity, unit}`), `queued[unit] → true`, `cursor`.

**Registration.**
- Build events `on_built_entity`, `on_robot_built_entity`, `script_raised_built`, `script_raised_revive`, `on_entity_cloned`, plus `on_space_platform_built_entity` when `defines.events.on_space_platform_built_entity ~= nil`. All use the filter `{{filter = "name", name = "magnetics-mend-coil"}}` [H §1.2].
- On build: append the coil; `script.register_on_object_destroyed(coil)`. Then run **one** `find_entities_filtered{position, radius = RADIUS, force, type = HEAL_TYPES}` and enqueue damaged results. This one-off scan catches walls damaged before the coil existed.
- Removal through `on_object_destroyed` (`useful_id` = unit number): swap-remove from the list and the grid. The code also swap-removes invalid entries lazily.
- `on_init` and `on_configuration_changed` rebuild everything: scan `game.surfaces` in index order for `name = "magnetics-mend-coil"`, re-register, re-scan each radius.

**Damage detection (event-driven, zero idle cost).**
- `on_entity_damaged` is registered **only while at least one coil exists**. The filters are `{filter = "type", type = t}` for each `t` in `HEAL_TYPES` (mode `or`), then `{filter = "final-health", comparison = ">", value = 0, mode = "and"}` (LuaEntityDamagedEventFilter [W §13.4]).
- Biters being shot never reach Lua.
- The handler is O(1): if `force_coils[entity.force.index] > 0` and not `queued[unit]`, append.
- `on_load` repeats the conditional registration from `storage` (the standard deterministic pattern; `storage` is read-only there [H §1.2]).
- Registering or unregistering happens only when the coil count crosses 0↔1.

**Heal cycle (`on_nth_tick(30)`)**: return immediately if the queue is empty. Otherwise process up to `QUEUE_CAP` entries round-robin from `cursor`:
1. If the entity is invalid or at full health: swap-remove it; `queued[unit] = nil`.
2. Look at the 3×3 grid cells around the entity. Take the **first** coil in insertion order that is valid, same surface and force, within `RADIUS`, has `budget > 0` (the budget resets lazily when `budget_tick ~= game.tick`) and has `entity.energy ≥ J_PER_HP`.
3. If none qualifies: dequeue the entity when no coil covers it at all; otherwise keep it (the covering coil lacks power or budget this cycle).
4. Otherwise `h = min(max_health − health, TARGET_CAP, budget, floor(energy / J_PER_HP))`. Then `health += h` (writes are clamped [H §1.4]), `coil.energy −= h × J_PER_HP` (`LuaEntity.energy` is J, R/W [H §6.3]), `budget −= h`.
5. Visual: `rendering.draw_line{from = coil, to = entity, color = {0.4, 1, 0.6, 0.8}, width = 2, time_to_live = 20}`, at most 10 per cycle.

**Numbers:**
- A fully busy coil heals 20 HP/s and draws 100 kW.
- The 1 MJ buffer holds 200 HP of reserve and refills at 200 kW.
- A magnet wall goes from 0 to 800 HP in 80 s.
- A single medium biter bites 15 per 35 ticks [W §12], i.e. ≈ 25.7 raw dps, above the per-target 10 HP/s. The coil does not make walls invulnerable in combat.

**UPS cost:**
- No coils: no damage handler; the nth-tick handler returns at once.
- Coils idle (no damage): 0 damage-handler calls and one empty nth-tick call per 30 ticks.
- Per damage event on a `HEAL_TYPES` entity: one table lookup.
- Per cycle: ≤ 100 × (9 cells × coils per cell) distance checks. There is no `find_entities` in the steady state.
- Budget: tests U1/U2.

**Multiplayer determinism:**
- All state is in `storage`; decisions iterate arrays only, never `pairs` over hash keys.
- No `math.random`, no player-local data, no wall-clock time.
- `on_load` only re-registers handlers.
- Rendering objects are part of the synchronised game state.

**Remote interface** (read-only): `magnetics.constants()`, `magnetics.state()` → `{coils = n, queue = n, handler_registered = bool}`.

### 6.2 Deliberately not scripted
Thorns (`attack_reaction`), the flux loop, turrets, drills, belts and the geomagnetic coil are pure prototype data.

### 6.3 Test-mod only: `/magnetics-showroom`
The separate `magnetics-tests` mod registers the console command `/magnetics-showroom`. It:
- creates surface `magnetics-showroom` with lab tiles [H §2];
- places one of each of the 26 entities on a 6-tile grid, powered by an EEI, with ammo, fuel and a demo recipe set;
- places one vanilla base entity next to each, for comparison;
- if a player exists, calls `game.take_screenshot` for the whole grid and one close-up per entity, into `script-output/magnetics/showroom*.png`.

Headless, only the placement part runs (test G3). The author runs it in the graphical Steam client to get world pictures of every model.

---

## 7. Space Age, quality and elevated-rails rules

### 7.1 Load order and stages
- `info.json`: `"dependencies": ["base >= 2.0.0", "? quality >= 2.0.0", "? elevated-rails >= 2.0.0", "? space-age >= 2.0.0"]`, `"factorio_version": "2.0"`. The expected effect is that Magnetics loads after SA, so deepcopies in data.lua see SA's data-stage edits (SA runs `base-data-updates` from its data.lua [C §3], [L §1]). This is **[PILOT-1]**.
- The mod never relies on that order for correctness: `heating_energy` and `surface_conditions` are written explicitly (§4.1 step 9), and all cross-mod edits sit in later stages:

| file | contents |
|---|---|
| `data.lua` | categories, subgroup, items, fluids, recipes (TOP resolved by `mods["space-age"]`), entities (`make()`), helpers, technologies |
| `data-updates.lua` | vanilla `next_upgrade` links; SA machine category inserts; T13 SA prerequisites and packs |
| `data-final-fixes.lua` | bonus mirroring (§5.3); resonator quality lock over `data.raw.quality` (§7.5) |

### 7.2 Vanilla edits (complete whitelist; test S7 fails on anything else)
1. `next_upgrade` on vanilla entities: `stone-wall → magnetics-ferrite-wall`, `gate → magnetics-magnet-gate`, `electric-mining-drill → magnetics-magnetic-drill`, `accumulator → magnetics-superconducting-accumulator`, `big-electric-pole → magnetics-superconducting-pylon`, and `express-transport-belt/underground-belt/splitter → magnetics-maglev-*` (base) or `turbo-*` (SA). Each target keeps the source's box, collision mask and FRG, as the API requires [L §11], [C §10.2].
2. SA only: `crafting_categories` inserts on `electromagnetic-plant`, `cryogenic-plant`, `foundry` (§3).
3. Appended effects on `physical-projectile-damage-1..7` and `weapon-shooting-speed-1..6` (§5.3).

No locomotive, character, AM2/AM3 or lab edit. No vanilla recipe, cost or prerequisite change.

### 7.3 Surface conditions (SA only; written only when `mods["space-age"]`, because `SurfaceCondition` "Requires Space Age to use" [C §4])

| target | conditions |
|---|---|
| every one of the 26 Magnetics entities | `{property = "magnetic-field", min = 10}` (planet-side hardware; space platform = 0 [P §11.6]) |
| + `magnetics-sintering-kiln` | `{property = "pressure", min = 10}` (as stone furnace [C §3]) |
| + `magnetics-mhd-generator` | `{property = "pressure", min = 10}` (as boiler [P §11.5]) |
| recipe `magnetics-stone-separation` | `{property = "magnetic-field", min = 50}` (Nauvis 90, Fulgora 99; not Vulcanus/Gleba 25, Aquilo 10 [P §11.6]); stops a stone→iron bypass of Gleba's biological iron |

### 7.4 `heating_energy` (SA only; copied from each vanilla analogue [C §3], [L §10], [P §11.5], [M §1], [W §0.6], [RS])

| entity | value | vanilla analogue |
|---|---|---|
| induction furnace, coil winder, cryo chamber, flux resonator, magnetic separator, magnetic drill | 100 kW | respectively electric furnace, AM2, chemical plant, centrifuge, AM3, electric drill |
| maglev belt / underground belt / splitter | 10 kW / 250 kW / 40 kW | express 10/150/40, turbo UG 200 (+50 per tier) |
| MHD generator, flux dynamo | 50 kW | steam engine |
| coilgun, gauss, rail cannon, arc emitter | 50 kW | gun turret, laser turret |
| kiln, capacitor, SC accumulator, pylon, geomagnetic coil, walls, gates, mend coil | none | stone furnace, accumulator, poles, solar panel, walls, EEI: none |

### 7.5 Quality
- **Flux-loop locks** (data-final-fixes):
  - resonator `module_slots = 0`;
  - `effect_receiver` module/beacon/surface effects all false;
  - `crafting_speed_quality_multiplier[q] = 1` for every `q` in `data.raw.quality` (the field exists [C §4]);
  - `quality_affects_energy_usage` stays false;
  - charging recipe `allow_productivity = false`, `allow_quality = false`, `auto_recycle = false`;
  - growth recipe `allow_quality = false`, `auto_recycle = false`;
  - crystal items `auto_recycle = false`;
  - flux rail slug recipe `auto_recycle = false`.
  
  Hence no path makes a quality crystal or a recycled crystal, and no quality, module, beacon or productivity effect lowers joules per charge. Tests S9, E6 and Q3; a round trip ≥ 1.0 anywhere is a **release blocker**.
- Recycling: `auto_recycle = false` on ferrite, alloy, ferrofluid, LN2, SC cable, stone separation, growth, charging and the flux rail slug; every other recipe (buildings, coil, ammo) gets its vanilla-generated `magnetics-*-recycling`. The expected list is test S9.
- Placeable item names equal entity names, so recycling names resolve [T §5.4].
- Everything else inherits vanilla quality scaling:
  - pole reach +2 per level; legendary level 5 → pylon 58 ≤ 64 [P §3.1];
  - accumulator capacity × (1 + level) [P §4];
  - turret range × min(1 + 0.1 × level, 3) [W §16].

### 7.6 Elevated rails, asteroids, misc
- The pylon keeps the big pole's `collision_mask` including `elevated_rail` [P §1]. No other interaction.
- No new damage type (only physical and electric), so SA asteroid resistances are unchanged [W §0.7].
- `hard-solid` (SA only) is never referenced [M §1].
- SA-only names (`turbo-*`, `electromagnetic-plant`, `cryogenic-plant`, `foundry`, `metallurgic-science-pack`, `electromagnetic-science-pack`, `space-science-pack` as a T13 pack) appear only inside `if mods["space-age"]`.
- The rail tracer, icons and technology art are `__magnetics__` paths; no `__space-age__` path anywhere [L §12.2].

---

## 8. Balance justification

### 8.1 Materials (raw cost in ore units: 1 ore/stone = 1; plates = 1 ore; from vanilla recipes [RB])
- **Ferrite** (1 iron ore + 1 stone, 3.2 s) takes the same time as an iron plate [RB], and the kiln is a stone furnace (speed 1, 90 kW, pollution 2 [C §1]). A kiln column has the same throughput as a smelting column and needs a mixed ore/stone lane: an early logistics puzzle. It costs 1 iron ore per ferrite, so it is never free iron.
- **Coil** = 1 Fe + 1 stone + 2 Cu = 4 raw. An electronic circuit is 1 Fe + 1.5 Cu = 2.5 raw [RB]. The coil is a slightly dearer green intermediate.
- **Magnet alloy** = steel (5 Fe) + 2 ferrite (2 Fe + 2 stone) + 1 Cu = 10 raw. An engine unit is 9 Fe [RB]. It is the blue gating intermediate, and the 1 : 1 induction-furnace ratio (§3.4) is deliberate.
- **SC cable** ≈ 6.5 raw + 0.5 plastic + 10 LN2 per cable. It is the purple bottleneck, in the role of the processing unit.
- **Uncharged crystal** = 2 SC + 1 PU + 1 U-238 + 20 ferrofluid + 50 LN2. It is a reusable catalyst and a sink for surplus U-238 (99.3 % of uranium processing output [RB]).

### 8.2 Machines, mining, logistics
- **Kiln**: exactly the stone furnace. Niche: the only red/green ferrite source.
- **Induction furnace** (speed 2, 2 modules, 240 kW) is the electric furnace (2, 2, 180 kW [C §1]) with 60 kW more for alloying. It cannot smelt vanilla ores, so it never competes with the electric furnace.
- **Coil winder** (speed 1, 150 kW, 2 modules) sits between AM2 (0.75 / 150 kW) and AM3 (1.25 / 375 kW) [C §1]. It has **no built-in productivity** in base; SA's EM plant (+50 % [C §1]) is the specialist reward.
- **Cryo chamber**: a chemical-plant sibling (1 / 210 kW / 3 modules [C §1]) at 300 kW.
- **Flux resonator**: a deliberate 5 MW sink with every efficiency path locked (§7.5).
- **Magnetic separator**: 10 stone + 5 ferrofluid → 2 iron ore + 0.5 copper ore per 5 s, i.e. 0.4 Fe + 0.1 Cu ore/s from 2 stone/s. Four electric drills on stone (4 × 0.5 = 2 stone/s [M §1]) plus one separator give less than **one** electric drill on iron (0.5/s). Niche: stone-rich, iron-poor maps and surplus stone. Under SA it is Nauvis/Fulgora only.
- **Magnetic drill**: 0.75 speed = +50 % over the electric drill, same 5×5 area, in-place upgrade.
  - Per footprint tile: 0.75/9 = **0.083 ore/s < big drill 2.5/25 = 0.1** [M §1].
  - Energy per unit speed: 200 kW, vs the electric drill's 90/0.5 = 180 kW, so slightly less efficient.
  - Pollution per unit speed: 20/min, the vanilla rate (10/0.5 [M §1]).
  - Cost ≈ 3 electric drills. The big drill stays the best drill.
- **Maglev 75/s** is the next exact step of the vanilla +8/256 progression [L §0, §2], with the UG reach +2 (13).
  - Base: 45 → 75, but at **utility science** with SC cable and ferrofluid, i.e. one tier later than logistics-3 (purple).
  - SA: 60 → 75, only after turbo (Vulcanus) **and** electromagnetic science (Fulgora), at 2× the turbo tech cost.
  - One speed, one test in both configurations.

### 8.3 Power
- **Coil capacitor** (1×1, 1 MJ, 1 MW).
  - Per tile it holds 0.8× the accumulator's capacity (1 vs 1.25 MJ/tile) but moves **13.3×** its power (1 MW vs 75 kW/tile [P §1]).
  - Per MJ it costs ≈ 15× an accumulator (5 coils + 2 steel + 2 EC vs 2 Fe + 5 batteries per 5 MJ [RB]).
  - It is useless for night storage and good for bursts: a laser turret can pull 9.6 MW [W §5.2], which is 32 accumulators or 10 capacitors.
- **SC accumulator** (2×2, 20 MJ, 1.2 MW): 4× capacity with the vanilla 16.7 s full-discharge time. It is an in-place upgrade at purple and costs more per MJ than the vanilla accumulator. SA adds no accumulator tier [P §0.3].
- **SC pylon** (reach 48 = 1.5 × big pole 32 [P §1]): about the same cost per tile of line (big pole 31 raw / 32 tiles ≈ 0.97; pylon 54 raw / 48 tiles ≈ 1.1 [RB]) but a third fewer poles. 48 is chosen so legendary (+10) = 58 ≤ the API max 64 [P §3.1].
- **MHD generator** (3×5, 5.4 MW, effectivity 0.9).
  - 5.4 MW = 3 boilers (1.8 MW each [P §1]). The steam equivalent is 3 × (boiler 3×2 + 2 engines 3×5) = 108 tiles plus water; the MHD needs 15 tiles and no water.
  - It burns 11 % more fuel: 6 MW of fuel = 1.5 coal/s (coal 4 MJ [P §9.2]).
  - Pollution **100/min per 6 MW of fuel = 16.7/min per MW = the boiler's 30/min per 1.8 MW** [P §2.6], i.e. 11 % more pollution per MW delivered.
  - Niche: dense or water-less bases, deathworld perimeter power. It is far below SA's heating tower (40 MW, 250 % [P §11.4]).
- **Flux loop** (power transport, not generation).
  - Charging draws 5 MW × 25 s + 10 kW drain × 25 s = **125.25 MJ**; the crystal gives **100 MJ** in the dynamo (effectivity 1), so the round trip is **0.798**. Vanilla accumulators are lossless.
  - Niche: moving power by train, belt or robot to islands, outposts and other planets, pollution-free at the point of use.
  - 20 × 100 MJ per slot equals rocket fuel [P §9.2] and is far below a uranium fuel cell (8 GJ [P §9.2]), so nuclear logistics are untouched.
  - One 10 MW dynamo burns 0.1 crystals/s behind 2.5 resonators.
- **Geomagnetic coil** (3×3, 20 kW nominal × field factor, constant day and night).
  - Nauvis (90): 18 kW (H1: v/100) or 20 kW (H2: v/default); Fulgora 19.8/22; Vulcanus/Gleba 5/5.6; Aquilo 2/2.2; platform blocked.
  - Solar: 60 kW peak, 0 at night by default [P §5]; Fulgora solar-power 20 % [P §5].
  - Per tile: 2.0–2.2 kW constant. Solar is 6.7 kW/tile at peak. The day average and the accumulator ratio are community figures (not in recon): ≈ 42 kW average and ≈ 0.84 accumulators per panel, i.e. ≈ 3.4 kW/tile with storage.
  - So the coil is ≈ 0.6× solar-with-storage per tile on Nauvis: a compact "no night, no batteries" niche, not a replacement.
  - On Fulgora it beats solar's 12 kW peak, which is the memorable Fulgora niche. It still needs imported ferrite (Fulgora has no iron ore), and lightning remains Fulgora's bulk power.

### 8.4 Defence (vanilla references)
- Gun turret: 10 shots/s, range 18, HP 400; firearm 5 / piercing 8 / uranium 24 per shot → 50 / 80 / 240 dps [W §5, §6.2].
- Laser turret: range 24, 800 kJ/shot every 40 ticks, HP 1000 [W §5.2].
- Worm ranges 25/30/38/48 [D:enemy-constants.lua:134-137].
- Biters (HP, physical resist) [W §12]: small 15 (—), medium 75 (4/10 %), big 375 (8/10 %), behemoth 3000 (12/10 %).
- Resistance hypothesis H_res: `applied = (D − decrease) × (1 − percent/100)`, pinned by PILOT-3.

| turret (tier) | single-target raw dps | vs medium | vs big | vs behemoth | range | niche / why not creep |
|---|---|---|---|---|---|---|
| gun + firearm (A) | 50 | 9 | 0* | 0* | 18 | — |
| gun + piercing (A+L) | 80 | 36 | 0* | 0* | 18 | — |
| gun + uranium (A+L+C+M+U) | 240 | 180 | 144 | 108 | 18 | — |
| **coilgun + ferrite** (A+L) | **50** (20 × 2.5/s) | **36** | 27 | 18 | 20 | = firearm raw, = piercing vs armour (1.0×, J3's 1.0–1.3× band); pierces up to 3 small biters; needs 100 kW firing |
| **coilgun + magnet** (A+L+C+M) | **80** | 63 | 54 | 45 | 20 | = piercing raw one tier later; an armour answer before uranium, below uranium on every target |
| **gauss** (A+L+C+M) | **90** (90 × 1/s) | 77.4 | 73.8 | 70.2 | **30** | long-range anti-armour; ties medium worms (30), never out-ranges big worms (38); 250 kW per shot |
| **arc emitter** (A+L+C+M) | **45** + chain 4 × 30 | 45 | 45 | 45 | 20 | swarm control with electric damage (no base enemy resists electric [W §12]); single target 0.5–1.0× the laser (PILOT-15); total 165/shot < tesla 120 + 10 × 120 [W §5.5, §9] |
| **rail cannon** (…+M+P+U) | **480** per target in a 36-tile line (1200 / 2.5 s) | 431 | 429 | 428 | 36 | anti-behemoth lanes (3 shots per behemoth); 4 MJ/shot = 1.6 MW; far below SA railgun (10 000, range 40 [W §5.4, §6.4]) |

\* Under H_res the damage is ≤ 0; the engine's minimum-damage rule is not in sources [W §16].

Ammo cost per damage (raw ore units; vanilla firearm 50 dmg / 4 Fe = 12.5, piercing 80 / 7.5 = 10.7 [RB]):
- ferrite slug 200 / 14 = 14.3;
- magnet slug 320 / 24 = 13.3;
- gauss slug 360 / 25 = 14.4.

All three sit within 1.0–1.35× vanilla, unlike appeal's ≈ 4–5× (J1).

**Walls** (stone 350 HP = 10 stone = 35 HP/raw [W §11.2]):
- Ferrite 500 HP for a stone wall + 2 ferrite (14 raw) = 35.7 HP/raw, the vanilla rate.
- Magnet 800 HP; SC 1500 HP, with walls taking the previous tier as an ingredient.
- Against a behemoth bite (90 [W §12]) under H_res: stone takes 69.6 per bite (6 bites); SC takes 53.3 (29 bites).
- This closes the vanilla late-game "behemoths shred walls" gap at a yellow-science price (SC cable + refined concrete).
- **SC wall absorbs laser and electric (100 %)**, as in Mindustry ("absorbs lasers and lightning").

**Thorns**: magnet 5, SC 10 electric per bite.
- A small biter (15 HP, heals 0.35 per 35-tick bite [W §12]) dies on the 4th bite on a magnet wall and on the 2nd on an SC wall.
- A behemoth loses 0.3 % per bite.
- Flavour, not a turret substitute: the reason J1 rejected appeal's 25-thorn SC wall at blue.

**Mend coil**: 20 HP/s per coil, 5 kJ/HP, between-wave maintenance (§6.1).

### 8.5 Risks
1. **R1 Load order and SA overwrites.** SA replaces categories with `=` and edits techs by index [C §3], [W §0.4]; optional-dependency order is unverified [T §9.2]. Mitigation: all cross-mod edits in data-updates/data-final-fixes; explicit SA fields; PILOT-1; S7/S8 in every configuration.
2. **R2 Two type conversions and one scaled sprite.** Kiln and induction furnace (furnace art → assembling-machine, same `graphics_set` type) and the 1×1 capacitor. Mitigation: PILOT-2 load in B/BQ/BE/SA with same-size fallbacks; look via showroom (PILOT-21) with the 2×2 capacitor fallback.
3. **R3 Undocumented combat semantics**: resistance order, `piercing_damage` accounting, line `force`/width from an ammo turret, chain targeting, `attack_reaction` target, turret energy on an ammo turret in base, how ammo-damage and turret-attack combine [W §16]. Mitigation: PILOT-3/6/7/8/9/11/15 before PREREG. Every combat test also runs a vanilla control or a formula-free ratio (K11), so a wrong absolute formula does not flip conclusions.
4. **R4 Energy-loop exploits** (quality, beacons, efficiency modules, productivity, recycling, dynamo quality). Mitigation: §7.5 locks; legendary resonator and legendary dynamo tests; ratio ≥ 1 is a release blocker.
5. **R5 Perceived power creep.** 45 → 75 belts in base, SC walls at 4.3× stone HP, the MHD's density and the magnet slug are the numbers a veteran will question. Mitigation: each is late and priced, and defined by one `spec.py` constant; the T-W wave scenario measures the effect; the council reviews the measured result (CLAUDE.md council rule 4).
6. **R6 Mend coil UPS in battles** (damage-event storms). Mitigation: O(1) handler, conditional registration, `QUEUE_CAP`; U1/U2 benchmarks gate release. Fallback: `on_nth_tick(60)` and `QUEUE_CAP = 50`.
7. **R7 Quality range scaling.** Epic (1.3×) gauss reaches 39 > big worm 38 [W §16]. This is vanilla behaviour (a legendary laser reaches 36) and arrives only after epic-quality research (5000×60 [T §4.1]), when artillery is available. Documented, not changed.

---

## 9. Locale (`locale/{en,ru,de}/magnetics.cfg`)

Placeable items take their name from the entity (`[entity-name]`), and non-placeable items from `[item-name]` [T §8.4]. Every prototype below gets a name in en, ru and de and a short description in en and ru (de descriptions fall back to en). Test S11 parses the three files.

### 9.1 Items and fluids

| key | en | ru | de | en description | ru description |
|---|---|---|---|---|---|
| item magnetics-ferrite | Ferrite | Феррит | Ferrit | Iron ore sintered with stone into a magnetic ceramic. The core of every coil. | Железная руда, спечённая с камнем в магнитную керамику. Сердечник каждой катушки. |
| item magnetics-coil | Coil | Катушка | Spule | Copper cable wound on a ferrite core. The universal part of magnetic machines. | Медный кабель на ферритовом сердечнике. Универсальная деталь магнитных машин. |
| item magnetics-magnet-alloy | Magnet alloy | Магнитный сплав | Magnetlegierung | Steel, ferrite and copper fused by eddy currents. The base of blue-tier magnetic machines. | Сталь, феррит и медь, сплавленные вихревыми токами. Основа магнитных машин синего уровня. |
| item magnetics-superconducting-cable | Superconducting cable | Сверхпроводящий кабель | Supraleitendes Kabel | Magnet alloy in a plastic sheath, frozen by liquid nitrogen. Carries current without loss. | Магнитный сплав в пластиковой оболочке, замороженный жидким азотом. Проводит ток без потерь. |
| item magnetics-flux-crystal | Flux crystal | Кристалл потока | Flusskristall | A charged crystal holding 100 MJ. Fuel for the flux dynamo and the core of flux rail slugs. | Заряженный кристалл на 100 МДж. Топливо динамо-машины потока и сердечник рельсовой болванки потока. |
| item magnetics-flux-crystal-uncharged | Uncharged flux crystal | Незаряженный кристалл потока | Ungeladener Flusskristall | Charge it in a flux resonator. The flux dynamo returns it after use. | Заряжается в резонаторе потока. Динамо-машина потока возвращает его после разрядки. |
| item magnetics-ferrite-slug | Ferrite slugs | Ферритовые болванки | Ferritbolzen | Coilgun ammo. A slug pierces small enemies standing in a line. | Боеприпас катушечника. Болванка пробивает мелких врагов, стоящих на одной линии. |
| item magnetics-magnet-slug | Magnet slugs | Магнитные болванки | Magnetbolzen | Heavy coilgun ammo that keeps its punch against armour. | Тяжёлый боеприпас катушечника, не теряющий силы против брони. |
| item magnetics-gauss-slug | Gauss slugs | Болванки Гаусса | Gauß-Bolzen | Gauss turret ammo: one heavy hit that ignores most armour. | Боеприпас пушки Гаусса: один тяжёлый удар, почти не замечающий брони. |
| item magnetics-rail-slug | Rail slug | Рельсовая болванка | Schienenbolzen | Rail cannon ammo. Hits every enemy on a 36-tile line. | Боеприпас рельсовой пушки. Поражает всех врагов на линии длиной 36 клеток. |
| item magnetics-flux-rail-slug | Flux rail slug | Рельсовая болванка потока | Fluss-Schienenbolzen | A rail slug around a charged flux crystal: three shots with physical and electric damage. | Рельсовая болванка вокруг заряженного кристалла: три выстрела с физическим и электрическим уроном. |
| fluid magnetics-ferrofluid | Ferrofluid | Феррожидкость | Ferrofluid | Ferrite suspended in light oil. The lubricant of maglev belts and the bath of the magnetic separator. | Феррит во взвеси лёгкой нефти. Смазка маглев-конвейеров и ванна магнитного сепаратора. |
| fluid magnetics-liquid-nitrogen | Liquid nitrogen | Жидкий азот | Flüssigstickstoff | Liquefied from air in the cryo chamber. Cools superconductors. | Сжижается из воздуха в криокамере. Охлаждает сверхпроводники. |

### 9.2 Entities (placeable items share these)

| key | en | ru | de | en description | ru description |
|---|---|---|---|---|---|
| magnetics-sintering-kiln | Sintering kiln | Спекательная печь | Sinterofen | Burns fuel to sinter iron ore and stone into ferrite. | Сжигает топливо и спекает железную руду с камнем в феррит. |
| magnetics-induction-furnace | Induction furnace | Индукционная печь | Induktionsofen | Electric furnace for ferrite and magnet alloy. | Электропечь для феррита и магнитного сплава. |
| magnetics-coil-winder | Coil winder | Намоточный станок | Wickelmaschine | Winds copper cable onto ferrite cores. | Наматывает медный кабель на ферритовые сердечники. |
| magnetics-cryo-chamber | Cryo chamber | Криокамера | Kryokammer | Liquefies nitrogen from air, makes superconducting cable and grows flux crystals. | Сжижает азот из воздуха, делает сверхпроводящий кабель и выращивает кристаллы потока. |
| magnetics-flux-resonator | Flux resonator | Резонатор потока | Flussresonator | Charges flux crystals from the grid. A fifth of the energy is lost; modules, beacons and quality do not help. | Заряжает кристаллы потока от сети. Пятая часть энергии теряется; модули, маяки и качество не помогают. |
| magnetics-magnetic-separator | Magnetic separator | Магнитный сепаратор | Magnetabscheider | Separates iron and copper ore from stone in a ferrofluid bath. | Отделяет железную и медную руду от камня в ванне с феррожидкостью. |
| magnetics-magnetic-drill | Magnetic mining drill | Магнитный бур | Magnetbohrer | Upgrade of the electric mining drill: 50% faster on the same 5×5 area. | Улучшение электробура: на 50% быстрее на той же площади 5×5. |
| magnetics-maglev-transport-belt | Maglev belt | Маглев-конвейер | Magnetschwebeband | The fastest belt: 75 items per second. | Самый быстрый конвейер: 75 предметов в секунду. |
| magnetics-maglev-underground-belt | Maglev underground belt | Подземный маглев-конвейер | Unterirdisches Magnetschwebeband | 75 items per second, maximum distance 13. | 75 предметов в секунду, наибольшая длина 13. |
| magnetics-maglev-splitter | Maglev splitter | Маглев-разделитель | Magnetschwebe-Splitter | Splits and merges maglev lanes at 75 items per second. | Делит и сливает потоки маглев-конвейеров, 75 предметов в секунду. |
| magnetics-coil-capacitor | Coil capacitor | Катушечный конденсатор | Spulenkondensator | 1×1 storage: only 1 MJ, but moves 1 MW. For burst loads such as turrets. | Накопитель 1×1: всего 1 МДж, зато отдаёт 1 МВт. Для пиковых нагрузок, например турелей. |
| magnetics-superconducting-accumulator | Superconducting accumulator | Сверхпроводящий аккумулятор | Supraleitender Akkumulator | Four times the capacity and power of an accumulator on the same 2×2. | Вчетверо больше ёмкости и мощности, чем у аккумулятора, на тех же 2×2. |
| magnetics-superconducting-pylon | Superconducting pylon | Сверхпроводящая опора | Supraleitender Mast | Wire reach 48: a third fewer poles on long lines. | Дальность провода 48: на треть меньше опор на длинных линиях. |
| magnetics-mhd-generator | MHD generator | МГД-генератор | MHD-Generator | Turns chemical fuel into 5.4 MW without water. Loses a tenth of the fuel energy. | Превращает химическое топливо в 5,4 МВт без воды. Теряет десятую часть энергии топлива. |
| magnetics-flux-dynamo | Flux dynamo | Динамо-машина потока | Flussdynamo | Discharges flux crystals: 10 MW with no pollution and no water. | Разряжает кристаллы потока: 10 МВт без загрязнения и без воды. |
| magnetics-geomagnetic-coil | Geomagnetic coil | Геомагнитная катушка | Geomagnetische Spule | Draws power from the planet's magnetic field: a small, constant output by day and night. | Берёт энергию из магнитного поля планеты: небольшая постоянная мощность днём и ночью. |
| magnetics-ferrite-wall | Ferrite wall | Ферритовая стена | Ferritwand | A cheap early upgrade of the stone wall. | Дешёвое раннее улучшение каменной стены. |
| magnetics-magnet-wall | Magnet wall | Магнитная стена | Magnetwand | Its field shocks the biters that bite it. | Её поле бьёт током кусающих её жуков. |
| magnetics-superconducting-wall | Superconducting wall | Сверхпроводящая стена | Supraleitende Wand | Absorbs lasers and lightning and shocks attackers. | Поглощает лазеры и молнии и бьёт током нападающих. |
| magnetics-magnet-gate | Magnet gate | Магнитные ворота | Magnettor | A gate as strong as a magnet wall. | Ворота, прочные, как магнитная стена. |
| magnetics-superconducting-gate | Superconducting gate | Сверхпроводящие ворота | Supraleitendes Tor | A gate as strong as a superconducting wall. | Ворота, прочные, как сверхпроводящая стена. |
| magnetics-mend-coil | Mend coil | Ремонтная катушка | Reparaturspule | Repairs walls and turrets within 10 tiles from the power grid, 5 kJ per point of health. | Чинит стены и турели в радиусе 10 клеток за счёт электросети, 5 кДж на единицу прочности. |
| magnetics-coilgun-turret | Coilgun | Катушечник | Spulenkanone | An electric turret firing ferrite slugs that pierce small enemies. | Электрическая турель: ферритовые болванки пробивают мелких врагов. |
| magnetics-gauss-turret | Gauss turret | Пушка Гаусса | Gauß-Geschütz | A long-range turret whose heavy slugs break armour. | Дальнобойная турель, тяжёлые болванки которой пробивают броню. |
| magnetics-arc-emitter | Arc emitter | Разрядник | Bogenstrahler | Chain lightning that jumps through a swarm and slows it. | Цепная молния перескакивает по стае и замедляет её. |
| magnetics-rail-cannon | Rail cannon | Рельсовая пушка | Schienenkanone | Fires a slug through every enemy on a line. | Прошивает болванкой всех врагов на линии. |

### 9.3 Recipes with their own names, categories

| key | en | ru | de |
|---|---|---|---|
| recipe magnetics-liquid-nitrogen | Air liquefaction | Сжижение воздуха | Luftverflüssigung |
| recipe magnetics-flux-crystal-growth | Flux crystal growth | Выращивание кристалла потока | Flusskristallzucht |
| recipe magnetics-flux-crystal-charging | Flux crystal charging | Зарядка кристалла потока | Flusskristall laden |
| recipe magnetics-stone-separation | Magnetic stone separation | Магнитная сепарация камня | Magnetische Gesteinstrennung |
| ammo-category magnetics-slug | Coilgun slugs | Болванки катушечника | Spulenbolzen |
| ammo-category magnetics-gauss | Gauss slugs | Болванки Гаусса | Gauß-Bolzen |
| ammo-category magnetics-rail | Rail slugs | Рельсовые болванки | Schienenbolzen |
| fuel-category magnetics-flux | Flux | Поток | Fluss |

### 9.4 Technologies

| key | en | ru | de | en description | ru description |
|---|---|---|---|---|---|
| magnetics-ferrite-sintering | Ferrite sintering | Спекание феррита | Ferritsintern | Sinter iron ore with stone into ferrite; ferrite walls. | Спекание железной руды с камнем в феррит; ферритовые стены. |
| magnetics-electromagnetic-coils | Electromagnetic coils | Электромагнитные катушки | Elektromagnetische Spulen | Wind copper cable on ferrite cores. | Намотка медного кабеля на ферритовые сердечники. |
| magnetics-coilgun | Coilgun | Катушечник | Spulenkanone | An electric turret with piercing ferrite slugs. | Электрическая турель с пробивающими ферритовыми болванками. |
| magnetics-induction-smelting | Induction smelting | Индукционная плавка | Induktionsschmelzen | Fuse steel, ferrite and copper into magnet alloy. | Сплавление стали, феррита и меди в магнитный сплав. |
| magnetics-magnetic-mining | Magnetic mining | Магнитная добыча | Magnetischer Bergbau | A faster in-place upgrade of the electric mining drill. | Более быстрое улучшение электробура на том же месте. |
| magnetics-magnetic-power | Magnetic power | Магнитная энергетика | Magnetische Energie | MHD generator, coil capacitor and geomagnetic coil. | МГД-генератор, катушечный конденсатор и геомагнитная катушка. |
| magnetics-magnetic-separation | Magnetic separation | Магнитная сепарация | Magnetische Trennung | Ferrofluid, and ore recovered from stone. | Феррожидкость и руда, извлечённая из камня. |
| magnetics-magnetic-fortifications | Magnetic fortifications | Магнитные укрепления | Magnetische Befestigungen | Magnet walls and gates, magnet slugs, the gauss turret and the mend coil. | Магнитные стены и ворота, магнитные болванки, пушка Гаусса и ремонтная катушка. |
| magnetics-arc-emitter | Arc emitter | Разрядник | Bogenstrahler | A chain-lightning turret against swarms. | Турель с цепной молнией против стай. |
| magnetics-superconductivity | Superconductivity | Сверхпроводимость | Supraleitung | Liquid nitrogen from air and superconducting cable. | Жидкий азот из воздуха и сверхпроводящий кабель. |
| magnetics-superconducting-power | Superconducting grid | Сверхпроводящие сети | Supraleitendes Stromnetz | Superconducting accumulators and pylons. | Сверхпроводящие аккумуляторы и опоры. |
| magnetics-flux-energy | Flux energy | Энергия потока | Flussenergie | Grow and charge flux crystals; carry power where poles cannot reach. | Выращивание и зарядка кристаллов потока; энергия туда, куда не дотянуть провода. |
| magnetics-maglev-logistics | Maglev logistics | Маглев-логистика | Magnetschwebe-Logistik | Belts, undergrounds and splitters at 75 items per second. | Конвейеры, подземные конвейеры и разделители на 75 предметов в секунду. |
| magnetics-superconducting-defense | Superconducting defense | Сверхпроводящая оборона | Supraleitende Verteidigung | Superconducting walls and gates, and the rail cannon. | Сверхпроводящие стены и ворота и рельсовая пушка. |

---

## 10. Icons and pictures of every model

### 10.1 Rules
- All drawn by `tools/paint.py` (PIL; extends the existing `tools/iconkit.py`). Items, entities, fluids, recipes, ammo categories: 64×64 RGBA, `icon_size = 64`. Technologies: 256×256, `icon_size = 256` [T §1.3, §7]. Mod `thumbnail.png`: 144×144.
- Style: 2 px dark outline `#1A1A1F` at 64 px (6 px at 256), one top-left highlight, soft drop shadow (black, alpha 0.35, offset 2 px), transparent background. Same visual family as the Mindustry mod.
- **Palette** (Mindustry `spec.py` colours plus additions): ferrite `#5C4A52` (hi `#8A7580`, speckle `#B39FA8`); magnet alloy `#6D86C9` (N `#D9534F`, S `#F2F2F2`); coil copper `#D6854A` (dark `#8C4A22`); superconductor `#9FE8FF` (frost `#E8FBFF`, deep `#3AA6C9`); flux `#B58CFF` (glow `#E4D4FF`, deep `#5B3BA8`); uncharged grey `#8C8C99`; ferrofluid `#120F17` (sheen `#7A5CB8`); liquid nitrogen `#BFE6FF` (mist `#F0FAFF`); steel `#8E949E` (dark `#4A4F57`); electric arc `#9FE8FF`; heal green `#66FF99`.
- **Building icons**: a simplified top-down silhouette of the vanilla base in the entity's tint colour (§4), plus a small magnet glyph (a red/white horseshoe or field-line arcs) in the lower-right corner, so a Magnetics building is recognisable in any inventory.

### 10.2 Per-icon art direction (64 px)

| icon | subject and composition | colours |
|---|---|---|
| magnetics-ferrite | a hexagonal ceramic pellet, 3/4 view, with sinter speckles | ferrite palette |
| magnetics-coil | a toroid wound with 6 copper turns over a dark ferrite ring | copper `#D6854A`/`#8C4A22` on `#5C4A52` |
| magnetics-magnet-alloy | an ingot, 3/4 view, left half red N, right half white S, blue body | `#6D86C9`, `#D9534F`, `#F2F2F2` |
| magnetics-superconducting-cable | a flat-tape spool with a frost rim and 3 cyan sparkles | `#9FE8FF`, `#E8FBFF`, `#3AA6C9` |
| magnetics-flux-crystal | a faceted octahedron with a white core glow and 2 field-line arcs | `#B58CFF`, `#E4D4FF`, `#5B3BA8` |
| magnetics-flux-crystal-uncharged | the same octahedron, grey, 1 hairline crack, no glow | `#8C8C99`, `#5A5A66` |
| magnetics-ferrite-slug | a clip of 5 short dark cylinders | `#5C4A52`, brass clip `#C9A04A` |
| magnetics-magnet-slug | a clip of 5 blue cylinders with red tips | `#6D86C9`, `#D9534F` |
| magnetics-gauss-slug | 2 long heavy blue bolts crossed, with a cyan ring | `#6D86C9`, `#9FE8FF` |
| magnetics-rail-slug | one long dart with 2 cyan rails along it | `#8E949E`, `#9FE8FF` |
| magnetics-flux-rail-slug | the rail dart with a glowing violet crystal core | `#8E949E`, `#B58CFF` |
| magnetics-ferrofluid | a black droplet with the ferrofluid "spike crown" and a violet sheen | `#120F17`, `#7A5CB8` |
| magnetics-liquid-nitrogen | a pale-blue droplet with frost wisps | `#BFE6FF`, `#F0FAFF` |
| recipe magnetics-liquid-nitrogen | the LN2 droplet over a 3-line air swirl | + `#FFFFFF` |
| recipe magnetics-flux-crystal-growth | the uncharged crystal on a frost plate with 2 cyan drops | `#8C8C99`, `#9FE8FF` |
| recipe magnetics-flux-crystal-charging | the charged crystal with a yellow lightning bolt | `#B58CFF`, `#FFD84A` |
| recipe magnetics-stone-separation | a grey stone pile, an arrow, small iron-ore (blue-grey) and copper-ore (orange) nuggets | `#8A8A80`, `#6E7A8A`, `#C87533` |
| ammo-category magnetics-slug / gauss / rail | the ferrite-slug / gauss-slug / rail-slug motif on a round dark badge | as the items |
| magnetics-sintering-kiln | a squat 2×2 stone-furnace silhouette with a mauve body and an orange fire mouth | `#CC9EA8`, `#FF8A3D` |
| magnetics-induction-furnace | an electric-furnace silhouette in steel blue with 3 copper coil rings around the chamber | `#9EB8FF`, `#D6854A` |
| magnetics-coil-winder | an assembler silhouette in copper with a spool on top | `#FFB880`, `#D6854A` |
| magnetics-cryo-chamber | a chemical-plant silhouette in ice colour with frost on the tanks | `#B3F2FF`, `#E8FBFF` |
| magnetics-flux-resonator | a centrifuge silhouette in violet with a floating crystal above | `#D1A3FF`, `#B58CFF` |
| magnetics-magnetic-separator | an assembler silhouette in slate with a black ferrofluid bath and ore nuggets | `#ADC7E0`, `#120F17` |
| magnetics-magnetic-drill | an electric-drill silhouette in blue with a horseshoe magnet on the head | `#99B8FF`, `#D9534F` |
| magnetics-maglev-transport-belt / underground / splitter | the vanilla belt/UG/splitter icon shapes in violet with 2 thin cyan levitation lines | `#E69EFF`, `#9FE8FF` |
| magnetics-coil-capacitor | a small copper cylinder with 2 terminals and a coil band | `#FFBF8C`, `#D6854A` |
| magnetics-superconducting-accumulator | the accumulator's 2 tanks in ice colour with a frost band | `#A6F2FF`, `#E8FBFF` |
| magnetics-superconducting-pylon | a lattice pylon silhouette in ice colour with glowing cyan insulators | `#A6F2FF`, `#9FE8FF` |
| magnetics-mhd-generator | a steam-engine silhouette in orange with a plasma-blue channel along the body | `#FF9973`, `#6FC8FF` |
| magnetics-flux-dynamo | a steam-engine silhouette in violet with a crystal in its fuel window | `#CC99FF`, `#B58CFF` |
| magnetics-geomagnetic-coil | a solar-panel silhouette in lilac with overlaid Earth-like field-line loops | `#D1BFFF`, `#6D86C9` |
| magnetics-ferrite-wall / magnet-wall / superconducting-wall | the vanilla wall block, 3/4 view, in the tier colour; magnet: 2 small field arcs; SC: a frost edge | `#9E8C99` / `#99B3FF` / `#B3F2FF` |
| magnetics-magnet-gate / superconducting-gate | the vanilla gate shape in the tier colour | as walls |
| magnetics-mend-coil | an accumulator-like body in green with a white cross and green arcs | `#99FFB3`, `#66FF99` |
| magnetics-coilgun-turret | a gun-turret silhouette in copper with 3 coil rings on the barrel | `#FFB380`, `#D6854A` |
| magnetics-gauss-turret | a gun-turret silhouette in blue with a long barrel and 5 coil rings | `#8CA6FF`, `#6D86C9` |
| magnetics-arc-emitter | a laser-turret silhouette in cyan with a lightning fork from the tip | `#99F2FF`, `#9FE8FF` |
| magnetics-rail-cannon | a gun-turret silhouette in violet with 2 parallel rails as the barrel and a cyan muzzle glow | `#C78CFF`, `#9FE8FF` |

### 10.3 Technology icons (256 px)
Each tech icon is the main unlock drawn at 4× (from §10.2), centred on a circular field-line halo whose ring colour gives the tier:
- red `#D9534F` (T1);
- green `#5CB85C` (T2, T3);
- blue `#5BC0DE` (T4–T7);
- military pink `#E07AB8` (T8, T9);
- purple `#9B59B6` (T10, T11);
- yellow `#F0C419` (T12–T14).

The one exception is `magnetics-magnetic-power`: a 3-object composition (MHD, capacitor, geomagnetic coil).

### 10.4 Pictures for the author ("pictures of every model")
1. `showcase.png`: every icon (items, entities, fluids, recipes with their own icon, ammo categories, techs), each with its en and ru name. Same generator as the Mindustry `showcase.py`.
2. `cards.png`: one card per entity with our icon, "vanilla base: X", the tint as an (r,g,b) triple and a swatch, and the base colour × tint preview swatch.
3. `/magnetics-showroom` (§6.3): real world screenshots of all 26 entities next to their vanilla bases, taken in the author's graphical Steam client. Headless servers have no PNGs [C header], so this is the only way to see tinted world sprites.
4. `rail-tracer.png`: the procedural gradient strip, reviewed as an image.

---

## 11. Automated test plan (headless 2.0.77)

### 11.1 Configurations, harness, conventions
- **Configurations:**
  - B = base;
  - BQ = base + quality;
  - BE = base + elevated-rails;
  - SA = base + elevated-rails + quality + space-age.
- **Coverage:** static/load tests (S) run in all four. Functional tests (P, M, L, E, W, K, R, U) run in B and SA. Quality tests (Q, S9, the legendary part of E6) run in BQ and SA.
- **Pipeline**: `tools/run.py` (exists: `--create` then `--benchmark`, log and `script-output` collection, `MAGNETICS_RAW_BEGIN/END` dump), `tools/check_props.py` (exists), `tools/spec.py` (numbers → Lua, locale, icons, expected values), test mod `tools/magnetics-tests/` (exists: data-final-fixes dump; extend its control.lua with the cells).
- **Test-mod prototypes** (names `magnetics-test-*`, exempt from S2 by that prefix):
  - `magnetics-test-source`: EEI copy, `usage_priority = "primary-output"`, buffer 10 GJ, `energy_production = "500GW"`. The base EEI is `tertiary` [P §8] and did **not** charge a vanilla accumulator in 20 s [PL2: `acc_energy_20s = 0`].
  - `magnetics-test-sink`: EEI copy, `usage_priority = "secondary-input"`, buffer 100 MJ, input 1 GW. A tertiary sink cannot drain an accumulator.
  - `magnetics-test-target`: `simple-entity-with-force`, `max_health = 1e7`, `is_military_target = true`, no resistances, 1×1, placeable-enemy. A formula-free DPS target with no healing and no movement **[PILOT-14]**.
- **Lab**: `game.create_surface` + `generate_with_lab_tiles` + forced chunks [H §0, §2]; `force = "player"` on every create [H §0]; one substation island per cell (`auto_connect = false`) [H §6.3].
- **Enabling content**: recipes and bonuses by `technologies[t].researched = true` or `research_recursive()` [H §11].
- **Biters**: pinned with `stop` + `distraction.none`, `allow_destroy_when_commands_fail = false` [H §10.1]; test turrets `destructible = false` [W §13.2].
- **Power metering**:
  - consumers draw from a base EEI; energy = buffer delta [H §6.3], validated by [PL];
  - generators: `pole.electric_network_statistics.get_flow_count{name, category = "output", precision_index = five_seconds, count = false}` × 60 = W. [PL2] read 16 666.67 J/tick = 1.000 MW for the base 1 MW burner generator.
- **Crafting**: crafts/s = speed / energy [H §7]; counted from the output inventory. `products_finished` is only a cross-check until PILOT-4.
- **Timing**: 600-tick warm-up; 3600-tick window unless stated; 60 UPS.
- **Tolerance**: integer craft counts ± 1 (cycle phase); fluid ± 1 craft's worth; power ± 1–2 %; binomial products as mean ± 3σ.
  - The only random checks are P7 copper ore in B and in SA. At 3σ (two-sided 0.27 % each) the series-wide false-alarm level is ≤ 0.6 %; the band is a normal approximation, not an exact p.
  - Every other expectation is deterministic.
- **Truth and reporting**: expected values come from `spec.py`, which is committed with the PREREG. Results go to JSON through `helpers.write_file` [H §14]. Every number in the report is read from that JSON.

### 11.2 Static and load tests (prototype dump + `prototypes.*` introspection [H §13])

| id | measures | expected |
|---|---|---|
| S1 | load `--create` in B, BQ, BE, SA | exit 0; 0 log lines matching `Error`, `non-recoverable`, `stack traceback`; 0 `Warning` lines naming `magnetics` |
| S2 | name hygiene: prototypes present with the mod minus without it | all start with `magnetics-`. Allowed generated names: `magnetics-*-recycling` (BQ, SA). Zero `empty-magnetics-*` / `magnetics-*-barrel`. Zero names shared with `names_base.tsv` / `names_sa.tsv`. Counts: 26 entities, 37 items, 2 fluids, 40 recipes (+ recycling), 14 techs, 3 ammo categories, 1 fuel category, 6 recipe categories, 1 subgroup, 3 projectiles, 2 beams, 1 chain trigger, 1 explosion |
| S3 | property typos (`check_props.py` on the dump) | 0 unknown keys outside `vanilla_tolerated.json` |
| S4 | every number in §2–§5 against `spec.py` | ≈ 500 assertions, 0 failures. Examples: `get_crafting_speed()` 1/2/1/1/1/1 (kiln…separator); `energy_usage` 90/240/150/300/5000/250 kW (units by PILOT-5); `mining_speed` 0.75 and `get_mining_drill_radius()` 2.49; `belt_speed` 0.15625; `max_underground_distance` 13; buffer 1/20 MJ and flow 1/1.2 MW; `get_max_wire_distance()` 48, supply 2; `get_max_power_output()` 5.4/10 MW; burner effectivity 0.9/1.0; solar production 20 kW; turret range/cooldown 20/24, 30/60, 20/60, 36/150; `max_health` per §4; resistances per §4.5; stack sizes, fuel value 100 MJ, magazine sizes 10/10/4/1/3; every recipe's ingredients, products, probability, energy, category, Prod, AR; every tech's prerequisites, count, time, packs, effects |
| S5 | tech graph | 14 techs; prerequisites exist; acyclic; every Magnetics recipe `enabled = false` and unlocked by exactly one Magnetics tech; **reachability** (the `spec_check.py` algorithm on the in-game prototypes) 0 problems in all 4 configs; no vanilla tech has a Magnetics prerequisite; `research_all_technologies()` raises no error |
| S6 | upgrade links | exactly the §7.2 vanilla links plus ferrite→magnet→SC wall and magnet→SC gate. Each pair shares `collision_box`, `collision_mask` and `fast_replaceable_group`; the targets' items are not hidden; the chain ends have `next_upgrade == nil`; no other Magnetics entity has a `next_upgrade`; every copy's FRG matches §4 |
| S7 | vanilla untouched: field-level JSON diff of every vanilla prototype with vs without Magnetics | only the §7.2 whitelist differs, per config. Anything else fails |
| S8 | SA handling | **SA:** `surface_conditions` exactly per §7.3 on all 26 entities and the separation recipe; `heating_energy` exactly per §7.4; category inserts on EM plant, cryogenic plant and foundry; T13 prerequisites and packs as SA. **B/BQ/BE:** no Magnetics prototype has `surface_conditions` or `heating_energy`; T13 in base form; the no-SA-name grep over the mod's Lua outside `mods["space-age"]` blocks is empty |
| S9 | quality locks and recycling (BQ, SA) | resonator `get_crafting_speed(q)` = 1.0 for every `q` in `prototypes.quality`; `module_inventory_size` 0; effect receiver flags false; charging recipe `allow_productivity = false`, `allow_quality = false`; growth `allow_quality = false`. **No recycling recipe has a flux crystal (charged or uncharged) as ingredient or result.** The set of `magnetics-*-recycling` recipes equals the list `spec.py` derives from the [C §11.3] rules and §7.5 |
| S10 | fluids | both fluids `auto_barrel = false`; no recipe mentions them with "barrel" |
| S11 | locale (Python) | every key of §9 present in en/ru/de names and en/ru descriptions; no unused key |
| S12 | tint isolation | vanilla source entities (stone-furnace, electric-furnace, AM2, AM3, chemical-plant, centrifuge, EMD, express belt/UG/splitter, accumulator, big pole, burner-generator, solar panel, stone wall, gate, EEI, gun turret, laser turret) have leaf tints identical to a run without the mod (catches the shared `express_belt_animation_set` trap [L §0]); each copy has ≥ 1 tinted leaf and 0 tinted `draw_as_shadow`/`draw_as_glow`/`draw_as_light`/`apply_runtime_tint` leaves |
| S13 | icons | every referenced `__magnetics__` PNG exists and decodes; 64×64 (items, entities, fluids, recipes, ammo categories), 256×256 (techs), 512×440 (tracer), 144×144 (thumbnail) |
| S14 | bonus mirror (static) | for each tech: appended copies equal the source modifiers. **B:** PPD-6 bullet/turret 0.4/0.4, PPD-7 0.4/0.7. **SA:** PPD-6 and PPD-7 0.2/0.2 [W §14.2-14.3]. WSS-1..6 gun-speed 0.1/0.2/0.2/0.3/0.3/0.4 on the three Magnetics categories |
| S15 | range caps (static) | at normal quality every Magnetics turret range ≤ 36 and every line `range` ≤ 36; gauss range 30 |
| S16 | fixed recipes | kiln `fixed_recipe = magnetics-ferrite`; resonator `fixed_recipe = magnetics-flux-crystal-charging` |

### 11.3 Production (one machine per cell, unlimited inputs via infinity chest/pipe, full power or fuel, normal quality, no modules)

Expected = speed × t / energy crafts; power = `energy_usage` + drain [C §1].

| id | machine × recipe | window | expected | power |
|---|---|---|---|---|
| P1 | kiln × ferrite, coal fuel | 60 s | 18.75 crafts → **18–19 ferrite** | coal 90 kW × 60 s / 4 MJ = **1.35 coal** (± 1 item, fuel slot granularity) |
| P2 | induction furnace × ferrite; × alloy | 60 s each | **37–38 ferrite**; **18–19 alloy** | 248 kW ± 2 % |
| P3 | coil winder × coil | 60 s | 37.5 → **37–38 coils** | 155 kW ± 2 % |
| P4 | chemical plant × ferrofluid | 60 s | 60 crafts → **600 ± 10 ferrofluid** | 217 kW (vanilla plant [C §1]) |
| P5 | cryo chamber × air liquefaction; × SC cable; × crystal growth | 60 s; 120 s; 120 s | **1500 ± 50 LN2**; 12 crafts → **24 ± 2 cable**; **6 ± 1 uncharged crystals** | 310 kW ± 2 % |
| P6 | flux resonator × charging | 250 s | **10 ± 1 charged crystals**; energy per crystal **125.25 MJ ± 2 %** (5 MW × 25 s + 10 kW × 25 s) | 5.01 MW while working |
| P7 | magnetic separator × stone separation | 600 s | 120 crafts → iron ore **240 ± 2**; copper ore Binomial(120, 0.5): mean 60, σ = 5.48 → **[44, 76]**; ferrofluid used **600 ± 5** | 258.3 kW ± 2 % |
| P8 | SA only: EM plant × coil; foundry × ferrite; foundry × alloy; cryogenic plant × SC cable | 60 s each | 2 × 60 / 1.6 = 75 crafts × 1.5 = **111–114 coils**; 4 × 60 / 3.2 = 75 × 1.5 = **111–114 ferrite**; 4 × 60 / 6.4 = 37.5 × 1.5 = **55–57 alloy**; 2 × 60 / 10 = 12 crafts → **23–25 cable** | — |
| P9 | category isolation | — | `set_recipe("magnetics-coil")` on AM2 and AM3 fails in B and SA; the character cannot hand-craft ferrite, coil, alloy or cable |

### 11.4 Mining and logistics

| id | measures | expected |
|---|---|---|
| M1 | magnetic drill on 1 000 000 iron ore (mining_time 1), 60 s, EMD control in the same run | **45 ± 1** vs **30 ± 1** ([PL]: EMD 0.5/s); ratio **1.50 ± 0.05** |
| M2 | `mining_area` | 5×5 (right_bottom − left_top ≈ 4.977 as [PL]) |
| M3 | uranium ore + sulfuric acid via input fluid box, 60 s | > 0 ore; never `missing_required_fluid` |
| M4 | drill power | 150 kW ± 2 % (a drill adds no drain [PL]) |
| L1 | 40 maglev belts, `insert_at_back` / `clear` method [H §8] (validated at 45/s on express [PL]) | **75.0 ± 1.875 items/s** (one 1/256 quantum [L §2]); controls express 45.0 (B), turbo 60.0 (SA) |
| L2 | maglev UG pair in a belt line at distance 13 / 14 | 13: **75 ± 1.875** items/s; 14: the pair does not connect, throughput 0 |
| L3 | maglev splitter, 75/s in | each output **37.5 ± 1.875**; total 75 ± 1.875 |
| L4 | upgrade planner | `prototypes.entity[<TOP>-transport-belt].next_upgrade == "magnetics-maglev-transport-belt"` (same for UG and splitter); SA: `express-* → turbo-*` unchanged. Runtime: `order_upgrade` of one express (B) or turbo (SA) belt with an upgrade planner succeeds **[PILOT-25]** |

### 11.5 Power

| id | measures | expected |
|---|---|---|
| E1 | coil capacitor charged from `magnetics-test-source`, then discharged into `magnetics-test-sink` (demand 5 MW) | full at **1.00 MJ ± 1 %** after **60 ± 2 ticks**; discharge **1.00 MW ± 1 %** for 60 ± 2 ticks, then 0 |
| E2 | SC accumulator, same method | **20.0 MJ ± 1 %** after **1000 ± 2 ticks** (1.2 MW); discharge **1.20 MW ± 1 %** |
| E3 | pylon reach: `LuaWireConnector.connect_to(target, true)` / `can_wire_reach` between copper connectors [P §8] | 48.0 connects, 48.5 does not; big-pole control 32 / 32.5 [P §1]; supply 2: a 1×1 consumer 2.0 tiles off-centre is powered, 3.0 is not |
| E4 | MHD, coal, sink demand 10 MW, 60 s | **5.40 MW ± 1 %**; coal burnt 6 MW × 60 s / 4 MJ = **90 ± 2**; with solid fuel (12 MJ [P §9.2]) **30 ± 1**; pollution statistics for the entity **100/min ± 2 %** **[PILOT-18]** |
| E5 | flux dynamo, 10 charged crystals, sink demand 20 MW, 60 s | **10.0 MW ± 1 %**; **6 ± 1 crystals** burnt; the same count of uncharged crystals in the burnt slot; 0 pollution |
| E6 | flux round trip = E5 energy out per crystal / P6 energy in per crystal | **0.798 ± 0.016**. **BQ and SA:** a **legendary** resonator uses 125.25 MJ ± 2 % per crystal; a **legendary** dynamo gives 100 MJ ± 2 % per crystal. **Any ratio ≥ 1.0 is a release blocker** |
| E7 | geomagnetic coil; `surface.set_property("magnetic-field", v)` for v ∈ {0, 10, 25, 90, 99} [H §2.3]; sampled at `daytime` 0 (noon) and 0.5 (midnight) with `freeze_daytime` | linear in v, identical day and night (± 1 %). H1 (v/100): **0 / 2.0 / 5.0 / 18.0 / 19.8 kW**. H2 (v/90): 0 / 2.22 / 5.56 / 20.0 / 22.0 kW. PILOT-12 picks H1 or H2 **before** registration; the other becomes a failure |
| E8 | SA placement (`can_place_entity`) on a lab surface with pressure 1000 | all 26 Magnetics entities: **false** at magnetic-field 0, **true** at 10. Kiln and MHD: false at pressure 0 (magnetic-field 90) |
| E9 | SA separation recipe condition | separator running stone separation crafts at magnetic-field 90; status blocked (no crafts in 60 s) at 25 |

### 11.6 Walls and combat

The arc emitter and gauss per-hit numbers use H_res `applied = (D − decrease) × (1 − percent/100)`, anchored by PILOT-3 (stone wall, physical 100 → 77.6). If PILOT-3 finds another order, every H_res expectation below is recomputed from the pinned formula **before** registration. Hit counts and ratios are formula-free.

| id | measures | expected |
|---|---|---|
| W1 | `LuaEntity.damage(100, "enemy", type)` [H §10.3] on each wall/gate + stone-wall control, 8 damage types | **stone:** phys 77.6, impact 22, explosion 63, fire 0, acid 20, laser 30, electric 100, poison 100. **ferrite:** 72.75, 22, 63, 0, 20, 30, 70, 100. **magnet (and magnet gate):** 66.5, 17.5, 55.25, 0, 15, 25, 50, 100. **SC (and SC gate):** 59.8, 12, 48, 0, 10, **0, 0**, 100. ± 0.01 |
| W2 | max health | 500 / 800 / 1500 / 800 / 1500 (ferrite, magnet, SC walls; magnet, SC gates) |
| W3 | thorns: 1 medium biter commanded to `attack` each wall for 20 s (stone control) | per bite (wall damage event with `cause` = biter) the biter receives exactly one damage event with `cause` = wall: **5 electric** (magnet wall/gate), **10** (SC), **0** events (stone). Count(thorn events) = count(bites) ± 1 **[PILOT-11]** |
| W4 | small biters vs a magnet wall | a small biter dies on its 4th bite (H: 15 HP, 0.35 heal per 35-tick bite interval [W §12]); on an SC wall on the 2nd |
| K1 | coilgun on `magnetics-test-target`, 60 s, ferrite then magnet slugs | per hit **20 / 32**; **2.50 ± 0.05 shots/s** (magazine consumption: 10 shots per item) |
| K2 | coilgun vs 1 pinned medium biter | per hit (`final_damage_amount` [W §13.4]) **14.4** (ferrite) / **25.2** (magnet) (H_res) |
| K3 | pierce: 5 pinned small biters in a line 1 tile apart, 8 tiles out, one ferrite shot; 5 medium biters, one magnet shot | distinct biters damaged by the first slug: **3** (30 → 15 → 0 → < 0) and **3** (150 → 75 → 0 → < 0). Band [2, 3] until PILOT-7 pins the accounting |
| K4 | friendly fire: coilgun and gauss behind 3 own stone walls firing at biters beyond, 30 s | wall health unchanged (`force_condition = "not-same"`) |
| K5 | gauss on test target; on 1 big biter; range | per hit **90**; vs big **73.8** (H_res); **1.00 ± 0.02 shots/s**; a target at 29.5 tiles is engaged within 5 s, one at 30.5 never **[PILOT-17 pins the range metric]** |
| K6 | energy per shot (buffer delta / shots; EEI-fed) | coilgun **40 kJ**, gauss **250 kJ**, rail cannon **4 MJ**, arc emitter **1 MJ** (± 2 %). Pole removed: 0 shots, status `no_power` |
| K7 | arc emitter: 5 pinned medium biters 4 tiles apart in a chain; one shot | primary **45**, 4 bounces of **30** → total **165** (medium biters have no electric resistance [W §12]); exactly **5** distinct entities damaged; each gets the `electric-mini-stun` sticker. A stone wall 2 tiles from the cluster keeps full health **[PILOT-9]** |
| K8 | arc vs laser control (same run) on test targets, 60 s | laser DPS measured (L). Arc single-target DPS = 45 × 1.00 shots/s. **Ratio ∈ [0.5, 1.0]** (J1). If PILOT-15 finds L outside [45, 90], the arc primary damage is retuned before registration |
| K9 | rail cannon: 5 pinned behemoths on one line at 10–34 tiles, 1 behemoth 3 tiles off the line, 1 behemoth on the line at 37.5, 2 own stone walls on the line | each in-line behemoth takes **1069.2** per shot (H_res); off-line 0; the one at 37.5 takes 0 (line range 36); own walls 0 (`force = "enemy"`) **[PILOT-8]** |
| K10 | flux rail slug on test target | per shot **1800 physical + 600 electric**; 3 shots per item |
| K11 | bonus mirroring at runtime: research PPD-1..3 and WSS-1..3 (SA also 4..6) | force modifiers equal: `get_ammo_damage_modifier` of the 3 Magnetics categories = `bullet` (0.4 after PPD-3); `get_gun_speed_modifier` likewise; `get_turret_attack_modifier` of the 3 Magnetics ammo turrets = `gun-turret`. **Per-hit ratio coilgun-ferrite / gun-turret-firearm on test targets = 4.00 ± 1 % before and after research** (formula-independent; fixes balance K10) |
| K12 | range caps (runtime) | `prototypes.entity[t].turret_range` = 20 / 30 / 20 / 36 |
| T-W | wave scenario: 20 medium + 10 big biters with `attack_area` on a 3×3 turret block behind a 2-deep wall line; evolution and seed fixed. Variants: gun turrets + piercing; coilguns + magnet slugs; gauss; lasers; arc emitters; each with stone walls vs SC walls | reported per variant: time to clear, wall HP lost, turret losses, energy. **Pass:** all attackers dead within 120 s in every Magnetics variant; SC-wall variants lose ≤ ½ of the stone-wall variants' wall HP. The vanilla-vs-Magnetics comparison is post-hoc for the council and does not change pass/fail |

### 11.7 Mend coil (script)

Walls are damaged with `damage(X, "enemy", "poison")`. Walls have no poison resistance, so exactly X is applied. The call raises `on_entity_damaged`, which the event-driven design needs; a direct `health` write would not raise it [W §13.4].

| id | setup | expected |
|---|---|---|
| R1 | powered coil; magnet wall at 5 tiles damaged by 300; 600 ticks | healed **100 ± 5** (20 cycles × 5 HP) |
| R2 | 3 walls damaged by 300 each; 600 ticks | total healed **200 ± 10** (coil budget 10/cycle) |
| R3 | wall at 10.5 tiles | 0 healed; dequeued after one cycle |
| R4 | coil with no pole, buffer 0 | 0 healed |
| R5 | coil with no pole, `energy` preset to 1 MJ; 3 damaged walls; 300 ticks | healed **100 ± 5**; coil energy **500 kJ ± 1 %** → **5 kJ per HP** |
| R6 | two overlapping coils, 1 wall damaged 300; 600 ticks | healed **100 ± 5** (no stacking), not 200 |
| R7 | enemy-force wall in range | 0 healed |
| R8 | registration | a coil created with `raise_built = true` heals within 60 ticks; a destroyed coil causes no error and `remote.call("magnetics","state").coils` drops by 1; the damage handler is unregistered when the last coil is gone (`handler_registered == false`) |
| R9 | rebuild on configuration change | coils created by the test mod with `raise_built = false` after magnetics' `on_init`. Control run: 0 healed. Second run with the test-mod version bumped (triggers `on_configuration_changed` [H §1.2]): the rebuilt list contains every coil, and R1's expectation holds on them **[PILOT-19]** |
| R10 | determinism | R1–R7 run twice from fresh `--create`: byte-identical result JSON (hash) |
| R11 | save/load path | walls damaged and coils built in `on_init` (queue non-empty at save); in `--benchmark` (which loads the save, so `on_load` runs [H §1.2]) a wall damaged at tick 100 is queued and healed: `handler_registered == true` after load, and heal totals as R1 |

### 11.8 Quality (BQ and SA)

| id | expected |
|---|---|
| Q1 | legendary SC accumulator buffer = 20 MJ × (1 + 5) = **120 MJ** (`accumulator_capacity_multiplier` = 1 + level; legendary level 5 [P §3.1, §4]) |
| Q2 | legendary pylon: wire 48 + 2 × 5 = **58** (≤ 64), supply 2 + 5 = **7** [P §3.1] |
| Q3 | resonator `get_crafting_speed(q)` = 1.0 for all qualities; a legendary resonator's energy per crystal is as E6 |
| Q4 | no quality crystal exists: growth and charging `allow_quality = false`; S9's recycling rule holds |
| Q5 | legendary coil winder speed / normal = legendary AM2 speed / normal (a ratio; no quality number invented) |

### 11.9 UPS (`--benchmark`, 5 runs each, median of mean ms/tick; noise measured in PILOT-20)

| id | expected |
|---|---|
| U1 | a 10 000-entity map with 200 idle coils minus the same map with 200 unpowered accumulators: **Δ ≤ 0.02 ms/tick** |
| U2 | 100 coils around 1000 walls; the test mod damages 50 random-but-seeded walls every 60 ticks; minus the same map without coils: **Δ ≤ 0.10 ms/tick** |

### 11.10 Graphics

| id | expected |
|---|---|
| G1 | `showcase.png` contains every icon of §10.2/§10.3 with en and ru names (count = 26 entities + 11 items + 2 fluids + 3 recipes + 1 LN2 recipe + 3 ammo categories + 14 techs = **60 tiles**) |
| G2 | `cards.png`: 26 entity cards (icon, vanilla base, tint triple, swatches) |
| G3 | headless `/magnetics-showroom` (called by the test mod through `remote`/command on a lab surface): all 26 entities placed, 0 errors. Screenshots are only taken in the graphical client |

### 11.11 Niche report (computed from the JSON above; reported to the council; blockers marked)

| id | claim | computed from | pass |
|---|---|---|---|
| N1 | magnetic drill per footprint tile < big drill | M1: 0.75/9 = 0.083 vs 2.5/25 = 0.1 [M §1] | < 0.1 (blocker) |
| N2 | separator is worse than mining iron | P7: 0.4 Fe ore/s from 2 stone/s (= 4 electric drills) vs 0.5/s from 1 drill on iron | < 0.5 |
| N3 | MHD pollution per MW of fuel = boiler | E4: 100 / 6 = 16.7 vs 30 / 1.8 [P §2.6] | ± 2 % |
| N4 | capacitor: capacity per tile < accumulator, flow per tile ≫ accumulator | E1: 1 MJ, 1 MW per tile vs 1.25 MJ, 75 kW [P §1] | both |
| N5 | flux loop is energy-negative | E6 | < 0.8 + 2 % (blocker at ≥ 1.0) |
| N6 | ferrite slug ≈ firearm raw, ≈ piercing vs medium | K1/K2 vs the gun-turret control | 1.0–1.3× |
| N7 | arc single target 0.5–1.0× laser | K8 | in band |
| N8 | geomagnetic coil per tile on Nauvis ≤ 20 kW / 9 tiles | E7 at v = 90 | ≤ 20 kW (blocker) |

---

## 12. Rejected or changed ideas (and why)

| idea (source) | decision | reason |
|---|---|---|
| rechargeable 2 GJ crystal, recharge ≈ 50 MJ (appeal) | rejected | ≈ 36–40× energy return (J1, J2, J3). Replaced by 100 MJ out per 125.25 MJ in, with locks |
| flux crystal as locomotive fuel (appeal) | rejected | J1 explicit; it needs a vanilla locomotive edit; the transport niche is covered by the dynamo |
| geomagnetic coil at 40 kW, A+L (appeal) | changed | 20 kW nominal (≤ 20 kW on Nauvis), blue tier (J1, J3) |
| thorns SC wall at blue, 25 electric (appeal) | changed | SC wall at yellow, 10 electric; magnet wall 5 (J1) |
| magnet slug 45 dmg × 3/s at A+L+M (appeal) | changed | 32 dmg × 2.5/s at A+L+C+M = piercing raw (J1, J3) |
| unlimited-pierce hitscan coilgun slugs (engine) | rejected | projectiles with `piercing_damage` (J1, J2, J3) |
| MHD 20 pollution/min for 3.75 MW fuel (engine) | changed | 100/min per 6 MW fuel = boiler rate (J1) |
| base maglev at purple (engine) | changed | utility science (J1, J2, J3) |
| magnetic drill 1.0 speed / 7×7 / 4 modules (engine, appeal) | changed | 0.75, 5×5, 3 modules (J1, J3) |
| calutron p(U-235) = 0.01 (engine) | dropped | beats vanilla ore efficiency before Kovarex (J1, J2) |
| SA scrap separation with 2× holmium; Fulgora-only crystal recipe (appeal) | dropped | changes Fulgora's holmium pacing (J1) |
| pylon reach 64 (appeal) | changed | 48 → legendary 58 ≤ 64 (J2, J3) |
| mass driver on flamethrower art; gauss on laser art (balance) | changed | gun-turret art, same type (J1, J2) |
| arc damage through beams (balance) | changed | instant damage, cosmetic beams (J2) |
| "Mass driver" name (balance) | changed | "Rail cannon" (Mindustry continuity, J3) |
| cryo coolant from water + petroleum (balance) | replaced | liquid nitrogen from air plus ferrofluid (appeal's fluid chain, J1 and J3 best ideas) |
| SMES 10 MJ / 2.5 MW strict upgrade (engine) | replaced | SC accumulator 20 MJ / 1.2 MW keeps the vanilla discharge time (J2) |
| SC substation (engine) | replaced | SC pylon (big-pole upgrade, balance) |
| coil winder +25 % / +50 % base productivity (engine, appeal) | none | J3: at most 25 % or none; SA EM plant keeps +50 % |
| cryo chamber `heating_energy = 0` (balance) | changed | 100 kW like the chemical plant: no Aquilo special case |

---

## 13. File layout

`games/Factorio_Magnetics/`
- `magnetics/` (shipped mod, zipped as `magnetics_1.0.0.zip`):
  - `info.json` (§7.1), `thumbnail.png`, `changelog.txt`;
  - `data.lua`: `require` of `prototypes/{categories,items,fluids,recipes,technology}.lua` and `prototypes/entity/{make,production,logistics,power,defense,turrets,helpers}.lua`;
  - `data-updates.lua`, `data-final-fixes.lua` (§7.1);
  - `control.lua` (§6.1 only);
  - `locale/{en,ru,de}/magnetics.cfg`;
  - `graphics/icons/*.png` (64 px), `graphics/technology/*.png` (256 px), `graphics/entity/rail-tracer.png`.
- `tools/`:
  - `spec.py` (single source of truth → `magnetics/prototypes/spec_data.lua`, locale, `expected.json`);
  - `paint.py` / `iconkit.py` (icons, showcase, cards);
  - `run.py`, `check_props.py`, `vanilla_tolerated.json` (exist);
  - `magnetics-tests/` (harness: prototype dump, test prototypes of §11.1, cells, `/magnetics-showroom`);
  - `tests.py` (orchestrates the 4 configs and compares `results.json` with `expected.json`).
- `design/`: `recon/`, three designs, this `FINAL_SPEC.md`, `spec_check.py`.

---

## 14. Open questions for implementation pilot

Each pilot runs on a separate save or seed that never enters the registered tests. Its output and every number it changes go into the PREREG before the first registered run.

| # | question (source says "not found" or it is a new use) | pilot | decides / fallback |
|---|---|---|---|
| PILOT-1 | does `"? space-age"` load Magnetics after SA's data.lua? [T §9.2], [L §1] | log `express-transport-belt.next_upgrade` and AM2 `crafting_categories` from Magnetics' data.lua in SA | if not after: only cosmetic loss (frozen patches), because SA fields are explicit (§4.1 step 9) |
| PILOT-2 | do furnace-art `assembling-machine` copies (kiln, induction furnace) load and run in B, BQ, BE, SA? | load plus one craft of each | fallback: AM1 art (kiln, 3×3) / AM2 art (induction furnace), same stats |
| PILOT-3 | resistance order (decrease then percent?) [W §1.2, §16] | stone wall `damage(100, physical)` = 77.6? plus a biter with flat resistance | pins H_res for W1, K2, K5, K9 |
| PILOT-4 | `products_finished` for multi-product recipes [H §7] | separator cell | P7 metric |
| PILOT-5 | units of `energy_usage` introspection and EEI `power_usage` [H §6.3, §13] | AM1 75 kW calibration; EEI power_usage 1e6/60 | S4 units; power metering |
| PILOT-6 | ammo-turret with `energy_source` + `energy_per_shot` works in base (only the SA railgun uses it) [W §5.4] | coilgun cell: shots stop without power | fallback: turrets without energy use; ammo recipes +50 % cost |
| PILOT-7 | `piercing_damage` accounting (health before/after the hit), `force_condition = "not-same"` and `direction_only` projectiles fired by an ammo turret [W §7] | K3/K4 geometry | registers the exact pierce count; fallback `force_condition = "enemy"` |
| PILOT-8 | line trigger from an ammo turret: `force = "enemy"`, `width`, `range` measured from the turret, `clamp_position` [W §6.4, §10] | K9 geometry | line width and range expectations |
| PILOT-9 | chain-active-trigger: jumps, target choice, friendlies, whether laser bonuses scale chained damage, stickers from chain deliveries [W §9] | K7 plus research of laser-weapons-damage-1 | arc numbers |
| PILOT-10 | does a `secondary-input` EEI with `energy_usage = 0` charge its buffer? [H §6.3] | mend coil energy after 300 ticks = 1 MJ? | fallback 1: `energy_usage = "1W"`; fallback 2: set `power_usage` at runtime |
| PILOT-11 | `attack_reaction` target and trigger (every bite? the attacker? only physical?) [D:entities.lua:3383-3410] | W3 | fallback: thorns removed |
| PILOT-12 | `solar_coefficient_property = "magnetic-field"` loads in base; output scale v/100 (H1) or v/default (H2) [P §5] | E7 cell in B and SA | picks H1/H2; fallback: default property + 18 kW constant |
| PILOT-13 | negative `default_temperature` (−196) in base; empty-ingredient recipe runs in the cryo chamber [C §11.1] | P5 LN2 cell in B | fallback: LN2 at 15 °C (display only) |
| PILOT-14 | `magnetics-test-target` (`simple-entity-with-force`, `is_military_target`) is targeted by ammo, electric and line turrets; pinned biters stay put when shot [H §10.1] | 60 s per turret | fallback: frozen behemoth plus `final_damage_amount` sums |
| PILOT-15 | laser-turret DPS baseline (beam `damage_interval` × `damage_modifier` semantics [W §5.2, §8]) | laser on test target, 60 s | retunes arc primary damage into the [0.5, 1.0] band |
| PILOT-16 | `fixed_recipe` on a burner assembling machine (kiln) and on the resonator; `disabled_when_recipe_not_researched` behaviour [C §4] | craft before and after research | fallback: no `fixed_recipe`, recipe set by player |
| PILOT-17 | turret engagement distance metric (`range_mode`; center-to-center vs bounding box) for gun-turret copies | K5 at 29.5 / 30.5 | pins K5 distances |
| PILOT-18 | pollution per entity via `game.get_pollution_statistics(surface)` flow by prototype name | E4 | fallback: static `emissions_per_minute` check only |
| PILOT-19 | a test-mod version bump fires `on_configuration_changed` for Magnetics [H §1.2] | R9 | fallback: bump Magnetics' own version in the pilot copy |
| PILOT-20 | benchmark noise (5 runs) of the 10 000-entity map | U1/U2 | thresholds kept only if ≥ 3× the noise; otherwise relaxed before registration |
| PILOT-21 | look: tints (multiplicative?), scaled 1×1 capacitor, rail tracer, mend-coil picture | author runs `/magnetics-showroom` in the Steam client | fallbacks in §4.4, §4.7; tints retuned in `spec.py` only |
| PILOT-22 | lab surface property defaults and `set_property` for pressure/magnetic-field in B and SA [H §2.3] | log `get_property` for all properties | E7/E8 set-up |
| PILOT-23 | does quality change a burner generator's energy per fuel item (dynamo)? | legendary dynamo energy per crystal | release blocker if > 125 MJ per crystal |
| PILOT-24 | how on_entity_damaged filters combine `or`/`and` modes; does the filter list exclude biters | fire damage on a biter and a wall; count handler calls | fallback: filter by type only, check health in Lua |
| PILOT-25 | runtime upgrade-planner orders (`order_upgrade`) on a headless lab surface for belt, wall and drill links | order one of each; bots not needed: check `to_be_upgraded()` and the target prototype | L4/S6 runtime part; fallback: static link check only |
