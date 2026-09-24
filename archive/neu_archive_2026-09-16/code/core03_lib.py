"""CORE-03 — predictor-class-relative irreducibility of a level.
f_C = (I(S_t;S_{t+tau}) - max_{c in C} I(c(x_t); S_{t+tau})) / I(S_t;S_{t+tau})
C = axes (single micro), linear (best linear score), nonlinear (cross-validated flexible classifier).
Ordering by construction: f_nonlin <= f_lin <= f_axis. Two-number fingerprint:
  D = f_axis - f_lin  (distributedness / basis sensitivity)
  N = f_lin - f_nonlin (nonlinearity: need a curved boundary)
"""
import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold

def disc_mi(a, b):
    ja=np.unique(a,return_inverse=True)[1]; jb=np.unique(b,return_inverse=True)[1]
    C=np.zeros((ja.max()+1,jb.max()+1)); np.add.at(C,(ja,jb),1.0); p=C/C.sum()
    pa=p.sum(1,keepdims=True); pb=p.sum(0,keepdims=True); nz=p>0
    return float((p[nz]*np.log(p[nz]/(pa@pb)[nz])).sum())

def _binq(v, nb=8):
    q=np.quantile(v,np.linspace(0,1,nb+1)[1:-1]); return np.searchsorted(q,v)

def f_curve(S, X, tau, nb=8, seed=0, folds=5, do_nonlin=True):
    """S: (n,) integer macrostate; X: (n,d) micro features; returns dict with I, f_axis, f_lin, f_nonlin, D, N."""
    S=np.asarray(S); X=np.asarray(X,float); n=len(S)
    St, Sp = S[:-tau], S[tau:]; Xt = X[:-tau]
    I = disc_mi(St, Sp)
    if I<=1e-9 or len(np.unique(Sp))<2:
        return dict(I=I, f_axis=np.nan, f_lin=np.nan, f_nonlin=np.nan, D=np.nan, N=np.nan)
    # axis: best single micro predicting Sp
    Iax=max(disc_mi(_binq(Xt[:,j],nb), Sp) for j in range(Xt.shape[1]))
    # linear: Fisher LDA (solver='svd' handles rank-deficiency; invariant to invertible linear maps of x by
    # construction on the data span, so f_lin is coordinate-free unlike f_axis). MI of binned LDA score(s).
    try:
        lda=LinearDiscriminantAnalysis(solver='svd').fit(Xt, Sp)
        Z=lda.transform(Xt)                        # (n, C-1) discriminant coords
        if Z.shape[1]==1:
            Ilin=disc_mi(_binq(Z[:,0],nb), Sp)
        else:
            # multiclass: MI of the joint bin of the two leading discriminants + LDA's own predicted class
            b=_binq(Z[:,0],nb)*nb+_binq(Z[:,1],nb) if Z.shape[1]>=2 else _binq(Z[:,0],nb)
            Ilin=max(disc_mi(b,Sp), disc_mi(lda.predict(Xt),Sp))
    except Exception:
        Ilin=Iax
    Ilin=max(Ilin,Iax)  # linear class contains axes; enforce monotonicity against estimator noise
    # nonlinear: cross-validated OOF predictions of a flexible classifier
    Inl=Ilin
    if do_nonlin and n>200:
        try:
            oof=np.zeros(len(Sp),int)
            skf=StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
            for tr,te in skf.split(Xt,Sp):
                clf=HistGradientBoostingClassifier(max_depth=3,max_iter=120,learning_rate=0.1,random_state=seed)
                clf.fit(Xt[tr],Sp[tr]); oof[te]=clf.predict(Xt[te])
            Inl=max(disc_mi(oof,Sp), Ilin)  # nonlinear class contains linear; enforce monotonicity
        except Exception:
            Inl=Ilin
    fa=(I-Iax)/I; fl=(I-Ilin)/I; fn=(I-Inl)/I
    return dict(I=I, Iax=Iax, Ilin=Ilin, Inl=Inl, f_axis=fa, f_lin=fl, f_nonlin=fn, D=fa-fl, N=fl-fn)
