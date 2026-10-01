# Pilots and test results: walls and combat (W1–W4, K1–K12, T-W)

Date 2026-10-01. Factorio 2.0.77 headless, configs B (base) and SA (base + ER + Q + SA).

The pilots ran on a scratch copy of the test mod. That copy had three extra pieces:
- an `on_entity_damaged` / `on_entity_died` dispatcher;
- the proposed `magnetics-test-target`;
- its own pilot cells.

The pilot cells never entered the registered cells. Every number below was read from the result JSON of a run.

Two more facts about the runs:
- Proposed fixes were checked on a scratch copy of the mod. `magnetics/` itself was not edited.
- The expected values in `cells/combat.lua` were typed from FINAL_SPEC §11.6, §4.5–§4.7 and §8.4. They were not taken from `spec.py` or `expected.lua`.

File: `tools/magnetics-tests/cells/combat.lua`. It has 24 slots: W1, W3, W4, K1–K11, and 10 T-W variants. W2 and K12 use `slots = 0`. All cells use `configs = {"base", "sa"}`.

## 1. Pilots settled

| pilot | question | experiment | measured (B and SA identical unless noted) |
|---|---|---|---|
| PILOT-3 | Resistance order | `LuaEntity.damage(D, force, type)` on a stone wall, and on medium, big and behemoth biters. 50 amounts in total. | **H_res holds**: `(D − decrease) × (1 − percent)`. Examples: stone 100 phys → 77.6; medium 32 → 25.2; big 90 → 73.8; behemoth 1200 → 1069.2 and 1800 → 1609.2. Behemoth 100 electric → 100. **Minimum rule** when D − decrease < 1 and D ≥ 1: `1/(2 + decrease − D) × (1 − percent)`. This fits all 14 such points. Examples: stone phys D = 1 → 0.2, D = 3 → 0.4; stone impact D = 45 → 0.2; behemoth D = 5 → 0.1. One point with D < 1: stone D = 0.5 → 0.1. A lethal hit returns the remaining health. |
| PILOT-6 | Does `energy_source` + `energy_per_shot` work on an ammo turret in base? | Coilgun, gauss and rail cannon on an isolated substation with a vanilla-EEI meter. Shots = rounds consumed. Separately, a turret with no pole. | **It works in B and SA.** Energy per shot, from the meter delta minus the turret's buffer change: coilgun **40 000 J** (75 shots), gauss **250 000 J** (30), rail cannon **4 000 000 J** (12), arc **1 000 000 J** (30, after subtracting 24 kW drain). Laser control: 800 kJ/shot. **No pole ever**: 0 shots, status `no_power`, energy 0. After the pole is removed, the buffer still gives 4 / 3 / 1 / 1 shots. Then 0 shots, but the status reads **`low_power`**, because a sub-shot remainder stays in the buffer (37.5 kJ / 250 kJ / 363 kJ / 3.9 MJ). The fallback is not needed. |
| PILOT-7 | `piercing_damage` accounting; `force_condition = "not-same"`; `direction_only` slug fired by an ammo turret | Pinned and disabled biters on the line of fire, 8–12 tiles out. One shot (1 item, `ammo = 1`). Health of the targets set and varied. `shooting_target` forced to a farther biter. | (1) Ammo turrets fire `direction_only` slugs correctly. (2) **A slug goes on only through entities its hit destroys. It stops in the first entity that survives**, even when that entity is not the aimed target. Examples: magnet slug (32, pierce 150) vs medium biters → **1** biter hit; gauss (90, pierce 400) vs big biters (73.8 per hit, they survive) → 1; small, small, medium(survives), small, small → 3, stopping at the medium. This is contrary to the API text "Otherwise, the projectile simply continues". (3) Among killed entities the budget falls by about their health before the hit. Ferrite (pierce 30) vs 15-HP small biters → **3**; vs 5-HP → 6 (all). At an exact zero budget the result depends on entity type and geometry: biters set to 10 HP → small 4 / medium 3 / test target 4. (4) `force_condition = "not-same"`: coilgun and gauss slugs pass through 12 own stone walls with 0 damage. |
| PILOT-8 | Line trigger from an ammo turret: `force`, `width`, `range` origin | Rail cannon, one slug. Disabled behemoths and small biters on and off the axis at 10–39.6 tiles. Own stone walls on the line. | `force = "enemy"` works: own walls on the line take 0. Off the line by 3 tiles: 0. **The line starts at the muzzle** (gun-turret `projectile_creation_distance` 1.39375) and is 36 long, so it reaches about **37.4 from the turret centre**, plus the target's radius. Small biter (r 0.2): hit at 37.4, not at 37.6. Behemoth (r 0.4): hit at **37.5** and 37.6, not at 38.6. **Width 1.5 is the full width.** Small biters are hit at lateral offset 0.9 (both sides), and at 1.0 on one side only, not at 1.05 or more. In-line behemoths take exactly 1069.2. |
| PILOT-9 | chain-active-trigger: jumps, targets, friendlies, stickers, laser bonus | Arc emitter with no network and a 1.2 MJ buffer, which gives exactly one shot. Tested on 5 medium biters in a line 4 apart, an 8-biter cluster, and a single biter. A separate force with laser-weapons-damage-1 and -2 researched. | Primary 45 at tick 43. Then **4 bounces of 30** at +3, +6, +9, +12 ticks; total 165; **5 distinct** biters. Each hop goes to a not-yet-hit neighbour. There is no re-hit and no fork. On a single target the chain does nothing: only 45. **An own stone wall 2.5 tiles off the chain and an own gun turret 3 tiles off take 0.** `electric-mini-stun` is on every hit biter one tick after its hit. **The laser bonus scales the chain:** with +0.4 on `laser`, primary 45 → **63** and bounces 30 → **42**. The `electric` modifier stays 0. Idle drain (24 kW = 400 J/tick) is taken from the buffer even without a network. |
| PILOT-11 | Does `attack_reaction` hit the attacker? | A free biter commanded to `attack` a wall, 15–20 s. Run against magnet, SC, stone and ferrite walls and both gates, with small, medium, big and behemoth biters. | For **medium and small biters: exactly one electric event per bite, in the same tick, with cause = the wall.** Magnet wall/gate: 17 thorns for 17 bites; the biter dies on bite 17. SC wall/gate: 8 for 8. Stone: 0 for 34 bites. Ferrite: 0. **Big and behemoth biters get no thorns at all**: 0 of 35 big bites on a magnet wall, 0 of 26 on an SC wall, 0 of 14 behemoth bites. They bite from **2.07 / 2.16** tiles (centre to wall centre), and the reaction has `range = 2`. Medium biters bite from 1.51. **Fix checked on a scratch mod copy:** with `range = 3`, big biters get 34/34 thorns, behemoths 14/14, and SC big-biter bites 26/26; medium is unchanged (17/17, 8/8). |
| PILOT-14 | A target that turrets engage | 6 turrets (gun + firearm, coilgun, gauss, laser, arc, rail) × 5 targets, 600 ticks, B and SA. Targets: proposed `magnetics-test-target`; enemy unpowered `laser-turret`; pinned `behemoth-spitter`; pinned + `disabled_by_script` behemoth biter; pinned behemoth biter. | **All 30 pairs engage.** Pinned and disabled units moved 0.000 tiles and never attacked. The test target and the enemy laser-turret read the **raw** per-hit damage: 5, 20, 90, 20, 45, 1200 (the rail kills the 1000-HP laser-turret). Polled deltas on enabled units lose 0.1, because healing applies in the same tick as the hit: spitter 19.9, pinned behemoth 7.1. **A disabled behemoth does not heal**, so polled deltas are exact: 7.2, 70.2, 1069.2. A gun turret with firearm vs a pinned behemoth: 0.1 per hit is exactly cancelled by healing. |
| PILOT-15 | Laser-turret DPS baseline | Laser turret on a no-resistance target, 600 ticks and 3600 ticks. | **One hit of 20 per shot** (10 × `damage_modifier` 2), every 40 ticks, with no second beam tick. This follows from `action_triggered_automatically = false`. **L = 30.0 DPS** (90 hits of 20 in 60 s). That is **outside the [45, 90] band the spec assumed.** Arc single-target DPS = 45.0, so **ratio 1.50**. |
| PILOT-17 | Engagement distance metric (gun-turret copy, default `range_mode`) | Gauss (range 30) vs one target at 29.0–31.0 tiles from the centre. | **Units are engaged out to range + their collision radius.** Behemoth (0.4): yes at 30.40, no at 30.45. Small (0.2): yes at 30.15, no at 30.20. **Buildings: no such allowance.** Enemy laser-turret: yes at 30.0, no at 30.5. Test target: yes at 29.504, no at 30.504. K5's 29.5 / 30.5 hold for every target type tried. |

