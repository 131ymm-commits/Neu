"""SORT-03 — iAAFT-суррогаты (Schreiber–Schmitz): тот же спектр мощности и то же распределение амплитуд; обратимый процесс."""
import numpy as np
def iaaft(x, rng, n_iter=100):
    x = np.asarray(x, float); n = len(x); xs = np.sort(x); amp = np.abs(np.fft.rfft(x))
    y = rng.permutation(x)
    for _ in range(n_iter):
        Y = np.fft.rfft(y); Y = amp * np.exp(1j * np.angle(Y)); y = np.fft.irfft(Y, n)
        ranks = np.argsort(np.argsort(y)); y = xs[ranks]
    return y
