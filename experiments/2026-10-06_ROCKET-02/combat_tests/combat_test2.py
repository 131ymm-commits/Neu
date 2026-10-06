import sys, json; sys.path.insert(0, '/home/user/neu/experiments/2026-10-06_ROCKET-02')
from fle.env.instance import FactorioInstance
import combat
inst = FactorioInstance(address='localhost', tcp_port=27108, fast=True, all_technologies_researched=False)
r = inst.rcon_client
OUT = open('/tmp/claude-0/-home-user/368a3030-ed6f-5d75-8ccd-d3417f8f1866/scratchpad/combat_results.jsonl', 'a')
for mode, rad, nb in [(m, rr, n) for n in (4, 8) for m, rr in (('kite', 14), ('strafe', 12), ('kite', 17), ('strafe', 16))]:
    inst.initial_inventory = {"submachine-gun": 1, "firearm-magazine": 100, "light-armor": 1}; inst.reset(all_technologies_researched=False)
    combat.arm(r)
    r.send_command('/sc local c=storage.agent_characters[1] local p=c.position local sf=c.surface for _,e in pairs(sf.find_entities_filtered{force="enemy", position=p, radius=120}) do e.destroy() end '
                   f'for k=1,{nb} do sf.create_entity{{name="small-biter", position={{p.x+30, p.y+k*1.5-4}}, force="enemy"}} end')
    me = json.loads(r.send_command('/sc rcon.print(helpers.table_to_json(storage.agent_characters[1].position))'))
    out = combat.fight(r, me['x'] + 30, me['y'], r=rad, mode=mode, seconds=40, retreat=0.3)
    rec = dict(mode=mode, r=rad, biters=nb, **out); print(json.dumps(rec, ensure_ascii=False), flush=True); OUT.write(json.dumps(rec, ensure_ascii=False) + '\n'); OUT.flush()
