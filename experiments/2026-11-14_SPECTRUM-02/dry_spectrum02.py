#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPECTRUM-02: сухой прогон анализа на заглушках (30 блоков). Ожидания записаны до запуска.
Заглушка группы: средняя CKA — логистическая кривая 0,47 → 0,995 с серединой t(c) = 30·λ_max^(−α)·m(c), шум 0,003 по
6 парам; λ кластеров — как в пилоте (S = O = 1,12 при q = 0, видимое действие поднимает свой кластер до 1,68 линейно по q).
m(c) — множитель кратности: «4 старшие моды» (A0, AB⅓, AB⅔, AB1, а также при q_a < 1 частично) против «2» (A1, B1).
  true      — α = 0,5, m = 0,92 у условий с 4 модами, A⅓ 0,95, A⅔ 0,98, A1 и B1 1,0 →
              P1, P2, P3, P4 «подтверждено», проверки метода пройдены;
  null      — кратность не влияет (m = 1 везде), α = 0,5 → P1 и P4 «подтверждено», P2 и P3 «не решено»;
  reverse   — кратность замедляет (m = 1,08 у условий с 4 модами, A⅓ 1,05, A⅔ 1,02) → P1 «подтверждено»,
              P2 и P3 «опровергнуто», P4 «подтверждено»;
  flatlaw   — α = 0,2, кратность не влияет → P1 «подтверждено», P4 «опровергнуто» (ДИ целиком ≤ 1/3);
  lammis    — у AB1 λ_O = 1,9 (λ_max не равен A1) → проверка метода не пройдена, вердикт «не определено»;
  undef     — в 3 блоках кривая A1 плоская (d_cka < 0,1) → проверка метода не пройдена, вердикт «не определено»."""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DRY = os.path.join(HERE, 'dry')
STEPS = list(range(0, 151)) + list(range(155, 301, 5))
CONDS = {'A0': (0.0, 0.0), 'A13': (1 / 3, 0.0), 'A23': (2 / 3, 0.0), 'A1': (1.0, 0.0),
         'AB13': (1 / 3, 1 / 3), 'AB23': (2 / 3, 2 / 3), 'AB1': (1.0, 1.0), 'B1': (0.0, 1.0)}
MULT = {'true': {'A0': 0.92, 'A13': 0.95, 'A23': 0.98, 'A1': 1.0, 'AB13': 0.92, 'AB23': 0.92, 'AB1': 0.92, 'B1': 1.0},
        'reverse': {'A0': 1.08, 'A13': 1.05, 'A23': 1.02, 'A1': 1.0, 'AB13': 1.08, 'AB23': 1.08, 'AB1': 1.08, 'B1': 1.0}}


def curve(mid, width=2.5):
    s = np.asarray(STEPS, float)
    return 0.47 + (0.995 - 0.47) / (1 + np.exp(-(s - mid) / width))


def lam(qa, qb, scen, cond):
    S, O = 1.12 + 0.56 * qa, 1.12 + 0.56 * qb
    if scen == 'lammis' and cond == 'AB1':
        O = 1.9
    return {'S': S, 'O': O, 'B': 0.64}


def group(b, cond, scen, g):
    qa, qb = CONDS[cond]
    th = lam(qa, qb, scen, cond)
    a = 0.2 if scen == 'flatlaw' else 0.5
    m = MULT.get(scen, {}).get(cond, 1.0)
    mid = 30 * max(th.values()) ** (-a) * m * np.exp(0.01 * g.standard_normal())
    cur = curve(mid)
    if scen == 'undef' and cond == 'A1' and b < 3:
        cur = 0.47 + 0.02 * np.asarray(STEPS) / 300
    jit = lambda: (cur[:, None] + 0.003 * g.standard_normal((len(STEPS), 6))).tolist()   # noqa: E731
    return dict(block=b, cond=cond, qa=qa, qb=qb, q=qa, regime='rich', d_nuis=64 - 10, extra=0, step=STEPS,
                ckaA=jit(), ckaB=jit(), behav=[[0.996] * 6 for _ in STEPS], r2=[[[0.99] * 5 for _ in range(4)] for _ in STEPS],
                ref=[[0.997] * 5] * 4, perm=[[0.01, 0.002, 0.02]] * 6, mknn0=[0.09] * 6, mknnT=[0.86] * 6, theory=[th] * 4)


def main():
    os.makedirs(DRY, exist_ok=True)
    expect = {'true': ({'P1': 'подтверждено', 'P2': 'подтверждено', 'P3': 'подтверждено', 'P4': 'подтверждено'}, True),
              'null': ({'P1': 'подтверждено', 'P2': 'не решено', 'P3': 'не решено', 'P4': 'подтверждено'}, True),
              'reverse': ({'P1': 'подтверждено', 'P2': 'опровергнуто', 'P3': 'опровергнуто', 'P4': 'подтверждено'}, True),
              'flatlaw': ({'P1': 'подтверждено', 'P4': 'опровергнуто'}, True),
              'lammis': ({}, False),
              'undef': ({}, False)}
    bad = []
    for scen, (want, method) in expect.items():
        g = np.random.default_rng(len(scen) * 7)
        src, dst = os.path.join(DRY, f'{scen}.json'), os.path.join(DRY, f'{scen}_an.json')
        json.dump(dict(conds={k: list(v) for k, v in CONDS.items()}, groups=[group(b, c, scen, g) for b in range(30) for c in CONDS]),
                  open(src, 'w'))
        r = subprocess.run([sys.executable, os.path.join(HERE, 'analyze_spectrum02.py'), src, dst], capture_output=True, text=True)
        if r.returncode:
            print(scen, 'ошибка анализа:', r.stderr[-1500:]); bad.append(scen); continue
        a = json.load(open(dst, encoding='utf-8'))
        got = {k: a['verdicts'][k] for k in want}
        is_undef = a['verdict'].startswith('не определено')
        ok = got == want and (is_undef != method)
        print(scen, '✓' if ok else '✗', got, '|', a['verdict'][:90])
        if not ok:
            bad.append(scen)
        os.remove(src)
    json.dump({'bad': bad}, open(os.path.join(DRY, 'dry_summary.json'), 'w'))
    print('несовпадений:', bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
