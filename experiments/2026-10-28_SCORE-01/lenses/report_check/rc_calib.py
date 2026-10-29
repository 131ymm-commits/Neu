#!/usr/bin/env python3
"""Калибровка: 24 строки SCORE-01 (при регистрации и сейчас), исходы против вердиктов основной выборки, сводки и класс «после пилота»."""
import ast, json, os, pickle, subprocess, re
OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = '/home/claude/neu'
V = pickle.load(open(f'{OUT}/rc_verdicts.pkl', 'rb'))
P5 = {'O1': .70, 'O2': .70, 'O3': .65, 'O4': .90, 'O5': .93, 'O6': .95, 'O7': .30, 'O8': .70, 'O9': .60, 'OE1': .35, 'OE2': .40, 'OE3': .55,
      'H1': .60, 'H2': .30, 'H3': .65, 'H4': .95, 'H5': .90, 'H6': .90, 'H8': .60, 'H9': .85, 'H7': .25, 'HE1': .15, 'HE2': .25, 'HE3': .65}  # PREREG §5, выписано вручную


def rows_of(src):
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', None) == 'ROWS':
            return ast.literal_eval(node.value)


then = rows_of(subprocess.run(['git', '-C', ROOT, 'show', '78626cd:tools/self_calibration.py'], capture_output=True, text=True, check=True).stdout)
now = rows_of(open(f'{ROOT}/tools/self_calibration.py', encoding='utf-8').read())
L = []
for name, R in (('78626cd', then), ('сейчас', now)):
    s = [r for r in R if r[0] == 'SCORE-01']
    ids = [r[1].split(' ')[0] for r in s]
    probs_ok = all(abs(r[4] - P5[i]) < 1e-12 for r, i in zip(s, ids))
    L.append(f'{name}: строк SCORE-01 {len(s)}, набор id = §5: {sorted(ids) == sorted(P5)}, вероятности = §5: {probs_ok}, исходы: {sorted({r[5] for r in s}, key=str)}')
s = [r for r in now if r[0] == 'SCORE-01']
bad = []
for r in s:
    i = r[1].split(' ')[0]
    mdl = 'opus' if i.startswith('O') else 'haiku'
    want = 1 if V['verdicts'][f'{i}|main_{mdl}']['outcome'] == 'подтверждено' else 0
    if r[5] != want:
        bad.append((i, r[5], want))
L.append(f'исходы против вердикта основной выборки: несовпадений {len(bad)} {bad}')
def summ(rs):
    n = len(rs); c = sum(r[4] for r in rs) / n; h = sum(r[5] for r in rs) / n; b = sum((r[4] - r[5]) ** 2 for r in rs) / n
    return n, c, h, b, c - h
for lab, rs in (('все 24', s), ('opus', [r for r in s if '(opus)' in r[1]]), ('haiku', [r for r in s if '(haiku)' in r[1]])):
    n, c, h, b, d = summ(rs)
    L.append(f'{lab}: n {n}, уверенность {c:.4f}, подтвердилось {h:.4f}, Брайер {b:.4f}, самообман {d:+.4f}')
# повтор у Opus
rep_hits = sum(1 for r in s if '(opus)' in r[1] and V['verdicts'][f'{r[1].split(" ")[0]}|rep_opus']['outcome'] == 'подтверждено')
L.append(f'opus по повтору: подтвердилось {rep_hits} из 12 ({rep_hits / 12:.4f})')
rep_h = sum(1 for r in s if '(haiku)' in r[1] and V['verdicts'][f'{r[1].split(" ")[0]}|rep_haiku']['outcome'] == 'подтверждено')
L.append(f'haiku по повтору: подтвердилось {rep_h} из 12 ({rep_h / 12:.4f})')
# класс «после пилота» как в main(): r[5] не None и заметка начинается с «(после пилота)»; S2 ×5
exp = [r for r in now for _ in range(5 if r[0] == 'S2' else 1)]
post = [r for r in exp if r[5] is not None and r[6].startswith('(после пилота)')]
n, c, h, b, d = summ(post)
L.append(f'класс «после пилота» сейчас: n {n}, уверенность {c:.4f}, подтвердилось {h:.4f}, Брайер {b:.4f}, самообман {d:+.4f}')
exp0 = [r for r in then for _ in range(5 if r[0] == 'S2' else 1)]
post0 = [r for r in exp0 if r[5] is not None and r[6].startswith('(после пилота)')]
n0, c0, h0, b0, d0 = summ(post0)
L.append(f'класс «после пилота» при регистрации: n {n0}, уверенность {c0:.4f}, подтвердилось {h0:.4f}, Брайер {b0:.4f}, самообман {d0:+.4f}')
# какие эксперименты в классе
from collections import Counter
L.append('состав класса сейчас: ' + str(Counter(r[0] for r in post)))
open(f'{OUT}/rc_calib.log', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
