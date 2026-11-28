"""CHILD-01: независимый пересчёт четырёх проверок с вердиктом прямо из сырых файлов прогонов — другим кодом,
без функций child01_analyze.py и stats01.py (наклон — np.polyfit, перебор знаков — по битовым маскам, интервал — свой бутстреп).
Написан и закоммичен до конца основного прогона. Вердикты выводятся по тексту PREREG-CHILD-01 §3.
  python3 recheck.py [pilot|test] → recheck.json (для pilot — recheck_pilot.json); код возврата 1, если расхождение с анализом"""
import glob, json, os, sys
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); mode = sys.argv[1] if len(sys.argv) > 1 else 'test'
folder = os.path.join(H, 'pilot' if mode == 'pilot' else 'runs')
A = json.load(open(os.path.join(H, 'pilot_results.json' if mode == 'pilot' else 'child01_results.json')))
LO, HI = 121, 150                                         # поздние поколения включительно (PREREG §2)
runs = {}
for f in glob.glob(os.path.join(folder, '*.json')):
    j = json.load(open(f)); s = j['series']
    runs[(j['task'], j['arm'], j['seed'])] = dict(W=float(np.mean(np.subtract(s['c_fix'][LO:HI + 1], s['t_fix'][LO:HI + 1]))),
                                                  Ti=float(np.mean(s['t_fix'][LO:HI + 1])), mT=float(np.mean(s['mT'][LO:HI + 1])))
seeds = sorted({k[2] for k in runs}); T5 = ['T2', 'T3', 'T4', 'T5', 'T6']; T6 = ['T1'] + T5
Q = [0.0, 0.125, 0.25, 0.5, 0.75, 1.0]; DARMS = ['FIX', 'ALT_12', 'ALT_25', 'ALT_50', 'ALT_75', 'RND']

def cells(kind):
    """Словарь (задача, сид) → величина проверки."""
    if kind == 'P1': return {(t, s): -float(np.polyfit(Q, [runs[(t, a, s)]['W'] for a in DARMS], 1)[0]) for t in T5 for s in seeds}
    if kind == 'P3': return {(t, s): runs[(t, 'ALT_50', s)]['Ti'] - runs[(t, 'NOISE_50', s)]['Ti'] for t in T6 for s in seeds}
    if kind == 'P4': return {(t, s): runs[(t, 'NOISE_50', s)]['W'] - runs[(t, 'ALT_50', s)]['W'] for t in T5 for s in seeds}
    if kind == 'P5': return {(t, s): runs[(t, 'ALT_25', s)]['mT'] - runs[(t, 'FINAL_25', s)]['mT'] for t in T6 for s in seeds}

def exact_p(m):
    """Точная перестановка знаков: все 2^n раскладов по битовым маскам."""
    m = np.asarray(m, float); n = len(m); masks = np.arange(2 ** n, dtype=np.int64); sums = np.zeros(2 ** n)
    for i in range(n): sums += np.where((masks >> i) & 1, -m[i], m[i])
    obs = float(m.sum()); tol = 1e-12 * max(1.0, float(np.abs(m).sum()))
    return float(np.mean(sums >= obs - tol)), float(np.mean(sums <= obs + tol))

def boot(m, B=20000, seed=12345):
    r = np.random.default_rng(seed); m = np.asarray(m, float); x = m[r.integers(0, len(m), (B, len(m)))].mean(1)
    return float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))

out = {}; bad = []
for kind, key in (('P1', 'P1a_dose_slope'), ('P3', 'P3_truth_ALT50_vs_NOISE50'), ('P4', 'P4_purge_NOISE50_minus_ALT50'), ('P5', 'P5_popmean_truth_ALT25_vs_FINAL25')):
    c = cells(kind); tasks = sorted({t for t, _ in c})
    m = np.array([np.mean([c[(t, s)] for t in tasks]) for s in seeds])                 # единица — сид: среднее по задачам внутри сида
    tm = {t: float(np.mean([c[(t, s)] for s in seeds])) for t in tasks}; plus = sum(1 for v in tm.values() if v > 0)
    d = dict(mean=float(m.mean()), seeds_plus=int(np.sum(m > 1e-12)), seeds_minus=int(np.sum(m < -1e-12)), tasks_plus=plus, tasks_total=len(tasks), by_task={t: round(v, 5) for t, v in tm.items()})
    if len(seeds) >= 8:
        up, down = exact_p(m); lo, hi = boot(m); d.update(p_up=up, p_down=down, ci=[round(lo, 5), round(hi, 5)])
        if kind == 'P4': d['verdict'] = 'экзамен чистит' if up <= 0.005 else 'обратный эффект' if down <= 0.005 else 'разницы нет' if (-0.05 < lo and hi < 0.05) else 'не решено'
        else: d['verdict'] = ('подтверждено' if plus >= len(tasks) - 1 else 'в среднем, неоднородно по задачам') if up <= 0.005 else 'обратный эффект' if down <= 0.005 else 'не решено'
    a = A[key]; out[kind] = d
    # сравнение с анализом
    if abs(a['mean'] - d['mean']) > 2e-5: bad.append(f"{kind}: среднее {d['mean']} против {a['mean']}")
    if a.get('tasks_positive') != d['tasks_plus']: bad.append(f"{kind}: задач со знаком плюс {d['tasks_plus']} против {a.get('tasks_positive')}")
    for t in tasks:
        if abs(a['by_task'][t]['mean'] - tm[t]) > 2e-5: bad.append(f"{kind} {t}: {tm[t]} против {a['by_task'][t]['mean']}")
    if 'p_up' in d:
        if abs(a['p_predicted'] - d['p_up']) > 2e-6 or abs(a['p_opposite'] - d['p_down']) > 2e-6: bad.append(f"{kind}: p {d['p_up']}, {d['p_down']} против {a['p_predicted']}, {a['p_opposite']}")
        if a['seeds_positive'] != d['seeds_plus'] or a['seeds_negative'] != d['seeds_minus']: bad.append(f'{kind}: счёт сидов')
        if a['verdict'] != d['verdict']: bad.append(f"{kind}: вердикт «{d['verdict']}» против «{a['verdict']}»")
        d['ci_analysis'] = a['ci95']
out['runs'] = len(runs); out['seeds'] = len(seeds); out['mismatches'] = bad
json.dump(out, open(os.path.join(H, 'recheck_pilot.json' if mode == 'pilot' else 'recheck.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for k in ('P1', 'P3', 'P4', 'P5'): print(k, {x: (round(y, 5) if isinstance(y, float) else y) for x, y in out[k].items() if x != 'by_task'})
print('расхождений с анализом:', len(bad)); [print('  ', b) for b in bad]
sys.exit(1 if bad else 0)
