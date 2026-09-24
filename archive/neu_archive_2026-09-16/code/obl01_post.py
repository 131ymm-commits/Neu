"""OBL-01 пост-хок (не в зачёт): время жизни n* рождённого уровня среднего разреза лифтированного пути при p* с NMAX = 4000; и AUC по ЗНАКУ d₂ (бинарный предиктор)."""
import numpy as np, json, sys; sys.path.insert(0, '/home/claude')
src = open('/home/claude/obl01_run.py').read(); exec(src.split("res = {}")[0])
out = {}
for L, p in ((64, 0.05), (128, 0.02), (256, 0.01)):
    P = lifted_path(L, p) if 'lifted_path' in dir() else None
