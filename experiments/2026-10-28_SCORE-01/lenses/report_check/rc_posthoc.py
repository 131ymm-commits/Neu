#!/usr/bin/env python3
"""Независимый пересчёт пост-хока П1–П6 SCORE-01 из rc_rows.pkl (свои меры), свои ГСЧ (numpy) для перестановок и бутстрепа.
Плюс проверка довода «симметричная монотонная перекалибровка не меняет AUC второго рода»."""
import json, math, os, pickle
import numpy as np
from scipy import stats

OUT = os.path.dirname(os.path.abspath(__file__))
EXP = '/home/claude/neu/experiments/2026-10-28_SCORE-01'
rows_all = pickle.load(open(f'{OUT}/rc_rows.pkl', 'rb'))
V = pickle.load(open(f'{OUT}/rc_verdicts.pkl', 'rb'))
F = json.load(open(f'{EXP}/report_facts_score01.json'))['posthoc']
ST = ['main_opus', 'rep_opus', 'main_haiku', 'rep_haiku']
ARMS = ['LOG', 'WIN', 'NONE']
L = []
rng = np.random.default_rng(20261029)


def tasks_of(rows):
    return sorted({r['task'] for r in rows.values()})


def arm_task_vals(rows, arm, m):
    d = {}
    for r in rows.values():
        if r['arm'] == arm and r['valid']:
            d.setdefault(r['task'], []).append(r[m] if m != 'out' else float(r['out']))
    return {t: sum(v) / len(v) for t, v in d.items()}


