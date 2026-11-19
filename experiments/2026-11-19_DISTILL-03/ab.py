#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DISTILL-03 «A-НА-B» (HYPOTHESIS.md, 50a2a8f7): контроль на неспецифичность C-109 — программа головы A на ответах головы B.

Код DISTILL-02 не меняется: программы, вероятность ответа и смесь λ — оттуда (`distill02.fit_family`, `answer_prob`, `mlog`).
  L(A, B, e) — средняя лог-вероятность (смесь λ = 1e-3) числовых ответов головы B в среде e под программой A;
  вид «программа» — полная программа головы A;
  вид «форма» — признаки и наклоны формулы A (округлённые, как в оценке) при уровне головы B: свободный член подобран на
    данных построения головы B при наклонах A, доля «прочих» ε и их частоты q — головы B;
  вид «без входа» (описательно, «B1-расщеплённый» совета 75) — у каждой головы своя формула без признаков (один свободный
    член на её построении) с её ε и q;
  вид «перенос» (описательно, для разбивки преимущества на форму, уровень и «прочие») — формула A целиком при ε и q головы B.
Статистика семейства: s(a, B) = среднее по средам головы B от [L(a, B, e) − среднее по A ≠ a от L(A, B, e)];
D = среднее по головам B от s(B, B). Нуль — перестановка меток программ между головами: D_π = среднее по B от s(π(B), B),
полный перебор всех перестановок (7! = 5040), p = доля D_π ≥ D (вместе с тождественной) — точное.
  python3 ab.py fits ВЫХОД.json SPEC.json        — программы по семействам и сверка с DISTILL-02 (formulas в analysis.json)
  python3 ab.py pilot ВЫХОД.json SPEC.json       — пилот: матрицы одной среды (T_X19_p3), описательно
  python3 ab.py test ВЫХОД.json SPEC.json        — тест: матрицы, D и p по семействам и видам, вердикты RULES при уровне LEVEL