### Pilot-only discoveries that matter for the harness

- **`magnetics-test-target` with `max_health = 1e7` is too coarse for polling.** Health is a float32, so at 1e7 one step is 1 HP. Polled per-hit values round to integers: measured 10 and 39 instead of 9.8 and 39.2, so K11 read 3.9 instead of 4.0. With `max_health = 1e4` the step is about 0.001 and every combat cell reads exact values. Lua is in §5.
- **Run-to-run variance comes only from the map seed.** Combat runs started within the same second gave byte-identical T-W results; runs started at different times differed. That fits a time-based default seed, but this was not checked in the source. `run.py` passes no `--map-gen-seed`.

## 2. Method used by the cells

- **Polling, not events.** The harness owns event registration, and a mod gets one handler per event. Each tick a target's health is read and written back to max (a health write raises no event). Proposed hook: §5.
- **Targets:**
  - `magnetics-test-target` if the test mod defines it.
  - Otherwise an **enemy unpowered `laser-turret`**: no resistances, no healing, immobile, engaged by all turrets.
  - Biters are pinned (stop + `distraction.none`, both ai_settings flags off) **and** `disabled_by_script`.
  - K10 needs more than 1000 HP, so without the test target it uses a disabled behemoth: expected (1800 − 12) × 0.9 + 600 = 2209.2.
