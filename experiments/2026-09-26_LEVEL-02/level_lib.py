# LEVEL-02: прибор «Грамматики переходов» (архив, UNIFIED-THEORY §2, SPEC-01/ZETA-01) для системы голов.
# Состояние группы — счёты (n_A, n_B, n_C) из N голов; MSM по траектории; реньевски-нормированные лог-зазоры → ζ.
import numpy as np, itertools
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM, BayesianMSM


def states(N, K=3):
    S = [s for s in itertools.product(range(N + 1), repeat=K) if sum(s) == N]
    return {s: i for i, s in enumerate(S)}


def spacing_stats(ts, tau):  # как в archive/.../code/zeta01_lib.py
    r = ts[ts > tau]
    if len(r) < 4: return None
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = k * s
    return dict(p1=float(np.exp(-z[0] / z[1:].mean())), z1_rest=float(z[0] / z[1:].mean()), m=len(s), z=[float(v) for v in z[:6]])


def zeta_of(lab, tau=1, ns=200, nts=10):
    c = TransitionCountEstimator(lagtime=tau, count_mode='effective').fit_fetch(np.asarray(lab, int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    nts = min(nts, c.n_states - 1)
    ts = np.sort(msm.timescales(nts))[::-1]; ml = spacing_stats(ts, tau)
    post = BayesianMSM(n_samples=ns, reversible=True).fit(msm).fetch_model(); zr, ps, ms = [], [], []
    for mm in post.samples:
        st = spacing_stats(np.sort(mm.timescales(nts))[::-1], tau)
        if st is None: ms.append(0); continue
        zr.append(st['z1_rest']); ps.append(st['p1']); ms.append(st['m'])
    unresolved = np.mean(np.array(ms) < 3) > 0.5; PL = float(np.mean(np.array(ps) <= 0.05)) if ps else 0.0
    dec = 'отказ:не разрешён' if unresolved else ('уровень' if PL >= 0.95 else ('нет' if PL <= 0.05 else 'отказ'))
    return dict(n=len(lab), n_states=int(c.n_states), its=[round(float(x), 2) for x in ts[:5]], zeta_ml=(ml['z1_rest'] if ml else None),
                zeta_median=(float(np.median(zr)) if zr else None), zeta_q=([float(x) for x in np.quantile(zr, [.05, .95])] if zr else None), PL=PL, dec=dec)


def recurrence(cons):
    """D3: уровень (рекуррентен) или эпоха. cons — метка консенсуса по шагам (None — нет большинства ≥ N−1)."""
    seq = [c for c in cons if c is not None]; switches = sum(a != b for a, b in zip(seq, seq[1:]))
    return dict(consensus_share=len(seq) / len(cons), switches=switches, distinct=len(set(seq)))


def simulate(N=5, T=400, eps=0.15, coupled=True, seed=0, K=2):
    """Калибровка: шумная модель голосования (асинхронно). coupled: голова берёт выбор случайного соседа, иначе — свой прежний; eps — частная подсказка (случайный вариант)."""
    rng = np.random.default_rng(seed); x = rng.integers(0, K, N); S = states(N, K); lab, cons = [], []
    for t in range(T):
        i = rng.integers(N)
        if rng.random() < eps: x[i] = rng.integers(K)
        elif coupled: x[i] = x[rng.choice([j for j in range(N) if j != i])]
        cnt = tuple(int((x == k).sum()) for k in range(K)); lab.append(S[cnt]); m = max(cnt); cons.append(cnt.index(m) if m >= N - 1 else None)
    return lab, cons
