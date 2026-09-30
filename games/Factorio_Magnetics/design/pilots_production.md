# Pilots and test results: production, mining, logistics (P1–P9, M1–M4, L1–L4)

Date 2026-09-30. Factorio 2.0.77 headless. Pilots ran on a separate scratch copy of the test mod, with their own cells. They never entered the registered cells. Every number below was read from the result JSON of the run named next to it.

Files:
- `tools/magnetics-tests/cells/production.lua` (P1–P9);
- `tools/magnetics-tests/cells/logistics.lua` (M1–M4, L1–L4).

Expected values were typed from FINAL_SPEC §11.3–11.4, not taken from `spec.py` or `expected.lua`.

## 1. Pilots settled

| pilot | question | experiment | measured |
|---|---|---|---|
| PILOT-2 | Do the furnace-art `assembling-machine` copies (kiln, induction furnace) load and craft? | Load, then 60 s of crafting in **B, BQ, BE and SA** | They load and craft in all 4 configurations. Crafts per 60 s (Δ products_finished + progress): induction furnace ferrite **37.5**, alloy **18.75**; kiln 19 crafts (2 → 21). Identical in all 4. The fallback is not needed. |
| PILOT-4 | What does `products_finished` count for a multi-product recipe? | Separator, 60 s and 600 s | It counts **crafts, not items**. Over 60 s: Δpf = 12 while the output was iron ore 24 + copper 4. Over 600 s: Δpf 120, iron ore 240. With productivity (SA EM plant, coil) Δpf = 113 = items made, so **bonus crafts are counted too**. The cryogenic plant (cable ×2, no productivity) gave Δpf 12 for 24 cables. |
| PILOT-13 | Does −196 °C load in base, and does the empty-ingredient recipe run in the cryo chamber? | Prototype readout; LN2 cell in B, BQ, BE, SA | `default_temperature` = −196 and `max_temperature` = −196 in all 4 configurations. The recipe runs: **30.0 crafts per 60 s → 1500 LN2**, output temperature **−196**. The fallback is not needed. |
| PILOT-16 | Does `fixed_recipe` work on the burner kiln and on the resonator? What happens before research? | Build both with T1/T12 **not** researched, observe for 300 ticks, research at tick 300, observe to tick 3000 (B and SA, identical numbers) | The fixed recipe is set at `create_entity` (kiln `magnetics-ferrite`, resonator `magnetics-flux-crystal-charging`). `set_recipe(nil)` and `set_recipe("magnetics-magnet-alloy")` raise **no error and are silently ignored**; the recipe stays. `recipe_locked` = false. **Both machines craft before research**: status `working` from tick 1, kiln 1 product by tick 290, resonator progress 0.193 at tick 290. This matches the API default "`disabled_when_recipe_not_researched` defaults to true if `fixed_recipe` is not given", i.e. false here. It is harmless in play: the kiln and the resonator are unlocked by the same technology as their fixed recipe (T1, T12). The fallback is not needed. |
| PILOT-25 | Do runtime upgrade orders work on a headless lab surface? | `order_upgrade{force, target}` and an `upgrade-planner` item with `set_mapper` + `LuaSurface.upgrade_area`, in B and SA | Every order returned true, `to_be_upgraded()` = true, and `get_upgrade_target()` = the Magnetics target. Covered: express→maglev belt, UG and splitter (B); turbo→maglev (SA); EMD→magnetic drill; stone wall→ferrite wall; the planner on a belt. **Caveat, measured by negative control:** with `next_upgrade` removed from the express/turbo belt, both runtime orders **still succeed**. `order_upgrade` and a planner with an explicit mapping do not read `next_upgrade`. Only the static half of L4 guards the link. |

## 2. Method facts measured (used by the cells)

- **Power meter.** Base `electric-energy-interface` (tertiary), `power_production = 0`, buffer 1e10 J, one substation with `auto_connect = false`. Power = buffer Δ / window. Calibration: AM2 on gears **155 000.0 W** = 150 kW + 5 kW drain. Runtime `energy_usage` of AM1 reads 1250, i.e. J/tick (PILOT-5 side result).
- **Lab surface properties** (B, BQ, BE, SA alike): magnetic-field 90, pressure 1000, gravity 10, solar-power 100. SA placement and the separation recipe condition (≥ 50) are therefore satisfied on the lab.
- **Fluid boxes.** Capacity is recipe-scaled. The separator's ferrofluid input has volume 1000 but `get_capacity` 10 (2 × 5). The cryo chamber's LN2 output has volume 100, capacity 200. Writes above capacity are clamped. `LuaFluidBox.get_prototype(i)` returns either **one** `LuaFluidBoxPrototype` (AM3-based separator, drill) or **a list** (chemical-plant-based cryo chamber).
- **Burner accounting** (kiln, 60 s window): coal items 9 → 8, `remaining_burning_fuel` 3 144 900 → 1 744 900 J, heat 1600 → 1600. Energy = 4 MJ + 1.4 MJ = **5.400 MJ** = 90 kW × 60 s exactly.
- **Belts.** Insert at the back of both lines of the first belt every tick; on the last belt, remove every item with `position ≥ line_length − 0.5` (`DetailedItemOnLine.stack.clear()`). Express **45.0**, maglev **75.0** items/s. Clearing the whole last belt gives the same 45.0; `line_length` of one straight belt = 1, `total_segment_length` of 40 belts = 40.
- **UG "distance".** The difference of the input and output tile positions. Control: express (`max_distance` 9) connects at 9, not at 10.
- **Drills.** `drop_target` reads nil right after the chest is created, but the ore still arrives in the chest. The drill fluid box has `production_type` "none", volume 200, no filter. Uranium: 23 ore per 60 s at speed 0.75 (mining time 2).

