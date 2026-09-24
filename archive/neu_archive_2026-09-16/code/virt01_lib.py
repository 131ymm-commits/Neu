"""VIRT-01 — библиотека. (A) полубесконечная цепочка сильной связи с контактной ямой (антисвязанный уровень) в мнимом времени;
(B) Λ-система (рамановский переход через виртуальный уровень) — лиувиллиан, матрица переходов населённостей при лаге τ,
2-блочные лумпинги, ρ_L, числовой радиус (HS, бесследовое подпространство), память D(n), время жизни рождённого уровня.
Обозначения: H = −Σ(|n⟩⟨n+1| + h.c.) − V|0⟩⟨0|; связанное состояние E = −(V + 1/V) при V > 1, виртуальное при V < 1;
длина рассеяния a = −1/(1 − V). Λ: H = Δ|2⟩⟨2| + (Ω/2)(|1⟩⟨2| + |2⟩⟨3| + h.c.); распад |2⟩ → |1⟩, |3⟩ по γ/2; дефазировка
основного дублета γ_g через L = √(γ_g/2)(|1⟩⟨1| − |3⟩⟨3|). Эффективно: Ω_R = Ω²/2Δ, R_sc = γΩ²/4Δ², Γ₁ = R_sc, Γ₂ = R_sc + γ_g,
EP основного дублета при γ_g = 2Ω_R."""
import numpy as np
from scipy.linalg import eigh_tridiagonal, eig, expm
TOL = 1e-9

# ---------- (A) антисвязанный уровень ----------
def chain_corr(N, V, nmax, tau=1.0):
    """C(n) = ⟨0|e^{−nτ(H+2)}|0⟩ (сдвиг: дно зоны → 0), спектр H' = H + 2 и вес g = δ₀."""
    d = np.full(N, 2.0); d[0] -= V; e = -np.ones(N - 1)
    w, U = eigh_tridiagonal(d, e); a0 = U[0, :] ** 2  # спектральная мера δ₀
    n = np.arange(nmax + 1); C = (a0[None, :] * np.exp(-np.outer(n, w) * tau)).sum(1)
    return w, a0, C

def implied_energy(C, tau=1.0):
    """E(n) = −ln(C(n)/C(n−1))/τ, n ≥ 1 (в сдвинутых единицах: кромка = 0)."""
    return -np.log(C[1:] / C[:-1]) / tau

def crossover(C, tau=1.0):
    """ε(n) = E(n)·nτ: 1/2 (n ≪ a²) → 3/2 (n ≫ a²); n_c — первая n, где ε(n) ≥ 1 (линейная интерполяция)."""
    E = implied_energy(C, tau); n = np.arange(1, len(C)); eps = E * n * tau
    idx = np.where(eps >= 1.0)[0]
    if len(idx) == 0 or idx[0] == 0: return None, eps
    i = idx[0]; x0, x1 = eps[i - 1], eps[i]; nc = (n[i - 1] + (1 - x0) / (x1 - x0)) if x1 != x0 else n[i]
    return float(nc), eps

def memory(C):
    """D(n) = C(n)/C(0) − (C(1)/C(0))^n."""
    c = C / C[0]; n = np.arange(len(c)); return c - c[1] ** n

# ---------- (B) Λ-система ----------
def lindbladian(H, Ls):
    """Супероператор L на vec(ρ) (столбцовая векторизация): L = −i(I⊗H − Hᵀ⊗I) + Σ [L̄⊗L − ½ I⊗L†L − ½ (L†L)ᵀ⊗I]."""
    d = H.shape[0]; I = np.eye(d); Lsup = -1j * (np.kron(I, H) - np.kron(H.T, I))
    for L in Ls:
        LdL = L.conj().T @ L
        Lsup += np.kron(L.conj(), L) - 0.5 * np.kron(I, LdL) - 0.5 * np.kron(LdL.T, I)
    return Lsup

def lambda_system(Omega, Delta, gamma, gamma_g):
    H = np.zeros((3, 3), complex); H[1, 1] = Delta; H[0, 1] = H[1, 0] = Omega / 2; H[1, 2] = H[2, 1] = Omega / 2
    Ls = []
    L1 = np.zeros((3, 3), complex); L1[0, 1] = np.sqrt(gamma / 2); Ls.append(L1)
    L3 = np.zeros((3, 3), complex); L3[2, 1] = np.sqrt(gamma / 2); Ls.append(L3)
    if gamma_g > 0:
        Lg = np.zeros((3, 3), complex); Lg[0, 0] = np.sqrt(gamma_g / 2); Lg[2, 2] = -np.sqrt(gamma_g / 2); Ls.append(Lg)
    return lindbladian(H, Ls)

def two_level_control(Omega_R, Gamma1, Gamma2):
    """Контроль без виртуального уровня: H = (Ω_R/2)σ_x; прыжки σ± по Γ₁/2 (Γ₁ = R_sc), дефазировка так, что Γ₂ = R_sc + γ_g."""
    sx = np.array([[0, 1], [1, 0]], complex); sm = np.array([[0, 0], [1, 0]], complex); sp = sm.T.copy(); sz = np.diag([1.0, -1.0]).astype(complex)
    H = (Omega_R / 2) * sx; r = Gamma1 / 2; gz = Gamma2 - Gamma1 / 2  # коэффициент при σ_z: дефазировка 2·(gz/2)... подбираем так, чтобы Γ₂ = r + gz
    Ls = [np.sqrt(r) * sm, np.sqrt(r) * sp, np.sqrt(gz / 2) * sz]
    return lindbladian(H, Ls)

