"""SORT-02 — прогон по PREREG (2026-09-15). (a) точный lifted_local L ∈ {64, 128}, s-сетка, c ∈ [1.5, 3.6] шаг 0.05, описание — средний разрез;
(b) ЭЭГ Бонна (25 сегментов, конвейер COG-01) + суррогатный нуль (20 траекторий из обратимой MSM сегмента). Числа — sort02_results.json."""
import numpy as np, json, time, warnings, sys
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from sort02_lib import indicator, analyze_description
from sort01_lib import lifted_local
from cog01_lib import stationary
from archive_loaders import series
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
t0 = time.time(); OUT = '/home/claude/sort02_results.json'; res = dict(A={}, B={}, verdict={})
# ---------------- (a)
def row_of(r, c): r = dict(r); r['c'] = float(c); return r
for L in (64, 128):
    xs = np.repeat(np.arange(1, L + 1), 2); ind = (xs <= L // 2).astype(int); cs = np.round(np.arange(1.5, 3.601, 0.05), 3); out = {}
    for s in (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.34, 0.36, 0.38):
        rows = []
        for c in cs:
            P = lifted_local(L, float(c / L), s); pi = stationary(P); r = analyze_description(P, pi, indicator(pi, ind), nmax_cap=8000); rows.append(row_of(r, c))
        b_rho = [r['c'] for r in rows if r['born_rho']]; b_plus = [r['c'] for r in rows if r['born_plus']]; perm = [r['c'] for r in rows if r['permanent_plus']]
        cplx = [r['c'] for r in rows if not r['real_plus']]; last_c = max(cplx) if cplx else None
        real_in_win = [r['c'] for r in rows if r['real_plus'] and r['born_plus']]; late = [r['c'] for r in rows if r['real_plus'] and r['late_plus']]
        out[str(s)] = dict(s=s, win_rho=[min(b_rho), max(b_rho)] if b_rho else None, win_plus=[min(b_plus), max(b_plus)] if b_plus else None, n_rho=len(b_rho), n_plus=len(b_plus),
                           perm_plus=perm, real_in_window=real_in_win, last_complex=last_c, late_real=[min(late), max(late)] if late else None, n_late=len(late),
                           a_plus_real=[(r['c'], round(r['a_plus'], 4)) for r in rows if r['real_plus']][:12])
        print(f"a L={L} s={s}: окно ρ {out[str(s)]['win_rho']} ({len(b_rho)}), окно ρ₊ {out[str(s)]['win_plus']} ({len(b_plus)}); постоянные₊ {perm[:2]}…{perm[-1:] } ({len(perm)}); вещ. в окне {real_in_win[:1]}…{real_in_win[-1:]} ({len(real_in_win)}); компл. до {last_c}; поздние₊ {out[str(s)]['late_real']} [{time.time()-t0:.0f}s]", flush=True)
    ss = sorted(float(k) for k in out); opened = [s for s in ss if out[str(s)]['n_plus'] > 0]; closed = [s for s in ss if out[str(s)]['n_plus'] == 0 and s > (max(opened) if opened else -1)]
    s_c_plus = (max(opened) + min(closed)) / 2 if opened and closed else None
    op_r = [s for s in ss if out[str(s)]['n_rho'] > 0]; cl_r = [s for s in ss if out[str(s)]['n_rho'] == 0 and s > (max(op_r) if op_r else -1)]
    res['A'][str(L)] = dict(L=L, windows=out, s_c_plus=s_c_plus, s_c_rho=((max(op_r) + min(cl_r)) / 2 if op_r and cl_r else None))
    print(f"a L={L}: s_c₊ ≈ {s_c_plus}, s_c(ρ) ≈ {res['A'][str(L)]['s_c_rho']}", flush=True)
json.dump(res, open(OUT, 'w'), default=float)
V = res['verdict']
def t1(L):
    W = res['A'][str(L)]['windows']; ok = True; det = {}
    for s in ('0.0', '0.02', '0.05', '0.1', '0.15', '0.2'):
        w = W[s]; perm = set(w['perm_plus']); real = set(w['real_in_window']); sym = perm ^ real
        det[s] = dict(n_perm=len(perm), n_real=len(real), symdiff=sorted(sym)); ok = ok and len(perm) > 0 and len(sym) <= 1 and all(abs(x - (w['last_complex'] or 0)) <= 0.051 for x in sym)
    return ok, det
V['PT1'] = {str(L): dict(zip(('ok', 'detail'), t1(L))) for L in (64, 128)}; V['PT1']['ok'] = all(V['PT1'][str(L)]['ok'] for L in (64, 128))
def k1(L):
    W = res['A'][str(L)]['windows']
    for s in ('0.02', '0.05', '0.1'):
        w = W[s]
        if not w['perm_plus']: return True
        if w['last_complex'] and any(c < w['last_complex'] - 0.051 for c in w['perm_plus']): return True
    return False
V['K1'] = any(k1(L) for L in (64, 128))
def t2(L):
    W = res['A'][str(L)]['windows']; ok = True
    for s, w in W.items():
        if w['win_rho'] and w['win_plus']:
            ok = ok and (w['win_plus'][1] >= w['win_rho'][1] - 1e-9) and (float(s) < 0.02 or w['win_plus'][1] > w['win_rho'][1] + 1e-9)
    sc = res['A'][str(L)]['s_c_plus']; return ok and sc is not None and 0.32 <= sc <= 0.38, sc
V['PT2'] = {str(L): dict(zip(('ok', 's_c_plus'), t2(L))) for L in (64, 128)}; V['PT2']['ok'] = all(V['PT2'][str(L)]['ok'] for L in (64, 128))
V['K2'] = any((res['A'][str(L)]['s_c_plus'] is None) or not (0.30 <= res['A'][str(L)]['s_c_plus'] <= 0.40) for L in (64, 128))
V['K0a'] = not (res['A']['64']['windows']['0.0']['win_rho'] == res['A']['64']['windows']['0.0']['win_plus'] and res['A']['128']['windows']['0.0']['win_rho'] == res['A']['128']['windows']['0.0']['win_plus'])
json.dump(res, open(OUT, 'w'), default=float); print('вердикт (a):', json.dumps({k: V[k] for k in ('PT1', 'PT2', 'K0a', 'K1', 'K2')}, default=float), flush=True)
# ---------------- (b) ЭЭГ
def est(lab, tau):
    c = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=False).fit(c).fetch_model(); msr = MaximumLikelihoodMSM(reversible=True).fit(c).fetch_model()
    return np.asarray(msm.transition_matrix), np.asarray(msm.stationary_distribution), np.asarray(msr.pcca(2).assignments), np.asarray(msr.transition_matrix), np.asarray(c.state_symbols)
