"""CORE-01 — relative level criterion v2 (surrogate-calibrated slowness AND bimodality) vs absolute gap>=3.
Two-sided calibration on known answers. Per PREREG (2026-09-03)."""
import numpy as np, scipy.io as sio, glob, os, json, sys, time
sys.path.insert(0,'/home/claude'); from mol_levels_lib import microstates, transition_matrix, implied_timescales
from sklearn.mixture import GaussianMixture
t0=time.time()

def block_surrogate_p95(lab, k, tau, nb=200, block=None, seed=0):
    block = block or max(2,tau)
    rng=np.random.default_rng(seed); n=len(lab); top=[]
    idx=np.arange(n)
    for _ in range(nb):
        # block permutation of the label series
        nbl=int(np.ceil(n/block)); order=rng.permutation(nbl)
        perm=np.concatenate([np.arange(b*block,min((b+1)*block,n)) for b in order])[:n]
        ls=lab[perm]
        try:
            P,keep=transition_matrix(ls,k,tau); its,_=implied_timescales(P,tau,3); top.append(its[0])
        except Exception: pass
    return float(np.quantile(top,0.95)) if top else np.inf

def dbic_bimodal(x):
    x=np.asarray(x,float).reshape(-1,1)
    if len(np.unique(x))<3: return -99.0
    g1=GaussianMixture(1,random_state=0).fit(x); g2=GaussianMixture(2,random_state=0,n_init=2).fit(x)
    return float(g1.bic(x)-g2.bic(x))   # >0 favors 2 components

def levels_v2(F, k, tau, nmax=5, seed=0):
    lab=microstates(F,k,seed=0); P,keep=transition_matrix(lab,k,tau); its,V=implied_timescales(P,tau,nmax)
    micro_ids=np.flatnonzero(keep); p95=block_surrogate_p95(lab,k,tau,seed=seed)
    modes=[]; passed=0; stop=False
    for m in range(nmax):
        proj_micro=np.full(k,np.nan); proj_micro[micro_ids]=V[:,m+1] if m+1<V.shape[1] else V[:,-1]
        coord=proj_micro[lab]
        db=dbic_bimodal(coord[np.isfinite(coord)])
        slow = its[m] > p95
        ok = slow and db>=6
        modes.append(dict(its=float(its[m]), p95=float(p95), dBIC=float(db), slow=bool(slow), bimodal=bool(db>=6), passed=bool(ok)))
        if ok and not stop: passed+=1
        else: stop=True
    # also v1 for comparison
    ratios=its[:-1]/its[1:]; v1=1
    for i,r in enumerate(ratios):
        if r>=3.0: v1=i+2; break
    return dict(n_levels_v2=1+passed, n_levels_v1=v1, modes=modes)

out={}
# ---- LJ13 controls: 0.18 (1 level), 0.36 (1 level), 0.28 (2 levels) ----
from lj13 import *
def lj_feat(T,seed,steps=500000):
    r=simulate(T,seed,steps,rec_every=50); return np.sort(r['D'][300:],axis=1)
for T,seeds in [(0.18,(41,42)),(0.36,(41,42)),(0.28,(321,322,323,324,325))]:
    for s in seeds:
        F=lj_feat(T,s); R=levels_v2(F,30,16)
        out[f'LJ_{T}_{s}']=dict(v2=R['n_levels_v2'],v1=R['n_levels_v1'],m0=R['modes'][0],m1=R['modes'][1])
        print(f'LJ T={T} s{s}: v2 {R["n_levels_v2"]} v1 {R["n_levels_v1"]} | m0 its {R["modes"][0]["its"]:.1f} p95 {R["modes"][0]["p95"]:.1f} dBIC {R["modes"][0]["dBIC"]:.1f} pass {R["modes"][0]["passed"]}',f'[{time.time()-t0:.0f}s]',flush=True)
        json.dump(out,open('/home/claude/core01_results.json','w'),indent=1,default=float)
# ---- dipeptide: 300K (1 level control), 400/500/700 (>=2) ----
for f in sorted(glob.glob('/home/claude/mol_ala2_m5_T*_s*.npz')):
    T=int(f.split('_T')[1].split('_')[0]); d=np.load(f); sc=d['scal']; phi,psi=sc[:,0],sc[:,1]
    F=np.column_stack([np.cos(phi),np.sin(phi),np.cos(psi),np.sin(psi)])
    R=levels_v2(F,30,25); out[os.path.basename(f)]=dict(T=T,v2=R['n_levels_v2'],v1=R['n_levels_v1'],m0=R['modes'][0])
    print(f'DIP T={T} {os.path.basename(f)[-9:]}: v2 {R["n_levels_v2"]} v1 {R["n_levels_v1"]} | m0 its {R["modes"][0]["its"]:.1f} p95 {R["modes"][0]["p95"]:.1f} dBIC {R["modes"][0]["dBIC"]:.1f}',flush=True)
    json.dump(out,open('/home/claude/core01_results.json','w'),indent=1,default=float)
# ---- sleep 6 nights ----
for psg_p in sorted(glob.glob('/home/claude/combsleepnet/example_data/psg/*.mat')):
    name=os.path.basename(psg_p).split('-')[0]
    psg=sio.loadmat(psg_p)['psg']; F=np.log10(np.mean(psg.astype(np.float64)**2,axis=2)+1e-20)
    R=levels_v2(F,30,4); out['SLEEP_'+name]=dict(v2=R['n_levels_v2'],v1=R['n_levels_v1'],m0=R['modes'][0],m1=R['modes'][1])
    print(f'SLEEP {name}: v2 {R["n_levels_v2"]} v1 {R["n_levels_v1"]} | m0 its {R["modes"][0]["its"]:.1f} p95 {R["modes"][0]["p95"]:.1f} dBIC {R["modes"][0]["dBIC"]:.1f} pass {R["modes"][0]["passed"]}',flush=True)
    json.dump(out,open('/home/claude/core01_results.json','w'),indent=1,default=float)
# verdicts
def v2(k): return out[k]['v2']
one_lvl_controls=[k for k in out if (k.startswith('LJ_0.18') or k.startswith('LJ_0.36'))]+[k for k in out if 'T300' in k]
c1_ok=all(v2(k)==1 for k in one_lvl_controls); c1_kill=any(v2(k)>=2 for k in one_lvl_controls)
sleep_keys=[k for k in out if k.startswith('SLEEP')]; c2_ok=sum(1 for k in sleep_keys if v2(k)>=2)>=4; c2_kill=sum(1 for k in sleep_keys if v2(k)==1)>=4
lj28=[k for k in out if k.startswith('LJ_0.28')]; c3_ok=sum(1 for k in lj28 if v2(k)>=2)>=4; c3_kill=sum(1 for k in lj28 if v2(k)==1)>=3
V=dict(PC1=dict(ok=bool(c1_ok),killed=bool(c1_kill),controls={k:v2(k) for k in one_lvl_controls}),
       PC2=dict(ok=bool(c2_ok),killed=bool(c2_kill),sleep={k:(v2(k),out[k]['v1']) for k in sleep_keys}),
       PC3=dict(ok=bool(c3_ok),killed=bool(c3_kill),lj28={k:v2(k) for k in lj28}))
out['verdicts']=V; json.dump(out,open('/home/claude/core01_results.json','w'),indent=1,default=float)
print('\n== VERDICTS ==')
for k,vv in V.items(): print(k,'ПОДТВЕРЖДЁН' if vv['ok'] else ('УБИТ' if vv['killed'] else 'не установлен'),{x:y for x,y in vv.items() if x not in('ok','killed')})
