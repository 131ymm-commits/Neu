"""GROK-LLC — LLC (devinterp SGLD, γ=1000, ε=1e-5) вдоль обучения x²-сети; излом против t_grok. По PREREG (2026-09-04)."""
import numpy as np, json, os, sys, time, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '/home/claude')
import grok_llc_lib as G
OUT = '/home/claude/grok_llc_results.json'; res = json.load(open(OUT)) if os.path.exists(OUT) else {}
t0 = time.time(); EVERY = 10; STEPS = 450; EPS = 1e-5; GAM = 1000.0; DRAWS = 400; BURN = 100

def run_one(name, ds, is_, wd):
    if name in res and 'llc' in res[name]: print('пропуск', name); return
    G.WD = wd
    R = G.train_ckpt(ds, is_, steps=STEPS, every=EVERY)
    ts = sorted(R['ck']); lam = []; sig = []
    for t in ts:
        c = R['ck'][t]
        o = G.llc(c['W1'], c['W2'], R['Xtr'], R['Ytr'], eps=EPS, gamma=GAM, draws=DRAWS, chains=2, burn=BURN, seed=0)
        lam.append(o['llc']); sig.append(o['std'])
    lam = np.array(lam); ts = np.array(ts)
    # излом: D(t) = λ̂(t+30) − λ̂(t); окно 3 чекпоинта; ограничение t ≤ t_grok + 100 (если t_grok есть)
    tmax = (R['t_grok'] + 100) if R['t_grok'] is not None else STEPS
    D = lam[3:] - lam[:-3]; tt = ts[:-3]; m = tt + 15 <= tmax
    i = int(np.argmax(np.abs(D[m]))); t_llc = float(tt[m][i] + 15); Dm = float(D[m][i]); sigma = float(np.mean(sig))
    res[name] = dict(data_seed=ds, init_seed=is_, wd=wd, t_grok=R['t_grok'], ts=ts.tolist(), llc=lam.tolist(), sig=[float(x) for x in sig],
                     acc=R['acc'].tolist(), t_llc=t_llc, D=Dm, sigma=sigma, readable=bool(abs(Dm) > 3 * sigma))
    json.dump(res, open(OUT, 'w'), indent=1, default=float)
    print(f"{name}: t_grok {R['t_grok']} t_LLC {t_llc:.0f} D {Dm:+.2f} σ {sigma:.2f} читаем {abs(Dm) > 3 * sigma} | λ̂: {np.round(lam[::9], 1).tolist()} [{time.time()-t0:.0f}s]", flush=True)

for k in range(8): run_one(f'grok_{641+k}', 641 + k, 648 + k, 3e-4)
for k in range(4): run_one(f'ctrl_{641+k}', 641 + k, 648 + k, 0.0)

# вердикты
g = [res[f'grok_{641+k}'] for k in range(8)]; c = [res[f'ctrl_{641+k}'] for k in range(4)]
ok = [r for r in g if r['t_grok'] is not None]
rel = [abs(r['t_llc'] - r['t_grok']) / r['t_grok'] for r in ok]
l1 = sum(1 for x in rel if x <= 0.10) >= 6; k1 = sum(1 for x in rel if x > 0.25) >= 4
drops = sum(1 for r in ok if r['D'] < 0); rises = sum(1 for r in ok if r['D'] > 0)
l2 = 'падение' if drops >= 7 else ('рост' if rises >= 7 else 'смешанный')
order = [(r['t_llc'] - r['t_grok']) / r['t_grok'] for r in ok]; l3 = sum(1 for x in order if -0.15 <= x <= 0.05) >= 6
k2 = sum(1 for r in g if not r['readable']) >= 4
medD = float(np.median([abs(r['D']) for r in g])); l4 = sum(1 for r in c if abs(r['D']) < medD / 3) >= 3; k3 = sum(1 for r in c if abs(r['D']) >= medD / 3) >= 2
V = dict(PL1=dict(ok=l1, K1=k1, rel=[round(x, 3) for x in rel]), PL2=dict(sign=l2, drops=drops, rises=rises), PL3=dict(ok=l3, order=[round(x, 3) for x in order]),
         PL4=dict(ok=l4, K3=k3, medD_grok=medD, D_ctrl=[round(r['D'], 2) for r in c]), K2=k2, censored=8 - len(ok))
res['verdicts'] = V; json.dump(res, open(OUT, 'w'), indent=1, default=float)
print('\n== ВЕРДИКТЫ ==')
for k, v in V.items(): print(k, v)
