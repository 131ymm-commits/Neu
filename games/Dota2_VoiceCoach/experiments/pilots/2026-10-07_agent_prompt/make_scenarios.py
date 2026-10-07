"""Пилот промпта агента: наблюдения из настоящего кода кастомки (Lua, coach_obs.lua) на имитации Доты,
промпты — из coach/voicecoach/agents.py. Пишет s<N>_system.txt, s<N>_user.txt, s<N>_obs.json."""
import json, sys
from pathlib import Path
GAME = Path('/home/user/Neu/games/Dota2_VoiceCoach/game')
sys.path.insert(0, str(GAME / 'tests')); sys.path.insert(0, str(GAME.parent / 'coach'))
import test_custom_game as T
from voicecoach import agents as A
OUT = Path(__file__).resolve().parent

class S(T.Game):
    def runTest(self): pass

g = S(); g.setUp(); g.start_match()
L, G = g.L, g.G
REAL = {"sniper": ["sniper_shrapnel", "sniper_headshot", "sniper_take_aim", "sniper_assassinate"],
        "viper": ["viper_poison_attack", "viper_nethertoxin", "viper_corrosive_skin", "viper_viper_strike"],
        "axe": ["axe_berserkers_call", "axe_battle_hunger", "axe_counter_helix", "axe_culling_blade"],
        "lion": ["lion_impale", "lion_voodoo", "lion_mana_drain", "lion_finger_of_death"],
        "crystal_maiden": ["crystal_maiden_crystal_nova", "crystal_maiden_frostbite", "crystal_maiden_brilliance_aura", "crystal_maiden_freezing_field"],
        "luna": ["luna_lucent_beam", "luna_moon_glaive", "luna_lunar_blessing", "luna_eclipse"],
        "lina": ["lina_dragon_slave", "lina_light_strike_array", "lina_fiery_soul", "lina_laguna_blade"],
        "bristleback": ["bristleback_viscous_nasal_goo", "bristleback_quill_spray", "bristleback_bristleback", "bristleback_warpath"],
        "witch_doctor": ["witch_doctor_paralyzing_cask", "witch_doctor_voodoo_restoration", "witch_doctor_maledict", "witch_doctor_death_ward"],
        "jakiro": ["jakiro_dual_breath", "jakiro_ice_path", "jakiro_liquid_fire", "jakiro_macropyre"]}
RANGE = {"sniper_shrapnel": 1800, "sniper_assassinate": 3000, "sniper_take_aim": 0, "luna_lucent_beam": 800,
         "lina_dragon_slave": 800, "lina_light_strike_array": 625, "lina_laguna_blade": 600,
         "crystal_maiden_crystal_nova": 700, "crystal_maiden_frostbite": 550, "crystal_maiden_freezing_field": 0,
         "axe_berserkers_call": 0, "axe_culling_blade": 150, "lion_impale": 500, "lion_voodoo": 500,
         "lion_finger_of_death": 900, "viper_viper_strike": 500}
PASSIVE = {"sniper_headshot", "viper_corrosive_skin", "axe_counter_helix", "crystal_maiden_brilliance_aura",
           "luna_moon_glaive", "luna_lunar_blessing", "lina_fiery_soul", "bristleback_bristleback", "bristleback_warpath"}
NOTARGET = {"sniper_take_aim", "axe_berserkers_call", "bristleback_quill_spray", "luna_eclipse",
            "crystal_maiden_freezing_field"}
set_passive = L.eval("function(ab) ab.IsPassive = function(self) return true end end")
for p in G["__players"].values():
    h = p["hero"]; short = h["name"].replace("npc_dota_hero_", "")
    if short in REAL:
        for i, n in enumerate(REAL[short]):
            ab = h["abilities"][i + 1]; ab["name"] = n
            if n in PASSIVE: set_passive(ab)
            if n in NOTARGET: ab["behavior"] = 4
            ab["range"] = RANGE.get(n, 600)
def hero(short): return g.by_name(short)
def V(x, y): return L.eval(f"Vector({x}, {y}, 0)")
def item(h, slot, name, charges=0):
    it = L.eval("__make_ability")(name, False, 8, 1); it["charges"] = charges; h["slots"][slot] = it
def payload(): return json.loads(L.eval('require("vc_json").encode')(G["CoachGame"]["TickPayload"](G["CoachGame"], G["__now"])))
def obs_of(team, pos): return next(o for o in payload()["heroes"] if o["team"] == team and o["pos"] == pos)
def team_level(lvls, spots):
    for (short, lv), xy in zip(lvls.items(), spots):
        h = hero(short); h["lvl"] = lv
        if xy: h["pos"] = V(*xy)

