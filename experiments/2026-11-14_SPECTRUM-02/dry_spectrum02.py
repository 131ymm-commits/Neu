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
  undef     — в 3 блоках кривая A1 плоская (d_cka < 0,1) → проверка метода не пройдена, вердикт «не определено».
Добавлено после совета 50 (условия A1B13, A1B23; правило формы; общий порог; перезапись вердиктов):
  true    — A1B13 0,99, A1B23 0,97 → правило формы «за кратность»;
  null    — правило формы «не решено»;  reverse — A1B13 1,01, A1B23 1,03 → «за добавочный сигнал» (Δ_low ≥ Δ_high);
  signal  — как true, но A1B13 0,95, A1B23 0,93 (убывающая отдача) → P2 «подтверждено», правило формы «за добавочный сигнал»;
  symfail — у B1 множитель 1,10 → симметрия не пройдена → каждый из P1…P4 и правило формы «не определено (проверка метода)»;
  thrdep  — как true, но у AB1 потолок CKA 0,80 и середина ×0,97 → по своему порогу AB1 раньше A1, по общему порогу A1 —
            позже → P2 «не определено (зависит от порога)»."""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DRY = os.path.join(HERE, 'dry')
STEPS = list(range(0, 151)) + list(range(155, 301, 5))
CONDS = {'A0': (0.0, 0.0), 'A13': (1 / 3, 0.0), 'A23': (2 / 3, 0.0), 'A1': (1.0, 0.0),
         'AB13': (1 / 3, 1 / 3), 'AB23': (2 / 3, 2 / 3), 'AB1': (1.0, 1.0), 'B1': (0.0, 1.0),
         'A1B13': (1.0, 1 / 3), 'A1B23': (1.0, 2 / 3)}
TRUE = {'A0': 0.92, 'A13': 0.95, 'A23': 0.98, 'A1': 1.0, 'AB13': 0.92, 'AB23': 0.92, 'AB1': 0.92, 'B1': 1.0, 'A1B13': 0.99, 'A1B23': 0.97}
MULT = {'true': TRUE, 'thrdep': TRUE,
        'reverse': {'A0': 1.08, 'A13': 1.05, 'A23': 1.02, 'A1': 1.0, 'AB13': 1.08, 'AB23': 1.08, 'AB1': 1.08, 'B1': 1.0,
                    'A1B13': 1.01, 'A1B23': 1.03},
        'signal': {**TRUE, 'A1B13': 0.95, 'A1B23': 0.93},
        'symfail': {**TRUE, 'B1': 1.10}}


def curve(mid, width=2.5, top=0.995):
    s = np.asarray(STEPS, float)
    return 0.47 + (top - 0.47) / (1 + np.exp(-(s - mid) / width))


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
    top = 0.995
    if scen == 'thrdep' and cond == 'AB1':
        mid, top = mid * 0.97 / 0.92, 0.80             # середина чуть раньше A1, потолок ниже
    cur = curve(mid, top=top)
    if scen == 'undef' and cond == 'A1' and b < 3:
        cur = 0.47 + 0.02 * np.asarray(STEPS) / 300
    jit = lambda: (cur[:, None] + 0.003 * g.standard_normal((len(STEPS), 6))).tolist()   # noqa: E731
    return dict(block=b, cond=cond, qa=qa, qb=qb, q=qa, regime='rich', d_nuis=64 - 10, extra=0, step=STEPS,
                ckaA=jit(), ckaB=jit(), behav=[[0.996] * 6 for _ in STEPS], r2=[[[0.99] * 5 for _ in range(4)] for _ in STEPS],
                ref=[[0.997] * 5] * 4, perm=[[0.01, 0.002, 0.02]] * 6, mknn0=[0.09] * 6, mknnT=[0.86] * 6, theory=[th] * 4,
                loss_frac=[[float(x)] * 4 for x in 1 / (1 + np.exp(-(np.asarray(STEPS) - 2.5 * mid) / 6))],
                norm_S=[[float(x)] * 4 for x in 1 / (1 + np.exp(-(np.asarray(STEPS) - 2.5 * mid) / 6))],
                norm_O=[[float(x)] * 4 for x in 1 / (1 + np.exp(-(np.asarray(STEPS) - 3 * mid) / 6))])


def main():
    os.makedirs(DRY, exist_ok=True)
    U = 'не определено (проверка метода)'
    expect = {'true': ({'P1': 'подтверждено', 'P2': 'подтверждено', 'P3': 'подтверждено', 'P4': 'подтверждено', 'shape': 'за кратность'}, True),
              'null': ({'P1': 'подтверждено', 'P2': 'не решено', 'P3': 'не решено', 'P4': 'подтверждено', 'shape': 'не решено'}, True),
              'reverse': ({'P1': 'подтверждено', 'P2': 'опровергнуто', 'P3': 'опровергнуто', 'P4': 'подтверждено',
                           'shape': 'за добавочный сигнал'}, True),
              'signal': ({'P2': 'подтверждено', 'shape': 'за добавочный сигнал'}, True),
              'symfail': ({'P1': U, 'P2': U, 'P3': U, 'P4': U, 'shape': U}, False),
              'thrdep': ({'P1': 'подтверждено', 'P2': 'не определено (зависит от порога)'}, True),
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


def emit(scen, out):
    """Заглушка результатов с зёрнами теста (база 151000) — для сухого прогона сценария gha_spectrum02.sh (совет 50, п. 6)."""
    g = np.random.default_rng(len(scen) * 7)
    G = [dict(group(b, c, scen, g), base=151000) for b in range(30) for c in CONDS]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(dict(conds={k: list(v) for k, v in CONDS.items()}, groups=G), open(out, 'w'))
    print('заглушка', scen, '→', out, '| групп', len(G))


if __name__ == '__main__':
    if '--emit' in sys.argv:
        i = sys.argv.index('--emit')
        emit(sys.argv[i + 1], sys.argv[i + 2])
    else:
        main()
