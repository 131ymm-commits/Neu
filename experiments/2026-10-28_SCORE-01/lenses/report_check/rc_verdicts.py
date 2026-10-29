#!/usr/bin/env python3
"""Независимый пересчёт вердиктов SCORE-01 по букве PREREG §2, §4 (проверяющий). Меры — rc_rows.pkl (rc_measures.py).
Предсказания выписаны заново из текста PREREG §4 (не из analyze_score01.py)."""
import json, math, os, pickle
from scipy import stats

EXP = '/home/claude/neu/experiments/2026-10-28_SCORE-01'
SEL = '/home/claude/neu/experiments/2026-10-07_SELECT-01'
OUT = os.path.dirname(os.path.abspath(__file__))
rows_all = pickle.load(open(f'{OUT}/rc_rows.pkl', 'rb'))

RULE = {'LOG': 0.5, 'WIN': 0.5, 'NONE': -1.0}
NONE_MINUS = {'NONE': 1.0, 'LOG': -0.5, 'WIN': -0.5}
WL = {'WIN': 1.0, 'LOG': -1.0}
# id, модель, мера, веса рук, вид, допуск, сводный
PREDS = [
    ('O1', 'opus', 'self_dec', WL, 'eq', 0.1, 'SA_opus'), ('O2', 'opus', 'acc', WL, 'eq', 0.1, 'SA_opus'),
    ('O3', 'opus', 'brier', WL, 'eq', 0.05, 'SA_opus'),
    ('O4', 'opus', 'self_dec', {'LOG': 1.0}, 'gt', None, 'SB_opus'), ('O5', 'opus', 'self_dec', {'WIN': 1.0}, 'gt', None, 'SB_opus'),
    ('O6', 'opus', 'self_dec', {'NONE': 1.0}, 'gt', None, 'SB_opus'),
    ('O7', 'opus', 'acc', RULE, 'gt', None, 'SC_opus'), ('O8', 'opus', 'out', RULE, 'gt', None, 'SD_opus'),
    ('O9', 'opus', 'out', WL, 'lt', None, 'SL_opus'),
    ('OE1', 'opus', 'conf', WL, 'lt', None, None), ('OE2', 'opus', 'self_dec', NONE_MINUS, 'gt', None, None),
    ('OE3', 'opus', 'auc', RULE, 'gt', None, None),
    ('H1', 'haiku', 'self_dec', WL, 'eq', 0.1, 'SA_haiku'), ('H2', 'haiku', 'acc', WL, 'eq', 0.1, 'SA_haiku'),
    ('H3', 'haiku', 'brier', WL, 'eq', 0.05, 'SA_haiku'),
    ('H4', 'haiku', 'self_dec', {'LOG': 1.0}, 'gt', None, 'SB_haiku'), ('H5', 'haiku', 'self_dec', {'WIN': 1.0}, 'gt', None, 'SB_haiku'),
    ('H6', 'haiku', 'self_dec', {'NONE': 1.0}, 'gt', None, 'SB_haiku'),
    ('H8', 'haiku', 'out', RULE, 'gt', None, 'SD_haiku'), ('H9', 'haiku', 'out', WL, 'gt', None, 'SL_haiku'),
    ('H7', 'haiku', 'acc', RULE, 'gt', None, None), ('HE1', 'haiku', 'self_dec', NONE_MINUS, 'gt', None, None),
    ('HE2', 'haiku', 'auc', RULE, 'gt', None, None), ('HE3', 'haiku', 'acc', WL, 'gt', None, None),
]
REPS = dict(opus=['0'], haiku=['0', '1'])


def sample_tasks(sample):
    rng = range(8001, 8101) if sample == 'main' else range(8101, 8201)
    return [f'WH_{s}' for s in rng if os.path.exists(f'{SEL}/pools/WH_{s}.json')]


def tint(x, level):
    n = len(x); m = sum(x) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1))
    h = stats.t.ppf(1 - (1 - level) / 2, n - 1) * sd / math.sqrt(n)
    return m, m - h, m + h


def val(r, m):
    return float(r['out']) if m == 'out' else r[m]


def series(rows, tasks, w, m, reps):
    xs = []
    for t in tasks:
        v = {}
        for a in w:
            got = [val(rows[f'{t}|{a}|{rp}'], m) for rp in reps if f'{t}|{a}|{rp}' in rows and rows[f'{t}|{a}|{rp}']['valid']]
            if got:
                v[a] = sum(got) / len(got)
        if len(v) == len(w):
            xs.append(sum(w[a] * v[a] for a in w))
    return xs


