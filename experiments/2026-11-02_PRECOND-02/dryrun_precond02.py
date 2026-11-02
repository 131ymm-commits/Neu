# PRECOND-02: сухой прогон до PREREG (как dryrun_precond_main.py PRECOND-01).
#   python3 dryrun_precond02.py <пустой каталог>
# 1) Синтетика последовательного плана: ложная тревога при δ = 0 и мощность при δ = 0,089 (sd 0,454, план из plan.json или 90/180)
#    — сверка с границами и power_precond02.json. 2) Вся цепочка на заглушках: задачи и пулы SELECT-01 (WH 8001–8020), соли сухого
#    прогона, выборы-заглушки (ANCHOR — выбор по заявке, NOREF — случайный, часть — отказы и сбои), защиты порядка, правда,
#    промежуточный анализ, защита заданий этапа B, итоговый анализ. 3) Промпты рук байт в байт равны D_N и C_N SELECT-01 / THINK-01.
import json, math, os, random, shutil, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); EXP = os.path.join(HERE, '..'); SEL = os.path.join(EXP, '2026-10-07_SELECT-01')
root = os.path.abspath(sys.argv[1]); assert os.path.isdir(root) and not os.listdir(root), 'нужен пустой каталог'
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(EXP, '2026-10-15_THINK-01'))
ok = True
def check(cond, msg):
    global ok; ok &= bool(cond); print(('ок  ' if cond else 'СБОЙ') + ' ' + msg)

# ---------- 1. синтетика последовательного плана ----------
import analyze_precond02 as A, harness_precond02 as HP0  # noqa: E402
from analyze_precond import t_ci  # noqa: E402
n1, nmax = 90, 180
if os.path.exists(os.path.join(HERE, 'plan.json')): pl = json.load(open(os.path.join(HERE, 'plan.json'))); n1, nmax = pl['n1'], pl['n_max']
b = A.bounds(n1 / nmax); rho = math.sqrt(n1 / nmax)
def seq(delta, rng, sd=0.454):
    g = rng.normal(delta, sd, nmax); r1 = t_ci(list(g[:n1]))
    if r1['p_greater'] <= b['p1_nominal']: return True
    if r1['mean'] <= 0: return False                                       # бесполезность — как в analyze_precond02.interim
    rt = t_ci(list(g)); return rt['p_greater'] <= b['p2_nominal']
rng = np.random.default_rng(2); reps = 2000
fa = sum(seq(0.0, rng) for _ in range(reps)) / reps; pw = sum(seq(0.089, rng) for _ in range(reps)) / reps
check(abs(b['alpha_check'] - 0.05) < 1e-4, f'границы: c1 {b["c1"]:.3f}, c2 {b["c2"]:.3f}, суммарный α {b["alpha_check"]:.4f}')
check(0.03 <= fa <= 0.065, f'ложная тревога плана {n1}/{nmax} при δ = 0 (t, с бесполезностью): {fa:.3f} (ожидание ≤ 0,05)')
PW = json.load(open(os.path.join(HERE, 'power_precond02.json')))['designs'][f'{n1}/{nmax}']['by_effect']['C-041 (открытие, точечно)']['power']
check(abs(pw - PW) < 0.04, f'мощность при δ 0,089: синтетика {pw:.3f}, расчёт {PW}')

# ---------- 2. вся цепочка на заглушках; порядок этапов проверяет код ----------
for d in ('tasks', 'pools'): os.makedirs(f'{root}/{d}')
dry, dryB = range(8001, 8011), range(8011, 8021)
for s_ in list(dry) + list(dryB):
    shutil.copy(f'{SEL}/tasks/WH_{s_}.json', f'{root}/tasks/'); shutil.copy(f'{SEL}/pools/WH_{s_}.json', f'{root}/pools/')
