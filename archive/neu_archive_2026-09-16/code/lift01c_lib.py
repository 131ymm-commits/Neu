"""LIFT-01c — библиотека: лифтированный путь LIFT-01 (вариант A: у стенки переворот и стояние; без ленивости) и анализ
ведущей пары. Формула Robichon–Monthus–Krauth (2609.05183, уравнение для λ±(h)) в нашей параметризации:
фурье-блок [[ (1−p)e^{ik}, p e^{−ik} ], [ p e^{ik}, (1−p)e^{−ik} ]], det = 1 − 2p."""
import numpy as np, sys
sys.path.insert(0, '/home/claude')
from cog01_lib import stationary, sym_form, restrict
TOL = 1e-9

def lifted_path(L, p):
    n = 2 * L; P = np.zeros((n, n)); idx = lambda x, s: 2 * (x - 1) + (0 if s == 1 else 1)
    for x in range(1, L + 1):
        for s in (1, -1):
            i = idx(x, s)
            for s2, pr in ((s, 1 - p), (-s, p)):
                x2 = x + s2
                if 1 <= x2 <= L: P[i, idx(x2, s2)] += pr
                else: P[i, idx(x, -s2)] += pr
    return P

def analyze(L, p):
    P = lifted_path(L, p); pi = stationary(P); A0 = restrict(sym_form(P, pi), pi)
    ev = np.linalg.eigvals(A0); k = int(np.argmax(np.abs(ev))); lead = ev[k]; rho = float(abs(lead))
    F = pi[:, None] * P; a = 2 * (L // 2); flux = F[:a, a:].sum(); piA = pi[:a].sum(); piB = 1 - piA
    mid = float(1 - flux * (1 / piA + 1 / piB))
    l2 = np.empty(L - 1)
    for kk in range(1, L):
        aa = 2 * kk; fl = F[:aa, aa:].sum(); pA = pi[:aa].sum(); l2[kk - 1] = 1 - fl * (1 / pA + 1 / (1 - pA))
    R = float(np.log(rho) / np.log(mid)) if (0 < mid < 1 and 0 < rho < 1) else None
    return dict(L=L, p=p, c=p * L, rho=rho, im_lead=float(abs(lead.imag)), re_lead=float(lead.real), complex_lead=bool(abs(lead.imag) > 1e-7),
                rho2_minus_1m2p=float(rho ** 2 - (1 - 2 * p)), l2_mid=mid, R_mid=R, birth_mid=bool(mid > rho + TOL),
                f_birth=float((l2 > rho + TOL).mean()))

def closed_form(L, p):
    """λ± первой моды k = π/L по фурье-блоку (без учёта стенки) и λ₂(mid) = 1 − 2(1−p)/L."""
    k = np.pi / L; a = (1 - p) * np.cos(k); d = a * a - (1 - 2 * p)
    lam = a + np.sqrt(d + 0j); return dict(rho_cf=float(abs(lam)), complex_cf=bool(d < 0), l2_mid_cf=1 - 2 * (1 - p) / L)
