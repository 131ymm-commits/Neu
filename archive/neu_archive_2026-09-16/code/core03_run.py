"""CORE-03 — predictor-class fingerprint (D,N) of a level, on LJ13 / dipeptide / sleep. Per PREREG (2026-09-03)."""
import numpy as np, scipy.io as sio, glob, os, json, sys
sys.path.insert(0,'/home/claude'); from core03_lib import f_curve, disc_mi
from scipy.stats import ortho_group, spearmanr
out={}

# ---------- LJ13 crystal/liquid at coexistence T=0.28 ----------
from lj13 import *; from mol_levels_lib import microstates_fit, find_levels, microstates, assign
lj={}
for seed in (321,322,323):
    r=simulate(0.28,seed,1000000,rec_every=50); D=np.sort(r['D'][400:],axis=1); Ep=r['Ep'][400:]
    lab=microstates(D,30,seed=0); L=find_levels(lab,30,16)
    if L['n_levels']<2: lj[str(seed)]=dict(one_level=True); continue
    S=L['S']; liq=int(np.argmax([Ep[S==s].mean() for s in range(L['n_levels'])])); Sb=(np.array([1 if L['macro_of_micro'][l]==liq else 0 for l in lab]))
    fc=f_curve(Sb, D, tau=16)
    # rotation null on D
    Ds=[];
    for k in range(6):
        Q=ortho_group.rvs(D.shape[1],random_state=k); Ds.append(f_curve(Sb,D@Q,tau=16,do_nonlin=False))
    fc['D_rot_faxis_std']=float(np.std([x['f_axis'] for x in Ds])); fc['D_rot_flin_std']=float(np.std([x['f_lin'] for x in Ds]))
    fc['weight']=float(Sb.mean()); lj[str(seed)]=fc
    print('LJ13',seed,'I %.3f fa %.3f fl %.3f fn %.3f | D %.3f N %.3f w %.3f'%(fc['I'],fc['f_axis'],fc['f_lin'],fc['f_nonlin'],fc['D'],fc['N'],fc['weight']),flush=True)
out['LJ13']=lj

# ---------- dipeptide phi>0 across T (weight varies) ----------
dip={}
for f in sorted(glob.glob('/home/claude/mol_ala2_m5_T*_s*.npz')):
    T=int(f.split('_T')[1].split('_')[0]);
    if T==300: continue  # single level
    d=np.load(f); sc=d['scal']; xyz=d['xyz']; heavy=d['heavy']; phi=sc[:,0]
    iu=np.triu_indices(len(heavy),1); Dm=np.linalg.norm(xyz[:,iu[0],:]-xyz[:,iu[1],:],axis=2)
    S=(phi>0).astype(int)
    if S.sum()<30: continue
    fc=f_curve(S,Dm,tau=25); fc['weight']=float(S.mean()); fc['T']=T
    dip[os.path.basename(f)]=fc
    print('DIP',os.path.basename(f),'fa %.3f fl %.3f fn %.3f | D %.3f N %.3f w %.3f'%(fc['f_axis'],fc['f_lin'],fc['f_nonlin'],fc['D'],fc['N'],fc['weight']),flush=True)
out['dipeptide']=dip

# ---------- sleep REM/rest, 6 nights, per half-night for weight relation ----------
sl={}; halves=[]
for psg_p in sorted(glob.glob('/home/claude/combsleepnet/example_data/psg/*.mat')):
    name=os.path.basename(psg_p).split('-')[0]; b=name[:6]
    hp=glob.glob(f'/home/claude/combsleepnet/example_data/hyp/{b}*.mat')[0]
    psg=sio.loadmat(psg_p)['psg']; hyp=sio.loadmat(hp)['hyp'].ravel().astype(int)
    n=min(len(psg),len(hyp)); psg=psg[:n]; hyp=hyp[:n]
    F=np.log10(np.mean(psg.astype(np.float64)**2,axis=2)+1e-20)   # 4 band powers
    S=(hyp==1).astype(int)   # REM vs rest
    fc=f_curve(S,F,tau=4); fc['weight']=float(S.mean()); sl[name]=fc
    print('SLEEP',name,'fa %.3f fl %.3f fn %.3f | D %.3f N %.3f w %.3f'%(fc['f_axis'],fc['f_lin'],fc['f_nonlin'],fc['D'],fc['N'],fc['weight']),flush=True)
    for a,bnd in [(0,n//2),(n//2,n)]:
        Sr=(hyp[a:bnd]==1).astype(int);
        if Sr.sum()<6: halves.append(None); continue
        h=f_curve(Sr,F[a:bnd],tau=4,do_nonlin=False); h['weight']=float(Sr.mean()); halves.append(h)
out['sleep']=sl; out['sleep_halves']=halves
json.dump(out,open('/home/claude/core03_results.json','w'),indent=1,default=float)

# ---------- verdicts ----------
def med(xs): xs=[x for x in xs if x is not None and np.isfinite(x)]; return float(np.median(xs)) if xs else None
D_all=[v['D'] for v in list(lj.values())+list(dip.values())+list(sl.values()) if 'D' in v and np.isfinite(v.get('D',np.nan))]
f1_ok=med(D_all)>=0.10; f1_kill=med(D_all)<=0.03
# F2: molecular deterministic S -> f_nonlin small
mol_fn=[v['f_nonlin'] for v in list(lj.values())+list(dip.values()) if 'f_nonlin' in v]
f2_ok=all(x<=0.10 for x in mol_fn); f2_kill=any(x>=0.3 for x in mol_fn)
# F3a: LJ13 N
ljN=[v['N'] for v in lj.values() if 'N' in v]
f3a_ok=med(ljN) is not None and med(ljN)>=0.15; f3a_lin=med(ljN) is not None and med(ljN)<=0.05
# F3b: sleep f_nonlin >=0.10 on >=4/6
sl_fn=[v['f_nonlin'] for v in sl.values()]
f3b_ok=sum(1 for x in sl_fn if x>=0.10)>=4; f3b_kill=sum(1 for x in sl_fn if x<=0)>=4
# F4: rho over half-nights
W=[h['weight'] for h in halves if h]; FA=[h['f_axis'] for h in halves if h]; FL=[h['f_lin'] for h in halves if h]
rho_ax=float(spearmanr(W,FA)[0]) if len(W)>=4 else float('nan')
rho_lin=float(spearmanr(W,FL)[0]) if len(W)>=4 else float('nan')
f4_ok=abs(rho_lin)<=0.2; f4_kill=abs(rho_lin)>=abs(rho_ax)
V=dict(
 PF1=dict(ok=bool(f1_ok),killed=bool(f1_kill),median_D=med(D_all),D_all=[round(x,3) for x in D_all]),
 PF2=dict(ok=bool(f2_ok),killed=bool(f2_kill),mol_fnonlin=[round(x,3) for x in mol_fn]),
 PF3a=dict(ok=bool(f3a_ok),linear=bool(f3a_lin),median_N_LJ13=med(ljN),N=[round(x,3) for x in ljN]),
 PF3b=dict(ok=bool(f3b_ok),killed=bool(f3b_kill),sleep_fnonlin=[round(x,3) for x in sl_fn]),
 PF4=dict(ok=bool(f4_ok),killed=bool(f4_kill),rho_axis=round(rho_ax,3),rho_lin=round(rho_lin,3)))
out['verdicts']=V; json.dump(out,open('/home/claude/core03_results.json','w'),indent=1,default=float)
print('\n== VERDICTS ==')
for k,v in V.items(): print(k, {kk:vv for kk,vv in v.items()})