def simulate(P, n, rng):
    cum = np.cumsum(P, 1); pi = stationary(P); st = int(rng.choice(len(P), p=pi / pi.sum())); traj = np.empty(n, int); u = rng.random(n)
    for t in range(n):
        traj[t] = st; st = int(min(np.searchsorted(cum[st], u[t]), len(P) - 1))
    return traj
NS = 20; B = {}
for name, F, tau, k, group in series(('eeg',)):
    lab = microstates(F, k, seed=0); P, pi, pcca, Pr, syms = est(lab, tau); h = indicator(pi, pcca); r = analyze_description(P, pi, h)
    rng = np.random.default_rng(abs(hash(name)) % (2 ** 32)); sur = []
    for j in range(NS):
        traj = simulate(Pr, len(lab), rng)  # траектория на микросостояниях из ОБРАТИМОЙ MSM (лаг τ — шаг суррогата = τ)
        Ps, pis, pccas, _, _ = est(traj, 1); hs = indicator(pis, pccas)
        rs = analyze_description(Ps, pis, hs) if hs is not None else None
        if rs: sur.append(dict(born_rho=rs['born_rho'], a_plus=rs['a_plus'], rho=rs['rho']))
    a_s = [x['a_plus'] for x in sur if x['a_plus'] is not None]; p95 = float(np.percentile(a_s, 95)) if a_s else None
    B[name] = dict(rho=r['rho'], rho_plus=r['rho_plus'], real_plus=r['real_plus'], theta_plus=r['theta_plus'], C1=r['C1'], born_rho=r['born_rho'], born_plus=r['born_plus'], a_plus=r['a_plus'],
                   permanent_plus=r['permanent_plus'], n_life_plus=r['n_life_plus'], t_plus=r['t_plus'], late_plus=(r['late_plus'] if r['real_plus'] else None),
                   sur_birth_frac=float(np.mean([x['born_rho'] for x in sur])) if sur else None, sur_a_p95=p95, sur_a_mean=float(np.mean(a_s)) if a_s else None, above_null=bool(p95 is not None and r['a_plus'] is not None and r['a_plus'] > p95))
    print(f"{name}: ρ={r['rho']:.3f} ρ₊={r['rho_plus']:.3f} real₊={r['real_plus']} | PCCA: C1={r['C1']:.3f} born_ρ={r['born_rho']} born₊={r['born_plus']} a₊={r['a_plus']:.3f} perm₊={r['permanent_plus']} life₊={r['n_life_plus']} t₊={r['t_plus']:.1f} | сурр.: доля рожд {B[name]['sur_birth_frac']:.2f} a₊ mean {B[name]['sur_a_mean']:.3f} P95 {p95:.3f} выше нуля {B[name]['above_null']} [{time.time()-t0:.0f}s]", flush=True)
res['B'] = B; json.dump(res, open(OUT, 'w'), default=float)
names = list(B); n_rho = sum(B[n]['born_rho'] for n in names); n_plus = sum(B[n]['born_plus'] for n in names); same = sum(abs(B[n]['rho'] - B[n]['rho_plus']) < 1e-9 for n in names)
V['PT3'] = dict(births_rho=n_rho, births_plus=n_plus, rho_eq=same, ok=bool(n_rho == 7 and 7 <= n_plus <= 10 and same >= 20)); V['K0b'] = bool(n_rho != 7)
sur_frac = float(np.mean([B[n]['sur_birth_frac'] for n in names])); V['PT4'] = dict(sur_birth_frac_mean=sur_frac, ok=bool(sur_frac >= 0.28)); V['K4'] = bool(sur_frac < 0.15)
above = sum(B[n]['above_null'] for n in names); V['PT5'] = dict(n_above_null=above, ok=bool(above <= 3)); V['K5'] = bool(above >= 6)
born = [n for n in names if B[n]['born_rho']]; nperm = sum(bool(B[n]['permanent_plus']) for n in born); V['PT6'] = dict(n_born=len(born), n_permanent=nperm, ok=bool(nperm <= 2))
json.dump(res, open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps({k: V[k] for k in ('PT1', 'PT2', 'PT3', 'PT4', 'PT5', 'PT6', 'K0a', 'K0b', 'K1', 'K2', 'K4', 'K5')}, default=float)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
