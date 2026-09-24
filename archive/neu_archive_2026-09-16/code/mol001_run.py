"""MOL-001 — level finding on alanine dipeptide replicas (600 K). Per PREREG (frozen 2026-09-03)."""
import numpy as np, sys, json
sys.path.insert(0,'/home/claude'); from mol_levels_lib import *
from itertools import permutations
TAU=25; K=30; PERSIST=25; out={}
for sd in (201,202,203):
    d=np.load(f'/home/claude/mol_ala2_r{sd}.npz'); sc=d['scal']; xyz=d['xyz']; heavy=d['heavy']
    phi,psi=sc[:,0],sc[:,1]; F=np.column_stack([np.cos(phi),np.sin(phi),np.cos(psi),np.sin(psi)])
    iu=np.triu_indices(len(heavy),1); Dm=np.linalg.norm(xyz[:,iu[0],:]-xyz[:,iu[1],:],axis=2)
    lab=microstates(F,K,seed=0); L=find_levels(lab,K,TAU); S=L['S']; n=L['n_levels']
    res=dict(n_levels=n, its_ps=(L['its'][:4]*0.2).tolist(), ratios=L['ratios'][:3].tolist(), frac_phi_pos=float(np.mean(phi>0)))
    if n>=2:
        labP=(phi>0).astype(int); best=0; bestperm=None
        for perm in permutations(range(n)):
            m=np.array(perm)[S]; a=np.mean((m>0)==(labP>0))
            if a>best: best=a; bestperm=perm
        res['purity']=float(best)
        pp,v,b=psi_prime(S,Dm,TAU); res['psi']=float(pp); res['I_macro']=float(v); res['I_best_micro']=float(b)
        rng=np.random.default_rng(0); nulls=[]
        for r_ in range(30):
            perm=rng.permutation(K); mm=np.zeros(K,int); mm[perm[:K//2]]=1; nulls.append(psi_prime(mm[lab],Dm,TAU)[0])
        res['null_p99']=float(np.quantile(nulls,0.99)); res['null_med']=float(np.median(nulls))
        Ssh=S.copy(); rng.shuffle(Ssh); res['psi_timeshuffle']=float(psi_prime(Ssh,Dm,TAU)[0])
        Sc=committed(S,PERSIST); seg,st=dwell_times(Sc)
        # minority level = the one with smaller fraction
        fr=[float(np.mean(Sc==s)) for s in range(n)]; mn=int(np.argmin(fr)); res['fracs']=fr
        dw=seg[st==mn]; res['n_dwell_min']=int(len(dw)); res['cv_min']=float(dw.std(ddof=1)/dw.mean()) if len(dw)>2 else None; res['mean_dwell_min_ps']=float(dw.mean()*0.2) if len(dw) else None
        dwM=seg[st!=mn]; res['n_dwell_maj']=int(len(dwM)); res['cv_maj']=float(dwM.std(ddof=1)/dwM.mean()) if len(dwM)>2 else None
    out[str(sd)]=res
    print(sd, {k:(round(v,3) if isinstance(v,float) else v) for k,v in res.items()}, flush=True)
R=[out[str(s)] for s in (201,202,203)]
ok1=all(r['n_levels']==2 and r['ratios'][0]>=3 and r.get('purity',0)>=0.9 for r in R); kill1=sum(1 for r in R if r['n_levels']==1 and r['ratios'][0]<1.5)>=2 or any(r.get('purity',1)<0.6 for r in R)
ok2=all(r.get('psi',-1)>r.get('null_p99',9) for r in R); kill2=sum(1 for r in R if r.get('psi',-1)<=r.get('null_p99',9))>=2
read3=[r for r in R if r.get('n_dwell_min',0)>=10]
ok3=len(read3)==3 and all(0.7<=r['cv_min']<=1.5 for r in read3); kill3=sum(1 for r in read3 if r['cv_min']<=0.3)>=2; unread3=len(read3)<2
out['verdicts']=dict(PA1=dict(ok=ok1,killed=kill1),PA2=dict(ok=ok2,killed=kill2),PA3=dict(ok=ok3,killed=kill3,unreadable=unread3))
json.dump(out,open('/home/claude/mol001_results.json','w'),indent=1,default=float)
for k,v in out['verdicts'].items(): print(k, 'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else ('не читается' if v.get('unreadable') else 'не установлен')))
