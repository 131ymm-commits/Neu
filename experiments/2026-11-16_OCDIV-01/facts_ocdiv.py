#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-01: производные числа отчёта, которых нет в json анализа (чтобы ledger.py audit их находил). Сборка чисел; вердиктов не меняет.
  python3 facts_ocdiv.py ANALYSIS.json MERGED_DIR EXPECT.json OUT.json
- Незнание и самообман оценщиков разнородной толпы вне диапазона (CLAUDE.md: «отчёт даёт незнание и самообман отдельно»). Анализ теста
  хранит по средам только точки правил, поэтому части считаются заново, только точки: зарегистрированная функция ocdiv.crowd_point
  (S.prepare + stats_div) на той же толпе (crowd_effective из analysis.json), с FIXED-нов и зерном частей 7 620 000 + 10·X + p, как в анализе.
  Сверка: wc CONF, wc POST, wc FIXED и C − T FIXED каждой годной среды должны совпасть с точками D2, D4, N и D3 в analysis.json — иначе СТОП.
- Те же части у девяти Pythia и у смешанной толпы — из analysis.json (descr_py, descr_mix); среднее по годным средам.
- Вес опоры — PREREG §10: все веса — верхняя оценка, не для реестра. D1, D2, D4, N, D5 — 0 бит. D3 «опровергнуто» — log₂(мощность
  «опровергнуто» при τ = s / 0,0025), мощность — expect_ocdiv.json. D3 «подтверждено» — по формуле не определён (мощность ≈ 0). Иначе 0.
