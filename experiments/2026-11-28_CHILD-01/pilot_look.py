"""CHILD-01: взгляд на пилот (сиды 990–992). Только пилотный каталог; тестовые прогоны не читает."""
import glob, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); P = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else 'pilot')
R = {}
for f in sorted(glob.glob(os.path.join(P, '*.json'))):
    j = json.load(open(f)); R[(j['task'], j['arm'], j['seed'])] = j
tasks = sorted({k[0] for k in R}); arms = []
for k in R:
    if k[1] not in arms: arms.append(k[1])
order = ['FIX', 'ALT_12', 'ALT_25', 'ALT_50', 'ALT_75', 'RND', 'NOISE_25', 'NOISE_50', 'MIX_25', 'MIX_50', 'FINAL_25', 'FINAL_50', 'RND4', 'ALT_6_N64', 'ALT_25_T20']
arms = [a for a in order if a in arms]
L = slice(121, 151)
def late(j, a, b=None):
    s = j['series']; x = np.array(s[a][L]); return float(np.mean(x - np.array(s[b][L])) if b else np.mean(x))
def tab(name, fn, fmt='{:6.3f}'):
    print(f'\n== {name} (среднее по сидам; столбцы — задачи) ==')
    print(f'{"ветвь":12s}' + ''.join(f'{t:>8s}' for t in tasks) + '   среднее')
    for a in arms:
        row = []
        for t in tasks:
            v = [fn(R[k]) for k in R if k[0] == t and k[1] == a]
            v = [x for x in v if x is not None]
            row.append(np.mean(v) if v else np.nan)
        print(f'{a:12s}' + ''.join(('  ' + fmt.format(x)) if x == x else '     н/д' for x in row) + '   ' + fmt.format(np.nanmean(row)))
tab('позднее завышение показателя W_ind = c_fix − t_fix', lambda j: late(j, 'c_fix', 't_fix'))
tab('поздняя правда лучшего по показателю', lambda j: late(j, 't_fix'))
tab('поздняя правда рабочей элиты', lambda j: late(j, 't_key'))
tab('позднее рабочее завышение c_key − t_key', lambda j: late(j, 'c_key', 't_key'))
tab('поздняя правда элиты вне диапазона', lambda j: late(j, 'to_key'))
tab('заявка с усадкой минус правда (поздно)', lambda j: late(j, 'c_eb', 't_key'))
tab('поздняя средняя правда популяции', lambda j: late(j, 'mT'))
tab('позднее среднее завышение популяции mI', lambda j: late(j, 'mI'))
tab('позднее число разных программ', lambda j: late(j, 'uniq'), '{:6.0f}')
for key, nm in (('SP_I', 'отбор по показателю → завышение, S_P(I)'), ('SE_I', 'отбор по экзамену → завышение, S_E(I)'), ('SP_T', 'отбор по показателю → правда, S_P(T)'),
                ('SE_T', 'отбор по экзамену → правда, S_E(T)'), ('C_TI', 'ковариация правды и завышения'), ('V_I', 'дисперсия завышения'), ('V_T', 'дисперсия правды'),
                ('rho_fix', 'связь показателя с правдой в популяции'), ('rho_ex', 'связь экзамена с правдой в популяции')):
    tab(nm + ' — окно 91–120', lambda j, key=key: j['win'][key][3], '{:6.4f}')
print('\nпрогонов:', len(R), 'сиды:', sorted({k[2] for k in R}), 'время, с:', round(np.mean([j['sec'] for j in R.values()]), 1))
