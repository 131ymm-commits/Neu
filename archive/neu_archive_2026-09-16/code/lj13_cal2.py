import numpy as np, sys, time, json
sys.path.insert(0,'/home/claude'); from lj13 import *; from mol_levels_lib import *
t0=time.time(); out={}
for T in (0.18, 0.22, 0.25, 0.32):
    r=simulate(T, 101, 1000000, rec_every=50); D=r['D'][400:]; Ds=np.sort(D,axis=1); Ep=r['Ep'][400:]
    lab=microstates(Ds, 30, seed=0); L=find_levels(lab,30,16); S=L['S']
    info=dict(its=L['its'][:4].tolist(), ratios=L['ratios'][:3].tolist(), n=L['n_levels'])
    if L['n_levels']>=2:
        Sc=committed(S,8); seg,st=dwell_times(Sc)
        info['frac']=[float(np.mean(Sc==s)) for s in range(L['n_levels'])]
        info['Emean']=[float(Ep[Sc==s].mean()) for s in range(L['n_levels'])]
        info['dwell']=[(int(np.sum(st==s)), float(seg[st==s].mean()*0.25), float(seg[st==s].std(ddof=1)/seg[st==s].mean()) if np.sum(st==s)>2 else None) for s in range(L['n_levels'])]
        info['psi']=psi_prime(S,D,16)[0]
    out[str(T)]=info
    print(T, info, f"[{time.time()-t0:.0f}s]", flush=True)
steps=3000000
def Ts(s):
    half=steps//2
    return 0.20+0.16*(s/half) if s<half else 0.36-0.16*((s-half)/half)
r=simulate(0.20, 101, steps, rec_every=50, Tsched=Ts); Ep=r['Ep']; T=r['T']
w=40; Es=np.convolve(Ep,np.ones(w)/w,'same'); dip=-35.5; half=len(Ep)//2
def first_committed(mask, persist=200):
    idx=np.flatnonzero(mask)
    for i in idx:
        if mask[i:i+persist].all(): return int(i)
    return None
iu=first_committed(Es[:half]>dip); idn=first_committed(Es[half:]<dip)
Tm=float(T[iu]) if iu is not None else None; Tf=float(T[half+idn]) if idn is not None else None
print(f"ramp: T_melt(heating)={Tm} T_freeze(cooling)={Tf} dT={None if Tm is None or Tf is None else round(Tm-Tf,3)} [{time.time()-t0:.0f}s]", flush=True)
out['ramp']=dict(Tm=Tm,Tf=Tf); np.save('/home/claude/lj13_ramp_cal.npy', np.column_stack([T,Ep]))
json.dump(out, open('/home/claude/lj13_cal2.json','w'), indent=1)
