"""VER-001c — fresh-seed replication of PRE-006c route tree. Per PREREG (frozen 2026-08-31).
Frozen thresholds pre006c_thresholds.json; fresh seeds test 970000+OFF+i, ctrl 975000+OFF+i."""
import json, os, time
import numpy as np

exec(open("/home/claude/pre006c_run.py").read().split("t0 = time.time()")[0])   # SYS, gen, features, OFF, ...
th = json.load(open("/home/claude/pre006c_thresholds.json"))

def classify_v(f):
    if f["R2"] >= th["thR2"]: return "hopf"
    if f["rise"] < th["thRise"]: return "none"
    if f["S"] is not None and f["S"] >= th["thS"]: return "fold"
    return "trans"

CK = "/home/claude/ver001c_ckpt.json"
ck = json.load(open(CK)) if os.path.exists(CK) else {"percase": [], "ctl": []}
done = {(c["truth"], c["i"]) for c in ck["percase"]}
t0 = time.time()
for name in SYS:
    for i in (1, 2, 3, 4, 5):
        if (name, i) in done: continue
        f = features(gen(name, True, 970000 + OFF[name] + i))
        lab = classify_v(f)
        ck["percase"].append(dict(truth=name, i=i, label=lab, **f))
        json.dump(ck, open(CK, "w"), default=float)
        print(f"тест {name}#{i}: R2={f['R2']:.2f} rise={f['rise']:.2f} S={f['S'] if f['S'] is None else round(f['S'],2)} -> {lab} [{time.time()-t0:.0f}s]", flush=True)
done_c = {(c["truth"], c["i"]) for c in ck["ctl"]}
for name in SYS:
    for i in (1, 2, 3):
        if (name, i) in done_c: continue
        f = features(gen(name, False, 975000 + OFF[name] + i))
        lab = classify_v(f)
        ck["ctl"].append(dict(truth=name, i=i, label=lab, **f))
        json.dump(ck, open(CK, "w"), default=float)
        print(f"контроль {name}#{i}: -> {lab} [{time.time()-t0:.0f}s]", flush=True)

correct = sum(1 for c in ck["percase"] if c["label"] == c["truth"])
fh = sum(1 for c in ck["percase"] if (c["truth"], c["label"]) in (("fold", "hopf"), ("hopf", "fold")))
ctl_none = sum(1 for c in ck["ctl"] if c["label"] == "none")
pv1c1 = correct >= 12 and fh == 0
pv1c1_kill = correct <= 10 or fh >= 2
pv1c2 = ctl_none >= 7
pv1c2_kill = ctl_none <= 5
loo_ok = True
for k in range(len(ck["percase"])):
    sub = [c for j, c in enumerate(ck["percase"]) if j != k]
    if sum(1 for c in sub if c["label"] == c["truth"]) < 11: loo_ok = False
ck["verdicts"] = dict(correct=correct, fh_swap=fh, ctl_none=ctl_none,
                      PV1c1=bool(pv1c1), PV1c1_killed=bool(pv1c1_kill),
                      PV1c2=bool(pv1c2), PV1c2_killed=bool(pv1c2_kill), loo_ok=bool(loo_ok))
json.dump(ck, open(CK, "w"), default=float)
conf = {}
for c in ck["percase"]:
    conf.setdefault(c["truth"], {}).setdefault(c["label"], 0)
    conf[c["truth"]][c["label"]] += 1
print(f"\nматрица: {conf}")
print(f"P-V1c1: верных {correct}/15 (исходно 13/15), фолд<->Хопф {fh} -> "
      f"{'РЕПЛИЦИРОВАН' if pv1c1 else ('ПРОВАЛ' if pv1c1_kill else 'не установлен')} (LOO={loo_ok})")
print(f"P-V1c2: контроли none {ctl_none}/9 -> {'✓' if pv1c2 else ('ПРОВАЛ' if pv1c2_kill else 'не уст.')}")
print(f"[{time.time()-t0:.0f}s]")
