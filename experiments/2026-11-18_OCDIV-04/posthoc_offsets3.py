#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-04, шаг 3: пост-хок разбор совпадающих смещений на готовых ответах теста OCDIV-03 «тысяч» (совет 71, РАЗБОР-СМЕЩЕНИЙ).
Описательно, вес 0. Мера OCDIV-04 закреплена до этого разбора (HYPOTHESIS.md, 7aed3606); разбор её не выбирает и в мощность не входит.

Толпа среды и задачи — как в анализе OCDIV-03 (`ocdiv3.test`): действующая толпа `effective_crowd`, проверка метода
`ocdiv2.prepare_id` с теми же зёрнами (`ocdiv2.SEED_CV2` + смещение среды) и числом задач ID по строению среды.
По каждой среде и области (вне диапазона, ID):
- F, Δ3c = F − F₀(N3c) со стратами c1 и, описательно, со стратами-клетками «c1 × u»;
- K — совпадение смещения при совместной ошибке пары голов минус то же при N3c;
- Т4 = F − F₀(N0) (связь с OCDIV-03);
- виды неверных смещений у каждой головы, пять самых частых смещений; виды совпавших смещений пар;
- Δ3c и K внутри каждой страты c1 (вне диапазона).
Сводка по средам — среднее и M4 при 0,005 (описательно) и t по средам.
  python3 posthoc_offsets3.py MERGED_TEST2 OUT.json [--boot B] [--workers N]"""
import concurrent.futures as cf
import json
import os
import sys
import time

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, X_DIR)
import ocdiv4 as C  # noqa: E402

W, S, V, O3 = C.W, C.S, C.V, C.O3
B_POST, K_POINT, K_BOOT = 2000, 1000, 10
SEED = 9_410_000            # новые зёрна пост-хока (+ смещение среды и номер потока)
STREAMS = {'d3c_ood': 0, 'd3c_id': 1, 'k_ood': 2, 'k_id': 3, 'd3u_ood': 4, 't4_ood': 5, 'c1_ood': 6}


def seeds(o, name):
    base = SEED + 10_000 * STREAMS[name] + o
    return base, base + 5_000


def env_job(job):
    env, n_id, o, B = job
    st, info = W.prepare_id(env, W.SEED_CV2 + o, n_id)
    keep = info['keep']
    names = [O3.short(info['names'][k]) for k in keep]
    out = dict(crowd=names, valid=bool(info['valid']), n_id=int(info['rid'].sum()), n_ood=int((~info['rid']).sum()))
    if not info['valid']:
        return out
    probs = env['problems']
    sums = [p['sum'] for p in probs]
    ans = [info['ans'][k] for k in keep]
    cols = {'ood': list(info['ood']), 'id': list(info['idi'])}
    D = {r: W.dmat(ans, sums, c) for r, c in cols.items()}
    sc = {r: C.strata_c1(probs, c) for r, c in cols.items()}
    for r in ('ood', 'id'):
        a, b = seeds(o, f'd3c_{r}')
        out[f'd3c_{r}'], bt = C.d3c_stream(D[r], sc[r], a, b, B, K_POINT, K_BOOT)
        out.setdefault('_boot', {})[f'd3c_{r}'] = bt
        a, b = seeds(o, f'k_{r}')
        out[f'k_{r}'], bt = C.k_stream(D[r], sc[r], a, b, B, K_POINT, K_BOOT)
        out['_boot'][f'k_{r}'] = bt
        out[f'kinds_{r}'] = {nm: C.kinds_of_head(D[r][:, k]) for k, nm in enumerate(names)}
        out[f'same_pairs_{r}'] = C.same_pairs_by_kind(D[r])
        out[f'strata_{r}'] = {int(s): int((sc[r] == s).sum()) for s in np.unique(sc[r])}
    a, b = seeds(o, 'd3u_ood')
    out['d3u_ood'], out['_boot']['d3u_ood'] = C.d3c_stream(D['ood'], C.cells_c1u(probs, cols['ood']), a, b, B, K_POINT, K_BOOT)
    a, b = seeds(o, 't4_ood')
    out['t4_ood'], out['_boot']['t4_ood'] = O3.t4_stream(D['ood'], None, a, b, B, K_POINT, K_BOOT)
    a, _ = seeds(o, 'c1_ood')
    g = np.random.default_rng(a)
    out['by_c1_ood'] = {}
    for s in np.unique(sc['ood']):
        m = sc['ood'] == s
        Ds, ss = D['ood'][m], sc['ood'][m]
        out['by_c1_ood'][int(s)] = dict(n=int(m.sum()), d3c=C.d3c_point(Ds, ss, g, K_POINT)[2], k=C.k_point(Ds, ss, g, K_POINT)[2])
    return out


def run(mdir, dst, B=B_POST, workers=1):
    t0 = time.time()
    d, envs = S.load_new(mdir)
    hm = {h['model']: h for h in d['heads']}
    names_c, dropped = V.effective_crowd(hm)
    jobs, order = [], sorted(envs, key=lambda n: int(envs[n]['meta']['X']))
    for n in order:
        env = envs[n]
        assert env['meta']['family'] == 'thousands' and int(env['meta']['p']) == 3, n
        env_c = dict(env, heads=[h for h in env['heads'] if h['model'] in names_c])
        jobs.append((env_c, sum(p['range'] == 'ID' for p in env['problems']), W.off_of(env['meta']), B))
    if workers <= 1:
        outs = [env_job(j) for j in jobs]
    else:
        with cf.ProcessPoolExecutor(workers) as ex:
            outs = list(ex.map(env_job, jobs))
    res = dict(what='OCDIV-04 шаг 3: пост-хок разбор совпадающих смещений на тесте OCDIV-03 (описательно, вес 0)',
               hypothesis_commit='7aed3606', source='gha_out/ocdiv3_test_* (сборка test2, thousands)', B=B, K_point=K_POINT, K_boot=K_BOOT,
               seed=SEED, crowd_effective=names_c, crowd_dropped=dropped, envs={})
    boots = {}
    for n, r in zip(order, outs):
        boots[n] = r.pop('_boot', {})
        res['envs'][n] = r
    valid = [n for n in order if res['envs'][n]['valid']]
    res['summary'] = {}
    for key in ('d3c_ood', 'd3c_id', 'k_ood', 'k_id', 'd3u_ood', 't4_ood'):
        pts = {n: res['envs'][n][key]['point'] for n in valid}
        res['summary'][key] = dict(**C.mean_entry(pts, {n: boots[n][key] for n in valid}, valid, C.DESCR_LEVEL), t_envs=C.t_envs(pts))
    pts = {n: res['envs'][n]['k_ood']['point'] - res['envs'][n]['k_id']['point'] for n in valid}
    res['summary']['k_ood_minus_id'] = dict(**C.mean_entry(pts, {n: boots[n]['k_ood'] - boots[n]['k_id'] for n in valid}, valid, C.DESCR_LEVEL),
                                            t_envs=C.t_envs(pts))
    res['seconds'] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    for key, e in res['summary'].items():
        print(f"{key}: среднее {e['delta']:+.4f} M4(0,005) [{e['ci'][0]:+.4f}; {e['ci'][1]:+.4f}] t {e['t_envs']['t']:.2f}", flush=True)
    print('время', res['seconds'], 'с')
    return res


if __name__ == '__main__':
    a = sys.argv[1:]
    run(a[0], a[1], B=int(a[a.index('--boot') + 1]) if '--boot' in a else B_POST,
        workers=int(a[a.index('--workers') + 1]) if '--workers' in a else 1)
