#!/usr/bin/env python3
"""SCORE-01: расчёты для сборщика PREREG и PILOT3.md — без побочных эффектов (LENSES-1b, N4: импорт сборщика пересобирал черновик
и переписывал pilot_power.json). Здесь только чтение evals/*.json и счёт; файлов модуль не пишет.
  direction_check()   — правило направлений NONE-контрастов по пилоту 3 (DESIGN_after_lenses1.md, 9962627); SE — по средним задач
                        (с 503e29f), рядом — SE одного вызова (толкование, при котором O7 ушёл бы в разведку; LENSES-1b, N2);
  rule_out_split()    — (LOG + WIN)/2 − NONE по выходным токенам = (LOG − NONE) + (WIN − LOG)/2 (LENSES-1b, N11);
  win_log_out_pilots() — WIN − LOG по выходным токенам в пилотах 0–3 (основа H9 и O9; LENSES-1b, N14)."""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
f = lambda x, d=3: f'{x:.{d}f}'.replace('.', ',').replace('-', '−')


def _sd(x):
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def direction_check():
    import power_score01 as PS
    out, keep = [], {}
    for model in ('opus', 'haiku'):
        ps, per_task = PS.variants(model)
        for j, p in enumerate(ps):
            if p['id'] not in ('O7', 'O8', 'H7', 'H8'):
                continue
            tv = [float(np.nanmean(v[:, j])) for v in per_task]            # значение задачи: у Opus — среднее двух вызовов пилота
            m = sum(tv) / len(tv)
            se = _sd(tv) / math.sqrt(len(tv))
            single = np.concatenate([v[:, j] for v in per_task]); single = single[~np.isnan(single)]
            se1 = float(single.std(ddof=1)) / math.sqrt(len(tv))         # SD одного вызова / √20 (другое толкование, N2)
            keep[p['id']] = dict(mean=m, se=se, se_single=se1, ratio=abs(m) / se, ratio_single=abs(m) / se1,
                                 sign=1 if m > 0 else -1, keep=abs(m) >= se, keep_single=abs(m) >= se1)
            d = 0 if p['measure'] == 'out' else 3
            line = (f"{p['id']} ({model}, {p['measure']}): среднее {f(m, d)}, SE {f(se, d)} ({f(abs(m) / se, 2)} SE) → " +
                    (f"направление {'> 0' if m > 0 else '< 0'}" if abs(m) >= se else 'в разведку'))
            if model == 'opus':
                line += f"; при SE одного вызова ({f(se1, d)}) — {f(abs(m) / se1, 2)} SE, " + ('направление' if abs(m) >= se1 else 'ушёл бы в разведку')
            out.append(line)
    return out, keep


def _task_arm_means(E, measure):
    by = {}
    for r in E['rows'].values():
        if r['valid']:
            by.setdefault((r['task'], r['arm']), []).append(float(r[measure]))
    return {k: sum(v) / len(v) for k, v in by.items()}


def rule_out_split():
    out = {}
    for model in ('opus', 'haiku'):
        E = json.load(open(os.path.join(HERE, 'evals', f'pilot3_{model}.json')))
        M = _task_arm_means(E, 'out')
        tasks = sorted({t for t, _ in M if all((t, a) in M for a in ('LOG', 'WIN', 'NONE'))})
        ln = [M[(t, 'LOG')] - M[(t, 'NONE')] for t in tasks]
        hw = [(M[(t, 'WIN')] - M[(t, 'LOG')]) / 2 for t in tasks]
        out[model] = dict(log_minus_none=sum(ln) / len(ln), half_win_minus_log=sum(hw) / len(hw), n=len(tasks))
    return out


def win_log_out_pilots():
    """WIN − LOG по выходным токенам, среднее по задачам: пилот 0 и 1 — повтор 0, пилот 2 — повтор 1 (evals/pilot12), пилот 3 — среднее
    двух повторов."""
    src = dict(pilot0=('pilot0', ('0',)), pilot1=('pilot1', ('0',)), pilot2=('pilot12', ('1',)), pilot3=('pilot3', ('0', '1')))
    out = {}
    for model in ('opus', 'haiku'):
        for name, (fn, reps) in src.items():
            R = json.load(open(os.path.join(HERE, 'evals', f'{fn}_{model}.json')))['rows']
            tasks = sorted({r['task'] for r in R.values()})
            d = []
            for t in tasks:
                v = {}
                for a in ('LOG', 'WIN'):
                    x = [float(R[f'{t}|{a}|{k}']['out']) for k in reps if R.get(f'{t}|{a}|{k}') and R[f'{t}|{a}|{k}']['valid']]
                    if x:
                        v[a] = sum(x) / len(x)
                if len(v) == 2:
                    d.append(v['WIN'] - v['LOG'])
            out[f'{model}|{name}'] = dict(mean=sum(d) / len(d), n=len(d))
    return out
