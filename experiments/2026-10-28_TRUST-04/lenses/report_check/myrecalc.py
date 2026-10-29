#!/usr/bin/env python3
"""Независимый пересчёт вердиктов TRUST-04 (проверяльщик отчёта, 29.10.2026).
Не импортирует код опыта. Пороги — переписаны из PREREG-TRUST-04.md §4/§6, FROZEN — из таблицы §2.
Выход: myrecalc.json рядом со скриптом + печать сверки с analysis_trust_04.json."""
import json, math, os
import numpy as np
from scipy import stats

D = '/home/claude/neu/experiments/2026-10-28_TRUST-04'
OUT = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(f'{D}/results_trust_04_A.json'))
B = json.load(open(f'{D}/results_trust_04_B.json'))
I = json.load(open(f'{D}/indep/test700/results_indep_04.json'))
AN = json.load(open(f'{D}/analysis_trust_04.json'))

# §2 PREREG: (близорукая, дальновидная)
FZ = {'base': (0.9873, 0.6891), 'r075': (0.5768, 0.3897), 'r095': (1.7134, 1.1968), 'b03': (1.2221, 0.9622), 'b09': (0.8328, 0.5372)}
# проверка FROZEN против теории в результатах
for w, (my, far) in FZ.items():
    th = A['theory'][w]
    assert abs(th['myopic']['wG'] - my) < 1e-4 and abs(th['farsighted']['wG'] - far) < 1e-4, w
    assert A['theory'][w] == B['theory'][w]
ARMS = {}
ARMS.update(A['params']['ARMS'])
assert A['params']['ARMS'] == B['params']['ARMS']
seeds = list(range(600, 620))
assert A['params']['SEEDS'] == seeds == B['params']['SEEDS']
F = {}
cnt = {}
for d in (A, B):
    for r in d['runs']:
        key = (r['seed'], r['arm'])
        assert key not in F
        F[key] = r['final']
        cnt[r['arm']] = cnt.get(r['arm'], 0) + 1
assert len(F) == 620 and all(v == 20 for v in cnt.values()) and len(cnt) == 31


def u(arm):
    my, far = FZ[ARMS[arm]['world']]
    return np.array([(F[(s, arm)]['wG'] - far) / (my - far) for s in seeds])


def col(arm, k='wG'):
    return np.array([F[(s, arm)][k] for s in seeds])


def oc_count(c, k, n):
    return 'подтверждено' if c >= k else ('опровергнуто' if c <= n - k else 'не показано')


def welch(x, y, level=0.95):
    x, y = np.asarray(x, float), np.asarray(y, float)
    r = stats.ttest_ind(x, y, equal_var=False)
    ci = r.confidence_interval(level)
    return float(x.mean() - y.mean()), float(ci.low), float(ci.high)


def oc_eq(lo, hi, dl=0.1):
    if -dl < lo and hi < dl:
        return 'подтверждено'
    if lo >= dl or hi <= -dl:
        return 'опровергнуто'
    return 'не показано'


