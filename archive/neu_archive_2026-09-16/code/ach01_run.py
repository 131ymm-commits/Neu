"""ACH-01 — достижимость рождения при огрублении как косинус: λ₂ 2-блочного лумпинга = ⟨S g_B, g_B⟩, S = (A₀ + A₀ᵀ)/2 — симметричная часть
сужения оператора переноса; c_B = |⟨g_B, f*⟩| — косинус между π-ортонормированным центрированным индикатором блока и верхним собственным
вектором S. Семейства: случайные необратимые N = 6 (сид 2026), кирхгофовы циклические токи при θ_max на обратимой базе (сид 777),
обратимые θ = 0 (вырожденный контроль), оценённые цепи ЭЭГ (PCCA(2) против 300 случайных 2-блочных). По PREREG 2026-09-10."""
import numpy as np, json, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from cog01_lib import *
from scipy.stats import mannwhitneyu
B = '/home/claude'; OUT = f'{B}/ach01_results.json'; t0 = time.time(); res = {}; TOL = 1e-9

def basis(pi):
    n = len(pi); u = np.sqrt(pi); u = u / np.linalg.norm(u)
    Q, _ = np.linalg.qr(np.column_stack([u, np.eye(n)[:, :n - 1]]))
    if np.dot(Q[:, 0], u) < 0: Q[:, 0] *= -1
    return Q[:, 1:]

def auc(x, y):
    """AUC ранжирования x → y (Манна–Уитни); None, если один класс"""
    x = np.asarray(x, float); y = np.asarray(y, bool)
    if len(y) == 0 or y.all() or (~y).all(): return None
    return float(mannwhitneyu(x[y], x[~y]).statistic / (y.sum() * (~y).sum()))

def chain_stats(P, pi, parts):
    """по разбиениям: c_B, R_B = ⟨S g_B, g_B⟩, рождение (|λ₂| > ρ), λ₂ со знаком, верхняя оценка; проверки тождества и неравенств"""
    Bm = basis(pi); A0 = Bm.T @ sym_form(P, pi) @ Bm; S = (A0 + A0.T) / 2; ev, U = np.linalg.eigh(S); f = U[:, -1]
    lmax, l2S, lmin = float(ev[-1]), float(ev[-2] if len(ev) > 1 else ev[-1]), float(ev[0])
    rho = spectral_radius(A0); w = numerical_radius(A0); rows = []; viol_id = 0; viol_bd = 0
    for b in parts:
        b = np.asarray(b); ind = (b == b.min()).astype(float); h = ind - pi @ ind; v = np.sqrt(pi) * h; nv = np.linalg.norm(v)
        if nv < 1e-12: continue
        g = Bm.T @ (v / nv); c = abs(float(g @ f)); R = float(g @ S @ g)
        PY, _ = lump(P, pi, b); l2 = float(PY[0, 0] + PY[1, 1] - 1.0)  # λ₂ 2×2 стохастической матрицы, со знаком
        viol_id += int(abs(R - l2) > TOL)
        lo = c * c * lmax + (1 - c * c) * lmin; hi = c * c * lmax + (1 - c * c) * l2S
        viol_bd += int((R < lo - TOL) or (R > hi + TOL))
        rows.append((c, R, float(abs(l2) > rho + TOL), l2, hi))
    return dict(rho=rho, w=w, lmax=lmax, l2S=l2S, lmin=lmin, rows=np.array(rows, float), viol_id=viol_id, viol_bd=viol_bd)

def knob_chain(P0, pi, rng, ncyc=3):
    """кирхгофовы циклические токи на обратимой базе: G = K/π бездивергентен, π сохраняется; θ_max — из положительности"""
    n = len(P0); K = np.zeros((n, n))
    for _ in range(ncyc):
        L = int(rng.integers(3, min(6, n) + 1)); cyc = rng.permutation(n)[:L]
        amp = min(pi[cyc[i]] * P0[cyc[i], cyc[(i + 1) % L]] for i in range(L))
        for i in range(L):
            a, b = cyc[i], cyc[(i + 1) % L]; K[a, b] += amp; K[b, a] -= amp
    G = K / pi[:, None]
    with np.errstate(divide='ignore', invalid='ignore'):
        th = np.where(G < -1e-15, -P0 / G, np.inf)
    thm = float(th.min()); P = np.maximum(P0 + thm * G, 0.0); P /= P.sum(1, keepdims=True); return P, thm

