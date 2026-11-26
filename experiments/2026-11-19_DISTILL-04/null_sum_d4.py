#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: сводка нулевой серии М ≡ Т (совет 78, п. 5; PREREG §10) — только из json заданий gha_out/distill04_null_*/null.json:
число миров, решающих вердиктов («больше», «меньше»), вердиктов «в среднем этих сред …» (только часть А); проверка зёрен (миры без
пересечений и без пропусков, 1000 … 2999) и полноты заданий. Правило СТОП (совет 78): решающих вердиктов не меньше STOP_AT = 17 из
2000 миров — регистрации нет, цепочку разбирать. Хвосты бинома считает scipy: P(≥ 17 | 2000, 0,005) и P(≥ 17 | 2000, 0,01).
  python3 null_sum_d4.py [ВЫХОД.json]"""
import glob
import json
import os
import sys

from scipy.stats import binom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
N_WORLDS, STOP_AT, SEEDS = 2000, 17, (1000, 2999)


def main(a):
    files = sorted(glob.glob(os.path.join(ROOT, 'gha_out', 'distill04_null_*', 'null.json')))
    runs, parts = [], []
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        parts.append(dict(file=os.path.relpath(f, ROOT), worlds=d['worlds'], done=len(d['runs']), seeds=d['seeds'], versions=d['versions'],
                          seconds=d.get('seconds'), seconds_per_world_wall=d.get('seconds_per_world_wall'), workers=d.get('workers')))
        runs += d['runs']
    seeds = sorted(r['seed'] for r in runs)
    complete = all(p['done'] == p['worlds'] for p in parts)
    seeds_ok = seeds == list(range(SEEDS[0], SEEDS[1] + 1))
    dec = sum(r['verdict'] in ('больше', 'меньше') for r in runs)
    by = {}
    for r in runs:
        by[r['verdict']] = by.get(r['verdict'], 0) + 1
    out = dict(files=parts, worlds=len(runs), complete=complete, seeds_ok=seeds_ok, decisive=dec, verdicts=by, stop_at=STOP_AT,
               stop=bool(dec >= STOP_AT), p_false_stop_at_0005=float(binom.sf(STOP_AT - 1, N_WORLDS, 0.005)),
               p_stop_at_001=float(binom.sf(STOP_AT - 1, N_WORLDS, 0.01)), share_decisive=dec / len(runs) if runs else None)
    print(f"миров {len(runs)} (заданий {len(parts)}, все полные — {complete}; зёрна 1000…2999 без пропусков и повторов — {seeds_ok})")
    print('вердикты:', by)
    print(f"решающих («больше» или «меньше»): {dec} из {len(runs)}; СТОП при ≥ {STOP_AT} — {'СТОП' if out['stop'] else 'нет'}")
    print(f"хвосты бинома (scipy): P(≥ {STOP_AT} | {N_WORLDS}, 0,005) = {out['p_false_stop_at_0005']:.4f}; P(≥ {STOP_AT} | {N_WORLDS}, 0,01) = {out['p_stop_at_001']:.4f}")
    if a:
        json.dump(out, open(a[0], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0 if (complete and seeds_ok and not out['stop'] and len(runs) == N_WORLDS) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
