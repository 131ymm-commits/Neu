"""UNI-T2 часть b — двухпопуляционный flip-flop W–N (взаимное торможение, пороговые S-функции) с ручкой b (драйв N); ось шума σ.
Рождение сна: рампа b вверх, первый committed fW<Fmax/2; смерть сна: рампа b вниз, первый committed fW>Fmax/2."""
import numpy as np, json
Fmax=6.0; BETA=1.0; ALPHA=0.4; CW=2.0; G=0.6; TAU=1.5
def S(c): return Fmax*0.5*(1+np.tanh((c-BETA)/ALPHA))
def run(b_sched, seed, sigma, T=600.0, dt=0.05, rec=0.5, start_awake=True):
    rng=np.random.default_rng(seed); nst=int(T/dt); nrec=int(rec/dt); sq=np.sqrt(dt)
    fW,fN=(5.5,0.1) if start_awake else (0.1,5.5); out=[]
    for i in range(nst):
        b=b_sched(i*dt)
        fW+=dt*((S(CW-G*fN)-fW)/TAU)+sigma*sq*rng.standard_normal()
        fN+=dt*((S(b-G*fW)-fN)/TAU)+sigma*sq*rng.standard_normal()
        fW=min(max(fW,0),Fmax); fN=min(max(fN,0),Fmax)
        if i%nrec==0: out.append((b,fW))
    return np.array(out)
def first_committed(arr, cond, persist):
    ok=cond(arr[:,1]).astype(int); n=len(ok); i=0
    while i<n:
        if ok[i]:
            j=i
            while j<n and ok[j]: j+=1
            if j-i>=persist: return float(arr[i,0])
            i=j
        else: i+=1
    return None
BLO,BHI,T=0.0,8.0,600.0
up=lambda t: BLO+(BHI-BLO)*min(t/T,1.0); dn=lambda t: BHI-(BHI-BLO)*min(t/T,1.0)
PERS=10
d_up=run(up,0,0.0); d_dn=run(dn,0,0.0,start_awake=False)
kb0=first_committed(d_up,lambda f:f<Fmax/2,PERS); kd0=first_committed(d_dn,lambda f:f>Fmax/2,PERS)
Wdet=(kb0-kd0) if (kb0 is not None and kd0 is not None) else None
print(f"детерминированно: рождение сна b_up={kb0}, смерть сна b_down={kd0}, W_det={Wdet}",flush=True)
res={'det':dict(b_up=kb0,b_down=kd0,W=Wdet)}
for s in (0.15,0.30,0.45,0.60,0.80):
    kb=[];kd=[];mb=0;md=0
    for r in range(8):
        a=run(up,100+r,s); v=first_committed(a,lambda f:f<Fmax/2,PERS)
        if v is None: mb+=1
        else: kb.append(v)
        bb=run(dn,200+r,s,start_awake=False); w=first_committed(bb,lambda f:f>Fmax/2,PERS)
        if w is None: md+=1
        else: kd.append(w)
    kb=np.array(kb); kd=np.array(kd)
    W=(kb.mean()-kd.mean()) if (len(kb) and len(kd)) else None
    cvb=float(np.std(kb-BLO,ddof=1)/np.mean(kb-BLO)) if len(kb)>=5 else None
    cvd=float(np.std(BHI-kd,ddof=1)/np.mean(BHI-kd)) if len(kd)>=5 else None
    res[str(s)]=dict(kb=kb.tolist(),kd=kd.tolist(),W=W,Wn=(W/Wdet) if (W is not None and Wdet) else None,cv_birth=cvb,cv_death=cvd,
                    std_kb=float(kb.std(ddof=1)) if len(kb)>2 else None,std_kd=float(kd.std(ddof=1)) if len(kd)>2 else None,miss_b=mb,miss_d=md)
    r_=res[str(s)]
    print(f"σ={s}: b_up={kb.mean():.3f}±{r_['std_kb']} b_down={kd.mean():.3f}±{r_['std_kd']} W={W:.3f} Wn={r_['Wn']:.3f} CV_b={cvb:.3f} CV_d={cvd:.3f} мимо {mb}/{md}",flush=True)
    json.dump(res,open('/home/claude/unit2b_results.json','w'),indent=1,default=float)
Sk=[k for k in res if k!='det']
hi=[k for k in Sk if res[k]['cv_birth'] is not None and res[k]['cv_birth']>=0.5]
okA=any(res[k]['Wn'] is not None and res[k]['Wn']<0.5 and res[k]['cv_birth'] is not None and res[k]['cv_birth']<0.2 for k in Sk) and all(res[k]['Wn'] is not None and res[k]['Wn']<=0.25 for k in hi)
killA=any(res[k]['Wn'] is not None and res[k]['Wn']>=0.5 for k in hi)
res['verdict_PA2a']='ПОДТВЕРЖДЁН' if okA else ('УБИТ' if killA else 'не установлен')
res['PA2b_sign']={k:('смерть шумовее' if (res[k]['std_kd'] or 0)>(res[k]['std_kb'] or 0) else 'рождение шумовее') for k in Sk}
json.dump(res,open('/home/claude/unit2b_results.json','w'),indent=1,default=float)
print("P-A2a:",res['verdict_PA2a']); print("P-A2b знаки:",res['PA2b_sign'])
