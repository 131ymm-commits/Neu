# Этап 0.Б.1: дыра «набить буфер» — руда добыта вручную, печи набиты, цепочки нет. Окна verify сразу (1–3) и после 10 игровых минут.
import json, sys, time
from fle.env.instance import FactorioInstance
from fle.eval.tasks.task_factory import TaskFactory
slot = int(sys.argv[1]); task = TaskFactory.create_task('iron_plate_throughput')
inst = FactorioInstance(address='localhost', tcp_port=27100 + slot, fast=True); task.setup(inst)
def tick(): return int(inst.rcon_client.send_command('/sc rcon.print(game.tick)').strip())
code = '''
pos = nearest(Resource.IronOre)
move_to(pos)
t0 = 0
got = harvest_resource(pos, quantity=400)
print('добыто', got, inspect_inventory())
fs = []
for i in range(8):
    try:
        f = place_entity(Prototype.StoneFurnace, position=Position(x=pos.x - 6 + 2*(i % 4) * 1.5, y=pos.y - 4 - 3*(i // 4)))
        f = insert_item(Prototype.Coal, f, quantity=20)
        f = insert_item(Prototype.IronOre, f, quantity=45)
        fs.append(f)
    except Exception as e:
        print('err', i, e)
print(len(fs), 'печей набито')
'''
t = time.time(); tk = tick(); r = inst.eval(code, agent_idx=0, timeout=600); out = dict(code_wall=round(time.time() - t, 1), code_ticks=tick() - tk, output=str(r[2])[-600:])
W = []
for w in range(3):
    t0 = tick(); res = task.verify(0, inst, {}); W.append(dict(window=w + 1, tp=res.meta.get(task.throughput_key), dtick=tick() - t0))
inst.eval('sleep(600)', agent_idx=0, timeout=900)
t0 = tick(); res = task.verify(0, inst, {}); W.append(dict(window='+10мин', tp=res.meta.get(task.throughput_key), dtick=tick() - t0))
out['windows'] = W; print(json.dumps(out, ensure_ascii=False, indent=1))
json.dump(out, open('../stage0/buffer.json', 'w'), ensure_ascii=False, indent=1)
