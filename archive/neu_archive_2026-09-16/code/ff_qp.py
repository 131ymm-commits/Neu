"""Quasi-potential barriers of the 2-population flip-flop vs handle b, via gMAM (gmam_lib). Predict which direction is noisier
under a ramp: dispersion ∝ 1/|dΔΦ/db| at matched barrier level → smaller slope = noisier."""
import numpy as np, sympy as sp, json, sys
from scipy.optimize import fsolve
sys.path.insert(0,'/home/claude'); from gmam_lib import make_system, gmam
Fmax=6.0
def S_np(c,beta,alpha): return Fmax*0.5*(1+np.tanh((c-beta)/alpha))
def fixed_points(bh,CW,G,beta,alpha):
    f=lambda v: [S_np(CW-G*v[1],beta,alpha)-v[0], S_np(bh-G*v[0],beta,alpha)-v[1]]
    pts=[]
    for x0 in (0.05,1,3,5.5):
        for y0 in (0.05,1,3,5.5):
            s,info,ier,msg=fsolve(f,[x0,y0],full_output=True)
            if ier==1 and np.linalg.norm(f(s))<1e-8 and all(-0.5<=v<=Fmax+0.5 for v in s):
                if not any(np.linalg.norm(s-q)<1e-4 for q in pts): pts.append(np.array(s))
    # classify by Jacobian
    def jac(v):
        eps=1e-6; J=np.zeros((2,2)); f0=np.array(f(v))
        for j in range(2):
            d=np.zeros(2); d[j]=eps; J[:,j]=(np.array(f(v+d))-f0)/eps
        return J
    nodes=[];saddles=[]
    for q in pts:
        ev=np.linalg.eigvals(jac(q))
        (nodes if np.all(ev.real<0) else saddles).append(q)
    return nodes,saddles
def barriers(bh,CW,G,beta,alpha,N=200):
    nodes,sad=fixed_points(bh,CW,G,beta,alpha)
    if len(nodes)<2 or len(sad)<1: return None
    W=max(nodes,key=lambda q:q[0]); Nn=max(nodes,key=lambda q:q[1]); s=sad[0]
    x0,x1=sp.symbols('x0 x1')
    S=lambda c: Fmax/2*(1+sp.tanh((c-beta)/alpha))
    sysd=make_system([S(CW-G*x1)-x0, S(bh-G*x0)-x1],(x0,x1))
    rW=gmam(sysd,W,s,N=N,delta_tau=0.02,kmax=600,threshold=1e-3)
    rN=gmam(sysd,Nn,s,N=N,delta_tau=0.02,kmax=600,threshold=1e-3)
    return dict(b=bh,W=W.tolist(),N=Nn.tolist(),saddle=s.tolist(),dPhi_W=rW['S'],dPhi_N=rN['S'],itW=rW['iters'],itN=rN['iters'])
def scan(CW,G,beta,alpha,bs):
    out=[]
    for bh in bs:
        r=barriers(bh,CW,G,beta,alpha)
        if r: out.append(r)
    return out
def slopes_at_level(out, level):
    """slope |dΔΦ/db| where ΔΦ_dir(b)=level, for W (birth: escape from wake) and N (death: escape from sleep)."""
    b=np.array([r['b'] for r in out]); dW=np.array([r['dPhi_W'] for r in out]); dN=np.array([r['dPhi_N'] for r in out])
    res={}
    for name,arr in (('W',dW),('N',dN)):
        # find crossing of level
        idx=np.flatnonzero(np.diff(np.sign(arr-level)))
        if idx.size==0: res[name]=None; continue
        i=idx[0]; bcross=b[i]+(level-arr[i])*(b[i+1]-b[i])/(arr[i+1]-arr[i])
        slope=abs((arr[i+1]-arr[i])/(b[i+1]-b[i]))
        res[name]=dict(b=float(bcross),slope=float(slope))
    return res
if __name__=='__main__':
    CW,G,beta,alpha=2.0,0.6,1.0,0.4
    bs=np.linspace(1.0,4.1,32)
    out=scan(CW,G,beta,alpha,bs)
    print("b    ΔΦ_W(рожд.сна: выход из W)  ΔΦ_N(смерть сна: выход из N)")
    for r in out: print(f"{r['b']:.2f}   {r['dPhi_W']:.4f}   {r['dPhi_N']:.4f}   (it {r['itW']}/{r['itN']})")
    json.dump(out,open('/home/claude/ff_qp_base.json','w'),indent=1)
    for lev in (0.3,0.7,1.3,2.0):
        s=slopes_at_level(out,lev)
        print(f"уровень барьера {lev}: W {s['W']}  N {s['N']}  → шумовее:", ('рождение (W)' if (s['W'] and s['N'] and s['W']['slope']<s['N']['slope']) else 'смерть (N)') if (s['W'] and s['N']) else 'н/д')
