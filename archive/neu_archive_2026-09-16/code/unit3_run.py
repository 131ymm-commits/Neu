"""UNI-T3 — blind test of the barrier rule: noise sweeps on sets D (handle N), E, G (handle W). Per PREREG (2026-09-04)."""
import numpy as np, json, time
Fmax=6.0; beta,alpha=1.0,0.4; TAU=1.5
def S(c): return Fmax*0.5*(1+np.tanh((c-beta)/alpha))
def run(h_sched, seed, sigma, handle, P, start_awake, T=600.0, dt=0.05, rec=0.5):
    rng=np.random.default_rng(seed); nst=int(T/dt); nrec=int(rec/dt); sq=np.sqrt(dt)
    x,y=(5.5,0.1) if start_awake else (0.1,5.5); out=[]
    for i in range(nst):
        h=h_sched(i*dt); cw,cn=(P['cw'],h) if handle=='N' else (h,P['cn'])
        x+=dt*((S(cw-P['G1']*y)-x)/TAU)+sigma*sq*rng.standard_normal()
        y+=dt*((S(cn-P['G2']*x)-y)/TAU)+sigma*sq*rng.standard_normal()
        x=min(max(x,0),Fmax); y=min(max(y,0),Fmax)
        if i%nrec==0: out.append((h,x))
    return np.array(out)
def first_committed(arr,cond,persist=10):
    ok=cond(arr[:,1]).astype(int); n=len(ok); i=0
    while i<n:
        if ok[i]:
            j=i
            while j<n and ok[j]: j+=1
            if j-i>=persist: return float(arr[i,0])
            i=j
        else: i+=1
    return None
pred=json.load(open('/home/claude/ff_qp_pred2.json'))
SETS=['D','E','G']; NREP=10; res={}; t0=time.time()
for name in SETS:
    handle=pred[name]['handle']; P=pred[name]['params']; lo,hi=pred[name]['folds']; a,b=lo-0.5,hi+0.5
    if handle=='N':   # birth: cn up (start awake); death: cn down (start asleep)
        birth_s=lambda t,a=a,b=b: a+(b-a)*min(t/600,1); death_s=lambda t,a=a,b=b: b-(b-a)*min(t/600,1)
    else:             # handle W: birth: cw down (start awake); death: cw up (start asleep)
        birth_s=lambda t,a=a,b=b: b-(b-a)*min(t/600,1); death_s=lambda t,a=a,b=b: a+(b-a)*min(t/600,1)
    res[name]={'handle':handle,'params':P,'folds':[lo,hi],'pred':pred[name]['pred']['1.0']['noisier']}
    for s in (0.5,0.8):
        hb=[];hd=[];mb=0;md=0
        for r in range(NREP):
            A=run(birth_s,300+r,s,handle,P,True); v=first_committed(A,lambda f:f<Fmax/2)
            if v is None: mb+=1
            else: hb.append(v)
            B=run(death_s,400+r,s,handle,P,False); w=first_committed(B,lambda f:f>Fmax/2)
            if w is None: md+=1
            else: hd.append(w)
        hb=np.array(hb); hd=np.array(hd)
        sb=float(hb.std(ddof=1)) if len(hb)>2 else None; sd=float(hd.std(ddof=1)) if len(hd)>2 else None
        # hysteresis window sign-aware: for handle N birth at high h, death at low h -> W=mean(hb)-mean(hd); for handle W birth at low cw, death at high cw -> W=mean(hd)-mean(hb)
        W=(hb.mean()-hd.mean()) if handle=='N' else (hd.mean()-hb.mean())
        Wdet=(hi-lo)
        obs=None if not(sb and sd) else ('birth' if sb>sd else 'death')
        res[name][str(s)]=dict(std_birth=sb,std_death=sd,ratio_birth_over_death=(sb/sd) if (sb and sd) else None,mean_birth=float(hb.mean()),mean_death=float(hd.mean()),Wn=W/Wdet,miss=[mb,md],observed_noisier=obs,match=(obs==res[name]['pred']) if obs else None)
        print(f"набор {name} σ={s}: std_рожд={sb:.3f} std_смерть={sd:.3f} отношение={sb/sd:.2f} Wn={W/Wdet:.2f} мимо {mb}/{md} → наблюдено шумовее: {obs}; предсказано: {res[name]['pred']} → {'СОВПАЛО' if obs==res[name]['pred'] else 'НЕ совпало'} [{time.time()-t0:.0f}s]",flush=True)
        json.dump(res,open('/home/claude/unit3_results.json','w'),indent=1,default=float)
m05=[res[n]['0.5']['match'] for n in SETS];
res['verdict']=dict(matches_sigma05=sum(1 for m in m05 if m), PB1='ПОДТВЕРЖДЁН' if sum(1 for m in m05 if m)==3 else ('УБИТ' if sum(1 for m in m05 if m is False)>=2 else 'не установлен'))
json.dump(res,open('/home/claude/unit3_results.json','w'),indent=1,default=float)
print("P-B1:",res['verdict'])
