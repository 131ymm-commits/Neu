"""ROT-01 — вращательность уровней, рождённых токами при ≥ 3 блоках: семейство KNOB-01, случайные цепи, оценённые цепи ЭЭГ/обратимых. По PREREG 2026-09-10."""
import numpy as np, json, sys, time, warnings, itertools
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from cog01_lib import *
OUT = '/home/claude/rot01_results.json'; t0 = time.time()
def set_partitions_k(n, k):
    """все разбиения {0..n-1} ровно на k блоков (метки канонические)"""
    out = []
    def rec(i, labs, nb):
        if i == n:
            if nb == k: out.append(np.array(labs)); 
            return
        for b in range(nb): rec(i + 1, labs + [b], nb)
        if nb < k: rec(i + 1, labs + [nb], nb + 1)
    rec(0, [], 0); return out
def lam2(PY):
    ev = np.linalg.eigvals(PY); ev = ev[np.argsort(-np.abs(ev))]; return ev[1]
def births(P, pi, parts, rho, w):
    n_b = 0; n_c = 0; viol = 0
    for b in parts:
        l = lam2(lump(P, pi, b)[0])
        if abs(l) > rho + 1e-9:
            n_b += 1; n_c += int(abs(l.imag) > 1e-9)
        if abs(l) > w + 1e-7: viol += 1
    return n_b, n_c, viol
P2 = all_bipartitions(6); P3 = set_partitions_k(6, 3); print('разбиений: 2-блочных', len(P2), '3-блочных', len(P3))
R = {}
# (i) семейство KNOB-01
rng = np.random.default_rng(777); rows = []
for it in range(200):
    P0 = random_reversible(6, rng); pi = stationary(P0); Fl = pi[:, None] * P0; K = np.zeros((6, 6))
    for _c in range(3):
        m = int(rng.integers(3, 7)); cyc = rng.permutation(6)[:m]; amp = min(Fl[cyc[i], cyc[(i + 1) % m]] for i in range(m))
        for i in range(m): a, b = cyc[i], cyc[(i + 1) % m]; K[a, b] += amp; K[b, a] -= amp
    G = K / pi[:, None]; neg = G < 0; th_max = float(np.min(-P0[neg] / G[neg])) * 0.999 if neg.any() else 1.0
    r = {}
    for tag, th in (('0', 0.0), ('max', th_max)):
        P = P0 + th * G; A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0); w = numerical_radius(A0, 180)
        b2, c2, v2 = births(P, pi, P2, rho, w); b3, c3, v3 = births(P, pi, P3, rho, w); r[tag] = dict(b2=b2, c2=c2, b3=b3, c3=c3, viol=v2 + v3, rho=rho, w=w)
    rows.append(r)
def summarize(rows, tag):
    b2 = sum(r[tag]['b2'] for r in rows); b3 = sum(r[tag]['b3'] for r in rows); c3 = sum(r[tag]['c3'] for r in rows); c2 = sum(r[tag]['c2'] for r in rows); viol = sum(r[tag]['viol'] for r in rows); n = len(rows)
    return dict(frac2=b2 / (n * len(P2)), frac3=b3 / (n * len(P3)), n_b2=b2, n_b3=b3, complex_frac3=(c3 / b3 if b3 else None), complex2=c2, viol=viol, pairs_with_b3=int(sum(r[tag]['b3'] > 0 for r in rows)), halves_complex3=[(sum(r[tag]['c3'] for r in rows[:100]) / max(1, sum(r[tag]['b3'] for r in rows[:100]))), (sum(r[tag]['c3'] for r in rows[100:]) / max(1, sum(r[tag]['b3'] for r in rows[100:])))])
R['knob_theta0'] = summarize(rows, '0'); R['knob_thetamax'] = summarize(rows, 'max'); print('KNOB θ=0', R['knob_theta0'], '\nKNOB θ_max', R['knob_thetamax'], f'[{time.time()-t0:.0f}s]', flush=True)
# (ii) случайные необратимые цепи COG-01 (тот же сид, N = 6)
rng2 = np.random.default_rng(2026); rows2 = []
for fam_name, gen in (('rev', random_reversible), ('nonrev', random_chain)):
    for n in (3, 4, 6):
        for i in range(2000):
            P = gen(n, rng2)
            if fam_name == 'rev' or n != 6: continue
            pi = stationary(P); A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0); w = numerical_radius(A0, 180)
            b2, c2, v2 = births(P, pi, P2, rho, w); b3, c3, v3 = births(P, pi, P3, rho, w); rows2.append(dict(x=dict(b2=b2, c2=c2, b3=b3, c3=c3, viol=v2 + v3, rho=rho, w=w)))
