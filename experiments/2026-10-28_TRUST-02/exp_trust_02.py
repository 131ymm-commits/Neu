#!/usr/bin/env python3
"""TRUST-02 — повтор TRUST-01 на другом мире, источник с интересом, который пользуется доверием к себе (Гудхарт),
и проверка механизма турнирной самоуверенности (малая выборка).

Агент, выплаты, отбор и оценка — как в TRUST-01 (`../2026-10-28_TRUST-01/exp_trust_01.py`; log_true, logistic_ml,
metrics, _ece импортируются без изменений). Мир обобщён (класс World): база π, независимые источники с надёжностью r,
пересказы (k, c): с вероятностью c повторяют источник k, иначе — независимый источник той же надёжности; и, по желанию,
источник с интересом (j, b): при W = 0 вместо верного «−1» говорит «+1» с вероятностью b, при W = 1 честен.
При мире A класс воспроизводит TRUST-01 побитно (проверка — `python3 exp_trust_02.py --check`).

Миры:
  A — мир TRUST-01: π = 0,3; r = 0,55 / 0,65 / 0,75 / 0,85 / 0,92; пересказ источника 0,75 с c = 0,8;
  B — новый мир (повтор): π = 0,1; r = 0,6 / 0,7 / 0,8 / 0,9; пересказ 0,7 с c = 0,5 и пересказ 0,9 с c = 0,5;
  G — мир A, но источник 0,85 — с интересом: врёт в пользу W = 1 с вероятностью b_t = B_MAX · clip(w̄_G / W_REF, 0, 1),
      где w̄_G — средний вес популяции на нём (репутация), W_REF = logit 0,85 — вес честного источника. Чем больше ему
      верят, тем больше он врёт. Ответ источника — на среднее популяции перед каждым поколением.
Руки: KELLY_A, CONTEST_A, CONTEST400_A (усечение при 400 эпизодах за жизнь), KELLY_G, KELLY_B, INDEP_B, KLUCK_B;
после проверки по трём линзам — KELLY6_A (контроль силы отбора) и KELLY_GFIX (мир G с постоянной долей лжи b*).
Оценка — точным перебором 2 × 64 состояний мира (основная) и на 200 000 эпизодах (второй способ).

Запуск: python3 exp_trust_02.py [--check | --pilot | --dry]. Результаты: results_trust_02.json. PREREG: PREREG-TRUST-02.md.
"""
import itertools
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '2026-10-28_TRUST-01'))
import exp_trust_01 as T1  # noqa: E402  (код TRUST-01 без изменений)

N_POP, N_PAR, G, SIG, WINDOW = T1.N_POP, T1.N_PAR, T1.G, T1.SIG, T1.WINDOW   # 400, 100, 1500, 0,04, 300
SHIFT = 0.10
B_MAX = 0.6
SEEDS = list(range(400, 410))
PILOT_SEEDS = [993, 994, 995, 996, 997]    # после проверки по трём линзам: 5 зёрен вместо одного (997 — первый пилот)
DRY_SEEDS = [980, 981]
lg = lambda p: float(np.log(p / (1 - p)))


