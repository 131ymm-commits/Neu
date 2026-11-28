"""CHILD-01, пост-хок после заседания совета 49 (вердиктов не меняет): интервалы для трёх описательных сравнений,
которые в отчёте стояли без интервала. Единица — сид (среднее по задачам внутри сида); интервал — бутстреп по сидам; p — точная перестановка знаков, двусторонняя.
  python3 posthoc.py → posthoc.json"""
import glob, json, os
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); LO, HI = 121, 150
runs = {}
for f in glob.glob(os.path.join(H, 'runs', '*.json')):
    j = json.load(open(f)); s = j['series']
    runs[(j['task'], j['arm'], j['seed'])] = dict(W=float(np.mean(np.subtract(s['c_fix'][LO:HI + 1], s['t_fix'][LO:HI + 1]))), Tk=float(np.mean(s['t_key'][LO:HI + 1])))
seeds = sorted({k[2] for k in runs}); T5 = ['T2', 'T3', 'T4', 'T5', 'T6']; T6 = ['T1'] + T5
def exact_two_sided(m):
    m = np.asarray(m, float); n = len(m); masks = np.arange(2 ** n, dtype=np.int64); sums = np.zeros(2 ** n)
    for i in range(n): sums += np.where((masks >> i) & 1, -m[i], m[i])
    return float(np.mean(np.abs(sums) >= abs(m.sum()) - 1e-12))
def block(metric, a, b, tasks):
    m = np.array([np.mean([runs[(t, a, s)][metric] - runs[(t, b, s)][metric] for t in tasks]) for s in seeds])
    r = np.random.default_rng(2026); x = m[r.integers(0, len(m), (20000, len(m)))].mean(1)
    tm = {t: round(float(np.mean([runs[(t, a, s)][metric] - runs[(t, b, s)][metric] for s in seeds])), 3) for t in tasks}
    return dict(mean=round(float(m.mean()), 3), ci95=[round(float(np.percentile(x, 2.5)), 3), round(float(np.percentile(x, 97.5)), 3)], p_two_sided=round(exact_two_sided(m), 4),
                seeds_plus=int(np.sum(m > 1e-12)), seeds_minus=int(np.sum(m < -1e-12)), by_task=tm, tasks_plus=sum(1 for v in tm.values() if v > 0), tasks_total=len(tasks))
out = dict(note='пост-хок: три описательных сравнения с интервалами; сравнений три, поправка на их число не делалась; вердиктов нет', seeds=len(seeds),
           truth_RND4_minus_ALT25=block('Tk', 'RND4', 'ALT_25', T6), truth_RND4_minus_ALT6N64=block('Tk', 'RND4', 'ALT_6_N64', T6), truth_ALT25_minus_ALT6N64=block('Tk', 'ALT_25', 'ALT_6_N64', T6),
           inflation_RND4_minus_ALT25=block('W', 'RND4', 'ALT_25', T5), inflation_ALT12_minus_FIX=block('W', 'ALT_12', 'FIX', T5), truth_ALT12_minus_FIX=block('Tk', 'ALT_12', 'FIX', T6))
json.dump(out, open(os.path.join(H, 'posthoc.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for k, v in out.items():
    if isinstance(v, dict): print(k, {x: y for x, y in v.items() if x != 'by_task'})
