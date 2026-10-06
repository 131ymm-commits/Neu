# Демон эпизода: держит FactorioInstance слота (пространство имён агента живёт между шагами), принимает шаги по unix-сокету, ведёт журнал.
#   python daemon.py <slot> <episode_id> <task_key> <max_steps> <logdir>
import json, os, re, socket, sys, time, traceback
from fle.env.instance import FactorioInstance
from fle.eval.tasks.task_factory import TaskFactory
from measure import final_measure
slot, ep, task_key, max_steps, logdir = int(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
SOCK = f'/tmp/claude-0/fact/slot{slot}.sock'
BANNED = re.compile(r'(\bimport\b|__|\brcon|\binstance\b|\bexec\b|\beval\b|\bopen\s*\(|\bglobals\b|\blocals\b|\bgetattr\b|\bsetattr\b|\bvars\b|\bcompile\b|lua|/sc|/c\b)', re.I)
task = TaskFactory.create_task(task_key)
inst = FactorioInstance(address='localhost', tcp_port=27100 + slot, fast=True)
task.setup(inst)
os.makedirs(logdir, exist_ok=True); LOG = open(os.path.join(logdir, f'{ep}.jsonl'), 'a')
def log(**k): LOG.write(json.dumps(dict(t=time.time(), **k), ensure_ascii=False) + '\n'); LOG.flush()
log(event='start', slot=slot, task=task_key, goal=task.goal_description, max_steps=max_steps)
def throughput():
    r = task.verify(0, inst, {}); return r.meta.get(task.throughput_key, 0), bool(r.success)
steps = 0; best = 0
if os.path.exists(SOCK): os.remove(SOCK)
srv = socket.socket(socket.AF_UNIX); srv.bind(SOCK); srv.listen(1)
print('READY', flush=True)
while True:
    c, _ = srv.accept(); data = b''
    while not data.endswith(b'\n\x00'):
        part = c.recv(65536)
        if not part: break
        data += part
    req = json.loads(data[:-2].decode()); cmd = req.get('cmd')
    if cmd == 'final':
        fm = final_measure(inst, task); out = dict(final=fm, measure=fm['measure'], success=fm['success'], best_during=best, steps=steps)
        log(event='final', **out); c.sendall(json.dumps(out).encode()); c.close(); break
    if cmd == 'info':
        c.sendall(json.dumps(dict(task=task_key, goal=task.goal_description, steps_used=steps, max_steps=max_steps, quota=task.quota)).encode()); c.close(); continue
    code = req.get('code', '')
    if steps >= max_steps: out = dict(error=f'лимит шагов {max_steps} исчерпан')
    elif BANNED.search(code): out = dict(error='запрещённая конструкция в коде (разрешены только инструменты FLE): ' + BANNED.search(code).group(0)); log(event='banned', code=code, match=BANNED.search(code).group(0))
    else:
        steps += 1
        try:
            r = inst.eval(code, agent_idx=0, timeout=180); res = r[2] if isinstance(r, tuple) and len(r) > 2 else str(r)
        except Exception as e: res = 'ошибка: ' + ''.join(traceback.format_exception_only(type(e), e))[-1500:]
        tp, ok = throughput(); best = max(best, tp)
        out = dict(step=steps, steps_left=max_steps - steps, output=str(res)[-6000:], throughput=tp, quota=task.quota, entity=str(task.throughput_entity))
        log(event='step', step=steps, code=code, output=str(res)[-6000:], throughput=tp)
    c.sendall(json.dumps(out, ensure_ascii=False).encode()); c.close()