- **K10 split.** An enemy SC wall on the line absorbs electric 100 %. It isolates the physical part: (1800 − 8) × 0.65 = 1164.8.
- **Shots** = rounds consumed. **One exact shot** = one item with `ammo = 1`, or for the arc a 1.2 MJ buffer with no network.
- **Energy** = vanilla-EEI meter delta − turret buffer change − drain × time.
  - Every substation is created with `auto_connect = false`. Without it, a pole of the slot below would be in wire reach (16.2 tiles) in a combined run.
- **Research only on the separate force `magnetics-k11`.** Research is force-wide, and K11 changes gun speed.
- **T-W layout:**
  - 3×3 turret block inside a closed 2-deep wall ring: 160 walls, inner half-size 9.
  - 20 medium + 10 big biters spawned 45 tiles north, with `attack_area` (radius 16, `by_enemy`).
  - Ammo is topped up every second. Energy comes from two isolated meter islands.
  - Survivors are destroyed at 120 s so that they cannot reach other cells.
  - I used a ring, not an open wall line, because with an open line the biters could path around it and the walls would take no bites.

## 3. Registered results

| run | config | pass | fail | work dir |
|---|---|---|---|---|
| `combat` | base | **171** | 9 | `/tmp/mgn_base__4q333oe` |
| `combat` | sa | **182** | 9 | `/tmp/mgn_sa_qklqdej0` |
| `smoke,production,logistics,power,quality,static,combat`, 40 000 ticks | base | 2166 | 9 (all in combat, same kinds) | `/tmp/mgn_base_3fkedghd` |
| same | sa | 2398 | 8 (all in combat, same kinds) | `/tmp/mgn_sa_d9bhyw03` |
| `combat` with the proposed `magnetics-test-target` (1e4 HP, scratch test-mod copy) | base / sa | 171 / 183 | 9 / 8 (same kinds) | `/tmp/mgn_base_jv6yjmpp`, `/tmp/mgn_sa_7tuzg0nr` |