## 3. Registered results (combined run `production,logistics`, 36 610 ticks)

| config | pass | fail | work dir |
|---|---|---|---|
| base | **62** | 0 | `/tmp/mgn_base_eate12sp` |
| sa | **69** | 0 | `/tmp/mgn_sa_sukja37i` |

Separate runs gave the same pass counts: production B 39/39, SA 43/43; logistics B 23/23, SA 26/26. The only random check is P7 copper ore: **61** (B), **63** (SA; 65 in the separate run), band [44, 76].

Main numbers (B = SA unless noted):

| test | result |
|---|---|
| P1 | ferrite 19; coal 1 item; 5.40 MJ |
| P2 | 38 ferrite, 19 alloy, 248.0 kW |
| P3 | 38 coils, 155.0 kW |
| P4 | 600 ferrofluid, 217.0 kW |
| P5 | LN2 1500 at −196 °C; cable 24; crystals 6; 310.0 kW ×3 |
| P6 | 10 crystals; 125.25 MJ per crystal; 5.010 MW |
| P7 | iron ore 240; ferrofluid 600; 258.33 kW; Δpf 120 |
| P8 (SA) | coils 113, ferrite 113, alloy 57, cable 24 |
| M1 | 45 vs 30, ratio 1.50 |
| M2 | 4.9765625 × 4.9765625 |
| M3 | 23 ore, 0 ticks `missing_required_fluid` |
| M4 | 150.0 kW |
| L1 | 75.0; control express 45.0 (B), turbo 60.0 (SA) |
| L2 | 13: connected, 75.0; 14: not connected, 0 |
| L3 | 37.5 + 37.5 = 75.0 |
| L4 | all links as spec |

**Negative control** (scratch copy of the mod with mutations appended to data-final-fixes):
- The mutations: belt speed 0.125, UG 14, drill 0.5 / 90 kW / radius 3.49, kiln speed 2, furnace speed 1, winder 180 kW, cryo drain 20 kW, resonator 4 MW, separator speed 1.25, AM2 + winding, LN2 −150, copper p 0.25, ferrofluid ×12, character + cryogenics, SA: EM plant loses winding and foundry speed 3, TOP-belt `next_upgrade` removed.
- Result: 29 of 62 checks failed in B and 32 of 69 in SA.
- Every mutation was caught by at least one check.
- The L4 runtime half did not fail on the `next_upgrade` removal (see PILOT-25).

## 4. Deviations found

- **Mod vs spec:** none in this area.
- **Spec assumptions contradicted by the engine:** none.

## 5. Open issues and notes for other owners

1. **Shared harness bug: `lib.lua` `L.topup` and `L.drain`.**
   - The line `local proto = p[1] or p` raises `bad argument #2 of 3 to '__index' (string expected, got number)` whenever `get_prototype(i)` returns a single `LuaFluidBoxPrototype`. Reproduced on the separator (AM3 copy); the drill's fluid box is the same kind.
   - Proposed fix, both functions:
     ```lua
     local proto = fb.get_prototype(i); if proto.object_name == nil then proto = proto[1] end
     ```
   - My cells use local helpers and do not depend on it.
2. **Shared-force side effect.** My cells research Magnetics technologies at setup (benchmark tick 1). This enables their recipes for the whole `player` force in any combined run. Magnetics techs carry only `unlock-recipe` effects, so bonuses (K11) are unaffected. A cell that checks runtime `force.recipes[..].enabled == false` must not share a run with them.
3. **`L.power` placement.** It places the test source at `origin − 6`, which lies in the neighbouring slot. My cells do not use it.
4. **Weak P9 case.** The cable hand-craft check cannot fail on the category alone, because the recipe has a fluid ingredient. The P9 check "character categories contain no `magnetics-*`" covers it (it caught the character + cryogenics mutation).
5. **Not run.** BQ and BE functional runs (§11.1 runs functional tests in B and SA only). PILOT-2 and PILOT-13 were piloted in all four configurations.
