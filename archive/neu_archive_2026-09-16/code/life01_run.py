"""LIFE-01 — время жизни рождённого уровня n*/t_ρ как сертификат сорта: ЭЭГ (PCCA(2)), кирхгофовы токи при θ_max (сид 777), случайные N = 6 (сид 2026).
Сорт I: τ = n*/t_ρ < 0.5; сорт II: τ ≥ 1 и d₂ > 0. По PREREG 2026-09-14."""
import numpy as np, json, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from cog01_lib import stationary, sym_form, restrict, spectral_radius, all_bipartitions, random_chain, random_reversible
src = open('/home/claude/ach01_run.py').read(); exec("def knob_chain" + src.split("def knob_chain")[1].split("def family")[0])
OUT = '/home/claude/life01_results.json'; t0 = time.time(); TOL = 1e-9; NMAX = 2000

def life(P, pi, rho, blocks):
    ind = (np.asarray(blocks) == np.asarray(blocks).min()).astype(float); h = ind - pi @ ind; h /= np.sqrt(np.sum(pi * h * h))
    v = h.copy(); C1 = float(np.sum(pi * (P @ h) * h)); Om = C1
    if not Om > rho + TOL: return None
    t_rho = -1 / np.log(rho); nstar = None; D2 = None; v = P @ (P @ h); n = 2
    while n <= NMAX:
        Cn = float(np.sum(pi * v * h)); Dn = Cn - Om ** n
        if n == 2: D2 = Dn
        if Dn < -1e-12: nstar = n; break
        v = P @ v; n += 1
    tau = (nstar / t_rho) if nstar else None; d2 = D2 / Om ** 2
    sort = 'I' if (tau is not None and tau < 0.5) else ('II' if (tau is None or tau >= 1) and d2 > 0 else 'X')
    return dict(Om=Om, rho=rho, t_rho=t_rho, nstar=nstar, tau=tau, d2=d2, sort=sort)

def summarize(recs, label, halves=True):
    s = [r['sort'] for r in recs]; n = len(s); fI = s.count('I') / n if n else None; fII = s.count('II') / n if n else None
    taus = [r['tau'] for r in recs if r['tau'] is not None]; out = dict(n=n, fI=fI, fII=fII, fX=(s.count('X') / n if n else None), frac_d2neg=(float(np.mean([r['d2'] < 0 for r in recs])) if n else None),
        tau_median=(float(np.median(taus)) if taus else None), n_inf=int(sum(r['tau'] is None for r in recs)),
        tau_med_d2pos=(float(np.median([r['tau'] if r['tau'] is not None else 1e9 for r in recs if r['d2'] > 0])) if any(r['d2'] > 0 for r in recs) else None),
        tau_med_d2neg=(float(np.median([r['tau'] if r['tau'] is not None else 1e9 for r in recs if r['d2'] < 0])) if any(r['d2'] < 0 for r in recs) else None))
    if halves and n >= 4: h = n // 2; out['halves_fII'] = [s[:h].count('II') / h, s[h:].count('II') / (n - h)]
    print(label, json.dumps(out, ensure_ascii=False), f'[{time.time()-t0:.0f}s]', flush=True); return out

res = {}
# ЭЭГ
from archive_loaders import series
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
E = {}; eeg_recs = []
for name, F, tau_, k, group in series(('eeg',)):
    lab = microstates(F, k, seed=0); cnt = TransitionCountEstimator(lagtime=tau_, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=False).fit(cnt).fetch_model(); msr = MaximumLikelihoodMSM(reversible=True).fit(cnt).fetch_model()
    P = np.asarray(msm.transition_matrix); pi = np.asarray(msm.stationary_distribution); pcca = np.asarray(msr.pcca(2).assignments)
    rho = spectral_radius(restrict(sym_form(P, pi), pi)); r = life(P, pi, rho, pcca)
    E[name] = r; 
    if r: eeg_recs.append(dict(r, name=name)); print(f"{name}: рождение Ω {r['Om']:.4f} ρ {rho:.4f} t_ρ {r['t_rho']:.1f} n* {r['nstar']} τ {r['tau']} d₂ {r['d2']:.3e} сорт {r['sort']}", flush=True)
res['eeg'] = dict(records=eeg_recs, summary=summarize(eeg_recs, 'ЭЭГ', halves=False), n_segments=len(E))
loo = [sum(1 for j, r in enumerate(eeg_recs) if j != i and r['sort'] == 'I') / max(1, len(eeg_recs) - 1) for i in range(len(eeg_recs))]; res['eeg']['loo_fI'] = loo
# кирхгофовы токи
parts = all_bipartitions(6); rng = np.random.default_rng(777); kn = []
for c in range(200):
    P0 = random_reversible(6, rng); pi0 = stationary(P0); Pk, thm = knob_chain(P0, pi0, rng); pi = stationary(Pk); rho = spectral_radius(restrict(sym_form(Pk, pi), pi))
    for b in parts:
        r = life(Pk, pi, rho, b)
        if r: kn.append(dict(r, chain=c))
res['knob'] = dict(summary=summarize(kn, 'токи θ_max'))
# случайные
rng = np.random.default_rng(2026); rd = []
for c in range(2000):
    P = random_chain(6, rng); pi = stationary(P); rho = spectral_radius(restrict(sym_form(P, pi), pi))
    for b in parts:
        r = life(P, pi, rho, b)
        if r: rd.append(dict(r, chain=c))
res['random'] = dict(summary=summarize(rd, 'случайные'))
# обратимые (K0)
rng = np.random.default_rng(777); nb = 0
for c in range(200):
    P = random_reversible(6, rng); pi = stationary(P); rho = spectral_radius(restrict(sym_form(P, pi), pi)); nb += sum(life(P, pi, rho, b) is not None for b in parts)
res['reversible_births'] = int(nb)
# вердикты
allr = eeg_recs + kn + rd; tp = [r['tau'] if r['tau'] is not None else 1e9 for r in allr if r['d2'] > 0]; tn = [r['tau'] if r['tau'] is not None else 1e9 for r in allr if r['d2'] < 0]
mp, mn = (float(np.median(tp)) if tp else None), (float(np.median(tn)) if tn else None)
eI = sum(r['sort'] == 'I' for r in eeg_recs); eII = sum(r['sort'] == 'II' for r in eeg_recs); ed = sum(r['d2'] < 0 for r in eeg_recs); ne = len(eeg_recs)
V = dict(K0=nb > 0, PF1=dict(n_born=ne, sortI=eI, sortII=eII, d2neg=ed, ok=(ne >= 7 and eI >= 5 and ed >= 5) or (ne < 7 and ne > 0 and eI / ne >= 5 / 7 and ed / ne >= 5 / 7)),
         PF2=dict(fII=res['knob']['summary']['fII'], ok=(res['knob']['summary']['fII'] or 0) >= 0.3), PF3=dict(fI=res['random']['summary']['fI'], fII=res['random']['summary']['fII'], ok=(res['random']['summary']['fI'] or 0) >= 0.6 and (res['random']['summary']['fII'] or 1) <= 0.1),
         PF4=dict(tau_med_d2pos=mp, tau_med_d2neg=mn, ok=(mp is not None and mn is not None and mp >= 1 and mn < 0.5)),
         K1=eII >= 4, K2=(res['knob']['summary']['fII'] or 0) < 0.1, K3=(mp is None or mn is None or (mn > 0 and mp / mn < 1.5)))
res['verdict'] = V; json.dump(res, open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps(V, default=float, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