# П1: WIN − LOG по самообману и точности, 95 % t, p перестановки знаков (своя оценка МК, 200 000)
for st in ST:
    rows = rows_all[st]
    for m in ('self_dec', 'acc'):
        w, l = arm_task_vals(rows, 'WIN', m), arm_task_vals(rows, 'LOG', m)
        x = np.array([w[t] - l[t] for t in tasks_of(rows)])
        n = len(x); mm = x.mean(); se = x.std(ddof=1) / math.sqrt(n); q = stats.t.ppf(0.975, n - 1)
        obs = abs(x.sum())
        hits = 0; B = 200_000
        for _ in range(B // 20000):
            s = rng.choice([-1.0, 1.0], size=(20000, n))
            hits += int(np.sum(np.abs(s @ x) >= obs - 1e-12))
        p = (hits + 1) / (B + 1)
        their = F['P1']['rows'][f'{st}|{m}']
        L.append(f'П1 {st} {m}: {mm:+.4f} 95% [{mm - q * se:+.4f}; {mm + q * se:+.4f}] p_МК {p:.4f} | их: {their["mean"]:+.4f} '
                 f'[{their["ci95"][0]:+.4f}; {their["ci95"][1]:+.4f}] p {their["p"]:.4f}')
# П2
for st in ST:
    rows = rows_all[st]
    cs, as_ = [], []
    for arm in ARMS:
        v = [r for r in rows.values() if r['arm'] == arm and r['valid']]
        cs.append(sum(r['conf'] for r in v) / len(v)); as_.append(sum(r['acc'] for r in v) / len(v))
    L.append(f'П2 {st}: уверенность {min(cs):.4f}–{max(cs):.4f} (размах {max(cs) - min(cs):.4f}); точность {min(as_):.4f}–{max(as_):.4f} '
             f'(размах {max(as_) - min(as_):.4f}); точность шире: {max(as_) - min(as_) > max(cs) - min(cs)}')


# П3: AUC второго рода (уверенность верных против неверных суждений; p = 0,5 не входят), бутстреп по задачам; Пирсон по задачам
def auc_rank(c, ok):
    c = np.asarray(c, float); ok = np.asarray(ok, bool)
    r = stats.rankdata(c)
    n1 = ok.sum(); n0 = len(ok) - n1
    return (r[ok].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


above = 0
p3 = {}
for st in ST:
    rows = rows_all[st]
    T = tasks_of(rows)
    for arm in ARMS:
        J = {t: [] for t in T}
        for r in rows.values():
            if r['arm'] == arm and r['valid']:
                for p, y in zip(r['p'], r['labels']):
                    if p != 0.5:
                        J[r['task']].append((max(p, 1 - p), (p > 0.5) == (y == 1)))
        allj = [j for t in T for j in J[t]]
        a0 = auc_rank([c for c, _ in allj], [o for _, o in allj])
        bs = []
        for _ in range(4000):
            idx = rng.integers(0, len(T), len(T))
            smp = [j for i in idx for j in J[T[i]]]
            bs.append(auc_rank([c for c, _ in smp], [o for _, o in smp]))
        lo, hi = np.percentile(bs, [2.5, 97.5])
        xc = arm_task_vals(rows, arm, 'conf'); xa = arm_task_vals(rows, arm, 'acc')
        tt = sorted(xc)
        rho = np.corrcoef([xc[t] for t in tt], [xa[t] for t in tt])[0, 1]
        their = F['P3']['rows'][f'{st}|{arm}']
        above += lo > 0.5
        p3[(st, arm)] = (a0, lo, hi, rho)
        L.append(f'П3 {st} {arm}: суждений {len(allj)} (верных {sum(o for _, o in allj)}); AUC2 {a0:.4f} [{lo:.4f}; {hi:.4f}] (свой бутстреп 4000); '
                 f'r по задачам {rho:.4f} | их: {their["n"]} ({their["n_correct"]}), {their["auc2"]:.4f} [{their["ci95"][0]:.4f}; {their["ci95"][1]:.4f}], r {their["r_tasks"]:.4f}')
L.append(f'П3: нижняя граница выше 0,5 (мой бутстреп) в {above} клетках из 12 (у них {F["P3"]["ci_above_half"]})')
L.append(f'П3: диапазон AUC2 {min(v[0] for v in p3.values()):.4f}–{max(v[0] for v in p3.values()):.4f}; '
         f'r {min(v[3] for v in p3.values()):.4f}–{max(v[3] for v in p3.values()):.4f}')
# П4
for st in ST:
    rows = rows_all[st]
    o = {a: np.mean([r['out'] for r in rows.values() if r['arm'] == a and r['valid']]) for a in ARMS}
    L.append(f'П4 {st}: WIN/LOG {o["WIN"] / o["LOG"]:.4f}; (LOG+WIN)/2/NONE {(o["LOG"] + o["WIN"]) / 2 / o["NONE"]:.4f}; '
             f'WIN/NONE {o["WIN"] / o["NONE"]:.4f}; LOG/NONE {o["LOG"] / o["NONE"]:.4f}')
# П5
picked = ['SC_opus', 'SD_opus', 'SL_opus', 'SD_haiku', 'SL_haiku']
expl = ['OE1', 'OE2', 'OE3', 'H7', 'HE1', 'HE2', 'HE3']
both_c = sum(1 for c in picked if V['composites'][f'{c}|main_{c.split("_")[1]}'][1] == V['composites'][f'{c}|rep_{c.split("_")[1]}'][1] == 'подтверждено')
cnt = {e: [V['verdicts'][f'{e}|{s}_{"opus" if e.startswith("O") else "haiku"}']['outcome'] for s in ('main', 'rep')].count('подтверждено') for e in expl}
L.append(f'П5: сводных с направлением по пилотам в обеих выборках {both_c} из {len(picked)}; разведка в обеих {sum(v == 2 for v in cnt.values())}, '
         f'ровно в одной {sum(v == 1 for v in cnt.values())}, ни в одной {sum(v == 0 for v in cnt.values())} из {len(expl)}')
# П6
cells = []
for st in ST:
    rows = rows_all[st]
    for a in ARMS:
        v = [r for r in rows.values() if r['arm'] == a and r['valid']]
        cells.append((st, a, np.mean([r['self_dec'] for r in v]), np.mean([r['ioi'] for r in v]), np.mean([r['ignorance'] for r in v]),
                      np.mean([r['deception'] for r in v])))
for k, name in ((2, 'самообман'), (3, 'ИОИ'), (4, 'незнание'), (5, 'самообман в ИОИ (max(0,·) по вызову)')):
    s = sorted(cells, key=lambda c: c[k])
    L.append(f'П6 {name}: {s[0][k]:.4f} ({s[0][0]} {s[0][1]}) — {s[-1][k]:.4f} ({s[-1][0]} {s[-1][1]})')
for st in ST:
    c = [x for x in cells if x[0] == st]
    L.append(f'П6 {st}: наибольший самообман — {max(c, key=lambda x: x[2])[1]}, ИОИ — {max(c, key=lambda x: x[3])[1]}')

# Довод «Чтения»: симметричная строго монотонная перекалибровка g (g(1−p) = 1 − g(p)) не меняет AUC2; линейное сжатие к 0,5
def shrink(p, k):
    return 0.5 + k * (p - 0.5)

for st in ('main_opus', 'main_haiku'):
    rows = rows_all[st]
    for arm in ('LOG',):
        v = [r for r in rows.values() if r['arm'] == arm and r['valid']]
        acc = np.mean([r['acc'] for r in v])
        for k in (1.0, 0.6, 0.3):
            cc, oo, conf = [], [], []
            for r in v:
                for p, y in zip(r['p'], r['labels']):
                    q = shrink(p, k)
                    conf.append(max(q, 1 - q))
                    if q != 0.5:
                        cc.append(max(q, 1 - q)); oo.append((q > 0.5) == (y == 1))
            L.append(f'перекалибровка {st} {arm} k={k}: средняя уверенность {np.mean(conf):.4f}, точность {acc:.4f}, '
                     f'самообман {np.mean(conf) - acc:+.4f}, AUC2 {auc_rank(cc, oo):.4f}')
        # нелинейная симметричная строго монотонная: логит-сжатие
        for gam in (0.5,):
            cc, oo = [], []
            for r in v:
                for p, y in zip(r['p'], r['labels']):
                    pc = min(max(p, 1e-9), 1 - 1e-9)
                    z = math.log(pc / (1 - pc)) * gam
                    q = 1 / (1 + math.exp(-z))
                    if p != 0.5:
                        cc.append(max(q, 1 - q)); oo.append((q > 0.5) == (y == 1))
            L.append(f'перекалибровка {st} {arm} логит×{gam}: AUC2 {auc_rank(cc, oo):.4f}')
open(f'{OUT}/rc_posthoc.log', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
