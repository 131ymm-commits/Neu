"""BRAIN-001 — sleep stages as levels of one brain across the night (Sleep-EDF, 6 nights).
Frozen level-finding pipeline (= MOL-001/005) on per-epoch band powers; theory arrows B1-B4. Per PREREG (2026-09-03)."""
import numpy as np, scipy.io as sio, glob, os, json
import sys; sys.path.insert(0,'/home/claude'); from mol_levels_lib import *
from sklearn.metrics import adjusted_mutual_info_score, v_measure_score
TAU=4; K=30; PERSIST=4; GAP=3.0
REF3={0:0,2:0, 3:1,4:1, 1:2}   # W,N1->0 wake/drowsy ; N2,N3->1 consolidated NREM ; REM->2
NIGHTS=sorted(glob.glob('/home/claude/combsleepnet/example_data/psg/*.mat'))
def hyp_for(psg):
    b=os.path.basename(psg).split('-')[0][:6]   # SC4001
    hp=glob.glob(f'/home/claude/combsleepnet/example_data/hyp/{b}*Hypnogram.mat')[0]
    return sio.loadmat(hp)['hyp'].ravel().astype(int)
def bandpower(psg):
    # psg: (n,4,3000) bandpassed delta/theta/alpha/sigma -> log10 mean-square power per band
    return np.log10(np.mean(psg.astype(np.float64)**2, axis=2)+1e-20)   # (n,4)
def maj_map(S, ref):
    out=np.zeros_like(S)
    for s in np.unique(S):
        m=S==s; vals,cnt=np.unique(ref[m],return_counts=True); out[m]=vals[cnt.argmax()]
    return out
def psip(Sbin, X):
    v=disc_mi(Sbin[:-TAU],Sbin[TAU:]);
    best=-np.inf
    for j in range(X.shape[1]):
        q=np.quantile(X[:,j],np.linspace(0,1,9)[1:-1]); xb=np.searchsorted(q,X[:,j]); best=max(best,disc_mi(xb[:-TAU],Sbin[TAU:]))
    return v-best, v
