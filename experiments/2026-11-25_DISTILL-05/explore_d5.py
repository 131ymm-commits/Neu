#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-05 «ТОКЕН-ОПЕРАТОРЫ»: разведка (описательно, до PREREG; HYPOTHESIS.md) — масштаб «прочих» смещений голов по длине суммы.
Данные — только уже виденные ответы: построение (тест OCDIV-03, пилот и тест OCDIV-04), test5/new5 DISTILL-02, test6/test6L DISTILL-04.
По каждой голове и длине суммы n (цифр): число «прочих» ответов, доли масштабов (масштаб смещения d — наибольшая степень 10, делящая |d|)
и самые частые смещения. Предсказание гипотезы для OLMo (куски по три цифры слева направо): n = 4 → масштабы 10 и 1; n = 5 → 100 и 1;
n = 6 → 1000 и 1; n = 7 → 10^4, 10 и 1. У голов с цифрами по одной особого сдвига нет.
  python3 explore_d5.py ВЫХОД.json SPEC.json      SPEC: {"sets": {имя: [папки сборок]}}"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'experiments', '2026-11-19_DISTILL-04'))
import explore_d4 as XE  # noqa: E402

D2 = XE.D2
TOP = 15


def scale(d):
    """Наибольшая степень 10, делящая |d| (d ≠ 0)."""
    d, p = abs(int(d)), 0
    while d and d % 10 == 0:
        d //= 10
        p += 1
    return p


def chunk_places(n, size=3):
    """Разряды последних цифр кусков при нарезке слева направо по size цифр числа из n цифр (младший разряд — 0)."""
    out, start = [], 0
    while start < n:
        end = min(start + size, n)
        out.append(n - end)
        start = end
    return out


def tally(items, offs, acc, src):
    for it, d in zip(items, offs):
        c = XE.classify(it, d)
        if c is None:
            continue
        n = str(len(str(it['sum'])))
        rec = acc.setdefault(n, dict(n_numeric=0, n_other=0, scales={}, offsets={}, sources={}))
        rec['n_numeric'] += 1
        if c != 'other':
            continue
        rec['n_other'] += 1
        sc = str(scale(d))
        rec['scales'][sc] = rec['scales'].get(sc, 0) + 1
        rec['offsets'][str(int(d))] = rec['offsets'].get(str(int(d)), 0) + 1
        rec['sources'][src] = rec['sources'].get(src, 0) + 1


def main(a):
    dst, spec = a[0], json.load(open(a[1], encoding='utf-8'))
    heads = {}
    for name, dirs in spec['sets'].items():
        for dd in dirs:
            for en, env in D2.load_merged(dd).items():
                items, offs = D2.env_table(env)
                for h, o in offs.items():
                    tally(items, o, heads.setdefault(h, {}), f'{name}:{en}')
    out = {}
    for h, by_n in heads.items():
        out[h] = {}
        for n, rec in sorted(by_n.items()):
            tot = max(rec['n_other'], 1)
            top = sorted(rec['offsets'].items(), key=lambda kv: -kv[1])[:TOP]
            out[h][n] = dict(n_numeric=rec['n_numeric'], n_other=rec['n_other'], share_other=rec['n_other'] / max(rec['n_numeric'], 1),
                             scales={k: v / tot for k, v in sorted(rec['scales'].items(), key=lambda kv: int(kv[0]))},
                             top_offsets=[[int(k), v] for k, v in top], sources=rec['sources'], chunk_places_3=chunk_places(int(n)))
            print(h, 'n =', n, '| «прочих»', rec['n_other'], '| масштабы', {k: round(v, 3) for k, v in out[h][n]['scales'].items()},
                  '| верх', out[h][n]['top_offsets'][:6], flush=True)
    json.dump(dict(heads=out, top=TOP), open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