R['random_n6'] = summarize(rows2, 'x'); print('случайные n=6', R['random_n6'], f'[{time.time()-t0:.0f}s]', flush=True)
# (iii) оценённые цепи архива
from archive_loaders import series
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
from hor02_lib import telegraph
from zeta01_lib import embed
def est(lab, tau):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    mn = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model(); mr = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    return np.asarray(mn.transition_matrix), np.asarray(mn.stationary_distribution), np.asarray(mr.pcca(3).assignments)
arch = {}
def run(name, F, tau, k, group):
    lab = microstates(F, k, seed=0); P, pi, pc3 = est(lab, tau); A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0); w = numerical_radius(A0, 180)
    rng3 = np.random.default_rng(5); parts = [b for b in (rng3.integers(0, 3, len(P)) for _ in range(300)) if len(np.unique(b)) == 3]
    b3, c3, v3 = births(P, pi, parts, rho, w); l = lam2(lump(P, pi, pc3)[0]); bp = bool(abs(l) > rho + 1e-9)
    arch[name] = dict(group=group, rho=rho, w=w, delta=w - rho, rand3_births=b3, rand3_complex=c3, n_rand3=len(parts), pcca3_birth=bp, pcca3_complex=bool(bp and abs(l.imag) > 1e-9), pcca3_l2=[float(l.real), float(l.imag)], viol=v3)
    print(f"{name:22s} [{group}] δ {w-rho:.3f} | случайные 3-бл.: рождений {b3}/{len(parts)} (компл. {c3}) | PCCA(3): рождение {bp} компл. {arch[name]['pcca3_complex']} λ₂ {l:.3f} [{time.time()-t0:.0f}s]", flush=True)
for s in range(5):
    rng4 = np.random.default_rng(1000 * 40 + s); x, _ = telegraph(8000, 40, rng4); run(f'tel40_s{s}', embed(x, 4), 1, 30, 'tel')
for name, F, tau, k, group in series(('eeg', 'insilico')): run(name, F, tau, k, group)
R['archive'] = arch
def g(gr): return {k: v for k, v in arch.items() if v['group'] == gr}
eeg = g('eeg'); rev = {**g('dip'), **g('lj13')}
eb = sum(v['rand3_births'] for v in eeg.values()) + sum(v['pcca3_birth'] for v in eeg.values()); ec = sum(v['rand3_complex'] for v in eeg.values()) + sum(v['pcca3_complex'] for v in eeg.values())
rb = sum(v['rand3_births'] for v in rev.values()) + sum(v['pcca3_birth'] for v in rev.values())
V = dict(PT1=dict(ok=bool((R['knob_thetamax']['complex_frac3'] or 0) >= 0.5), complex_frac3=R['knob_thetamax']['complex_frac3']), PT2=dict(ok=bool(R['knob_thetamax']['frac3'] >= 1.5 * R['knob_thetamax']['frac2']), frac3=R['knob_thetamax']['frac3'], frac2=R['knob_thetamax']['frac2']),
         PT3=dict(ok=bool((R['random_n6']['complex_frac3'] or 0) >= 0.3), complex_frac3=R['random_n6']['complex_frac3']), PT4=dict(eeg_births=eb, eeg_complex=ec, eeg_complex_frac=(ec / eb if eb else None), rev_births=rb, ok=bool(eb and ec / eb >= 0.5 and rb == 0)),
         K0=dict(hit=bool(R['knob_theta0']['n_b2'] + R['knob_theta0']['n_b3'] > 0 or rb > 0 or R['knob_thetamax']['viol'] + R['random_n6']['viol'] + sum(v['viol'] for v in arch.values()) > 0)),
         K1=dict(hit=bool((R['knob_thetamax']['complex_frac3'] or 0) <= 0.2)), K2=dict(hit=bool(R['knob_thetamax']['frac3'] <= 1.2 * R['knob_thetamax']['frac2'])), K3=dict(hit=bool(eb and ec / eb <= 0.2)))
R['verdicts'] = V; json.dump(R, open(OUT, 'w'), default=float); print('== ВЕРДИКТЫ ROT-01 ==', json.dumps(V, ensure_ascii=False, default=float))
