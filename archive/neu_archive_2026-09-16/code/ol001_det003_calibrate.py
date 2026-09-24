"""Calibration for OL-001 (data structures) and DET-003 (exact kernel operator).
Pre-prereg: no empirical detector on trajectories; exact operator + data inventory only."""
import json, gzip, re, numpy as np
import xml.etree.ElementTree as ET

HUB = "/home/claude/hub/hub_theory_bundle/"

# ---------- OL-001: currency lists ----------
r6 = json.load(open(HUB + "results_hub_006.json"))
r7 = json.load(open(HUB + "results_hub_007.json"))
r8 = json.load(open(HUB + "results_hub_008.json"))
cur = {
    "iIT341": r6["iIT341_Hpylori"]["R5"]["removed"],
    "iAF692": r6["iAF692_Mbarkeri"]["R5"]["removed"],
    "iND750": r7["detector"]["removed"],
    "iNJ661": r8["detector"]["removed"],
}
for k, v in cur.items():
    print(k, len(v), v)

def parse_sbml(path):
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rb") as f:
        tree = ET.parse(f)
    root = tree.getroot()
    ns = {"s": root.tag.split("}")[0].strip("{")}
    species = {}
    for sp in root.iter():
        if sp.tag.endswith("species"):
            sid = sp.get("id", "")
            if sid.startswith("M_"):
                species[sid[2:]] = sp.get("name", "")
    deg = {s: 0 for s in species}
    for rx in root.iter():
        if rx.tag.endswith("reaction"):
            seen = set()
            for sr in rx.iter():
                if sr.tag.endswith("speciesReference"):
                    sid = sr.get("species", "")
                    if sid.startswith("M_"):
                        seen.add(sid[2:])
            for s in seen:
                if s in deg: deg[s] += 1
    return species, deg

MODELS = {"iIT341": HUB + "iIT341.xml", "iAF692": HUB + "iAF692.xml",
          "iND750": HUB + "iND750.xml", "iNJ661": HUB + "iNJ661.xml"}
for org, path in MODELS.items():
    sp, deg = parse_sbml(path)
    missing = [c for c in cur[org] if c not in sp]
    print(f"{org}: species={len(sp)} deg_nonzero={sum(1 for v in deg.values() if v>0)} "
          f"missing_currencies={missing}")
    ex = list(sp.items())[:3]
    print("   sample:", ex)

# ---------- DET-003: exact kernel operator of noisy logistic ----------
def exact_op(r, sigma, nb=200):
    edges = np.linspace(0, 1, nb + 1)
    cent = 0.5 * (edges[:-1] + edges[1:])
    fx = r * cent * (1 - cent)
    from math import erf
    P = np.zeros((nb, nb))
    s2 = sigma * np.sqrt(2)
    for i in range(nb):
        z = (edges - fx[i]) / s2
        cdf = 0.5 * (1 + np.vectorize(erf)(z))
        w = np.diff(cdf)
        # clipping mass to boundary bins
        w[0] += cdf[0]
        w[-1] += 1 - cdf[-1]
        P[i] = w / w.sum()
    ev = np.linalg.eigvals(P)
    idx = np.argsort(-np.abs(ev))
    lam = ev[idx]
    return lam

print("\nDET-003 exact: lam2 (|.|, angle/pi), lam3 |.| ; t2/t3 via |lam|")
for sigma in (0.005, 0.01, 0.02):
    print(f"-- sigma={sigma}")
    for r in (2.60, 2.75, 2.90, 3.00, 3.05, 3.10, 3.20, 3.30, 3.40):
        lam = exact_op(r, sigma)
        l2, l3 = lam[1], lam[2]
        t2 = -1 / np.log(np.abs(l2)); t3 = -1 / np.log(np.abs(l3))
        print(f" r={r:.2f} |l2|={np.abs(l2):.4f} th2/pi={np.angle(l2)/np.pi:+.3f} "
              f"|l3|={np.abs(l3):.4f} th3/pi={np.angle(l3)/np.pi:+.3f} Rc={t2/t3:6.2f}")
