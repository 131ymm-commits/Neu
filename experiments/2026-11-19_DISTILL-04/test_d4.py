#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-04 «ПРОЧИЕ»: анализ теста на свежих ответах (PREREG-DISTILL-04.md). Константы правил — RULES, RULES_ACTIVE, B_TEST, SEED_TEST —
записываются до регистрации; без регистрации анализ не идёт (test_lock).
  Программы — по построению DISTILL-02 (OCDIV-03/04); каталог операторов — правило CATALOG_MIN на построении (prog_m.select_catalog).
  Меры по средам test6 («тысячи», 8 новых сред) — prog_m.env_measures с бутстрепом по задачам (B_TEST повторов, зерно — имя среды);
  правила — distill02.family_rule (часть А — M4 среднего сред при 0,0025, часть Б — t по средам); L_X9999 (test6L) — описательно.
  Повтор контроля A-на-B (DISTILL-03, ab.py без изменений) — на тех же 8 новых средах: виды «программа» и «форма», D > 0 и точное
  p ≤ 0,0025 при k голов (k! перестановок).
  python3 test_d4.py ВЫХОД.json SPEC.json
SPEC: {"construction": {семейство: [папки]}, "test": {"thousands": [папки test6]}, "descriptive": {"length": [папки test6L]}}"""
import hashlib
import json
import os
import sys
import time

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, X_DIR)
sys.path.insert(0, os.path.join(ROOT, 'experiments', '2026-11-19_DISTILL-03'))
import prog_m as PM  # noqa: E402
import ab as AB  # noqa: E402   DISTILL-03 без изменений (хеш — в регистрации)

D2 = PM.D2
TEST_ENVS = ('T_X14_p3', 'T_X24_p3', 'T_X34_p3', 'T_X44_p3', 'T_X54_p3', 'T_X64_p3', 'T_X74_p3', 'T_X84_p3')
# PREREG: правило → (мера, вид, часть Б). Вид 'two' — двусторонний («больше» / «меньше»), 'pos' — односторонний.
RULES = {'П1-Т': ('m_M', 'two', True), 'П1МТ-Т': ('m_MT', 'pos', True), 'П2-Т': ('top3', 'pos', True)}
# PREREG §5: правило активности по пилоту 2 (gha_out/distill04_pilot2/pilot.json; prereg_numbers_d4.py сверяет): True — решающее
RULES_ACTIVE = {'П1-Т': True, 'П1МТ-Т': False, 'П2-Т': False}
AB_RULES = {'АБ-П-Т6': 'prog', 'АБ-Ф-Т6': 'shape'}
B_TEST = 4000
SEED_TEST = 9_940_400


def test_lock():
    assert RULES_ACTIVE is not None and set(RULES_ACTIVE) == set(RULES), 'константы PREREG не записаны: анализ теста не идёт'


def load_list(dirs, fam):
    out = []
    for d in dirs:
        out += [(n, e) for n, e in D2.load_merged(d).items() if D2.family_of(n) == fam]
    return out


def code_hashes():
    h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()   # noqa: E731
    return {os.path.basename(p): h(p) for p in (os.path.abspath(__file__), PM.__file__, AB.__file__, D2.__file__, PM.XE.__file__)}


def env_seed(name):
    return np.random.default_rng([SEED_TEST, int.from_bytes(name.encode(), 'little') % (2 ** 32)])


def head_points(er):
    """Описательно (PREREG §4; токенизатор как ковариата, совет 77): меры по головам в точке — те же разности, что prog_m.measures_w
    до среднего по головам (среднее по головам этих чисел = точка среды; проверка — test_analysis_d4.py)."""
    L, out = er['L'], {}
    for j, h in enumerate(er['heads']):
        num = np.isfinite(L['M'][:, j])
        oth, wr = er['other'][:, j], er['wrong'][:, j]

        def d(x, y, m):
            return float(np.mean(L[x][m, j] - L[y][m, j])) if m.any() else float('nan')
        top = float(((er['hitM'][:, j] & wr).sum() - (er['hitT'][:, j] & wr).sum()) / wr.sum()) if wr.any() else float('nan')
        out[h] = dict(m_M=d('M', 'T', num), m_Mo=d('M', 'T', oth), top3=top, m_T30=d('M', 'T30', num), m_MT=d('MT', 'T30', num),
                      m_M_sym=d('M_sym', 'T_sym', num), n_num=int(num.sum()), n_wrong=int(wr.sum()), n_other=int(oth.sum()))
    return out


def measure_envs(fits, envs):
    out, boots = {}, {}
    for en, env in sorted(envs.items()):
        items_e, offs_e = D2.env_table(env)
        heads = [h for h in sorted(fits) if h in offs_e and int((offs_e[h] < PM.NC).sum()) >= D2.MIN_NUMERIC]
        er = PM.env_rows(fits, items_e, offs_e, heads)
        pt, sd, reps = PM.env_measures(er, B_TEST, env_seed(en))
        out[en] = dict(point=pt, sd=sd, heads=heads, n=er['n'], per_head=head_points(er))
        boots[en] = reps
    return out, boots


KIN = (('Qwen2.5-0.5B-Instruct', 'Qwen2.5-1.5B-Instruct'), ('SmolLM2-360M-Instruct', 'SmolLM2-1.7B-Instruct'))


def op_kinship(weights):
    """Описательно (HYPOTHESIS: родство весов операторов): расстояние полной вариации ½·Σ|π_A − π_B| между весами операторов и остатка
    (построение); у каждой головы пары — до родича и среднее до пяти чужих (не родич и не она сама)."""
    heads = sorted(weights)
    pi = {h: np.array(weights[h]['pi'], float) for h in heads}
    tv = {(a, b): float(0.5 * np.abs(pi[a] - pi[b]).sum()) for a in heads for b in heads}
    out = []
    for x, y in KIN:
        for h, kin in ((x, y), (y, x)):
            if h in pi and kin in pi:
                others = [tv[(h, o)] for o in heads if o not in (h, kin)]
                out.append(dict(head=h, kin=kin, tv_kin=tv[(h, kin)], tv_others=float(np.mean(others)), kin_closer=bool(tv[(h, kin)] < np.mean(others))))
    return dict(pairs=out, n_kin_closer=int(sum(p['kin_closer'] for p in out)), n=len(out))


def ab_replication(construction_envs, test_envs):
    """Повтор DISTILL-03 на новых ответах: программы и формы по построению (ab.family_programs), матрицы и перебор (ab.family_result)."""
    P = AB.family_programs([e for _, e in construction_envs])
    heads_order = sorted(P['prog'])
    res = AB.family_result(P, test_envs, sorted(test_envs), heads_order)
    v = {}
    for rule, kind in AB_RULES.items():
        r = res.get(kind)
        if r is None:
            v[rule] = dict(kind=kind, verdict='непроверяемо', k=res.get('k', 0))
            continue
        min_p = 1 / r['n_perm']
        verdict = 'непроверяемо' if min_p > AB.LEVEL else ('да' if (r['D'] > 0 and r['p'] <= AB.LEVEL + 1e-15) else 'нет')
        v[rule] = dict(kind=kind, D=r['D'], p=r['p'], rank=r['rank'], n_perm=r['n_perm'], k=r['k'], min_p=min_p, n_distinct=r['n_distinct'],
                       verdict=verdict)
    return res, v


def ab_slices(ab_res):
    """Совет 77 (опись DISTILL-04): срезы D формы и программы — своя минус среднее чужих (как D), минус медиана чужих, минус среднее
    чужих без худшей чужой; по средам и головам, описательно. Матрицы — из ab.family_result (строки — чья программа, столбцы — чьи ответы)."""
    out = {}
    for kind in ('prog', 'shape'):
        hk = ab_res.get('heads_kept') or ab_res['heads']
        heads = ab_res['heads']
        jj = [heads.index(h) for h in hk]
        per = {h: dict(mean=[], median=[], drop_worst=[]) for h in hk}
        for en in ab_res.get('envs_kept', []):
            M = np.array(ab_res['envs'][en][kind], dtype=float)[np.ix_(jj, jj)]
            for b, h in enumerate(hk):
                o = np.delete(M[:, b], b)
                per[h]['mean'].append(M[b, b] - o.mean())
                per[h]['median'].append(M[b, b] - np.median(o))
                per[h]['drop_worst'].append(M[b, b] - np.delete(o, np.argmin(o)).mean())
        ph = {h: {k: float(np.mean(v)) for k, v in d.items()} for h, d in per.items()}
        out[kind] = dict(per_head=ph, mean={k: float(np.mean([ph[h][k] for h in hk])) for k in ('mean', 'median', 'drop_worst')},
                         n_pos={k: int(sum(ph[h][k] > 0 for h in hk)) for k in ('mean', 'median', 'drop_worst')})
    return out


def main(a):
    t0 = time.time()
    test_lock()
    dst, spec = a[0], json.load(open(a[1], encoding='utf-8'))
    out = dict(code=code_hashes(), B=B_TEST, seed=SEED_TEST, rules={}, descriptive={})
    cons = {fam: load_list(dirs, fam) for fam, dirs in spec['construction'].items()}
    data = {fam: D2.family_data([e for _, e in lst]) for fam, lst in cons.items()}
    cov = {fam: PM.coverage_family(*data[fam]) for fam in data}
    catalog = PM.select_catalog(cov)
    out.update(catalog=catalog, coverage=cov)
    fits = {fam: PM.fit_family(*data[fam], catalog) for fam in data}
    out['weights'] = {fam: {h: dict(pi=[float(x) for x in f['pi']], pi_mt=[float(x) for x in f['pi_mt']], pi_sym=[float(x) for x in f['pi_sym']],
                                    n_other=f['n_other'])
                            for h, f in fs.items()} for fam, fs in fits.items()}
    out['op_kinship'] = {fam: op_kinship(w) for fam, w in out['weights'].items()}
    lst = load_list(spec['test']['thousands'], 'thousands')
    tenv = dict(lst)
    assert len(tenv) == len(lst), 'одна среда теста дважды'
    miss = [n for n in TEST_ENVS if n not in tenv]
    assert not miss, f'в тесте нет сред: {miss}'
    tenv = {n: tenv[n] for n in TEST_ENVS}
    res, boots = measure_envs(fits['thousands'], tenv)
    out['envs'] = res
    names = list(TEST_ENVS)
    for rule, (meas, kind, part_b) in RULES.items():
        e = D2.family_rule({n: res[n]['point'][meas] for n in names}, {n: boots[n][meas] for n in names},
                           {n: res[n]['sd'][meas] for n in names}, names, kind, part_b)
        e.update(measure=meas, kind=kind, active=bool(RULES_ACTIVE[rule]))
        e['verdict_final'] = e['verdict_rule'] if RULES_ACTIVE[rule] else f"описательно ({e['verdict_rule']})"
        out['rules'][rule] = {k: (v if not isinstance(v, np.ndarray) else v.tolist()) for k, v in e.items()}
        print(rule, '|', meas, '| среднее сред', round(float(np.mean([res[n]['point'][meas] for n in names])), 4), '|', out['rules'][rule]['verdict_final'], flush=True)
    # совет 78, п. 6: симметричная версия нормировки — описательно (ветвь «мала», PREREG §4); то же правило, вердикт в реестр не идёт
    e = D2.family_rule({n: res[n]['point']['m_M_sym'] for n in names}, {n: boots[n]['m_M_sym'] for n in names},
                       {n: res[n]['sd']['m_M_sym'] for n in names}, names, 'two', True)
    out['descriptive']['m_M_sym'] = {k: (v if not isinstance(v, np.ndarray) else v.tolist()) for k, v in e.items()}
    ab_res, ab_v = ab_replication(cons['thousands'], tenv)
    out['ab'] = dict(result=ab_res, verdicts=ab_v, slices=ab_slices(ab_res))
    for rule, v in ab_v.items():
        print(rule, '|', v['verdict'], '| D', None if v.get('D') is None else round(v['D'], 4), '| p', v.get('p'), '| k', v.get('k'), flush=True)
    if spec.get('descriptive', {}).get('length'):
        lenv = dict(load_list(spec['descriptive']['length'], 'length'))
        lres, _ = measure_envs(fits['length'], lenv)
        out['descriptive']['length_test6L'] = lres
    out['seconds'] = round(time.time() - t0, 1)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