SPEC: {"construction": {семейство: [папки]}, "test": {семейство: [папки]}, "descriptive": {семейство: {имя: [папки]}} (необяз.)}"""
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
KINDS = ('prog', 'shape')                  # решающие виды; 'carry' и 'const' — описательные
DESCR_KINDS = ('carry',)                   # формула переноса A целиком при «прочих» головы B — для разбивки преимущества
PILOT_ENVS = ('T_X19_p3',)                 # пилот совета 75; в тест не входит
TEST_ENVS = {'thousands': ('T_X29_p3', 'T_X39_p3', 'T_X49_p3', 'T_X59_p3', 'T_X69_p3', 'T_X79_p3', 'T_X89_p3'),
             'length': ('L_X9_p3', 'L_X99_p3', 'L_X999_p3')}
# PREREG: решающие проверки — D > 0 и точное p ≤ LEVEL (уровень на проверку, как в программе); четыре проверки → серия ≤ 0,01
LEVEL = 0.0025
RULES = {'АБ-П-Т': ('thousands', 'prog'), 'АБ-П-Л': ('length', 'prog'), 'АБ-Ф-Т': ('thousands', 'shape'), 'АБ-Ф-Л': ('length', 'shape')}
KIN = (('Qwen2.5-0.5B-Instruct', 'Qwen2.5-1.5B-Instruct'), ('SmolLM2-360M-Instruct', 'SmolLM2-1.7B-Instruct'))   # родичи (совет 75)


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


def fit_intercept(rows, y, feats, slopes, lo=-60.0, hi=60.0, iters=200):
    """Свободный член логистической формулы при заданных признаках и наклонах. Уравнение Σ(y − σ(b + x·w)) = 0 монотонно по b —
    решается делением отрезка (метод Ньютона расходился при наклонах ±20, ERRORS № 224). Все y одной метки — край отрезка."""
    if not len(y):
        return 0.0
    off = np.array([sum(s * r[f] for s, f in zip(slopes, feats)) for r in rows], float) if feats else np.zeros(len(y))
    y = np.asarray(y, float)

    def g(b):
        return float(np.sum(y - 1 / (1 + np.exp(-np.clip(b + off, -60, 60)))))
    if g(lo) <= 0:
        return lo
    if g(hi) >= 0:
        return hi
    for _ in range(iters):
        mid = (lo + hi) / 2
        if g(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-10:
            break
    return float((lo + hi) / 2)


def shape_at_level(prog_a, prog_b, rows_b, y_b):
    """Форма формулы A (признаки и округлённые наклоны) при уровне головы B: свободный член — на построении B, ε и q — головы B."""
    feats = list(prog_a['features'])
    slopes = list(prog_a['w_round'][1:])
    b0 = fit_intercept(rows_b, y_b, feats, slopes)
    out = dict(prog_b)
    out.update(features=feats, w=[b0] + list(prog_a['w'][1:]), w_round=[D2.sig2(b0)] + slopes, shape_of=prog_a.get('_head'))
    return out


def carry_with_others(prog_a, prog_b):
    """Описательно (разбивка): формула потери переноса головы A целиком — признаки, наклоны и свободный член — при «прочих» головы B
    (её ε и частоты q). Между «формой» (свободный член B) и «программой» (всё от A): отделяет уровень переноса от «прочих»."""
    out = dict(prog_a)
    out.update(eps=prog_b['eps'], q=prog_b['q'], q_rest=prog_b['q_rest'], others_of=prog_b.get('_head'))
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
    carry = {(a, b): carry_with_others(progs[a], progs[b]) for a in progs for b in progs}
    const = {b: const_program(progs[b], *rows[b]) for b in progs}
    acc = {h: float(np.mean(np.asarray(o)[np.asarray(o) < NC] == 0)) if np.any(np.asarray(o) < NC) else None for h, o in offs.items()}
    return dict(prog=progs, shape=shape, carry=carry, const=const, acc=acc)


def env_matrices(P, env, heads_order):
    """Матрицы L[kind][a, b] одной среды: строки — чья программа (форма), столбцы — чьи ответы. NaN — голова не в среде
    (числовых ответов меньше MIN_NUMERIC). Распределение ответа программы на задаче считается один раз (`program_dist`)."""
    return matrices_from(P, *D2.env_table(env), heads_order)


def matrices_from(P, items, offs, heads_order):
    k = len(heads_order)
    M = {kind: np.full((k, k), np.nan) for kind in KINDS + DESCR_KINDS}
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
            M['carry'][ja, jb] = ll_of(P['carry'][(ha, hb)], hb)
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


_PERMS = {}


def perm_test(s):
    """D = среднее по головам s[b, b]; D_π для всех перестановок меток программ; p = доля D_π ≥ D (с допуском 1e-12)."""
    k = s.shape[0]
    D = float(np.mean(np.diag(s)))
    if k not in _PERMS:
        _PERMS[k] = np.array(list(itertools.permutations(range(k))), dtype=np.int64)
    vals = s[_PERMS[k], np.arange(k)].mean(axis=1)                     # все перестановки меток программ сразу
    p = float(np.mean(vals >= D - 1e-12))
    return dict(D=D, p=p, n_perm=len(vals), rank=int(np.sum(vals > D + 1e-12)) + 1, perm_mean=float(np.mean(vals)),
                perm_max=float(np.max(vals)), n_distinct=int(len(np.unique(np.round(vals, 12)))),
                per_head={int(b): float(s[b, b] - (np.sum(s[:, b]) - s[b, b]) / (k - 1)) for b in range(k)})


def decomposition(mats, heads_order):
    """Описательно (гипотеза: «разбивка преимущества программы на уровень, форму и „прочие“»). Для головы B в среде e, среднее по A ≠ B:
      всё     = Lп(B, B) − Lп(A, B);
      форма   = Lп(B, B) − Lф(A, B)  (чужие признаки и наклоны при уровне и «прочих» B);
      уровень = Lф(A, B) − Lпер(A, B) (свободный член B против свободного члена A — при «прочих» B);
      прочие  = Lпер(A, B) − Lп(A, B) («прочие» B против «прочих» A — при формуле A целиком).
    Сумма трёх частей равна «всему» тождественно; среднее «всего» по головам — D вида «программа». Дальше — среднее по средам головы."""
    k = len(heads_order)
    parts = {p: [] for p in ('total', 'form', 'level', 'others')}
    for Mp, Ms, Mc in zip(mats['prog'], mats['shape'], mats['carry']):
        row = {p: np.full(k, np.nan) for p in parts}
        for b in range(k):
            if not np.isfinite(Mp[b, b]):
                continue
            o = [a for a in range(k) if a != b]
            row['total'][b] = Mp[b, b] - np.mean(Mp[o, b])
            row['form'][b] = Mp[b, b] - np.mean(Ms[o, b])
            row['level'][b] = np.mean(Ms[o, b] - Mc[o, b])
            row['others'][b] = np.mean(Mc[o, b] - Mp[o, b])
        for p in parts:
            parts[p].append(row[p])
    out = {}
    for p, v in parts.items():
        with np.errstate(invalid='ignore'):
            ph = np.nanmean(np.array(v), axis=0)
        out[p] = dict(per_head={h: float(x) for h, x in zip(heads_order, ph)}, mean=float(np.nanmean(ph)))
    return out


def kinship(mats, heads_order, pairs=KIN):
    """Описательно (совет 75, «градиент родства»): своя / родич / чужие. Для головы B с родичем R, среднее по средам головы:
    своя − родич = L(B, B) − L(R, B); родич − чужие = L(R, B) − среднее по A ∉ {B, R} от L(A, B); своя − чужие — так же."""
    k = len(heads_order)
    out = {}
    for h1, h2 in pairs:
        if h1 not in heads_order or h2 not in heads_order:
            continue
        for hb, hr in ((h1, h2), (h2, h1)):
            b, r = heads_order.index(hb), heads_order.index(hr)
            st = [a for a in range(k) if a not in (b, r)]
            v = np.array([[M[b, b] - M[r, b], M[r, b] - np.mean(M[st, b]), M[b, b] - np.mean(M[st, b])] for M in mats])
            with np.errstate(invalid='ignore'):
                m = np.nanmean(v, axis=0)
            out[hb] = dict(relative=hr, own_minus_relative=float(m[0]), relative_minus_strangers=float(m[1]), own_minus_strangers=float(m[2]))
    keys = ('own_minus_relative', 'relative_minus_strangers', 'own_minus_strangers')
    mean = {kk: float(np.nanmean([v[kk] for v in out.values()])) if out else float('nan') for kk in keys}
    return dict(per_head=out, mean=mean)


def family_result(P, envs, names, heads_order):
    """envs: {имя: среда-словарь сборки} или {имя: (items, offs)} — второе для заглушек."""
    mats = {kind: [] for kind in KINDS + DESCR_KINDS}
    const, envs_out = [], {}
    for name in names:
        e = envs[name]
        M, n_num = matrices_from(P, *e, heads_order) if isinstance(e, tuple) else env_matrices(P, e, heads_order)
        for kind in KINDS + DESCR_KINDS:
            mats[kind].append(M[kind])
        const.append(M['const'])
        envs_out[name] = dict(n_numeric=n_num, **{kind: M[kind].tolist() for kind in KINDS + DESCR_KINDS}, const=M['const'].tolist(),
                              diag_minus_offmean={kind: (np.diag(M[kind]) - (np.nansum(M[kind], axis=0) - np.diag(M[kind])) /
                                                         (len(heads_order) - 1)).tolist() for kind in KINDS})
    res = dict(envs=envs_out, heads=heads_order)
    for kind in KINDS:
        s = s_table(mats[kind])
        ok = [j for j in range(len(heads_order)) if np.all(np.isfinite(s[:, j]))]      # голова хоть в одной среде
        res[kind] = dict(s=s.tolist(), heads_in_test=[heads_order[j] for j in ok], **perm_test(s[np.ix_(ok, ok)]))
    own = np.array([np.diag(m) for m in mats['prog']])         # среды × головы
    res['input_gain'] = dict(per_env_head=(own - np.array(const)).tolist(), mean=float(np.nanmean(own - np.array(const))))
    # описательно (записка литературы): «ближайший чужой» — своя минус лучшая из чужих, по средам и головам
    for kind in KINDS:
        nn = []
        for m in mats[kind]:
            k = m.shape[0]
            nn.append([float(m[b, b] - np.nanmax(np.delete(m[:, b], b))) if np.isfinite(m[b, b]) else float('nan') for b in range(k)])
        nn = np.array(nn)
        res[kind]['nearest_other'] = dict(per_env_head=nn.tolist(), per_head=np.nanmean(nn, axis=0).tolist(), mean=float(np.nanmean(nn)),
                                          heads_own_best=int(np.sum(np.nanmean(nn, axis=0) > 0)))
    res['decomposition'] = decomposition(mats, heads_order)
    res['kinship'] = {kind: kinship(mats[kind], heads_order) for kind in KINDS}
    res['accuracy_construction'] = {h: P['acc'].get(h) for h in heads_order}
    # проверка формы: своя форма при своём уровне почти совпадает со своей программой (наклоны те же, свободный член подобран заново)
    res['own_shape_minus_own_prog'] = (np.array([np.diag(m) for m in mats['shape']]) - own).tolist()
    res['shape_intercepts'] = {f"{a}|{b}": P['shape'][(a, b)]['w_round'][0] for a in heads_order for b in heads_order}
    return res


# ───────────── сборка данных и команды
def load_family_envs(dirs, fam):
    """Список сред семейства из всех папок — как в DISTILL-02 (`test_d2`): одна и та же среда (T_X19_p3) есть в нескольких фазах,
    поэтому список, а не словарь по имени (ERRORS № 224: словарь оставлял только последнюю фазу)."""
    envs = []
    for d in dirs:
        envs += [(n, e) for n, e in D2.load_merged(d).items() if D2.family_of(n) == fam]
    return envs


def fits_cmd(dst, spec):
    t0 = time.time()
    out = dict(families={})
    ref = json.load(open(spec['distill02_analysis'], encoding='utf-8'))['formulas'] if spec.get('distill02_analysis') else None
    for fam, dirs in spec['construction'].items():
        progs = family_programs([e for _, e in load_family_envs(dirs, fam)])['prog']
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


def code_hashes():
    import hashlib

    def h(p):
        return hashlib.sha256(open(p, 'rb').read()).hexdigest()
    return {'ab.py': h(os.path.abspath(__file__)), 'distill02.py': h(os.path.abspath(D2.__file__))}


def unique_envs(dirs, fam):
    """{имя: среда} семейства; одна среда дважды — СТОП (в тесте и в описательных наборах фаза одна; ERRORS № 224)."""
    lst = load_family_envs(dirs, fam)
    d = dict(lst)
    assert len(d) == len(lst), 'одна среда встретилась дважды'
    return d


def verdicts(families):
    """PREREG: «да» — D > 0 и точное p ≤ LEVEL; иначе «нет». Нет данных семейства — None."""
    out = {}
    for rule, (fam, kind) in RULES.items():
        r = families.get(fam, {}).get(kind)
        if r is None:
            out[rule] = dict(family=fam, kind=kind, verdict=None)
            continue
        yes = bool(r['D'] > 0 and r['p'] <= LEVEL + 1e-15)
        out[rule] = dict(family=fam, kind=kind, D=r['D'], p=r['p'], rank=r['rank'], n_perm=r['n_perm'], heads=len(r['heads_in_test']),
                         level=LEVEL, verdict='да' if yes else 'нет')
    return out


def run_cmd(dst, spec, phase):
    t0 = time.time()
    out = dict(phase=phase, lam=D2.LAMBDA, level=LEVEL, code=code_hashes(), families={})
    for fam, dirs in spec['construction'].items():
        P = family_programs([e for _, e in load_family_envs(dirs, fam)])
        heads_order = sorted(P['prog'])
        test_envs = unique_envs(spec['test'][fam], fam)
        out.setdefault('construction_n', {})[fam] = {h: int(p['n_numeric']) for h, p in P['prog'].items()}
        want = PILOT_ENVS if phase == 'pilot' else TEST_ENVS[fam]
        if phase == 'test':
            miss = [n for n in want if n not in test_envs]
            assert not miss, f'в тесте нет сред: {miss}'
        names = [n for n in want if n in test_envs]
        fo = {}
        if names:
            fo = family_result(P, test_envs, names, heads_order)
            for kind in KINDS:
                r = fo[kind]
                print(fam, kind, '| сред', len(names), '| D =', round(r['D'], 4), '| p =', round(r['p'], 5), '| ранг', r['rank'], 'из', r['n_perm'], flush=True)
        for dname, ddirs in spec.get('descriptive', {}).get(fam, {}).items():
            denvs = unique_envs(ddirs, fam)
            fo.setdefault('descriptive', {})[dname] = family_result(P, denvs, sorted(denvs), heads_order)
        if fo:
            out['families'][fam] = fo
    if phase == 'test':
        out['verdicts'] = verdicts(out['families'])
        for rule, v in out['verdicts'].items():
            print(rule, '|', v['verdict'], '| D =', None if v.get('D') is None else round(v['D'], 4), '| p =', v.get('p'), flush=True)
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
