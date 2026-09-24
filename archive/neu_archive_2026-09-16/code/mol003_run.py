"""MOL-003 — collectivity of the found level vs T (fresh seeds). Per PREREG (2026-09-03)."""
import numpy as np, sys, json, time
sys.path.insert(0,'/home/claude'); from lj13 import *; from mol_levels_lib import *
t0=time.time(); out={}
for seed in (321,322,323):
    for T in (0.22,0.25,0.28):
        r=simulate(T,seed,1000000,rec_every=50); D=r['D'][400:]; Ds=np.sort(D,axis=1)
        lab=microstates(Ds,30,seed=0); L=find_levels(lab,30,16); S=L['S']
        key=f"{seed}_{T}"
        if L['n_levels']>=2:
            pp,v,b=psi_prime(S,D,16); rng=np.random.default_rng(0); Ssh=S.copy(); rng.shuffle(Ssh); psh=psi_prime(Ssh,D,16)[0]
            out[key]=dict(n=L['n_levels'],ratio=float(L['ratios'][0]),psi=float(pp),I=float(v),best=float(b),f=float(pp/v),psi_shuffle=float(psh),minority=float(min(np.mean(S==s) for s in range(L['n_levels']))))
        else: out[key]=dict(n=1,ratio=float(L['ratios'][0]))
        print(key, {k:(round(v,4) if isinstance(v,float) else v) for k,v in out[key].items()}, f"[{time.time()-t0:.0f}s]", flush=True)
        json.dump(out,open('/home/claude/mol003_results.json','w'),indent=1)
ok_a=[]; ok_b=[]
for seed in (321,322,323):
    a=out[f"{seed}_0.22"]; c=out[f"{seed}_0.28"]
    if a['n']>=2 and c['n']>=2:
        ok_a.append(c['psi']>=2*a['psi']); ok_b.append(0.67<=c['f']/a['f']<=1.5)
        print(seed, "psi ratio %.2f  f ratio %.2f"%(c['psi']/a['psi'], c['f']/a['f']))
kill_a=sum(1 for seed in (321,322,323) if out[f"{seed}_0.22"]['n']>=2 and out[f"{seed}_0.28"]['n']>=2 and out[f"{seed}_0.28"]['psi']<=out[f"{seed}_0.22"]['psi'])>=2
kill_b=sum(1 for seed in (321,322,323) if out[f"{seed}_0.22"]['n']>=2 and out[f"{seed}_0.28"]['n']>=2 and not (0.67<=out[f"{seed}_0.28"]['f']/out[f"{seed}_0.22"]['f']<=1.5))>=2
V=dict(PM6a=dict(ok=len(ok_a)==3 and all(ok_a),killed=kill_a),PM6b=dict(ok=sum(ok_b)>=2,killed=kill_b)); out['verdicts']=V
json.dump(out,open('/home/claude/mol003_results.json','w'),indent=1)
for k,v in V.items(): print(k,'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else 'не установлен'))
