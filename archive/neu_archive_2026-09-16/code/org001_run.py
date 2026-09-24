"""ORG-001 — IGOs as levels (COW IGO v3 via igoR). Per PREREG (2026-09-03)."""
import pandas as pd, numpy as np, json
d=pd.read_stata('/home/claude/igoR/data-raw/igo_stata/igo_year_format_3.dta', convert_categoricals=False)
meta={'ioname','orgname','year','integrated','replaced','longorgname','ionum','igocode','version','accuracyofpre1965membershipdates','sourcesandnotes','imputed','political','social','economic','dead','sdate','deaddate'}
country_cols=[c for c in d.columns if c not in meta]
M=(d[country_cols]==1).sum(axis=1)  # full members coded 1
d['nmem']=M
g=d.groupby('ionum').agg(name=('ioname','first'),sdate=('sdate','first'),deaddate=('deaddate','first'),dead=('dead','max'),integrated=('integrated','max'),replaced=('replaced','max'),peak=('nmem','max'),nrows=('year','count'))
out=dict(n_igo=int(len(g)))
rng=np.random.default_rng(0)
def DI(years, y0, y1, n_null=10000):
    yrs=np.arange(y0,y1+1); cnt=np.array([(years==y).sum() for y in yrs]); di=cnt.var()/cnt.mean()
    n=len(years); nulls=[]
    for _ in range(n_null):
        c=np.bincount(rng.integers(0,len(yrs),n),minlength=len(yrs)); nulls.append(c.var()/c.mean())
    return float(di), float(np.quantile(nulls,0.95)), cnt, yrs
sd=g.sdate.values.astype(int); sd=np.clip(sd,1816,2014)
di,p95,cnt,yrs=DI(sd,1816,2014); out.update(DI=di,null_p95=p95)
top=sorted(zip(cnt.tolist(),yrs.tolist()),reverse=True)[:8]; out['top_birth_years']={str(y):int(c) for c,y in top}
sub=[];
for _ in range(50):
    idx=rng.choice(len(sd),int(0.9*len(sd)),replace=False); sub.append(DI(sd[idx],1816,2014,n_null=200)[0])
out['DI_sub']=[float(min(sub)),float(max(sub))]
sd20=sd[sd>=1900]; out['DI_post1900']=DI(sd20,1900,2014,n_null=2000)[0]; out['null_p95_post1900']=DI(sd20,1900,2014,n_null=2000)[1]; out['n_pre1900']=int((sd<1900).sum())
# lifetimes
dd=g[g.dead==1].copy(); life=(dd.deaddate-dd.sdate).values.astype(float); life[life<=0]=0.5
out.update(n_dead=int(len(dd)),life_mean=float(life.mean()),life_median=float(np.median(life)),CV_life=float(life.std(ddof=1)/life.mean()))
cvs=[]
for _ in range(50):
    idx=rng.choice(len(life),int(0.9*len(life)),replace=False); l=life[idx]; cvs.append(l.std(ddof=1)/l.mean())
out['CV_sub']=[float(min(cvs)),float(max(cvs))]
# succession share (descriptive; seen before prereg)
succ=((dd.integrated==1)|(dd.replaced==1)).values; out['share_succession']=float(succ.mean()); out['n_succ']=int(succ.sum())
# P-O4 peak membership by death type
pk=dd.peak.values.astype(float); nomem=int((dd.nrows==0).sum()); out['n_no_membership_rows']=nomem
m_out=float(np.median(pk[~succ])); m_suc=float(np.median(pk[succ])); out.update(median_peak_outright=m_out,median_peak_succession=m_suc,ratio=m_suc/m_out if m_out>0 else None)
boots=[]
for _ in range(10000):
    a=rng.choice(pk[~succ],len(pk[~succ])); b=rng.choice(pk[succ],len(pk[succ])); ma=np.median(a); boots.append(np.median(b)/ma if ma>0 else np.nan)
boots=np.array(boots); out['ratio_ci95']=[float(np.nanquantile(boots,0.025)),float(np.nanquantile(boots,0.975))]
rep=(dd.replaced==1).values; integ=(dd.integrated==1).values
out['median_peak_replaced_only']=float(np.median(pk[rep])); out['median_peak_integrated_only']=float(np.median(pk[integ]))
out['mean_peak_outright']=float(pk[~succ].mean()); out['mean_peak_succession']=float(pk[succ].mean())
# verdicts
V=dict(PO1=dict(ok=bool(di>=3 and di>p95),killed=bool(di<=1.5)),
       PO2=dict(ok=bool(out['CV_life']>=0.7),killed=bool(out['CV_life']<=0.3)),
       PO4=dict(ok=bool(out['ratio'] is not None and out['ratio']>=1.5),killed=bool(out['ratio'] is not None and out['ratio']<=1.0)))
out['verdicts']=V
json.dump(out,open('/home/claude/org001_results.json','w'),indent=1)
for k,v in out.items():
    if k!='verdicts': print(k, v if not isinstance(v,float) else round(v,3))
for k,v in V.items(): print(k,'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else 'не установлен'))
