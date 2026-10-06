import sys
from fle.env.instance import FactorioInstance
inst = FactorioInstance(address='localhost', tcp_port=27106, fast=True)
print(inst.eval('''
move_to(Position(x=-2.5, y=5.5))
b = get_entity(Prototype.Boiler, Position(x=-5.0, y=4.5))
b = insert_item(Prototype.Coal, b, 20)
sleep(120)
print('котёл', get_entity(Prototype.Boiler, Position(x=-5.0, y=4.5)).fuel)
print([e.status for e in get_entities({Prototype.ElectricMiningDrill, Prototype.ElectricFurnace, Prototype.Inserter, Prototype.BurnerInserter})])
''', agent_idx=0, timeout=600)[2])
