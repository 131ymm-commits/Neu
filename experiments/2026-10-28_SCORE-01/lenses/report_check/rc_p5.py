#!/usr/bin/env python3
"""П5 подробнее: знак точечной оценки теста против пилотного направления; исход против мощности (§6) и ожиданий (§5)."""
import json, os, pickle
OUT = os.path.dirname(os.path.abspath(__file__))
EXP = '/home/claude/neu/experiments/2026-10-28_SCORE-01'
V = pickle.load(open(f'{OUT}/rc_verdicts.pkl', 'rb'))
PP = dict(json.load(open(f'{EXP}/pilot_power.json'))['preds'])
EXPECT = {'O7': 0.30, 'O8': 0.70, 'O9': 0.60, 'H8': 0.60, 'H9': 0.85, 'OE1': 0.35, 'OE2': 0.40, 'OE3': 0.55, 'H7': 0.25, 'HE1': 0.15, 'HE2': 0.25, 'HE3': 0.65}
L = []
sums = {}
for grp, ids in (('сводные', ['O7', 'O8', 'O9', 'H8', 'H9']), ('разведка', ['OE1', 'OE2', 'OE3', 'H7', 'HE1', 'HE2', 'HE3'])):
    s = dict(exp=0, pw=0, pw2=0, main=0, rep=0, both=0, sign_both=0)
    for i in ids:
        mdl = 'opus' if i.startswith('O') else 'haiku'
        kind = PP[i]['kind']; sgn = 1 if kind == 'gt0' else -1
        vm, vr = V['verdicts'][f'{i}|main_{mdl}'], V['verdicts'][f'{i}|rep_{mdl}']
        pw = PP[i]['power_low']
        okm, okr = vm['outcome'] == 'подтверждено', vr['outcome'] == 'подтверждено'
        sm, sr = sgn * vm['mean'] > 0, sgn * vr['mean'] > 0
        s['exp'] += EXPECT[i]; s['pw'] += pw; s['pw2'] += pw * pw; s['main'] += okm; s['rep'] += okr; s['both'] += okm and okr; s['sign_both'] += sm and sr
        L.append(f'{i:4s} {kind}: пилот 3 {PP[i]["pilot_mean"]:+.4g}; тест {vm["mean"]:+.4g} / {vr["mean"]:+.4g}; знак как в пилоте: {sm}/{sr}; '
                 f'мощность (нижняя) {pw:.3f}; ожидание {EXPECT[i]:.2f}; исход {vm["outcome"]} / {vr["outcome"]}')
    L.append(f'{grp}: сумма ожиданий §5 {s["exp"]:.2f}, сумма мощностей {s["pw"]:.2f}, сумма квадратов мощностей {s["pw2"]:.2f}; '
             f'подтверждено: основная {s["main"]}, повтор {s["rep"]}, обе {s["both"]}; знак точечной оценки как в пилоте в обеих — {s["sign_both"]} из {len(ids)}')
open(f'{OUT}/rc_p5.log', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
