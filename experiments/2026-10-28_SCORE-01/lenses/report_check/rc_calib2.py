#!/usr/bin/env python3
"""Оправдалась ли поправка вниз (§5) против мощности (§6): Брайер и средняя вероятность — ожидания §5 против нижней мощности §6."""
import json, os, pickle
OUT = os.path.dirname(os.path.abspath(__file__))
EXP = '/home/claude/neu/experiments/2026-10-28_SCORE-01'
V = pickle.load(open(f'{OUT}/rc_verdicts.pkl', 'rb'))
PP = dict(json.load(open(f'{EXP}/pilot_power.json'))['preds'])
P5 = {'O1': .70, 'O2': .70, 'O3': .65, 'O4': .90, 'O5': .93, 'O6': .95, 'O7': .30, 'O8': .70, 'O9': .60, 'OE1': .35, 'OE2': .40, 'OE3': .55,
      'H1': .60, 'H2': .30, 'H3': .65, 'H4': .95, 'H5': .90, 'H6': .90, 'H8': .60, 'H9': .85, 'H7': .25, 'HE1': .15, 'HE2': .25, 'HE3': .65}
L = []
for mdl in ('opus', 'haiku'):
    ids = [i for i in P5 if (i.startswith('O')) == (mdl == 'opus')]
    for key in ('power_low', 'power_assurance'):
        pass
    for samp in ('main', 'rep', 'обе'):
        outs = []
        for i in ids:
            if samp == 'обе':
                for s in ('main', 'rep'):
                    outs.append((i, 1 if V['verdicts'][f'{i}|{s}_{mdl}']['outcome'] == 'подтверждено' else 0))
            else:
                outs.append((i, 1 if V['verdicts'][f'{i}|{samp}_{mdl}']['outcome'] == 'подтверждено' else 0))
        n = len(outs); hit = sum(t for _, t in outs) / n
        res = []
        for lab, prob in (('ожидания §5', lambda i: P5[i]), ('мощность нижняя §6', lambda i: PP[i]['power_low']),
                          ('мощность с неопр. пилота', lambda i: PP[i]['power_assurance'])):
            c = sum(prob(i) for i, _ in outs) / n
            b = sum((prob(i) - t) ** 2 for i, t in outs) / n
            res.append(f'{lab}: ср. {c:.3f}, Брайер {b:.4f}')
        L.append(f'{mdl} {samp}: доля подтверждённых {hit:.3f}; ' + '; '.join(res))
open(f'{OUT}/rc_calib2.log', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
