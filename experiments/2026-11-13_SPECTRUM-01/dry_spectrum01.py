#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-01: сухой прогон анализа на заглушках (10 блоков; ожидания записаны до прогона).
  true      — богатый: CKA 0,47 → 0,99, середина подъёма на 14,4 (q = 1) и 17,3 (q = 0); ленивый: 0,47 → 0,50;
              поведение 0,996; контроль без помех: CKA₀ 0,815 → ждём P1a, P1b, P2, P3, P4 «подтверждено»,
              вердикт «гипотеза подтверждена»;
  null      — богатый как ленивый (плоско) → P1a, P1b, P3 не подтверждены, вердикт «гипотеза опровергнута»;
  reverse   — подъём при q = 0 раньше, чем при q = 1 → P3 не подтверждено, вердикт «гипотеза опровергнута»;
  lazymoves — ленивый тоже поднимается до 0,95 → P1a и P2 не подтверждены, вердикт не «подтверждена»."""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DRY = os.path.join(HERE, 'dry')
STEPS = {'rich': list(range(0, 151)) + list(range(155, 301, 5)), 'lazy': list(range(0, 151)) + list(range(155, 601, 5)) + list(range(625, 3001, 25))}


def curve(steps, c0, c1, mid, width=2.5):
    s = np.asarray(steps, float)
    return c0 + (c1 - c0) / (1 + np.exp(-(s - mid) / width))


def group(b, q, regime, nz, scen, g):
    st = STEPS[regime]
    c0 = 0.815 if nz == 0 else 0.47 + 0.01 * g.standard_normal()
    if regime == 'rich' and scen != 'null':
        mid = (14.4 if q == 1.0 else 17.3) if scen != 'reverse' else (17.3 if q == 1.0 else 14.4)
        cur = curve(st, c0, 0.99, mid + 0.3 * g.standard_normal())
    elif regime == 'lazy' and scen == 'lazymoves':
        cur = curve(st, c0, 0.95, 400)
    else:
        cur = curve(st, c0, c0 + 0.03, 1500, 300)
    jit = lambda: (cur[:, None] + 0.003 * g.standard_normal((len(st), 6))).tolist()
    behav = [[0.996] * 6 for _ in st]
    r2 = [[[0.99] * 5 for _ in range(4)] for _ in st]
    return dict(block=b, q=q, regime=regime, d_nuis=nz, step=st, ckaA=jit(), ckaB=jit(), behav=behav, r2=r2,
                ref=[[0.997] * 5] * 4, perm=[[0.01, 0.002, 0.02]] * 6, mknn0=[0.09] * 6, mknnT=[0.85 if regime == 'rich' else 0.1] * 6,
                theory=[{'S': 1.68 if q == 1.0 else 1.12, 'O': 1.13, 'B': 0.64}] * 4)


def main():
    os.makedirs(DRY, exist_ok=True)
    expect = {'true': (dict(P1a=True, P1b=True, P2=True, P3=True, P4=True), 'гипотеза подтверждена'),
              'null': (dict(P1a=False, P1b=False, P3=False), 'гипотеза опровергнута'),
              'reverse': (dict(P3=False), 'гипотеза опровергнута'),
              'lazymoves': (dict(P1a=False, P2=False), None)}
    bad = []
    for scen, (want, vwant) in expect.items():
        g = np.random.default_rng(len(scen))
        G = [group(b, q, rg, 52, scen, g) for b in range(10) for q in (0.0, 1.0) for rg in ('rich', 'lazy')]
        G += [group(b, 1.0, rg, 0, scen, g) for b in range(10) for rg in ('rich', 'lazy')]
        src, dst = os.path.join(DRY, f'{scen}.json'), os.path.join(DRY, f'{scen}_an.json')
        json.dump(dict(d_nuis=52, groups=G), open(src, 'w'))
        r = subprocess.run([sys.executable, os.path.join(HERE, 'analyze_spectrum01.py'), src, dst], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[-1500:]); bad.append(scen); continue
        a = json.load(open(dst, encoding='utf-8'))
        got = {k: a[k]['ok'] for k in want}
        ok = got == want and (vwant is None and not a['verdict'].startswith('гипотеза подтверждена:') or
                              vwant is not None and a['verdict'].startswith(vwant))
        print(scen, '✓' if ok else '✗', got, '|', a['verdict'][:60])
        if not ok:
            bad.append(scen)
        os.remove(src)
    json.dump({'bad': bad}, open(os.path.join(DRY, 'dry_summary.json'), 'w'))
    print('несовпадений:', bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
