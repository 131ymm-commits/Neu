"""Подмены в копии кода рук (рецензия 11, ERRORS №104): каждое правило рук должно ловиться тестами.

Запуск: скопировать game/ и coach/ во временную папку (рядом, как в репозитории), поправить пути HERE/SRC/PY ниже и
запустить: python mutate_hands.py [M1 M2 …]. Итог 11.10.2026: поймано 51 из 51 (после правки теста M41); после правок
рецензии 11б — 64 из 64 (в первом прогоне выжили 6 — ERRORS №105).
Не тест: unittest его не собирает (имя не test_*)."""
import shutil, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
MUT = HERE / "game"
SRC = Path("/home/user/Neu/games/Dota2_VoiceCoach/game/custom_game/game/scripts/vscripts")
VS = MUT / "custom_game" / "game" / "scripts" / "vscripts"
PY = "/tmp/claude-0/-home-user-Neu/c2746a83-5006-51b9-9f59-346f06e713bc/scratchpad/venv/bin/python"
E, W, G = "coach_exec.lua", "coach_world.lua", "coach_game.lua"
M = [
 ("M1 размен без busy", E, [("return { kind = \"attack\", target = e, busy = math.min(1.5, walk + world.attack_point(hero) + 0.1),", "return { kind = \"attack\", target = e,")]),
 ("M2 добивание кора без busy", E, [("if best then return { kind = \"attack\", target = best, busy = math.min(1.5, bt + 0.1), why", "if best then return { kind = \"attack\", target = best, why")]),
 ("M3 issue не ставит busy", E, [("if order.busy then st.busy_until = math.max(st.busy_until or 0, now + order.busy) end", "")]),
 ("M4 скорость 0", E, [("  return math.max(0, (pts[1].hp - hp) / span)\nend", "  return 0\nend")]),
 ("M4b прогноз без повторов", E, [("if d > 0 and tau > now - X.LH_PERIOD and tau + X.LH_PERIOD <= now + t then before = before + d end", "")]),
 ("M4c повтор без фазы (все удары окна)", E, [("tau + X.LH_PERIOD <= now + t then", "true then")]),
 ("M5 без полёта снаряда", E, [("local fly = world.is_ranged(hero) and math.min(d, range) / math.max(300, world.projectile_speed(hero)) or 0", "local fly = 0")]),
 ("M6 без pred > 0", E, [("pred <= dmg * X.LH_MARGIN and pred > 0 and", "pred <= dmg * X.LH_MARGIN and")]),
 ("M6b запас 1.0", E, [("X.LH_MARGIN = 0.85 ", "X.LH_MARGIN = 1.0 ")]),
 ("M6c ближний бой с упреждением", E, [("(world.is_ranged(hero) or hp <= dmg)", "true")]),
 ("M6d окно 2 с", E, [("X.LH_WINDOW = 1.0 ", "X.LH_WINDOW = 2.0 ")]),
 ("M6e период 2 с", E, [("X.LH_PERIOD = 1.0 ", "X.LH_PERIOD = 2.0 ")]),
 ("M6f окно короче периода", E, [("X.LH_WINDOW = 1.0 ", "X.LH_WINDOW = 0.5 ")]),
 ("M7 смерть цели не снимает замах", E, [("if not world.alive(last.target) or (st.retreat_hp > 0 and hp < st.retreat_hp)", "if (st.retreat_hp > 0 and hp < st.retreat_hp)")]),
 ("M7b отход не прерывает замах", E, [("if not world.alive(last.target) or (st.retreat_hp > 0 and hp < st.retreat_hp)", "if not world.alive(last.target) or false")]),
 ("M7c вышка не прерывает замах", E, [("        or world.tower_hitting(ag.team, hero, X.TOWER_KEEP) then\n      st.busy_until = now", "        then\n      st.busy_until = now")]),
 ("M8 размен без сравнения здоровья", E, [("if hp < X.HARASS_HP or hp + 10 < world.hp_pct(e) then return nil end", "if hp < X.HARASS_HP then return nil end")]),
 ("M8b размен без HARASS_HP", E, [("if hp < X.HARASS_HP or hp + 10 < world.hp_pct(e) then return nil end", "if hp + 10 < world.hp_pct(e) then return nil end")]),
 ("M9 керри подходит для размена", E, [("range + (ag.pos == 1 and 0 or X.HARASS_REACH)", "range + X.HARASS_REACH")]),
 ("M10 ближний без проверки крипов", E, [("if not ranged and #world.lane_creeps(hero, 500, true) > 2 then return nil end", "")]),
 ("M11 размен у их вышки (своя позиция)", E, [("if world.near_enemy_tower(team, world.pos(e), X.TOWER_KEEP) or world.near_enemy_tower(team, my, X.TOWER_KEEP)", "if world.near_enemy_tower(team, world.pos(e), X.TOWER_KEEP)")]),
 ("M12 размен без перевеса", E, [("      or #world.enemies_near(team, world.pos(e), X.NUMBERS_R) > world.allies_near(team, my, X.NUMBERS_R) then", "      then")]),
 ("M13 стычка у их вышки", E, [("return not bans[e] and not world.near_enemy_tower(team, ep, X.TOWER_KEEP)", "return not bans[e]")]),
 ("M14 стычка без удержания", E, [("X.SKIRMISH_HOLD = 3 ", "X.SKIRMISH_HOLD = 0 ")]),
 ("M15 стычка без липкости", E, [("if sk and why_of[sk.target] and not", "if false and sk and why_of[sk.target] and not")]),
 ("M16 ульта в стычке без порога", E, [("ult_ok = world.hp_pct(target) <= 50", "ult_ok = world.hp_pct(target) <= 100")]),
 ("M17 размен способностью без маны", E, [("          and world.mana_pct(hero) >= (X.HARASS_MANA[ag.pos] or 70)\n", "")]),
 ("M18 размен способностью без паузы", E, [("if harass then st.harass_cast_next = now + X.HARASS_CAST_GAP end", "")]),
 ("M19 вышка: бежать и в драке", E, [("if tw and (not (st.plan and (st.plan.kind == \"fight\" or st.plan.kind == \"save\")) or hp < 50) then", "if tw then")]),
 ("M20 вышка: в драке не бежать никогда", E, [("or st.plan.kind == \"save\")) or hp < 50) then", "or st.plan.kind == \"save\"))) then")]),
 ("M21 ждать у ближайшего", E, [("      if h1 < shp then soon, shp = c, h1 end", "")]),
 ("M21b ближний бой без стоянки у волны", E, [("if not world.is_ranged(hero) and near <= range + 250 then", "if false then")]),
 ("M22 отвечаю без «дольше секунды»", E, [("if victim == hero and for_s >= X.HIT_SUSTAIN and ehp <= hp + 15 then", "if victim == hero and ehp <= hp + 15 then")]),
 ("M22b отвечаю без сравнения здоровья", E, [("if victim == hero and for_s >= X.HIT_SUSTAIN and ehp <= hp + 15 then", "if victim == hero and for_s >= X.HIT_SUSTAIN then")]),
 ("M23 добиваю без своего здоровья", E, [("if ehp <= X.KILL_HP and hp >= 30 and world.dist(my, world.pos(e)) <= reach then", "if ehp <= X.KILL_HP and world.dist(my, world.pos(e)) <= reach then")]),
 ("M23b добиваю без досягаемости", E, [("if ehp <= X.KILL_HP and hp >= 30 and world.dist(my, world.pos(e)) <= reach then", "if ehp <= X.KILL_HP and hp >= 30 then")]),
 ("M24 своих не считать", W, [("    if W.alive(hero) and W.dist(hero:GetAbsOrigin(), point) <= radius then n = n + 1 end", "    n = n + 1")]),
 ("M25 смерть не сбрасывает стычку", E, [("st.retreating, st.last, st.busy_until, st.skirmish = false, nil, 0, nil", "st.retreating, st.last, st.busy_until = false, nil, 0")]),
 ("M26 саппорт не разменивается", E, [("    local h = harass_order(st, ag, world, now, own, tag)", "    local h = nil")]),
 ("M27 размен без паузы", E, [("  st.harass_next = now + (ranged and X.HARASS_GAP.ranged or X.HARASS_GAP.melee)\n", "")]),
 ("M28 размен при добивании на подходе", E, [("  if lasthit_soon(hero, world, creeps) then return nil end\n", "")]),
 ("M29 выручать здорового", E, [("if victim == a.unit and for_s >= X.HIT_SUSTAIN and world.hp_pct(a.unit) < X.HELP_HP", "if victim == a.unit and for_s >= X.HIT_SUSTAIN")]),
 ("M29b выручать без «дольше 1.75 с»", E, [("if victim == a.unit and for_s >= X.HIT_SUSTAIN and world.hp_pct(a.unit) < X.HELP_HP", "if victim == a.unit and world.hp_pct(a.unit) < X.HELP_HP")]),
 ("M30 стычка без SKIRMISH_HP", E, [("elseif hp >= X.SKIRMISH_HP then", "elseif true then")]),
 ("M31 рефлекс вышки выкл.", E, [("  local tw = world.tower_hitting(ag.team, hero, X.TOWER_KEEP)\n  if tw and", "  local tw = nil\n  if tw and")]),
 ("M32 броня выкл.", W, [("  return 1 - 0.06 * a / (1 + 0.06 * math.abs(a))", "  return 1")]),
 ("M33 замах без SPA/BAT", W, [("if bat and bat > 0 and spa and spa > 0 then return point * spa / bat end", "")]),
 ("M34 вместе — и по здоровому", E, [("elseif ehp <= X.HELP_HP and a.victim == e", "elseif a.victim == e")]),
 ("M34b вместе без «дольше 1.75 с»", E, [("a.victim == e and a.for_s >= X.HIT_SUSTAIN and not a.join", "a.victim == e and not a.join")]),
 ("M34c вместе с тем, кто сам лишь поддерживает", E, [("a.victim == e and a.for_s >= X.HIT_SUSTAIN and not a.join", "a.victim == e and a.for_s >= X.HIT_SUSTAIN")]),
 ("M35 керри вступает на фарме", E, [("local carry_farm = ag.pos == 1 and plan == \"farm\"", "local carry_farm = false")]),
 ("M36 без поводка", E, [("X.SKIRMISH_LEASH = 1500 ", "X.SKIRMISH_LEASH = 1e9 ")]),
 ("M37 без запрета после поводка", E, [("return not bans[e] and not world.near_enemy_tower", "return not world.near_enemy_tower")]),
 ("M37b запрет один на всех", E, [("    bans[sk.target] = now + X.SKIRMISH_BAN ", "    for k in pairs(bans) do bans[k] = nil end\n    bans[sk.target] = now + X.SKIRMISH_BAN ")]),
 ("M37c место начала — заново при смене цели", E, [("origin = (st.skirmish and st.skirmish.origin) or my }", "origin = my }")]),
 ("M38 размен любой способностью", E, [("          and (not harass or X.HARASS_SPELLS[i.name])\n", "")]),
 ("M39 размен способностью при добивании на подходе", E, [("          and not lasthit_soon(hero, world)\n", "")]),
 ("M40 вышка раньше применений агента", E, [
     ("  local c = cast_step(st, ag, world, now)                    -- применения агента — раньше рефлексов (рецензия 11)\n  if c then return cast(c) end\n", "  local c\n"),
     ("  c = auto_cast(st, ag, world, now, sk and \"skirmish\" or nil)", "  c = cast_step(st, ag, world, now) or auto_cast(st, ag, world, now, sk and \"skirmish\" or nil)")]),
 ("M41 денай у их вышки", E, [("return world.hp_pct(c) < X.DENY_PCT and not world.near_enemy_tower(team, world.pos(c), X.TOWER_KEEP)", "return world.hp_pct(c) < X.DENY_PCT")]),
 ("M42 отход без применений агента", E, [("    local c0 = cast_step(st, ag, world, now, true)", "    local c0 = nil")]),
 ("M42b при отходе — и с подходом", E, [("    local c0 = cast_step(st, ag, world, now, true)", "    local c0 = cast_step(st, ag, world, now, false)")]),
 ("M43 замер не сбрасывается при росте здоровья", E, [("if r == nil or now - r.seen > X.LH_KEEP or hp > r.pts[#r.pts].hp then", "if r == nil or now - r.seen > X.LH_KEEP then")]),
 ("M44 «бьёт» — дольше секунды", E, [("X.HIT_SUSTAIN = 1.75 ", "X.HIT_SUSTAIN = 1.0 ")]),
 ("M46 при отходе — и канальные с долгим замахом", E, [("        elseif still and not TELEPORTS[c.ability] and (info.channel or (info.cast_point or 0) > X.STILL_CAST) then\n          keep[#keep + 1] = c                                  -- при отходе не стоять на канале и долгом замахе\n", "")]),
 ("M47 ожидание на фарме — простой", E, [("if st.last and st.last.kind == \"hold\" and not st.last.wait then", "if st.last and st.last.kind == \"hold\" then")]),
 ("M48 Рошан — крип линии", "coach_game.lua", [("return (t == DOTA_TEAM_GOODGUYS or t == DOTA_TEAM_BADGUYS) and killed:IsCreep()", "return killed:IsCreep()")]),
 ("M45 размен Goo и Lucent Beam", E, [("viper_nethertoxin = true, sniper_shrapnel = true }", "viper_nethertoxin = true, sniper_shrapnel = true, luna_lucent_beam = true, bristleback_viscous_nasal_goo = true }")]),
]
def run():
    r = subprocess.run([PY, "-m", "unittest", "tests.test_custom_game"], cwd=MUT, capture_output=True, text=True, timeout=900)
    fails = [l.split("(")[0].replace("FAIL: ", "").replace("ERROR: ", "").strip() for l in r.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    ran = [l for l in r.stderr.splitlines() if l.startswith("Ran ")]
    if not ran or ran[-1].split()[1] in ("0", "1"):
        raise SystemExit("тесты не запустились: " + r.stderr[-500:])           # не выдавать сбой загрузки за «поймана»
    return r.returncode == 0, fails
only = sys.argv[1:]
for name, f, reps in M:
    if only and not any(name.startswith(o + " ") for o in only):
        continue
    for fn in (E, W, G):
        shutil.copy(SRC / fn, VS / fn)
    text = (SRC / f).read_text(encoding="utf-8")
    bad = [o for o, _ in reps if text.count(o) != 1]
    if bad:
        print(f"{name}: шаблон не найден ровно раз — пропуск", flush=True)
        continue
    for o, n in reps:
        text = text.replace(o, n)
    (VS / f).write_text(text, encoding="utf-8")
    ok, fails = run()
    print(f"{name}: {'ВЫЖИЛА' if ok else 'поймана'}{'' if ok else ' — ' + ', '.join(fails[:3])}", flush=True)
for fn in (E, W, G):
    shutil.copy(SRC / fn, VS / fn)
