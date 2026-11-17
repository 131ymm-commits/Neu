#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-02, совет 68, п. 0 — проверка прибора по выводу пилотов (их правда уже разобрана) и, для сравнения, теста OCDIV-01.
Точность не печатается. По каждой паре «среда × голова»:
  (i)   доля числовых ответов с n_tok = max_new (ответ мог оборваться на пределе генерации);
  (ii)  доля числовых ответов с n_tok > (цифр в ответе) + 1 — в число засчитаны токены, которые декодируются в пустую строку
        (служебные: конец последовательности, заполнитель пакета): цикл answer_logp на них не останавливается;
  (iii) доля ответов — собственных префиксов правды (правда, у которой отрезаны последние цифры), и длина ответа против длины правды.
Правда — из ключей задач в самом выводе (a + b).
  python3 trunc_check.py OUT.json GLOB [GLOB ...]"""
import glob
import json
import sys

import numpy as np


def check_file(f):
    h = json.load(open(f, encoding='utf-8'))
    out = []
    if 'cols' not in h:
        return out
    envs = {e['name']: e for e in h.get('envs', [])}
    for name, c in h['cols'].items():
        e = envs.get(name, {})
        max_new = int(e.get('max_new') or 6)
        truth = [a + b for a, b in e.get('keys', [])]
        if len(truth) != len(c['answer']):
            continue
        num = [(x, n, t) for x, n, t in zip(c['answer'], c['n_tok'], truth) if x is not None]
        if not num:
            continue
        dig = lambda v: len(str(abs(int(v))))   # noqa: E731
        at_max = sum(n == max_new for x, n, t in num)
        extra = sum(n > dig(x) + 1 for x, n, t in num)
        prefix = sum(dig(x) < dig(t) and str(t).startswith(str(x)) for x, n, t in num)
        shorter = sum(dig(x) < dig(t) for x, n, t in num)
        longer = sum(dig(x) > dig(t) for x, n, t in num)
        out.append(dict(file=f, model=h.get('model'), env=name, phase=h.get('phase', 'ocdiv01'), max_new=max_new, n_numeric=len(num),
                        n_at_max=at_max, share_at_max=at_max / len(num), n_extra_tokens=extra, share_extra_tokens=extra / len(num),
                        n_prefix_of_truth=prefix, n_shorter=shorter, n_longer=longer,
                        max_digits_answer=max(dig(x) for x, n, t in num), max_digits_truth=max(dig(t) for t in truth),
                        n_tok_hist={int(k): int(v) for k, v in zip(*np.unique([n for x, n, t in num], return_counts=True))}))
    return out


def main(dst, globs):
    rows = [r for g in globs for f in sorted(glob.glob(g)) for r in check_file(f)]
    summ = {}
    for r in rows:
        key = (r['phase'], r['env'][:1] if r['phase'] != 'ocdiv01' else 'X')
        s = summ.setdefault(f'{key[0]} {key[1]}', dict(n_pairs=0, n_numeric=0, n_at_max=0, n_extra_tokens=0, n_prefix_of_truth=0))
        s['n_pairs'] += 1
        for k in ('n_numeric', 'n_at_max', 'n_extra_tokens', 'n_prefix_of_truth'):
            s[k] += r[k]
    json.dump(dict(rows=rows, summary=summ), open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, s in summ.items():
        print(k, s)
    worst = sorted(rows, key=lambda r: -r['share_extra_tokens'])[:8]
    for r in worst:
        print('лишние токены:', r['phase'], r['env'], r['model'], round(r['share_extra_tokens'], 4), '| на пределе', round(r['share_at_max'], 4), '| n_tok', r['n_tok_hist'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
