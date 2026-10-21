# PRECOND-01: сухой прогон цепочки пилота на заглушках (ворота CLAUDE.md). Головы не вызываются.
# Заглушка: голос попадает в лучшего с вероятностью 0,25, а если включена PROCEDURE — 0,6; при REFUSE отказ в 20 % голосов.
# Проверки: 96 заданий; анализ видит заложенное действие PROCEDURE и не видит его у остальных; отказы → A0; сбой → регрет 1.
import json, os, random, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); env = dict(os.environ, PRECOND_TAG='dry'); ok = True
def run(*a): return subprocess.run([sys.executable, f'{HERE}/pilot_precond.py', *a], env=env, capture_output=True, text=True, check=True).stdout
def check(c, m):
    global ok; print(('ОК  ' if c else 'ОШИБКА  ') + m); ok &= bool(c)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '2026-10-07_SELECT-01'))
import harness as H  # noqa: E402
run('jobs'); js = [json.loads(l) for l in open(f'{HERE}/run/dry_jobs.jsonl')]; D = json.load(open(f'{HERE}/run/dry_design.json'))
check(len(js) == 96, f'заданий {len(js)}')
rng = random.Random(1)
with open(f'{HERE}/run/dry_out.jsonl', 'w') as fh:
    for j in js:
        t, p, _ = j['id'].split('|'); on = D[p]; tr = json.load(open(f'/root/select_secret/truth/{t}.json')); best = tr.index(max(tr)); pm = H.perm(t)
        if j['id'] == 'WH_8001|P03|0':
            fh.write(json.dumps(dict(id=j['id'], result=None, error='сбой (заглушка)', out=0)) + '\n'); continue
        c = -1 if 'REFUSE' in on and rng.random() < 0.2 else (pm.index(best) if rng.random() < (0.6 if 'PROCEDURE' in on else 0.25) else rng.randrange(8))
        res = dict(choice=c) | (dict(p_best=0.7) if 'CONF' in on else {})
        fh.write(json.dumps(dict(id=j['id'], result=res, error=None, out=4000 + 1500 * ('PROCEDURE' in on), models={'stub': 1}), ensure_ascii=False) + '\n')
run('collect'); run('analyze'); an = json.load(open(f'{HERE}/dry_analysis.json'))
e = an['effects']
check(e['PROCEDURE']['regret'] < -0.15, f'действие PROCEDURE найдено: {e["PROCEDURE"]["regret"]}')
check(all(abs(v['regret']) < abs(e['PROCEDURE']['regret']) for k, v in e.items() if k != 'PROCEDURE'), 'у остальных ингредиентов действие меньше заложенного')
check(an['lost'] == 1, f'сбойный вызов посчитан потерянным: {an["lost"]}')
check(an['refused'] > 0 and e['REFUSE']['refusal'] > 0, f'отказы учтены: {an["refused"]}')
check(an['conf']['n'] > 0 and an['conf']['mean_p'] == 0.7, f'самооценка собрана: {an["conf"]}')
check(e['PROCEDURE']['out'] == 1500 or abs(e['PROCEDURE']['out'] - 1500) < 200, f'длина ответа по ингредиенту: {e["PROCEDURE"]["out"]}')
for f in ('dry_jobs.jsonl', 'dry_design.json', 'dry_out.jsonl'): os.remove(f'{HERE}/run/{f}')
os.remove(f'{HERE}/evals/dry.jsonl'); os.remove(f'{HERE}/dry_analysis.json')
print('СУХОЙ ПРОГОН:', 'ПРОЙДЕН' if ok else 'ЕСТЬ ОШИБКИ'); sys.exit(0 if ok else 1)