class World:
    def __init__(self, pi, r, copies=(), adaptive=None):
        self.pi, self.r, self.copies, self.adaptive = pi, np.asarray(r, float), list(copies), adaptive
        assert len(self.r) + len(self.copies) == 6, 'агент TRUST-01: 6 сигналов'
        if adaptive is not None:
            assert adaptive[0] not in [k for k, _ in self.copies], 'пересказ источника с интересом не предусмотрен'

    def with_b(self, b):
        return World(self.pi, self.r, self.copies, None if self.adaptive is None else (self.adaptive[0], float(b)))

    def episodes(self, rng, n, shift=0.0):
        """Матрица [1, x_1..x_6] (n × 7) и W. Порядок вызовов rng в мире без источника с интересом — как в
        T1.episodes: W, ok (n × m), затем для каждого пересказа copy_ok, is_copy."""
        W = (rng.random(n) < self.pi).astype(int)
        s = 2 * W - 1
        r = self.r - shift
        ok = rng.random((n, len(r))) < r
        x = np.where(ok, 1, -1) * s[:, None]
        if self.adaptive is not None:
            j, b = self.adaptive
            lie = rng.random(n) < b
            x[:, j] = np.where((W == 0) & ok[:, j] & lie, 1, x[:, j])
        cols = [x]
        for k, c in self.copies:
            copy_ok = rng.random(n) < (self.r[k] - shift)
            indep = np.where(copy_ok, 1, -1) * s
            is_copy = rng.random(n) < c
            cols.append(np.where(is_copy, x[:, k], indep)[:, None])
        X = np.concatenate([np.ones((n, 1))] + cols, axis=1).astype(float)
        return X, W

    def probs(self, shift=0.0):
        """P(W = 0, узор), P(W = 1, узор) для всех 64 узоров (порядок — как T1.PATTERNS)."""
        m = len(self.r)
        pats = np.array(list(itertools.product([-1, 1], repeat=6)))
        r = self.r - shift
        out = []
        for Wv in (0, 1):
            s = 2 * Wv - 1
            pW = self.pi if Wv == 1 else 1 - self.pi
            p = np.where(pats[:, :m] == s, r, 1 - r)
            if self.adaptive is not None and Wv == 0:
                j, b = self.adaptive
                p_plus = (1 - r[j]) + r[j] * b
                p[:, j] = np.where(pats[:, j] == 1, p_plus, 1 - p_plus)
            px = p.prod(1)
            pc = np.ones(len(pats))
            for q, (k, c) in enumerate(self.copies):
                rk = self.r[k] - shift
                xk, xq = pats[:, k], pats[:, m + q]
                pc = pc * (c * (xq == xk) + (1 - c) * np.where(xq == s, rk, 1 - rk))
            out.append(pW * px * pc)
        P0, P1 = out
        assert abs(P0.sum() + P1.sum() - 1) < 1e-12
        return pats, P0, P1

    def exact_metrics(self, w, shift=0.0):
        """Метрики точным перебором (формулы — как T1.exact_metrics)."""
        pats, P0, P1 = self.probs(shift)
        X = np.concatenate([np.ones((64, 1)), pats], axis=1).astype(float)
        z = X @ np.asarray(w, float)
        p1 = 1 / (1 + np.exp(-z)); conf_pat = np.maximum(p1, 1 - p1); dec1 = z > 0
        mass = P0 + P1
        acc = float((P1 * dec1).sum() + (P0 * ~dec1).sum())
        conf = float((mass * conf_pat).sum())
        ll = float(-(P1 * T1.log_true(z, 1) + P0 * T1.log_true(z, 0)).sum())
        brier = float((P1 * (1 - p1) ** 2 + P0 * p1 ** 2).sum())
        hit = np.where(dec1, P1, P0) / mass
        return dict(acc=acc, conf=conf, self_dec=conf - acc, ignorance=1 - acc, deception=max(0.0, conf - acc),
                    logloss=ll, brier=brier, ece=T1._ece(conf_pat, hit, mass))

    def exact_weights(self):
        """Точные байесовские веса в закрытой форме; проверка: X·w = log P1/P0 на всех узорах."""
        m = len(self.r)
        w = np.zeros(7); w[0] = lg(self.pi)
        for i in range(m):
            w[1 + i] = lg(self.r[i])
        if self.adaptive is not None:
            j, b = self.adaptive
            s_, f_ = self.r[j], (1 - self.r[j]) + self.r[j] * b
            lp, lm = np.log(s_ / f_), np.log((1 - s_) / (1 - f_))
            w[1 + j] = (lp - lm) / 2; w[0] += (lp + lm) / 2
        for q, (k, c) in enumerate(self.copies):
            r = self.r[k]
            L = np.log(r * (c + (1 - c) * r) / ((1 - r) * (c + (1 - c) * (1 - r))))
            w[1 + k] = L / 2; w[1 + m + q] = L / 2
        pats, P0, P1 = self.probs()
        X = np.concatenate([np.ones((64, 1)), pats], axis=1).astype(float)
        assert np.allclose(X @ w, np.log(P1 / P0), atol=1e-10), 'точная апостериорная не линейна'
        return w

    def naive_weights(self):
        """Наивная формула: logit надёжности каждого сигнала, пересказ считается независимым; интерес не учтён."""
        m = len(self.r)
        w = np.concatenate([[lg(self.pi)], [lg(x) for x in self.r], [lg(self.r[k]) for k, _ in self.copies]])
        assert len(w) == 1 + m + len(self.copies)
        return w

    def pairs(self):
        """Индексы весов пар «источник + пересказ» (в векторе из 7)."""
        m = len(self.r)
        return [(1 + k, 1 + m + q) for q, (k, _) in enumerate(self.copies)]

    def identifiable(self, w):
        """Опознаваемые величины: w0, веса источников вне пар, суммы пар."""
        w = np.asarray(w, float)
        in_pair = {i for p in self.pairs() for i in p}
        single = [w[i] for i in range(1, 7) if i not in in_pair]
        return np.array([w[0]] + single + [w[a] + w[b] for a, b in self.pairs()])

    def scale(self, w):
        """Масштаб — как в PREREG-TRUST-01 §4: √(Σ весов вне пар² + Σ сумм пар²), без w0."""
        v = self.identifiable(w)[1:]
        return float(np.sqrt((v ** 2).sum()))