def steady_state(Lsup, d):
    w, V = eig(Lsup); k = int(np.argmin(np.abs(w))); rho = V[:, k].reshape(d, d, order='F'); rho = rho / np.trace(rho)
    return rho, w

def population_matrix(Lsup, d, tau):
    """P_τ(i→j) = ⟨j| e^{Lτ}[|i⟩⟨i|] |j⟩ — матрица переходов измеренных населённостей."""
    U = expm(Lsup * tau); P = np.zeros((d, d))
    for i in range(d):
        rho0 = np.zeros((d, d), complex); rho0[i, i] = 1.0; rt = (U @ rho0.reshape(-1, order='F')).reshape(d, d, order='F')
        P[i, :] = np.real(np.diag(rt))
    P = np.clip(P, 0, None); P /= P.sum(1, keepdims=True); return P, U

def stat_dist(P):
    w, V = eig(P.T); k = int(np.argmin(np.abs(w - 1))); pi = np.real(V[:, k]); pi = np.abs(pi) / np.abs(pi).sum(); return pi

def lumped_l2(P, pi, A):
    """λ₂ 2-блочного лумпинга по потокам: λ₂ = 1 − Φ(1/π_A + 1/π_B)."""
    A = np.array(A); B = np.array([i for i in range(len(pi)) if i not in A])
    F = pi[:, None] * P; flux = F[np.ix_(A, B)].sum(); piA = pi[A].sum(); piB = pi[B].sum()
    return float(1 - flux * (1 / piA + 1 / piB))

def rho_L(w, tau):
    """max |e^{λτ}| по ненулевым собственным значениям лиувиллиана."""
    nz = w[np.abs(w) > 1e-10]; return float(np.max(np.abs(np.exp(nz * tau)))), float(np.min(np.abs(nz.real)))

def numerical_radius_traceless(U, d, nth=180):
    """Числовой радиус e^{Lτ} на бесследовом подпространстве (HS-метрика)."""
    # ортонормированный базис бесследовых матриц (HS): комплемент к I/√d
    Id = np.eye(d).reshape(-1, order='F') / np.sqrt(d); Q = np.linalg.qr(np.column_stack([Id, np.random.RandomState(0).randn(d * d, d * d - 1)]))[0][:, 1:]
    M = Q.conj().T @ U @ Q; best = 0.0
    for th in np.linspace(0, np.pi, nth, endpoint=False):
        Hm = (np.exp(1j * th) * M + (np.exp(1j * th) * M).conj().T) / 2; best = max(best, float(np.linalg.eigvalsh(Hm)[-1]))
    return best

def description_analysis(Lsup, d, tau, blocks, nmax=None, rel_tol=1e-6, floor=1e-6):
    """Для описания (блок A против остального): C_n = Cov(1_A(0), 1_A(nτ))/Var(1_A) под совместным распределением ПРОЕКТИВНЫХ
    измерений (первое — на стационарном состоянии, π = diag ρ_ss); при диагональном ρ_ss это λ₂ 2-блочного лумпинга.
    ρ = ρ_L(τ); рождение при n = 1: C_1 > ρ(1 + rel_tol); жизнь n_life = min{n: C_n ≤ ρ^n(1 + rel_tol)} − 1 на n ≤ n_max,
    где ρ^{n_max} = floor (сравнение не уходит в шум); если выхода нет — permanent = True, q_end = C_{n_max}/ρ^{n_max}.
    Память D(n) = C_n − C_1^n."""
    rho_ss, w = steady_state(Lsup, d); pi = np.real(np.diag(rho_ss)); pi = np.clip(pi, 0, None); pi /= pi.sum()
    rho, gap = rho_L(w, tau); t_rho = float(-1 / np.log(rho))
    n_max = int(np.ceil(np.log(floor) / np.log(rho))) if nmax is None else nmax
    out = dict(tau=tau, rho=rho, gap=gap, t_rho=t_rho, pi=pi.tolist(), n_max=n_max, blocks={})
    U1 = expm(Lsup * tau); Un = np.eye(d * d, dtype=complex); Cs = {str(A): [] for A in blocks}
    for n in range(1, n_max + 1):
        Un = Un @ U1; P = np.zeros((d, d))
        for i in range(d):
            rho0 = np.zeros((d, d), complex); rho0[i, i] = 1.0; rt = (Un @ rho0.reshape(-1, order='F')).reshape(d, d, order='F'); P[i, :] = np.real(np.diag(rt))
        for A in blocks:
            A_ = np.array(A); pA = pi[A_].sum(); joint = (pi[A_, None] * P[A_][:, A_]).sum(); marg = (pi[:, None] * P[:, A_]).sum()
            Cs[str(A)].append((joint - pA * marg) / (pA * (1 - pA)))
    for A in blocks:
        C = np.array(Cs[str(A)]); n = np.arange(1, n_max + 1); rn = rho ** n; born = bool(C[0] > rho * (1 + rel_tol))
        above = C > rn * (1 + rel_tol); exit_idx = np.where(~above)[0]
        permanent = bool(len(exit_idx) == 0); n_life = int(exit_idx[0]) if not permanent else n_max
        D = C - C[0] ** n; R = float(np.log(rho) / np.log(C[0])) if 0 < C[0] < 1 else None
        first_neg = int(np.argmax(D < -1e-12) + 1) if (D < -1e-12).any() else None
        out['blocks'][str(A)] = dict(C1=float(C[0]), born=born, R=R, n_life=n_life, life_over_trho=float(n_life / t_rho), permanent=permanent,
                                     q_end=float(C[-1] / rn[-1]), q_max=float((C / rn).max()), D2=float(D[1]), D_first_neg=first_neg, C_head=C[:30].tolist())
    return out
