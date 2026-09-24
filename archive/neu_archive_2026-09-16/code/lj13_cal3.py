import numpy as np, sys, time, json
sys.path.insert(0,'/home/claude'); from lj13 import *
t0=time.time(); out={}
def mid_q6(T,Q,win,thr=0.45):
    half=len(Q)//2; sol=(np.convolve(Q,np.ones(4)/4,'same')>thr).astype(float); f=1-np.convolve(sol,np.ones(win)/win,'same')
    iu=np.flatnonzero(f[:half]>=0.5); idn=np.flatnonzero(f[half:]<=0.5)
    return (float(T[iu[0]]) if len(iu) else None, float(T[half+idn[0]]) if len(idn) else None)
# Q6 reference values at fixed T (solid 0.22 / liquid 0.36)
for T in (0.22,0.36):
    r=simulate(T,101,200000,rec_every=100,want_q6=True); out[f"q6_T{T}"]=[float(np.median(r['Q'])), float(np.quantile(r['Q'],0.1)), float(np.quantile(r['Q'],0.9))]
    print(T, out[f"q6_T{T}"], f"[{time.time()-t0:.0f}s]", flush=True)
for steps,name,win in ((3000000,'slow',200),(300000,'fast10',100),(100000,'fast30',50)):
    def Ts(s, steps=steps):
        half=steps//2
        return 0.20+0.16*(s/half) if s<half else 0.36-0.16*((s-half)/half)
    r=simulate(0.20,101,steps,rec_every=(100 if steps==3000000 else 20),Tsched=Ts,want_q6=True)
    Tm,Tf=mid_q6(r['T'],r['Q'],win); out[name]=dict(Tm=Tm,Tf=Tf)
    print(f"{name} ({steps*0.005/2:.0f} t.u./leg): Q6-midpoints heating {Tm} cooling {Tf} dT={None if Tm is None or Tf is None else round(Tm-Tf,3)} [{time.time()-t0:.0f}s]", flush=True)
    np.save(f'/home/claude/lj13_ramp_{name}_cal.npy', np.column_stack([r['T'],r['Ep'],r['Q']]))
json.dump(out, open('/home/claude/lj13_cal3.json','w'), indent=1)
