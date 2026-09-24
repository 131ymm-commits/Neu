"""LEV-001 calibration: exact analysis of the Schlogl-type birth-death chain.

Deterministic: xdot = k3 + k1*x^2 - k4*x - k2*x^3,  k2=1.
Base roots at (a,b,c)=(0.5,1.75,3.5) -> k1=a+b+c, k4=ab+ac+bc, k3=abc.
Sweep parameter: k3 (inflow). Find fold window [SN1, SN2] in k3,
then for candidate V compute exact pi, spectrum, MFPTs to pick regime.
NO empirical pipeline here - exact quantities only (allowed pre-prereg).
"""
import numpy as np
from numpy.polynomial import polynomial as P

k2 = 1.0
a, b, c = 0.5, 1.75, 3.5
k1 = a + b + c
k4 = a*b + a*c + b*c
print(f"k1={k1}, k4={k4}, base k3={a*b*c}")

# fold window in k3: cubic -x^3 + k1 x^2 - k4 x + k3 has double root
# f'(x) = -3x^2 + 2k1 x - k4 = 0 -> x_pm
disc = (2*k1)**2 - 4*3*k4
xm = (2*k1 - np.sqrt(disc)) / 6.0
xp = (2*k1 + np.sqrt(disc)) / 6.0
def fx(x, k3): return k3 + k1*x**2 - k4*x - k2*x**3
# folds: k3 such that f(x_pm)=0
SN_a = -(k1*xm**2 - k4*xm - xm**3)   # k3 at which f(xm)=0
SN_b = -(k1*xp**2 - k4*xp - xp**3)
SN1, SN2 = sorted([SN_a, SN_b])
print(f"x_-={xm:.4f} x_+={xp:.4f}  fold window k3 in [{SN1:.5f}, {SN2:.5f}], width W={SN2-SN1:.5f}")

def roots_at(k3):
    r = np.roots([-1.0, k1, -k4, k3])
    r = np.sort(r[np.isreal(r)].real)
    return r[r >= -1e-9]

for k3 in [0.5*SN1, SN1*1.001, SN1 + 0.3*(SN2-SN1), SN1 + 0.6*(SN2-SN1), SN2*0.999]:
    print(f"  k3={k3:.4f} roots={np.round(roots_at(k3),3)}")

# ---- exact chain quantities ----
def chain(V, k3, xmax=6.0):
    n = np.arange(0, int(np.ceil(V*xmax)) + 1)
    x = n / V
    Wp = V * (k3 + k1 * x**2)            # birth
    Wm = V * (k4 * x + k2 * x**3)        # death (Wm[0]=0)
    Wp = Wp.copy(); Wm = Wm.copy()
    Wp[-1] = 0.0                          # reflecting cap
    return n, Wp, Wm

def stationary(Wp, Wm):
    with np.errstate(divide='ignore'):
        lg = np.concatenate([[0.0], np.cumsum(np.log(Wp[:-1]) - np.log(Wm[1:]))])
    lg -= lg.max()
    pi = np.exp(lg); pi /= pi.sum()
    return pi

def spectrum_ct(Wp, Wm, pi, k=4):
    # symmetrized generator eigenvalues (continuous time), exact, dense
    N = len(Wp)
    Q = np.zeros((N, N))
    idx = np.arange(N)
    Q[idx[:-1], idx[:-1]+1] = Wp[:-1]
    Q[idx[1:], idx[1:]-1] = Wm[1:]
    Q[idx, idx] = -(Wp + Wm)
    D = np.sqrt(pi)
    S = (Q * D[None, :] / D[:, None])
    ev = np.linalg.eigvalsh((S + S.T) / 2)
    ev = np.sort(ev)[::-1]
    rates = -ev[1:k+1]                    # relaxation rates (positive)
    return rates                          # t_i = 1/rates

def mfpt_up(Wp, Wm, pi, n_from, n_to):
    # mean first passage from n_from (< n_to) to n_to, birth-death standard sum
    # T = sum_{j=n_from}^{n_to-1} (1/(Wp_j pi_j)) * sum_{i<=j} pi_i
    cs = np.cumsum(pi)
    j = np.arange(n_from, n_to)
    return np.sum(cs[j] / (Wp[j] * pi[j]))

def mfpt_down(Wp, Wm, pi, n_from, n_to):
    # from n_from (> n_to) down to n_to
    cs_rev = np.cumsum(pi[::-1])[::-1]    # sum_{i>=j} pi_i
    j = np.arange(n_to + 1, n_from + 1)
    return np.sum(cs_rev[j] / (Wm[j] * pi[j]))

W = SN2 - SN1
grid_frac = [0.05, 0.15, 0.30, 0.45, 0.60, 0.80]
for V in [15, 20, 30, 40]:
    print(f"\n=== V={V} ===")
    for fr in grid_frac:
        k3 = SN1 + fr * W
        r = roots_at(k3)
        n, Wp, Wm = chain(V, k3)
        pi = stationary(Wp, Wm)
        rates = spectrum_ct(Wp, Wm, pi)
        t2, t3 = 1/rates[0], 1/rates[1]
        if len(r) == 3:
            nl, nm, nh = [int(round(V*v)) for v in r]
            T_lh = mfpt_up(Wp, Wm, pi, nl, nh)
            T_hl = mfpt_down(Wp, Wm, pi, nh, nl)
        else:
            T_lh = T_hl = np.nan
        # exact bimodality of pi
        from scipy.signal import find_peaks
        pk, _ = find_peaks(pi, prominence=0.05*pi.max())
        print(f" fr={fr:.2f} k3={k3:.4f} t2={t2:9.1f} t3={t3:7.2f} R={t2/t3:8.1f} "
              f"T_lh={T_lh:10.1f} T_hl={T_hl:9.1f} peaks={len(pk)} piHigh={pi[int(V*2.5):].sum():.3f}")
