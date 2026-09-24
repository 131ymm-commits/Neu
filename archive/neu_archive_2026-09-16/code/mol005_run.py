"""MOL-005 — level-birth profile of alanine dipeptide vs T (300/400/500/700 K, seeds 211/212, 20 ns).
Pipeline = MOL-001 unchanged (k=30, tau=25 frames = 5 ps, gap>=3, persist 25 frames; psi' vs 45 heavy-atom distances).
Per PREREG (2026-09-03)."""
import numpy as np, sys, json, os
sys.path.insert(0,'/home/claude'); from mol_levels_lib import *
from itertools import permutations
TAU=25; K=30; PERSIST=25; TS=(300,400,500,700); SEEDS=(211,212); out={}
def analyze(path):
    d=np.load(path); sc=d['scal']; xyz=d['xyz']; heavy=d['heavy']
    phi,psi=sc[:,0],sc[:,1]; F=np.column_stack([np.cos(phi),np.sin(phi),np.cos(psi),np.sin(psi)])
    iu=np.triu_indices(len(heavy),1); Dm=np.linalg.norm(xyz[:,iu[0],:]-xyz[:,iu[1],:],axis=2)
    lab=microstates(F,K,seed=0); L=find_levels(lab,K,TAU); S=L['S']; n=L['n_levels']
    res=dict(n_levels=n, its_ps=(L['its'][:4]*0.2).tolist(), ratios=L['ratios'][:3].tolist(), frac_phi_pos=float(np.mean(phi>0)))
    # direct phi>0 committed dwells (prereg wording), independent of pipeline
    P=committed((phi>0).astype(int),PERSIST); seg,st=dwell_times(P); dwP=seg[st==1]
    res['n_dwell_phipos']=int(len(dwP)); res['cv_phipos']=float(dwP.std(ddof=1)/dwP.mean()) if len(dwP)>2 else None
    res['mean_dwell_phipos_ps']=float(dwP.mean()*0.2) if len(dwP) else None
    if n>=2:
        labP=(phi>0).astype(int); best=0
        for perm in permutations(range(n)):
            m=np.array(perm)[S]; a=np.mean((m>0)==(labP>0)); best=max(best,a)
        res['purity']=float(best)
        pp,v,b=psi_prime(S,Dm,TAU); res['psi']=float(pp); res['I_macro']=float(v); res['I_best_micro']=float(b); res['f']=float(pp/v) if v>0 else None
        rng=np.random.default_rng(0); nulls=[]
        for r_ in range(30):
            perm=rng.permutation(K); mm=np.zeros(K,int); mm[perm[:K//2]]=1; nulls.append(psi_prime(mm[lab],Dm,TAU)[0])
        res['null_p99']=float(np.quantile(nulls,0.99)); res['null_med']=float(np.median(nulls))
        Ssh=S.copy(); rng.shuffle(Ssh); res['psi_timeshuffle']=float(psi_prime(Ssh,Dm,TAU)[0])
        Sc=committed(S,PERSIST); seg,st=dwell_times(Sc); fr=[float(np.mean(Sc==s)) for s in range(n)]; mn=int(np.argmin(fr)); res['fracs']=fr
        dw=seg[st==mn]; res['n_dwell_min']=int(len(dw)); res['cv_min']=float(dw.std(ddof=1)/dw.mean()) if len(dw)>2 else None
    return res
for T in TS:
    for sd in SEEDS:
        p=f'/home/claude/mol_ala2_m5_T{T}_s{sd}.npz'
        if not os.path.exists(p): print(T,sd,'MISSING'); continue
        res=analyze(p); out[f'{T}_{sd}']=res
        print(T, sd, {k:(round(v,3) if isinstance(v,float) else v) for k,v in res.items() if k not in ('its_ps','ratios','fracs')}, 'its_ps',[round(x,1) for x in res['its_ps'][:3]], flush=True)
json.dump(out,open('/home/claude/mol005_results.json','w'),indent=1,default=float)
if all(f'{T}_{sd}' in out for T in TS for sd in SEEDS):
    nl={sd:[out[f'{T}_{sd}']['n_levels'] for T in TS] for sd in SEEDS}
    ok_a=all(nl[sd]==[1,2,2,2] for sd in SEEDS)
    kill_a=all(nl[sd][0]>=2 for sd in SEEDS) or all(nl[sd][2]==1 for sd in SEEDS) or all(nl[sd][3]==1 for sd in SEEDS)
    fr={sd:(out[f'700_{sd}'].get('f'),out[f'400_{sd}'].get('f')) for sd in SEEDS}
    readable_b=all(fr[sd][0] is not None and fr[sd][1] is not None for sd in SEEDS)
    ok_b=readable_b and all(fr[sd][0]/fr[sd][1]>=1.3 for sd in SEEDS); kill_b=readable_b and all(fr[sd][0]<=fr[sd][1] for sd in SEEDS)
    cvs=[(k,r['cv_phipos']) for k,r in out.items() if r.get('n_dwell_phipos',0)>=10]
    ok_c=len(cvs)>=1 and all(0.7<=c<=1.5 for _,c in cvs); kill_c=sum(1 for _,c in cvs if c<=0.3)>=2
    V=dict(PM8a=dict(ok=ok_a,killed=kill_a,n_levels=nl),PM8b=dict(ok=ok_b,killed=kill_b,readable=readable_b,f700_f400=fr),PM8c=dict(ok=ok_c,killed=kill_c,cvs=cvs,unreadable=len(cvs)==0))
    out['verdicts']=V; json.dump(out,open('/home/claude/mol005_results.json','w'),indent=1,default=float)
    for k,v in V.items(): print(k,'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else ('не читается' if v.get('unreadable') or (k=='PM8b' and not v['readable']) else 'не установлен')), {kk:vv for kk,vv in v.items() if kk not in ('ok','killed')})
else: print('incomplete: 700 K pending')
