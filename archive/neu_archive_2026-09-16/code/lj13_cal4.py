"""Ramp hysteresis with level-finder-defined states (spent seed 101)."""
import numpy as np, sys, time, json
sys.path.insert(0,'/home/claude'); from lj13 import *; from mol_levels_lib import *
t0=time.time()
r=simulate(0.28,101,1000000,rec_every=50); Ds=np.sort(r['D'][400:],axis=1)
model,lab=microstates_fit(Ds,30,seed=0); L=find_levels(lab,30,16); mom=L['macro_of_micro']
Ep=r['Ep'][400:]; S=L['S']; liq=int(np.argmax([Ep[S==s].mean() for s in range(L['n_levels'])])); print("levels", L['n_levels'], "liquid macro", liq, f"[{time.time()-t0:.0f}s]", flush=True)
def midpoints(T, Sl, win):
    half=len(Sl)//2; f=np.convolve(Sl.astype(float),np.ones(win)/win,'same')
    iu=np.flatnonzero(f[:half]>=0.5); idn=np.flatnonzero(f[half:]<=0.5)
    return (float(T[iu[0]]) if len(iu) else None, float(T[half+idn[0]]) if len(idn) else None)
out={}
for steps,name,rec,win in ((3000000,'slow',50,400),(300000,'fast10',10,200),(100000,'fast30',10,60)):
    def Ts(s, steps=steps):
        half=steps//2
        return 0.20+0.16*(s/half) if s<half else 0.36-0.16*((s-half)/half)
    rr=simulate(0.20,101,steps,rec_every=rec,Tsched=Ts)
    lab2=assign(np.sort(rr['D'],axis=1),model); Sl=(mom[lab2]==liq).astype(int)
    Tm,Tf=midpoints(rr['T'],Sl,win); out[name]=dict(Tm=Tm,Tf=Tf,dT=None if Tm is None or Tf is None else Tm-Tf)
    print(f"{name} ({steps*0.005/2:.0f} t.u./leg): midpoints heating {Tm} cooling {Tf} dT={out[name]['dT']} [{time.time()-t0:.0f}s]", flush=True)
json.dump(out, open('/home/claude/lj13_cal4.json','w'), indent=1)
