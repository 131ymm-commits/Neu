"""UNI-T2 часть c — LJ13: δT плавления vs замерзания по 20 репликам, плечо 100 t.u. Per PREREG (2026-09-04)."""
import numpy as np, sys, json, time
sys.path.insert(0,'/home/claude'); from lj13 import *; from mol_levels_lib import *
t0=time.time()
ref=simulate(0.28,7,1000000,rec_every=50); Dref=np.sort(ref['D'][400:],axis=1)
model,lab=microstates_fit(Dref,30,seed=0); L=find_levels(lab,30,16); mom=L['macro_of_micro']
Ep=ref['Ep'][400:]; S=L['S']; liq=int(np.argmax([Ep[S==s].mean() for s in range(L['n_levels'])]))
print("модель состояний готова, уровней",L['n_levels'],f"[{time.time()-t0:.0f}s]",flush=True)
leg=100; steps=int(leg/0.005); rec=5; persist=int(8.0/(0.005*rec))
def first_committed_T(rr, target):
    lab2=assign(np.sort(rr['D'],axis=1),model); Sl=(mom[lab2]==liq).astype(int); c=committed(Sl,persist)
    idx=np.flatnonzero(c==target)
    return float(rr['T'][idx[0]]) if idx.size else None
out={'melt':[], 'freeze':[], 'miss_melt':0, 'miss_freeze':0}
for r in range(20):
    def Tup(s, steps=steps): return 0.20+0.16*(s/steps)
    rr=simulate(0.20,5000+r,steps,rec_every=rec,Tsched=Tup)
    Tm=first_committed_T(rr,1)
    if Tm is None: out['miss_melt']+=1
    else: out['melt'].append(Tm)
    def Tdn(s, steps=steps): return 0.36-0.16*(s/steps)
    # start from a liquid configuration: equilibrate briefly at 0.36 then cool
    r0=simulate(0.36,6000+r,20000,rec_every=1000); x0=r0['x'] if 'x' in r0 else None
    rr2=simulate(0.36,7000+r,steps,rec_every=rec,Tsched=Tdn,x0=x0)
    Tf=first_committed_T(rr2,0)
    if Tf is None: out['miss_freeze']+=1
    else: out['freeze'].append(Tf)
    print(f"реплика {r}: T_плавл {Tm} T_замерз {Tf} [{time.time()-t0:.0f}s]",flush=True)
    json.dump(out,open('/home/claude/unit2c_results.json','w'),indent=1)
m=np.array(out['melt']); f=np.array(out['freeze'])
out['summary']=dict(n_melt=len(m),n_freeze=len(f),mean_melt=float(m.mean()) if len(m) else None,std_melt=float(m.std(ddof=1)) if len(m)>2 else None,
                    mean_freeze=float(f.mean()) if len(f) else None,std_freeze=float(f.std(ddof=1)) if len(f)>2 else None)
s=out['summary']
if s['std_melt'] and s['std_freeze']:
    ratio=s['std_freeze']/s['std_melt']; s['ratio_freeze_over_melt']=ratio
    s['PA3']='ПОДТВЕРЖДЁН' if ratio>=1.2 else ('УБИТ' if ratio<=1/1.2 else 'не установлен (симметрично)')
json.dump(out,open('/home/claude/unit2c_results.json','w'),indent=1)
print(s)
