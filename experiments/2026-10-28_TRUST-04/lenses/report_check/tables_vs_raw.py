#!/usr/bin/env python3
"""Сверка таблиц REPORT-TRUST-04.md с пересчётом из сырых results_*.json (не из facts и не из analysis).
Руки, половины окна, части Прайса, EB6, срывы, проверки построения, блоки А/Б/В, разведка."""
import json, math, re
import numpy as np
from scipy import stats

D = '/home/claude/neu/experiments/2026-10-28_TRUST-04'
rep = open(f'{D}/REPORT-TRUST-04.md', encoding='utf-8').read()
A = json.load(open(f'{D}/results_trust_04_A.json'))
B = json.load(open(f'{D}/results_trust_04_B.json'))
FZ = {'base': (0.9873, 0.6891), 'r075': (0.5768, 0.3897), 'r095': (1.7134, 1.1968), 'b03': (1.2221, 0.9622), 'b09': (0.8328, 0.5372)}
ARMS = A['params']['ARMS']
seeds = list(range(600, 620))
RUN = {}
for d in (A, B):
    for r in d['runs']:
        RUN[(r['seed'], r['arm'])] = r
F = {k: v['final'] for k, v in RUN.items()}


def boot(x, B_=10000, seed=0):
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    m = x[g.integers(0, len(x), (B_, len(x)))].mean(1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def fmt(x, d=4):
    s = f'{x:.{d}f}'.replace('.', ',').replace('-', '−')
    return s


ci = lambda v: f'{fmt(v[0])} [{fmt(v[1])}; {fmt(v[2])}]'


def u_arm(a):
    my, far = FZ[ARMS[a]['world']]
    return [(F[(s, a)]['wG'] - far) / (my - far) for s in seeds]


col = lambda a, k: [F[(s, a)][k] for s in seeds]
rows = {}
for line in rep.splitlines():
    if line.startswith('| '):
        cells = [c.strip() for c in line.strip('|').split('|')]
        rows.setdefault(cells[0], []).append(cells)
bad = []
nchk = 0
# --- таблица «Руки»
for a in ARMS:
    exp = [a, ci(boot(u_arm(a))), fmt(np.mean(col(a, 'wG'))), fmt(np.mean(col(a, 'logloss'))), fmt(np.mean(col(a, 'acc'))),
           fmt(np.mean(col(a, 'self_dec'))), fmt(np.mean(col(a, 'R')), 3), fmt(np.mean(col(a, 'step_sd')))]
    got = [r for r in rows.get(a, []) if len(r) == 8]
    nchk += 1
    if not got or got[0] != exp:
        bad.append(('Руки', a, got[0] if got else None, exp))
# --- сходимость: разность половин окна по траекториям
for a in ARMS:
    my, far = FZ[ARMS[a]['world']]
    half = []
    for s in seeds:
        tr = RUN[(s, a)]['traj']
        h2 = np.mean([(t['wG'] - far) / (my - far) for t in tr if t['g'] >= 2000])
        h1 = np.mean([(t['wG'] - far) / (my - far) for t in tr if 1000 <= t['g'] < 2000])
        half.append(h2 - h1)
    exp = [a, ci(boot(half)), str(int(sum(x < 0 for x in half)))]
    got = [r for r in rows.get(a, []) if len(r) == 3 and '[' in r[1]]
    nchk += 1
    if not got or got[0] != exp:
        bad.append(('Сходимость', a, got[0] if got else None, exp))
# --- части Прайса (среднее по зёрнам, 5 знаков)
for a in ARMS:
    w = np.mean(col(a, 'price_within')); b = np.mean(col(a, 'price_between'))
    exp = [a, fmt(round(w, 5), 5), fmt(round(b, 5), 5)]
    got = [r for r in rows.get(a, []) if len(r) == 3 and '[' not in r[1]]
    nchk += 1
    if not got or got[0] != exp:
        bad.append(('Прайс', a, got[0] if got else None, exp))
# --- EB6 по рукам
E1 = ['DEMES', 'DEMES_FREE', 'DEMES_GPOOL', 'DEMES_IND', 'DEMES_MIG', 'DEMES_SIG5', 'DEMES_r075', 'DEMES_r095', 'DEMES_b03', 'DEMES_b09']
for a in E1:
    ub = np.mean(u_arm(a)); vb, vw = np.mean(col(a, 'V_between')), np.mean(col(a, 'V_within'))
    omr = 1 - vb / (vb + vw)
    exp = [a, fmt(round(ub, 4)), fmt(round(omr, 4)), fmt(round(abs(ub - omr), 4))]
    got = [r for r in rows.get(a, []) if len(r) == 4]
    nchk += 1
    if not got or got[0] != exp:
        bad.append(('EB6', a, got[0] if got else None, exp))
# --- срывы
for a in ARMS:
    if ARMS[a]['sig'] != 0.04 or ARMS[a]['sig_g'] != 0.04:
        continue
    br = [(F[(s, a)]['wG_sd_groups'] > 0.5) or (F[(s, a)]['V_within'] > 0.1) for s in seeds]
    n = sum(br)
    nchk += 1
    m = re.search(rf'^- {a}: (\d+) из 20', rep, re.M)
    if n and (not m or int(m.group(1)) != n):
        bad.append(('Срывы', a, m.group(0) if m else None, n))
    if not n and m:
        bad.append(('Срывы', a, m.group(0), 0))
    if n:
        uu = [x for x, b_ in zip(u_arm(a), br) if b_]
        vv = [F[(s, a)]['V_within'] for s, b_ in zip(seeds, br) if b_]
        line = [l for l in rep.splitlines() if l.startswith(f'- {a}:')][0]
        if ', '.join(fmt(x) for x in uu) not in line or ', '.join(fmt(x) for x in vv) not in line:
            bad.append(('Срывы-числа', a))
# SD шага DEMES_NOWITHIN без срывов
br = [(F[(s, 'DEMES_NOWITHIN')]['wG_sd_groups'] > 0.5) or (F[(s, 'DEMES_NOWITHIN')]['V_within'] > 0.1) for s in seeds]
st = [F[(s, 'DEMES_NOWITHIN')]['step_sd'] for s, b_ in zip(seeds, br) if not b_]
nchk += 1
if f'SD шага DEMES_NOWITHIN без срывов — {ci(boot(st))}' not in rep:
    bad.append(('step_nb', ci(boot(st))))
# проверки построения
for a in ('POOLED_NOSEL', 'POOLED_NOSEL_FREE'):
    gap = [F[(s, a)]['logloss'] - F[(s, 'POOLED')]['logloss'] for s in seeds]
    s_ = (f"- {a}: разность лог-потери с POOLED {ci(boot(gap))}, зёрен с разностью ≥ 0,02 — {sum(x >= 0.02 for x in gap)}; "
          f"w_G {ci(boot(col(a, 'wG')))}; SD между группами {ci(boot(col(a, 'wG_sd_groups')))}.")
    nchk += 1
    if s_ not in rep:
        bad.append(('K', a, s_))
print('проверено строк/ячеек-групп:', nchk, '; расхождений:', len(bad))
for b_ in bad:
    print('  ', b_)
