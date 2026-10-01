# Pilots and test results: power and quality (E1–E9, Q1–Q5, E6 legendary part)

Date 2026-09-30. Factorio 2.0.77 headless. The pilots ran on a scratch copy of the test mod, with their own cells (`pilot_power`, `pilot_quality`, `pilot_q2`, `pilot_q3`). They never entered the registered cells. Every number below was read from the result JSON of the run named next to it.

Files:
- `tools/magnetics-tests/cells/power.lua`: E1–E9. E8 and E9 run only in SA.
- `tools/magnetics-tests/cells/quality.lua`: Q1–Q5, plus `E6Q`, the legendary part of E6. Configs `{"bq"}`, which the harness runs in BQ, BQE and SA.

Expected values were typed from FINAL_SPEC §11.5, §11.8, §4.4, §7.5 and §8.3. They were not taken from `spec.py` or `expected.lua`.

## 1. Pilots settled

| pilot | question | experiment | measured (B, BQ and SA identical unless noted) |
|---|---|---|---|
| PILOT-12 | Does `solar_coefficient_property = "magnetic-field"` load in base? Does output scale as v/100 (H1) or v/default (H2)? | Geomagnetic coil on its own surface, `freeze_daytime`. 10 phases of 120 ticks over v ∈ {0, 10, 25, 45, 90, 99} × daytime {0, 0.25, 0.35, 0.5}. Test-load energy measured over 60 ticks. Vanilla solar panel as a control. | It loads and works in B, BQ and SA. Output: **0 / 2222.2 / 5555.6 / 10000 / 20000 / 22000 W** for v = 0 / 10 / 25 / 45 / 90 / 99. Day and night are identical. That is **H2 = 20 kW × v / 90**; H1 is rejected. The solar control read 60 000 W at noon, 30 000 W at daytime 0.35 and 0 W at midnight, so the daytime setting works. `get_max_energy_production()` = 333.33 J/tick. |
| PILOT-18 | Can pollution be read per entity from `pollution_statistics`? | MHD with coal on the lab, on nauvis and on a fresh `create_surface` surface. Traces of `get_input_count`, `get_output_count` and `get_flow_count`. | It works on every surface. A fresh `create_surface` surface has `pollutant_type = "pollution"`. Emissions go to **input** counts, keyed by entity name; output = 0. One MHD reads **100.000/min** (nauvis; own surface 100.000001). **The counter is summed over every entity of that name on the surface:** two MHDs on the lab read 200/min. E4 therefore runs its coal MHD alone on its own surface. The five-seconds/one-minute `get_flow_count` averages lag at window edges (199.95 instead of 200), so the test uses the cumulative count. |
| PILOT-22 | Surface property defaults on a planet-less `create_surface` surface; does `set_property` work in B and SA? | Read every `prototypes.surface_property` on the lab, a fresh surface and nauvis; `set_property` and read back. | The lab and fresh surfaces read **magnetic-field 90, pressure 1000, gravity 10, solar-power 100, day-night-cycle 300** in B, BQ and SA. These equal the prototype `default_value`s. Nauvis reads day-night-cycle 25200. `set_property` works in base and SA and reads back exactly (25, 0). **No validation:** −5 is accepted and read back. `planet = nil` and `ignore_surface_conditions = false` on lab and fresh surfaces. |
| PILOT-23 | Does quality change a burner generator's energy per fuel item? | Normal and legendary dynamo (10 crystals each) and MHD (100 coal each). Test-load energy between successive fuel takes. BQ and SA. | **No.** Legendary dynamo: **100.000 MJ per crystal**, 240 ticks per crystal (normal: 100.000 MJ, 600 ticks). `get_max_power_output("legendary")` = 25 MW for the dynamo (normal 10) and 13.5 MW for the MHD (normal 5.4). The MHD gives 3.600 MJ per coal at both qualities. Only the power scales (×2.5); energy per item does not. **Not a release blocker.** Legendary round trip = 0.7984. |

## 2. Method facts measured (used by the cells)

