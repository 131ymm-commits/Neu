"""Exact calibrations for DET-004 (delayed logistic, NS) and DET-005 (cascade rungs)."""
import numpy as np
from math import erf

def gauss_bins(fx, edges, sigma):
    z = (edges - fx) / (sigma * np.sqrt(2))
    cdf = 0.5 * (1 + np.vectorize(erf)(z))
    w = np.diff(cdf); w[0] += cdf[0]; w[-1] += 1 - cdf[-1]
    return w / w.sum()

def exact_delayed(r, sigma, nb=28):
    edges = np.linspace(0, 1, nb + 1)
    cent = 0.5 * (edges[:-1] + edges[1:])
    P = np.zeros((nb * nb, nb * nb))
    for i in range(nb):          # x_t bin
        for j in range(nb):      # x_{t-1} bin
            fx = r * cent[i] * (1 - cent[j])
            w = gauss_bins(np.clip(fx, -0.5, 1.5), edges, sigma)
            P[i * nb + j, np.arange(nb) * nb + i] = w   # new state (i', j'=i)
    ev = np.linalg.eigvals(P)
    return ev[np.argsort(-np.abs(ev))]

def exact_1d(r, sigma, nb=200):
    edges = np.linspace(0, 1, nb + 1)
    cent = 0.5 * (edges[:-1] + edges[1:])
    P = np.zeros((nb, nb))
    for i in range(nb):
        P[i] = gauss_bins(r * cent[i] * (1 - cent[i]), edges, sigma)
    ev = np.linalg.eigvals(P)
    return ev[np.argsort(-np.abs(ev))]

def show(ev, k=6):
    return " ".join(f"|{np.abs(ev[i]):.4f}|∠{np.angle(ev[i])/np.pi:+.2f}π" for i in range(1, k))

print("=== DET-004: delayed logistic, sigma=0.01 / 0.02 ===")
for sigma in (0.01, 0.02):
    print(f"-- sigma={sigma}")
    for r in (1.40, 1.60, 1.80, 1.95, 2.00, 2.05, 2.10, 2.16, 2.22):
        ev = exact_delayed(r, sigma)
        l2, l3, l4 = ev[1], ev[2], ev[3]
        pair = abs(np.abs(l3) / np.abs(l2) - 1) < 0.05 and abs(np.angle(l2) + np.angle(l3)) < 0.2
        t2 = -1 / np.log(np.abs(l2))
        tn = -1 / np.log(np.abs(l4 if pair else l3))
        print(f" r={r:.2f} {show(ev,5)} pair={int(pair)} Rgrp={t2/tn:7.2f}")

print("\n=== DET-005: cascade rungs, 1D logistic ===")
for sigma, rs in ((0.005, (3.20, 3.30, 3.40, 3.44, 3.46, 3.48, 3.52, 3.55)),
                  (0.001, (3.50, 3.54, 3.552, 3.558, 3.565))):
    print(f"-- sigma={sigma}")
    for r in rs:
        ev = exact_1d(r, sigma, nb=400 if sigma < 0.003 else 200)
        print(f" r={r:.3f} {show(ev,7)}")
