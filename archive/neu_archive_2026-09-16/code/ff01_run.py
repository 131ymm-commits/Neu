"""FF-01 — запас рождения δ на моделях программы: flip-flop (неградиентный) против градиентной ямы и Шлёгля. По PREREG 2026-09-09."""
import numpy as np, json, os, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
from cog01_lib import sym_form, restrict, numerical_radius, spectral_radius, lump, lambda2
from scipy.stats import spearmanr
B = '/home/claude'; OUT = f'{B}/ff01_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()
Fmax = 6.0; BETA = 1.0; ALPHA = 0.4; CW = 2.0; G = 0.6; TAU = 1.5
def S(c): return Fmax * 0.5 * (1 + np.tanh((c - BETA) / ALPHA))
def run_ff(b, sigma, seed, T=20000.0, dt=0.05, rec=0.5):
    rng = np.random.default_rng(seed); nst = int(T / dt); nrec = int(rec / dt); sq = np.sqrt(dt); fW, fN = 5.5, 0.1; out = np.empty((nst // nrec, 2)); j = 0
    noise = rng.standard_normal((nst, 2)) * sigma * sq
    for i in range(nst):
        fW += dt * ((S(CW - G * fN) - fW) / TAU) + noise[i, 0]; fN += dt * ((S(b - G * fW) - fN) / TAU) + noise[i, 1]
        fW = min(max(fW, 0), Fmax); fN = min(max(fN, 0), Fmax)
        if i % nrec == 0: out[j] = (fW, fN); j += 1
    return out[:j]
def run_grad(h, sigma, seed, T=20000.0, dt=0.01, rec=0.5):  # dt 0.01: при h = 4 явный Эйлер с dt 0.05 расходится (жёсткость ~16)
    rng = np.random.default_rng(seed); nst = int(T / dt); nrec = int(rec / dt); sq = np.sqrt(dt); x, y = 1.0, 0.0; out = np.empty((nst // nrec, 2)); j = 0
    noise = rng.standard_normal((nst, 2)) * sigma * sq
    for i in range(nst):
        x += dt * (-4 * h * x * (x * x - 1)) + noise[i, 0]; y += dt * (-y) + noise[i, 1]
        if i % nrec == 0: out[j] = (x, y); j += 1
    return out[:j]
def fit(lab, tau, rev=False):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    return MaximumLikelihoodMSM(reversible=rev).fit(c).fetch_model(), c
def top_its(m, tau): return float(np.sort(np.abs(np.real(m.timescales(3))))[::-1][0])
def bisect_hierarchy(P, pi, depth=4):
    n = len(P); levels = []; blocks = np.zeros(n, int)
    for d in range(depth):
        new = np.zeros(n, int); nb = 0
        for bb in np.unique(blocks):
            idx = np.where(blocks == bb)[0]
            if len(idx) < 2: new[idx] = nb; nb += 1; continue
            Pb = P[np.ix_(idx, idx)]; pib = pi[idx] / pi[idx].sum(); Sm = (sym_form(Pb + 1e-12, pib) + sym_form(Pb + 1e-12, pib).T) / 2
            ev, U = np.linalg.eigh(Sm); v = U[:, -2]; sgn = v >= 0
            if sgn.all() or (~sgn).all(): sgn[np.argmax(np.abs(v))] = ~sgn[np.argmax(np.abs(v))]
            new[idx[sgn]] = nb; new[idx[~sgn]] = nb + 1; nb += 2
        blocks = new; levels.append(blocks.copy())
    return levels
def analyze(lab, tau=1):
    n = len(lab); mn, c = fit(lab, tau); P = np.asarray(mn.transition_matrix); pi = np.asarray(mn.stationary_distribution); syms = np.asarray(c.state_symbols)
    A0 = restrict(sym_form(P, pi), pi); rho = spectral_radius(A0); w = numerical_radius(A0)
    halves = []
    for l in (lab[:n // 2], lab[n // 2:]):
        try:
            m2, _ = fit(l, tau); P2 = np.asarray(m2.transition_matrix); pi2 = np.asarray(m2.stationary_distribution); A2 = restrict(sym_form(P2, pi2), pi2); halves.append(numerical_radius(A2) - spectral_radius(A2))
        except Exception: halves.append(None)
    mr, _ = fit(lab, tau, rev=True); pc = np.asarray(mr.pcca(2).assignments); l2p = lambda2(lump(P, pi, pc)[0]); birth = bool(l2p > rho + 1e-6)
    levels = bisect_hierarchy(P, pi, depth=min(4, int(np.floor(np.log2(len(P)))))); seq = [lambda2(lump(P, pi, bl)[0]) for bl in levels] + [rho]
    inv = int(sum(seq[i] > seq[i + 1] + 1e-6 for i in range(len(seq) - 1)))
    coarse = np.zeros(lab.max() + 1, int) - 1; coarse[syms] = pc; lc = coarse[lab]; ok = lc >= 0; rr = {}
    for nl in (1, 2, 4, 8):
        try:
            mf, _ = fit(lab, tau * nl); mc, _ = fit(lc[ok], tau * nl); rr[str(nl)] = top_its(mc, tau * nl) / top_its(mf, tau * nl)
        except Exception: rr[str(nl)] = None
    return dict(k=int(len(P)), rho=rho, w=w, delta=w - rho, delta_halves=halves, t_fine=float(-tau / np.log(rho)) if 0 < rho < 1 else None, birth_pcca=birth, l2_pcca=l2p, inversions=inv, levels=seq, r=rr)
def run(name, F, group, k=50, meta=None):
    if name in res: return
    lab = microstates(F, k, seed=0) if F.ndim == 2 else F; r = analyze(lab); r['group'] = group
    if meta: r.update(meta)
    res[name] = r; json.dump(res, open(OUT, 'w'), default=float)
    print(f"{name:16s} [{group}] k={r['k']} ρ {r['rho']:.4f} w {r['w']:.4f} δ {r['delta']:.4f} (половины {[None if x is None else round(x, 4) for x in r['delta_halves']]}) t_fine {r['t_fine']:.1f} | PCCA-рождение {r['birth_pcca']} инверсий {r['inversions']} r(n) {[None if v is None else round(v, 2) for v in r['r'].values()]} [{time.time()-t0:.0f}s]", flush=True)
for b in (1.5, 1.75, 2.0, 2.25, 2.5):
    for s in range(4):
        x = run_ff(b, 1.0, 100 + s); sw = int(np.sum(np.diff((x[:, 0] > 3).astype(int)) != 0)); run(f'ff_b{b}_s{s}', x, 'ff', meta=dict(b=b, seed=s, switches=sw))
for h in (0.5, 1.0, 2.0, 4.0):
    for s in range(4):
        x = run_grad(h, 1.0, 200 + s); sw = int(np.sum(np.diff((x[:, 0] > 0).astype(int)) != 0)); run(f'grad_h{h}_s{s}', x, 'grad', meta=dict(h=h, seed=s, switches=sw))
# Шлёгль
hh = {}; exec(open(f'{B}/pre005b_run.py').read().split('def indicators')[0], hh)
for s in range(4):
    rec = hh['sim_ext'](lambda t: 0.70, 300 + s, 1, 50)[0]; edges = np.quantile(rec, np.linspace(0, 1, 31)[1:-1]); lab = np.searchsorted(edges, rec); sw = int(np.sum(np.diff((rec > np.median(rec)).astype(int)) != 0))
    run(f'schlogl_s{s}', lab.astype(int), 'schlogl', meta=dict(seed=s, switches=sw, n=int(len(rec))))
# --- вердикты ---
def grp(g): return {k: v for k, v in res.items() if isinstance(v, dict) and v.get('group') == g}
ff, gr, sc = grp('ff'), grp('grad'), grp('schlogl')
d_ff = float(np.median([v['delta'] for v in ff.values()])); rho_ff = float(np.median([v['rho'] for v in ff.values()]))
# ближайший по ρ градиентный h
byh = {}
for h in (0.5, 1.0, 2.0, 4.0):
    vs = [v for v in gr.values() if v['h'] == h]; byh[str(h)] = dict(rho=float(np.median([v['rho'] for v in vs])), delta=float(np.median([v['delta'] for v in vs])))
h_near = min(byh, key=lambda h: abs(np.log(byh[h]['rho']) - np.log(rho_ff))); d_gr = byh[h_near]['delta']; d_sc = float(np.median([v['delta'] for v in sc.values()]))
sp = []
for s in range(4):
    bs = [v['b'] for v in ff.values() if v['seed'] == s]; ds = [v['delta'] for v in ff.values() if v['seed'] == s]; sp.append(float(spearmanr(bs, ds)[0]))
births = dict(ff=int(sum(v['birth_pcca'] for v in ff.values())), grad=int(sum(v['birth_pcca'] for v in gr.values())), schlogl=int(sum(v['birth_pcca'] for v in sc.values())))
conv = float(np.mean([abs(v['delta_halves'][0] - v['delta_halves'][1]) <= 0.5 * max(v['delta'], 1e-9) for v in ff.values() if None not in v['delta_halves']]))
loo = [float(np.median([v['delta'] for v in ff.values() if v['seed'] != s])) for s in range(4)]
V = dict(delta_ff=d_ff, rho_ff=rho_ff, grad_by_h=byh, h_near=h_near, delta_grad_near=d_gr, delta_schlogl=d_sc, delta_ff_by_b={str(b): float(np.median([v['delta'] for v in ff.values() if v['b'] == b])) for b in (1.5, 1.75, 2.0, 2.25, 2.5)},
         spearman_b_delta=sp, births=births, conv_halves=conv, loo_delta_ff=loo, born=[k for k, v in ff.items() if v['birth_pcca']],
         r_born={k: v['r'] for k, v in ff.items() if v['birth_pcca']}, inversions=dict(ff=int(sum(v['inversions'] > 0 for v in ff.values())), grad=int(sum(v['inversions'] > 0 for v in gr.values())), schlogl=int(sum(v['inversions'] > 0 for v in sc.values()))))
V['PF1'] = dict(ok=bool(d_ff >= 0.01 and d_ff >= 3 * d_gr)); V['PF2'] = dict(ok=bool(d_sc <= 0.005)); V['PF3'] = dict(ok=bool(sum(s <= -0.6 for s in sp) >= 3)); V['PF4'] = dict(ok=bool(births['ff'] >= 3 and births['grad'] == 0 and births['schlogl'] == 0))
V['K1'] = dict(hit=bool(d_ff <= 2 * d_gr)); V['K2'] = dict(hit=bool(d_sc > 0.01 or d_gr > 0.01)); V['K3'] = dict(hit=bool(births['grad'] + births['schlogl'] >= births['ff']))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), default=float)
print('== ВЕРДИКТЫ FF-01 ==', json.dumps(V, ensure_ascii=False, default=float))
