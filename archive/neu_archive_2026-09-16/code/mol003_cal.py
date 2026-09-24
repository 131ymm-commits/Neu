import numpy as np, sys, time, json
sys.path.insert(0,'/home/claude'); from lj13 import *; from mol_levels_lib import *
t0=time.time(); out={}
for T in (0.22,0.25,0.28):
    r=simulate(T,101,1000000,rec_every=50); D=r['D'][400:]; Ds=np.sort(D,axis=1)
    lab=microstates(Ds,30,seed=0); L=find_levels(lab,30,16); S=L['S']
    if L['n_levels']>=2:
        pp,v,b=psi_prime(S,D,16); out[str(T)]=dict(psi=pp,I=v,best=b,frac=pp/v, n=L['n_levels'], ratio=L['ratios'][0], minority=float(min(np.mean(S==s) for s in range(L['n_levels']))))
    else: out[str(T)]=dict(n=1)
    print(T, {k:(round(v,4) if isinstance(v,float) else v) for k,v in out[str(T)].items()}, f"[{time.time()-t0:.0f}s]", flush=True)
json.dump(out,open('/home/claude/mol003_cal.json','w'),indent=1)
