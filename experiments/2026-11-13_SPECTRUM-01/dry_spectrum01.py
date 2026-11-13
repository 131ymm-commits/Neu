#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-01: сухой прогон анализа на заглушках (10 блоков; ожидания записаны до прогона; редакция после совета 48).
Теория в заглушках: λ_S(q = 1) = 1,68; при q = 0 λ_S = 1,12, λ_O = 1,13 → теория отношения √(1,68/1,13) = 1,219.
  true      — богатый: CKA 0,47 → 0,99, середина подъёма 14,4 (q = 1) и 17,6 (q = 0 и q0_d64); ленивый плоский →
              P3 «подтверждено», P1a, P1b, P2 пройдены, вердикт «гипотеза подтверждена»;
  null      — богатый плоский, как ленивый → P1a не пройдена, вердикт «не определено: проверка метода…»;
  reverse   — q = 0 раньше q = 1 во всех блоках → P3 «опровергнуто», вердикт «гипотеза опровергнута»;
  ties      — середины подъёма равны (17,6) при q = 0 и q = 1, без шума → ничьи не засчитываются против гипотезы:
              P3 «не решено» (отношение/теория 0,82, отклонение 0,18), вердикт «не решено» (совет 48, п. «а»);
  undef     — в 2 блоках богатый при q = 1 плоский (t_align не определено) → определено 8 < 9: P3 «не решено»; та же
              плоскость проваливает и проверку метода P1a (8 из 10) → вердикт «не определено…» (ожидание поправлено
              после первого запуска: сначала я ждал «не решено», не учтя, что P1a проверяется раньше P3);
  lazymoves — ленивый тоже поднимается до 0,95 → P1a и P2 не пройдены, вердикт «не определено…»."""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DRY = os.path.join(HERE, 'dry')
STEPS = {'rich': list(range(0, 151)) + list(range(155, 301, 5)),
         'lazy': list(range(0, 151)) + list(range(155, 601, 5)) + list(range(625, 3001, 25))}


def curve(steps, c0, c1, mid, width=2.5):
    s = np.asarray(steps, float)
    return c0 + (c1 - c0) / (1 + np.exp(-(s - mid) / width))


def group(b, q, regime, nz, ex, scen, g):
    st = STEPS[regime]
    c0 = {0: 0.815, 20: 0.6, 52: 0.47}[nz] + 0.01 * g.standard_normal()
    flat = curve(st, c0, c0 + 0.03, 1500, 300)
    if regime == 'rich' and scen not in ('null',) and not (scen == 'undef' and q == 1.0 and b < 2):
        if scen == 'reverse':
            mid = 17.6 if q == 1.0 else 14.4
        elif scen == 'ties':
            mid = 17.6
        else:
            mid = 14.4 if q == 1.0 else 17.6
        cur = curve(st, c0, 0.99, mid + (0 if scen == 'ties' else 0.3 * g.standard_normal()))
    elif regime == 'lazy' and scen == 'lazymoves':
        cur = curve(st, c0, 0.95, 400)
    else:
        cur = flat
    noise = 0 if scen == 'ties' else 0.003
    jit = lambda: (cur[:, None] + noise * g.standard_normal((len(st), 6))).tolist()
    return dict(block=b, q=q, regime=regime, d_nuis=nz, extra=ex, step=st, ckaA=jit(), ckaB=jit(),
                behav=[[0.996] * 6 for _ in st], r2=[[[0.99] * 5 for _ in range(4)] for _ in st], ref=[[0.997] * 5] * 4,
                perm=[[0.01, 0.002, 0.02]] * 6, mknn0=[0.09] * 6, mknnT=[0.85 if regime == 'rich' else 0.1] * 6,
                theory=[{'S': 1.68 if q == 1.0 else 1.12, 'O': 1.13, 'B': 0.64}] * 4)


def build(scen):
    g = np.random.default_rng(len(scen))
    G = [group(b, q, rg, 52, 0, scen, g) for b in range(10) for q in (0.0, 1.0) for rg in ('rich', 'lazy')]
    G += [group(b, 0.0, 'rich', 52, 2, scen, g) for b in range(10)]
    G += [group(b, 1.0, rg, nz, 0, scen, g) for nz in (0, 20) for b in range(10) for rg in ('rich', 'lazy')]
    return G


def main():
    os.makedirs(DRY, exist_ok=True)
    expect = {'true': ({'P3': 'подтверждено'}, dict(P1a=True, P1b=True, P2=True), 'гипотеза подтверждена'),
              'null': ({}, dict(P1a=False), 'не определено'),
              'reverse': ({'P3': 'опровергнуто'}, {}, 'гипотеза опровергнута'),
              'ties': ({'P3': 'не решено'}, {}, 'не решено'),
              'undef': ({'P3': 'не решено'}, dict(P1a=False), 'не определено'),
              'lazymoves': ({}, dict(P1a=False, P2=False), 'не определено')}
    bad = []
    for scen, (want3, want, vwant) in expect.items():
        src, dst = os.path.join(DRY, f'{scen}.json'), os.path.join(DRY, f'{scen}_an.json')
        json.dump(dict(d_nuis=52, groups=build(scen)), open(src, 'w'))
        r = subprocess.run([sys.executable, os.path.join(HERE, 'analyze_spectrum01.py'), src, dst], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[-1500:]); bad.append(scen); continue
        a = json.load(open(dst, encoding='utf-8'))
        got3 = {'P3': a['P3']['verdict']} if want3 else {}
        got = {k: a[k]['ok'] for k in want}
        ok = got3 == want3 and got == want and a['verdict'].startswith(vwant)
        print(scen, '✓' if ok else '✗', got3, got, '|', a['verdict'][:70], '| n_def', a['P3']['n_defined'], 'k', a['P3']['k'],
              'k_rev', a['P3']['k_rev'], 'отн/теор', None if a['P3']['median_rel'] is None else round(a['P3']['median_rel'], 3))
        if not ok:
            bad.append(scen)
        os.remove(src)
    json.dump({'bad': bad}, open(os.path.join(DRY, 'dry_summary.json'), 'w'))
    print('несовпадений:', bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