WA = World(0.3, [0.55, 0.65, 0.75, 0.85, 0.92], [(2, 0.8)])
WB = World(0.1, [0.6, 0.7, 0.8, 0.9], [(1, 0.5), (3, 0.5)])
G_IDX = 3                                    # источник 0,85 мира A — с интересом
W_REF = lg(0.85)
WG = World(0.3, [0.55, 0.65, 0.75, 0.85, 0.92], [(2, 0.8)], adaptive=(G_IDX, 0.0))
WORLDS = dict(A=WA, B=WB, G=WG)
NAMES = dict(A=['w0', 'r0.55', 'r0.65', 'r0.75', 'r0.85', 'r0.92', 'COPY(r0.75)'],
             B=['w0', 'r0.6', 'r0.7', 'r0.8', 'r0.9', 'COPY(r0.7)', 'COPY(r0.9)'],
             G=['w0', 'r0.55', 'r0.65', 'r0.75', 'G(r0.85)', 'r0.92', 'COPY(r0.75)'])
ARMS = {'KELLY_A': dict(world='A', payoff='KELLY', L=40, stream=0),
        'CONTEST_A': dict(world='A', payoff='CONTEST', L=40, stream=1),
        'CONTEST400_A': dict(world='A', payoff='CONTEST', L=400, stream=2),
        'KELLY_G': dict(world='G', payoff='KELLY', L=40, stream=3),
        'KELLY_B': dict(world='B', payoff='KELLY', L=40, stream=4),
        'INDEP_B': dict(world='B', payoff='INDEP', L=40, stream=5),
        'KLUCK_B': dict(world='B', payoff='KLUCK', L=40, stream=6),
        # добавлены после проверки по трём линзам (28.10): KELLY6_A — контроль силы отбора, как в T9 TRUST-01;
        # KELLY_GFIX — мир G с постоянной долей лжи b* (источник на репутацию не отвечает): контроль к KELLY_G
        'KELLY6_A': dict(world='A', payoff='KELLY6', L=40, stream=7),
        'KELLY_GFIX': dict(world='G', payoff='KELLY', L=40, stream=8, b_fixed=True)}


def b_of(wbar):
    """Ответ источника с интересом на репутацию: доля лжи b = B_MAX · clip(w̄_G / W_REF, 0, 1)."""
    return B_MAX * min(max(wbar / W_REF, 0.0), 1.0)


def fixed_point():
    """Неподвижная точка b* = b_of(w_G(b*)), где w_G(b) — точный байесовский вес при доле лжи b (бисекция)."""
    lo, hi = 0.0, B_MAX
    f = lambda b: b - b_of(WG.with_b(b).exact_weights()[1 + G_IDX])
    assert f(lo) < 0 < f(hi)
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    b = (lo + hi) / 2
    return b, WG.with_b(b).exact_weights()


B_STAR, _W_STAR = fixed_point()


