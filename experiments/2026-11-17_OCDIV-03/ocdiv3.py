#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCDIV-03 «тысячи» (HYPOTHESIS.md, коммит 4b8160ec): ложное большинство голов вне диапазона на семействе «тысячи».
- П1: Т4 = F − F₀(N0) тем же кодом и теми же зёрнами, что OCDIV-02 (повтор C-105).
- П2: Т4ᵈ = F − F₀(Nd): нуль со стратами по предсказанной трудности задачи d̂ из признаков входа (S = 8; модели голов — на пилоте 2).
- П3: Т4-ID — та же F − F₀(N0) на задачах ID (правило, если мощность по пилоту ≥ 0,2).
- Описательно: другие S, страты по переносам и клетки «c1 × u», разложение Т4 (нуль N3), гомоплазия, пары производителей, Т4 из формул.
  python3 ocdiv3.py pilot RESULT.json MERGED_PILOT2 [--boot 1000] [--workers 4]
  python3 ocdiv3.py test  RESULT.json MERGED_TEST2 MERGED_PILOT2 PILOT_RESULT.json [--boot 10000] [--boot-descr 2000] [--workers 4]
MERGED_* — каталоги ocdiv2.py merge (семейство thousands, фаза pilot2 или test2). PILOT_RESULT — разбор пилота, закоммиченный до PREREG:
анализ теста сверяет с ним веса моделей голов и останавливается при расхождении.
Код счёта — OCDIV-02 (регистрация, prereg_hashes2.json): prepare_id, dmat, false_major, permute_cols, f_stats, homoplasy, carries;
блок N0 повторяет ocdiv2.env_analysis (стр. 296–314) тем же порядком вызовов (совпадение до бита — test_ocdiv3.py).
Сырой вывод теста до этого анализа не читается (замок ERRORS № 180)."""
import concurrent.futures as cf
import itertools
import json
import os
import sys
import time

import platform

import numpy as np
import scipy
from scipy.stats import chi2, norm

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(EXP)
sys.path.insert(0, os.path.join(EXP, '2026-11-17_OCDIV-02'))
sys.path.insert(0, os.path.join(EXP, '2026-11-17_DISTILL-01'))
import ocdiv2 as W  # noqa: E402   OCDIV-02 (prereg_hashes2.json): счёт Т4, проверка метода, сборка
import distill as DS  # noqa: E402  DISTILL-01: sig, false_major_indep (Т4 из формул, ступень 1)

V, P, S, D2 = W.V, W.P, W.S, W.D2
NC = W.NONE_CODE
CROWD = W.CROWD

# ───────────── константы HYPOTHESIS (4b8160ec): пилотом не выбираются
FAMILY, PILOT_PHASE, TEST_PHASE = 'thousands', 'pilot2', 'test2'
S_RULE, S_DESCR = 8, (2, 4, 16)
LAMBDA = 1.0
LEVEL, DESCR_LEVEL, Z = P.LEVEL, P.DESCR_LEVEL, P.Z
N_ENVS = 5
Z_ENV = float(norm.ppf(1 - LEVEL / N_ENVS))        # пометка «общий»: интервал среды при 0,0025 / 5
GENERAL_MIN = 2
P3_POWER_MIN = 0.2
MIN_VALID = 4
NONDEG_ORACLE = 0.1
K_POINT, K_BOOT = W.K_NULL_POINT, W.K_NULL_BOOT   # 1000 и 10 перестановок, как в OCDIV-02
B_DESCR = 2000
UG = 'не решено (предохранитель)'
# зёрна (+ смещение среды ocdiv2.off_of); N0 теста — зёрна OCDIV-02 (W.SEED_NULL_TEST, W.SEED_NULL_BOOT_TEST)
SEED_ND, SEED_ND_BOOT = 8_800_000, 8_810_000
SEED_ID, SEED_ID_BOOT = 8_820_000, 8_830_000
SEED_DS, SEED_DS_BOOT = 8_840_000, 8_850_000
SEED_PAIRS = 8_860_000
SEED_FIX = 8_870_000                                # пересчёт без ответов с лишними токенами (описательно)
SEED_READ, SEED_P_READ = 8_880_000, 8_885_000       # совет 70, Н1: проверка чтения П2 (тест и пилот)
READ_MIN_ENVS, EMPTY_MAX = 4, 2                     # Н1: шаг 1 пройден хотя бы в 4 годных средах; шаг 0 — пустых страт не больше 2 из 8
READ_INFORMATIVE = 'сверх трудности, видимой во входе'
READ_NONINF = 'П2 неинформативно: страты d̂ на тесте не различили трудность (перенос моделей p = 1 → p = 3 не подтверждён)'
SEED_P_N0, SEED_P_N0_BOOT = 8_710_000, 8_720_000   # пилот (мощность)
SEED_P_ND, SEED_P_ND_BOOT = 8_730_000, 8_740_000
SEED_P_ID, SEED_P_ID_BOOT = 8_760_000, 8_770_000
SEED_P_DS, SEED_P_DS_BOOT = 8_780_000, 8_790_000
SEED_P_PAIRS = 8_795_000
SEED_POWER3 = 8_610_000
SEED_REP = 8_990_000
DS_NULLS = ('N0', 'Nd2', 'Nd4', 'Nd8', 'Nd16', 'переносы', 'клетки c1×u', 'N3')
K_PAIRS = 200
OBSERVED_PAIRS = frozenset({frozenset({'Qwen2.5-0.5B-Instruct', 'Qwen2.5-1.5B-Instruct'}),
                            frozenset({'SmolLM2-1.7B-Instruct', 'SmolLM2-360M-Instruct'})})
NONDEG_ENVS = ('T_X19_p3', 'T_X29_p3', 'T_X39_p3', 'T_X49_p3', 'T_X59_p3')   # невырождены по пилоту 2: оракул 0,56–0,96 (HYPOTHESIS §1)
# константы PREREG (по разбору пилота, до данных теста); None — не заданы
P3_RULE = True            # мощность «подтверждено» Т4-ID по пилоту 2 — 1,000 ≥ 0,2 (gha_out/ocdiv3_pilot/pilot.json, a0359075): П3 — правило


# ───────────── признаки входа, модели голов, страты
def feats(a, b):
    """x(j) — только признаки входа (HYPOTHESIS §4): c1 — перенос из единиц; n9 — девяток в двух младших цифрах a; u и v — цифры
    десятков и единиц суммы, one-hot по 10 значениям. Ответы голов не читаются."""
    s = a + b
    x = np.zeros(22)
    x[0] = float(a % 10 + b % 10 >= 10)
    x[1] = float(f'{a % 100:02d}'.count('9'))
    x[2 + (s // 10) % 10] = 1.0
    x[12 + s % 10] = 1.0
    return x


def cell_of(a, b):
    """Клетка «c1 × u» (описательно): 20 клеток."""
    s = a + b
    return int(a % 10 + b % 10 >= 10) * 10 + (s // 10) % 10


def ridge_logit(X, y, lam=LAMBDA, iters=200):
    """Гребневая логистическая регрессия ошибки головы (Ньютон); свободный член без штрафа."""
    Xb = np.column_stack([np.ones(len(X)), X])
    pen = np.full(Xb.shape[1], float(lam))
    pen[0] = 0.0
    w = np.zeros(Xb.shape[1])
    for _ in range(iters):
        p = DS.sig(Xb @ w)
        g = Xb.T @ (y - p) - pen * w
        H = (Xb * (p * (1 - p))[:, None]).T @ Xb + np.diag(pen) + 1e-9 * np.eye(len(w))
        step = np.linalg.solve(H, g)
        w = w + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return w


def p_hat(w, X):
    return DS.sig(np.column_stack([np.ones(len(X)), X]) @ np.asarray(w, float))


def short(label):
    return label.split('@')[0]


def head_rows(envs, exclude=()):
    """Задачи вне диапазона сред пилота (кроме exclude): {голова: (X, y)}; y = 1 — ответ не верен (в том числе без числа)."""
    acc = {}
    for name in sorted(envs):
        if name in exclude:
            continue
        env = envs[name]
        ood = [j for j, q in enumerate(env['problems']) if q['range'] != 'ID']
        Xe = np.array([feats(env['problems'][j]['a'], env['problems'][j]['b']) for j in ood])
        for h in env['heads']:
            y = np.array([0.0 if h['rows'][j]['correct'] else 1.0 for j in ood])
            xs, ys = acc.setdefault(short(h['model']), ([], []))
            xs.append(Xe)
            ys.append(y)
    return {nm: (np.vstack(xs), np.concatenate(ys)) for nm, (xs, ys) in acc.items()}


def fit_models(envs, exclude=()):
    return {nm: ridge_logit(X, y) for nm, (X, y) in sorted(head_rows(envs, exclude).items())}


def dhat(models, crowd, X):
    """d̂(j) — средняя по толпе среды предсказанная вероятность ошибки."""
    return np.mean([p_hat(models[nm], X) for nm in crowd], axis=0)


def strata_of(d, n_strata):
    """Страты по d̂: порядок (d̂, номер задачи), n_strata равных подряд идущих групп."""
    order = np.lexsort((np.arange(len(d)), d))
    lab = np.empty(len(d), np.int64)
    for s, g in enumerate(np.array_split(order, n_strata)):
        lab[g] = s
    return lab


# ───────────── нули
def permute_wrong(D, rng, strata):
    """N3 (описательно): внутри головы неверные числовые ответы переставляются между её задачами с неверным числовым ответом внутри
    страты; верные ответы и «без числа» остаются на месте (картина «кто где ошибся» сохраняется)."""
    out = D.copy()
    groups = [np.nonzero(strata == s)[0] for s in np.unique(strata)]
    for k in range(D.shape[1]):
        col = D[:, k]
        for g in groups:
            w = g[(col[g] != 0) & (col[g] < NC)]
            if len(w) > 1:
                out[w, k] = col[w[rng.permutation(len(w))]]
    return out


def t4_block_ocdiv2(D, strata_c, seed_null, seed_null_boot, B, K_point, K_boot):
    """Т4 (N0), Т4 со стратами по переносам и гомоплазия — тем же порядком вызовов и теми же потоками, что ocdiv2.env_analysis
    (стр. 296–314). Возвращает (поле T4 как в OCDIV-02, повторы N0, повторы со стратами, гомоплазия)."""
    n = D.shape[0]
    gn = np.random.default_rng(seed_null)
    F, F0, dF = W.f_stats(D, gn, K_point)
    _, F0s, dFs = W.f_stats(D, gn, K_point, strata_c)
    gbn = np.random.default_rng(seed_null_boot)
    bF, bFs = [], []
    for _ in range(B):
        rows = gbn.integers(0, n, n)
        Db, sb = D[rows], strata_c[rows]
        bF.append(W.f_stats(Db, gbn, K_boot)[2])
        bFs.append(W.f_stats(Db, gbn, K_boot, sb)[2])
    t4 = dict(F=F, F0=F0, point=dF, sd=float(np.std(bF, ddof=1)), F0_strata=F0s, point_strata=dFs, sd_strata=float(np.std(bFs, ddof=1)),
              strata_counts={int(s): int((strata_c == s).sum()) for s in np.unique(strata_c)})
    hm = W.homoplasy(D)
    H0 = float(np.mean([W.homoplasy(W.permute_cols(D, gn)).mean() for _ in range(K_point)]))
    return t4, np.array(bF), np.array(bFs), dict(H=float(hm.mean()), H0=H0, diff=float(hm.mean()) - H0)


def t4_stream(D, strata, seed, seed_boot, B, K_point, K_boot):
    """F − F₀ при перестановке внутри головы (внутри страт, если strata задана): точка и повторы бутстрепа своим потоком."""
    n = D.shape[0]
    g = np.random.default_rng(seed)
    F, F0, dF = W.f_stats(D, g, K_point, strata)
    gb = np.random.default_rng(seed_boot)
    bt = []
    for _ in range(B):
        rows = gb.integers(0, n, n)
        bt.append(W.f_stats(D[rows], gb, K_boot, None if strata is None else strata[rows])[2])
    bt = np.array(bt)
    return dict(F=F, F0=F0, point=dF, sd=float(np.std(bt, ddof=1)) if B > 1 else float('nan'), n=int(n)), bt


def f0_all(D, g, K, sm):
    """F₀ всех описательных нулей DS_NULLS — по K перестановок каждый, в порядке DS_NULLS."""
    out = {}
    for k in DS_NULLS:
        if k == 'N3':
            out[k] = float(np.mean([W.false_major(permute_wrong(D, g, sm['Nd8'])).mean() for _ in range(K)]))
        else:
            st = None if k == 'N0' else sm[k]
            out[k] = float(np.mean([W.false_major(W.permute_cols(D, g, st)).mean() for _ in range(K)]))
    return out


def descr_stream(D, sm, seed, seed_boot, B, K_point, K_boot):
    """Описательные нули на общих повторах (для разностей): Т4 при каждом нуле и разложение
    Т4 = [F₀(Nd8) − F₀(N0)] + [F₀(N3) − F₀(Nd8)] + [F − F₀(N3)]."""
    n = D.shape[0]

    def comp(F, f0):
        r = {f'T4 {k}': F - f0[k] for k in DS_NULLS}
        r['трудность по входу'] = f0['Nd8'] - f0['N0']
        r['совместность ошибок'] = f0['N3'] - f0['Nd8']
        r['совпадение ответов'] = F - f0['N3']
        return r
    g = np.random.default_rng(seed)
    pt = comp(float(W.false_major(D).mean()), f0_all(D, g, K_point, sm))
    gb = np.random.default_rng(seed_boot)
    reps = []
    for _ in range(B):
        rows = gb.integers(0, n, n)
        Db = D[rows]
        reps.append(comp(float(W.false_major(Db).mean()), f0_all(Db, gb, K_boot, {k: (None if v is None else v[rows]) for k, v in sm.items()})))
    bt = {k: np.array([r[k] for r in reps]) for k in pt}
    return pt, bt


def pair_excess(D, rng, K):
    """r_ij — доля задач, где обе головы ошиблись одним и тем же числовым ответом, минус то же при N0 (среднее K перестановок)."""
    def u(Dx):
        wrong = (Dx != 0) & (Dx < NC)
        return ((Dx[:, :, None] == Dx[:, None, :]) & wrong[:, :, None]).mean(0)
    u_obs = u(D)
    u0 = np.mean([u(W.permute_cols(D, rng)) for _ in range(K)], axis=0)
    return u_obs - u0


def structures(heads):
    """Все 105 способов выбрать две непересекающиеся пары «одного производителя» среди семи голов."""
    out = []
    pairs = list(itertools.combinations(heads, 2))
    for p1, p2 in itertools.combinations(pairs, 2):
        if not set(p1) & set(p2):
            out.append(frozenset({frozenset(p1), frozenset(p2)}))
    return sorted(set(out), key=lambda s: sorted(tuple(sorted(p)) for p in s))


def contrast(rmaps, struct):
    """Контраст «пары одного производителя − пары разных» по r, среднее по средам, где есть пары обоих видов."""
    vals = []
    for crowd, r in rmaps:
        same, cross = [], []
        for i, j in itertools.combinations(range(len(crowd)), 2):
            (same if frozenset({crowd[i], crowd[j]}) in struct else cross).append(r[i, j])
        if same and cross:
            vals.append(np.mean(same) - np.mean(cross))
    return float(np.mean(vals)) if vals else float('nan')


def pairs_test(rmaps):
    """Точный перебор 105 структур: p — доля структур с контрастом не меньше наблюдённого (описательно; наименьшее p = 1/105)."""
    obs = contrast(rmaps, OBSERVED_PAIRS)
    allc = [contrast(rmaps, s) for s in structures(list(CROWD))]
    fin = [c for c in allc if np.isfinite(c)]
    return dict(observed=obs, n_structures=len(allc), p_exact=(float(np.mean([c >= obs - 1e-15 for c in fin])) if fin and np.isfinite(obs) else None),
                null_mean=(float(np.mean(fin)) if fin else None))


def t4_formula(models, crowd, X):
    """Т4 из формул (DISTILL-01, ступень 1): условная независимость, неверные ответы без совпадений."""
    Pm = np.array([p_hat(models[nm], X) for nm in crowd])
    F = float(np.mean([DS.false_major_indep(Pm[:, j]) for j in range(Pm.shape[1])]))
    F0 = float(DS.false_major_indep(Pm.mean(1)))
    return dict(F_pred=F, F0_pred=F0, T4_pred=F - F0, crowd=list(crowd), n=int(Pm.shape[1]))


def empty_strata(d, lab, n_strata=S_RULE):
    """Совет 70, Н1, шаг 0 (без правды): страта «пустая», если каждое её значение d̂ есть и в соседней страте (страта не добавляет
    своего уровня трудности; при равных d̂ её отделяет от соседей только номер задачи)."""
    vals = [set(np.round(d[lab == s], 12).tolist()) for s in range(n_strata)]
    cnt = 0
    for s in range(n_strata):
        nb = (vals[s - 1] if s > 0 else set()) | (vals[s + 1] if s < n_strata - 1 else set())
        cnt += bool(vals[s]) and vals[s] <= nb
    return int(cnt)


def read_check_env(D, lab, d, seed, B, n_strata=S_RULE):
    """Совет 70, Н1 — проверка чтения П2 в одной среде (вердикт П2 не меняет).
    Шаг 0, без правды: пустых страт не больше EMPTY_MAX. Шаг 1, по правде теста: разность ошибки большинства толпы (ложное большинство
    ocdiv2.false_major на задаче) между верхней и нижней стратой d̂; M4 при 0,0025 — бутстреп задач внутри каждой из двух страт."""
    n_empty = empty_strata(d, lab, n_strata)
    fm = W.false_major(D).astype(float)
    top, bot = np.nonzero(lab == n_strata - 1)[0], np.nonzero(lab == 0)[0]
    diff = float(fm[top].mean() - fm[bot].mean())
    g = np.random.default_rng(seed)
    bt = np.array([fm[g.choice(top, len(top))].mean() - fm[g.choice(bot, len(bot))].mean() for _ in range(B)])
    iv, sd = P.m4(diff, bt, LEVEL)
    ok0 = n_empty <= EMPTY_MAX
    return dict(n_empty=n_empty, step0=bool(ok0), diff=diff, ci=iv, sd=sd, step1=bool(ok0 and iv[0] > 0), fm_top=float(fm[top].mean()),
                fm_bottom=float(fm[bot].mean()), n_top=int(len(top)), n_bottom=int(len(bot)))


def read_verdict(checks, n_valid):
    """Н1: чтение П2 «сверх трудности, видимой во входе» — если шаг 1 пройден хотя бы в 4 годных средах; при n_годных < 4 — П2
    неинформативно. Правда теста определяет только чтение, вердикт П2 не меняет."""
    n_pass = int(sum(c['step1'] for c in checks.values()))
    ok = bool(n_valid >= READ_MIN_ENVS and n_pass >= READ_MIN_ENVS)
    return dict(n_valid=int(n_valid), n_pass=n_pass, informative=ok, reading=READ_INFORMATIVE if ok else READ_NONINF,
                by_env={n: dict(step0=c['step0'], step1=c['step1'], n_empty=c['n_empty'], diff=c['diff'], ci=c['ci']) for n, c in checks.items()})


def slope(y):
    x = np.arange(len(y), dtype=float)
    return float(np.polyfit(x, np.asarray(y, float), 1)[0])


def extra_token_cells(env, crowd, idx):
    """Прибор (ЗАЩИТА-ANSWER_LOGP): (строка, голова) числовых ответов толпы с n_tok больше числа цифр + 1 — цикл answer_logp мог
    засчитать в число служебные токены. Точность не читается."""
    rows_by = {h['model']: h['rows'] for h in env['heads']}
    out = []
    for k, nm in enumerate(crowd):
        for r_, j in enumerate(idx):
            x = rows_by[nm][j]
            if x['answer'] is not None and x.get('n_tok') is not None and x['n_tok'] > len(str(abs(int(x['answer'])))) + 1:
                out.append((r_, k))
    return out


# ───────────── одна среда
def env_t4(env, models, seeds, n_id_test, B, B_descr, K_point, K_boot, keep_boot=False):
    """Т4 при всех нулях на одной среде. seeds: cv, n0, n0_boot, nd, nd_boot, id, id_boot, ds, ds_boot, pairs."""
    st, info = W.prepare_id(env, seeds['cv'], n_id_test)
    keep = info['keep']
    names = [info['names'][k] for k in keep]
    crowd = [short(nm) for nm in names]
    rid = info['rid']
    out = dict(n_id=int(rid.sum()), n_ood=int((~rid).sum()), crowd=crowd, valid=bool(info['valid']), min_each=info.get('min_each'),
               method={short(k): v for k, v in info['method'].items()})
    if not info['valid']:
        return out
    idi, ood = info['idi'], info['ood']
    ans_k = [info['ans'][k] for k in keep]
    sums = [p['sum'] for p in env['problems']]
    D = W.dmat(ans_k, sums, list(ood))
    D_id = W.dmat(ans_k, sums, list(idi))
    probs = env['problems']
    strata_c = np.array([W.carries(probs[j]['a'], probs[j]['b']) for j in ood])
    X = np.array([feats(probs[j]['a'], probs[j]['b']) for j in ood])
    d = dhat(models, crowd, X)
    sm = {f'Nd{s}': strata_of(d, s) for s in sorted({S_RULE, *S_DESCR})}
    sm['переносы'] = strata_c
    sm['клетки c1×u'] = np.array([cell_of(probs[j]['a'], probs[j]['b']) for j in ood])
    t4, bF, bFs, hom = t4_block_ocdiv2(D, strata_c, seeds['n0'], seeds['n0_boot'], B, K_point, K_boot)
    t4d, bd = t4_stream(D, sm[f'Nd{S_RULE}'], seeds['nd'], seeds['nd_boot'], B, K_point, K_boot)
    t4i, bi = t4_stream(D_id, None, seeds['id'], seeds['id_boot'], B, K_point, K_boot)
    dpt, dbt = descr_stream(D, sm, seeds['ds'], seeds['ds_boot'], B_descr, K_point, K_boot)
    r = pair_excess(D, np.random.default_rng(seeds['pairs']), K_PAIRS)
    lab8 = sm[f'Nd{S_RULE}']
    err = (D != 0).mean(1)                                     # описательно (по правде): доля неверных голов толпы на задаче
    read = read_check_env(D, lab8, d, seeds['read'], B)        # совет 70, Н1: проверка чтения П2
    fm = W.false_major(D).astype(float)
    fm_s = [float(fm[lab8 == s].mean()) for s in range(S_RULE)]
    err_s = [float(err[lab8 == s].mean()) for s in range(S_RULE)]
    auc_h = [DS.auc(p_hat(models[nm], X), (D[:, k] != 0).astype(float)) for k, nm in enumerate(crowd) if 0 < (D[:, k] != 0).mean() < 1]
    sep = dict(auc_dhat_false_major=(DS.auc(d, fm) if 0 < fm.mean() < 1 else None), auc_heads_mean=(float(np.mean(auc_h)) if auc_h else None),
               slope_false_major=slope(fm_s), slope_crowd_err=slope(err_s), dhat_range=float(d.max() - d.min()), false_major_by_stratum=fm_s)
    cells = extra_token_cells(env, crowd, list(ood))
    fix = None
    if cells:                                                  # описательно: такие ответы — «без числа», вердикт — по основному счёту
        Df = D.copy()
        for r_, k in cells:
            Df[r_, k] = NC + k
        gf = np.random.default_rng(seeds['fix'])
        fix = dict(n_cells=len(cells), T4=W.f_stats(Df, gf, K_point)[2], T4d=W.f_stats(Df, gf, K_point, sm[f'Nd{S_RULE}'])[2])
    out.update(T4=t4, T4d=t4d, T4id=t4i, homoplasy=hom, descr={k: dict(point=float(v), sd=float(np.std(dbt[k], ddof=1))) for k, v in dpt.items()},
               dhat=dict(min=float(d.min()), max=float(d.max()), mean=float(d.mean()),
                         by_stratum=[dict(dhat=float(d[lab8 == s].mean()), crowd_err=float(err[lab8 == s].mean()), n=int((lab8 == s).sum()))
                                     for s in range(S_RULE)]),
               pairs=dict(crowd=crowd, r=[[float(x) for x in row] for row in r]),
               formula=t4_formula(models, crowd, X),
               oracle_ood=float(st['corr'][keep][:, ood].any(0).mean()),
               extra_tokens=dict(n_cells=len(cells), recount=fix), read=read, separation=sep,
               seeds=seeds)
    out['_r'] = r
    if keep_boot:
        out['_boot'] = {'T4': bF, 'T4 (страты по переносам)': bFs, 'T4d': bd, 'T4id': bi, **{f'descr {k}': v for k, v in dbt.items()}}
    return out


def seeds_of(o, test):
    if test:
        return dict(cv=W.SEED_CV2 + o, n0=W.SEED_NULL_TEST + o, n0_boot=W.SEED_NULL_BOOT_TEST + o, nd=SEED_ND + o, nd_boot=SEED_ND_BOOT + o,
                    id=SEED_ID + o, id_boot=SEED_ID_BOOT + o, ds=SEED_DS + o, ds_boot=SEED_DS_BOOT + o, pairs=SEED_PAIRS + o, fix=SEED_FIX + o,
                    read=SEED_READ + o)
    return dict(cv=W.SEED_CV2 + o, n0=SEED_P_N0 + o, n0_boot=SEED_P_N0_BOOT + o, nd=SEED_P_ND + o, nd_boot=SEED_P_ND_BOOT + o,
                id=SEED_P_ID + o, id_boot=SEED_P_ID_BOOT + o, ds=SEED_P_DS + o, ds_boot=SEED_P_DS_BOOT + o, pairs=SEED_P_PAIRS + o, fix=SEED_FIX + 50 + o,
                read=SEED_P_READ + o)


def _env_job(job):
    env, models, seeds, n_id_test, B, B_descr, K_point, K_boot, keep_boot = job
    return env_t4(env, models, seeds, n_id_test, B, B_descr, K_point, K_boot, keep_boot)


def pmap(jobs, workers):
    if workers <= 1:
        return [_env_job(j) for j in jobs]
    with cf.ProcessPoolExecutor(workers) as ex:
        return list(ex.map(_env_job, jobs))


# ───────────── правила, предохранитель, «общий», мощность
def mean_entry(points, boots, names, level):
    use = [n for n in names if np.isfinite(points[n])]
    if not use:
        return dict(delta=float('nan'), ci=[float('nan'), float('nan')], n_envs=0, verdict='не решено')
    pt = float(np.mean([points[n] for n in use]))
    stack = np.vstack([boots[n] for n in use])
    ok = np.all(np.isfinite(stack), axis=0)                 # как в OCDIV-02: повтор с NaN хоть в одной среде исключается целиком
    bt = stack[:, ok].mean(0)
    iv, sd = P.m4(pt, bt, level)
    return dict(delta=pt, ci=iv, boot_sd=sd, n_envs=len(use), n_boot_dropped=int((~ok).sum()), by_env={n: float(points[n]) for n in use},
                z_star=W.z_star2('pos', pt, sd), verdict=W.verdict2('pos', iv), level=level)


def rule_entry(points, boots, sds, names, nondeg):
    """Вердикт правила: M4 среднего; предохранитель — тот же вердикт в каждой выборке «без одной среды»; пометка «общий» — интервал
    при 0,0025 / 5 целиком > 0 хотя бы в GENERAL_MIN невырожденных по пилоту средах."""
    e = mean_entry(points, boots, names, LEVEL)
    v = e['verdict']
    loo = {}
    if len(e.get('by_env', {})) >= 2:
        for n0 in e['by_env']:
            sub = [n for n in e['by_env'] if n != n0]
            m = mean_entry(points, boots, sub, LEVEL)
            loo[n0] = dict(delta=m['delta'], ci=m['ci'], verdict=m['verdict'])
    holds = bool(loo) and all(x['verdict'] == v for x in loo.values())
    e['leave_one_env_out'] = dict(by_env=loo, holds=holds)
    e['verdict_rule'] = v if (v not in ('подтверждено', 'опровергнуто') or holds) else UG
    lo_env = {n: float(points[n] - Z_ENV * sds[n]) for n in e.get('by_env', {})}
    e['env_lower'] = lo_env
    e['n_env_positive'] = int(sum(lo_env[n] > 0 for n in lo_env if n in nondeg))
    e['mark'] = (('общий' if e['n_env_positive'] >= GENERAL_MIN else 'сосредоточенный') if e['verdict_rule'] == 'подтверждено' else None)
    return e


def power3(mu, tau, s, m=N_ENVS, n=200_000, seed=SEED_POWER3):
    """Мощность правила вида pos с предохранителем по интервалу и пометкой «общий»: точка среды ~ N(mu, tau² + s²); M4 среднего m сред —
    ± z·s/√m, выборки «без одной среды» — ± z·s/√(m − 1); интервал среды — ± Z_ENV·s."""
    g = np.random.default_rng(seed)
    x = g.normal(mu, np.sqrt(tau ** 2 + s ** 2), size=(n, m))
    mean = x.mean(1)
    loo = (x.sum(1, keepdims=True) - x) / (m - 1)
    h, h1 = Z * s / np.sqrt(m), Z * s / np.sqrt(m - 1)
    conf_plain = mean - h > 0
    conf = conf_plain & np.all(loo - h1 > 0, axis=1)
    refu = (mean + h < 0) & np.all(loo + h1 < 0, axis=1)
    gen = conf & ((x - Z_ENV * s > 0).sum(1) >= GENERAL_MIN)
    return dict(confirm_no_guard=float(conf_plain.mean()), confirm=float(conf.mean()), refute=float(refu.mean()), general=float(gen.mean()))


def power_entry(points, sds, scale):
    x, sp = np.asarray(points, float), np.asarray(sds, float)
    ok = np.isfinite(x) & np.isfinite(sp)
    x, sp = x[ok], sp[ok]
    if len(x) < 2:
        return None
    s_test = float(np.sqrt(np.mean(sp ** 2)) * scale)
    tau = float(np.sqrt(max(0.0, x.var(ddof=1) - np.mean(sp ** 2))))
    # совет 70 («можно»): τ — по пяти средам при p = 1; мощность и при τ из верхней границы 95 % интервала дисперсии точек (χ², n − 1)
    var_hi = (len(x) - 1) * x.var(ddof=1) / float(chi2.ppf(0.025, len(x) - 1))
    tau_hi = float(np.sqrt(max(0.0, var_hi - np.mean(sp ** 2))))
    return dict(n_envs=int(len(x)), mu=float(x.mean()), tau=tau, tau_hi=tau_hi, s_pilot_rms=float(np.sqrt(np.mean(sp ** 2))), s_test=s_test, scale=scale,
                power=power3(float(x.mean()), tau, s_test), power_tau_s=power3(float(x.mean()), s_test, s_test),
                power_tau_hi=power3(float(x.mean()), tau_hi, s_test))


def test_counts(X):
    e = D2.env_of(FAMILY, X, D2.PHASES[TEST_PHASE]['p'], D2.PHASES[TEST_PHASE]['n'], D2.PHASES[TEST_PHASE]['start'], D2.PHASES[TEST_PHASE]['prompt'])
    n_id = sum(p['range'] == 'ID' for p in e['problems'])
    return e, n_id, len(e['problems']) - n_id


def rep_jobs():
    """ДЕТЕРМИНИЗМ-НА-3: три задания из 35 (головы ocdiv.CROWD × среды теста, упорядоченно), зерно SEED_REP."""
    jobs = [(nm, e['name']) for nm in CROWD for e in D2.envs_ocdiv2(TEST_PHASE, (FAMILY,))]
    pick = np.random.default_rng(SEED_REP).choice(len(jobs), 3, replace=False)
    return [jobs[int(i)] for i in sorted(pick)]


def models_json(models):
    return {nm: [float(x) for x in w] for nm, w in sorted(models.items())}


# ───────────── пилот: проверка до бита, кросс-подгонка, мощность, Т4 из формул по задачам теста
def pilot(dst, mdir, B=1000, workers=1, ref=os.path.join(ROOT, 'gha_out/ocdiv2_sum_pilot2v2/pilot.json')):
    t0 = time.time()
    d, envs = S.load_new(mdir)
    assert all(e['meta']['family'] == FAMILY and int(e['meta']['p']) == D2.PHASES[PILOT_PHASE]['p'] for e in envs.values()), 'не пилот 2 «тысяч»'
    names = sorted(envs, key=lambda n: int(envs[n]['meta']['X']))
    res = dict(phase='pilot', hypothesis='4b8160ec', B=B, K_point=K_POINT, K_boot=K_BOOT, B_descr=min(B, B_DESCR), envs={}, check_ocdiv2={})
    refj = json.load(open(ref, encoding='utf-8')) if ref and os.path.exists(ref) else None
    jobs, metas = [], {}
    for name in names:
        env = envs[name]
        meta = env['meta']
        o = W.off_of(meta)
        n_id_test = W.test_id_count(FAMILY, meta['X'], TEST_PHASE)
        metas[name] = (o, n_id_test)
        models_cf = fit_models(envs, exclude=(name,))                    # кросс-подгонка: модели — по четырём другим средам
        jobs.append((env, models_cf, seeds_of(o, False), n_id_test, B, min(B, B_DESCR), K_POINT, K_BOOT, False))
        # проверка до бита: блок N0 с зёрнами и параметрами разбора пилота OCDIV-02 (B = 200, 200 и 5 перестановок)
        st, info = W.prepare_id(env, W.SEED_CV2 + o, n_id_test)
        if info['valid'] and refj:
            keep, ood = info['keep'], info['ood']
            D = W.dmat([info['ans'][k] for k in keep], [p['sum'] for p in env['problems']], list(ood))
            sc = np.array([W.carries(env['problems'][j]['a'], env['problems'][j]['b']) for j in ood])
            t4c, _, _, homc = t4_block_ocdiv2(D, sc, W.SEED_NULL + o, W.SEED_NULL_BOOT + o, 200, 200, 5)
            r0 = refj['envs'][name]
            diffs = {k: abs(t4c[k] - r0['T4'][k]) for k in ('F', 'F0', 'point', 'sd', 'F0_strata', 'point_strata', 'sd_strata')}
            diffs.update({f'H {k}': abs(homc[k] - r0['homoplasy'][k]) for k in ('H', 'H0')})
            res['check_ocdiv2'][name] = dict(max_abs_diff=float(max(diffs.values())), equal=bool(max(diffs.values()) == 0.0), diffs=diffs)
    outs = pmap(jobs, workers)
    rmaps = []
    for name, r in zip(names, outs):
        rr = r.pop('_r', None)
        if r['valid'] and rr is not None:
            rmaps.append((r['pairs']['crowd'], rr))
        r['meta'] = {k: envs[name]['meta'].get(k) for k in ('family', 'X', 'p', 'bound', 'max_new')}
        res['envs'][name] = r
        print(f"{name}: годна {r['valid']}, толпа {len(r['crowd'])}, {round(time.time() - t0)} с", flush=True)
    res['pairs'] = pairs_test(rmaps) if rmaps else None
    valid = [n for n in names if res['envs'][n]['valid']]
    res['read_pilot'] = read_verdict({n: res['envs'][n]['read'] for n in valid}, len(valid))   # совет 70, Н2: правило Н1 на пилоте (кросс-подгонка)
    # мощность: s пересчитывается на тест по числу задач вне диапазона (Т4, Т4ᵈ) или ID (Т4-ID)
    n_ood_p = np.mean([res['envs'][n]['n_ood'] for n in valid])
    n_id_p = np.mean([res['envs'][n]['n_id'] for n in valid])
    tc = {n: test_counts(int(envs[n]['meta']['X'])) for n in valid}
    n_ood_t = np.mean([tc[n][2] for n in valid])
    n_id_t = np.mean([tc[n][1] for n in valid])
    sc_ood, sc_id = float(np.sqrt(n_ood_p / n_ood_t)), float(np.sqrt(n_id_p / n_id_t))
    pw = {}
    for key, fld, scale in (('П1 Т4', 'T4', sc_ood), (f'П2 Т4ᵈ (S = {S_RULE})', 'T4d', sc_ood), ('П3 Т4-ID', 'T4id', sc_id)):
        pw[key] = power_entry([res['envs'][n][fld]['point'] for n in valid], [res['envs'][n][fld]['sd'] for n in valid], scale)
    res['power'] = pw
    res['scale'] = dict(ood=sc_ood, id=sc_id, n_ood_pilot=float(n_ood_p), n_ood_test=float(n_ood_t), n_id_pilot=float(n_id_p), n_id_test=float(n_id_t))
    p3 = pw['П3 Т4-ID']
    res['p3_rule'] = bool(p3 is not None and p3['power']['confirm'] >= P3_POWER_MIN)
    # модели на всех пяти средах пилота — для теста; Т4 из формул по задачам теста с толпой пилота той же X
    models_all = fit_models(envs)
    res['models'] = dict(features='c1, n9, u (10), v (10); свободный член без штрафа', lam=LAMBDA, weights=models_json(models_all))
    res['models']['auc_in_sample'] = {}
    for nm, (Xh, yh) in head_rows(envs).items():
        res['models']['auc_in_sample'][nm] = DS.auc(p_hat(models_all[nm], Xh), yh) if 0 < yh.mean() < 1 else None
    res['formula_test'] = {}
    for n in names:
        X_ = int(envs[n]['meta']['X'])
        e_t, _, _ = tc.get(n) or test_counts(X_)
        ood_t = [q for q in e_t['problems'] if q['range'] != 'ID']
        Xt = np.array([feats(q['a'], q['b']) for q in ood_t])
        crowd_p = res['envs'][n]['crowd'] if res['envs'][n]['valid'] else list(CROWD)
        res['formula_test'][e_t['name']] = t4_formula(models_all, crowd_p, Xt)
    res['rep_jobs'] = rep_jobs()
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('проверка до бита (N0 против разбора пилота OCDIV-02):', {n: v['equal'] for n, v in res['check_ocdiv2'].items()})
    for k, v in pw.items():
        if v:
            print(f"{k}: μ {v['mu']:+.4f} τ {v['tau']:.4f} s(тест) {v['s_test']:.4f} | подтверждено {v['power']['confirm']:.3f} "
                  f"(без предохранителя {v['power']['confirm_no_guard']:.3f}), «общий» {v['power']['general']:.3f}, опровергнуто {v['power']['refute']:.3f}")
    print('П3 — правило' if res['p3_rule'] else 'П3 — описательно (мощность < 0,2)')
    rp = res['read_pilot']
    print(f"Н1 на пилоте: шаг 1 пройден в {rp['n_pass']} из {rp['n_valid']} годных сред — {'проходит' if rp['informative'] else 'не проходит'}")
    return res


# ───────────── тест
def test(dst, mdir, pilot_mdir, pilot_res, B=10000, B_descr=B_DESCR, workers=1):
    assert P3_RULE is not None, 'константа PREREG P3_RULE не задана'
    t00 = time.time()
    _, penvs = S.load_new(pilot_mdir)
    models = fit_models(penvs)
    pr = json.load(open(pilot_res, encoding='utf-8'))
    ref_w = pr['models']['weights']
    if set(ref_w) != set(models) or any(max(abs(a - b) for a, b in zip(ref_w[nm], models[nm])) > 1e-9 for nm in models):
        raise SystemExit('СТОП: веса моделей голов не совпали с разбором пилота, закоммиченным до PREREG')
    d, envs = S.load_new(mdir)
    hm = {h['model']: h for h in d['heads']}
    names_c, dropped = V.effective_crowd(hm)
    res = dict(level=LEVEL, z=Z, z_env=Z_ENV, B=B, B_descr=B_descr, K_point=K_POINT, K_boot=K_BOOT, family=FAMILY, s_rule=S_RULE, p3_rule=P3_RULE,
               crowd=CROWD, crowd_effective=names_c, crowd_dropped=dropped, head_errors=d.get('head_errors', []), keys_checked=d.get('keys_checked'),
               models_checked=True, versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__), envs={})
    names = sorted(envs, key=lambda n: int(envs[n]['meta']['X']))
    jobs = []
    for name in names:
        env = envs[name]
        meta = env['meta']
        assert meta['family'] == FAMILY and int(meta['p']) == D2.PHASES[TEST_PHASE]['p'], f'среда {name} не из теста «тысяч»'
        env_c = dict(env, heads=[h for h in env['heads'] if h['model'] in names_c])
        n_id = sum(p['range'] == 'ID' for p in env['problems'])
        jobs.append((env_c, models, seeds_of(W.off_of(meta), True), n_id, B, B_descr, K_POINT, K_BOOT, True))
    outs = pmap(jobs, workers)
    boots, rmaps, valid = {}, [], []
    for name, r in zip(names, outs):
        r['meta'] = {k: envs[name]['meta'][k] for k in ('family', 'X', 'p', 'bound', 'max_new')}
        if r['valid']:
            valid.append(name)
            boots[name] = r.pop('_boot')
            rmaps.append((r['pairs']['crowd'], r.pop('_r')))
        res['envs'][name] = r
        print(f"{name}: ID {r['n_id']}, OOD {r['n_ood']}, толпа {len(r['crowd'])}, годна {r['valid']}, {round(time.time() - t00)} с", flush=True)
    m = len(valid)
    method_ok = bool(m >= MIN_VALID and len(names) == N_ENVS)
    res['method'] = dict(ok=method_ok, n_envs=len(names), n_valid=m, valid=valid)
    rules = {'П1': ('T4', 'T4'), 'П2': ('T4d', 'T4d'), 'П3': ('T4id', 'T4id')}
    for k, (fld, bk) in rules.items():
        pts = {n: res['envs'][n][fld]['point'] for n in valid}
        sds = {n: res['envs'][n][fld]['sd'] for n in valid}
        e = rule_entry(pts, {n: boots[n][bk] for n in valid}, sds, valid, set(NONDEG_ENVS)) if valid else dict(verdict_rule='не решено', mark=None)
        if not method_ok:
            e['verdict'], e['mark'] = P.U, None
        elif k == 'П3' and not P3_RULE:
            e['verdict'], e['mark'] = 'описательно (мощность по пилоту < 0,2; PREREG)', None
        else:
            e['verdict'] = e['verdict_rule']
        res[k] = e
    if method_ok:                                             # совет 70, Н1: чтение П2 — по правде теста, вердикт П2 не меняет
        res['П2']['reading'] = read_verdict({n: res['envs'][n]['read'] for n in valid}, m)
    if valid:                                                 # совет 70, Н3: описательно, задано заранее
        res['descr_T4 − T4-ID'] = mean_entry({n: res['envs'][n]['T4']['point'] - res['envs'][n]['T4id']['point'] for n in valid},
                                             {n: boots[n]['T4'] - boots[n]['T4id'] for n in valid}, valid, DESCR_LEVEL)
    dkeys = ['T4 (страты по переносам)'] + ([f'descr {x}' for x in res['envs'][valid[0]]['descr']] if valid else [])
    for key in (dkeys if valid else []):
        pts = {}
        for n in valid:
            ee = res['envs'][n]
            pts[n] = ee['T4']['point_strata'] if key == 'T4 (страты по переносам)' else ee['descr'][key[len('descr '):]]['point']
        res[f'descr_{key}'] = mean_entry(pts, {n: boots[n][key] for n in valid}, valid, DESCR_LEVEL)
    res['pairs'] = pairs_test(rmaps) if rmaps else None
    res['formula'] = {n: dict(**res['envs'][n]['formula'], T4_observed=res['envs'][n]['T4']['point'],
                              T4_minus_T4d=res['envs'][n]['T4']['point'] - res['envs'][n]['T4d']['point']) for n in valid}
    res['formula_pilot_prediction'] = pr.get('formula_test')
    res['homoplasy_mean'] = {k: float(np.mean([res['envs'][n]['homoplasy'][k] for n in valid])) for k in ('H', 'H0', 'diff')} if valid else None
    res['oracle_ood'] = {n: res['envs'][n]['oracle_ood'] for n in valid}
    res['nondeg_mismatch'] = [n for n in valid if res['envs'][n]['oracle_ood'] < NONDEG_ORACLE]
    res['repeat_check'] = W.repeat_check(os.path.join(ROOT, 'gha_out/ocdiv3_test_*/answers_*.json'), os.path.join(ROOT, 'gha_out/ocdiv3_rep_*/answers_*.json'))
    res['rep_jobs'] = rep_jobs()
    res['verdicts'] = {k: res[k]['verdict'] for k in rules}
    res['marks'] = {k: res[k].get('mark') for k in rules}
    res['verdict'] = '; '.join(f'{k}: {v}' + (f" ({res['marks'][k]})" if res['marks'][k] else '') for k, v in res['verdicts'].items())
    res['seconds'] = round(time.time() - t00, 1)
    json.dump(res, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('вердикт:', res['verdict'])
    if 'reading' in res.get('П2', {}):
        print('П2, чтение (Н1):', res['П2']['reading']['reading'], f"(шаг 1 — {res['П2']['reading']['n_pass']} из {res['П2']['reading']['n_valid']})")
    for k in rules:
        e = res[k]
        if 'ci' in e:
            print(f"{k}: Δ {e['delta']:+.4f} M4 [{e['ci'][0]:+.4f}; {e['ci'][1]:+.4f}] | предохранитель {e['leave_one_env_out']['holds']} | "
                  f"сред с интервалом > 0: {e['n_env_positive']}")
    print('годных сред', m, 'из', len(names), '| толпа', len(names_c), '| выбыли', dropped, '| время', res['seconds'], 'с')
    return res


def main():
    a = sys.argv[1:]
    opt = lambda k, dv: type(dv)(a[a.index(k) + 1]) if k in a else dv   # noqa: E731
    if a[0] == 'pilot':
        pilot(a[1], a[2], opt('--boot', 1000), opt('--workers', 1))
    elif a[0] == 'test':
        test(a[1], a[2], a[3], a[4], opt('--boot', 10000), opt('--boot-descr', B_DESCR), opt('--workers', 1))
    elif a[0] == 'rep_jobs':
        print(json.dumps(rep_jobs(), ensure_ascii=False))


if __name__ == '__main__':
    main()
