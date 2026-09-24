"""Blind prediction: barrier slopes for NEW asymmetric flip-flop parameter sets (G1: W inhibited by N; G2: N inhibited by W)."""
import numpy as np, sympy as sp, json, sys, time
from scipy.optimize import fsolve
sys.path.insert(0,'/home/claude'); from gmam_lib import make_system, gmam
Fmax=6.0
def S_np(c,beta,alpha): return Fmax*0.5*(1+np.tanh((c-beta)/alpha))
def fixed_points(bh,CW,G1,G2,beta,alpha):
    f=lambda v:[S_np(CW-G1*v[1],beta,alpha)-v[0], S_np(bh-G2*v[0],beta,alpha)-v[1]]
    pts=[]
    for x0 in (0.05,1,3,5.5):
        for y0 in (0.05,1,3,5.5):
            s,info,ier,msg=fsolve(f,[x0,y0],full_output=True)
            if ier==1 and np.linalg.norm(f(s))<1e-8 and all(-0.5<=v<=Fmax+0.5 for v in s) and not any(np.linalg.norm(s-q)<1e-4 for q in pts): pts.append(np.array(s))
    def jac(v):
        eps=1e-6; J=np.zeros((2,2)); f0=np.array(f(v))
        for j in range(2):
            d=np.zeros(2); d[j]=eps; J[:,j]=(np.array(f(v+d))-f0)/eps
        return J
    nodes=[q for q in pts if np.all(np.linalg.eigvals(jac(q)).real<0)]; sad=[q for q in pts if not np.all(np.linalg.eigvals(jac(q)).real<0)]
    return nodes,sad
def barriers(bh,CW,G1,G2,beta,alpha,N=160):
    nodes,sad=fixed_points(bh,CW,G1,G2,beta,alpha)
    if len(nodes)<2 or len(sad)<1: return None
    W=max(nodes,key=lambda q:q[0]); Nn=max(nodes,key=lambda q:q[1]); s=sad[0]
    x0,x1=sp.symbols('x0 x1'); S=lambda c: Fmax/2*(1+sp.tanh((c-beta)/alpha))
    sysd=make_system([S(CW-G1*x1)-x0, S(bh-G2*x0)-x1],(x0,x1))
    rW=gmam(sysd,W,s,N=N,delta_tau=0.02,kmax=500,threshold=2e-3); rN=gmam(sysd,Nn,s,N=N,delta_tau=0.02,kmax=500,threshold=2e-3)
    return dict(b=float(bh),dPhi_W=rW['S'],dPhi_N=rN['S'])
def slopes_at_level(out,level):
    b=np.array([r['b'] for r in out]); res={}
    for name in ('W','N'):
        arr=np.array([r['dPhi_'+name] for r in out]); idx=np.flatnonzero(np.diff(np.sign(arr-level)))
        if idx.size==0: res[name]=None; continue
        i=idx[0]; res[name]=dict(b=float(b[i]+(level-arr[i])*(b[i+1]-b[i])/(arr[i+1]-arr[i])),slope=float(abs((arr[i+1]-arr[i])/(b[i+1]-b[i]))))
    return res
SETS={'A':dict(CW=2.0,G1=0.6,G2=1.2),'B':dict(CW=3.0,G1=1.0,G2=0.6),'C':dict(CW=1.5,G1=0.4,G2=0.8),'D':dict(CW=2.0,G1=1.2,G2=0.6)}
beta,alpha=1.0,0.4; t0=time.time(); allres={}
for name,P in SETS.items():
    # find bistable range by scanning fixed points
    bs=np.linspace(0.2,9.0,89); bist=[bh for bh in bs if (lambda n_s: len(n_s[0])>=2 and len(n_s[1])>=1)(fixed_points(bh,P['CW'],P['G1'],P['G2'],beta,alpha))]
    if not bist: print(name,'нет бистабильности'); continue
    lo,hi=min(bist),max(bist); grid=np.linspace(lo+0.02,hi-0.02,14)
    out=[r for r in (barriers(bh,P['CW'],P['G1'],P['G2'],beta,alpha) for bh in grid) if r]
    pred={}
    for lev in (0.7,1.3,2.0):
        s=slopes_at_level(out,lev)
        pred[str(lev)]=None if not (s['W'] and s['N']) else ('birth' if s['W']['slope']<s['N']['slope'] else 'death')
        pred[str(lev)+'_slopes']=s
    allres[name]=dict(params=P,bistable=[float(lo),float(hi)],scan=out,pred=pred)
    print(f"набор {name} {P}: бистабильно b∈[{lo:.2f},{hi:.2f}]; предсказание (шумовее) по уровням 0.7/1.3/2.0 →",pred['0.7'],pred['1.3'],pred['2.0'],f"[{time.time()-t0:.0f}s]",flush=True)
    json.dump(allres,open('/home/claude/ff_qp_pred.json','w'),indent=1,default=float)