The combined runs show no interference: every other module passes, and combat gives the same numbers.

The failures are the same kinds in B and SA:
- K3 magnet (1);
- K9 at 37.5 (1);
- K6 status after pole removal (4);
- K8 ratio (1);
- T-W "SC ≤ ½ stone" (2). The variants differ by seed: base failed coilgun and gauss, SA failed gauss and arc.

Passing:

| test | result (B = SA) |
|---|---|
| W1 | All 48 values within ±0.01. Stone 77.6 / 22 / 63 / 0 / 20 / 30 / 100 / 100; ferrite 72.75 … 70; magnet and magnet gate 66.5 / 17.5 / 55.25 / 0 / 15 / 25 / 50 / 100; SC and SC gate 59.8 / 12 / 48 / 0 / 10 / 0 / 0 / 100 |
| W2 | 500 / 800 / 1500 / 800 / 1500 |
| W3 | Magnet wall and gate: thorn 5.01 (5 + one tick of healing), 17 events for 17 bites. SC wall and gate: 10.01, 8 for 8. Stone: 0 events for 34 bites. Every thorn falls on a bite tick. |
| W4 | Small biter dies on bite **4** (magnet) and bite **2** (SC) |
| K1 | 20 / 32 per hit; **2.50 shots/s**; 150 hits = 150 shots; 15 items for 150 shots |
| K2 | 14.4 / 25.2 |
| K3 ferrite | 3 small biters (1, 2, 3) |
| K4 | 0 damage on 12 + 12 own walls (coilgun 30 shots, gauss 5) |
| K5 | 90 per hit; **1.00 shots/s**; vs big 73.8; first hit at 29.5 on tick 79; 0 hits at 30.5 in 70 s |
| K6 | Energy per shot 40 kJ / 250 kJ / 1 MJ / 4 MJ (exact); 0 shots once the buffer is spent; a turret with no pole has 0 shots and `no_power` |
| K7 | 45 + 4 × 30 = 165; 5 distinct; 5 stickers; own wall 350 |
| K8 | Arc DPS **45.00** |
| K9 | 5 in-line behemoths 1069.2 each; off-line 0; own walls 350 |
| K10 | Stand-in 2209.2 per shot (= 1609.2 + 600); SC wall 1164.8 (physical only); **3 shots** per item, then `no_ammo` |
| K11 | Ratio 4.000 before research, after PPD-1..3 / WSS-1..3, and (SA) after 4..6. Firearm 5 → 9.8 → 20 (SA); ferrite 20 → 39.2 → 80. All magnetics ammo-damage and gun-speed modifiers equal `bullet`; turret-attack modifiers equal gun-turret. Base: bullet 0.4, speed 0.5. SA after 1..6: 1.0, 1.5, turret 1.0. **Ammo-damage and turret-attack multiply**: 5 × 1.4 × 1.4 = 9.8. |
| K12 | 20 / 30 / 20 / 36 |
| T-W | All 30 attackers die in every Magnetics variant (6/6 per config) |

T-W measurements, registered runs (B | SA):

