"""Ramp hysteresis (spent seed 101), finder-defined states, T-binned liquid fraction (not first crossing)."""
import numpy as np, sys, time, json
sys.path.insert(0,'/home/claude'); from lj13 import *; from mol_levels_lib import *
t0=time.time()
r=simulate(0.28,101,1000000,rec_every=50); Ds=np.sort(r['D'][400:],axis=1)
model,lab=microstates_fit(Ds,30,seed=0); L=find_levels(lab,30,16); mom=L['macro_of_micro']
Ep=r['Ep'][400:]; S=L['S']; liq=int(np.argmax([Ep[S==s].mean() for s in range(L['n_levels'])]))
def binned_mid(T, Sl, edges=np.arange(0.20,0.3601,0.01)):
    c=0.5*(edges[1:]+edges[:-1]); f=np.array([Sl[(T>=a)&(T<b)].mean() if np.any((T>=a)&(T<b)) else np.nan for a,b in zip(edges[:-1],edges[1:])])
    # midpoint by interpolation of the monotone-smoothed fraction
    ok=~np.isnan(f); cc=c[ok]; ff=f[ok]
    # isotonic (increasing in T) via cumulative max
    fi=np.maximum.accumulate(ff)
    if fi[0]>=0.5 or fi[-1]<0.5: return None, cc, ff
    i=np.flatnonzero(fi>=0.5)[0]; x0,x1,y0,y1=cc[i-1],cc[i],fi[i-1],fi[i]
    return float(x0+(0.5-y0)/(y1-y0)*(x1-x0)), cc, ff
out={}
for steps,name,rec in ((3000000,'slow',50),(300000,'fast10',10),(100000,'fast30',10)):
    def Ts(s, steps=steps):
        half=steps//2
        return 0.20+0.16*(s/half) if s<half else 0.36-0.16*((s-half)/half)
    rr=simulate(0.20,101,steps,rec_every=rec,Tsched=Ts)
    lab2=assign(np.sort(rr['D'],axis=1),model); Sl=(mom[lab2]==liq).astype(int); half=len(Sl)//2
    Tm,c1,f1=binned_mid(rr['T'][:half],Sl[:half]); Tf,c2,f2=binned_mid(rr['T'][half:],Sl[half:])
    out[name]=dict(Tm=Tm,Tf=Tf,dT=None if Tm is None or Tf is None else Tm-Tf, f_heat=np.round(f1,2).tolist(), f_cool=np.round(f2,2).tolist())
    print(f"{name} ({steps*0.005/2:.0f} t.u./leg): T_mid heating {Tm} cooling {Tf} dT={out[name]['dT']}\n   heat f: {np.round(f1,2).tolist()}\n   cool f: {np.round(f2,2).tolist()} [{time.time()-t0:.0f}s]", flush=True)
json.dump(out, open('/home/claude/lj13_cal5.json','w'), indent=1)
