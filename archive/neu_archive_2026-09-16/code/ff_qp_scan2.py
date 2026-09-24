"""Blind barrier-rule predictions on new flip-flop sets. Model: x'=S(cw-G1*y)-x, y'=S(cn-G2*x)-y (x=wake, y=sleep).
Handle = cn ('N') or cw ('W'). Sleep birth = escape from wake node; sleep death = escape from sleep node.
Folds by bisection; geometric grid toward each fold; slopes |dΔΦ/dh| at matched barrier levels."""
import numpy as np, sympy as sp, json, sys, time
from scipy.optimize import fsolve
sys.path.insert(0,'/home/claude'); from gmam_lib import make_system, gmam
Fmax=6.0; beta,alpha=1.0,0.4
def S_np(c): return Fmax*0.5*(1+np.tanh((c-beta)/alpha))
def fps(cw,cn,G1,G2):
    f=lambda v:[S_np(cw-G1*v[1])-v[0], S_np(cn-G2*v[0])-v[1]]
    pts=[]
    for x0 in np.linspace(0.05,5.9,6):
        for y0 in np.linspace(0.05,5.9,6):
            s,info,ier,msg=fsolve(f,[x0,y0],full_output=True)
            if ier==1 and np.linalg.norm(f(s))<1e-9 and all(-0.2<=v<=Fmax+0.2 for v in s) and not any(np.linalg.norm(s-q)<1e-5 for q in pts): pts.append(np.array(s))
    def jac(v):
        eps=1e-6; J=np.zeros((2,2)); f0=np.array(f(v))
        for j in range(2):
            d=np.zeros(2); d[j]=eps; J[:,j]=(np.array(f(v+d))-f0)/eps
        return J
    nodes=[q for q in pts if np.all(np.linalg.eigvals(jac(q)).real<0)]; sad=[q for q in pts if not np.all(np.linalg.eigvals(jac(q)).real<0)]
    return nodes,sad
def bistable(h,handle,P):
    cw,cn=(P['cw'],h) if handle=='N' else (h,P['cn'])
    n,s=fps(cw,cn,P['G1'],P['G2']); return len(n)>=2 and len(s)>=1
def find_folds(handle,P,lo=-2.0,hi=12.0):
    hs=np.linspace(lo,hi,281); bi=[h for h in hs if bistable(h,handle,P)]
    if not bi: return None
    a,b=min(bi),max(bi)
    # bisection on each edge
    def bis(inside,outside):
        for _ in range(30):
            m=0.5*(inside+outside)
            if bistable(m,handle,P): inside=m
            else: outside=m
        return inside
    return bis(a,a-0.05), bis(b,b+0.05)
def barriers(h,handle,P,N=160):
    cw,cn=(P['cw'],h) if handle=='N' else (h,P['cn'])
    nodes,sad=fps(cw,cn,P['G1'],P['G2'])
    if len(nodes)<2 or len(sad)<1: return None
    W=max(nodes,key=lambda q:q[0]); Nn=max(nodes,key=lambda q:q[1]); s=sad[0]
    x0,x1=sp.symbols('x0 x1'); S=lambda c: Fmax/2*(1+sp.tanh((c-beta)/alpha))
    sysd=make_system([S(cw-P['G1']*x1)-x0, S(cn-P['G2']*x0)-x1],(x0,x1))
    rW=gmam(sysd,W,s,N=N,delta_tau=0.02,kmax=600,threshold=2e-3); rN=gmam(sysd,Nn,s,N=N,delta_tau=0.02,kmax=600,threshold=2e-3)
    return dict(h=float(h),dPhi_W=rW['S'],dPhi_N=rN['S'])
def geo_grid(lo,hi):
    d=np.array([0.005,0.01,0.02,0.04,0.08,0.16,0.32,0.64,1.28])
    g=np.concatenate([lo+d, hi-d, np.linspace(lo,hi,7)[1:-1]]); g=g[(g>lo)&(g<hi)]; return np.unique(np.round(g,5))
def slope_at_level(scan,key,level):
    h=np.array([r['h'] for r in scan]); arr=np.array([r[key] for r in scan]); o=np.argsort(h); h,arr=h[o],arr[o]
    idx=np.flatnonzero(np.diff(np.sign(arr-level)))
    if idx.size==0: return None
    i=idx[0]; return dict(h=float(h[i]+(level-arr[i])*(h[i+1]-h[i])/(arr[i+1]-arr[i])), slope=float(abs((arr[i+1]-arr[i])/(h[i+1]-h[i]))))
SETS={'A':('N',dict(cw=2.0,G1=0.6,G2=1.2)),'D':('N',dict(cw=2.0,G1=1.2,G2=0.6)),
      'E':('W',dict(cn=2.0,G1=0.6,G2=0.6)),'F':('W',dict(cn=2.0,G1=1.2,G2=0.6)),'G':('W',dict(cn=2.5,G1=0.6,G2=1.2))}
t0=time.time(); allres={}
for name,(handle,P) in SETS.items():
    f=find_folds(handle,P)
    if not f: print(name,'нет бистабильности'); continue
    lo,hi=f; grid=geo_grid(lo,hi)
    scan=[r for r in (barriers(h,handle,P) for h in grid) if r]
    pred={}
    for lev in (0.5,1.0,2.0):
        sW=slope_at_level(scan,'dPhi_W',lev); sN=slope_at_level(scan,'dPhi_N',lev)
        pred[str(lev)]=dict(W=sW,N=sN,noisier=None if not(sW and sN) else ('birth' if sW['slope']<sN['slope'] else 'death'))
    allres[name]=dict(handle=handle,params=P,folds=[lo,hi],scan=scan,pred=pred)
    print(f"набор {name} ручка={handle} {P}: фолды [{lo:.3f},{hi:.3f}] n_scan={len(scan)}; шумовее по уровням 0.5/1/2 →",[pred[k]['noisier'] for k in ('0.5','1.0','2.0')],
          "наклоны W/N @1:",None if not pred['1.0']['W'] else round(pred['1.0']['W']['slope'],2),None if not pred['1.0']['N'] else round(pred['1.0']['N']['slope'],2),f"[{time.time()-t0:.0f}s]",flush=True)
    json.dump(allres,open('/home/claude/ff_qp_pred2.json','w'),indent=1,default=float)
