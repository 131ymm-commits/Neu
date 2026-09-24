"""UNI-T1 — карта дуальности D1 по размеру V на Шлёгле: окно гистерезиса W(V) против часов CV_fwd/CV_back. Per PREREG (2026-09-04)."""
import json, time, numpy as np
h = {}
exec(open("/home/claude/pre005b_run.py").read().split("ck = json.load")[0], h)
u = {}
exec(open("/home/claude/uni07_run.py").read().split("# ---------- root sanity")[0], u)
sim_ext, drift, REC_DT = h["sim_ext"], h["drift"], h["REC_DT"]
sim_rev, rev, T_REV = u["sim_rev"], u["rev"], u["T_REV"]
t0=time.time(); res={}
VS=[20,50,100,200,500,1000,2000]; NREP=8
for V in VS:
    fw=sim_ext(drift, 30290854+V+154, NREP, V); w_f=[]; miss_f=0
    for r in range(NREP):
        c=np.flatnonzero(fw[r]>2.2)
        if c.size: w_f.append(float(drift(c[0]*REC_DT))-0.30)
        else: miss_f+=1
    bw=sim_rev(rev, 30290854+V+254, NREP, V, T_REV); w_b=[]; miss_b=0
    for r in range(NREP):
        c=np.flatnonzero(bw[r]<2.2)
        if c.size: w_b.append(1.10-float(rev(c[0]*REC_DT)))
        else: miss_b+=1
    cvf=float(np.std(w_f)/np.mean(w_f)) if len(w_f)>=5 else None
    cvb=float(np.std(w_b)/np.mean(w_b)) if len(w_b)>=5 else None
    W=(float(np.mean(w_f))+float(np.mean(w_b))-0.80) if (w_f and w_b) else None
    # LOO interval of CV_fwd
    loo=[float(np.std(np.delete(w_f,i))/np.mean(np.delete(w_f,i))) for i in range(len(w_f))] if len(w_f)>=5 else []
    res[str(V)]=dict(w_fwd=w_f,w_back=w_b,cv_fwd=cvf,cv_back=cvb,W=W,miss_f=miss_f,miss_b=miss_b,cv_fwd_loo=[min(loo),max(loo)] if loo else None)
    print(f"V={V}: W={None if W is None else round(W,3)} CV_fwd={None if cvf is None else round(cvf,3)} CV_back={None if cvb is None else round(cvb,3)} мимо {miss_f}/{miss_b} [{time.time()-t0:.0f}s]",flush=True)
    json.dump(res,open('/home/claude/unit1_results.json','w'),default=float,indent=1)
W0=res['2000']['W']
for V in VS: res[str(V)]['Wn']=(res[str(V)]['W']/W0) if (res[str(V)]['W'] is not None and W0) else None
def ok(v): return v is not None
# P-U1: exists V with CV_fwd>=0.5 and Wn>=0.5 ; killer: all V with CV_fwd>=0.5 have Wn<=0.25
hi=[V for V in VS if ok(res[str(V)]['cv_fwd']) and res[str(V)]['cv_fwd']>=0.5]
u1_ok=any(ok(res[str(V)]['Wn']) and res[str(V)]['Wn']>=0.5 for V in hi)
u1_kill=len(hi)>0 and all(ok(res[str(V)]['Wn']) and res[str(V)]['Wn']<=0.25 for V in hi)
# P-U1': Wn drops below 0.5 at a V where CV_fwd<0.2, and CV_fwd>=0.5 only where Wn<=0.25; killer: CV_fwd>=0.5 at any V with Wn>=0.5
low_w=[V for V in VS if ok(res[str(V)]['Wn']) and res[str(V)]['Wn']<0.5]
u1p_ok=any(ok(res[str(V)]['cv_fwd']) and res[str(V)]['cv_fwd']<0.2 for V in low_w) and all(ok(res[str(V)]['Wn']) and res[str(V)]['Wn']<=0.25 for V in hi)
u1p_kill=any(ok(res[str(V)]['Wn']) and res[str(V)]['Wn']>=0.5 for V in hi)
# P-U1b: CV_back >= CV_fwd for all V<=500 ; killer: CV_back<CV_fwd at >=2 of them
small=[V for V in VS if V<=500 and ok(res[str(V)]['cv_fwd']) and ok(res[str(V)]['cv_back'])]
u1b_ok=all(res[str(V)]['cv_back']>=res[str(V)]['cv_fwd'] for V in small)
u1b_kill=sum(1 for V in small if res[str(V)]['cv_back']<res[str(V)]['cv_fwd'])>=2
res['verdicts']=dict(PU1=dict(ok=bool(u1_ok),killed=bool(u1_kill)),PU1p=dict(ok=bool(u1p_ok),killed=bool(u1p_kill)),PU1b=dict(ok=bool(u1b_ok),killed=bool(u1b_kill)),
    chart={V:dict(Wn=res[str(V)]['Wn'],cv_fwd=res[str(V)]['cv_fwd'],cv_back=res[str(V)]['cv_back']) for V in VS})
json.dump(res,open('/home/claude/unit1_results.json','w'),default=float,indent=1)
print("\n== карта D1 (V: Wn, CV_fwd, CV_back) ==")
for V in VS: c=res['verdicts']['chart'][V]; print(V, {k:(None if v is None else round(v,3)) for k,v in c.items()})
for k in ('PU1','PU1p','PU1b'):
    v=res['verdicts'][k]; print(k,'ПОДТВЕРЖДЁН' if v['ok'] else ('УБИТ' if v['killed'] else 'не установлен'))
