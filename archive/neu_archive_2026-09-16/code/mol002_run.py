"""MOL-002 — LJ13 levels across T + ramp hysteresis. Per PREREG (frozen 2026-09-03)."""
import numpy as np, sys, json, time, os
sys.path.insert(0,'/home/claude'); from lj13 import *; from mol_levels_lib import *
CK='/home/claude/mol002_ckpt.json'; ck=json.load(open(CK)) if os.path.exists(CK) else {}
def save(): json.dump(ck,open(CK,'w'),indent=1,default=float)
t0=time.time(); mode=sys.argv[1]
def energy_labels(Ep):
    w=8; Es=np.convolve(Ep,np.ones(w)/w,'same'); h,e=np.histogram(Es,bins=50); c=0.5*(e[1:]+e[:-1]); hs=np.convolve(h,np.ones(3)/3,'same'); pk=np.argsort(hs)[::-1]
    i1=pk[0]; cand=[i for i in pk[1:] if abs(i-i1)>8]
    if not cand: return None
    i2=cand[0]; lo,hi=sorted([i1,i2]); dip=c[lo+np.argmin(hs[lo:hi+1])]; return (Es>dip).astype(int)
def analyze_T(seed,T):
    r=simulate(T,seed,1000000,rec_every=50); D=r['D'][400:]; Ds=np.sort(D,axis=1); Ep=r['Ep'][400:]
    model,lab=microstates_fit(Ds,30,seed=0); L=find_levels(lab,30,16); S=L['S']; n=L['n_levels']
    res=dict(n_levels=n, its=L['its'][:4].tolist(), ratios=L['ratios'][:3].tolist())
    if n>=2:
        labE=energy_labels(Ep)
        if labE is not None and n==2: res['purity']=float(max(np.mean(S==labE),np.mean(S!=labE)))
        pp,v,b=psi_prime(S,D,16); res['psi']=float(pp)
        rng=np.random.default_rng(0); nulls=[]
        for r_ in range(30):
            perm=rng.permutation(30); mm=np.zeros(30,int); mm[perm[:15]]=1; nulls.append(psi_prime(mm[lab],D,16)[0])
        res['null_p99']=float(np.quantile(nulls,0.99)); Ssh=S.copy(); rng.shuffle(Ssh); res['psi_shuffle']=float(psi_prime(Ssh,D,16)[0])
        Sc=committed(S,8); seg,st=dwell_times(Sc)
        res['cv']=[float(seg[st==s].std(ddof=1)/seg[st==s].mean()) if np.sum(st==s)>2 else None for s in range(n)]
        res['n_dwell']=[int(np.sum(st==s)) for s in range(n)]; res['fracs']=[float(np.mean(Sc==s)) for s in range(n)]
        res['Emean']=[float(Ep[S==s].mean()) for s in range(n)]
    return res, model, L, Ep
if mode=='scan':
    for seed in (301,302,303):
        for T in (0.18,0.22,0.25,0.28,0.36):
            key=f"scan_{seed}_{T}"
            if key in ck: continue
            res,_,_,_=analyze_T(seed,T); ck[key]=res; save()
            print(key, {k:(np.round(v,3).tolist() if isinstance(v,list) else (round(v,3) if isinstance(v,float) else v)) for k,v in res.items()}, f"[{time.time()-t0:.0f}s]", flush=True)
