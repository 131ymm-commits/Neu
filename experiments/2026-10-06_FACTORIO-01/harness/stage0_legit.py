# Этап 0: честная цепочка (2 угольных бура → печи → угольные манипуляторы → сундуки, топливо вручную) под финальной мерой. Ожидание: мера ≥ 16.
import json, sys
from fle.env.instance import FactorioInstance
from fle.eval.tasks.task_factory import TaskFactory
from measure import final_measure
slot = int(sys.argv[1]); task = TaskFactory.create_task('iron_plate_throughput')
inst = FactorioInstance(address='localhost', tcp_port=27100 + slot, fast=True); task.setup(inst)
code = '''
ore = nearest(Resource.IronOre)
move_to(ore)
for i in range(3):
    d = place_entity(Prototype.BurnerMiningDrill, position=Position(x=ore.x + 3*i, y=ore.y), direction=Direction.DOWN)
    d = insert_item(Prototype.Coal, d, quantity=50)
    f = place_entity(Prototype.StoneFurnace, position=d.drop_position)
    f = insert_item(Prototype.Coal, f, quantity=50)
    ins = place_entity_next_to(Prototype.BurnerInserter, f.position, direction=Direction.DOWN, spacing=0)
    ins = insert_item(Prototype.Coal, ins, quantity=10)
    c = place_entity(Prototype.WoodenChest, position=ins.drop_position)
print(get_entities())
'''
print(str(inst.eval(code, agent_idx=0, timeout=600)[2])[-800:])
r = final_measure(inst, task); print(json.dumps(r, ensure_ascii=False)); json.dump(r, open('../stage0/legit.json', 'w'), ensure_ascii=False, indent=1)