- **Tick origin.** `setup` runs at relative tick 0; the first `tick(ctx, t)` call is t = 1. My first E7 run set phase 1 at t = 0, which never ran (see §5).
- **Storage charge/discharge.** The coil capacitor starts at 0 J. It charges at exactly 16 666.67 J/tick from t = 1 and is full at **t = 60** (999 999.99999 J, float). It then discharges into a 5 MW-demand test load at exactly 16 666.67 J/tick for **60 ticks**, then 0.
- **Generators.** The MHD and the dynamo deliver full power from tick 1; there is no warm-up. The burner `heat` stays 0 (MHD `heat_capacity` 90 kJ). The MHD takes a new coal every 40 ticks (6 MW of fuel). The **burnt result appears when the next item is taken** (or when the last one finishes), so at a take tick the burnt slot = items taken − 1.
- **Generator metering.** `get_flow_count{category = "output", five_seconds, count = false}` × 60 and the test-load buffer delta agree to 1e-7. The load uses `power_usage = 0` and a 10 GJ buffer, so its demand is far above the spec's 10 and 20 MW. This is more sensitive than a capped demand.
- **Wire reach** is the Euclidean distance between entity positions, with ≤ max. The pylon connects at 48.0 but not at 48.0104 (48, 1), 48.5 or 49. The big pole connects at 32 but not at 32.0156 or 32.5. `create_entity{snap_to_grid = false}` places a 2×2 pole and a 1×1 lamp at exact half-tile positions (48.5, +2.0, +3.0).
- **Supply area.** Lamp collision box ±0.148. At pylon supply 2, lamps at +1.5 and +2.0 are powered; +2.5 and +3.0 are not.
- **`can_place_entity` and surface conditions (SA).** `build_check_type` `script` and `script_ghost` **ignore** surface conditions (true at magnetic-field 0). `manual`, `manual_ghost`, `blueprint_ghost` and `ghost_revive` (the default) enforce them. Thresholds are inclusive: 9.99 is false and 10 is true. `LuaSurface.ignore_surface_conditions = true` makes all of them true. A mining drill needs ore under it for a manual check.
- **Recipe surface conditions (SA, stone separation, magnetic-field ≥ 50):**
  - At magnetic-field 25, `create_entity{recipe = ...}` **silently drops the recipe**. `get_recipe()` = nil, status `no_recipe`, 0 crafts.
  - But a script `set_recipe("magnetics-stone-separation")` on the same surface is **accepted and crafts** (12 crafts in about 60 s).
  - A separator started at 90 keeps crafting after the property drops to 25.
  - So a script can bypass the condition; the player's GUI path cannot (not tested here).
- **Quality.**
  - The roll only yields qualities the force has unlocked. Before `LuaForce.unlock_quality`, a legendary AM2 with 12.4 % quality made 0 quality gears in 206 crafts. After it, 19 of 193 were quality.
  - A crafter whose recipe has `allow_quality = false` **rejects** quality modules: 0 of 3 inserted. It **ejects** them on `set_recipe`: 3 inserted, all 3 returned by `set_recipe`.
  - A legendary uncharged crystal cannot be inserted into a resonator: the fixed normal recipe gives an empty input.
- **Quality scaling not stated in the spec (information for balance):**
  - legendary accumulator in/out flow also scales ×2.5, so the legendary SC accumulator charges at 3 MW (50 000 J/tick) and the vanilla one at 750 kW;
  - legendary burner-generator power scales ×2.5;
  - legendary crafting speed: winder 2.5, AM2 1.875.
- **Isolation.** Surface properties, daytime and pollution statistics are surface-wide. E4 (coal MHD), E7, E8 and E9 therefore use their own small lab surfaces (`magnetics-power-E4`, `-E7`, `-E8`, `-E9-mf90`, `-E9-mf25`). All other cells stay in their 128×128 slot on `magnetics-lab`. Q4 calls `unlock_quality` and E9/Q4 research Magnetics techs; both are force-wide. Combined runs with the production and logistics modules show no interference (below).

## 3. Registered results

| run | config | pass | fail | work dir |
|---|---|---|---|---|
| `power` | base | **59** | 0 | `/tmp/mgn_base_xjpghxoe` |
| `power` | sa | **119** | 0 | `/tmp/mgn_sa__lnmy49n` |
| `quality` | bq | **41** | 0 | `/tmp/mgn_bq_9hshu7uq` |
| `quality` | sa | **41** | 0 | `/tmp/mgn_sa_932jf42e` |
| `smoke,production,logistics,power,quality` | sa | 230 | 0 | `/tmp/mgn_sa_t9kjymxv` |
| `smoke,production,logistics,power,quality` | base | 122 | 0 | `/tmp/mgn_base_h144pb29` |

Main numbers (B = SA):