A = json.load(open(f'{EXP}/analysis_score01.json'))
lines = []
mism = []
mine = {'verdicts': {}, 'composites': {}, 'status': {}, 'aa': {}}
for st in ['main_opus', 'rep_opus', 'main_haiku', 'rep_haiku']:
    sample, model = st.split('_')
    rows = rows_all[st]
    tasks = sample_tasks(sample)
    assert set(tasks) == {r['task'] for r in rows.values()}, st
    for pid, mdl, m, w, kind, d, comp in PREDS:
        if mdl != model:
            continue
        x = series(rows, tasks, w, m, REPS[model])
        if len(x) < 0.9 * len(tasks):
            out = 'не показано (потери)'; ci = None; mean = None
        elif kind == 'eq':
            mean, lo, hi = tint(x, 0.90); ci = (lo, hi)
            out = 'подтверждено' if (lo > -d and hi < d) else ('опровергнуто' if (lo >= d or hi <= -d) else 'не показано')
        else:
            mean, lo, hi = tint(x, 0.95); ci = (lo, hi)
            if kind == 'gt':
                out = 'подтверждено' if lo > 0 else ('опровергнуто' if hi < 0 else 'не показано')
            else:
                out = 'подтверждено' if hi < 0 else ('опровергнуто' if lo > 0 else 'не показано')
        mine['verdicts'][f'{pid}|{st}'] = dict(outcome=out, mean=mean, ci=ci, n=len(x), n_tasks=len(tasks))
        av = A['verdicts'][f'{pid}|{st}']
        aci = av['ci90'] if kind == 'eq' else av['ci95']
        dm = abs(av['mean'] - mean); dci = max(abs(aci[0] - ci[0]), abs(aci[1] - ci[1]))
        ok = av['outcome'] == out and av['n'] == len(x) and dm < 1e-9 and dci < 1e-9
        if not ok:
            mism.append((pid, st, av['outcome'], out, dm, dci))
        lines.append(f'{pid:4s} {st:10s} {m:8s} {kind}: {out:14s} {mean:+.4f} [{ci[0]:+.4f}; {ci[1]:+.4f}] n {len(x)}/{len(tasks)}'
                     f' | анализ: {av["outcome"]}, |Δсреднего| {dm:.1e}, |Δинтервала| {dci:.1e}')
    # A/A у Haiku
    flag = False
    if model == 'haiku':
        aa = {}
        for arm in ('LOG', 'WIN', 'NONE'):
            for m, d in (('self_dec', 0.1), ('acc', 0.1), ('brier', 0.05)):
                x = [val(rows[f'{t}|{arm}|1'], m) - val(rows[f'{t}|{arm}|0'], m) for t in tasks
                     if rows[f'{t}|{arm}|0']['valid'] and rows[f'{t}|{arm}|1']['valid']]
                mm, lo, hi = tint(x, 0.90)
                aa[f'{arm}|{m}'] = (mm, lo, hi, len(x), lo > -d and hi < d, lo >= d or hi <= -d)
                an = A['aa'][st]['arms'][f'{arm}|{m}']
                if abs(an['mean'] - mm) > 1e-9 or abs(an['ci90'][0] - lo) > 1e-9 or an['within'] != (lo > -d and hi < d):
                    mism.append(('AA', st, arm, m))
        diff = {}
        for m, d in (('self_dec', 0.1), ('acc', 0.1), ('brier', 0.05)):
            x = [(val(rows[f'{t}|WIN|1'], m) - val(rows[f'{t}|WIN|0'], m)) - (val(rows[f'{t}|LOG|1'], m) - val(rows[f'{t}|LOG|0'], m))
                 for t in tasks]
            mm, lo, hi = tint(x, 0.90)
            within = lo > -2 * d and hi < 2 * d
            diff[m] = (mm, lo, hi, len(x), within)
            an = A['aa'][st]['diff'][m]
            if abs(an['mean'] - mm) > 1e-9 or abs(an['ci90'][1] - hi) > 1e-9 or an['within'] != within:
                mism.append(('AAdiff', st, m))
        flag = not all(v[4] for v in diff.values())
        mine['aa'][st] = dict(arms=aa, diff=diff, flag=flag)
        lines.append(f'{st}: A/A разность между руками: ' + '; '.join(f'{m} {v[0]:+.3f} [{v[1]:+.3f}; {v[2]:+.3f}] внутри {v[4]}' for m, v in diff.items())
                     + f' → флаг {flag} (анализ: {A["aa"][st]["flag"]})')
        lines.append(f'{st}: A/A по рукам: ' + '; '.join(f'{k} {v[0]:+.3f} [{v[1]:+.3f}; {v[2]:+.3f}] n{v[3]} внутри {v[4]} вне {v[5]}' for k, v in aa.items()))
    # контекст: флаг из analysis (пересчитывается отдельно в rc_ctx.py)
    ctxflag = A['ctx'][st]['flag']
    for comp in sorted({p[6] for p in PREDS if p[6] and p[1] == model}):
        parts = [p[0] for p in PREDS if p[6] == comp]
        outs = [mine['verdicts'][f'{i}|{st}']['outcome'] for i in parts]
        o = 'подтверждено' if all(x == 'подтверждено' for x in outs) else ('опровергнуто' if 'опровергнуто' in outs else 'не подтверждено')
        rd = 'не показано (контекст)' if ctxflag else ('не показано (A/A: артефакт повтора различает руки)' if comp.startswith('SA_') and flag and o == 'подтверждено' else o)
        mine['composites'][f'{comp}|{st}'] = (o, rd)
        if A['composites'][f'{comp}|{st}']['outcome'] != o or A['readings'][f'{comp}|{st}'] != rd:
            mism.append(('comp', comp, st))
        lines.append(f'сводный {comp} {st}: {o}; чтение {rd} ({", ".join(f"{i} {x}" for i, x in zip(parts, outs))})')
for comp in sorted({p[6] for p in PREDS if p[6]}):
    model = comp.split('_')[1]
    m_, r_ = mine['composites'][f'{comp}|main_{model}'][1], mine['composites'][f'{comp}|rep_{model}'][1]
    if m_ == r_ == 'подтверждено':
        s = 'установлено' if comp[:2] in ('SA', 'SB') else 'подтверждено (повторено; причина не проверялась)'
    else:
        s = f'{m_}; повтор: {r_}'
    mine['status'][comp] = s
    if A['status'][comp]['status'] != s:
        mism.append(('status', comp, A['status'][comp]['status'], s))
    lines.append(f'статус {comp}: {s} (анализ: {A["status"][comp]["status"]})')
lines.append(f'РАСХОЖДЕНИЙ С analysis_score01.json: {len(mism)} {mism}')
pickle.dump(mine, open(f'{OUT}/rc_verdicts.pkl', 'wb'))
open(f'{OUT}/rc_verdicts.log', 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
