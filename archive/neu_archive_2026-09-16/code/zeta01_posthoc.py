"""ZETA-01 — ПОСТ-ХОК диагностика (НЕ предрегистрировано; вердикт K1 уже записан). Цель — только классифицировать провал P-Z1:
A (δ18O в одиночку не двухъямен — как дрейф у Riechers 2023) или C (режим: голоцен/дегляциация внутри окна 0–60 ka, разрешение).
Окна: 12–60 ka (ледниковый период без голоцена), 27–59 ka (окно Riechers и др. 2023), 27–59 ka с шагом вложения 5 (100-летние лаги),
12–60 ka с линейным детрендом. Тот же тест, те же k = 30, τ = 1."""
import numpy as np, json, sys, warnings
warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/claude')
import xlrd
from zeta01_lib import embed, zeta
wb = xlrd.open_workbook('/home/claude/neu_archive/user_bundles/GICC05_NGRIP_60ka_20y_10sep2007_1.xls'); sh = wb.sheet_by_index(0); ages, d18 = [], []
for r in range(61, sh.nrows):
    a, d = sh.cell_value(r, 0), sh.cell_value(r, 2)
    if isinstance(a, float) and isinstance(d, float): ages.append(a); d18.append(d)
ages = np.array(ages); d18 = np.array(d18); o = np.argsort(ages); ages, d18 = ages[o], d18[o]
out = {}
def go(name, x, m, step):
    F = embed(x, m, step) if m > 1 else x.reshape(-1, 1)
    out[name] = zeta(F, 1, 30, name=name); json.dump(out, open('/home/claude/zeta01_posthoc.json', 'w'), indent=1, default=float)
w1 = (ages >= 12000) & (ages <= 60000); w2 = (ages >= 27000) & (ages <= 59000)
go('NGRIP_12-60ka_m4', d18[w1], 4, 1); go('NGRIP_12-60ka_m1', d18[w1], 1, 1)
go('NGRIP_27-59ka_m4', d18[w2], 4, 1); go('NGRIP_27-59ka_m1', d18[w2], 1, 1)
go('NGRIP_27-59ka_m4_step5', d18[w2], 4, 5)
xd = d18[w1] - np.polyval(np.polyfit(ages[w1], d18[w1], 1), ages[w1]); go('NGRIP_12-60ka_detr_m4', xd, 4, 1)
# суррогат-нуль по построению: та же спектральная плотность, фазы случайные (IAAFT-подобный простой FFT-суррогат) — должен дать «нет»
rng = np.random.default_rng(0); X = np.fft.rfft(d18[w2]); ph = np.exp(1j * rng.uniform(0, 2 * np.pi, len(X))); ph[0] = 1
xs = np.fft.irfft(np.abs(X) * ph, n=len(d18[w2])); go('NGRIP_27-59ka_phase_surrogate_m4', xs, 4, 1)
print('готово')