def write(n, o, coach_new, trigger, memory=()):
    sysp = A.system_prompt(o["team"], o["pos"], o["hero"])
    user = A.user_prompt(o, list(memory), coach_new, trigger)
    (OUT / f"s{n}_system.txt").write_text(sysp, encoding="utf-8")
    (OUT / f"s{n}_user.txt").write_text(user, encoding="utf-8")
    (OUT / f"s{n}_obs.json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    print(n, o["hero"], len(sysp), len(user))

sn, luna, lina, vip = hero("sniper"), hero("luna"), hero("lina"), hero("viper")
# 1: линия, 2:30, снайпер на боте, рядом крипы, Луна видна, без приказа
G["__now"] = 90 + 150
sn["pos"] = V(5200, -4300); sn["lvl"] = 3; sn["health"] = 430; sn["gold"] = 310
for k, lv in zip(range(1, 5), (1, 1, 1, 0)): sn["abilities"][k]["level"] = lv
item(sn, 0, "item_tango", 2); item(sn, 1, "item_quelling_blade"); item(sn, 2, "item_branches")
L.eval("__creep")(3, 5500, -4000, 95); L.eval("__creep")(3, 5550, -3950, 400); L.eval("__creep")(3, 5600, -4050, 300)
L.eval("__creep")(2, 5300, -4150, 380); L.eval("__creep")(2, 5350, -4100, 550)
luna["pos"] = V(5900, -3700); luna["health"] = 380; luna["max_health"] = 560; luna["lvl"] = 3
for o in (lina, hero("bristleback"), hero("witch_doctor"), hero("jakiro")): o["hidden"] = True
write(1, obs_of("radiant", 1), [], "очередное решение", ["2:26 farm bot"])
# 2: 14:00, приказ «1 пуш бот т2», их Т1 бот снесена
G["__now"] = 90 + 840
team_level({"viper": 13, "axe": 12, "lion": 10, "crystal_maiden": 9},
           [(-1200, -1000), (-5800, 2500), (-5600, 2300), (5400, -3400)])
for t in G["__towers"].values():
    if t["name"] == "npc_dota_badguys_tower1_bot": t["alive"] = False
for c in G["__creeps"].values(): c["alive"] = False
sn["pos"] = V(5800, -3000); sn["lvl"] = 12; sn["health"] = 1180; sn["max_health"] = 1400; sn["gold"] = 1650
sn["abilities"][1]["level"], sn["abilities"][2]["level"], sn["abilities"][3]["level"], sn["abilities"][4]["level"] = 4, 4, 2, 1
sn["slots"][2] = None; item(sn, 2, "item_power_treads"); item(sn, 3, "item_maelstrom"); item(sn, 4, "item_magic_wand", 8)
luna["hidden"] = True
L.eval("__creep")(2, 6000, -2600, 550); L.eval("__creep")(2, 6050, -2550, 550)
g.hud("1 пуш бот т2")
o = obs_of("radiant", 1)
write(2, o, o["coach"][-1:], "приказ тренера", ["13:52 farm bot", "13:56 farm bot"])
# 3: 22:00 драка, Луна видна на 600 с 35 %, Лина на 900, ульт готов, приказ «все драка !»
G["__now"] = 90 + 1320
sn["pos"] = V(0, 0); sn["lvl"] = 18; sn["health"] = 1500; sn["max_health"] = 2100; sn["gold"] = 900
sn["abilities"][4]["level"] = 3
luna["hidden"] = False; luna["pos"] = V(600, 0); luna["health"] = 700; luna["max_health"] = 2000; luna["lvl"] = 17
lina["hidden"] = False; lina["pos"] = V(-200, 880); lina["health"] = 1300; lina["max_health"] = 1500; lina["lvl"] = 16
team_level({"viper": 19, "axe": 18, "lion": 15, "crystal_maiden": 14},
           [(-300, -200), (-500, 300), (-700, -400), (-900, 100)])
for x in (hero("bristleback"), hero("witch_doctor"), hero("jakiro")): x["lvl"] = 16
g.hud("все драка !")
o = obs_of("radiant", 1)
write(3, o, o["coach"][-1:], "приказ тренера", ["21:50 group mid", "21:55 fight → luna"])
# 4: мёртв, 31:00, выкуп, золото, приказ «1 бб !»
G["__now"] = 90 + 1860
sn["alive"] = False; sn["gold"] = 4200
g.hud("1 бб !")
o = obs_of("radiant", 1)
o["events"] = ["30:52 тебя убил lina", "30:53 у нас погиб viper"]
write(4, o, o["coach"][-1:], "приказ тренера", ["30:40 fight → lina"])
# 5: саппорт 5 (кристал) 8:00, приказ «5 вард руна» (руки варды не умеют), рядом керри
G["__now"] = 90 + 480
for t in G["__towers"].values(): t["alive"] = True                  # 8:00 — все вышки стоят
for pos in range(1, 6): G["CoachGame"]["teams"][2]["coach"][pos] = L.table_from([])
team_level({"viper": 8, "axe": 7, "lion": 6, "sniper": 7}, [(-1200, -1000), (-5800, 2500), (-5600, 2300), None])
sn["alive"] = True; sn["pos"] = V(5200, -4300)
cm = hero("crystal_maiden"); cm["pos"] = V(5000, -4500); cm["lvl"] = 6; cm["health"] = 420; cm["max_health"] = 640; cm["gold"] = 420
cm["points"] = 1
for k, lv in zip(range(1, 5), (2, 2, 1, 0)): cm["abilities"][k]["level"] = lv
item(cm, 0, "item_tango", 1); item(cm, 1, "item_ward_observer", 1); item(cm, 2, "item_boots")
for x in (luna, lina): x["hidden"] = True
g.hud("5 вард руна")
o = obs_of("radiant", 5)
write(5, o, o["coach"][-1:], "приказ тренера", ["7:52 follow 1"])
g.tearDown()
