"""LEV-PLK-001 — level finding on the Beninca plankton mesocosm (real, unlabeled). Per PREREG (2026-09-03)."""
import numpy as np, pandas as pd, sys, json
sys.path.insert(0,'/home/claude'); from mol_levels_lib import *
df=pd.read_csv("/home/claude/RREEBES/Beninca_etal_2008_Nature/data/direct_from_Steve/interp_short_allsystem_newnames.csv")
X=df.iloc[:,1:].values.astype(float)
eps=np.array([1e-3*np.median(c[c>0]) for c in X.T]); Xl=np.log10(X+eps); Xz=(Xl-Xl.mean(0))/Xl.std(0)
K=20; out={}
lab=microstates(Xz,K,seed=0)
rng=np.random.default_rng(0)
for tau in (1,2,3):
    L=find_levels(lab,K,tau); S=L['S']; res=dict(n=L['n_levels'],ratio=float(L['ratios'][0]),its=[float(x) for x in L['its'][:4]])
    # block bootstrap stability of n_levels
    n=len(lab); B=30; blocks=[lab[i:i+B] for i in range(0,n,B)]; same=0; nb=50
    for b in range(nb):
        idx=rng.integers(0,len(blocks),len(blocks)); lb=np.concatenate([blocks[i] for i in idx])
        try:
            Lb=find_levels(lb,K,tau); same+= (Lb['n_levels']==L['n_levels'])
        except Exception: pass
    res['stability']=same/nb
    if L['n_levels']>=2:
        pp,v,b=psi_prime(S,Xl,tau); res['psi']=float(pp); res['I']=float(v)
        nulls=[]
        for r_ in range(30):
            perm=rng.permutation(K); mm=np.zeros(K,int); mm[perm[:K//2]]=1; nulls.append(psi_prime(mm[lab],Xl,tau)[0])
        res['null_p99']=float(np.quantile(nulls,0.99))
        Sc=committed(S,2); seg,st=dwell_times(Sc); res['fracs']=[float(np.mean(Sc==s)) for s in range(L['n_levels'])]
        res['cv']=[float(seg[st==s].std(ddof=1)/seg[st==s].mean()) if np.sum(st==s)>2 else None for s in range(L['n_levels'])]; res['n_dwell']=[int(np.sum(st==s)) for s in range(L['n_levels'])]
    # time-shuffle control
    labs=lab.copy(); rng.shuffle(labs); Ls=find_levels(labs,K,tau); res['shuffle_ratio']=float(Ls['ratios'][0]); res['shuffle_n']=Ls['n_levels']
    out[str(tau)]=res; print("tau",tau,{k:(round(v,3) if isinstance(v,float) else v) for k,v in res.items()})
ok1=all(out[t]['ratio']<3 for t in ('1','2','3'))
kill1=sum(1 for t in ('1','2','3') if out[t]['ratio']>=3 and out[t].get('psi',-1)>out[t].get('null_p99',9) and out[t]['stability']>=0.8)>=2
out['verdict']=dict(PK1=dict(ok=ok1,killed=kill1)); json.dump(out,open('/home/claude/plk001_results.json','w'),indent=1)
print("P-K1:", 'ПОДТВЕРЖДЁН (уровней нет)' if ok1 else ('УБИТ (уровни есть)' if kill1 else 'не установлен'))
