"""PTOL-01 — словарь наблюдаемых от скаляра до избытка на траекториях NET-01 (LJ13): VAMP на обучающей половине, проверка мод на
отложенной (ложные = не переживают), ранг уровня, ζ до и после чистки, VAMP-2 на отложенной. По PREREG 2026-09-08 (ночь)."""
import numpy as np, json, glob, os, sys, time, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
from deeptime.decomposition import VAMP
TAU = 2; K = 14; OUT = '/home/claude/ptol01_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}; t0 = time.time()

def p_rank1(z): m = len(z); g = z[0] / z.sum(); return float((1 - g) ** (m - 1))
def renyi(ts, tau):
    r = np.sort(np.asarray(ts))[::-1]; r = r[np.isfinite(r) & (r > tau)]
    if len(r) < 4: return None
    s = np.log(r[:-1] / r[1:]); k = np.arange(1, len(s) + 1); z = np.maximum(k * s, 1e-12); return dict(m=len(z), zeta=float(z[0] / z[1:].mean()), p=p_rank1(z))
def embed(x, m, step=1):
    n = len(x) - (m - 1) * step; return np.column_stack([x[i * step: i * step + n] for i in range(m)])
def rff(Xs, n_feat, seed):
    rng = np.random.default_rng(seed); d = Xs.shape[1]
    sub = Xs[rng.choice(len(Xs), 500, replace=False)]; med = np.median(np.linalg.norm(sub[:, None] - sub[None], axis=-1)); sigma = med / np.sqrt(2)
    W = rng.normal(0, 1 / sigma, (d, n_feat)); b = rng.uniform(0, 2 * np.pi, n_feat); return np.sqrt(2 / n_feat) * np.cos(Xs @ W + b)
def dictionaries(Ep, D):
    off = 3; Xd = (D - D.mean(0)) / (D.std(0) + 1e-9)
    out = {'D1_Epot': Ep[off:, None], 'D2_Epot_m4': embed(Ep, 4), 'D3_dist78': Xd[off:], 'D4_dist_lag': np.hstack([Xd[off:], Xd[off - 1: -1]])}   # все словари начинаются с кадра 3 (embed m=4 даёт строки для кадров 3..n−1)
    base = out['D4_dist_lag']; out['D5_D4_rff300'] = np.hstack([base, rff(Xd[off:], 300, 1)]); out['D6_D4_rff1000'] = np.hstack([base, rff(Xd[off:], 1000, 2)])
    n = min(len(v) for v in out.values()); return {k: v[:n] for k, v in out.items()}

def fit_eval(Xtr, Xte, ind_te, dim):
    vamp = VAMP(lagtime=TAU, dim=dim).fit(Xtr); mdl = vamp.fetch_model()
    sv = np.asarray(mdl.singular_values); shift = sv >= 0.9999          # сдвиговые артефакты лагового вложения (точная предсказуемость копий) — не динамика
    ts = mdl.timescales(); ts = np.where(np.isfinite(ts) & ~shift, ts, np.nan)
    Ftr = mdl.transform(Xtr); Fte = mdl.transform(Xte); nk = Fte.shape[1]
    t_test = np.zeros(nk); spur = np.zeros(nk, bool); vanish = np.zeros(nk, bool); cor = np.zeros(nk)
    for k in range(nk):
        g = Fte[:, k]; a = np.corrcoef(g[:-TAU], g[TAU:])[0, 1] if g.std() > 0 else 0.0
        t_test[k] = (-TAU / np.log(a)) if a > 0 else 0.0
        ok = bool(np.isfinite(ts[k]) and ts[k] > TAU)
        spur[k] = ok and (t_test[k] / ts[k] < 0.5)                      # замороженный критерий (PREREG)
        vanish[k] = ok and (t_test[k] <= TAU)                           # описательно: мода исчезает на отложенной половине
        cor[k] = abs(np.corrcoef(g, ind_te)[0, 1]) if (g.std() > 0 and ind_te.std() > 0) else 0.0
    r_ico = int(np.argmax(cor)) + 1 if cor.max() >= 0.3 else None
    tsK = ts[:K]; fin = np.isfinite(tsK); st = renyi(tsK[fin], TAU); surv = tsK[fin & ~spur[:K]]; stp = renyi(surv, TAU)
    tt = t_test[:K][fin & ~vanish[:K]]; stt = renyi(tt, TAU)                                   # описательно: ζ по шкалам отложенной половины
    try:
        mte = VAMP(lagtime=TAU, dim=dim).fit(Xte).fetch_model(); score = float(mdl.score(2, test_model=mte))
    except Exception as ex: score = None
    return dict(its=[float(x) for x in tsK], t_test=[float(x) for x in t_test[:K]], spur=[bool(x) for x in spur[:K]], n_spur=int(spur[:K].sum()), n_vanish=int(vanish[:K].sum()), n_shift=int(shift[:K].sum()),
                n_resolved=int(np.nansum(tsK > TAU)), r_ico=r_ico, corr_max=float(cor.max()), zeta=(st['zeta'] if st else None), m=(st['m'] if st else 0), p=(st['p'] if st else None),
                zeta_pruned=(stp['zeta'] if stp else None), m_pruned=(stp['m'] if stp else 0), zeta_test=(stt['zeta'] if stt else None), vamp2_test=score), mdl