| test | result |
|---|---|
| E1 | full 1 000 000 J at tick 60; discharge 1.000 MW for 60 ticks; then 0 |
| E2 | full 20 000 000 J at tick 1000; discharge 1.200 MW for 1000 ticks; then 0 |
| E3 | pylon 48 connects, 48.5 does not; big pole 32 / 32.5 likewise; lamp +2.0 powered, +3.0 not |
| E4 | 5.400 MW (statistics and load); coal 90; solid fuel 30; pollution 100.000/min |
| E5 | 10.000 MW; 6.0 crystals burnt (7 taken, 100 MJ left in the burning one); burnt slot 6; pollution 0 |
| E6 | round trip **0.79840** (100.000 MJ out / 125.250 MJ in) |
| E7 | 0 / 2222.2 / 5555.6 / 20000 / 22000 W, day = night |
| E8 (SA) | 26/26 false at magnetic-field 0 and true at 10; kiln and MHD false at pressure 0; controls OK |
| E9 (SA) | 11 crafts at 90; 0 at 25 (recipe refused, `no_recipe`) |
| Q1 | legendary SC accumulator 120 000 000 J (buffer and after charge); vanilla control 30 MJ |
| Q2 | legendary pylon 58 (≤ 64) connects, 58.5 does not; supply 7: lamp +7 powered, +8 not |
| Q3 | resonator speed 1.0 at all 6 qualities; legendary 125.25 MJ per crystal |
| Q4 | growth/charging `allowed_effects.quality = false`; 0 recycling recipes with a crystal; growth 37 crystals, all normal, 0 quality modules accepted/kept; control SC cable 126 made, 20 (BQ) / 28 (SA) quality |
| Q5 | 2.5 = 2.5 |
| E6Q | legendary resonator 125.25 MJ, legendary dynamo 100.000 MJ, round trip 0.79840 |

**Negative control** (scratch copy of the mod, mutations appended to its `data-final-fixes.lua`):
- The mutations: capacitor 2 MJ; SC accumulator 25 MJ, out 1 MW; pylon reach 50, supply 3; MHD effectivity 1.0, pollution 50; dynamo effectivity 1.3, pollution 5; geomagnetic coil without `solar_coefficient_property`; resonator `crafting_speed_quality_multiplier` removed; growth `allow_quality = true`; SA only: coil winder and MHD lose their magnetic-field/pressure condition, stone separation loses its recipe condition.
- Result: power B 28 of 59 failed, SA 31 of 119; quality BQ 21 of 41, SA 21 of 41.
- Every mutation was caught by at least one check. The dynamo mutation made the round trip 1.038 (B/SA) and 2.59 (legendary without the resonator lock), and the blocker checks fired.

## 4. Deviations found

**Mod vs spec: none in this area.**

**Spec assumptions settled or contradicted by the engine:**

1. **PILOT-12 picks H2.**
   - The spec offered both hypotheses; the pilot decides.
   - Consequences for the spec text:
     - §4.4: "18 or 20 kW on Nauvis" → **20 kW**;
     - §8.3: Nauvis 20, Fulgora 22, Vulcanus/Gleba 5.56, Aquilo 2.22 kW;
     - E7's expected row is H2, and H1 becomes the failure.
   - **Niche check N8** ("≤ 20 kW at v = 90, blocker") will read 20000.000000000004 W (float), so a strict `≤ 20000` fails. Proposed fix in the niche report: `≤ 20 kW × (1 + 1e-6)`, or the §11.1 power tolerance.
2. **E9 wording.** "status blocked" does not describe what the engine does. At magnetic-field 25 the recipe is refused at creation (status `no_recipe`), and the separator does not stop while holding the recipe. The test checks the parenthetical "no crafts in 60 s" and records the status. Proposed spec text: "at 25 the recipe is not accepted (`get_recipe()` nil, status `no_recipe`), 0 crafts in 60 s".
   - Also note: a **script** `set_recipe` bypasses the condition. This is an engine behaviour, not a mod bug, and matters only to scripted set-ups.
3. **E8 method.** The spec does not name a `build_check_type`. `script` would pass every entity everywhere, so the test uses `manual`.
4. **§7.5 lists only the quality capacity scaling.** Legendary also scales accumulator flow (×2.5 → SC accumulator 3 MW) and burner-generator power (dynamo 25 MW, MHD 13.5 MW). This is information for the balance section, not a failure.

## 5. My errors caught before registration

- E7 first registered run: phase 1 was set at t = 0, which the harness never calls. So v = 0 read 20 kW (the lab default 90). Fixed by starting phases at t = 1.
- E8 first run: a mining drill cannot be placed manually without ore under it, so it read false at magnetic-field 10. Fixed by putting 3×3 iron ore under the probe position, with an electric-mining-drill control.
- Q4 first version:
  - The quality-module control assumed that modules alone produce quality. They do not, until the quality is unlocked for the force.
  - The first dynamic check also "passed" trivially, because the growth chamber had silently rejected its modules (0 inserted).
  - Both points are now explicit checks.

## 6. Open issues and notes for other owners

1. The niche report (N8) needs a float tolerance (see §4.1).
2. §4.4 and §8.3 text: replace "18 or 20 kW" with the H2 values.
3. Any test that sets a recipe by script on a surface with changed properties must use `create_entity{recipe = ...}`, not `set_recipe`: `set_recipe` ignores recipe surface conditions.
4. Any cell that reads pollution statistics must be the only one with that entity name on its surface.
