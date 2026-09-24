"""UNI-T2 часть d — часы смерти гроккинга по ступени wd 3e-4 -> 3e-3, 8 свежих сидов. Per PREREG (2026-09-04)."""
import json, time, numpy as np
exec(open("/home/claude/grok_cal.py").read().split("t0 = time.time()")[0])
def run_switch(seed, wd0, t_switch, wd1, steps, lr=10.0, D=512, rec_every=2):
    (Xtr, Ytr), (Xte, Yte) = make_data(seed)
    rng = np.random.default_rng(seed + 7)
    W1 = rng.normal(0, 1/np.sqrt(2*P), (2*P, D)); W2 = rng.normal(0, 1/np.sqrt(D), (D, P))
    n = len(Xtr); hist = []
    for t in range(steps):
        wd = wd0 if t < t_switch else wd1
        H = Xtr @ W1; A = H*H; Out = A @ W2; G = (Out - Ytr)/n
        gW2 = A.T @ G; gA = G @ W2.T; gH = 2*H*gA; gW1 = Xtr.T @ gH
        W1 -= lr*(gW1 + wd*W1); W2 -= lr*(gW2 + wd*W2)
        if t % rec_every == 0:
            Hte = Xte @ W1; Ote = (Hte*Hte) @ W2
            hist.append((t, float((Out.argmax(1)==Ytr.argmax(1)).mean()), float((Ote.argmax(1)==Yte.argmax(1)).mean())))
    return np.array(hist)
t0=time.time(); out={}
for sd in range(431,439):
    h=run_switch(sd, 3e-4, 1000, 3e-3, 4000)
    pre=h[h[:,0]<1000]; born=bool((pre[:,2]>=0.5).any())
    post=h[h[:,0]>=1000]; v=post[:,2]
    td=int(post[np.flatnonzero(v<0.5)[0],0])-1000 if (v<0.5).any() else None
    out[str(sd)]=dict(born_before_switch=born, t_death_from_switch=td, val_final=float(v[-1]), val_min=float(v.min()))
    print(f"сид {sd}: рождён до ступени {born}; смерть через {td} шагов; val_final {v[-1]:.2f} [{time.time()-t0:.0f}s]",flush=True)
    json.dump(out,open('/home/claude/unit2d_results.json','w'),indent=1)
td=[o['t_death_from_switch'] for o in out.values() if o['t_death_from_switch'] is not None and o['born_before_switch']]
cv=float(np.std(td,ddof=1)/np.mean(td)) if len(td)>=5 else None
out['summary']=dict(n=len(td),t_death=td,mean=float(np.mean(td)) if td else None,cv_death=cv,cv_birth_ref=0.020)
json.dump(out,open('/home/claude/unit2d_results.json','w'),indent=1)
print("CV_death =",cv,"n =",len(td))
