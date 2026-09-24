"""CORE-02 — birth-through-failed-attempt vs ramp speed (LJ13, 20 replicas/leg). Per PREREG (2026-09-03)."""
import numpy as np, sys, json, time
sys.path.insert(0,'/home/claude'); from lj13 import *; from mol_levels_lib import *
t0=time.time(); LEGS=[200,100,50,25]; NREP=20; PERSIST_TU=8.0  # committed visit must persist >=8 t.u.
# state model: fit at coexistence T=0.28 on a reference seed
ref=simulate(0.28,7,1000000,rec_every=50); Dref=np.sort(ref['D'][400:],axis=1)
model,lab=microstates_fit(Dref,30,seed=0); L=find_levels(lab,30,16); mom=L['macro_of_micro']
Ep=ref['Ep'][400:]; S=L['S']; liq=int(np.argmax([Ep[S==s].mean() for s in range(L['n_levels'])])) if L['n_levels']>=2 else 1
out={'meta':dict(n_levels=int(L['n_levels']),liq=liq)}
def first_attempt_unstable(Sl, persist_frames):
    # committed series; find first entry into liquid; is there a return to crystal before the FINAL sustained liquid?
    c=committed(Sl,persist_frames); # 1=liquid,0=crystal
    if c.max()==0: return None  # never born
    # indices where committed==1
    first=np.flatnonzero(c==1)[0]
    # after first commit to liquid, does it ever return to crystal (0) later?
    returned = np.any(c[first:]==0)
    return bool(returned)
for leg in LEGS:
    steps=int(leg/0.005); rec=5; frames=steps//rec
    persist_frames=max(1,int(PERSIST_TU/(0.005*rec)))
    Rvals=[]; born=0
    for r in range(NREP):
        seed=2000+leg*7+r
        def Ts(s, steps=steps): return 0.20+0.16*(s/steps)
        rr=simulate(0.20,seed,steps,rec_every=rec,Tsched=Ts,x0=None)
        lab2=assign(np.sort(rr['D'],axis=1),model); Sl=(mom[lab2]==liq).astype(int)
        u=first_attempt_unstable(Sl,persist_frames)
        if u is not None: born+=1; Rvals.append(1.0 if u else 0.0)
    R=float(np.mean(Rvals)) if Rvals else None
    out[str(leg)]=dict(R=R, n_born=int(len(Rvals)), n_rep=NREP)
    print(leg,'R',None if R is None else round(R,3),'born',len(Rvals),f'[{time.time()-t0:.0f}s]',flush=True)
    json.dump(out,open('/home/claude/core02_results.json','w'),indent=1)
# verdicts
def g(l): return out[str(l)]['R']
R200,R25=g(200),g(25)
r1_ok = (R200 is not None and R25 is not None and (R200-R25)>=0.3); r1_kill=(R200 is not None and R25 is not None and abs(R200-R25)<0.1)
mid=[g(50),g(25)]  # legs near clock 25-40
r2_ok = (R200 is not None and R200>=0.6) and (R25 is not None and R25<=0.3) and any(v is not None and 0.2<=v<=0.8 for v in [g(100),g(50)])
r2_kill = all(v is None or (v<0.5) for v in [g(200),g(100),g(50),g(25)]) or all(v is None or v>0.5 for v in [g(200),g(100),g(50),g(25)])
out['verdicts']=dict(PR1=dict(ok=bool(r1_ok),killed=bool(r1_kill),R={l:g(l) for l in LEGS}),
                     PR2=dict(ok=bool(r2_ok),killed=bool(r2_kill),R={l:g(l) for l in LEGS}))
json.dump(out,open('/home/claude/core02_results.json','w'),indent=1)
for k,v in out['verdicts'].items(): print(k,'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else 'не установлен'), v['R'])