def boot_PL(Xtr, dim, nb=30, block=200, seed=0):
    rng = np.random.default_rng(seed); n = len(Xtr); nblk = n // block; ps = []
    for b in range(nb):
        idx = np.concatenate([np.arange(s * block, (s + 1) * block) for s in rng.integers(0, nblk, nblk)])
        try:
            m = VAMP(lagtime=TAU, dim=dim).fit(Xtr[idx]).fetch_model(); tsb = m.timescales()[:K]; svb = np.asarray(m.singular_values)[:K]; st = renyi(tsb[np.isfinite(tsb) & (svb < 0.9999)], TAU)
            if st: ps.append(st['p'])
        except Exception: pass
    return (float(np.mean(np.array(ps) <= 0.05)) if ps else None, len(ps))

for fp in sorted(glob.glob('/home/claude/net01_T*_s*.npz')):
    name = os.path.basename(fp)[6:-4]
    if name in res: continue
    d = np.load(fp); Ep = d['Ep']; D = d['D'].astype(float); Eis = d['Eis']
    dicts = dictionaries(Ep, D); n = len(dicts['D3_dist78']); ind = (Eis[3:3 + n] <= -44.32).astype(float); h = n // 2
    r = dict(n=int(n), frac_ico=float(ind.mean()))
    print(f"{name}: кадров {n}, доля икосаэдра {ind.mean():.3f}", flush=True)
    for dk, X in dicts.items():
        dim = min(K, X.shape[1]); folds = []
        for fold, (tr, te) in enumerate(((slice(0, h), slice(h, n)), (slice(h, n), slice(0, h)))):
            e, _ = fit_eval(X[tr], X[te], ind[te], dim); e['fold'] = fold; folds.append(e)
        PL, nb = boot_PL(X[:h], dim)
        r[dk] = dict(N=int(X.shape[1]), folds=folds, PL_boot=PL, n_boot=nb, n_spur_mean=float(np.mean([f['n_spur'] for f in folds])), r_ico=[f['r_ico'] for f in folds],
                     zeta=[f['zeta'] for f in folds], zeta_pruned=[f['zeta_pruned'] for f in folds], vamp2_test=[f['vamp2_test'] for f in folds])
        f0 = folds[0]; r[dk]['n_vanish'] = [f['n_vanish'] for f in folds]; r[dk]['zeta_test'] = [f['zeta_test'] for f in folds]; r[dk]['n_shift'] = [f['n_shift'] for f in folds]
        print(f"  {dk:14s} N={X.shape[1]:5d} | ITS {np.round(f0['its'][:5], 1)} | тест-ITS {np.round(f0['t_test'][:5], 1)} | ложных {[f['n_spur'] for f in folds]}/{f0['n_resolved']} исчезли {[f['n_vanish'] for f in folds]} сдвиг {f0['n_shift']} | r_ico {[f['r_ico'] for f in folds]} (|corr| {f0['corr_max']:.2f}) | ζ {None if f0['zeta'] is None else round(f0['zeta'], 2)} → чистка {None if f0['zeta_pruned'] is None else round(f0['zeta_pruned'], 2)} | ζ_test {None if f0['zeta_test'] is None else round(f0['zeta_test'], 2)} | P_L {PL} | VAMP2 тест {[None if v is None else round(v, 2) for v in r[dk]['vamp2_test']]} [{time.time()-t0:.0f}s]", flush=True)
    # контроли: перестановка блоками по 10 на D6; D6 на 5 000 обучающих кадров
    X = dicts['D6_D4_rff1000']; rng = np.random.default_rng(0); nb10 = h // 10; perm = rng.permutation(nb10); idx = (perm[:, None] * 10 + np.arange(10)).ravel()
    e, _ = fit_eval(X[:h][idx], X[h:n], ind[h:n], K); r['D6_shuffled'] = dict(n_spur=e['n_spur'], n_resolved=e['n_resolved'], its=e['its'][:5], t_test=e['t_test'][:5])
    e5, _ = fit_eval(X[:5000], X[h:n], ind[h:n], K); r['D6_train5000'] = dict(n_spur=e5['n_spur'], n_resolved=e5['n_resolved'], zeta=e5['zeta'], zeta_pruned=e5['zeta_pruned'], vamp2_test=e5['vamp2_test'])
    print(f"  контроли: D6 перестановка — ложных {e['n_spur']}/{e['n_resolved']} (ITS {np.round(e['its'][:4], 1)}, тест {np.round(e['t_test'][:4], 1)}); D6 на 5 000 кадров — ложных {e5['n_spur']}/{e5['n_resolved']}, VAMP2 тест {None if e5['vamp2_test'] is None else round(e5['vamp2_test'], 2)}", flush=True)
    res[name] = r; json.dump(res, open(OUT, 'w'), indent=1, default=float)
print('готово', time.time() - t0)
