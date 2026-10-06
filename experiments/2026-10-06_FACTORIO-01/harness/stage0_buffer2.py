# Этап 0: та же набивка печей рудой, затем финальная мера с опустошением буферов. Ожидание: мера = 0.
import json, sys
from fle.env.instance import FactorioInstance
from fle.eval.tasks.task_factory import TaskFactory
from measure import final_measure
slot = int(sys.argv[1]); task = TaskFactory.create_task('iron_plate_throughput')
inst = FactorioInstance(address='localhost', tcp_port=27100 + slot, fast=True); task.setup(inst)
code = open('stage0_buffer.py').read().split("code = '''")[1].split("'''")[0]
inst.eval(code, agent_idx=0, timeout=600)
r = final_measure(inst, task); print(json.dumps(r, ensure_ascii=False)); json.dump(r, open('../stage0/buffer_cleared.json', 'w'), ensure_ascii=False, indent=1)