def evolve2(seed, arm, gens=G, track_every=10, rng=None):
    """Эволюция, как T1.evolve, в обобщённом мире. rng можно передать (проверка равенства с TRUST-01)."""
    spec = ARMS[arm] if isinstance(arm, str) else arm
    world, payoff, L = WORLDS[spec['world']], spec['payoff'], spec['L']
    rng = rng if rng is not None else np.random.default_rng(seed * 100 + spec['stream'])
    pop = rng.normal(0, 0.01, (N_POP, 7))
    adaptive = world.adaptive is not None
    fixed = bool(spec.get('b_fixed'))
    respond = (lambda wm: B_STAR) if fixed else (lambda wm: b_of(wm[1 + G_IDX]))
    w_bayes0 = None if adaptive else world.exact_weights()
    ll_bayes0 = None if adaptive else world.exact_metrics(w_bayes0)['logloss']
    traj, neff, sdF = [], [], []
    for g in range(gens):
        b = respond(pop.mean(0)) if adaptive else 0.0
        wd = world.with_b(b)
        if payoff == 'INDEP':
            X, W = wd.episodes(rng, N_POP * L)
            Z = np.einsum('nlk,nk->nl', X.reshape(N_POP, L, 7), pop)
            logF = T1.log_true(Z, W.reshape(N_POP, L)).sum(1)
        else:
            X, W = wd.episodes(rng, L)
            Z = pop @ X.T
            if payoff == 'ACC':
                logF = ((Z > 0) == (W[None, :] == 1)).sum(1).astype(float)
            else:
                logF = T1.log_true(Z, W[None, :]).sum(1)
            if payoff == 'KLUCK':
                Xi, Wi = wd.episodes(rng, N_POP * L)
                zi = (Xi @ pop.mean(0)).reshape(N_POP, L)
                logF = logF + T1.log_true(zi, Wi.reshape(N_POP, L)).sum(1)
            if payoff == 'KELLY6':
                logF = 6.0 * logF
        sdF.append(float(logF.std()))
        if payoff == 'CONTEST':
            order = np.lexsort((rng.random(N_POP), -logF))
            parents = pop[order[:N_PAR]]
            pop = np.repeat(parents, N_POP // N_PAR, axis=0) + rng.normal(0, SIG, (N_POP, 7))
            neff.append(float(N_PAR))
        else:
            pr = np.exp(logF - logF.max()); pr /= pr.sum()
            neff.append(float(1 / (pr ** 2).sum()))
            idx = rng.choice(N_POP, size=N_POP, p=pr)
            pop = pop[idx] + rng.normal(0, SIG, (N_POP, 7))
        if g % track_every == 0 or g == gens - 1:
            wm = pop.mean(0)
            bn = respond(wm) if adaptive else 0.0               # мир, который встретит это поколение
            wb = world.with_b(bn)
            m = wb.exact_metrics(wm)
            llb = wb.exact_metrics(wb.exact_weights())['logloss'] if adaptive else ll_bayes0
            traj.append(dict(g=g, w=wm.round(4).tolist(), b=round(bn, 5), spread=float(pop.std(0).mean()),
                             acc=m['acc'], conf=m['conf'], self_dec=m['self_dec'], logloss=m['logloss'],
                             logloss_bayes=llb, ece=m['ece']))
    last = [t for t in traj if t['g'] >= gens - WINDOW]
    w_final = np.mean([t['w'] for t in last], 0)
    b_final = float(np.mean([t['b'] for t in last]))
    wf = world.with_b(b_final)
    trng = np.random.default_rng(seed + 90_000)
    Xt, Wt = wf.episodes(trng, 200_000)
    late = slice(gens - WINDOW, gens)
    return dict(seed=seed, arm=spec if not isinstance(arm, str) else arm, w_final=w_final.tolist(), n_snap=len(last),
                b_final=b_final, exact=wf.exact_metrics(w_final), test=T1.metrics(w_final, Xt, Wt),
                exact_shifted=None if adaptive else world.exact_metrics(w_final, SHIFT),
                self_dec_snap_mean=float(np.mean([t['self_dec'] for t in last])),
                excess_logloss_snap_mean=float(np.mean([t['logloss'] - t['logloss_bayes'] for t in last])),
                ece_snap_mean=float(np.mean([t['ece'] for t in last])), b_sd_window=float(np.std([t['b'] for t in last])),
                neff_late=float(np.median(neff[late])), sdF_late=float(np.median(sdF[late])), traj=traj)


def theory(seed=12345):
    out = {}
    bstar, wg = fixed_point()
    for key, world in (('A', WA), ('B', WB), ('G', WG.with_b(bstar))):
        rng = np.random.default_rng(seed)
        X, W = world.episodes(rng, 1_000_000)
        w_ml = T1.logistic_ml(X, W)
        w_ex = world.exact_weights()
        w_nv = world.naive_weights() if key != 'G' else WA.naive_weights()
        out[key] = dict(w_exact=w_ex.tolist(), w_ml=w_ml.tolist(), w_naive=w_nv.tolist(),
                        max_abs_ml_minus_exact=float(np.abs(w_ml - w_ex).max()),
                        exact_exact=world.exact_metrics(w_ex), exact_naive=world.exact_metrics(w_nv),
                        exact_ml=world.exact_metrics(w_ml), scale_exact=world.scale(w_ex),
                        identifiable_exact=world.identifiable(w_ex).tolist(),
                        identifiable_naive=world.identifiable(w_nv).tolist())
        if key != 'G':
            out[key]['exact_shifted_exact'] = world.exact_metrics(w_ex, SHIFT)
    out['G'].update(b_star=bstar, w_ref=W_REF, wG_star=float(wg[1 + G_IDX]), honest_A_weights=WA.exact_weights().tolist(),
                    # честная формула TRUST-01 в мире с ложью b*: что будет, если не учесть интерес источника
                    exact_honest_formula_at_bstar=WG.with_b(bstar).exact_metrics(WA.exact_weights()))
    return out


def check():
    """Мир A и evolve2 воспроизводят TRUST-01: вероятности, веса, метрики, эпизоды и траектории популяции."""
    pats, P0, P1 = WA.probs(); Q0, Q1 = T1.world_probs()
    assert np.array_equal(pats, T1.PATTERNS) and np.allclose(P0, Q0, atol=1e-15) and np.allclose(P1, Q1, atol=1e-15)
    for sh in (0.0, SHIFT):
        a, b = WA.probs(sh)[1:], T1.world_probs(sh)
        assert np.allclose(a[0], b[0], atol=1e-15) and np.allclose(a[1], b[1], atol=1e-15)
    assert np.allclose(WA.exact_weights(), T1.exact_weights(), atol=1e-12)
    rng = np.random.default_rng(1)
    for _ in range(20):
        w = rng.normal(0, 2, 7)
        e1, e2 = WA.exact_metrics(w), T1.exact_metrics(w)
        assert all(abs(e1[k] - e2[k]) < 1e-12 for k in e1), (e1, e2)
        e1, e2 = WA.exact_metrics(w, SHIFT), T1.exact_metrics(w, SHIFT)
        assert all(abs(e1[k] - e2[k]) < 1e-12 for k in e1)
    for sh in (0.0, SHIFT):
        X1, W1 = WA.episodes(np.random.default_rng(7), 5000, sh); X2, W2 = T1.episodes(np.random.default_rng(7), 5000, sh)
        assert np.array_equal(X1, X2) and np.array_equal(W1, W2)
    for payoff in ('KELLY', 'INDEP', 'KLUCK', 'CONTEST', 'ACC', 'KELLY6'):
        r1 = T1.evolve(123, payoff, gens=60)
        r2 = evolve2(123, dict(world='A', payoff=payoff, L=T1.L_EP, stream=-1), gens=60,
                     rng=np.random.default_rng(123 * 10 + T1.ARMS.index(payoff)))
        assert [t['w'] for t in r1['traj']] == [t['w'] for t in r2['traj']], payoff
        assert np.allclose(r1['w_final'], r2['w_final'], atol=1e-12), payoff
    # мир G при b = 0 — это мир A; при b > 0 точная апостериорная линейна (assert в exact_weights)
    assert np.allclose(WG.with_b(0.0).exact_weights(), WA.exact_weights(), atol=1e-12)
    for b in (0.1, 0.34, 0.6):
        WG.with_b(b).exact_weights()
    # эмпирическая частота «+1» источника G при W = 0 сходится к (1 − r) + r·b
    X, W = WG.with_b(0.4).episodes(np.random.default_rng(3), 400_000)
    emp = float((X[W == 0, 1 + G_IDX] == 1).mean()); want = 0.15 + 0.85 * 0.4
    assert abs(emp - want) < 0.005, (emp, want)
    print('проверка: мир A и evolve2 совпадают с TRUST-01 (вероятности, веса, метрики, эпизоды, траектории 6 выплат); '
          f'мир G линеен, частота лжи {emp:.4f} при ожидаемой {want:.4f}')


def run(seeds, outdir, arms=None):
    t0 = time.time()
    th = theory()
    arms = arms or list(ARMS)
    runs = [evolve2(s, a) for s in seeds for a in arms]
    json.dump(dict(names=NAMES, theory=th, runs=runs,
                   params=dict(N_POP=N_POP, N_PAR=N_PAR, G=G, SIG=SIG, WINDOW=WINDOW, SHIFT=SHIFT, B_MAX=B_MAX,
                               W_REF=W_REF, G_IDX=G_IDX, ARMS=ARMS, SEEDS=seeds,
                               WORLDS={k: dict(pi=v.pi, r=v.r.tolist(), copies=v.copies, adaptive=v.adaptive)
                                       for k, v in WORLDS.items()}),
                   seconds=time.time() - t0),
              open(os.path.join(outdir, 'results_trust_02.json'), 'w'))
    return th, runs, time.time() - t0


if __name__ == '__main__':
    if '--check' in sys.argv:
        check(); sys.exit(0)
    if '--pilot' in sys.argv:
        os.makedirs(os.path.join(HERE, 'pilot'), exist_ok=True)
        th, runs, sec = run(PILOT_SEEDS, os.path.join(HERE, 'pilot'))
        print(f'пилот: {sec:.0f} с')
        sys.exit(0)
    dry = '--dry' in sys.argv
    outdir = os.path.join(HERE, 'dry') if dry else HERE
    os.makedirs(outdir, exist_ok=True)
    th, runs, sec = run(DRY_SEEDS if dry else SEEDS, outdir)
    print(f'готово за {sec:.0f} с; анализ — analyze_trust_02.py')
