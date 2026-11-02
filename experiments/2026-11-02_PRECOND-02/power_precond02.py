# PRECOND-02: мощность и цена вариантов плана до PREREG (совет 39: «границы и мощность считает закоммиченный скрипт по sd
# парных разностей именно для контраста REFUSE»). sd — из prior_refuse.json (старые выборки, мера PRECOND-01) и пилота (pilot_an.json),
# для плана берётся наибольший — осторожная оценка. Тест — z-приближение к t по задачам (n ≥ 90, df ≥ 89).
# Сила: θ = δ / sd · √n_max; Z1 ~ N(θ√t1, 1), Z2 ~ N(θ, 1), corr √t1. Мощность без остановки по бесполезности и с ней (Z1 ≤ 0 → стоп).
#   python3 power_precond02.py  →  power_precond02.json
import json, math, os, statistics as st
import analyze_precond02 as A
HERE = os.path.dirname(os.path.abspath(__file__))
prior = json.load(open(os.path.join(HERE, 'prior_refuse.json')))
sds = {k: v['D_minus_C']['sd'] for k, v in prior.items()}
pil = os.path.join(HERE, 'pilot_an.json')
if os.path.exists(pil): sds['pilot'] = json.load(open(pil))['primary']['gain']['sd']
sd = max(sds.values())
eff = {'C-041 (открытие, точечно)': 0.089, 'половина C-041 (совет 39)': 0.045}
pm = [-v['D_minus_C']['mean'] for v in prior.values()]; eff['старые выборки, среднее по трём'] = round(st.mean(pm), 3)
# цена: выход на вызов — средний по рукам C_N и D_N старых выборок; исполнитель — PRECOND-01 (val_exec: 380 859 на 50 задач)
out_eval = st.mean(st.mean(v['out_mean'].values()) for v in prior.values()); out_exec = 380859 / 50
# скорость — по журналам пилота (та же конфигурация, параллельность 3; совет 40, «что проверить первым», п. 1)
from datetime import datetime
def seg(j):
    ev = [json.loads(l) for l in open(os.path.join(HERE, 'run', j, 'run_log.jsonl')) if l.strip()]
    t = lambda e: datetime.fromisoformat(e['at']).timestamp(); a = next(e for e in ev if e['event'] == 'старт'); b = next(e for e in ev if e['event'] == 'готово')
    return (t(b) - t(a)) / 3600, sum(e['event'] == 'вызов' for e in ev)
he, ne = seg('pilot_exec_journal'); hv, nv = seg('pilot_eval_journal')
speed = dict(exec_calls_per_hour=round(ne / he, 1), eval_calls_per_hour=round(nv / hv, 1), note='пилот 02.11: исполнитель 10 вызовов, оценщики 100, параллельность 3; без ожиданий лимита')
res = dict(sd_sources=sds, sd_plan=sd, effects=eff, out_per_eval_call=round(out_eval), out_per_exec_call=round(out_exec), speed=speed, designs={})
for n1, nmax in ((90, 180), (120, 240), (180, 360)):
    b = A.bounds(n1 / nmax); rho = math.sqrt(n1 / nmax); d = dict(n1=n1, n_max=nmax, c1=round(b['c1'], 4), c2=round(b['c2'], 4),
                                                                   p1_nominal=round(b['p1_nominal'], 5), p2_nominal=round(b['p2_nominal'], 5), by_effect={})
    for name, delta in eff.items():
        th = delta / sd * math.sqrt(nmax); m1, m2 = th * rho, th
        p_eff1 = 1 - A.Phi(b['c1'] - m1)
        p_cont_nofut = A.cross2(b['c1'], b['c2'], rho, m1, m2)                          # Z1 < c1, Z2 ≥ c2
        p_fut_and_win = A.cross2(0.0, b['c2'], rho, m1, m2)                             # Z1 < 0, Z2 ≥ c2 — теряется при остановке по бесполезности
        p_fut = A.Phi(0.0 - m1); p_cont = 1 - p_eff1 - p_fut
        calls = (n1 + (nmax - n1) * p_cont) * 10; tasks = n1 + (nmax - n1) * p_cont
        d['by_effect'][name] = dict(delta=delta, power_no_futility=round(p_eff1 + p_cont_nofut, 3), power=round(p_eff1 + p_cont_nofut - p_fut_and_win, 3),
                                    p_stop_efficacy=round(p_eff1, 3), p_stop_futility=round(p_fut, 3), expected_tasks=round(tasks),
                                    expected_out_mln=round((calls * out_eval + tasks * out_exec) / 1e6, 2))
    d['max_out_mln'] = round((nmax * 10 * out_eval + nmax * out_exec) / 1e6, 2)
    d['max_hours'] = round(nmax / speed['exec_calls_per_hour'] + nmax * 10 / speed['eval_calls_per_hour'], 1)       # счёт без ожиданий лимита
    for x in d['by_effect'].values(): x['expected_hours'] = round(nmax / speed['exec_calls_per_hour'] + x['expected_tasks'] * 10 / speed['eval_calls_per_hour'], 1)
    res['designs'][f'{n1}/{nmax}'] = d
json.dump(res, open(os.path.join(HERE, 'power_precond02.json'), 'w'), ensure_ascii=False, indent=1); print(json.dumps(res, ensure_ascii=False, indent=1))