Написан после того, как пришёл сырой вывод теста, и до вывода анализа (DEVIATIONS, п. 2)."""
import json
import os
import sys
from math import log2

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocdiv as V  # noqa: E402

LEVEL = 0.0025
PARTS = ('T', 'C', 'ign', 'dec', 'ioi', 'brier')
EST = ('CONF', 'POST-CV', 'ONE-BEST', 'FIXED', 'SHIFT', 'AGREE')
CHECK = {'D2': ('wc CONF', None), 'D4': ('wc POST', None), 'N': ('wc FIXED', None), 'D3': ('C FIXED', 'T FIXED')}
TOL = 1e-12


def fin(x):
    return x is not None and np.isfinite(x)


def mean_parts(stats):
    """Среднее частей ИОИ по средам (точки); у каждого оценщика — число сред, где он определён."""
    out = {}
    for e in EST:
        row = {}
        for q in PARTS:
            v = [s[f'{q} {e}'] for s in stats if fin(s.get(f'{q} {e}'))]
            row[q] = float(np.mean(v)) if v else None
        row['n_envs'] = int(sum(bool(fin(s.get(f'T {e}'))) for s in stats))
        out[e] = row
    return out


def weights(an, ex):
    v = an['verdicts']
    w = {k: dict(bits=0.0, verdict=v[k]) for k in ('D1', 'D2', 'D4', 'D5', 'N')}
    w['D1']['note'] = 'повтор пилота, знак известен (совет 66, п. 2); в реестр о D1 ничего не идёт'
    w['D2']['note'] = w['D4']['note'] = 'ожидаемо по построению (совет 66, п. 3); в реестр — как перенос, без прибавки веса'
    w['N']['note'] = 'служебное условие для D4'
    w['D5']['note'] = 'описательно'
    p3 = ex['rules']['D3']
    if v['D3'] == 'опровергнуто':
        w['D3'] = dict(bits=log2(p3['power_refute_tau_s'] / LEVEL), verdict=v['D3'], power=p3['power_refute_tau_s'],
                       note='log₂(мощность «опровергнуто» при τ = s / 0,0025); верхняя оценка, не для реестра')
    elif v['D3'] == 'подтверждено':
        w['D3'] = dict(bits=None, verdict=v['D3'], power=p3['power_confirm_tau_s'], note='мощность «подтверждено» ≈ 0: вес по формуле не определён')
    else:
        w['D3'] = dict(bits=0.0, verdict=v['D3'])
    return w


def main(an_path, merged_dir, ex_path, dst):
    an = json.load(open(an_path, encoding='utf-8'))
    ex = json.load(open(ex_path, encoding='utf-8'))
    valid = an['method']['valid']
    _, envs_new = V.S.load_new(merged_dir)
    crowd = an['crowd_effective']
    out = dict(source='PREREG-OCDIV-01 §5, §10 (регистрация c626aa32)', valid=valid, crowd=crowd, check={}, new={}, weights=weights(an, ex))
    stats_new = []
    for name in valid:
        env = envs_new[name]
        off = 10 * env['meta']['X'] + env['meta']['p']
        env_c = dict(env, heads=[h for h in env['heads'] if h['model'] in crowd])
        cp = V.crowd_point(env_c, V.FIXED_NEW, V.SEED_CV_P + off)
        if not cp['valid']:
            raise SystemExit(f'СТОП: среда {name} годна в анализе, но не при пересчёте')
        diff = {k: abs(V.P.val(cp['stats'], pr) - an['envs'][name]['rules_env'][k]['point']) for k, pr in CHECK.items()}
        out['check'][name] = diff
        if not all(d <= TOL for d in diff.values()):
            raise SystemExit(f'СТОП: пересчёт точек {name} не совпал с анализом: {diff}')
        out['new'][name] = dict(stats={k: cp['stats'][k] for k in cp['stats']}, oracle_ood=cp['oracle_ood'], crowd=cp['crowd'])
        stats_new.append(cp['stats'])
    out['check_ok'] = True
    out['parts_mean'] = dict(new=mean_parts(stats_new),
                             py=mean_parts([an['envs'][n]['descr_py']['stats'] for n in valid if an['envs'][n]['descr_py'].get('valid')]),
                             mix=mean_parts([an['envs'][n]['descr_mix']['stats'] for n in valid if an['envs'][n]['descr_mix'].get('valid')]))
    out['n_envs_descr'] = dict(py=sum(bool(an['envs'][n]['descr_py'].get('valid')) for n in valid),
                               mix=sum(bool(an['envs'][n]['descr_mix'].get('valid')) for n in valid))
    out['oracle_ood_mean'] = dict(new=float(np.mean([an['envs'][n]['oracle_ood'] for n in valid])),
                                  py=float(np.mean([an['envs'][n]['descr_py']['oracle_ood'] for n in valid if an['envs'][n]['descr_py'].get('valid')])),
                                  mix=float(np.mean([an['envs'][n]['descr_mix']['oracle_ood'] for n in valid if an['envs'][n]['descr_mix'].get('valid')])))
    # совпадение ошибок: средние по годным средам
    q = {k: float(np.mean([an['envs'][n]['q'][k] for n in valid])) for k in ('q_new', 'q_py', 'q_literal', 'q_cross_descr', 'adj_beta')}
    q['n_joint_new_sum'] = int(sum(an['envs'][n]['q']['n_joint_new'] for n in valid))
    q['n_joint_py_sum'] = int(sum(an['envs'][n]['q']['n_joint_py'] for n in valid))
    out['q_mean'] = q
    et = {}
    for side in ('нов', 'py'):                                   # типы ошибок (числовые ответы): сумма по годным средам и доли
        cnt = {}
        for n in valid:
            for t, c in an['envs'][n]['q']['err_types'][side].items():
                cnt[t] = cnt.get(t, 0) + int(c)
        tot = sum(cnt.values())
        et[side] = dict(counts=cnt, total=tot, share={t: (c / tot if tot else None) for t, c in cnt.items()})
    out['err_types_sum'] = et
    # головы: точность ID и OOD, C − T вне диапазона (среднее по годным средам); ONE-BEST по средам (наибольшая точность на ID, первая при равенстве)
    heads = {}
    for nm in crowd:
        rows = [an['envs'][n]['acc_id_ood_by_head'][nm] for n in valid if nm in an['envs'][n]['acc_id_ood_by_head']]
        heads[nm] = dict(vendor=V.vendor(V.CROWD[nm].split('@')[0]), id=float(np.mean([r['id'] for r in rows])) if rows else None,
                         ood=float(np.mean([r['ood'] for r in rows])) if rows else None, n_envs=len(rows),
                         ct_ood=an.get('ct_ood_by_head_descr', {}).get(nm))
    out['heads'] = heads
    out['one_best'] = {n: max(an['envs'][n]['acc_id_ood_by_head'].items(), key=lambda kv: kv[1]['id'])[0] for n in valid}
    # знаки и полосы по средам (описательно)
    by = {n: {k: an['envs'][n]['rules_env'][k]['point'] for k in ('D1', 'D2', 'D3', 'D4', 'D5', 'N')} for n in valid}
    out['sign_count'] = {k: dict(neg=int(sum(by[n][k] < 0 for n in valid)), pos=int(sum(by[n][k] > 0 for n in valid)), n=len(valid))
                         for k in ('D1', 'D2', 'D5')}
    out['in_band_count'] = {k: int(sum(abs(by[n][k]) <= V.P.BAND for n in valid)) for k in ('D3', 'D4', 'N')}
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(dict(check_ok=out['check_ok'], weights={k: v['bits'] for k, v in out['weights'].items()},
                          max_diff=max(max(d.values()) for d in out['check'].values()) if out['check'] else None), ensure_ascii=False))


if __name__ == '__main__':
    main(*sys.argv[1:5])