json.dump({'WH': list(dry)}, open(f'{root}/seeds_dry.json', 'w')); json.dump({'WH': list(dryB)}, open(f'{root}/seeds_dryB.json', 'w'))
import hashlib  # noqa: E402
os.makedirs(f'{root}/run')
for st_, rng_ in (('dry', dry), ('dryB', dryB)):          # как collect_exec: манифест пулов и явный список задач без пула
    json.dump({f'WH_{s_}': hashlib.sha256(open(f'{root}/pools/WH_{s_}.json', 'rb').read()).hexdigest() for s_ in rng_}, open(f'{root}/run/{st_}_exec_pools.sha256', 'w'), indent=0)
    json.dump([], open(f'{root}/run/{st_}_exec_missing.json', 'w'))
json.dump(dict(n1=len(dry), n_max=len(dry) + len(dryB), alpha=0.05, note='сухой прогон'), open(f'{root}/plan.json', 'w'))
G = lambda *a: subprocess.run(['git', '-C', root, *a], check=True, capture_output=True, text=True)
G('init', '-q'); G('config', 'user.email', 'dry@example'); G('config', 'user.name', 'dry'); G('add', '-A'); G('commit', '-qm', 'сухой прогон: задачи и пулы')
env = dict(os.environ, PRECOND02_ROOT=root, PRECOND02_SECRET=f'{root}/secret')
def H(*a, fail=False):
    r = subprocess.run([sys.executable, f'{HERE}/harness_precond02.py', *a], env=env, capture_output=True, text=True)
    if fail: return r.returncode != 0, (r.stderr.strip().splitlines() or [''])[-1]
    assert r.returncode == 0, r.stderr[-600:]; return r.stdout
def AN(*a):
    return subprocess.run([sys.executable, f'{HERE}/analyze_precond02.py', *a], env=env, capture_output=True, text=True, cwd=root)
os.environ.update(PRECOND02_ROOT=root, PRECOND02_SECRET=f'{root}/secret')
import importlib; HP = importlib.reload(HP0)   # обвязка с D = root для заглушек (A0 по пулу задачи)
sys.path.insert(0, SEL); from analyze import a0  # noqa: E402
def fake(name, seed):
    rr = random.Random(seed); n = 0
    with open(f'{root}/run/{name}_out.jsonl', 'w') as fh:
        for j in map(json.loads, open(f'{root}/run/{name}_jobs.jsonl')):
            t, arm, i = j['id'].split('|'); u = rr.random(); inv = {v: k for k, v in enumerate(HP.perm(t))}
            if u < 0.02: res = None
            elif arm == 'ANCHOR': res = dict(choice=-1) if u < 0.08 else dict(choice=inv[a0(HP.pool(t), t)])   # показанный номер плана A0
            else: res = dict(choice=rr.randrange(8))
            fh.write(json.dumps(dict(id=j['id'], result=res, error='сбой' if res is None else None, out=rr.randrange(2000, 9000), inp=6000,
                                     models={'stub': 1}), ensure_ascii=False) + '\n'); n += 1
    return n