def family(chains, parts, label):
    per = []; pooled_c = []; pooled_b = []; per_auc = []; argmax_hit = []; vid = vbd = 0; cmin_born = []
    for P, pi in chains:
        st = chain_stats(P, pi, parts); vid += st['viol_id']; vbd += st['viol_bd']; r = st['rows']; born = r[:, 2] > 0.5
        nb = int(born.sum()); per.append((float(r[:, 0].max()), nb, st['rho'], st['w'], st['lmax'], st['l2S'], float(r[:, 4].max())))
        if nb > 0:
            pooled_c.extend(r[:, 0]); pooled_b.extend(born); a = auc(r[:, 0], born); per_auc.append(a if a is not None else np.nan)
            argmax_hit.append(bool(born[int(np.argmax(r[:, 0]))])); d = st['lmax'] - st['l2S']
            cmin_born.append(float(np.sqrt(max(0.0, (st['rho'] - st['l2S']) / d))) if d > 1e-12 else 1.0)
    per = np.array(per, float); cmax, nb, rho, w, lmax, l2S, himax = per.T; chain_born = nb > 0; possible = lmax > rho + TOL
    pooled_c = np.array(pooled_c); pooled_b = np.array(pooled_b, bool); half = len(chains) // 2; hp = len(pooled_c) // 2
    out = dict(n_chains=len(chains), n_parts=len(parts), viol_identity=int(vid), viol_bounds=int(vbd), frac_chains_birth=float(chain_born.mean()), n_births=int(nb.sum()),
               auc_c_birth_pooled=auc(pooled_c, pooled_b), auc_c_birth_per_chain_median=(float(np.nanmedian(per_auc)) if per_auc else None),
               halves_auc_c_birth=([auc(pooled_c[:hp], pooled_b[:hp]), auc(pooled_c[hp:], pooled_b[hp:])] if len(pooled_c) else None),
               frac_argmax_c_is_birth=(float(np.mean(argmax_hit)) if argmax_hit else None),
               auc_cmax_chain=auc(cmax, chain_born), halves_auc_cmax=[auc(cmax[:half], chain_born[:half]), auc(cmax[half:], chain_born[half:])],
               frac_possible=float(possible.mean()), frac_born_among_possible=(float(chain_born[possible].mean()) if possible.any() else None),
               auc_cmax_within_possible=(auc(cmax[possible], chain_born[possible]) if possible.sum() > 1 else None),
               auc_lmaxS_minus_rho_chain=auc(lmax - rho, chain_born), auc_hi_chain=auc(himax, chain_born),
               cmax_born_median=(float(np.median(cmax[chain_born])) if chain_born.any() else None), cmax_unborn_median=(float(np.median(cmax[~chain_born])) if (~chain_born).any() else None),
               cmin_born_median=(float(np.median(cmin_born)) if cmin_born else None), cmin_born_p90=(float(np.percentile(cmin_born, 90)) if cmin_born else None))
    print(label, json.dumps(out, default=float, ensure_ascii=False), f'[{time.time()-t0:.0f}s]', flush=True); return out

parts = all_bipartitions(6); rng = np.random.default_rng(2026)
res['random_n6'] = family([(P, stationary(P)) for P in (random_chain(6, rng) for _ in range(2000))], parts, 'случайные N=6')
rng = np.random.default_rng(777); knob = []; rev = []; thms = []
for _ in range(200):
    P0 = random_reversible(6, rng); pi0 = stationary(P0); Pk, thm = knob_chain(P0, pi0, rng); thms.append(thm); knob.append((Pk, stationary(Pk))); rev.append((P0, pi0))
res['knob_thetamax'] = family(knob, parts, 'ручка θ_max'); res['knob_thetamax']['theta_max_median'] = float(np.median(thms))
res['reversible_theta0'] = family(rev, parts, 'обратимые θ=0 (вырожденный контроль)')
json.dump(res, open(OUT, 'w'), default=float)

