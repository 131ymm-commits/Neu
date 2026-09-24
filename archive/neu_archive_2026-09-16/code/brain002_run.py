"""BRAIN-002 — flip-flop sleep model: frozen pipeline + theory arrows under a dialable REM handle. Per PREREG (2026-09-03)."""
import numpy as np, json, importlib
import sleepmodel as sm; importlib.reload(sm)
import sys; sys.path.insert(0,'/home/claude'); from mol_levels_lib import *
from scipy.stats import spearmanr
TAU=8; K=20; PERSIST=8; GAP=3.0
NODES=[-2.5,-2.0,-1.0,0.0,0.5,1.0]; SEEDS=[1,2]
def psip(Sbin,X):
    v=disc_mi(Sbin[:-TAU],Sbin[TAU:]); best=-np.inf
    for j in range(X.shape[1]):
        q=np.quantile(X[:,j],np.linspace(0,1,9)[1:-1]); xb=np.searchsorted(q,X[:,j]); best=max(best,disc_mi(xb[:-TAU],Sbin[TAU:]))
    return v-best, v
def maj(S,ref):
    o={}
    for s in np.unique(S):
        m=S==s; vv,cc=np.unique(ref[m],return_counts=True); o[int(s)]=int(vv[cc.argmax()])
    return o
out={}
for mu in NODES:
    for seed in SEEDS:
        r=sm.simulate(mu,seed); F=r['F']; ref=r['ref']
        frac={n:float(np.mean(ref==s)) for n,s in [('W',0),('N',1),('R',2)]}
        lab=microstates(F,K,seed=0); L=find_levels(lab,K,TAU,gap_min=GAP); S=L['S']; nlv=L['n_levels']
        lvmaj=maj(S,ref)
        # discovered REM-level weight
        rem_lvls=[s for s,mj in lvmaj.items() if mj==2]
        Sc=committed(S,PERSIST); remlvl_w=float(np.mean(np.isin(Sc,rem_lvls))) if rem_lvls else 0.0
        # ref REM-vs-rest: f and weight
        Sr=(ref==2).astype(int); w=float(Sr.mean())
        if Sr.sum()>TAU+2 and not (Sr==0).all():
            pp,I=psip(Sr,F); f=float(pp/I) if I>1e-9 else np.nan
        else: pp,I,f=np.nan,np.nan,np.nan
        # committed ref-REM dwell CV
        refc=committed(ref,PERSIST); seg,st=dwell_times(refc); dR=seg[st==2]
        cvR=float(dR.std(ddof=1)/dR.mean()) if len(dR)>2 else None
        out[f"{mu}_{seed}"]=dict(mu=mu,seed=seed,frac=frac,n_levels=int(nlv),
            ratios=[round(float(x),2) for x in L['ratios'][:3]], lvmaj=lvmaj,
            remlvl_w=remlvl_w, refREM_w=w, f=f, psi=float(pp) if np.isfinite(pp) else None, I=float(I) if np.isfinite(I) else None,
            cvR=cvR, nR=int(len(dR)))
        print(f"mu={mu:+.1f} s{seed} nlv{nlv} lvmaj{lvmaj} remlvlW {remlvl_w:.3f} refREMw {w:.3f} f {f if not np.isfinite(f) else round(f,3)} cvR {cvR} nR {len(dR)}",flush=True)
json.dump(out,open('/home/claude/brain002_results.json','w'),indent=1,default=float)
# verdicts
keys=list(out)
# M1: REM discovered level absent (<0.02) at some node and present (>=0.15) at another, both seeds
def rem_absent_present(seed):
    ws=[out[f"{mu}_{seed}"]['remlvl_w'] for mu in NODES]
    return (min(ws)<0.02) and (max(ws)>=0.15)
m1_ok=all(rem_absent_present(s) for s in SEEDS)
m1_kill=all(all(out[f"{mu}_{s}"]['remlvl_w']>=0.02 for mu in NODES) for s in SEEDS) or all(all(out[f"{mu}_{s}"]['remlvl_w']<0.15 for mu in NODES) for s in SEEDS)
# M2: rho(f, refREM weight) over nodes with 2+ ref states & finite f
W=[];Ff=[]
for k in keys:
    if out[k]['f'] is not None and np.isfinite(out[k]['f']) and out[k]['refREM_w']>0.01: W.append(out[k]['refREM_w']); Ff.append(out[k]['f'])
rho=float(spearmanr(W,Ff)[0]) if len(W)>=4 else float('nan')
m2_ok=rho>=0.5; m2_kill=rho<=0
# M3: CV of committed ref-REM dwells in [0.7,1.5] on nodes with >=10 dwells
cvs=[(k,out[k]['cvR']) for k in keys if out[k]['nR']>=10 and out[k]['cvR'] is not None]
m3_ok=len(cvs)>=1 and all(0.7<=c<=1.5 for _,c in cvs); m3_kill=sum(1 for _,c in cvs if c<=0.3)>=2
V=dict(PM1=dict(ok=bool(m1_ok),killed=bool(m1_kill),remlvl_w={f"{mu}":[out[f'{mu}_{s}']['remlvl_w'] for s in SEEDS] for mu in NODES}, nlv={f"{mu}":[out[f'{mu}_{s}']['n_levels'] for s in SEEDS] for mu in NODES}),
        PM2=dict(ok=bool(m2_ok),killed=bool(m2_kill),rho=round(rho,3),n=len(W),pairs=[(round(w,3),round(f,3)) for w,f in sorted(zip(W,Ff))]),
        PM3=dict(ok=bool(m3_ok),killed=bool(m3_kill),cvs=[(k,round(c,3)) for k,c in cvs]))
out['verdicts']=V; json.dump(out,open('/home/claude/brain002_results.json','w'),indent=1,default=float)
print('\n== VERDICTS ==')
for k,v in V.items(): print(k,'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else 'не установлен'),{kk:vv for kk,vv in v.items() if kk not in('ok','killed')})
