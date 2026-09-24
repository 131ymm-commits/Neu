"""gMAM wrapper (adapted from pascalwangt/PyGMAM, Heymann & Vanden-Eijnden 2008) + geometric action.
Quasi-potential barrier from node xA to saddle xB for dX = b(X)dt + sigma dW with a = I:
  S_geom = ∫ (|phi'| |b(phi)| − phi'·b(phi)) dα ;  escape rate ∝ exp(−S_geom / (sigma^2/2))  (FW: rate ~ exp(-2S/sigma^2))."""
import numpy as np, sympy as sp, scipy.linalg, scipy.interpolate

def make_system(b_sym, xsyms):
    dim=len(xsyms); psyms=sp.symbols(f'p:{dim}'); p=sp.Matrix(psyms); x=sp.Matrix(xsyms); b=sp.Matrix(b_sym)
    a=sp.eye(dim); a_inv=a
    ham=(b.T*p+sp.Rational(1,2)*p.T*a*p)
    ham_p=ham.jacobian(p); ham_x=ham.jacobian(x); ham_px=ham_p.jacobian(x); ham_pp=ham_p.jacobian(p)
    theta=a_inv*(b.T.dot(a_inv*b)/p.T.dot(a_inv*p)*p-b)
    args=list(xsyms)+list(psyms)
    return dict(dim=dim,
        b_np=sp.lambdify(list(xsyms), b, "numpy"),
        ham_p=sp.lambdify(args, ham_p, "numpy"), ham_px=sp.lambdify(args, ham_px, "numpy"),
        ham_pp_x=sp.lambdify(args, ham_pp*ham_x.T, "numpy"), theta=sp.lambdify(args, theta, "numpy"))

def gmam(sysd, xA, xB, N=300, delta_tau=0.05, kmax=400, threshold=1e-3, init=None, verbose=False):
    dim=sysd['dim']; xA=np.asarray(xA,float); xB=np.asarray(xB,float)
    if init is None:
        s=np.linspace(0,1,N); phi=np.outer(xA,1-s)+np.outer(xB,s)
    else: phi=init.copy()
    incr=np.inf; k=1
    while k<kmax and incr>threshold:
        dphi=(phi[:,2:]-phi[:,:-2])/(2/N)
        th=np.squeeze(sysd['theta'](*phi[:,1:-1],*dphi))
        if th.ndim==1: th=th.reshape(dim,-1)
        hp=np.squeeze(sysd['ham_p'](*phi[:,1:-1],*th));
        if hp.ndim==1: hp=hp.reshape(dim,-1)
        lam=np.einsum('ij,ij->j',hp,dphi)/np.linalg.norm(dphi,axis=0)
        lam0=3*lam[0]-3*lam[1]+lam[2]; lamN=3*lam[-1]-3*lam[-2]+lam[-3]
        lamf=np.insert(np.append(lam,lamN),0,lam0); lamp=(lamf[2:]-lamf[:-2])/(2/N)
        Hpx=np.array([np.array(sysd['ham_px'](*xx,*pp),float).reshape(dim,dim) for xx,pp in zip(phi[:,1:-1].T,th.T)])
        t2=lam*np.einsum('ijk,ki->ji',Hpx,dphi)
        t3=np.squeeze(sysd['ham_pp_x'](*phi[:,1:-1],*th));
        if t3.ndim==1: t3=t3.reshape(dim,-1)
        t4=lam*lamp*dphi; lh=phi[:,1:-1]/delta_tau
        B=np.empty((dim,N)); B[:,0]=xA; B[:,-1]=xB; B[:,1:-1]=-t2+t3+t4+lh
        diag=np.ones(N); diag[1:-1]=1/delta_tau+2*N**2*lam**2; band=-lam**2*N**2
        ab=np.zeros((3,N)); ab[0,2:]=band; ab[1]=diag; ab[2,:-2]=band
        phit=scipy.linalg.solve_banded((1,1),ab,B.T)
        tck,u=scipy.interpolate.splprep(phit.T,k=1,s=0); f=scipy.interpolate.CubicSpline(u,phit)
        upd=f(np.linspace(0,1,N)).T
        incr=np.sum(np.linalg.norm(upd-phi,axis=0)); phi=upd; k+=1
    # geometric action along converged curve (a = I)
    d=np.gradient(phi,axis=1)*N  # dphi/dα
    bb=np.array([np.array(sysd['b_np'](*xx),float).ravel() for xx in phi.T]).T
    integrand=np.linalg.norm(d,axis=0)*np.linalg.norm(bb,axis=0)-np.einsum('ij,ij->j',d,bb)
    S=float(np.trapezoid(integrand, dx=1.0/N)) if hasattr(np,'trapezoid') else float(np.trapz(integrand,dx=1.0/N))
    return dict(path=phi, S=S, iters=k, incr=incr)

if __name__=='__main__':
    # validation: 2D double well b = (x - x^3, -y); barrier from (-1,0) to saddle (0,0): U = -x^2/2 + x^4/4 → ΔU = 1/4; S_geom = 2ΔU?? For gradient b=-∇U with a=I: S_geom = ΔU*? check numerically
    xs=sp.symbols('x0 x1'); x,y=xs
    sysd=make_system([x-x**3,-y],xs)
    r=gmam(sysd,[-1,0],[0,0],N=200,delta_tau=0.05,kmax=300)
    print("double well: S_geom node->saddle =",round(r['S'],4),"(ΔU = 0.25; FW quasipotential V = 2ΔU = 0.5 for b=-∇U, a=I; geometric action S = V/2 = ΔU → expect 0.25) iters",r['iters'],"incr",r['incr'])
