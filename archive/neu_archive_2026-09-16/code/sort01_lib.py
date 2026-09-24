"""SORT-01 — библиотека: сорт рождённого уровня по постоянству (q_n = C_n/ρⁿ) против сорта по знаку памяти (LIFE-02) на точных
лифтированных цепях (LIFT-01 вариант A; lifted_local LIFE-02 с локальным шумом s). Всё без выборки: C_n = ⟨Pⁿ g, g⟩_π."""
import numpy as np, sys
sys.path.insert(0, '/home/claude')
from cog01_lib import stationary, sym_form, restrict
from life02_lib import lifted_local
TOL = 1e-9

def leading(P, pi):
    """ρ, аргумент θ ведущего нетривиального собственного значения (по полной симметризованной форме A = D^{1/2} P D^{-1/2};
    тривиальная мода 1 исключена), вещественно ли; возвращает разложение для биортогональных весов."""
    A = sym_form(P, pi); ev, R = np.linalg.eig(A); triv = int(np.argmin(np.abs(ev - 1))); mask = np.ones(len(ev), bool); mask[triv] = False
    idx = np.where(mask)[0]; rho = float(np.max(np.abs(ev[idx])))
    top = idx[np.abs(ev[idx]) >= rho * (1 - 1e-9)]  # все с максимальным модулем (плоский модуль комплексной ветви!)
    k = int(top[np.argmax(ev[top].real)]); lam = ev[k]  # «положительное ведущее»: наибольшая вещественная часть среди них
    return rho, float(abs(np.angle(lam))), bool(abs(lam.imag) < 1e-9), A, ev, R, k

def mid_indicator(L, pi):
    xs = np.repeat(np.arange(1, L + 1), 2); ind = (xs <= L // 2).astype(float); h = ind - pi @ ind; h /= np.sqrt(np.sum(pi * h * h)); return h

def corr_seq(P, pi, h, nmax):
    C = np.empty(nmax); v = h.copy()
    for n in range(1, nmax + 1):
        v = P @ v; C[n - 1] = float(np.sum(pi * v * h))
    return C

def analyze(P, L, rel_tol=1e-6, floor=1e-6, nmax_cap=20000):
    pi = stationary(P); rho, theta, real_lead, A0, ev, R, k = leading(P, pi); h = mid_indicator(L, pi)
    t_rho = -1 / np.log(rho); n_max = min(int(np.ceil(np.log(floor) / np.log(rho))), nmax_cap)
    C = corr_seq(P, pi, h, n_max); n = np.arange(1, n_max + 1); rn = rho ** n
    born = bool(C[0] > rho + TOL); above = C > rn * (1 + rel_tol); ex = np.where(~above)[0]
    permanent = bool(len(ex) == 0); n_life = int(ex[0]) if not permanent else n_max
    q = C / rn; D = C - C[0] ** n; d2 = float(D[1] / C[0] ** 2)
    neg = np.where(D < -1e-12)[0]; nstar = int(neg[0] + 1) if len(neg) else None; tau_life02 = (nstar / t_rho) if nstar else None
    # возвраты: число отрезков n, где q > 1 после первого выхода
    ret = 0
    if not permanent:
        s = above.astype(int); ret = int(np.sum((s[1:] == 1) & (s[:-1] == 0)))
    # биортогональный вес разреза на ведущем собственном значении (в π-метрике A₀ симметризована: используем левый/правый векторы A₀)
    Lv = np.linalg.inv(R); g0 = np.sqrt(pi) * h  # C_n = g0ᵀ Aⁿ g0, g0 ⟂ √π, |g0| = 1
    ak = (R.T @ g0) * (Lv @ g0)  # биортогональные веса, Σ a_k = 1 (проверяется)
    a_sum = float(np.real(ak.sum())); a1 = float(np.real(ak[k])) if real_lead else float(2 * np.real(ak[k]))  # у комплексной пары — вклад пары
    C_rec_err = float(np.max(np.abs(np.real(ak @ (ev[:, None] ** np.arange(1, 6)[None, :])) - C[:5])))
    period = (2 * np.pi / theta) if theta > 1e-9 else None
    late = None
    if not born:
        w_ = np.where(above)[0]; late = int(w_[0] + 1) if len(w_) else None
    return dict(rho=rho, theta=theta, real_lead=real_lead, t_rho=float(t_rho), n_max=n_max, C1=float(C[0]), born=born, n_life=n_life, permanent=permanent,
                q_end=float(q[-1]), q_max=float(q.max()), q_min_after_birth=float(q.min()), returns=ret, d2=d2, nstar=nstar, tau_life02=tau_life02,
                period_pred=period, half_period=(np.pi / theta if theta > 1e-9 else None), a1=a1, a_sum=a_sum, C_rec_err=C_rec_err, late_birth_n=late, q_head=q[:12].tolist())
