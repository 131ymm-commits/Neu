# HIVE-01: промпты голов улья и пачки вызовов.
import json, os, sys

NO_TOOLS = 'Не используй никакие инструменты и не открывай файлы: оценивай сам, опираясь только на текст ниже.'
ASK = ('Для каждого вопроса нужна оценка, точный подсчёт не требуется. Для каждого ID верни: estimate — лучшая оценка (число); '
       'lo и hi — границы интервала, в который правильный ответ попадает с вероятностью 80 %; note — метод одной фразой.')


def qblock(qs):
    return '\n'.join(f'[{q["id"]}] {q["text"]}' for q in qs)


def head_prompt(qs, laws=(), role=None, seen=None):
    L = ('Законы улья, в котором ты работаешь (соблюдай их):\n' + '\n'.join(f'{i + 1}. {x}' for i, x in enumerate(laws)) + '\n\n') if laws else ''
    R = f'Твоя роль в улье: {role}\n\n' if role else ''
    S = ('Первые оценки других голов улья:\n' + seen + '\n\n') if seen else ''
    return f'{NO_TOOLS}\n\n{L}{R}{S}Вопросы:\n{qblock(qs)}\n\n{ASK}'


def bundle(D, tag, calls):
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hive_runner.js')).read()
    head, body = src.split('\n// args:', 1)
    a = json.dumps(dict(part=tag, calls=calls), ensure_ascii=False)
    open(os.path.join(D, f'runner_{tag}.js'), 'w').write(head.replace("name: 'hive-runner'", f"name: 'hive-{tag}'") + f'\nconst ARGS = {a}\n// args:' + body.replace('args.', 'ARGS.'))
    json.dump(dict(calls=calls), open(os.path.join(D, f'calls_{tag}.json'), 'w'), ensure_ascii=False, indent=0)
    print(tag, len(calls), 'вызовов')


if __name__ == '__main__':
    D = sys.argv[1]
    qs = json.load(open(f'{D}/questions.json'))
    ids = [q['id'] for q in qs]
    bundle(D, 'pilot', [dict(label=f'R{k}', alias=f'h{k}', kind='batch', ids=ids, prompt=head_prompt(qs)) for k in (1, 2, 3)])
