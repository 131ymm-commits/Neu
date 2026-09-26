# HIVE-01: сборка ARGS и файла workflow для полного прогона (или сухого).
import json, sys, os
from hive_q import make, FAMS
from hive_core import SEED_LAWS, ROLES

INIT = dict(laws=[SEED_LAWS[0], SEED_LAWS[1], SEED_LAWS[6], SEED_LAWS[8]], roles=ROLES[:3], delphi=False, agg='median')
NO_TOOLS = 'Не используй никакие инструменты и не открывай файлы: оценивай сам, опираясь только на текст ниже.'


def build(D, n_gens=5, per_fam_gen=2, per_fam_test=4, gen_seed=1000, test_seed=5000):
    gens = [[dict(make(f, gen_seed + 100 * g + i), id=f'{f}-{gen_seed + 100 * g + i}') for f in FAMS for i in range(per_fam_gen)] for g in range(n_gens)]
    test = [dict(make(f, test_seed + i), id=f'{f}-{test_seed + i}') for f in FAMS for i in range(per_fam_test)]
    for qs in gens + [test]:
        for q in qs: q.pop('kind', None)
    args = dict(gens=gens, test=test, init=INIT, hives=['A', 'B'], no_tools=NO_TOOLS, max_laws=8)
    os.makedirs(D, exist_ok=True)
    json.dump(args, open(f'{D}/args.json', 'w'), ensure_ascii=False, indent=0)
    src = open('hive_evolve.js').read()
    head, body = src.split('\n// ARGS:', 1)
    open(f'{D}/evolve.js', 'w').write(head + f'\nconst ARGS = {json.dumps(args, ensure_ascii=False)}\n// ARGS:' + body)
    print('поколений', len(gens), 'вопросов на поколение', len(gens[0]), 'тест', len(test), 'байт', os.path.getsize(f'{D}/evolve.js'))


if __name__ == '__main__':
    build(sys.argv[1])
