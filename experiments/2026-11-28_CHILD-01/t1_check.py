"""CHILD-01, после теста: почему пилот и тест расходятся на задаче T1 при постоянных тестах (ветвь FIX).
Проверка, что это не ошибка кода CHILD-01: исходный код EVO-01 (evo01.py, ветвь FIXED16) на пилотных сидах 990–992 даёт тот же ряд, что пилот CHILD-01.
Сверка с архивами: EVO-01 (сиды 0–19) и пилот DEFER-01 (сиды 996–998).  python3 t1_check.py → t1_check.json"""
import glob, json, os
import numpy as np
import evo01 as E
H = os.path.dirname(os.path.abspath(__file__)); X = os.path.dirname(H)
late = lambda v: float(np.mean(v[121:151]))
out = {}
for name, folder, seeds in (('pilot', 'pilot', range(990, 993)), ('test', 'runs', range(100, 120))):
    for arm in ('FIX', 'RND'):
        v = [late(json.load(open(os.path.join(H, folder, f'T1_{arm}_s{s}.json')))['series']['t_key']) for s in seeds]
        out[f'{name}_{arm}'] = dict(seeds=len(v), late_truth=[round(x, 3) for x in v], mean=round(float(np.mean(v)), 3), solved=int(sum(x > 0.999 for x in v)), above_0_9=int(sum(x > 0.9 for x in v)))
a = [json.load(open(f))['final_true'] for f in sorted(glob.glob(os.path.join(X, '2026-09-26_EVO-01', 'runs', 'T1_FIXED16_s*.json')))]
out['EVO01_archive_FIXED16'] = dict(seeds=len(a), final_truth_solved=int(sum(x > 0.999 for x in a)), final_truth_above_0_4=int(sum(x > 0.4 for x in a)), mean=round(float(np.mean(a)), 3))
d = [json.load(open(f))['hist'][-1]['true'] for f in sorted(glob.glob(os.path.join(X, '2026-11-27_DEFER-01', 'pilot', 'T1_FIXED16_s*.json')))]
out['DEFER01_pilot_FIXED16'] = dict(seeds=len(d), final_truth=[round(x, 3) for x in d], solved=int(sum(x > 0.999 for x in d)))
rep = {}
for s in (990, 991, 992):
    h = E.run('T1', 'FIXED16', s)['hist']; j = json.load(open(os.path.join(H, 'pilot', f'T1_FIX_s{s}.json')))['series']
    rep[str(s)] = dict(final_truth=round(h[-1]['true'], 3), max_abs_diff_truth=float(max(abs(x['true'] - y) for x, y in zip(h, j['t_key']))),
                       max_abs_diff_claim=float(max(abs(x['claimed'] - y) for x, y in zip(h, j['c_key']))))
out['rerun_original_EVO01_code_on_pilot_seeds'] = rep
out['chance_three_of_three'] = {'if_rate_0.05': round(0.05 ** 3, 5), 'if_rate_0.1': round(0.1 ** 3, 4), 'if_rate_0.25': round(0.25 ** 3, 4)}   # 0,05 — частота из архива EVO-01 и теста (1 из 20)
json.dump(out, open(os.path.join(H, 't1_check.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