from archive_loaders import series
from mol_levels_lib import microstates
from deeptime.markov import TransitionCountEstimator
from deeptime.markov.msm import MaximumLikelihoodMSM
E = {}
for name, F, tau, k, group in series(('eeg',)):
    lab = microstates(F, k, seed=0)
    cnt = TransitionCountEstimator(lagtime=tau, count_mode='sliding').fit_fetch(lab.astype(int)).submodel_largest()
    msm = MaximumLikelihoodMSM(reversible=False).fit(cnt).fetch_model(); msr = MaximumLikelihoodMSM(reversible=True).fit(cnt).fetch_model()
    P = np.asarray(msm.transition_matrix); pi = np.asarray(msm.stationary_distribution); pcca = np.asarray(msr.pcca(2).assignments)
    rng = np.random.default_rng(1); rand = []
    while len(rand) < 300:
        b = rng.integers(0, 2, len(P))
        if len(np.unique(b)) >= 2: rand.append(b)
    st = chain_stats(P, pi, [pcca] + rand); r = st['rows']; cp, Rp, bp = float(r[0, 0]), float(r[0, 1]), bool(r[0, 2] > 0.5); cr = r[1:, 0]; q = float(np.mean(cr < cp))
    d = st['lmax'] - st['l2S']; cmin = (float(np.sqrt(max(0.0, (st['rho'] - st['l2S']) / d))) if d > 1e-12 else None)
    E[name] = dict(n=int(len(P)), rho=st['rho'], w=st['w'], lmax=st['lmax'], l2S=st['l2S'], c_pcca=cp, l2_pcca=Rp, birth_pcca=bp, q_pcca=q, c_rand_p95=float(np.percentile(cr, 95)), c_rand_max=float(cr.max()),
                   c_rand_median=float(np.median(cr)), n_birth_rand=int(r[1:, 2].sum()), cmin_birth=cmin, viol_identity=st['viol_id'], viol_bounds=st['viol_bd'])
    print(f"{name:16s} k={len(P)} ρ {st['rho']:.3f} λmax(S) {st['lmax']:.3f} λ₂(S) {st['l2S']:.3f} c_min {cmin} | PCCA: c {cp:.3f} λ₂ {Rp:.3f} рождение {bp} квантиль {q:.3f} | случайные: медиана {E[name]['c_rand_median']:.3f} p95 {E[name]['c_rand_p95']:.3f} max {E[name]['c_rand_max']:.3f} рождений {E[name]['n_birth_rand']} | нарушений {st['viol_id']}/{st['viol_bd']} [{time.time()-t0:.0f}s]", flush=True)
res['eeg'] = E
R6, Kb, Rv = res['random_n6'], res['knob_thetamax'], res['reversible_theta0']; nE = len(E); n_q95 = int(sum(e['q_pcca'] >= 0.95 for e in E.values()))
viol = sum(x['viol_identity'] + x['viol_bounds'] for x in (R6, Kb, Rv)) + sum(e['viol_identity'] + e['viol_bounds'] for e in E.values())
ge = lambda v, t: (v is not None) and (v >= t); le = lambda v, t: (v is not None) and (v <= t)
res['verdict'] = dict(PA1=dict(random=R6['auc_c_birth_pooled'], knob=Kb['auc_c_birth_pooled'], ok=ge(R6['auc_c_birth_pooled'], 0.85) and ge(Kb['auc_c_birth_pooled'], 0.85)),
                      PA2=dict(random=R6['auc_cmax_chain'], knob=Kb['auc_cmax_chain'], ok=ge(R6['auc_cmax_chain'], 0.8) and ge(Kb['auc_cmax_chain'], 0.8)),
                      PA3=dict(n_q95=n_q95, n=nE, ok=n_q95 >= 20, n_birth_pcca=int(sum(e['birth_pcca'] for e in E.values()))), PA4=dict(violations=int(viol), ok=viol == 0),
                      K0=viol > 0, K1=le(R6['auc_c_birth_pooled'], 0.6) or le(Kb['auc_c_birth_pooled'], 0.6), K2=le(R6['auc_cmax_chain'], 0.6) or le(Kb['auc_cmax_chain'], 0.6), K3=n_q95 <= 12,
                      reversible_births=Rv['n_births'], reversible_cmax_median=Rv['cmax_unborn_median'])
json.dump(res, open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps(res['verdict'], default=float, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s', flush=True)
