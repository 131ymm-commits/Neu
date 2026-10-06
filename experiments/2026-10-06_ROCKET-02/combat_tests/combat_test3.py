import sys, json; sys.path.insert(0, '/home/user/neu/experiments/2026-10-06_ROCKET-02')
from fle.env.instance import FactorioInstance
import combat
inst = FactorioInstance(address='localhost', tcp_port=27108, fast=True, all_technologies_researched=False)
r = inst.rcon_client
OUT = open('/tmp/claude-0/-home-user/368a3030-ed6f-5d75-8ccd-d3417f8f1866/scratchpad/combat_results3.jsonl', 'a')
CASES = [
 dict(name='пистолет, 4 кусаки', inv={"pistol": 1, "firearm-magazine": 10}, spawn=[('small-biter', 4)], f=dict(mode='kite', r=12, seconds=40)),
 dict(name='ПП, гнездо + 5 кусак, стрейф 16', inv={"submachine-gun": 1, "firearm-magazine": 100, "light-armor": 1}, spawn=[('biter-spawner', 1), ('small-biter', 5)], f=dict(mode='strafe', r=16, seconds=90)),
 dict(name='ПП, гнездо + 5 кусак, кайт 16', inv={"submachine-gun": 1, "firearm-magazine": 100, "light-armor": 1}, spawn=[('biter-spawner', 1), ('small-biter', 5)], f=dict(mode='kite', r=16, seconds=90)),
 dict(name='ПП, гнездо + червь + 5 кусак, стрейф 16', inv={"submachine-gun": 1, "firearm-magazine": 100, "light-armor": 1}, spawn=[('biter-spawner', 1), ('small-worm-turret', 1), ('small-biter', 5)], f=dict(mode='strafe', r=16, seconds=90)),
 dict(name='ПП, гнездо + червь + 5 кусак, стрейф 16, червь первым', inv={"submachine-gun": 1, "firearm-magazine": 100, "light-armor": 1}, spawn=[('biter-spawner', 1), ('small-worm-turret', 1), ('small-biter', 5)], f=dict(mode='strafe', r=16, seconds=90, priority=['turret', 'unit', 'unit-spawner'])),
]
for cs in CASES:
    inst.initial_inventory = cs['inv']; inst.reset(all_technologies_researched=False)
    r.send_command('/sc local c=storage.agent_characters[1] c.health=c.max_health')
    combat.arm(r)
    me = json.loads(r.send_command('/sc rcon.print(helpers.table_to_json(storage.agent_characters[1].position))'))
    cx, cy = me['x'] + 35, me['y']
    r.send_command(f'/sc local sf=game.surfaces[1] for _,e in pairs(sf.find_entities_filtered{{force="enemy", position={{{cx},{cy}}}, radius=150}}) do e.destroy() end')
    for nm, n in cs['spawn']:
        for k in range(n):
            dx = {'biter-spawner': 0, 'small-worm-turret': -4}.get(nm, -6); dy = (k - n / 2) * 1.5 if nm == 'small-biter' else (4 if nm == 'small-worm-turret' else 0)
            r.send_command(f'/sc game.surfaces[1].create_entity{{name="{nm}", position={{{cx + dx},{cy + dy}}}, force="enemy"}}')
    out = combat.fight(r, cx, cy, **cs['f'])
    rec = dict(case=cs['name'], **out); print(json.dumps(rec, ensure_ascii=False), flush=True); OUT.write(json.dumps(rec, ensure_ascii=False) + '\n'); OUT.flush()
