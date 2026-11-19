#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-03 «A-НА-B» (HYPOTHESIS.md, 50a2a8f7): контроль на неспецифичность C-109 — программа головы A на ответах головы B.

Код DISTILL-02 не меняется: программы, вероятность ответа и смесь λ — оттуда (`distill02.fit_family`, `answer_prob`, `mlog`).
  L(A, B, e) — средняя лог-вероятность (смесь λ = 1e-3) числовых ответов головы B в среде e под программой A;
  вид «программа» — полная программа головы A;
  вид «форма» — признаки и наклоны формулы A (округлённые, как в оценке) при уровне головы B: свободный член подобран на
    данных построения головы B при наклонах A, доля «прочих» ε и их частоты q — головы B;
  вид «без входа» (описательно, «B1-расщеплённый» совета 75) — у каждой головы своя формула без признаков (один свободный
    член на её построении) с её ε и q.
Статистика семейства: s(a, B) = среднее по средам головы B от [L(a, B, e) − среднее по A ≠ a от L(A, B, e)];
D = среднее по головам B от s(B, B). Нуль — перестановка меток программ между головами: D_π = среднее по B от s(π(B), B),
полный перебор всех перестановок (7! = 5040), p = доля D_π ≥ D (вместе с тождественной) — точное.
  python3 ab.py fits ВЫХОД.json SPEC.json        — программы по семействам и сверка с DISTILL-02 (formulas в analysis.json)
  python3 ab.py pilot ВЫХОД.json SPEC.json       — пилот: матрицы одной среды (T_X19_p3), описательно
  python3 ab.py test ВЫХОД.json SPEC.json        — тест: матрицы, D и p по семействам и видам (нужны константы PREREG)"""
import itertools
import json
import math
import os
import sys
import time

import numpy as np

X_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(X_DIR))
sys.path.insert(0, os.path.join(ROOT, 'experiments', '2026-11-18_DISTILL-02'))
import distill02 as D2  # noqa: E402

NC = D2.NC
MIN_NUMERIC = D2.MIN_NUMERIC
KINDS = ('prog', 'shape')                  # решающие виды; 'const' — описательный
PILOT_ENVS = ('T_X19_p3',)                 # пилот совета 75; в тест не входит
TEST_ENVS = {'thousands': ('T_X29_p3', 'T_X39_p3', 'T_X49_p3', 'T_X59_p3', 'T_X69_p3', 'T_X79_p3', 'T_X89_p3'),
             'length': ('L_X9_p3', 'L_X99_p3', 'L_X999_p3')}


# ───────────── строки формулы (как в distill02.fit_program) и подбор свободного члена при заданных наклонах
def program_rows(items, offsets):
    """Строки и метки формулы головы: по задачам с числовым ответом, чьё смещение — набор потерянных переносов (как fit_program)."""
    rows, y = [], []
    for it, d in zip(items, offsets):
        if d >= NC:
            continue
        pf = D2.position_features(it['a'], it['b'], it['ood'])
        Dset = D2.lost_set(int(d), [r['j'] for r in pf])
        if Dset is None:
            continue
        for r in pf:
            rows.append(r)
            y.append(1.0 if r['j'] in Dset else 0.0)
    return rows, np.array(y)


def fit_intercept(rows, y, feats, slopes, iters=100):
    """Свободный член логистической формулы при заданных признаках и наклонах (метод Ньютона по одному параметру)."""
    if not len(y):
        return 0.0
    off = np.array([sum(s * r[f] for s, f in zip(slopes, feats)) for r in rows], float) if feats else np.zeros(len(y))
    b = 0.0
    for _ in range(iters):
        z = np.clip(b + off, -30, 30)
        p = 1 / (1 + np.exp(-z))
        g = float(np.sum(y - p))
        h = float(np.sum(p * (1 - p))) + 1e-12
        step = g / h
        b += step
        if abs(step) < 1e-12:
            break
    return float(b)


def shape_at_level(prog_a, prog_b, rows_b, y_b):
    """Форма формулы A (признаки и округлённые наклоны) при уровне головы B: свободный член — на построении B, ε и q — головы B."""
    feats = list(prog_a['features'])
    slopes = list(prog_a['w_round'][1:])
    b0 = fit_intercept(rows_b, y_b, feats, slopes)
    out = dict(prog_b)
    out.update(features=feats, w=[b0] + list(prog_a['w'][1:]), w_round=[D2.sig2(b0)] + slopes, shape_of=prog_a.get('_head'))
    return out


def const_program(prog_b, rows_b, y_b):
    """Формула без входа (один свободный член на построении головы B) с её ε и q — «B1-расщеплённый», описательно."""
    b0 = fit_intercept(rows_b, y_b, [], [])
    out = dict(prog_b)
    out.update(features=[], w=[b0], w_round=[D2.sig2(b0)])
    return out


# ───────────── матрицы
def family_programs(env_dicts):
    """Программы голов семейства (как в DISTILL-02, без ящика); формы «A при уровне B» и формулы «без входа» — один раз на семейство."""
    return programs_from(*D2.family_data(env_dicts))


def programs_from(items, offs):
    progs, rows = {}, {}
    for h, o in offs.items():
        p = D2.fit_program(items, o)
        p['_head'] = h
        progs[h] = p
        rows[h] = program_rows(items, o)
    shape = {(a, b): shape_at_level(progs[a], progs[b], *rows[b]) for a in progs for b in progs}     # и диагональ — той же процедурой
    const = {b: const_program(progs[b], *rows[b]) for b in progs}
    return dict(prog=progs, shape=shape, const=const)


def env_matrices(P, env, heads_order):
    """Матрицы L[kind][a, b] одной среды: строки — чья программа (форма), столбцы — чьи ответы. NaN — голова не в среде
    (числовых ответов меньше MIN_NUMERIC). Распределение ответа программы на задаче считается один раз (`program_dist`)."""
    return matrices_from(P, *D2.env_table(env), heads_order)


def matrices_from(P, items, offs, heads_order):
    k = len(heads_order)
    M = {kind: np.full((k, k), np.nan) for kind in KINDS}
    M['const'] = np.full(k, np.nan)
    present = [hb for hb in heads_order if hb in offs and int((offs[hb] < NC).sum()) >= MIN_NUMERIC]
    n_num = {hb: int((offs[hb] < NC).sum()) for hb in present}

    def ll_of(prog, hb, dists=None):
        out = []
        for i, (it, d) in enumerate(zip(items, offs[hb])):
            if d >= NC:
                continue
            y = it['sum'] + int(d)
            dist = dists[i] if dists is not None else D2.program_dist(prog, it, True)
            out.append(D2.mlog(D2.answer_prob(prog, it, y, True, dist), it['sum']))
        return float(np.mean(out)) if out else float('nan')

    for ja, ha in enumerate(heads_order):
        dists = [D2.program_dist(P['prog'][ha], it, True) for it in items]
        for hb in present:
            M['prog'][ja, heads_order.index(hb)] = ll_of(P['prog'][ha], hb, dists)
    for hb in present:
        jb = heads_order.index(hb)
        for ja, ha in enumerate(heads_order):
            M['shape'][ja, jb] = ll_of(P['shape'][(ha, hb)], hb)
        M['const'][jb] = ll_of(P['const'][hb], hb)
    return M, n_num


# ───────────── статистика и точный перестановочный тест
def s_table(mats):
    """s[a, b] = среднее по средам головы b от [L(a, b, e) − среднее по A ≠ a от L(A, b, e)] (NaN-среды головы пропускаются)."""
    st = []
    for M in mats:
        k = M.shape[0]
        S = np.nansum(M, axis=0, keepdims=True)
        st.append(M - (S - M) / (k - 1))
    A = np.stack(st)                               # среды × a × b
    with np.errstate(invalid='ignore'):
        return np.nanmean(A, axis=0)


def perm_test(s):
    """D = среднее по головам s[b, b]; D_π для всех перестановок меток программ; p = доля D_π ≥ D (с допуском 1e-12)."""
    k = s.shape[0]
    D = float(np.mean(np.diag(s)))
    vals = np.array([np.mean(s[list(pi), range(k)]) for pi in itertools.permutations(range(k))])
    p = float(np.mean(vals >= D - 1e-12))
    return dict(D=D, p=p, n_perm=len(vals), rank=int(np.sum(vals > D + 1e-12)) + 1, perm_mean=float(np.mean(vals)),
                perm_max=float(np.max(vals)), per_head={int(b): float(s[b, b] - (np.sum(s[:, b]) - s[b, b]) / (k - 1)) for b in range(k)})


def family_result(P, envs, names, heads_order):
    """envs: {имя: среда-словарь сборки} или {имя: (items, offs)} — второе для заглушек."""
    mats = {kind: [] for kind in KINDS}
    const, envs_out = [], {}
    for name in names:
        e = envs[name]
        M, n_num = matrices_from(P, *e, heads_order) if isinstance(e, tuple) else env_matrices(P, e, heads_order)
        for kind in KINDS:
            mats[kind].append(M[kind])
        const.append(M['const'])
        envs_out[name] = dict(n_numeric=n_num, **{kind: M[kind].tolist() for kind in KINDS}, const=M['const'].tolist(),
                              diag_minus_offmean={kind: (np.diag(M[kind]) - (np.nansum(M[kind], axis=0) - np.diag(M[kind])) /
                                                         (len(heads_order) - 1)).tolist() for kind in KINDS})
    res = dict(envs=envs_out, heads=heads_order)
    for kind in KINDS:
        s = s_table(mats[kind])
        ok = [j for j in range(len(heads_order)) if np.all(np.isfinite(s[:, j]))]      # голова хоть в одной среде
        res[kind] = dict(s=s.tolist(), heads_in_test=[heads_order[j] for j in ok], **perm_test(s[np.ix_(ok, ok)]))
    own = np.array([np.diag(m) for m in mats['prog']])         # среды × головы
    res['input_gain'] = dict(per_env_head=(own - np.array(const)).tolist(), mean=float(np.nanmean(own - np.array(const))))
    return res


# ───────────── сборка данных и команды
def load_family_envs(dirs):
    envs = {}
    for d in dirs:
        envs.update(D2.load_merged(d))
    return envs


def fits_cmd(dst, spec):
    t0 = time.time()
    out = dict(families={})
    ref = json.load(open(spec['distill02_analysis'], encoding='utf-8'))['formulas'] if spec.get('distill02_analysis') else None
    for fam, dirs in spec['construction'].items():
        envs = load_family_envs(dirs)
        progs = family_programs(list(envs.values()))['prog']
        cmp = {}
        for h, p in progs.items():
            r = (ref or {}).get(fam, {}).get(h)
            cmp[h] = None if r is None else dict(features=r['features'] == p['features'], w_round=r['w_round'] == p['w_round'],
                                                 eps=abs(r['eps'] - p['eps']) < 1e-12, q=r['q'] == {str(k): v for k, v in p['q'].items()})
        out['families'][fam] = dict(programs={h: {k: v for k, v in p.items() if k != '_head'} for h, p in progs.items()}, same_as_distill02=cmp)
    out['seconds'] = round(time.time() - t0, 1)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    for fam, f in out['families'].items():
        print(fam, '| совпадение с DISTILL-02:', {h: (all(v.values()) if v else None) for h, v in f['same_as_distill02'].items()})
    return 0


def run_cmd(dst, spec, phase):
    t0 = time.time()
    out = dict(phase=phase, lam=D2.LAMBDA, families={})
    for fam, dirs in spec['construction'].items():
        P = family_programs(list(load_family_envs(dirs).values()))
        heads_order = sorted(P['prog'])
        test_envs = load_family_envs(spec['test'][fam])
        names = [n for n in (PILOT_ENVS if phase == 'pilot' else TEST_ENVS[fam]) if n in test_envs]
        if not names:
            continue
        out['families'][fam] = family_result(P, test_envs, names, heads_order)
        for kind in KINDS:
            r = out['families'][fam][kind]
            print(fam, kind, '| сред', len(names), '| D =', round(r['D'], 4), '| p =', round(r['p'], 5), '| ранг', r['rank'], 'из', r['n_perm'], flush=True)
        if 'descriptive' in spec:
            for dfam_name, ddirs in spec['descriptive'].get(fam, {}).items():
                denvs = load_family_envs(ddirs)
                out['families'][fam].setdefault('descriptive', {})[dfam_name] = family_result(P, denvs, sorted(denvs), heads_order)
    out['seconds'] = round(time.time() - t0, 1)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return 0


def main(a):
    spec = json.load(open(a[2], encoding='utf-8'))
    if a[0] == 'fits':
        return fits_cmd(a[1], spec)
    if a[0] in ('pilot', 'test'):
        return run_cmd(a[1], spec, a[0])
    raise SystemExit('команда: fits | pilot | test')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
