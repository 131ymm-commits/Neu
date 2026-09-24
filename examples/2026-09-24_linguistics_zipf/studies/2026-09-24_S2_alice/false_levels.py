import itertools, numpy as np
print("Ложные уровни Спирмена при случайном порядке (точно для n<=9, Монте-Карло 400000 для n>9)")
for n in range(6,13):
    x=np.arange(n); rng=np.random.default_rng(1)
    P=np.array(list(itertools.permutations(range(n)))) if n<=9 else np.array([rng.permutation(n) for _ in range(400000)])
    rho=1-6*((P-x)**2).sum(1)/(n*(n*n-1))
    print(f"n={n}: P(rho>=0.6)={(rho>=0.6-1e-12).mean():.4f}  P(rho<=-0.6)={(rho<=-0.6+1e-12).mean():.4f}  P(rho<0.3)={(rho<0.3-1e-12).mean():.3f}  P5: 2/n*1/(n-1)={2/n/(n-1):.4f}")