| variant | clear s | wall HP lost | walls destroyed | turrets lost | energy MJ |
|---|---|---|---|---|---|
| gun + piercing, stone | never (9 alive) \| never (9) | 30 150 \| 31 317 | 81 \| 85 | 9 \| 9 | 0 |
| gun + piercing, SC | 31.9 \| 29.6 | 4 607 \| 4 777 | 0 \| 1 | 0 | 0 |
| coilgun + magnet, stone | 13.2 \| 12.8 | 1 837 \| 2 298 | 4 \| 4 | 0 | 11.7 \| 11.3 |
| coilgun + magnet, SC | 11.2 \| 11.3 | 1 217 \| 1 118 | 0 | 0 | 9.8 \| 9.9 |
| gauss, stone | 9.3 \| 8.4 | 660 \| 732 | 1 \| 0 | 0 | 26.0 \| 24.7 |
| gauss, SC | 7.4 \| 7.5 | 348 \| 380 | 0 | 0 | 22.5 \| 22.5 |
| laser, stone | 23.3 \| 22.7 | 4 347 \| 4 544 | 10 \| 11 | 0 | 253.9 \| 251.5 |
| laser, SC | 15.2 \| 15.1 | 2 119 \| 1 911 | 0 | 0 | 171.5 \| 169.1 |
| arc, stone | 7.2 \| 7.1 | 223 \| 84 | 0 | 0 | 82.9 \| 82.9 |
| arc, SC | 7.1 \| 7.3 | 86 \| 138 | 0 | 0 | 81.9 \| 81.9 |

SC/stone wall-HP ratio over all runs with distinct seeds (7 B, 4 SA; same mod):

| turret | base | SA |
|---|---|---|
| gun | 0.13–0.16 | 0.15–0.16 |
| laser | 0.36–0.49 | 0.40–0.53 |
| coilgun | 0.45–0.66 (5 of 7 > 0.5) | 0.43–0.57 (1 of 4) |
| gauss | 0.36–0.70 (4 of 7) | 0.50–0.58 (4 of 4) |
| arc | 0.07–0.70 (2 of 7) | 0.11–1.64 (3 of 4) |

## 4. Deviations

### Mod bugs (implementation ≠ spec)
None found. Every number the cells can see matches the spec: resistances, HP, per-hit damage, rates, energy per shot, chain, line force and width, range caps and bonus mirroring.

### The spec rests on a wrong engine assumption (tests encoded with the spec value; they fail)

1. **PILOT-7, spec assumption wrong: measured 1 medium biter, spec expects 3 (band [2, 3]) — K3 magnet.**
   - Cause: a slug passes only through entities it kills.
   - Fix (spec, council):
     - K3 magnet expected = 1;
     - rewrite §8.4 "pierces": magnet and gauss slugs pierce only through targets they kill (magnet slugs pass through small biters; gauss slugs through medium biters);
     - or redesign the armour-piercing role, e.g. a short `line` sub-action.
   - No mod change makes `piercing_damage` pass a survivor.
2. **PILOT-8, spec assumption wrong: measured 1069.2 on the behemoth at 37.5, spec expects 0 — K9.**
   - Cause: the line starts at the muzzle, 1.39375 from the turret centre.
   - Fix (mod), checked on a scratch copy: `tools/spec.py:61` and `:66`, `line=dict(range=36, …)` → `range=34.60625` (= 36 − 1.39375). With it, small biters are hit at 35.5 and not at 36.5; the 37.5 behemoth is not hit; the 34 one still is. S15 (≤ 36) still holds.
   - Alternative (spec): move the K9 probe to 38.5.
   - This also matters for J1's "nothing reaches 38": the current line hits a target whose edge is within 37.4.
3. **PILOT-15, spec assumption wrong: measured L = 30.0 DPS, spec expects [45, 90] — K8 ratio 1.50, not in [0.5, 1.0].**
   - Fix (mod, council choice) at `tools/spec.py:324`, either:
     - `cooldown=60` → `120`: arc DPS 22.5, ratio 0.75, still 1 MJ/shot. K8's expected arc DPS becomes 22.5, and the T-W arc variants get weaker;
     - or `damage=45` → `24`: ratio 0.80, total per shot 144.
4. **K6 status, engine semantics: measured `low_power`, spec expects `no_power` after the pole is removed.**
   - A sub-shot remainder stays in the buffer. Ammo turrets have no drain.
   - Shots do stop (0 after the buffer).
   - `no_power` appears only at 0 J. A turret that never had a pole shows it (checked, passes).
   - Fix (spec): "Pole removed: 0 shots once the buffer is below one shot; status `low_power`. No pole at all: `no_power`."
