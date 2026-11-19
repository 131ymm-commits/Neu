#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04: пилот (описательно, до PREREG) — программы по построению DISTILL-02 (OCDIV-03/04), каталог операторов по правилу
CATALOG_MIN на построении, меры на уже виденных test5 (и new5) DISTILL-02 с бутстрепом по задачам; мощность П1 и П2 для теста на
новых средах (модель «новая среда» DISTILL-02 / OCDIV-04). Тест DISTILL-04 — на новых ответах, этих данных он не касается.
  python3 pilot_d4.py ВЫХОД.json SPEC.json
SPEC: {"construction": {семейство: [папки]}, "eval": {имя: {"family": семейство, "dirs": [папки]}}, "B": 200, "seed": 9940000,
       "m_test": {семейство: число сред теста}}"""
import json
import os
import sys
import time

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, X_DIR)
import prog_m as PM  # noqa: E402

D2 = PM.D2


def load_list(dirs, fam):
    out = []
    for d in dirs:
        out += [(n, e) for n, e in D2.load_merged(d).items() if D2.family_of(n) == fam]
    return out


def main(a):
    t0 = time.time()
    dst, spec = a[0], json.load(open(a[1], encoding='utf-8'))
    B, seed = int(spec.get('B', 200)), int(spec.get('seed', 9_940_000))
    data, cov = {}, {}
    for fam, dirs in spec['construction'].items():
        items, offs = D2.family_data([e for _, e in load_list(dirs, fam)])
        data[fam] = (items, offs)
        cov[fam] = PM.coverage_family(items, offs)
    catalog = PM.select_catalog(cov)
    print('каталог (правило CATALOG_MIN на построении):', catalog, flush=True)
    fits = {fam: PM.fit_family(items, offs, catalog) for fam, (items, offs) in data.items()}
    out = dict(B=B, seed=seed, catalog=catalog, catalog_min=PM.CATALOG_MIN, coverage=cov,
               weights={fam: {h: dict(pi=[float(x) for x in f['pi']], pi_mt=[float(x) for x in f['pi_mt']], n_other=f['n_other'],
                                      eps=float(f['prog']['eps']), T_offsets=list(f['prog_T']['q'])) for h, f in fs.items()} for fam, fs in fits.items()},
               sets={}, power={})
    for name, s in spec['eval'].items():
        fam = s['family']
        res = {}
        for en, env in sorted(load_list(s['dirs'], fam)):
            items_e, offs_e = D2.env_table(env)
            heads = [h for h in sorted(fits[fam]) if h in offs_e and int((offs_e[h] < PM.NC).sum()) >= D2.MIN_NUMERIC]
            er = PM.env_rows(fits[fam], items_e, offs_e, heads)
            rng = np.random.default_rng([seed, int.from_bytes(en.encode(), 'little') % (2 ** 32)])
            pt, sd, _ = PM.env_measures(er, B, rng)
            res[en] = dict(point=pt, sd=sd, heads=heads, n=er['n'])
            print(name, en, '| m_M', round(pt['m_M'], 4), '| по «прочим»', round(pt['m_Mo'], 4), '| top3', round(pt['top3'], 4),
                  '| М − таблица 30', round(pt['m_T30'], 4), '| М+Т − таблица 30', round(pt['m_MT'], 4), flush=True)
        out['sets'][name] = dict(family=fam, envs=res)
        m = int(spec.get('m_test', {}).get(fam, len(res)))
        names = sorted(res)
        pw = {}
        for meas in ('m_M', 'top3', 'm_MT'):            # m_MT — после первого пилота (bc50da0f): М+Т против таблицы 30, то же число параметров
            e = D2.power_rule([res[n]['point'][meas] for n in names], [res[n]['sd'][meas] for n in names], 1.0, m, m >= 4)
            pw[meas] = e
            if e is not None:
                print('   мощность', meas, '| сред теста', m, '|', {k: round(v, 4) for k, v in e['power'].items()}, flush=True)
        out['power'][name] = dict(m_test=m, **pw)
    out['seconds'] = round(time.time() - t0, 1)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
