"""LEV-001 calibration v2 — EMBEDDED (jump) chain, exact quantities only.

Model (frozen here, pre-prereg): discrete-time birth-death jump chain on
n in {0..N}, x=n/V, from Schlogl rates
  W+(x) = k3 + k1 x^2 ; W-(x) = k4 x + k2 x^3   (k2=1, k1=5.75, k4=8.75)
  p_up(n) = W+/(W+ + W-), p_down = 1 - p_up ; reflecting at 0 and N (x_max=5).
Clock = number of jump events. All exact & empirical statements in this clock.
Sweep k3. Deterministic folds: SN1=1.37154 (birth of high branch), SN2=4.00578.
"""
import numpy as np
from scipy.linalg import eigh_tridiagonal
from scipy.signal import find_peaks

k2, k1, k4 = 1.0, 5.75, 8.75
SN1, SN2 = 1.37154, 4.00578
W = SN2 - SN1

def build(V, k3, xmax=5.0):
    N = int(np.ceil(V * xmax))
    n = np.arange(N + 1)
    x = n / V
    Wp = k3 + k1 * x**2
    Wm = k4 * x + k2 * x**3
    pu = Wp / (Wp + Wm)
    pd = 1.0 - pu
    pu[-1] = 0.0; pd[-1] = 1.0     # reflect top
    pd[0] = 0.0; pu[0] = 1.0       # reflect bottom (Wm(0)=0 anyway)
    return n, pu, pd

def stationary_log(pu, pd):
    lg = np.concatenate([[0.0], np.cumsum(np.log(pu[:-1]) - np.log(pd[1:]))])
    lg -= lg.max()
    pi = np.exp(lg); pi /= pi.sum()
    return pi, lg

def spectrum_events(pu, pd, k=4):
    d = np.zeros(len(pu))                       # jump chain: no self loops
    off = np.sqrt(pu[:-1] * pd[1:])
    ev = eigh_tridiagonal(d, off, eigvals_only=True)
    ev = np.sort(ev)[::-1]                      # ev[0]=1 (as eigenvalue of P; here d=0 so ev of the off-diag matrix)
    return ev

# NOTE: with zero diagonal the tridiagonal matrix IS P symmetrized; its top
# eigenvalue should be 1.0. Timescales: t_i = -1/ln(ev_i) for ev_i in (0,1).
# Jump chains are periodic-ish (bipartite when no self-loops!) -> ev_min = -1.
# To avoid bipartite parity artifacts use LAZY chain: P' = (I+P)/2 exactly.
def spectrum_lazy(pu, pd, k=5):
    d = np.full(len(pu), 0.5)
    off = 0.5 * np.sqrt(pu[:-1] * pd[1:])
    ev = eigh_tridiagonal(d, off, eigvals_only=True)
    return np.sort(ev)[::-1]

def mfpt_up(pu, pd, pi, nf, nt):
    cs = np.cumsum(pi)
    j = np.arange(nf, nt)
    return np.sum(cs[j] / (pu[j] * pi[j]))

def mfpt_down(pu, pd, pi, nf, nt):
    csr = np.cumsum(pi[::-1])[::-1]
    j = np.arange(nt + 1, nf + 1)
    return np.sum(csr[j] / (pd[j] * pi[j]))

def mfpt_direct(pu, pd, target, N):
    # linear solve check: E[T] from each state to absorbing target
    idx = [i for i in range(N + 1) if i != target]
    A = np.zeros((len(idx), len(idx))); bvec = np.ones(len(idx))
    pos = {s: i for i, s in enumerate(idx)}
    for s in idx:
        A[pos[s], pos[s]] = 1.0
        for s2, p in ((s + 1, pu[s]), (s - 1, pd[s])):
            if 0 <= s2 <= N and p > 0 and s2 != target:
                A[pos[s], pos[s2]] -= p
    T = np.linalg.solve(A, bvec)
    return {s: T[pos[s]] for s in idx}

def roots_at(k3):
    r = np.roots([-1.0, k1, -k4, k3])
    r = np.sort(r[np.isreal(r)].real)
    return r[r >= -1e-9]

# --- verify MFPT formulas on a small case ---
V = 8
n, pu, pd = build(V, 2.5)
pi, _ = stationary_log(pu, pd)
r = roots_at(2.5); nl, nh = int(round(V*r[0])), int(round(V*r[2]))
Td = mfpt_direct(pu, pd, nh, len(n)-1)[nl]
Tf = mfpt_up(pu, pd, pi, nl, nh)
print(f"verify MFPT: direct={Td:.2f} formula={Tf:.2f} ratio={Td/Tf:.4f}")

# --- main table ---
V = 20
print(f"\nV={V}, lazy-chain spectrum (events clock; lazy => real times x2)")
print("fr    k3      t2_ev      t3_ev     R_ex   T_lh_ev     T_hl_ev    piHi    peaks")
for fr in [-0.08, 0.02, 0.08, 0.15, 0.22, 0.30, 0.38, 0.45, 0.52, 0.60, 0.70, 0.80]:
    k3 = SN1 + fr * W
    n, pu, pd = build(V, k3)
    pi, lg = stationary_log(pu, pd)
    ev = spectrum_lazy(pu, pd)
    t = -1.0 / np.log(np.clip(ev[1:4], 1e-12, 1 - 1e-15))
    r = roots_at(k3)
    if len(r) == 3:
        nl, nm, nh = [int(round(V * v)) for v in r]
        Tlh = mfpt_up(pu, pd, pi, nl, nh) * 2   # lazy factor: 2 lazy steps per event...
        Thl = mfpt_down(pu, pd, pi, nh, nl) * 2
        # NOTE: MFPT formulas above use the JUMP chain pi/pu (not lazy); factor 2 NOT correct there.
        Tlh, Thl = Tlh / 2, Thl / 2             # keep pure jump-chain MFPT (events)
    else:
        Tlh = Thl = np.nan
    piHi = pi[int(V * 2.5):].sum()
    pk, _ = find_peaks(np.convolve(pi, np.ones(3)/3, mode='same'), prominence=0.05 * pi.max())
    print(f"{fr:5.2f} {k3:6.3f} {t[0]:10.1f} {t[1]:8.1f} {t[0]/t[1]:8.2f} "
          f"{Tlh:11.1f} {Thl:10.1f} {piHi:8.4f} {len(pk)}")
