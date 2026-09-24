"""CORE-01 fix (descriptive, not pre-registered as verdict): scale-free bimodality coefficient replaces absolute dBIC."""
import numpy as np, scipy.io as sio, glob, os, sys
sys.path.insert(0,'/home/claude'); from mol_levels_lib import microstates, transition_matrix, implied_timescales
from scipy.stats import skew, kurtosis
def block_surrogate_p95(lab, k, tau, nb=200, block=None, seed=0):
    block = block or max(2,tau); rng=np.random.default_rng(seed); n=len(lab); top=[]
    for _ in range(nb):
        nbl=int(np.ceil(n/block)); order=rng.permutation(nbl)
        perm=np.concatenate([np.arange(b*block,min((b+1)*block,n)) for b in order])[:n]; ls=lab[perm]
        try:
            P,keep=transition_matrix(ls,k,tau); its,_=implied_timescales(P,tau,3); top.append(its[0])
        except Exception: pass
    return float(np.quantile(top,0.95)) if top else np.inf
def BC(x):
    x=np.asarray(x,float); n=len(x)
    if n<8 or np.std(x)<1e-12: return 0.0
    g=skew(x); k=kurtosis(x,fisher=True)  # excess
    denom = k + 3*(n-1)**2/((n-2)*(n-3))
    return float((g**2+1)/denom) if denom>0 else 0.0
def levels_v3(F,k,tau,nmax=5,bc_thr=0.555):
    lab=microstates(F,k,seed=0); P,keep=transition_matrix(lab,k,tau); its,V=implied_timescales(P,tau,nmax)
    micro=np.flatnonzero(keep); p95=block_surrogate_p95(lab,k,tau,seed=0); passed=0; stop=False; info=[]
    for m in range(nmax):
        pm=np.full(k,np.nan); pm[micro]=V[:,m+1] if m+1<V.shape[1] else V[:,-1]; coord=pm[lab]; coord=coord[np.isfinite(coord)]
        bc=BC(coord); ok=(its[m]>p95) and (bc>=bc_thr)
        info.append((round(float(its[m]),1),round(float(p95),1),round(bc,3),ok))
        if ok and not stop: passed+=1
        else: stop=True
    return 1+passed, info
from lj13 import *
print("system            v3  (its,p95,BC,pass) for top modes")
for T,s in [(0.18,41),(0.36,41),(0.28,321)]:
    r=simulate(T,s,500000,rec_every=50); F=np.sort(r['D'][300:],axis=1); nl,info=levels_v3(F,30,16)
    print(f"LJ T={T} s{s}:   v3={nl}  {info[:3]}")
for f in ['mol_ala2_m5_T300_s211.npz','mol_ala2_m5_T400_s211.npz','mol_ala2_m5_T700_s211.npz']:
    d=np.load(f); sc=d['scal']; phi,psi=sc[:,0],sc[:,1]; F=np.column_stack([np.cos(phi),np.sin(phi),np.cos(psi),np.sin(psi)])
    nl,info=levels_v3(F,30,25); print(f"DIP {f[-13:-4]}: v3={nl}  {info[:3]}")
for psg_p in sorted(glob.glob('combsleepnet/example_data/psg/*.mat'))[:3]:
    name=os.path.basename(psg_p).split('-')[0]; psg=sio.loadmat(psg_p)['psg']
    F=np.log10(np.mean(psg.astype(np.float64)**2,axis=2)+1e-20); nl,info=levels_v3(F,30,4)
    print(f"SLEEP {name}: v3={nl}  {info[:3]}")