elif mode=='ramp':
    def binned_mid(T, Sl, edges=np.arange(0.20,0.3601,0.01)):
        c=0.5*(edges[1:]+edges[:-1]); f=np.array([Sl[(T>=a)&(T<b)].mean() if np.any((T>=a)&(T<b)) else np.nan for a,b in zip(edges[:-1],edges[1:])])
        ok=~np.isnan(f); cc=c[ok]; fi=np.maximum.accumulate(f[ok])
        if fi[0]>=0.5 or fi[-1]<0.5: return None
        i=np.flatnonzero(fi>=0.5)[0]; x0,x1,y0,y1=cc[i-1],cc[i],fi[i-1],fi[i]
        return float(x0+(0.5-y0)/(y1-y0)*(x1-x0))
    for seed in (311,312,313,314,315):
        key=f"ramp_{seed}"
        if key in ck: continue
        res,model,L,Ep=analyze_T(seed,0.28)
        if L['n_levels']<2: ck[key]=dict(unreadable='no two levels at 0.28'); save(); print(key,'unreadable',flush=True); continue
        S=L['S']; liq=int(np.argmax([Ep[S==s].mean() for s in range(L['n_levels'])])); mom=L['macro_of_micro']; out=dict(levels28=L['n_levels'])
        for steps,name,rec in ((3000000,'slow',50),(100000,'fast30',10)):
            def Ts(s, steps=steps):
                half=steps//2
                return 0.20+0.16*(s/half) if s<half else 0.36-0.16*((s-half)/half)
            rr=simulate(0.20,seed+1000,steps,rec_every=rec,Tsched=Ts)
            lab2=assign(np.sort(rr['D'],axis=1),model); Sl=(mom[lab2]==liq).astype(int); half=len(Sl)//2
            Tm=binned_mid(rr['T'][:half],Sl[:half]); Tf=binned_mid(rr['T'][half:],Sl[half:])
            out[name]=dict(Tm=Tm,Tf=Tf,dT=None if Tm is None or Tf is None else Tm-Tf)
        ck[key]=out; save(); print(key, out, f"[{time.time()-t0:.0f}s]", flush=True)
elif mode=='verdict':
    S=[ck[f"scan_{s}_0.28"] for s in (301,302,303)]
    ok1=all(r['n_levels']==2 and r['ratios'][0]>=3 and r.get('purity',0)>=0.8 for r in S); kill1=sum(1 for r in S if r['n_levels']==1 and r['ratios'][0]<1.5)>=2 or any(r.get('purity',1)<0.6 for r in S)
    ok2=all(r.get('psi',-1)>r.get('null_p99',9) for r in S); kill2=sum(1 for r in S if r.get('psi',-1)<=r.get('null_p99',9))>=2
    ok3=all(r.get('cv') and all(c is not None and 0.7<=c<=1.5 for c in r['cv']) for r in S); kill3=sum(1 for r in S if r.get('cv') and any(c is not None and c<=0.3 for c in r['cv']))>=2
    prof={s:[ck[f"scan_{s}_{T}"]['n_levels'] for T in (0.18,0.22,0.25,0.28,0.36)] for s in (301,302,303)}
    ok4=sum(1 for s in prof if prof[s]==[1,2,2,2,1])>=2; kill4=sum(1 for s in prof if prof[s][0]==2 and prof[s][4]==2)>=2 or sum(1 for s in prof if all(x==1 for x in prof[s]))>=2
    R=[ck[f"ramp_{s}"] for s in (311,312,313,314,315) if 'slow' in ck.get(f"ramp_{s}",{})]
    slow=[r['slow']['dT'] for r in R if r['slow']['dT'] is not None]; fast=[r['fast30']['dT'] for r in R if r['fast30']['dT'] is not None]
    ok5=sum(1 for d in slow if abs(d)<=0.015)>=4 and sum(1 for d in fast if d>=0.02)>=4; kill5=sum(1 for d in slow if d>=0.02)>=3 or sum(1 for d in fast if d<=0)>=3
    V=dict(PM1=dict(ok=ok1,killed=kill1),PM2=dict(ok=ok2,killed=kill2),PM3=dict(ok=ok3,killed=kill3),PM4=dict(ok=ok4,killed=kill4,profiles=prof),PM5=dict(ok=ok5,killed=kill5,slow=slow,fast=fast))
    ck['verdicts']=V; save()
    for k,v in V.items(): print(k,'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else 'не установлен'), {kk:vv for kk,vv in v.items() if kk not in ('ok','killed')})
print(f"[{time.time()-t0:.0f}s]")