out={}
for psg_p in NIGHTS:
    name=os.path.basename(psg_p).split('-')[0]
    psg=sio.loadmat(psg_p)['psg']; hyp=hyp_for(psg_p)
    n=min(len(psg),len(hyp)); psg=psg[:n]; hyp=hyp[:n]
    F=bandpower(psg); ref=np.array([REF3[x] for x in hyp])
    lab=microstates(F,K,seed=0); L=find_levels(lab,K,TAU,gap_min=GAP); S=L['S']; nlv=L['n_levels']
    r=dict(n=int(n), n_levels=int(nlv), its=[round(float(x),1) for x in L['its'][:4]], ratios=[round(float(x),2) for x in L['ratios'][:3]])
    # B1 purity vs R3 (majority mapping), plus AMI/v vs 5-class
    pred3=maj_map(S,ref); r['purity_R3']=float(np.mean(pred3==ref))
    r['AMI_5']=float(adjusted_mutual_info_score(hyp,S)); r['v_5']=float(v_measure_score(hyp,S))
    r['dominant_R3']=float(max(np.mean(ref==c) for c in (0,1,2)))
    # B2 committed dwell CV per discovered level
    Sc=committed(S,PERSIST); seg,st=dwell_times(Sc); cvs=[]
    lvl_major={}
    for s in range(nlv):
        d=seg[st==s]
        if len(d)>2: cvs.append(float(d.std(ddof=1)/d.mean()))
        m=Sc==s;
        if m.sum(): vals,cnt=np.unique(hyp[m],return_counts=True); lvl_major[s]=int(vals[cnt.argmax()])
    r['cv_by_level']=[round(c,3) for c in cvs]; r['cv_med']=float(np.median(cvs)) if cvs else None
    r['level_major_stage']=lvl_major  # human stage each discovered committed level maps to
    # B3 discovered REM-like level weight by third
    rem_levels=[s for s,mj in lvl_major.items() if mj==1]
    t=n//3
    if rem_levels:
        remmask=np.isin(Sc,rem_levels)
        r['REMlvl_first']=float(remmask[:t].mean()); r['REMlvl_last']=float(remmask[2*t:].mean())
        r['REMlvl_dweight']=r['REMlvl_last']-r['REMlvl_first']
    else:
        r['REMlvl_first']=0.0; r['REMlvl_last']=0.0; r['REMlvl_dweight']=0.0; r['REM_not_a_level']=True
    r['humanREM_first']=float(np.mean(hyp[:t]==1)); r['humanREM_last']=float(np.mean(hyp[2*t:]==1))
    # B4 pieces: per half-night, REM(human)-vs-rest f=psi'/I and REM weight
    halves=[]
    for a,b in [(0,n//2),(n//2,n)]:
        Sr=(hyp[a:b]==1).astype(int); Xf=F[a:b]
        if Sr.sum()<TAU+2 or (Sr==0).all(): halves.append(None); continue
        pp,I=psip(Sr,Xf); f=pp/I if I>1e-9 else np.nan
        halves.append(dict(w=float(Sr.mean()), f=float(f), psi=float(pp), I=float(I)))
    r['halves']=halves
    # psi' of discovered S vs nulls (night-level sanity)
    if nlv>=2:
        pp,I=psip((S==S).astype(int)*0+ (maj_map(S,(hyp==1).astype(int))), F)  # placeholder not used
    rng=np.random.default_rng(0); nulls=[]
    for _ in range(30):
        perm=rng.permutation(K); mm=np.zeros(K,int); mm[perm[:K//2]]=1
        nulls.append(psip(mm[lab],F)[0])
    r['null_p99_psi']=float(np.quantile(nulls,0.99))
    Ssh=S.copy(); rng.shuffle(Ssh); r['psi_S_timeshuffle']=float(psip((Ssh==Ssh[0]).astype(int) if nlv<2 else maj_map(Ssh,(hyp==1).astype(int)),F)[0])
    out[name]=r
    print(name,'nlv',nlv,'pur',round(r['purity_R3'],3),'AMI',round(r['AMI_5'],3),'cvmed',r['cv_med'],
          'REMlvl d',round(r['REMlvl_dweight'],3),'major',lvl_major,flush=True)
json.dump(out,open('/home/claude/brain001_results.json','w'),indent=1,default=float)

# ---- verdicts ----
names=list(out)
pur=[out[k]['purity_R3'] for k in names]; nlv=[out[k]['n_levels'] for k in names]
b1_ok=sum(1 for k in names if 2<=out[k]['n_levels']<=4 and out[k]['purity_R3']>=0.70)>=5
b1_kill=sum(1 for k in names if out[k]['purity_R3']<=0.55)>=3
cvm=[out[k]['cv_med'] for k in names if out[k]['cv_med'] is not None]
b2_ok=sum(1 for k in names if out[k]['cv_med'] is not None and out[k]['cv_med']>=0.7)>=5
b2_kill=sum(1 for k in names if out[k]['cv_med'] is not None and out[k]['cv_med']<=0.3)>=2
dw=[out[k]['REMlvl_dweight'] for k in names]
b3_ok=(float(np.median(dw))>=0.03) and (sum(1 for d in dw if d>0)>=5)
b3_kill=(float(np.median(dw))<=0) or (sum(1 for d in dw if d>0)<=3)
# B4 spearman over half-nights
from scipy.stats import spearmanr
W=[]; Ff=[]
for k in names:
    for h in out[k]['halves']:
        if h and np.isfinite(h['f']): W.append(h['w']); Ff.append(h['f'])
rho,pval=spearmanr(W,Ff) if len(W)>=4 else (float('nan'),float('nan'))
b4_ok=(rho>=0.5); b4_kill=(rho<=0)
# LOO on B4
loo=[]
for drop in names:
    w=[];f=[]
    for k in names:
        if k==drop: continue
        for h in out[k]['halves']:
            if h and np.isfinite(h['f']): w.append(h['w']); f.append(h['f'])
    loo.append(round(float(spearmanr(w,f)[0]),3))
V=dict(
 PB1=dict(ok=bool(b1_ok),killed=bool(b1_kill),purity=[round(x,3) for x in pur],n_levels=nlv,dominant=[round(out[k]['dominant_R3'],3) for k in names]),
 PB2=dict(ok=bool(b2_ok),killed=bool(b2_kill),cv_med=[out[k]['cv_med'] for k in names]),
 PB3=dict(ok=bool(b3_ok),killed=bool(b3_kill),dweight=[round(x,3) for x in dw],median=round(float(np.median(dw)),3),
          humanREM_d=[round(out[k]['humanREM_last']-out[k]['humanREM_first'],3) for k in names]),
 PB4=dict(ok=bool(b4_ok),killed=bool(b4_kill),rho=round(float(rho),3),n_halves=len(W),loo=loo))
out['verdicts']=V; json.dump(out,open('/home/claude/brain001_results.json','w'),indent=1,default=float)
print('\n== VERDICTS ==')
for k,v in V.items(): print(k,'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else 'не установлен'), {kk:vv for kk,vv in v.items() if kk not in('ok','killed')})
