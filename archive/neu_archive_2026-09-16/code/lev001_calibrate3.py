"""LEV-001 calibration v3 — REAL-TIME clock (uniformized), exact quantities.
Freezes: V, cap, Lambda, grid, lags, thresholds -> go into PREREG.
"""
import numpy as np
from scipy.linalg import eigh_tridiagonal
from scipy.signal import find_peaks

k2, k1, k4 = 1.0, 5.75, 8.75
SN1, SN2 = 1.37154, 4.00578
W = SN2 - SN1
V = 20
XMAX = 4.6

def build(k3):
    N = int(np.ceil(V * XMAX))
    n = np.arange(N + 1)
    x = n / V
    Wp = k3 + k1 * x**2
    Wm = k4 * x + k2 * x**3
    Wp[-1] = 0.0
    return n, Wp, Wm

def stationary(Wp, Wm):
    lg = np.concatenate([[0.0], np.cumsum(np.log(Wp[:-1]) - np.log(Wm[1:]))])
    lg -= lg.max()
    pi = np.exp(lg); pi /= pi.sum()
    return pi

def spectrum_rt(Wp, Wm, k=4):
    d = -(Wp + Wm)
    off = np.sqrt(Wp[:-1] * Wm[1:])
    ev = eigh_tridiagonal(d, off, eigvals_only=True)
    ev = np.sort(ev)[::-1]          # ev[0] ~ 0
    rates = -ev[1:k+1]
    return 1.0 / rates              # real-time timescales t2,t3,...

def mfpt_up(Wp, pi, nf, nt):
    cs = np.cumsum(pi)
    j = np.arange(nf, nt)
    return np.sum(cs[j] / (Wp[j] * pi[j]))

def mfpt_down(Wm, pi, nf, nt):
    csr = np.cumsum(pi[::-1])[::-1]
    j = np.arange(nt + 1, nf + 1)
    return np.sum(csr[j] / (Wm[j] * pi[j]))

def roots_at(k3):
    r = np.roots([-1.0, k1, -k4, k3])
    r = np.sort(r[np.isreal(r)].real)
    return r[r >= -1e-9]

print(f"V={V} cap={XMAX} N={int(V*XMAX)}  real-time clock")
print("fr     k3      t2_rt      t3_rt     R_ex    T_lh_rt     T_hl_rt   piHi   pk")
rows = []
fr_deg = [(0.4 - SN1) / W, (0.7 - SN1) / W, (1.0 - SN1) / W]
fr_grid = fr_deg + list(np.round(np.linspace(-0.08, 0.85, 17), 4))
for fr in fr_grid:
    k3 = SN1 + fr * W
    n, Wp, Wm = build(k3)
    pi = stationary(Wp, Wm)
    t = spectrum_rt(Wp, Wm)
    r = roots_at(k3)
    if len(r) == 3:
        nl, nh = int(round(V * r[0])), int(round(V * r[2]))
        Tlh = mfpt_up(Wp, pi, nl, nh)
        Thl = mfpt_down(Wm, pi, nh, nl)
    else:
        Tlh = Thl = np.nan
    piHi = pi[int(V * 2.5):].sum()
    pk, _ = find_peaks(np.convolve(pi, np.ones(3) / 3, mode='same'),
                       prominence=0.05 * pi.max())
    print(f"{fr:6.3f} {k3:6.3f} {t[0]:10.2f} {t[1]:9.3f} {t[0]/t[1]:8.2f} "
          f"{Tlh:10.1f} {Thl:11.1f} {piHi:7.4f} {len(pk)}")
    rows.append((fr, k3, t[0], t[1], t[0]/t[1], Tlh, Thl, piHi, len(pk)))

# Lambda for uniformized simulation
k3max = SN1 + 0.85 * W
n, Wp, Wm = build(k3max)
Lam = 1.05 * (Wp + Wm).max()
print(f"\nLambda (x1.05 margin) = {Lam:.1f} per time unit; steps per T=200: {Lam*200:.2e}")
print(f"suggested stride 16 -> dt_rec = {16/Lam:.5f} units; samples/traj = {200*Lam/16:.0f}")
t3s = [r[3] for r in rows if r[0] > 0]
print(f"t3 range in window: {min(t3s):.3f} .. {max(t3s):.3f} units")