5. **T-W "SC-wall variants lose ≤ ½ of stone" is not a stable property.**
   - It fails in about half of the seeds for coilgun and gauss, and the arc variants lose only 84–285 HP. This is not a mod bug.
   - Per-bite SC/stone ratios: medium 4.55 / 9.6 = **0.47**, big 14.3 / 21.6 = **0.66**, behemoth (90 − 8) × 0.65 / 69.6 = **0.77**. Big-biter bites dominate.
   - With the thorn fix (6) the ratio is still 0.45–0.63 (coilgun / gauss, 6 runs).
   - Options for the council:
     - fix the seed (run.py `--map-gen-seed`) and compare means over n ≥ 5 runs;
     - state the criterion per bite against medium biters;
     - or raise SC physical resistance to about 8 / 52 % (big-biter bite ratio 0.49).

### Design claim not covered by a §11 test
6. **PILOT-11, spec assumption wrong: big and behemoth biters receive 0 thorns.**
   - §8.4 says "a behemoth loses 0.3 % per bite".
   - Cause: they bite from 2.07–2.16 tiles, and `attack_reaction.range = 2`.
   - Fix (mod), checked: `magnetics/prototypes/entities.lua:120` (`thorns()`) `range = 2` → `range = 3`. Mirror it in spec §4.5.
   - W3, which uses medium biters only, passes either way.

## 5. Proposals for the shared harness (I did not edit these files)

**`magnetics-test-target`** (append to `tools/magnetics-tests/data.lua`). It is the spec §11.1 target, but with `max_health = 1e4` because of the float32 resolution. Checked: with it, every combat cell reads exact values. The combat module gives 171 pass in base and 183 in SA, with only the known failures (§3).
```lua
-- formula-free DPS target (FINAL_SPEC §11.1, PILOT-14). max_health 1e4, not 1e7: health is float32, so at 1e7 one step
-- is 1 HP and polled per-hit values round to integers (measured 9.8 → 10, 39.2 → 39); at 1e4 the step is ~0.001.
do
  local t = table.deepcopy(data.raw["simple-entity-with-force"]["simple-entity-with-force"])
  t.name = "magnetics-test-target"
  t.max_health = 10000
  t.is_military_target = true
  t.resistances = nil
  t.flags = { "placeable-neutral", "placeable-player", "placeable-enemy", "not-on-map" }
  t.minable = nil
  t.hidden = true
  data:extend{ t }
end
```
`combat.lua` uses it automatically when it exists.

**Damage hooks.** One handler per event per mod, so dispatch in `control.lua`.
- `lib.lua`, after `L.results = {}`:
  ```lua
  L.on_damaged, L.on_died = {}, {}   -- cells append function(e) at module load; state goes to storage
  ```
- `control.lua`, end of the main chunk:
  ```lua
  script.on_event(defines.events.on_entity_damaged, function(e) for _, f in ipairs(L.on_damaged) do f(e) end end)
  script.on_event(defines.events.on_entity_died, function(e) for _, f in ipairs(L.on_died) do f(e) end end)
  ```
- Note: an unfiltered `on_entity_damaged` handler costs UPS in the U1/U2 benchmarks. Register it only when `#L.on_damaged > 0`.

**Seed.** `tools/run.py`, `--create` call: add `'--map-gen-seed', '<fixed>'`, so that T-W (and any unit behaviour) repeats.

## 6. Open issues
- T-W pass/fail on "SC ≤ ½" depends on the seed until the seed is fixed or the criterion is changed (§4.5).
- The `clamp_position` of the rail ammo was not tested on its own. Targets were always within range.
- Piercing at an exact zero budget depends on entity type and geometry (PILOT-7 (3)). K3 ferrite (3 small biters, budget exactly 0 at the 2nd) gave 3 in every run, B and SA.
- The minimum-damage rule for D < 1 rests on one point.
