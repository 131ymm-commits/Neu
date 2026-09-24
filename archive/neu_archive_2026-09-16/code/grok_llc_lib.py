"""GROK-LLC — обучение x²-сети (динамика GROK-005: LR 10, WD 3e-4, D 512, полный батч) с сохранением чекпоинтов
и оценка локального коэффициента обучения (LLC) через devinterp 1.3.2 (SGLD, Lau и др. 2023)."""
import numpy as np, torch, sys, time
sys.path.insert(0, '/home/claude')
exec(open('/home/claude/grok_cal.py').read().split('def run(')[0])   # P=53, FRAC=0.5, make_data
from devinterp.optim.sgld import SGLD
from devinterp.slt.sampler import estimate_learning_coeff_with_summary
LR, WD, D = 10.0, 3e-4, 512

def train_ckpt(data_seed, init_seed, steps=450, every=5, budget=None):
    (Xtr, Ytr), (Xte, Yte) = make_data(data_seed)
    rng = np.random.default_rng(init_seed + 7)
    W1 = rng.normal(0, 1 / np.sqrt(2 * P), (2 * P, D)); W2 = rng.normal(0, 1 / np.sqrt(D), (D, P)); n = len(Xtr)
    ck = {}; acc = []; t_grok = None
    for t in range(steps):
        H = Xtr @ W1; A = H * H; Out = A @ W2; G = (Out - Ytr) / n
        gW2 = A.T @ G; gA = G @ W2.T; gH = 2 * H * gA; gW1 = Xtr.T @ gH
        if t % every == 0:
            Ote = ((Xte @ W1) ** 2) @ W2; acc_te = float((Ote.argmax(1) == Yte.argmax(1)).mean()); acc_tr = float((Out.argmax(1) == Ytr.argmax(1)).mean())
            ltr = float(0.5 * ((Out - Ytr) ** 2).sum(1).mean())
            ck[t] = dict(W1=W1.copy(), W2=W2.copy(), acc_te=acc_te, acc_tr=acc_tr, loss=ltr); acc.append((t, acc_te, acc_tr, ltr))
            if t_grok is None and acc_te >= 0.5: t_grok = t
        W1 -= LR * (gW1 + WD * W1); W2 -= LR * (gW2 + WD * W2)
    return dict(ck=ck, acc=np.array(acc), t_grok=t_grok, Xtr=Xtr, Ytr=Ytr)

class QNet(torch.nn.Module):
    def __init__(self, W1, W2):
        super().__init__(); self.W1 = torch.nn.Parameter(torch.tensor(W1, dtype=torch.float32)); self.W2 = torch.nn.Parameter(torch.tensor(W2, dtype=torch.float32))
    def forward(self, X): return ((X @ self.W1) ** 2) @ self.W2

def evaluate(model, data):
    X, Y = data; out = model(X); loss = 0.5 * ((out - Y) ** 2).sum(1).mean(); return loss, {'loss': loss}

def llc(W1, W2, Xtr, Ytr, eps=1e-4, gamma=100.0, nbeta=None, draws=200, chains=2, burn=0, batch=256, seed=0):
    n = len(Xtr); nbeta = nbeta or n / np.log(n)
    X = torch.tensor(Xtr, dtype=torch.float32); Y = torch.tensor(Ytr, dtype=torch.float32)
    ds = torch.utils.data.TensorDataset(X, Y); loader = torch.utils.data.DataLoader(ds, batch_size=batch, shuffle=True)
    model = QNet(W1, W2); torch.manual_seed(seed)
    with torch.no_grad(): init_loss = float(evaluate(model, (X, Y))[0])
    r = estimate_learning_coeff_with_summary(model, loader, evaluate=evaluate, sampling_method=SGLD,
        optimizer_kwargs=dict(lr=eps, localization=gamma, nbeta=nbeta), num_draws=draws, num_chains=chains, num_burnin_steps=burn,
        num_steps_bw_draws=1, init_loss=init_loss, seed=seed, verbose=False, online=False)
    return dict(llc=float(r['llc/mean']), std=float(r['llc/std']), init_loss=init_loss, loss_trace_max=float(np.max(r['loss/trace'])) if 'loss/trace' in r else None)
