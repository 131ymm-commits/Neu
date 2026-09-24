"""HIST-002 — political level births on BMR half B. Per PREREG (2026-09-03)."""
import sys, json, numpy as np; sys.path.insert(0,'/home/claude'); from hist_lib import *
b=load_bmr(); S=spells(b); codes=sorted(S.keys()); half_B=[c for i,c in enumerate(codes) if i%2==1]
df=load_maddison(); rng=np.random.default_rng(20260903)
births=[]; failed=[]; inc_birth=[]; inc_death=[]; excl=0
for c in half_B:
    sp=S[c]; sb=sustained_birth(sp)
    if sb is not None: births.append(sb); failed.append(sum(1 for a,e,en in sp if a<sb and en))
    g=df[df.countrycode==c]
    if len(g)==0: excl+=1
    for a,e,en in sp:
        ga=g[g.year==a]['gdppc'].values
        if len(ga): inc_birth.append(float(np.log(ga[0])))
        if en:
            gd=g[g.year==e+1]['gdppc'].values
            if len(gd): inc_death.append(float(np.log(gd[0])))
births=np.array(births); years=np.arange(1800,2001); cnt=np.array([(births==y).sum() for y in years]); DI=cnt.var(ddof=1)/cnt.mean()
n=len(births); null=[]
for _ in range(10000):
    ys=rng.integers(1800,2001,n); c2=np.bincount(ys-1800,minlength=201); null.append(c2.var(ddof=1)/c2.mean())
p95=float(np.quantile(null,0.95))
subs=[]
for _ in range(50):
    idx=rng.choice(len(half_B), int(0.9*len(half_B)), replace=False); bb=[]
    for i in idx:
        sb=sustained_birth(S[half_B[i]]); 
        if sb is not None: bb.append(sb)
    bb=np.array(bb); c3=np.array([(bb==y).sum() for y in years]); subs.append(c3.var(ddof=1)/c3.mean())
share=float(np.mean(np.array(failed)>=1)); mb=float(np.median(inc_birth)); md=float(np.median(inc_death))
res=dict(n_countries=len(half_B), n_births=int(n), DI=float(DI), null_p95=p95, DI_sub90=[float(min(subs)),float(max(subs))], share_failed=share, mean_failed=float(np.mean(failed)),
         n_inc_birth=len(inc_birth), n_inc_death=len(inc_death), med_inc_birth=mb, med_inc_death=md, delta=mb-md, excluded_no_maddison=excl, max_inc_death=float(max(inc_death)))
V=dict(PHD1=dict(ok=bool(DI>=1.5 and DI>p95),killed=bool(DI<=1.2)), PHD2=dict(ok=bool(share>=0.5),killed=bool(share<=0.35)), PHD3=dict(ok=bool(md<=mb-0.15),killed=bool(md>=mb)))
res['verdicts']=V; json.dump(res,open('/home/claude/hist002_results.json','w'),indent=1)
print({k:(round(v,3) if isinstance(v,float) else v) for k,v in res.items() if k!='verdicts'})
for k,v in V.items(): print(k,'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else 'не установлен'))
# descriptive: birth-year histogram by decade (both halves not needed; B only)
dec=(births//10)*10; import collections; print("births by decade (B):", dict(sorted(collections.Counter(dec).items())))
