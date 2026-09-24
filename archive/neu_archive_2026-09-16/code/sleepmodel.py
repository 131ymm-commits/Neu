"""BRAIN-002 phenomenological flip-flop sleep model (Wake/NREM/REM mutual inhibition + homeostat + noise).
Clearly a MODEL, not fit to any dataset. Produces metastable W/N/R states with Kramers switching; handle mu_R = REM propensity."""
import numpy as np

Fmax=6.0
def Sx(c, beta, alpha):
    return Fmax*0.5*(1.0+np.tanh((c-beta)/alpha))

def simulate(mu_R, seed, T=960.0, dt=0.05, rec=0.5,
             tauW=1.5, tauN=1.5, tauR=1.0, tauH=150.0, tauHs=80.0, taua=7.0,
             gNW=1.6, gRW=1.2, gWN=1.5, gRN=0.25, gWR=2.4, gNR=1.0, ga=5.0,
             kh=3.4, kc=3.0, Cwake=1.2, sigma=0.45, betaR=1.0):
    rng=np.random.default_rng(seed)
    nst=int(T/dt); nrec=int(rec/dt)
    fW,fN,fR=4.0,0.2,0.1; h=0.3; a=0.0
    rec_f=[]; sq=np.sqrt(dt)
    for i in range(nst):
        awake = fW> 2.5
        dh = ((1.0-h)/tauH) if awake else (-(h)/tauHs)
        # mutual inhibition; high sleep pressure h suppresses arousal; REM has adaptation a (self-terminating, recurs)
        iW = -gNW*fN - gRW*fR + Cwake - kc*h
        iN = -gWN*fW - gRN*fR + kh*h
        iR = -gWR*fW - gRN*fN*0 + gNR*fN + mu_R - ga*a
        fW += dt*((Sx(iW,0.0,0.4)-fW)/tauW) + sigma*sq*rng.standard_normal()
        fN += dt*((Sx(iN,0.0,0.4)-fN)/tauN) + sigma*sq*rng.standard_normal()
        fR += dt*((Sx(iR,betaR,0.4)-fR)/tauR) + sigma*sq*rng.standard_normal()
        fW=min(max(fW,0.0),Fmax); fN=min(max(fN,0.0),Fmax); fR=min(max(fR,0.0),Fmax)
        a += dt*((fR/Fmax)-a)/taua
        h=min(max(h+dt*dh,0.0),1.0)
        if i%nrec==0: rec_f.append((fW,fN,fR,h))
    A=np.array(rec_f)
    ref=np.argmax(A[:,:3],axis=1)  # 0=W,1=N,2=R
    return dict(F=A[:,:3], h=A[:,3], ref=ref)

if __name__=='__main__':
    for mu in (-0.8,-0.4,0.0,0.4,0.8):
        r=simulate(mu, 1)
        ref=r['ref']; frac=[float(np.mean(ref==s)) for s in (0,1,2)]
        sw=int(np.sum(np.diff(ref)!=0))
        print(f"mu_R={mu:+.1f}  W {frac[0]:.2f}  N {frac[1]:.2f}  R {frac[2]:.2f}  switches {sw}")