def boot(x, B_=10000, seed=0):
    """тот же бутстреп, что в analyze (для сверки последних знаков)"""
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    m = x[g.integers(0, len(x), (B_, len(x)))].mean(1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def boot_alt(x, B_=200000, seed=12345):
    """свой бутстреп (другое зерно, больше повторов) — устойчивость 4-го знака"""
    x = np.asarray(x, float); g = np.random.default_rng(seed)
    idx = g.integers(0, len(x), (B_, len(x)))
    m = x[idx].mean(1)
    return [float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


V = {}


def interval(name, x, lo, hi, k, strict):
    c = int(np.sum((x > lo) & (x < hi))) if strict else int(np.sum((x >= lo) & (x <= hi)))
    V[name] = dict(kind='интервал', n=c, N=len(x), k=k, outcome=oc_count(c, k, len(x)), value=boot(x), value_alt=boot_alt(x),
                   min=float(x.min()), max=float(x.max()))


def sign(name, a, b, k):
    d = col(a) - col(b)
    c = int(np.sum(d < 0))
    V[name] = dict(kind='знак', n=c, N=20, k=k, outcome=oc_count(c, k, 20), diff=boot(d), diff_alt=boot_alt(d), maxdiff=float(d.max()))


def equiv(name, x, y, store=None):
    m, lo, hi = welch(x, y)
    (store if store is not None else V)[name] = dict(kind='экв', diff_ci=[m, lo, hi], outcome=oc_eq(lo, hi))


# блок А
interval('A1', u('POOLED'), -1/6, 1/6, 18, False)
interval('A2', u('POOLED_FREE'), -1/6, 1/6, 17, False)
interval('A3', u('DEMES'), 1/6, 5/6, 18, True)
interval('A4', u('DEMES_FREE'), 1/6, 5/6, 18, True)
sign('A5', 'POOLED', 'DEMES', 18)
sign('A6', 'POOLED_FREE', 'DEMES_FREE', 18)
equiv('A7', u('POOLED'), u('POOLED_FREE'))
equiv('A8', u('DEMES'), u('DEMES_FREE'))
interval('A9', u('DEMES_NOSEL'), 2/3, 4/3, 18, False)
interval('A10', u('DEMES_NOSEL_FREE'), 2/3, 4/3, 18, False)
interval('A11', u('COUNCIL_SIGN'), -1/3, 1/3, 18, False)
equiv('A12', u('COUNCIL'), u('COUNCIL_SIGN'))
interval('A13', u('COUNCIL'), -1/6, 1/6, 18, False)
interval('A14', u('MYOPIC'), 2/3, 4/3, 18, False)
# A15: срыв — SD между группами > 0,5 или V_внутри > 0,1 (§2)
brk = np.array([(F[(s, 'DEMES_NOWITHIN')]['wG_sd_groups'] > 0.5) or (F[(s, 'DEMES_NOWITHIN')]['V_within'] > 0.1) for s in seeds])
un = u('DEMES_NOWITHIN')[~brk]
nnb = len(un); k15 = math.ceil(0.8 * nnb); c15 = int(np.sum(np.abs(un) <= 1/6))
oc15 = 'не показано' if nnb < 13 else ('подтверждено' if c15 >= k15 else ('опровергнуто' if c15 <= nnb - k15 else 'не показано'))
V['A15'] = dict(kind='A15', n=c15, N=nnb, k=k15, breakdowns=int(brk.sum()), outcome=oc15, value=boot(u('DEMES_NOWITHIN')),
                value_nb=boot(un), max_abs=float(np.abs(un).max()),
                sd_groups_max=float(col('DEMES_NOWITHIN', 'wG_sd_groups').max()), Vw_max=float(col('DEMES_NOWITHIN', 'V_within').max()))
interval('A16', u('DEMES_GPOOL'), 1/6, 5/6, 18, True)
equiv('A17', u('DEMES_GPOOL'), u('DEMES_FREE'))
sign('A18', 'POOLED_FREE', 'DEMES_GPOOL', 18)
# блок Б
for i, c in enumerate(('r075', 'r095', 'b03', 'b09', 'IND', 'MIG', 'SIG5')):
    sign(f'B{i+1}', f'POOLED_{c}', f'DEMES_{c}', 18)
for i, w in enumerate(('r075', 'r095', 'b03', 'b09')):
    interval(f'B{i+8}', u(f'POOLED_{w}'), -1/3, 1/3, 18, False)
    interval(f'B{i+12}', u(f'MYOPIC_{w}'), 2/3, 4/3, 18, False)
# блок В
iseeds = I['meta']['seeds']
assert iseeds == list(range(700, 720)), iseeds
IR = {(r['seed'], r['arm']): r for r in I['runs']}
assert len(IR) == 80
my0, far0 = FZ['base']
ui = lambda a: np.array([(IR[(s, a)]['w_G'] - far0) / (my0 - far0) for s in iseeds])
for a in ('MYOPIC', 'DEMES', 'POOLED', 'COUNCIL'):
    equiv(f'C_{a}', ui(a), u(a))
    V[f'C_{a}']['u_indep'] = boot(ui(a)); V[f'C_{a}']['u_main'] = boot(u(a))
dd = ui('POOLED') - ui('DEMES')
cO = int(np.sum(dd < 0))
V['C_ORDER'] = dict(kind='знак', n=cO, N=20, k=18, outcome=oc_count(cO, 18, 20), diff=boot(dd))
# разведка
X = {}
a_, b_ = u('POOLED_IND'), u('POOLED')
lev = stats.levene(a_, b_, center='median')
sdI, sdB = float(a_.std(ddof=1)), float(b_.std(ddof=1))
p1 = lev.pvalue / 2 if sdI > sdB else 1 - lev.pvalue / 2
X['EB1'] = dict(sd_IND=sdI, sd_base=sdB, p_one=float(p1), outcome='подтверждено' if (sdI > sdB and p1 < 0.05) else 'не показано')
# второй способ Брауна–Форсайта: ANOVA по |x - median|
za, zb = np.abs(a_ - np.median(a_)), np.abs(b_ - np.median(b_))
X['EB1']['p_two_anova_dev'] = float(stats.f_oneway(za, zb).pvalue)
equiv('EB2', u('POOLED_MIG'), u('POOLED'), X)
for nm, (a, b) in {'EB3': ('DEMES', 'DEMES_MIG'), 'EB4': ('DEMES', 'DEMES_SIG5')}.items():
    d = col(a) - col(b); c = int(np.sum(d < 0))
    X[nm] = dict(n=c, k=15, outcome=oc_count(c, 15, 20), diff=boot(d))
for w in ('r075', 'r095', 'b03', 'b09'):
    equiv(f'EB5_{w}', u(f'DEMES_{w}'), u('DEMES'), X)
E1 = ['DEMES', 'DEMES_FREE', 'DEMES_GPOOL', 'DEMES_IND', 'DEMES_MIG', 'DEMES_SIG5', 'DEMES_r075', 'DEMES_r095', 'DEMES_b03', 'DEMES_b09']
ub = np.array([u(a).mean() for a in E1])
Rb = np.array([col(a, 'V_between').mean() / (col(a, 'V_between').mean() + col(a, 'V_within').mean()) for a in E1])
gap = np.abs(ub - (1 - Rb))
rho = stats.spearmanr(ub, 1 - Rb)
g = dict(zip(E1, gap))
X['EB6'] = dict(u=dict(zip(E1, ub.round(6).tolist())), one_minus_R=dict(zip(E1, (1 - Rb).round(6).tolist())), gap=dict(zip(E1, gap.round(6).tolist())),
                n01=int(np.sum(gap <= 0.1)), rho=float(rho.statistic), rho_p=float(rho.pvalue),
                outcome='подтверждено' if (g['DEMES_MIG'] <= 0.1 and g['DEMES_SIG5'] <= 0.1) else 'не показано')
# R по зёрнам (среднее R зерна) — для сравнения с R̄ по средним дисперсиям
X['EB6']['R_seedmean'] = {a: float(np.mean(col(a, 'V_between') / (col(a, 'V_between') + col(a, 'V_within')))) for a in E1}
# сводные
COMP = dict(SA=['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8'], SA2=['A11', 'A12'], SA3=['A2', 'A4', 'A15', 'A16', 'A17', 'A18'],
            SB=[f'B{i}' for i in range(1, 8)], SB2=[f'B{i}' for i in range(8, 12)], SC=['C_MYOPIC', 'C_DEMES', 'C_POOLED', 'C_COUNCIL', 'C_ORDER'])
S = {}
for c, ps in COMP.items():
    oc = [V[p]['outcome'] for p in ps]
    S[c] = 'подтверждено' if all(o == 'подтверждено' for o in oc) else ('опровергнуто' if 'опровергнуто' in oc else 'не подтверждено')
# чтения
okv = lambda p: V[p]['outcome'] == 'подтверждено'
read = {c: S[c] for c in COMP}
if not okv('A14'):
    for c in ('SA', 'SA2', 'SA3', 'SC'):
        read[c] = 'не установлено'
if not (okv('A9') and okv('A10')):
    for c in ('SA', 'SA3'):
        read[c] = 'не установлено'
if not all(okv(f'B{12+i}') for i in range(4)):
    read['SB2'] = 'не установлено'
# реестр по PREREG §4
REGP = {'C-048': ['A13', 'A12', 'C_COUNCIL', 'A14'],
        'C-049': ['A3', 'A8', 'A9', 'A10', 'C_DEMES', 'A14'],
        'C-050': ['A1', 'A5', 'C_POOLED', 'A2', 'A4', 'A15', 'A16', 'A17', 'A18', 'A9', 'A10', 'A14']}
# §6: ложный уровень частей (таблица) и мощность (таблица реестра)
FL = dict(A1=0.0002, A2=0.0013, A3=0.0002, A4=0.0002, A5=0.0002, A6=0.0002, A7=0.0253, A8=0.0238, A9=0.0002, A10=0.0002, A11=0.0002,
          A12=0.0274, A13=0.0002, A14=0.0002, A15=0.0176, A16=0.0002, A17=0.0248, A18=0.0002, C_COUNCIL=0.0227, C_DEMES=0.0228,
          C_MYOPIC=0.0256, C_ORDER=0.0002, C_POOLED=0.0237, **{f'B{i}': 0.0002 for i in range(1, 16)})
PW = {'C-048': 0.9958, 'C-049': 0.9985, 'C-050': 0.9994}
REG = {}
for cid, ps in REGP.items():
    oc = [V[p]['outcome'] for p in ps]
    res = 'держится' if all(o == 'подтверждено' for o in oc) else ('опровергнуто' if 'опровергнуто' in oc else 'не показано')
    fl = max(max(FL[p] for p in ps), 0.001)
    REG[cid] = dict(outcome=res, fl=max(FL[p] for p in ps), bits=math.log2(PW[cid] / fl))
fam38 = sum(FL.values())
out = dict(V=V, X=X, S=S, read=read, REG=REG, fam38=fam38, n_parts=len(FL))
json.dump(out, open(f'{OUT}/myrecalc.json', 'w'), ensure_ascii=False, indent=1)

# ---- сверка с analysis_trust_04.json ----
mism = []
for nm, v in V.items():
    a = AN['verdicts'][nm]
    if a['outcome'] != v['outcome']:
        mism.append((nm, 'outcome', a['outcome'], v['outcome']))
    if 'n' in v and a.get('n') != v['n']:
        mism.append((nm, 'n', a.get('n'), v['n']))
    if 'k' in v and a.get('k') != v['k']:
        mism.append((nm, 'k', a.get('k'), v['k']))
    for key_me, key_an in (('value', 'value'), ('diff', 'diff'), ('diff_ci', 'diff_ci')):
        if key_me in v:
            if not np.allclose(v[key_me], a[key_an], atol=1e-12):
                mism.append((nm, key_me, a[key_an], v[key_me]))
    if nm == 'A15':
        if not np.allclose(v['value_nb'], a['value_no_breakdown'], atol=1e-12):
            mism.append((nm, 'value_nb', a['value_no_breakdown'], v['value_nb']))
        if a['breakdowns'] != v['breakdowns']:
            mism.append((nm, 'breakdowns', a['breakdowns'], v['breakdowns']))
for nm, v in X.items():
    a = AN['explore'][nm]
    if a['outcome'] != v['outcome']:
        mism.append((nm, 'outcome', a['outcome'], v['outcome']))
    if 'diff_ci' in v and not np.allclose(v['diff_ci'], a['diff_ci'], atol=1e-12):
        mism.append((nm, 'diff_ci', a['diff_ci'], v['diff_ci']))
    if 'diff' in v and not np.allclose(v['diff'], a['diff'], atol=1e-12):
        mism.append((nm, 'diff', a['diff'], v['diff']))
for c in COMP:
    if AN['summary'][c]['outcome'] != S[c]:
        mism.append((c, 'summary', AN['summary'][c]['outcome'], S[c]))
    if AN['readings'][c]['reading'] != read[c]:
        mism.append((c, 'reading', AN['readings'][c]['reading'], read[c]))
for cid, r in REG.items():
    a = AN['registry'][cid]
    if a['outcome'] != r['outcome'] or abs(a['bits'] - r['bits']) > 0.01 or sorted(a['parts']) != sorted(REGP[cid]):
        mism.append((cid, 'registry', (a['outcome'], a['bits'], a['parts']), (r['outcome'], r['bits'], REGP[cid])))
print('расхождений с analysis_trust_04.json:', len(mism))
for m in mism:
    print('  ', m)
print('сводные:', S)
print('чтения:', read)
print('реестр:', {k: (v['outcome'], round(v['bits'], 3), v['fl']) for k, v in REG.items()})
print('Бонферрони 38 частей:', round(fam38, 4), 'частей', len(FL))
print('A15:', {k: v for k, v in V['A15'].items() if k not in ('value', 'value_nb')}, 'nb mean/CI', np.round(V['A15']['value_nb'], 4))
print('EB1:', X['EB1'])
print('EB6:', {k: X['EB6'][k] for k in ('n01', 'rho', 'rho_p', 'outcome')}, 'gap MIG/SIG5', X['EB6']['gap']['DEMES_MIG'], X['EB6']['gap']['DEMES_SIG5'])
# минимальный запас интервальных/знаковых
for nm, v in V.items():
    if v['kind'] == 'интервал':
        print(f"  {nm}: {v['n']}/{v['N']} (k={v['k']}) мин {v['min']:.4f} макс {v['max']:.4f}")
    elif v['kind'] == 'знак' and 'maxdiff' in v:
        print(f"  {nm}: {v['n']}/20 наибольшая разность {v['maxdiff']:.4f}")
    elif v['kind'] == 'экв':
        print(f"  {nm}: {np.round(v['diff_ci'], 4)} {v['outcome']}")
