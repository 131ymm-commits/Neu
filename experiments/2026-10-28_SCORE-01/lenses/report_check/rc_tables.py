#!/usr/bin/env python3
"""Свои строки таблиц «Руки», «Предсказания», A/A — из rc_rows.pkl/rc_verdicts.pkl; сличение со строками REPORT-SCORE-01.md."""
import os, pickle, re
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP

OUT = os.path.dirname(os.path.abspath(__file__))
EXP = '/home/claude/neu/experiments/2026-10-28_SCORE-01'
rows_all = pickle.load(open(f'{OUT}/rc_rows.pkl', 'rb'))
V = pickle.load(open(f'{OUT}/rc_verdicts.pkl', 'rb'))
rep = open(f'{EXP}/REPORT-SCORE-01.md', encoding='utf-8').read().splitlines()


def f(x, k=3):
    s = f'{x:.{k}f}'.replace('.', ',').replace('-', '−')
    return '0,000' if s == '−0,000' else s


def fi(x):
    s = f'{x:.0f}'.replace('-', '−')
    return s


res = []
# Руки
for st in ['main_opus', 'rep_opus', 'main_haiku', 'rep_haiku']:
    rows = rows_all[st]
    for arm in ('LOG', 'WIN', 'NONE'):
        v = [r for r in rows.values() if r['arm'] == arm and r['valid']]
        n_all = sum(1 for r in rows.values() if r['arm'] == arm)
        mean = lambda k: sum(r[k] for r in v) / len(v)
        from collections import Counter
        pts = [(x, l) for r in v for x, l in zip(r['p'], r['labels'])]
        cp = Counter(x for x, l in pts if l); cn = Counter(x for x, l in pts if not l)
        below = 0; num = 0.0
        for x in sorted(set(x for x, _ in pts)):
            num += cp[x] * (below + 0.5 * cn[x]); below += cn[x]
        aucp = num / (sum(cp.values()) * sum(cn.values()))
        line = (f'| {st} | {arm} | {len(v)} из {n_all} | {f(mean("acc"))} | {f(mean("conf"))} | {f(mean("conf") - mean("acc"))} | '
                f'{f(mean("brier"))} | {f(mean("logloss"))} | {f(aucp)} | {f(mean("ioi"))} = {f(mean("ignorance"))} + {f(mean("deception"))} | '
                f'{fi(mean("out"))} |')
        hit = line in rep
        res.append(('Руки', st, arm, hit, line if not hit else ''))
# Предсказания
txt = {}
for l in rep:
    m = re.match(r'^\| (O\d|OE\d|H\d|HE\d) \| (opus|haiku) \|', l)
    if m:
        txt[m.group(1)] = l
for pid in txt:
    model = 'opus' if pid.startswith('O') else 'haiku'
    cells = []
    for s in ('main', 'rep'):
        v = V['verdicts'][f'{pid}|{s}_{model}']
        if abs(v['mean']) >= 50:
            cells.append(f'{fi(v["mean"])} [{fi(v["ci"][0])}; {fi(v["ci"][1])}], {v["n"]} из {v["n_tasks"]} | {v["outcome"]}')
        else:
            cells.append(f'{f(v["mean"])} [{f(v["ci"][0])}; {f(v["ci"][1])}], {v["n"]} из {v["n_tasks"]} | {v["outcome"]}')
    tail = ' | '.join(cells) + ' |'
    hit = txt[pid].endswith(tail)
    res.append(('Предсказания', pid, '', hit, '' if hit else f'моё: {tail}\n   отчёт: {txt[pid]}'))
# A/A
for st in ('main_haiku', 'rep_haiku'):
    for k, (mm, lo, hi, n, w, o) in V['aa'][st]['arms'].items():
        arm, m = k.split('|')
        d = '0,10' if m != 'brier' else '0,05'
        line = f'| {st} | {arm}|{m} (±{d}) | {f(mm)} [{f(lo)}; {f(hi)}] | {n} | {"да" if w else "нет"} | {"да" if o else "нет"} |'
        hit = line in rep
        res.append(('A/A рук', st, k, hit, '' if hit else line))
    for m, (mm, lo, hi, n, w) in V['aa'][st]['diff'].items():
        d = {'self_dec': '±0,20', 'acc': '±0,20', 'brier': '±0,10'}[m]
        line = f'| {st} | {m} | {f(mm)} [{f(lo)}; {f(hi)}] | {n} | {d} | {"да" if w else "нет"} | {"да" if V["aa"][st]["flag"] else "нет"} |'
        hit = line in rep
        res.append(('A/A разность', st, m, hit, '' if hit else line))
bad = [r for r in res if not r[3]]
print(f'строк сверено: {len(res)}, не найдено в отчёте: {len(bad)}')
for r in bad:
    print(r)
open(f'{OUT}/rc_tables.log', 'w').write(f'строк сверено: {len(res)}, не найдено: {len(bad)}\n' + '\n'.join(map(str, bad)) + '\n')
