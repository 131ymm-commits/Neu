# Часть 3: промпты слишком велики для аргументов workflow. Генерирует файлы run/runner3_<k>.js:
# код humor01_runner.js (args → ARGS) + строка `const ARGS = {...}` с частью вызовов, каждая пачка ≤ LIMIT байт.
import json, sys
LIMIT = 450_000
D = sys.argv[1]
calls = json.load(open(f'{D}/calls3.json'))['calls']
src = open('humor01_runner.js').read()
head, body = src.split('\n// args:', 1)
packs, cur, size = [], [], 0
for c in calls:
    n = len(json.dumps(c, ensure_ascii=False).encode())
    if cur and size + n > LIMIT: packs.append(cur); cur, size = [], 0
    cur.append(c); size += n
packs.append(cur)
for k, p in enumerate(packs, 1):
    a = json.dumps(dict(part=3, calls=p), ensure_ascii=False)
    out = head.replace("name: 'humor01-runner'", f"name: 'humor01-runner3-{k}'") + f'\nconst ARGS = {a}\n// args:' + body.replace('args.', 'ARGS.')
    open(f'{D}/runner3_{k}.js', 'w').write(out)
    print(k, len(p), [c['alias'] for c in p], len(out.encode()))
