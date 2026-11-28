"""CHILD-01: проверка самопроверки анализа внесением ошибок. Каждая испорченная копия child01_analyze.py обязана не пройти selftest.
python3 mutants.py → печатает, сколько поймано; код возврата 0, только если пойманы все."""
import subprocess, os, shutil, tempfile, sys
HERE = os.path.dirname(os.path.abspath(__file__)); src = open(os.path.join(HERE, 'child01_analyze.py'), encoding='utf-8').read()
MUTS = [
 ("LATE = (121, 150)", "LATE = (120, 149)", 'окно сдвинуто на одно поколение'),
 ("LATE = (121, 150)", "LATE = (91, 120)", 'окно не то'),
 ("return win(a('c_fix') - a('t_fix'), *LATE)", "return win(a('c_fix') - a('t_key'), *LATE)", 'завышение показателя считается от правды рабочей элиты'),
 ("return win(a('t_fix'), *LATE)", "return win(a('c_fix'), *LATE)", 'правда лучшего по показателю подменена заявкой'),
 ("return win(a('t_key'), *LATE)", "return win(a('c_key'), *LATE)", 'правда рабочей элиты подменена заявкой'),
 ("if name == 'mT': return win(a('mT'), *LATE)", "if name == 'mT': return win(a('t_key'), *LATE)", 'средняя правда популяции подменена правдой элиты'),
 ("[metric(R[(t, arm_a, s)], name) - metric(R[(t, arm_b, s)], name) for t, s in keys]", "[metric(R[(t, arm_b, s)], name) - metric(R[(t, arm_a, s)], name) for t, s in keys]", 'знак разности перевёрнут'),
 ("return keys, [-float(np.dot(qc,", "return keys, [float(np.dot(qc,", 'знак наклона перевёрнут'),
 ("diff(R, 'W_ind', 'NOISE_50', 'ALT_50', TASKS_INFL); d4", "diff(R, 'W_ind', 'ALT_50', 'NOISE_50', TASKS_INFL); d4", 'P4: ветви переставлены'),
 ("test_dir(*diff(R, 'mT', 'ALT_25', 'FINAL_25', TASKS6))", "test_dir(*diff(R, 'mT', 'ALT_25', 'FINAL_50', TASKS6))", 'P5: не та ветвь'),
 ("test_dir(*diff(R, 'mT', 'ALT_25', 'FINAL_25', TASKS6))", "test_dir(*diff(R, 'T_key', 'ALT_25', 'FINAL_25', TASKS6))", 'P5: не та мера'),
 ("for x in range(31, GENS + 1) if b[x] is not None", "for x in range(0, GENS + 1) if b[x] is not None", 'P2: первые поколения не отброшены'),
 ("b = g['bE_I'] if name == 'bI' else g['bE_T']", "b = g['bE_T'] if name == 'bI' else g['bE_I']", 'P2: градиенты по правде и по завышению переставлены'),
 ("diff(R, 'T_ind', 'ALT_50', 'NOISE_50', TASKS6))", "diff(R, 'T_ind', 'ALT_50', 'NOISE_50', TASKS_INFL))", 'P3: не тот набор задач'),
 ("out['P1a_dose_slope'] = test_dir(*neg_slope(R, 'W_ind', TASKS_INFL))", "out['P1a_dose_slope'] = test_dir(*neg_slope(R, 'W_ind', TASKS6))", 'P1: не тот набор задач'),
 ("else 'разницы нет' if (-EQ < lo and hi < EQ) else 'не решено')", "else 'не решено' if (-EQ < lo and hi < EQ) else 'разницы нет')", 'P4: вердикты переставлены'),
 ("('экзамен чистит' if d4['p_predicted'] <= S.ALPHA_SIDE else 'обратный эффект' if d4['p_opposite'] <= S.ALPHA_SIDE", "('обратный эффект' if d4['p_predicted'] <= S.ALPHA_SIDE else 'экзамен чистит' if d4['p_opposite'] <= S.ALPHA_SIDE", 'P4: стороны переставлены'),
 ("EQ = 0.05 ", "EQ = 0.5  ", 'P4: граница «разницы нет» в десять раз шире'),
 ("EQ_SENS = 0.02 ", "EQ_SENS = 0.2  ", 'P4: узкая граница в десять раз шире'),
 ("EQ_B = 0.1 ", "EQ_B = 5.0 ", 'P2: граница «слеп» в пятьдесят раз шире'),
 ("('экзамен предпочитает завышенных' if d2['p_predicted'] <= S.ALPHA_SIDE else 'экзамен чистит' if d2['p_opposite'] <= S.ALPHA_SIDE", "('экзамен чистит' if d2['p_predicted'] <= S.ALPHA_SIDE else 'экзамен предпочитает завышенных' if d2['p_opposite'] <= S.ALPHA_SIDE", 'P2: стороны переставлены'),
 ("if d.get('verdict') == 'подтверждено' and same < nt - 1:", "if d.get('verdict') == 'подтверждено' and same < nt - 4:", 'правило по задачам ослаблено'),
 ("same = sum(1 for x in d['by_task'].values() if x['mean'] > 0)", "same = sum(1 for x in d['by_task'].values() if x['mean'] < 0)", 'правило по задачам считает не тот знак'),
 ("[(a, q) for a, q in DOSES if a in INNER]", "[(a, q) for a, q in DOSES]", 'внутренний наклон считается с концами'),
 ("assert set(R) == want,", "assert True or set(R) == want,", 'проверка состава прогонов отключена'),
 ("assert j['kinds'][g] == want,", "assert True or j['kinds'][g] == want,", 'проверка расписания отключена'),
]
killed = 0
for a, b, name in MUTS:
    assert src.count(a) == 1, (name, src.count(a))
    d = tempfile.mkdtemp()
    for f in ('stats01.py', 'child01.py', 'evo01.py', 'evo02.py', 'evo03.py', 'truth.py'): shutil.copy(os.path.join(HERE, f), d)
    open(os.path.join(d, 'child01_analyze.py'), 'w', encoding='utf-8').write(src.replace(a, b))
    p = subprocess.run([sys.executable, 'child01_analyze.py', 'selftest'], cwd=d, capture_output=True, text=True)
    dead = p.returncode != 0; killed += dead
    if not dead: print('  ПРОПУЩЕН ' + name)
    shutil.rmtree(d)
print(f'поймано {killed} из {len(MUTS)}'); sys.exit(0 if killed == len(MUTS) else 1)
