# PERSUADE-01: тесты входа мутатора (слепота к правде), паритета JS/Python, разбора ответа и формулы бюджета.
#   python3 -m unittest test_persuade -v     (из папки опыта)
import json, os, re, subprocess, unittest
import persuade as P

HERE = os.path.dirname(os.path.abspath(__file__))
TRUTHS = [123457, 98765432, 4410, 777001]
TASKS = ['Сколько пар простых чисел-близнецов (p, p + 2) с p в отрезке от 460492353 до 460592353?',
         'Итерация x → (x² + 895) mod 891442427, x_0 = 562962161. Сделай ровно 12 шагов (вычисли x_1, …, x_12). Чему равно x_12?']
ANSWERS = ['x_1 = 5551212\nfinal=123457', 'Я уверен.\nfinal=98765432']


def poisoned_pop():
    """Особи с «ядовитыми» полями: всё, чего мутатор видеть не должен, лежит рядом с текстом промпта и средней p."""
    pop = []
    for i, (pid, text) in enumerate(P.PROMPTS):
        pop.append(dict(prompt=text, mean_p=0.1 * i + 0.05, id=pid, truth=TRUTHS[i % 4], truths=TRUTHS, tasks=TASKS, answers=ANSWERS,
                        p_by_task={'A-TWIN': 0.91, 'A-MODSQ': 0.12}, judge_reasons=['судья: верно, 123457'], T=0.5, finals=[4410, 777001]))
    pop.append(dict(pop[0]))                                   # дубликат промпта — должен уйти
    pop.append(dict(pop[1], prompt='  ' + pop[1]['prompt'].upper() + '  '))   # тот же текст с другим регистром и пробелами — тоже дубликат
    return pop


class MutatorInput(unittest.TestCase):
    def test_no_truth_tasks_answers(self):
        s = P.mutator_input(poisoned_pop())
        toks = set(re.findall(r'\d+', s))
        for v in TRUTHS + [5551212, 4410, 777001]: self.assertNotIn(str(v), toks)
        for t in TASKS: self.assertNotIn(t, s)
        for a in ANSWERS: self.assertNotIn(a, s)
        for w in ('final=', 'x_1', 'A-TWIN', 'судья: верно', 'близнец', 'mod 891442427', '0.91', '0.12'): self.assertNotIn(w, s)

    def test_only_prompt_and_mean_p(self):
        pop = poisoned_pop(); s = P.mutator_input(pop)
        allowed = '\n\n'.join(f'Промпт {i + 1} (средняя оценка судьи {P.fmt3(x["mean_p"])}):\n{x["prompt"]}' for i, x in
                              enumerate(sorted(pop[:len(P.PROMPTS)], key=lambda x: -x['mean_p'])))
        self.assertEqual(s, allowed)                            # вход — ровно пары (текст, средняя p), по убыванию p, без дубликатов
        self.assertEqual(s.count('Промпт '), len(P.PROMPTS))

    def test_extra_fields_do_not_change_input(self):
        clean = [dict(prompt=x['prompt'], mean_p=x['mean_p']) for x in poisoned_pop()]
        self.assertEqual(P.mutator_input(clean), P.mutator_input(poisoned_pop()))

    def test_forbid_catches_answer_number_in_prompt_text(self):
        pop = [dict(prompt='Ответ всегда 123457, пиши его.', mean_p=0.9)]
        with self.assertRaises(P.LeakError): P.mutator_input(pop, forbid=TRUTHS)
        P.mutator_input([dict(prompt='Решай аккуратно.', mean_p=0.9)], forbid=TRUTHS)

    def test_bad_mean_p(self):
        with self.assertRaises(ValueError): P.mutator_input([dict(prompt='x', mean_p=1.5)])

    def test_js_parity(self):
        """mutatorInput из шаблона скрипта (JS) даёт побайтно ту же строку и тот же FNV-хэш, что Python."""
        src = open(os.path.join(HERE, 'persuade_pilot_step.js')).read()
        fn = src.split('// <mutatorInput>')[1].split('// </mutatorInput>')[0]
        fnv = re.search(r'const fnv = .*\n', src).group(0)
        pop = poisoned_pop() + [dict(prompt='Граница округления', mean_p=0.5625), dict(prompt='Ещё граница', mean_p=0.0625)]
        js = fn + fnv + f'const pop = {json.dumps(pop, ensure_ascii=False)};\nconst s = mutatorInput(pop);\nprocess.stdout.write(JSON.stringify({{s, h: fnv(s).toString(16)}}))'
        r = subprocess.run(['node', '-e', js], capture_output=True, text=True, check=True)
        got = json.loads(r.stdout); py = P.mutator_input(pop)
        self.assertEqual(got['s'], py); self.assertEqual(got['h'], format(P.fnv(py), 'x'))


class Parse(unittest.TestCase):
    def test_statuses(self):
        self.assertEqual(P.parse('x_1 = 5\nfinal=12 345')['value'], 12345)
        self.assertEqual(P.parse('final=1\nfinal=1')['status'], 'multi')
        self.assertEqual(P.parse('Ответ: 7')['status'], 'none')
        self.assertEqual(P.parse('final=около 7')['status'], 'bad')
        self.assertEqual(P.parse('x_1 = 3^2 + 1 = 10\nx_2 = 101\nfinal=101')['steps'], {1: 10, 2: 101})

    def test_step_check(self):
        t = P.make_task('MODSQ', 5)
        ch = P.modsq_chain(t['params']['x0'], t['params']['c'], t['params']['p'], t['params']['L'])
        self.assertEqual(P.step_check(t, {1: ch[1], 2: ch[2] + 1}), 0.5)


class Truth(unittest.TestCase):
    def test_second_method(self):
        for f in P.FAMS:
            for s in (1, 2):
                t = P.make_task(f, 900 + s); self.assertEqual(P.truth_second(t), t['truth'], (f, s))


class Budget(unittest.TestCase):
    def test_engineer_table(self):
        self.assertEqual(P.E_calls(6, 3), 912); self.assertEqual(P.E_calls(10, 2), 1072)
        self.assertEqual(250 + 912 + 31 * 43, 2495); self.assertEqual((2500 - 250 - 912) // 31, 43); self.assertEqual((2500 - 250 - 1072) // 31, 38)

    def test_plan_under_cap(self):
        self.assertLessEqual(P.pilot_plan()['planned'], P.CAP)

    def test_n_min_sanity(self):   # SD = 0,2, δ = 0,1: нормальное приближение (1,645 + 0,842)² · 4 ≈ 24,7 → t-тест даёт 26–27
        self.assertIn(P.n_min(0.2), (26, 27))


if __name__ == '__main__': unittest.main()
