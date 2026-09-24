"""MOL-004 — ramp hysteresis vs leg duration (fresh seeds 331-335). Per PREREG (2026-09-03)."""
import numpy as np, sys, json, time
sys.path.insert(0,'/home/claude'); from lj13 import *; from mol_levels_lib import *
t0=time.time(); out={}
def binned_mid(T, Sl, width):
    edges=np.arange(0.20,0.3601,width); c=0.5*(edges[1:]+edges[:-1])
    f=np.array([Sl[(T>=a)&(T<b)].mean() if np.any((T>=a)&(T<b)) else np.nan for a,b in zip(edges[:-1],edges[1:])])
    ok=~np.isnan(f); cc=c[ok]; fi=np.maximum.accumulate(f[ok])
    if len(fi)<3 or fi[0]>=0.5 or fi[-1]<0.5: return None
    i=np.flatnonzero(fi>=0.5)[0]; x0,x1,y0,y1=cc[i-1],cc[i],fi[i-1],fi[i]
    return float(x0+(0.5-y0)/(y1-y0)*(x1-x0)) if y1!=y0 else float(x1)
for seed in (331,332,333,334,335):
    r=simulate(0.28,seed,1000000,rec_every=50); Ds=np.sort(r['D'][400:],axis=1)
    model,lab=microstates_fit(Ds,30,seed=0); L=find_levels(lab,30,16); mom=L['macro_of_micro']
    Ep=r['Ep'][400:]; S=L['S']
    if L['n_levels']<2: out[str(seed)]=dict(unreadable=True); print(seed,'no two levels at 0.28'); continue
    liq=int(np.argmax([Ep[S==s].mean() for s in range(L['n_levels'])])); res={}
    for leg_tu in (100,50,25):
        steps=int(2*leg_tu/0.005)
        def Ts(s, steps=steps):
            half=steps//2
            return 0.20+0.16*(s/half) if s<half else 0.36-0.16*((s-half)/half)
        rr=simulate(0.20,seed+1000,steps,rec_every=5,Tsched=Ts)
        lab2=assign(np.sort(rr['D'],axis=1),model); Sl=(mom[lab2]==liq).astype(int); half=len(Sl)//2
        width=0.01 if leg_tu>=50 else 0.02
        Tm=binned_mid(rr['T'][:half],Sl[:half],width); Tf=binned_mid(rr['T'][half:],Sl[half:],width)
        res[str(leg_tu)]=dict(Tm=Tm,Tf=Tf,dT=None if Tm is None or Tf is None else Tm-Tf)
    out[str(seed)]=res; print(seed, {k:(None if v['dT'] is None else round(v['dT'],3)) for k,v in res.items()}, f"[{time.time()-t0:.0f}s]", flush=True)
    json.dump(out,open('/home/claude/mol004_results.json','w'),indent=1)
# verdicts
d25=[out[s]['25']['dT'] for s in out if 'unreadable' not in out[s] and out[s]['25']['dT'] is not None]
ok_a=sum(1 for d in d25 if d>=0.03)>=4; kill_a=sum(1 for d in d25 if abs(d)<0.02)>=3
med={leg: float(np.median([out[s][str(leg)]['dT'] for s in out if 'unreadable' not in out[s] and out[s][str(leg)]['dT'] is not None])) for leg in (100,50,25)}
med[250]=-0.010  # MOL-002 median over 5 seeds (ramp arm), recorded in PREREG
ok_b = med[250] < med[100] < med[50] < med[25]; kill_b = med[25] <= med[100]
V=dict(PM7a=dict(ok=bool(ok_a),killed=bool(kill_a),d25=d25),PM7b=dict(ok=bool(ok_b),killed=bool(kill_b),medians=med)); out['verdicts']=V
json.dump(out,open('/home/claude/mol004_results.json','w'),indent=1)
for k,v in V.items(): print(k,'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else 'не установлен'), {kk:vv for kk,vv in v.items() if kk not in ('ok','killed')})
