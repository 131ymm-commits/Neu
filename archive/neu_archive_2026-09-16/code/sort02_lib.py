"""SORT-02 — библиотека: второй радиус ρ₊ = max{|λ| : λ ≠ 1, Re λ > 0} (медленнейшая нечередующаяся мода) рядом с ρ = max|λ|;
анализ описания-индикатора относительно обоих: рождение при лаге 1, постоянство (C_n > ρ₊ⁿ до ρ₊^{n_max} = 10⁻⁶),
биортогональный вес a₊ на моде ρ₊, позднее рождение. Работает и с точными, и с оценёнными цепями (P, π заданы)."""
import numpy as np, sys
sys.path.insert(0, '/home/claude')
from cog01_lib import sym_form
TOL = 1e-6

def spectrum_info(P, pi):
    A = sym_form(P, pi); ev, R = np.linalg.eig(A); triv = int(np.argmin(np.abs(ev - 1)))
    mask = np.ones(len(ev), bool); mask[triv] = False; idx = np.where(mask)[0]
    rho = float(np.max(np.abs(ev[idx]))); k_rho = int(idx[np.argmax(np.abs(ev[idx]))])
    pos = idx[ev[idx].real > 0]
    if len(pos) == 0: return dict(rho=rho, rho_plus=None, k_rho=k_rho, k_plus=None, ev=ev, R=R, A=A)
    k_plus = int(pos[np.argmax(np.abs(ev[pos]))]); rho_plus = float(abs(ev[k_plus]))
    return dict(rho=rho, rho_plus=rho_plus, k_rho=k_rho, k_plus=k_plus, lam_rho=ev[k_rho], lam_plus=ev[k_plus],
                theta_plus=float(abs(np.angle(ev[k_plus]))), real_plus=bool(abs(ev[k_plus].imag) < 1e-9), ev=ev, R=R, A=A)

def indicator(pi, blocks):
    ind = np.asarray(blocks, float); h = ind - pi @ ind; nrm = np.sqrt(np.sum(pi * h * h))
    return h / nrm if nrm > 0 else None

def analyze_description(P, pi, h, floor=1e-6, nmax_cap=6000):
    S = spectrum_info(P, pi); rho, rp = S['rho'], S['rho_plus']
    ref = rp if rp is not None else rho; n_max = min(int(np.ceil(np.log(floor) / np.log(ref))), nmax_cap) if 0 < ref < 1 else nmax_cap
    C = np.empty(n_max); v = h.copy()
    for n in range(1, n_max + 1):
        v = P @ v; C[n - 1] = float(np.sum(pi * v * h))
    n = np.arange(1, n_max + 1); out = dict(rho=rho, rho_plus=rp, theta_plus=S.get('theta_plus'), real_plus=S.get('real_plus'), n_max=n_max, C1=float(C[0]),
                                            born_rho=bool(C[0] > rho * (1 + TOL)), born_plus=bool(rp is not None and C[0] > rp * (1 + TOL)))
    if rp is not None and 0 < rp < 1:
        rn = rp ** n; above = C > rn * (1 + TOL); ex = np.where(~above)[0]
        out['permanent_plus'] = bool(len(ex) == 0); out['n_life_plus'] = int(ex[0]) if len(ex) else n_max; out['q_end_plus'] = float(C[-1] / rn[-1])
        w_ = np.where(above)[0]; out['late_plus'] = (int(w_[0] + 1) if (not out['born_plus'] and len(w_)) else None)
        # биортогональный вес на моде ρ₊
        Lv = np.linalg.inv(S['R']); g0 = np.sqrt(pi) * h; ak = (S['R'].T @ g0) * (Lv @ g0); k = S['k_plus']
        out['a_plus'] = float(np.real(ak[k])) if S['real_plus'] else float(2 * np.real(ak[k])); out['a_sum'] = float(np.real(ak.sum()))
        out['a_rho'] = float(np.real(ak[S['k_rho']])) if abs(S['lam_rho'].imag) < 1e-9 else float(2 * np.real(ak[S['k_rho']]))
    else:
        out.update(permanent_plus=None, n_life_plus=None, q_end_plus=None, late_plus=None, a_plus=None, a_sum=None, a_rho=None)
    if 0 < rho < 1:
        rn = rho ** n; above = C > rn * (1 + TOL); ex = np.where(~above)[0]; out['n_life_rho'] = int(ex[0]) if len(ex) else n_max
    out['t_rho'] = float(-1 / np.log(rho)) if 0 < rho < 1 else None; out['t_plus'] = float(-1 / np.log(rp)) if (rp and 0 < rp < 1) else None
    out['D2_sign'] = int(np.sign(C[1] - C[0] ** 2)) if n_max >= 2 else None
    return out
