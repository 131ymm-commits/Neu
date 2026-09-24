"""GROK-008 calibration (spent seed 101): 1-layer transformer on modular addition, full-batch GD (+wd) in torch (CPU).
Goal: does it grok within budget at some lr/wd; step time. NOT a test run."""
import time, sys, math
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(1); torch.manual_seed(101)
P = 53; FRAC = 0.5; D = 128; H = 4; DFF = 512
rng = np.random.default_rng(101)
pairs = np.array([(a, b) for a in range(P) for b in range(P)]); rng.shuffle(pairs)
ntr = int(FRAC * len(pairs)); tr, te = pairs[:ntr], pairs[ntr:]
def enc(ps): return torch.tensor(np.stack([ps[:, 0], ps[:, 1], np.full(len(ps), P)], 1)), torch.tensor((ps[:, 0] + ps[:, 1]) % P)
Xtr, Ytr = enc(tr); Xte, Yte = enc(te)
class T1(nn.Module):
    def __init__(s):
        super().__init__(); s.emb = nn.Embedding(P + 1, D); s.pos = nn.Parameter(torch.randn(3, D) * 0.02)
        s.q = nn.Linear(D, D, bias=False); s.k = nn.Linear(D, D, bias=False); s.v = nn.Linear(D, D, bias=False); s.o = nn.Linear(D, D, bias=False)
        s.f1 = nn.Linear(D, DFF); s.f2 = nn.Linear(DFF, D); s.unemb = nn.Linear(D, P, bias=False)
    def forward(s, x):
        h = s.emb(x) + s.pos
        B, L, _ = h.shape
        q = s.q(h).view(B, L, H, D // H).transpose(1, 2); k = s.k(h).view(B, L, H, D // H).transpose(1, 2); v = s.v(h).view(B, L, H, D // H).transpose(1, 2)
        att = (q @ k.transpose(-1, -2)) / math.sqrt(D // H)
        mask = torch.triu(torch.ones(L, L), 1).bool(); att = att.masked_fill(mask, -1e9).softmax(-1)
        h = h + s.o((att @ v).transpose(1, 2).reshape(B, L, D))
        h = h + s.f2(F.relu(s.f1(h)))
        return s.unemb(h[:, -1])
lr, wd, steps = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
opt_name = sys.argv[4] if len(sys.argv) > 4 else "gd"
m = T1(); t0 = time.time()
opt = torch.optim.SGD(m.parameters(), lr=lr, weight_decay=wd) if opt_name == "gd" else torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=wd, betas=(0.9, 0.98))
tg = None
for t in range(steps):
    opt.zero_grad(); loss = F.cross_entropy(m(Xtr), Ytr); loss.backward(); opt.step()
    if t % 50 == 0:
        with torch.no_grad():
            acc_tr = (m(Xtr).argmax(1) == Ytr).float().mean().item(); acc_te = (m(Xte).argmax(1) == Yte).float().mean().item()
        if tg is None and acc_te >= 0.5: tg = t
        if t % 500 == 0: print(f"t={t} loss={loss.item():.4f} tr={acc_tr:.3f} te={acc_te:.3f} [{time.time()-t0:.0f}s]", flush=True)
print(f"done: t_grok={tg} final te={acc_te:.3f} time/step={(time.time()-t0)/steps*1000:.1f} ms")