H('salt', 'dry')
os.rename(f'{root}/pools/WH_8005.json', f'{root}/WH_8005.bak')
f0, m0 = H('eval_jobs', 'dry', fail=True); check(f0 and 'нет пула WH_8005' in m0, f'пропавший пул без записи в список пропусков ловится: {m0}')
os.rename(f'{root}/WH_8005.bak', f'{root}/pools/WH_8005.json')
H('eval_jobs', 'dry'); n = fake('dry_eval', 1)
check(n == 10 * 2 * 5, f'задания этапа A: {n} (= 10 задач × 2 руки × 5 голосов)')
jobs = [json.loads(l) for l in open(f'{root}/run/dry_eval_jobs.jsonl')]
import prompts_think as PT, sim  # noqa: E402
tk = HP.task('WH_8001'); shown = [HP.pool('WH_8001')[i] for i in HP.perm('WH_8001')]; rules = sim.RULES[tk['type']](tk)
pa = next(j['prompt'] for j in jobs if j['id'] == 'WH_8001|ANCHOR|0'); pn = next(j['prompt'] for j in jobs if j['id'] == 'WH_8001|NOREF|0')
check(pa == PT.eval_prompt('D_N', rules, shown) and pn == PT.eval_prompt('C_N', rules, shown), 'промпты: ANCHOR = D_N, NOREF = C_N байт в байт (SELECT-01 / THINK-01)')
H('collect_eval', 'dry')
f1, m1 = H('truth', 'dry', fail=True); check(f1 and 'не закоммичен' in m1, f'правда до коммита выборов запрещена: {m1}')
G('add', 'evals', 'run'); G('commit', '-qm', 'выборы dry')
f2, m2 = H('truth', 'dry', fail=True); check(f2, f'правда до события пуша запрещена: {m2}')
H('push_event', 'dry', '--local'); G('add', 'dry_push_activity.json'); G('commit', '-qm', 'событие dry')
open(f'{root}/evals/dry.jsonl', 'a').write('{}\n')
f3, m3 = H('truth', 'dry', fail=True); check(f3, f'правда при выборах, изменённых после пуша, запрещена: {m3}')
G('checkout', '--', 'evals/dry.jsonl'); H('truth', 'dry')
r = AN('interim', 'evals/dry.jsonl', '--out', f'{root}/interim_an.json', '--keys', 'dry,dryB')
check(r.returncode == 0, 'промежуточный анализ отработал' + ('' if r.returncode == 0 else ': ' + r.stderr[-400:]))
ia = json.load(open(f'{root}/interim_an.json'))
check(ia['decision'] == 'продолжить', f'решение промежуточного: {ia["decision"]} (заглушка подобрана на «продолжить»); выигрыш {ia["primary"]["gain"]["mean"]}, p {ia["primary"]["p_one_sided"]}')
check(set(ia['describe']) >= {'ANCHOR', 'NOREF', 'A0_no_calls', 'vote_status', 'input_span'}, f'описание: отказы ANCHOR {ia["describe"]["ANCHOR"]["refusals"]}, статусы {ia["describe"]["vote_status"]}')
f4, m4 = H('eval_jobs', 'dryB', fail=True); check(f4 and 'не закоммичен' in m4, f'задания B до коммита промежуточного решения запрещены: {m4}')
G('add', 'interim_an.json'); G('commit', '-qm', 'промежуточный dry')
H('salt', 'dryB'); H('eval_jobs', 'dryB'); nb = fake('dryB_eval', 2); H('collect_eval', 'dryB')
check(nb == 100, f'задания этапа B: {nb}')
G('add', 'evals', 'run'); G('commit', '-qm', 'выборы dryB'); H('push_event', 'dryB', '--local'); G('add', 'dryB_push_activity.json'); G('commit', '-qm', 'событие dryB')
H('truth', 'dryB')
r = AN('final', 'evals/dry.jsonl', 'evals/dryB.jsonl', '--out', f'{root}/final_an.json', '--keys', 'dry,dryB')
check(r.returncode == 0, 'итоговый анализ отработал' + ('' if r.returncode == 0 else ': ' + r.stderr[-400:]))
fa_ = json.load(open(f'{root}/final_an.json'))
check(fa_['n_tasks'] == fa_['n_A'] + fa_['n_B'] and 0 < fa_['final_bound']['p2_nominal'] < 0.05, f'итог: задач {fa_["n_tasks"]}, граница p {fa_["final_bound"]["p2_nominal"]}, исход reject={fa_["primary"]["reject"]}')
# защита: решение «остановить» запрещает этап B
ia['decision'] = 'остановить: эффективность'; json.dump(ia, open(f'{root}/interim_an.json', 'w'), ensure_ascii=False, indent=1); G('commit', '-qam', 'подмена решения')
f5, m5 = H('eval_jobs', 'dryB', fail=True); check(f5 and 'не совпадает' in m5, f'подменённое промежуточное решение ловится: {m5}')
print('СУХОЙ ПРОГОН ПРОЙДЕН' if ok else 'СУХОЙ ПРОГОН НЕ ПРОЙДЕН'); sys.exit(0 if ok else 1)
