"""ACH-02 — относительная форма косинуса (c − c_min) и знак на свежих семействах: N = 6 (сид 4045), N = 8 (сид 4046), кирхгофовы токи (сид 4047),
обратимые (сид 4048). По PREREG 2026-09-14."""
import numpy as np, json, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from cog01_lib import stationary, sym_form, spectral_radius, lump, all_bipartitions, random_chain, random_reversible
from scipy.stats import mannwhitneyu
src = open('/home/claude/ach01_run.py').read()
exec(src.split("def chain_stats")[0].split("B = '/home/claude'")[1].split("\n", 1)[1])  # basis, auc
exec("def knob_chain" + src.split("def knob_chain")[1].split("def family")[0])
OUT = '/home/claude/ach02_results.json'; t0 = time.time(); TOL = 1e-9

def rows_for(P, pi, parts):
    Bm = basis(pi); A0 = Bm.T @ sym_form(P, pi) @ Bm; S = (A0 + A0.T) / 2; ev, U = np.linalg.eigh(S); fmax, fmin = U[:, -1], U[:, 0]
    lmax, l2S, lmin, lpen = float(ev[-1]), float(ev[-2]), float(ev[0]), float(ev[1]); rho = spectral_radius(A0); out = []
    dpos = lmax - l2S; cpmin = float(np.sqrt(max(0.0, (rho - l2S) / dpos))) if dpos > 1e-12 else None
    dneg = -lmin + lpen; cnmin = float(np.sqrt(max(0.0, (rho + lpen) / dneg))) if dneg > 1e-12 else None
    for b in parts:
        b = np.asarray(b); ind = (b == b.min()).astype(float); h = ind - pi @ ind; v = np.sqrt(pi) * h; nv = np.linalg.norm(v)
        if nv < 1e-12: continue
        g = Bm.T @ (v / nv); cp = abs(float(g @ fmax)); cn = abs(float(g @ fmin)); R = float(g @ S @ g)
        PY, _ = lump(P, pi, b); l2 = float(PY[0, 0] + PY[1, 1] - 1.0); viol = int(abs(R - l2) > TOL)
        lo = cp * cp * lmax + (1 - cp * cp) * lmin; hi = cp * cp * lmax + (1 - cp * cp) * l2S; viol += int(R < lo - TOL or R > hi + TOL)
        out.append(dict(cp=cp, cn=cn, rp=(cp - cpmin) if cpmin is not None else None, rn=(cn - cnmin) if cnmin is not None else None, posb=bool(l2 > rho + TOL), negb=bool(l2 < -rho - TOL),
                        pos_possible=bool(lmax > rho + TOL), neg_possible=bool(-lmin > rho + TOL), viol=viol))
    return out

def family(chains, parts, label):
    R = [r for P, pi in chains for r in rows_for(P, pi, parts)]; viol = sum(r['viol'] for r in R)
    pp = [r for r in R if r['pos_possible'] and r['rp'] is not None]; nn = [r for r in R if r['neg_possible'] and r['rn'] is not None]
    def A(rs, key, lab):
        x = np.array([r[key] for r in rs], float); y = np.array([r[lab] for r in rs]); h = len(rs) // 2
        return dict(auc=auc(x, y), halves=[auc(x[:h], y[:h]), auc(x[h:], y[h:])], n=len(rs), n_events=int(y.sum()))
    out = dict(n_rows=len(R), viol=int(viol), pos_rel=A(pp, 'rp', 'posb'), pos_abs=A(pp, 'cp', 'posb'), neg_rel=A(nn, 'rn', 'negb'), neg_abs=A(nn, 'cn', 'negb'),
               n_pos_births=int(sum(r['posb'] for r in R)), n_neg_births=int(sum(r['negb'] for r in R)))
    print(label, json.dumps(out, ensure_ascii=False), f'[{time.time()-t0:.0f}s]', flush=True); return out

res = {}
rng = np.random.default_rng(4045); res['n6'] = family([(P, stationary(P)) for P in (random_chain(6, rng) for _ in range(2000))], all_bipartitions(6), 'N=6 свежие')
rng = np.random.default_rng(4046); res['n8'] = family([(P, stationary(P)) for P in (random_chain(8, rng) for _ in range(500))], all_bipartitions(8), 'N=8')
rng = np.random.default_rng(4047); kn = []
for _ in range(300):
    P0 = random_reversible(6, rng); pi0 = stationary(P0); Pk, thm = knob_chain(P0, pi0, rng); kn.append((Pk, stationary(Pk)))
res['knob'] = family(kn, all_bipartitions(6), 'токи θ_max')
rng = np.random.default_rng(4048); res['rev'] = family([(P, stationary(P)) for P in (random_reversible(6, rng) for _ in range(200))], all_bipartitions(6), 'обратимые')
g = lambda d, k: (d[k]['auc'] or 0)
V = dict(K0=bool(res['rev']['n_pos_births'] + res['rev']['n_neg_births'] > 0 or sum(res[k]['viol'] for k in res) > 0),
         PA1=dict(n6=g(res['n6'], 'pos_rel'), n8=g(res['n8'], 'pos_rel'), knob=g(res['knob'], 'pos_rel'), halves=[res['n6']['pos_rel']['halves'], res['n8']['pos_rel']['halves'], res['knob']['pos_rel']['halves']],
                  ok=g(res['n6'], 'pos_rel') >= 0.9 and g(res['n8'], 'pos_rel') >= 0.85 and g(res['knob'], 'pos_rel') >= 0.9 and all((h or 0) >= 0.85 for h in res['n6']['pos_rel']['halves']) and all((h or 0) >= 0.8 for h in res['n8']['pos_rel']['halves']) and all((h or 0) >= 0.85 for h in res['knob']['pos_rel']['halves'])),
         PA2=dict(n6=g(res['n6'], 'neg_rel'), knob=g(res['knob'], 'neg_rel'), ok=g(res['n6'], 'neg_rel') >= 0.85 and g(res['knob'], 'neg_rel') >= 0.85),
         PA3=dict(n6_abs=g(res['n6'], 'pos_abs'), n8_abs=g(res['n8'], 'pos_abs'), knob_abs=g(res['knob'], 'pos_abs'), n6_negabs=g(res['n6'], 'neg_abs'), ok=max(g(res['n6'], 'pos_abs'), g(res['n8'], 'pos_abs'), g(res['knob'], 'pos_abs')) <= 0.75),
         K1=g(res['n6'], 'pos_rel') <= 0.75, K2=g(res['n6'], 'neg_rel') <= 0.7, K3=max(g(res['n6'], 'pos_abs'), g(res['n8'], 'pos_abs'), g(res['knob'], 'pos_abs')) >= 0.85)
res['verdict'] = V; json.dump(res, open(OUT, 'w'), default=float); print('ВЕРДИКТ', json.dumps(V, default=float, ensure_ascii=False)); print('ГОТОВО', f'{time.time()-t0:.0f}s')
